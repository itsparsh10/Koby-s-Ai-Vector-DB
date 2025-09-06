import os
import json
import logging
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import faiss
from django.conf import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from settings
EMBED_MODEL_NAME = getattr(settings, 'EMBED_MODEL_NAME', 'all-MiniLM-L6-v2')
EMBED_DIM = 384
INDEX_PATH = getattr(settings, 'INDEX_PATH', os.path.join("indexes", "faiss_index.bin"))
META_PATH = getattr(settings, 'METADATA_PATH', os.path.join("indexes", "metadata.json"))
CHUNK_SIZE = getattr(settings, 'CHUNK_SIZE', 1000)
CHUNK_OVERLAP = getattr(settings, 'CHUNK_OVERLAP', 200)

_model = None

def get_model() -> SentenceTransformer:
    """Get or initialize the sentence transformer model."""
    global _model
    if _model is None:
        try:
            logger.info(f"Loading embedding model: {EMBED_MODEL_NAME}")
            _model = SentenceTransformer(EMBED_MODEL_NAME)
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _model

def extract_text_from_pdf(path: str) -> str:
    """Extract text from a PDF file with error handling."""
    try:
        if not os.path.exists(path):
            raise FileNotFoundError(f"PDF file not found: {path}")
        
        if not path.lower().endswith('.pdf'):
            raise ValueError(f"File is not a PDF: {path}")
        
        logger.info(f"Extracting text from: {path}")
        reader = PdfReader(path)
        
        if len(reader.pages) == 0:
            logger.warning(f"PDF has no pages: {path}")
            return ""
        
        text_parts = []
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {i+1} of {path}: {e}")
                continue
        
        full_text = "\n".join(text_parts)
        logger.info(f"Extracted {len(full_text)} characters from {len(reader.pages)} pages")
        return full_text
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF {path}: {e}")
        raise

def chunk_text(text: str, chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> List[str]:
    """Split text into overlapping chunks with improved logic."""
    if chunk_size is None:
        chunk_size = CHUNK_SIZE
    if overlap is None:
        overlap = CHUNK_OVERLAP
    
    if not text or not text.strip():
        logger.warning("Empty text provided for chunking")
        return []
    
    if overlap >= chunk_size:
        logger.warning(f"Overlap ({overlap}) >= chunk_size ({chunk_size}), setting overlap to chunk_size//2")
        overlap = chunk_size // 2
    
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        
        if chunk:
            chunks.append(chunk)
        
        # Move start position, ensuring we don't go backwards
        if end >= text_length:
            break
        start = max(start + 1, end - overlap)
    
    logger.info(f"Created {len(chunks)} chunks from text of length {text_length}")
    return chunks

def embed_texts(texts: List[str]) -> np.ndarray:
    """Generate embeddings for a list of texts."""
    if not texts:
        logger.warning("Empty text list provided for embedding")
        return np.array([])
    
    try:
        model = get_model()
        logger.info(f"Generating embeddings for {len(texts)} texts")
        embeddings = model.encode(
            texts, 
            convert_to_numpy=True, 
            show_progress_bar=len(texts) > 10,
            batch_size=32
        )
        logger.info(f"Generated embeddings with shape: {embeddings.shape}")
        return embeddings
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise

def normalize(vecs: np.ndarray) -> np.ndarray:
    """Normalize vectors to unit length."""
    if vecs.size == 0:
        return vecs
    
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10  # Avoid division by zero
    normalized = vecs / norms
    logger.debug(f"Normalized {len(vecs)} vectors")
    return normalized

def save_index(index: faiss.Index) -> None:
    """Save FAISS index to disk."""
    try:
        index_dir = os.path.dirname(INDEX_PATH)
        os.makedirs(index_dir, exist_ok=True)
        
        logger.info(f"Saving FAISS index to: {INDEX_PATH}")
        faiss.write_index(index, INDEX_PATH)
        logger.info(f"FAISS index saved successfully with {index.ntotal} vectors")
    except Exception as e:
        logger.error(f"Error saving FAISS index: {e}")
        raise

def load_index() -> faiss.Index:
    """Load FAISS index from disk."""
    try:
        if not os.path.exists(INDEX_PATH):
            raise FileNotFoundError(f"FAISS index not found at {INDEX_PATH}. Run 'python manage.py embed_pdfs' first.")
        
        logger.info(f"Loading FAISS index from: {INDEX_PATH}")
        index = faiss.read_index(INDEX_PATH)
        logger.info(f"FAISS index loaded successfully with {index.ntotal} vectors")
        return index
    except Exception as e:
        logger.error(f"Error loading FAISS index: {e}")
        raise

def save_metadata(metadata: List[Dict]) -> None:
    """Save metadata to JSON file."""
    try:
        metadata_dir = os.path.dirname(META_PATH)
        os.makedirs(metadata_dir, exist_ok=True)
        
        logger.info(f"Saving metadata to: {META_PATH}")
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Metadata saved successfully with {len(metadata)} entries")
    except Exception as e:
        logger.error(f"Error saving metadata: {e}")
        raise

def load_metadata() -> List[Dict]:
    """Load metadata from JSON file."""
    try:
        if not os.path.exists(META_PATH):
            logger.warning(f"Metadata file not found at {META_PATH}")
            return []
        
        logger.info(f"Loading metadata from: {META_PATH}")
        with open(META_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        logger.info(f"Metadata loaded successfully with {len(metadata)} entries")
        return metadata
    except Exception as e:
        logger.error(f"Error loading metadata: {e}")
        raise

def search_similar_chunks(query: str, k: Optional[int] = None, similarity_threshold: Optional[float] = None) -> Dict[str, Any]:
    """Search for similar text chunks using the FAISS index."""
    if k is None:
        k = getattr(settings, 'MAX_SEARCH_RESULTS', 5)
    if similarity_threshold is None:
        similarity_threshold = getattr(settings, 'SIMILARITY_THRESHOLD', 0.0)
    
    try:
        # Load index and metadata
        index = load_index()
        metadata = load_metadata()
        
        if not metadata:
            logger.warning("No metadata available for search")
            return {
                'success': False,
                'error': 'No indexed documents found. Please run: python manage.py embed_pdfs',
                'chunks': [],
                'scores': []
            }
        
        # Generate query embedding
        query_embedding = embed_texts([query])
        query_embedding = normalize(query_embedding)
        
        # Search
        logger.info(f"Searching for top {k} similar chunks")
        scores, indices = index.search(query_embedding, k)
        
        # Extract results
        chunks = []
        result_scores = []
        
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < len(metadata) and score >= similarity_threshold:
                chunk_data = metadata[idx].copy()
                chunk_data['similarity'] = float(score)
                chunks.append(chunk_data)
                result_scores.append(float(score))
            elif idx >= len(metadata):
                logger.warning(f"Index {idx} out of range for metadata (length: {len(metadata)})")
        
        logger.info(f"Found {len(chunks)} similar chunks above threshold {similarity_threshold}")
        
        # Ensure we always return chunks even if empty
        if not chunks:
            logger.warning(f"No chunks found above similarity threshold {similarity_threshold}")
            return {
                'success': True,
                'chunks': [],
                'scores': [],
                'total_found': 0,
                'message': f'No results found above similarity threshold {similarity_threshold}'
            }
        
        return {
            'success': True,
            'chunks': chunks,
            'scores': result_scores,
            'total_found': len(chunks)
        }
        
    except Exception as e:
        logger.error(f"Error searching similar chunks: {e}")
        return {
            'success': False,
            'error': f'Search error: {str(e)}',
            'chunks': [],
            'scores': []
        }
