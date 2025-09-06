"""
MongoDB Utility Functions for User Contributions and Feedback
This module provides functions to interact with MongoDB for user contributions
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
from mongoengine import connect, disconnect
from django.conf import settings

from .feedback_models import UserContribution, FeedbackAnalytics

logger = logging.getLogger(__name__)


def connect_to_mongodb():
    """Connect to MongoDB using Django settings"""
    try:
        # Disconnect if already connected
        disconnect()
        
        # Connect with settings
        connect(
            db=settings.MONGODB_DB,
            host=settings.MONGODB_HOST,
            port=settings.MONGODB_PORT,
            username=settings.MONGODB_USERNAME if settings.MONGODB_USERNAME else None,
            password=settings.MONGODB_PASSWORD if settings.MONGODB_PASSWORD else None,
            authentication_source='admin' if settings.MONGODB_USERNAME else None
        )
        logger.info("Successfully connected to MongoDB")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return False


def search_similar_contributions(query: str, limit: int = 5, min_rating: float = 0.0) -> List[Dict[str, Any]]:
    """
    Search for similar user contributions in MongoDB
    
    Args:
        query: Search query
        limit: Maximum number of results
        min_rating: Minimum rating threshold
    
    Returns:
        List of similar contributions
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        logger.info(f"Searching contributions for query: '{query}' (limit: {limit}, min_rating: {min_rating})")
        
        # Extract keywords from query
        query_keywords = _extract_keywords(query)
        logger.info(f"Extracted keywords: {query_keywords}")
        
        # Search using multiple strategies
        results = []
        seen_ids = set()
        
        # Strategy 1: Direct question matching (exact and partial)
        normalized_query = _normalize_text(query)
        logger.info(f"Normalized query: '{normalized_query}'")
        
        # Get all approved contributions first
        all_contributions = UserContribution.objects(
            is_approved="approved",
            rating__gte=min_rating
        ).order_by('-rating', '-usage_count')
        
        approved_count = all_contributions.count()
        logger.info(f"Found {approved_count} approved contributions")
        
        # Only use approved contributions for search results
        # Pending contributions should not appear in search until approved by admin
        
        # Strategy 2: Question similarity (lowered threshold for better matching)
        for contrib in all_contributions:
            if len(results) >= limit:
                break
            
            contrib_id = str(contrib.id)
            if contrib_id in seen_ids:
                continue
            
            # Calculate similarity with question
            question_similarity = _calculate_text_similarity(normalized_query, _normalize_text(contrib.question))
            
            # Calculate similarity with answer
            answer_similarity = _calculate_text_similarity(normalized_query, _normalize_text(contrib.answer))
            
            # Use the higher similarity score
            max_similarity = max(question_similarity, answer_similarity)
            
            # Very low threshold for better matching - prioritize finding user contributions
            if max_similarity > 0.05:  # Only 5% similarity threshold
                contrib_dict = contrib.to_dict()
                contrib_dict['similarity_score'] = max_similarity
                contrib_dict['question_similarity'] = question_similarity
                contrib_dict['answer_similarity'] = answer_similarity
                results.append(contrib_dict)
                seen_ids.add(contrib_id)
                logger.info(f"Found match: {contrib.question[:50]}... (similarity: {max_similarity:.3f})")
        
        # Strategy 3: Keyword matching (if we still need more results)
        if len(results) < limit and query_keywords:
            for contrib in all_contributions:
                if len(results) >= limit:
                    break
                
                contrib_id = str(contrib.id)
                if contrib_id in seen_ids:
                    continue
                
                # Check if any keywords match
                contrib_text = _normalize_text(f"{contrib.question} {contrib.answer}")
                keyword_matches = sum(1 for keyword in query_keywords if keyword in contrib_text)
                
                if keyword_matches > 0:
                    # Calculate keyword-based similarity
                    keyword_similarity = keyword_matches / len(query_keywords)
                    
                    if keyword_similarity > 0.05:  # At least 5% keyword match
                        contrib_dict = contrib.to_dict()
                        contrib_dict['similarity_score'] = keyword_similarity
                        contrib_dict['keyword_matches'] = keyword_matches
                        results.append(contrib_dict)
                        seen_ids.add(contrib_id)
                        logger.info(f"Found keyword match: {contrib.question[:50]}... (keywords: {keyword_matches})")
        
        # Strategy 4: Text search (if MongoDB text index is available)
        if len(results) < limit:
            try:
                # Use same fallback logic for text search
                text_query = {"$text": {"$search": query}}
                if approved_count > 0:
                    text_query["is_approved"] = "approved"
                else:
                    text_query["is_approved"] = {"$in": ["approved", "pending"]}
                text_query["rating"] = {"$gte": min_rating}
                
                text_results = UserContribution.objects(
                    __raw__=text_query
                ).limit(limit - len(results))
                
                for contrib in text_results:
                    contrib_id = str(contrib.id)
                    if contrib_id not in seen_ids:
                        contrib_dict = contrib.to_dict()
                        contrib_dict['similarity_score'] = 0.5  # Default score for text search
                        contrib_dict['search_method'] = 'text_index'
                        results.append(contrib_dict)
                        seen_ids.add(contrib_id)
                        logger.info(f"Found text index match: {contrib.question[:50]}...")
                        
            except Exception as e:
                logger.warning(f"Text search not available: {e}")
        
        # Sort by similarity score, then by rating and usage count
        results.sort(key=lambda x: (x.get('similarity_score', 0), x.get('rating', 0), x.get('usage_count', 0)), reverse=True)
        
        # Increment usage count for returned results
        for result in results[:3]:  # Only increment for top 3 results
            try:
                contrib = UserContribution.objects.get(id=result['id'])
                contrib.increment_usage()
            except Exception as e:
                logger.warning(f"Failed to increment usage for contribution {result['id']}: {e}")
        
        logger.info(f"Found {len(results)} similar contributions for query: {query[:50]}...")
        for i, result in enumerate(results):
            logger.info(f"  {i+1}. {result.get('question', '')[:50]}... (similarity: {result.get('similarity_score', 0):.3f})")
        
        return results[:limit]
        
    except Exception as e:
        logger.error(f"Error searching similar contributions: {e}")
        return []


def store_user_contribution(contribution_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store a new user contribution in MongoDB
    
    Args:
        contribution_data: Dictionary containing contribution data
    
    Returns:
        Dictionary with success status and contribution ID
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        # Create new contribution
        contribution = UserContribution(
            question=contribution_data.get('question', ''),
            original_question=contribution_data.get('original_question', ''),
            answer=contribution_data.get('message', ''),
            question_type=contribution_data.get('type', 'general'),
            user_id=contribution_data.get('user_id', ''),
            user_email=contribution_data.get('email', ''),
            improvement_type=contribution_data.get('improvement_type', 'enhancement'),
            rating=contribution_data.get('rating', 0.0),
            is_approved="pending"  # New contributions need admin approval
        )
        
        # Save contribution
        contribution.save()
        
        # Update analytics
        _update_analytics(contribution)
        
        logger.info(f"Successfully stored user contribution: {contribution.id}")
        
        return {
            'success': True,
            'contribution_id': str(contribution.id),
            'message': 'Contribution stored successfully'
        }
        
    except Exception as e:
        logger.error(f"Error storing user contribution: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to store contribution'
        }


def get_contribution_analytics(question_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get analytics for user contributions
    
    Args:
        question_type: Optional filter by question type
    
    Returns:
        Dictionary with analytics data
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        if question_type:
            analytics = FeedbackAnalytics.objects(question_type=question_type).first()
        else:
            # Get overall analytics
            analytics = FeedbackAnalytics.objects().first()
        
        if analytics:
            return analytics.to_dict()
        else:
            return {
                'question_type': question_type or 'overall',
                'total_contributions': 0,
                'average_rating': 0.0,
                'most_common_questions': [],
                'last_updated': None
            }
            
    except Exception as e:
        logger.error(f"Error getting contribution analytics: {e}")
        return {
            'error': str(e),
            'total_contributions': 0,
            'average_rating': 0.0
        }


def _extract_keywords(text: str) -> List[str]:
    """Extract keywords from text for similarity matching"""
    # Convert to lowercase and remove special characters
    clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
    
    # Split into words and filter out common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
        'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'can', 'what', 'how', 'when',
        'where', 'why', 'who', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
        'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her',
        'its', 'our', 'their', 'am', 'not', 'so', 'if', 'then', 'than', 'as', 'up', 'down',
        'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
        'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
        'other', 'some', 'such', 'no', 'nor', 'only', 'own', 'same', 'so', 'than', 'too',
        'very', 'just', 'now', 'get', 'got', 'go', 'goes', 'went', 'come', 'came', 'see',
        'saw', 'know', 'knew', 'think', 'thought', 'take', 'took', 'give', 'gave', 'make',
        'made', 'find', 'found', 'tell', 'told', 'ask', 'asked', 'work', 'worked', 'seem',
        'seemed', 'feel', 'felt', 'try', 'tried', 'leave', 'left', 'call', 'called'
    }
    
    words = [word for word in clean_text.split() if word not in stop_words and len(word) > 2]
    
    # Return unique keywords (limit to 15 most relevant for better matching)
    return list(set(words))[:15]


def _normalize_text(text: str) -> str:
    """Normalize text for similarity comparison"""
    # Convert to lowercase, remove special characters, normalize whitespace
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate enhanced text similarity using multiple methods"""
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    if not words1 or not words2:
        return 0.0
    
    # Method 1: Jaccard similarity (word overlap)
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    jaccard_similarity = len(intersection) / len(union) if union else 0.0
    
    # Method 2: Substring matching (for partial word matches)
    substring_matches = 0
    for word1 in words1:
        for word2 in words2:
            if len(word1) > 3 and len(word2) > 3:  # Only for longer words
                if word1 in word2 or word2 in word1:
                    substring_matches += 1
                    break
    
    substring_similarity = substring_matches / max(len(words1), len(words2)) if max(len(words1), len(words2)) > 0 else 0.0
    
    # Method 3: Exact phrase matching (for multi-word phrases)
    phrase_similarity = 0.0
    if len(text1.split()) > 1 and len(text2.split()) > 1:
        # Check for exact phrase matches
        phrases1 = [text1[i:i+len(text2)] for i in range(len(text1) - len(text2) + 1)]
        phrases2 = [text2[i:i+len(text1)] for i in range(len(text2) - len(text1) + 1)]
        
        if text1 in text2 or text2 in text1:
            phrase_similarity = 0.5
        elif any(phrase in text2 for phrase in phrases1 if len(phrase) > 10):
            phrase_similarity = 0.3
        elif any(phrase in text1 for phrase in phrases2 if len(phrase) > 10):
            phrase_similarity = 0.3
    
    # Combine all similarity methods with weights
    final_similarity = (
        jaccard_similarity * 0.6 +      # 60% weight for word overlap
        substring_similarity * 0.3 +    # 30% weight for substring matches
        phrase_similarity * 0.1         # 10% weight for phrase matches
    )
    
    return min(final_similarity, 1.0)  # Cap at 1.0


def _update_analytics(contribution: UserContribution):
    """Update analytics when a new contribution is added"""
    try:
        analytics = FeedbackAnalytics.objects(question_type=contribution.question_type).first()
        
        if not analytics:
            analytics = FeedbackAnalytics(question_type=contribution.question_type)
        
        analytics.update_analytics(contribution)
        
    except Exception as e:
        logger.warning(f"Failed to update analytics: {e}")


def get_top_contributions(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top-rated user contributions
    
    Args:
        limit: Maximum number of contributions to return
    
    Returns:
        List of top contributions
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        contributions = UserContribution.objects(
            is_approved="approved"
        ).order_by('-rating', '-usage_count').limit(limit)
        
        return [contrib.to_dict() for contrib in contributions]
        
    except Exception as e:
        logger.error(f"Error getting top contributions: {e}")
        return []


def get_questions_and_answers(question_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get questions and answers from analytics
    
    Args:
        question_type: Optional filter by question type
        limit: Maximum number of Q&A pairs to return
    
    Returns:
        List of questions and answers
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        if question_type:
            analytics = FeedbackAnalytics.objects(question_type=question_type).first()
        else:
            # Get overall analytics
            analytics = FeedbackAnalytics.objects().first()
        
        if analytics and analytics.questions_and_answers:
            return analytics.questions_and_answers[:limit]
        else:
            return []
            
    except Exception as e:
        logger.error(f"Error getting questions and answers: {e}")
        return []


def get_top_rated_qa(question_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top-rated questions and answers
    
    Args:
        question_type: Optional filter by question type
        limit: Maximum number of Q&A pairs to return
    
    Returns:
        List of top-rated questions and answers
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        if question_type:
            analytics = FeedbackAnalytics.objects(question_type=question_type).first()
        else:
            # Get overall analytics
            analytics = FeedbackAnalytics.objects().first()
        
        if analytics and analytics.top_rated_qa:
            return analytics.top_rated_qa[:limit]
        else:
            return []
            
    except Exception as e:
        logger.error(f"Error getting top-rated Q&A: {e}")
        return []


def get_recent_qa(question_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent questions and answers
    
    Args:
        question_type: Optional filter by question type
        limit: Maximum number of Q&A pairs to return
    
    Returns:
        List of recent questions and answers
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        if question_type:
            analytics = FeedbackAnalytics.objects(question_type=question_type).first()
        else:
            # Get overall analytics
            analytics = FeedbackAnalytics.objects().first()
        
        if analytics and analytics.recent_contributions:
            return analytics.recent_contributions[:limit]
        else:
            return []
            
    except Exception as e:
        logger.error(f"Error getting recent Q&A: {e}")
        return []


def search_qa_by_keyword(keyword: str, question_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search questions and answers by keyword
    
    Args:
        keyword: Search keyword
        question_type: Optional filter by question type
    
    Returns:
        List of matching questions and answers
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        if question_type:
            analytics = FeedbackAnalytics.objects(question_type=question_type).first()
        else:
            # Get overall analytics
            analytics = FeedbackAnalytics.objects().first()
        
        if analytics:
            return analytics.search_questions(keyword)
        else:
            return []
            
    except Exception as e:
        logger.error(f"Error searching Q&A by keyword: {e}")
        return []


def approve_all_pending_contributions() -> Dict[str, Any]:
    """
    Utility function to approve all pending user contributions
    This is useful for fixing the issue where contributions were stuck in pending status
    
    Returns:
        Dictionary with success status and count of approved contributions
    """
    try:
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        # Find all pending contributions
        pending_contributions = UserContribution.objects(is_approved="pending")
        pending_count = pending_contributions.count()
        
        if pending_count == 0:
            return {
                'success': True,
                'message': 'No pending contributions found',
                'approved_count': 0
            }
        
        # Approve all pending contributions
        updated_count = UserContribution.objects(is_approved="pending").update(
            set__is_approved="approved"
        )
        
        logger.info(f"Approved {updated_count} pending contributions")
        
        return {
            'success': True,
            'message': f'Successfully approved {updated_count} pending contributions',
            'approved_count': updated_count,
            'pending_count': pending_count
        }
        
    except Exception as e:
        logger.error(f"Error approving pending contributions: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to approve pending contributions'
        }
