import os
import tempfile
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from PIL import Image
import io
import json

from core.utils import (
    extract_text_from_pdf,
    chunk_text,
    embed_texts,
    normalize,
    search_similar_chunks
)


class UtilsTestCase(TestCase):
    """Test cases for utility functions"""

    def test_chunk_text(self):
        """Test text chunking functionality"""
        text = "This is a test. " * 100  # Create long text
        chunks = chunk_text(text, chunk_size=50, chunk_overlap=10)
        
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 60)  # Allow some flexibility

    def test_chunk_text_empty(self):
        """Test chunking with empty text"""
        chunks = chunk_text("", chunk_size=100, chunk_overlap=20)
        self.assertEqual(chunks, [])

    def test_normalize(self):
        """Test vector normalization"""
        import numpy as np
        
        vector = np.array([3.0, 4.0])
        normalized = normalize(vector)
        
        # Check if normalized vector has unit length
        self.assertAlmostEqual(np.linalg.norm(normalized), 1.0, places=5)

    def test_normalize_zero_vector(self):
        """Test normalization of zero vector"""
        import numpy as np
        
        vector = np.array([0.0, 0.0])
        normalized = normalize(vector)
        
        # Zero vector should remain zero
        np.testing.assert_array_equal(normalized, vector)

    @patch('core.utils.SentenceTransformer')
    def test_embed_texts(self, mock_transformer):
        """Test text embedding functionality"""
        import numpy as np
        
        # Mock the transformer
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        mock_transformer.return_value = mock_model
        
        texts = ["Hello world", "Test text"]
        embeddings = embed_texts(texts)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape[0], 2)
        mock_model.encode.assert_called_once_with(texts, convert_to_numpy=True)


class APITestCase(TestCase):
    """Test cases for API endpoints"""

    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        """Test health check API endpoint"""
        response = self.client.get('/api/health/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertIn('status', data)
        self.assertIn('search_index_available', data)
        self.assertIn('ai_service_available', data)
        self.assertIn('document_count', data)

    @patch('core.views.search_similar_chunks')
    @patch('core.views.genai')
    def test_ask_endpoint_success(self, mock_genai, mock_search):
        """Test successful ask API endpoint"""
        # Mock search results
        mock_search.return_value = [
            {'text': 'Test content', 'filename': 'test.pdf', 'similarity': 0.9}
        ]
        
        # Mock AI response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is a test answer."
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        response = self.client.post('/api/ask/', {
            'question': 'What is this about?'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['success'])
        self.assertIn('answer', data)
        self.assertIn('sources', data)
        self.assertIn('processing_time', data)

    def test_ask_endpoint_empty_question(self):
        """Test ask endpoint with empty question"""
        response = self.client.post('/api/ask/', {
            'question': ''
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_list_documents_endpoint(self):
        """Test list documents API endpoint"""
        response = self.client.get('/api/documents/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['success'])
        self.assertIn('documents', data)
        self.assertIn('total_documents', data)
        self.assertIn('total_chunks', data)

    def test_frontend_loads(self):
        """Test that the frontend page loads correctly"""
        response = self.client.get('/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PDF Q&A System')
        self.assertContains(response, 'search-btn')
        self.assertContains(response, 'image-btn')
        self.assertContains(response, 'voice-btn')
