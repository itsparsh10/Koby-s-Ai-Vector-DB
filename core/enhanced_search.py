"""
Enhanced Search Module
This module provides dual search functionality combining FAISS index and MongoDB user contributions
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .utils import search_similar_chunks
from .mongodb_utils import search_similar_contributions, connect_to_mongodb

logger = logging.getLogger(__name__)


def enhanced_search_with_contributions(
    query: str, 
    k: Optional[int] = None, 
    similarity_threshold: Optional[float] = None,
    include_contributions: bool = True,
    contribution_limit: int = 5
) -> Dict[str, Any]:
    """
    Enhanced search that combines FAISS index results with MongoDB user contributions
    Implements fallback mechanism: if FAISS results are poor, prioritize MongoDB results
    
    Args:
        query: Search query
        k: Number of FAISS results to return
        similarity_threshold: Similarity threshold for FAISS search
        include_contributions: Whether to include user contributions
        contribution_limit: Maximum number of contributions to include
    
    Returns:
        Dictionary containing combined search results
    """
    try:
        logger.info(f"Starting enhanced search for query: {query[:100]}...")
        
        # Step 1: Search FAISS index (existing functionality)
        faiss_result = search_similar_chunks(query, k, similarity_threshold)
        faiss_chunks = faiss_result.get('chunks', []) if faiss_result['success'] else []
        
        # Step 2: Search MongoDB contributions (ALWAYS search, regardless of FAISS results)
        contribution_results = []
        if include_contributions:
            try:
                logger.info(f"Searching MongoDB contributions for query: '{query}'")
                contribution_results = search_similar_contributions(
                    query, 
                    limit=contribution_limit,
                    min_rating=0.0  # Include all contributions
                )
                logger.info(f"Found {len(contribution_results)} user contributions")
                
                # Log contribution details for debugging
                for i, contrib in enumerate(contribution_results):
                    logger.info(f"  Contribution {i+1}: {contrib.get('question', '')[:50]}... (similarity: {contrib.get('similarity_score', 0):.3f})")
                    
            except Exception as e:
                logger.error(f"Failed to search contributions: {e}")
                contribution_results = []
        
        # Step 3: Determine if we should prioritize MongoDB results
        faiss_quality = _assess_faiss_quality(faiss_chunks, query)
        mongodb_quality = _assess_mongodb_quality(contribution_results, query)
        
        logger.info(f"FAISS quality: {faiss_quality}, MongoDB quality: {mongodb_quality}")
        
        # Step 4: Create combined context with proper prioritization
        if mongodb_quality > faiss_quality and contribution_results:
            # MongoDB has better results, prioritize them
            logger.info("Prioritizing MongoDB results over FAISS")
            combined_context = _create_prioritized_context(contribution_results, faiss_chunks, prioritize_mongodb=True)
        else:
            # Use standard combination
            combined_context = _create_combined_context(faiss_chunks, contribution_results)
        
        # Step 5: Prepare search metadata
        search_metadata = {
            'faiss_count': len(faiss_chunks),
            'contribution_count': len(contribution_results),
            'search_time': faiss_result.get('search_time', 0) if faiss_result['success'] else 0,
            'has_contributions': len(contribution_results) > 0,
            'total_sources': len(faiss_chunks) + len(contribution_results),
            'faiss_quality': faiss_quality,
            'mongodb_quality': mongodb_quality,
            'prioritized_mongodb': mongodb_quality > faiss_quality and contribution_results
        }
        
        logger.info(f"Enhanced search completed: {search_metadata['faiss_count']} FAISS + {search_metadata['contribution_count']} contributions")
        
        return {
            'success': True,
            'faiss_results': faiss_chunks,
            'contribution_results': contribution_results,
            'combined_context': combined_context,
            'search_metadata': search_metadata,
            'original_faiss_result': faiss_result
        }
        
    except Exception as e:
        logger.error(f"Error in enhanced search: {e}")
        return {
            'success': False,
            'error': str(e),
            'faiss_results': [],
            'contribution_results': [],
            'combined_context': '',
            'search_metadata': {
                'faiss_count': 0,
                'contribution_count': 0,
                'search_time': 0
            }
        }


def _create_combined_context(faiss_chunks: List[Dict], contributions: List[Dict]) -> str:
    """
    Create a combined context string from FAISS results and user contributions
    
    Args:
        faiss_chunks: Results from FAISS search
        contributions: Results from MongoDB search
    
    Returns:
        Combined context string
    """
    context_parts = []
    
    # Add user contributions first (they're more relevant and recent)
    if contributions:
        contribution_contexts = []
        for i, contrib in enumerate(contributions, 1):
            question = contrib.get('question', '')
            answer = contrib.get('answer', '')
            rating = contrib.get('rating', 0.0)
            similarity = contrib.get('similarity_score', 0.0)
            
            contrib_text = f"USER CONTRIBUTION #{i}:\n"
            if question:
                contrib_text += f"Question: {question}\n"
            contrib_text += f"Answer: {answer}\n"
            contrib_text += f"Rating: {rating}/5.0 (Similarity: {similarity:.2f})"
            
            contribution_contexts.append(contrib_text)
        
        contributions_text = '\n\n'.join(contribution_contexts)
        context_parts.append(f"USER CONTRIBUTIONS AND ENHANCEMENTS:\n{contributions_text}")
    
    # Add FAISS results (original knowledge base)
    if faiss_chunks:
        faiss_contexts = []
        for i, chunk in enumerate(faiss_chunks, 1):
            text = chunk.get('text', '')
            filename = chunk.get('filename', 'Unknown')
            similarity = chunk.get('similarity', 0.0)
            
            faiss_text = f"DOCUMENT #{i} (from {filename}):\n{text}\n(Similarity: {similarity:.2f})"
            faiss_contexts.append(faiss_text)
        
        faiss_context = '\n\n'.join(faiss_contexts)
        context_parts.append(f"ORIGINAL KNOWLEDGE BASE:\n{faiss_context}")
    
    # Combine all parts
    combined_context = '\n\n'.join(context_parts)
    
    return combined_context


def _assess_faiss_quality(faiss_chunks: List[Dict], query: str) -> float:
    """
    Assess the quality of FAISS search results
    
    Args:
        faiss_chunks: FAISS search results
        query: Original search query
    
    Returns:
        Quality score between 0.0 and 1.0
    """
    if not faiss_chunks:
        return 0.0
    
    # Calculate average similarity
    similarities = [chunk.get('similarity', 0.0) for chunk in faiss_chunks]
    avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
    
    # Bonus for having multiple results
    count_bonus = min(len(faiss_chunks) / 5.0, 0.2)  # Max 0.2 bonus for 5+ results
    
    # Quality score combines similarity and count
    quality = min(avg_similarity + count_bonus, 1.0)
    
    return quality


def _assess_mongodb_quality(contributions: List[Dict], query: str) -> float:
    """
    Assess the quality of MongoDB search results
    
    Args:
        contributions: MongoDB search results
        query: Original search query
    
    Returns:
        Quality score between 0.0 and 1.0
    """
    if not contributions:
        return 0.0
    
    # Calculate average similarity
    similarities = [contrib.get('similarity_score', 0.0) for contrib in contributions]
    avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
    
    # Bonus for high-rated contributions
    ratings = [contrib.get('rating', 0.0) for contrib in contributions]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
    rating_bonus = (avg_rating / 5.0) * 0.3  # Max 0.3 bonus for 5-star rating
    
    # Bonus for having multiple results
    count_bonus = min(len(contributions) / 3.0, 0.2)  # Max 0.2 bonus for 3+ results
    
    # Quality score combines similarity, rating, and count
    quality = min(avg_similarity + rating_bonus + count_bonus, 1.0)
    
    return quality


def _create_prioritized_context(contributions: List[Dict], faiss_chunks: List[Dict], prioritize_mongodb: bool = True) -> str:
    """
    Create context with MongoDB contributions prioritized
    
    Args:
        contributions: MongoDB search results
        faiss_chunks: FAISS search results
        prioritize_mongodb: Whether to prioritize MongoDB results
    
    Returns:
        Prioritized context string
    """
    context_parts = []
    
    if prioritize_mongodb and contributions:
        # MongoDB contributions first with emphasis
        contribution_contexts = []
        for i, contrib in enumerate(contributions, 1):
            question = contrib.get('question', '')
            answer = contrib.get('answer', '')
            rating = contrib.get('rating', 0.0)
            similarity = contrib.get('similarity_score', 0.0)
            
            contrib_text = f"🎯 HIGHLY RELEVANT USER CONTRIBUTION #{i}:\n"
            if question:
                contrib_text += f"Question: {question}\n"
            contrib_text += f"Answer: {answer}\n"
            contrib_text += f"Rating: {rating}/5.0 (Similarity: {similarity:.2f})"
            
            contribution_contexts.append(contrib_text)
        
        contributions_text = '\n\n'.join(contribution_contexts)
        context_parts.append(f"USER CONTRIBUTIONS (PRIORITIZED):\n{contributions_text}")
        
        # Add FAISS results as supplementary
        if faiss_chunks:
            faiss_contexts = []
            for i, chunk in enumerate(faiss_chunks, 1):
                text = chunk.get('text', '')
                filename = chunk.get('filename', 'Unknown')
                similarity = chunk.get('similarity', 0.0)
                
                faiss_text = f"DOCUMENT #{i} (from {filename}):\n{text}\n(Similarity: {similarity:.2f})"
                faiss_contexts.append(faiss_text)
            
            faiss_context = '\n\n'.join(faiss_contexts)
            context_parts.append(f"SUPPLEMENTARY DOCUMENTATION:\n{faiss_context}")
    else:
        # Standard combination
        return _create_combined_context(faiss_chunks, contributions)
    
    return '\n\n'.join(context_parts)


def get_enhanced_sources(faiss_chunks: List[Dict], contributions: List[Dict]) -> List[Dict]:
    """
    Get combined sources information for API response
    
    Args:
        faiss_chunks: FAISS search results
        contributions: MongoDB contribution results
    
    Returns:
        List of source information dictionaries
    """
    sources = []
    
    # Add FAISS sources
    for chunk in faiss_chunks:
        source_info = {
            'filename': chunk.get('filename', 'Unknown'),
            'page': chunk.get('page', 'Unknown'),
            'similarity': chunk.get('similarity', 0.0),
            'source_type': 'original_document',
            'text_preview': chunk.get('text', '')[:200] + '...' if len(chunk.get('text', '')) > 200 else chunk.get('text', '')
        }
        if source_info not in sources:
            sources.append(source_info)
    
    # Add contribution sources
    for contrib in contributions:
        source_info = {
            'filename': 'User Contribution',
            'page': 'N/A',
            'similarity': contrib.get('similarity_score', 0.0),
            'source_type': 'user_contribution',
            'contribution_id': contrib.get('id'),
            'rating': contrib.get('rating', 0.0),
            'usage_count': contrib.get('usage_count', 0),
            'text_preview': contrib.get('answer', '')[:200] + '...' if len(contrib.get('answer', '')) > 200 else contrib.get('answer', '')
        }
        sources.append(source_info)
    
    return sources


def prioritize_enhanced_results(faiss_chunks: List[Dict], contributions: List[Dict]) -> List[Dict]:
    """
    Prioritize and rank combined results
    
    Args:
        faiss_chunks: FAISS search results
        contributions: MongoDB contribution results
    
    Returns:
        Prioritized list of results
    """
    prioritized_results = []
    
    # Sort contributions by rating and usage count
    sorted_contributions = sorted(
        contributions, 
        key=lambda x: (x.get('rating', 0), x.get('usage_count', 0)), 
        reverse=True
    )
    
    # Add top contributions first (they're user-enhanced)
    for contrib in sorted_contributions[:2]:  # Top 2 contributions
        contrib['priority'] = 'high'
        contrib['source'] = 'user_contribution'
        prioritized_results.append(contrib)
    
    # Add FAISS results
    for chunk in faiss_chunks:
        chunk['priority'] = 'medium'
        chunk['source'] = 'original_document'
        prioritized_results.append(chunk)
    
    # Add remaining contributions
    for contrib in sorted_contributions[2:]:
        contrib['priority'] = 'low'
        contrib['source'] = 'user_contribution'
        prioritized_results.append(contrib)
    
    return prioritized_results


def analyze_search_effectiveness(query: str, results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze the effectiveness of the enhanced search
    
    Args:
        query: Original search query
        results: Search results from enhanced_search_with_contributions
    
    Returns:
        Analysis dictionary
    """
    try:
        faiss_count = results.get('search_metadata', {}).get('faiss_count', 0)
        contribution_count = results.get('search_metadata', {}).get('contribution_count', 0)
        
        analysis = {
            'query_length': len(query),
            'faiss_results_found': faiss_count > 0,
            'contributions_found': contribution_count > 0,
            'total_sources': faiss_count + contribution_count,
            'search_effectiveness': 'high' if (faiss_count + contribution_count) >= 3 else 'medium' if (faiss_count + contribution_count) >= 1 else 'low',
            'has_enhanced_content': contribution_count > 0,
            'recommendation': _get_search_recommendation(faiss_count, contribution_count)
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing search effectiveness: {e}")
        return {
            'error': str(e),
            'search_effectiveness': 'unknown'
        }


def _get_search_recommendation(faiss_count: int, contribution_count: int) -> str:
    """Get recommendation based on search results"""
    if faiss_count == 0 and contribution_count == 0:
        return "No relevant information found. Consider rephrasing your question or adding more specific keywords."
    elif faiss_count > 0 and contribution_count > 0:
        return "Great! Found both original documentation and user contributions for comprehensive answers."
    elif faiss_count > 0:
        return "Found relevant information in the original documentation."
    else:
        return "Found user contributions that may help answer your question."
