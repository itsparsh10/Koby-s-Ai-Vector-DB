from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
import logging
import time
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from core.utils import search_similar_chunks
from core.mongodb_utils import (
    connect_to_mongodb, store_user_contribution, search_similar_contributions,
    get_contribution_analytics, get_top_contributions, get_questions_and_answers,
    get_top_rated_qa, get_recent_qa, search_qa_by_keyword
)
from core.enhanced_search import (
    enhanced_search_with_contributions, get_enhanced_sources, 
    prioritize_enhanced_results, analyze_search_effectiveness
)
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from datetime import datetime, timezone
# Import session tracking with error handling
try:
    from .session_utils import (
        track_user_login, track_user_logout, track_user_activity,
        get_live_user_count, get_user_session_stats, get_user_activity_summary,
        SESSION_TRACKING_AVAILABLE
    )
except ImportError as e:
    print(f"⚠️ Session tracking not available: {e}")
    SESSION_TRACKING_AVAILABLE = False
    
    # Create dummy functions
    def track_user_login(request, user):
        print("⚠️ Session tracking not available")
        return False
    
    def track_user_logout(request, user_id):
        print("⚠️ Session tracking not available")
        return False
    
    def track_user_activity(request, user_id, activity_type, activity_data=None):
        print("⚠️ Session tracking not available")
        return False
    
    def get_live_user_count():
        return 0
    
    def get_user_session_stats():
        return {
            'total_sessions': 0,
            'active_sessions': 0,
            'today_sessions': 0,
            'live_users': 0
        }
    
    def get_user_activity_summary(user_id, days=7):
        return {
            'total_activities': 0,
            'activity_breakdown': {},
            'period_days': days
        }

# Configure logging
logger = logging.getLogger(__name__)

# Configure Gemini AI
gemini_api_key = getattr(settings, 'GEMINI_API_KEY', None)
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    logger.info("Gemini AI configured successfully")
else:
    logger.warning("Gemini API key not found. AI functionality will be limited.")

def validate_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize request data."""
    errors = {}
    
    question = data.get('question', '').strip()
    if not question:
        errors['question'] = 'Question is required and cannot be empty'
    elif len(question) > 1000:
        errors['question'] = 'Question is too long (maximum 1000 characters)'
    elif len(question) < 3:
        errors['question'] = 'Question is too short (minimum 3 characters)'
    
    return {'question': question, 'errors': errors}

def _create_mongodb_only_context(contributions: List[Dict]) -> str:
    """
    Create context string from MongoDB contributions only
    
    Args:
        contributions: MongoDB search results
    
    Returns:
        Context string for AI processing
    """
    if not contributions:
        return ""
    
    contribution_contexts = []
    for i, contrib in enumerate(contributions, 1):
        question = contrib.get('question', '')
        answer = contrib.get('answer', '')
        rating = contrib.get('rating', 0.0)
        similarity = contrib.get('similarity_score', 0.0)
        
        contrib_text = f"🎯 USER CONTRIBUTION #{i}:\n"
        if question:
            contrib_text += f"Question: {question}\n"
        contrib_text += f"Answer: {answer}\n"
        contrib_text += f"Rating: {rating}/5.0 (Similarity: {similarity:.2f})"
        
        contribution_contexts.append(contrib_text)
    
    return f"USER CONTRIBUTIONS (FALLBACK SEARCH):\n" + '\n\n'.join(contribution_contexts)


def generate_ai_response(question: str, context: str) -> Dict[str, Any]:
    """Generate AI response using Gemini."""
    try:
        if not gemini_api_key:
            return {
                'success': False,
                'error': 'AI service not configured',
                'answer': None
            }
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""You are an AI assistant helping users with questions about barista training and coffee shop operations. Based on the following context from both original documents and user contributions, provide a comprehensive and accurate answer to the question.

Question: {question}

Context:
{context}

Instructions:
1. If the context contains user contributions, prioritize and reference them as they represent real-world experience and enhancements
2. Combine information from both original documents and user contributions when relevant
3. If the context doesn't contain enough information, clearly state that
4. Provide a clear, well-structured answer based on the provided context
5. If user contributions are available, mention that the answer includes insights from user experience

Please provide a helpful and accurate response."""
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            return {
                'success': True,
                'error': None,
                'answer': response.text.strip()
            }
        else:
            return {
                'success': False,
                'error': 'Empty response from AI service',
                'answer': None
            }
            
    except Exception as e:
        logger.error(f"AI service error: {str(e)}")
        return {
            'success': False,
            'error': f'AI service error: {str(e)}',
            'answer': None
        }

@csrf_exempt
@api_view(['POST'])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def ask(request):
    """Handle question answering requests with comprehensive validation and error handling."""
    start_time = time.time()
    
    try:
        # Validate request data
        validation_result = validate_request_data(request.data)
        
        if validation_result['errors']:
            logger.warning(f"Validation errors: {validation_result['errors']}")
            return Response({
                'success': False,
                'error': 'Validation failed',
                'details': validation_result['errors'],
                'answer': None,
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        question = validation_result['question']
        logger.info(f"Processing question: {question[:100]}...")
        
        # Use enhanced search that combines FAISS and MongoDB with aggressive MongoDB search
        search_result = enhanced_search_with_contributions(
            question, 
            k=getattr(settings, 'MAX_SEARCH_RESULTS', 5),
            similarity_threshold=getattr(settings, 'SIMILARITY_THRESHOLD', 0.3),
            include_contributions=True,
            contribution_limit=5  # Increased limit for better coverage
        )
        
        if not search_result['success']:
            logger.error(f"Search error: {search_result['error']}")
            return Response({
                'success': False,
                'error': search_result['error'],
                'answer': None,
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Extract context from enhanced search results
        faiss_chunks = search_result.get('faiss_results', [])
        contribution_results = search_result.get('contribution_results', [])
        combined_context = search_result.get('combined_context', '')
        
        # Check if we have any results - if not, try direct MongoDB search as fallback
        if not faiss_chunks and not contribution_results:
            logger.info("No results from enhanced search, trying direct MongoDB search as fallback")
            try:
                from core.mongodb_utils import search_similar_contributions
                fallback_contributions = search_similar_contributions(question, limit=5, min_rating=0.0)
                
                if fallback_contributions:
                    logger.info(f"Fallback MongoDB search found {len(fallback_contributions)} contributions")
                    contribution_results = fallback_contributions
                    # Create context from MongoDB results only
                    context = _create_mongodb_only_context(contribution_results)
                else:
                    return Response({
                        'success': False,
                        'error': 'No relevant information found in the documents or user contributions. Try rephrasing your question.',
                        'answer': None,
                        'processing_time': round(time.time() - start_time, 3)
                    }, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                logger.error(f"Fallback MongoDB search failed: {e}")
                return Response({
                    'success': False,
                    'error': 'No relevant information found in the documents or user contributions. Try rephrasing your question.',
                    'answer': None,
                    'processing_time': round(time.time() - start_time, 3)
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Use combined context from enhanced search
            context = combined_context
        
        # Generate AI response
        ai_response = generate_ai_response(question, context)
        
        if not ai_response['success']:
            logger.error(f"AI response error: {ai_response['error']}")
            return Response({
                'success': False,
                'error': ai_response['error'],
                'answer': None,
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Prepare enhanced sources information
        sources = get_enhanced_sources(faiss_chunks, contribution_results)
        
        processing_time = round(time.time() - start_time, 3)
        logger.info(f"Successfully processed question in {processing_time}s")
        
        # Analyze search effectiveness
        search_analysis = analyze_search_effectiveness(question, search_result)
        
        # Track user search activity if available and authenticated
        if SESSION_TRACKING_AVAILABLE:
            try:
                user_id = request.session.get('user_id')
                if user_id:
                    track_user_activity(
                        request, 
                        user_id, 
                        'search', 
                        f"Question: {question[:100]}..."
                    )
            except Exception as e:
                logger.warning(f"Failed to track search activity: {str(e)}")
        
        return Response({
            'success': True,
            'answer': ai_response['answer'],
            'sources': sources,
            'processing_time': processing_time,
            'search_metadata': search_result.get('search_metadata', {}),
            'search_analysis': search_analysis,
            'has_user_contributions': len(contribution_results) > 0
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        processing_time = round(time.time() - start_time, 3)
        logger.error(f"Unexpected error in ask view: {str(e)}")
        return Response({
             'success': False,
             'error': 'An unexpected error occurred while processing your request',
             'answer': None,
             'processing_time': processing_time
         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def health_check(request):
    """Health check endpoint to verify system status."""
    try:
        from core.utils import load_index, load_metadata
        
        # Check if index and metadata are available
        try:
            index = load_index()
            metadata = load_metadata()
            index_status = 'available'
            document_count = len(metadata) if metadata else 0
        except Exception as e:
            index_status = 'unavailable'
            document_count = 0
            logger.warning(f"Index not available: {str(e)}")
        
        # Check AI service
        ai_status = 'available' if gemini_api_key else 'unavailable'
        
        return Response({
            'success': True,
            'status': 'healthy',
            'services': {
                'search_index': index_status,
                'ai_service': ai_status,
                'document_count': document_count
            },
            'timestamp': time.time()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return Response({
            'success': False,
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.time()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def list_documents(request):
    """List all indexed documents."""
    try:
        from core.utils import load_metadata
        
        try:
            metadata = load_metadata()
            
            documents = []
            for item in metadata:
                documents.append({
                    'filename': item.get('filename', 'Unknown'),
                    'text_preview': item.get('text', '')[:200] + '...' if len(item.get('text', '')) > 200 else item.get('text', ''),
                    'chunk_count': 1  # Each metadata item represents one chunk
                })
            
            # Group by filename
            doc_summary = {}
            for doc in documents:
                filename = doc['filename']
                if filename not in doc_summary:
                    doc_summary[filename] = {
                        'filename': filename,
                        'chunk_count': 0,
                        'total_characters': 0
                    }
                doc_summary[filename]['chunk_count'] += 1
                doc_summary[filename]['total_characters'] += len(doc['text_preview'])
            
            return Response({
                'success': True,
                'documents': list(doc_summary.values()),
                'total_documents': len(doc_summary),
                'total_chunks': len(documents)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.warning(f"Could not load documents: {str(e)}")
            return Response({
                'success': True,
                'documents': [],
                'total_documents': 0,
                'total_chunks': 0,
                'message': 'No documents indexed yet. Run embed_pdfs command to index PDFs.'
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"List documents error: {str(e)}")
        return Response({
             'success': False,
             'error': str(e)
         }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def image_search(request):
    """Handle image-based search requests."""
    start_time = time.time()
    
    try:
        # Check if image file is provided
        if 'image' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No image file provided',
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        image_file = request.FILES['image']
        
        # Validate image file
        if not image_file.content_type.startswith('image/'):
            return Response({
                'success': False,
                'error': 'Invalid file type. Please upload an image file.',
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check file size (max 10MB)
        if image_file.size > 10 * 1024 * 1024:
            return Response({
                'success': False,
                'error': 'Image file too large. Maximum size is 10MB.',
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Processing image search: {image_file.name} ({image_file.size} bytes)")
        
        # Process image and extract text/description
        try:
            image_result = process_image_for_search(image_file)
            
            if not image_result['success']:
                return Response({
                    'success': False,
                    'error': image_result['error'],
                    'processing_time': round(time.time() - start_time, 3)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Use extracted text/description as search query
            search_query = image_result['description']
            logger.info(f"Generated search query from image: {search_query[:100]}...")
            
            # Search for similar chunks
            search_result = search_similar_chunks(
                search_query,
                k=getattr(settings, 'MAX_SEARCH_RESULTS', 5),
                similarity_threshold=getattr(settings, 'SIMILARITY_THRESHOLD', 0.3)
            )
            
            if not search_result['success']:
                return Response({
                    'success': False,
                    'error': search_result['error'],
                    'processing_time': round(time.time() - start_time, 3)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Check if we found relevant context
            if not search_result['chunks']:
                return Response({
                    'success': True,
                    'answer': f'I analyzed the image and extracted: "{search_query}", but could not find relevant information in the available documents.',
                    'image_description': search_query,
                    'sources': [],
                    'processing_time': round(time.time() - start_time, 3)
                }, status=status.HTTP_200_OK)
            
            # Extract context from search results
            context = '\n\n'.join([chunk['text'] for chunk in search_result['chunks']])
            
            # Generate AI response based on image analysis
            ai_result = generate_ai_response_for_image(search_query, context)
            
            if not ai_result['success']:
                return Response({
                    'success': False,
                    'error': ai_result['error'],
                    'processing_time': round(time.time() - start_time, 3)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Successful response
            processing_time = round(time.time() - start_time, 3)
            logger.info(f"Successfully processed image search in {processing_time}s")
            
            # Track user image search activity if available and authenticated
            if SESSION_TRACKING_AVAILABLE:
                try:
                    user_id = request.session.get('user_id')
                    if user_id:
                        track_user_activity(
                            request, 
                            user_id, 
                            'image_search', 
                            f"Image: {image_file.name}, Query: {search_query[:100]}..."
                        )
                except Exception as e:
                    logger.warning(f"Failed to track image search activity: {str(e)}")
            
            # Prepare sources information
            sources = []
            for chunk in search_result['chunks']:
                source_info = {
                    'filename': chunk.get('filename', 'Unknown'),
                    'page': chunk.get('page', 'Unknown'),
                    'similarity': chunk.get('similarity', 0.0)
                }
                if source_info not in sources:
                    sources.append(source_info)
            
            return Response({
                'success': True,
                'answer': ai_result['answer'],
                'image_description': search_query,
                'sources': sources,
                'processing_time': processing_time
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Image processing error: {str(e)}")
            return Response({
                'success': False,
                'error': 'Failed to process image. Please try again with a different image.',
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        processing_time = round(time.time() - start_time, 3)
        logger.error(f"Unexpected error in image_search view: {str(e)}")
        return Response({
            'success': False,
            'error': 'An unexpected error occurred while processing your image',
            'processing_time': processing_time
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def process_image_for_search(image_file) -> Dict[str, Any]:
    """Process uploaded image and extract searchable content."""
    try:
        # For now, we'll use a simple approach with Gemini Vision
        # In a production system, you might want to use OCR, object detection, etc.
        
        if not gemini_api_key:
            return {
                'success': False,
                'error': 'AI service not configured for image processing',
                'description': None
            }
        
        import PIL.Image
        import io
        
        # Open and process the image
        image_data = image_file.read()
        image = PIL.Image.open(io.BytesIO(image_data))
        
        # Use Gemini Vision to analyze the image
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = """Analyze this image and provide a detailed description that could be used to search for related information in documents. Focus on:
1. Any text visible in the image
2. Objects, products, or items shown
3. Context or setting
4. Any relevant details that might help find related information

Provide a concise but comprehensive description suitable for document search."""
        
        response = model.generate_content([prompt, image])
        
        if response and response.text:
            return {
                'success': True,
                'error': None,
                'description': response.text.strip()
            }
        else:
            return {
                'success': False,
                'error': 'Could not analyze image content',
                'description': None
            }
            
    except Exception as e:
        logger.error(f"Image processing error: {str(e)}")
        return {
            'success': False,
            'error': f'Image processing failed: {str(e)}',
            'description': None
        }

def generate_ai_response_for_image(image_description: str, context: str) -> Dict[str, Any]:
    """Generate AI response for image-based search."""
    try:
        if not gemini_api_key:
            return {
                'success': False,
                'error': 'AI service not configured',
                'answer': None
            }
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""Based on the image analysis and the following context from PDF documents, provide a comprehensive answer.

Image Analysis: {image_description}

Context from Documents:
{context}

Please provide a helpful response that connects the image content with the available document information. If the documents don't contain relevant information about what's shown in the image, clearly state that."""
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            return {
                'success': True,
                'error': None,
                'answer': response.text.strip()
            }
        else:
            return {
                'success': False,
                'error': 'Empty response from AI service',
                'answer': None
            }
            
    except Exception as e:
        logger.error(f"AI service error for image: {str(e)}")
        return {
            'success': False,
            'error': f'AI service error: {str(e)}',
            'answer': None
        }

@require_http_methods(["GET", "POST"])
def create_account(request):
    """Handle user account creation."""
    if request.method == "POST":
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Basic validation
        errors = []
        
        if not full_name:
            errors.append('Full name is required')
        
        if not email:
            errors.append('Email is required')
        elif User.objects.filter(email=email).exists():
            errors.append('Email already exists')
        
        if not password:
            errors.append('Password is required')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters long')
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        if errors:
            # Re-render the form with errors
            return render(request, 'createAccount.html', {
                'errors': errors,
                'form_data': {
                    'full_name': full_name,
                    'email': email
                }
            })
        
        try:
            # Create user
            username = email.split('@')[0]  # Use email prefix as username
            # Ensure username is unique
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=full_name.split()[0] if ' ' in full_name else full_name,
                last_name=' '.join(full_name.split()[1:]) if ' ' in full_name else ''
            )
            
            # Log the user in
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'Account created successfully!')
                return redirect('home')
            else:
                messages.error(request, 'Account created but login failed. Please try logging in.')
                return redirect('login')
                
        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            errors.append('Failed to create account. Please try again.')
            return render(request, 'createAccount.html', {
                'errors': errors,
                'form_data': {
                    'full_name': full_name,
                    'email': email
                }
            })
    
    # GET request - show the form
    return render(request, 'createAccount.html')

# Admin-specific views
@api_view(['GET'])
def admin_dashboard_stats(request):
    """Get comprehensive admin dashboard statistics."""
    try:
        from core.utils import load_metadata
        
        # Get document statistics
        try:
            metadata = load_metadata()
            document_count = len(metadata) if metadata else 0
            total_chunks = document_count
        except Exception as e:
            document_count = 0
            total_chunks = 0
            logger.warning(f"Could not load metadata: {str(e)}")
        
        # Get user statistics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        
        # Get AI service status
        ai_status = 'available' if gemini_api_key else 'unavailable'
        
        # Get system information
        import psutil
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            system_stats = {
                'cpu_usage': round(cpu_percent, 1),
                'memory_usage': round(memory.percent, 1),
                'memory_available': round(memory.available / (1024**3), 2),  # GB
                'disk_usage': round(disk.percent, 1),
                'disk_free': round(disk.free / (1024**3), 2)  # GB
            }
        except ImportError:
            system_stats = {
                'cpu_usage': 0,
                'memory_usage': 0,
                'memory_available': 0,
                'disk_usage': 0,
                'disk_free': 0
            }
        
        return Response({
            'success': True,
            'stats': {
                'documents': {
                    'total': document_count,
                    'chunks': total_chunks
                },
                'users': {
                    'total': total_users,
                    'active': active_users
                },
                'ai_service': {
                    'status': ai_status,
                    'api_key_configured': bool(gemini_api_key)
                },
                'system': system_stats
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Admin dashboard stats error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def admin_upload_pdf(request):
    """Admin endpoint for uploading and indexing PDFs."""
    try:
        if 'pdf' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No PDF file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        pdf_file = request.FILES['pdf']
        
        # Validate file type
        if not pdf_file.content_type == 'application/pdf':
            return Response({
                'success': False,
                'error': 'Invalid file type. Only PDF files are allowed.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check file size (max 50MB)
        if pdf_file.size > 50 * 1024 * 1024:
            return Response({
                'success': False,
                'error': 'File too large. Maximum size is 50MB.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save file to pdfs directory
        import os
        pdf_dir = os.path.join(settings.BASE_DIR, 'pdfs')
        os.makedirs(pdf_dir, exist_ok=True)
        
        filename = pdf_file.name
        file_path = os.path.join(pdf_dir, filename)
        
        with open(file_path, 'wb+') as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)
        
        # Here you would call your PDF processing/indexing logic
        # For now, we'll just return success
        logger.info(f"PDF uploaded successfully: {filename}")
        
        return Response({
            'success': True,
            'message': f'PDF "{filename}" uploaded successfully',
            'filename': filename,
            'size': pdf_file.size
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"PDF upload error: {str(e)}")
        return Response({
            'success': False,
            'error': f'Upload failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def admin_create_user(request):
    """Admin endpoint for creating new users."""
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'first_name']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if username or email already exists
        if User.objects.filter(username=data['username']).exists():
            return Response({
                'success': False,
                'error': 'Username already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=data['email']).exists():
            return Response({
                'success': False,
                'error': 'Email already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create user
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data.get('last_name', ''),
            is_active=data.get('is_active', True)
        )
        
        # Set staff/superuser status if provided
        if data.get('is_staff'):
            user.is_staff = True
        if data.get('is_superuser'):
            user.is_superuser = True
        
        user.save()
        
        logger.info(f"User created successfully: {user.username}")
        
        return Response({
            'success': True,
            'message': f'User "{user.username}" created successfully',
            'user_id': user.id
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"User creation error: {str(e)}")
        return Response({
            'success': False,
            'error': f'Failed to create user: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def admin_list_users(request):
    """Admin endpoint for listing all users."""
    try:
        users = User.objects.all().values(
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'date_joined'
        )
        
        return Response({
            'success': True,
            'users': list(users)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"User listing error: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def admin_reindex_documents(request):
    """Admin endpoint for reindexing all documents."""
    try:
        # Here you would call your reindexing logic
        # For now, we'll simulate the process
        logger.info("Document reindexing started by admin")
        
        return Response({
            'success': True,
            'message': 'Document reindexing started successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Reindexing error: {str(e)}")
        return Response({
            'success': False,
            'error': f'Reindexing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def admin_list_contributions(request):
    """Admin endpoint for listing user contributions with filtering."""
    try:
        from core.mongodb_utils import connect_to_mongodb
        from core.feedback_models import UserContribution
        
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        # Get query parameters
        status_filter = request.GET.get('status', 'all')  # all, pending, approved, rejected
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        search_query = request.GET.get('search', '').lower()
        
        # Build query
        query = {}
        if status_filter != 'all':
            query['is_approved'] = status_filter
        
        # Get contributions
        if search_query:
            # Search in question or answer
            from mongoengine import Q
            contributions = UserContribution.objects(
                Q(**query) & (Q(question__icontains=search_query) | Q(answer__icontains=search_query))
            ).order_by('-timestamp')
        else:
            contributions = UserContribution.objects(**query).order_by('-timestamp')
        
        # Pagination
        total_count = contributions.count()
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        page_contributions = contributions[start_index:end_index]
        
        # Convert to list of dictionaries
        contributions_data = []
        for contrib in page_contributions:
            contributions_data.append({
                'id': str(contrib.id),
                'question': contrib.question,
                'answer': contrib.answer,
                'question_type': contrib.question_type,
                'user_id': contrib.user_id,
                'user_email': contrib.user_email,
                'timestamp': contrib.timestamp.isoformat() if contrib.timestamp else None,
                'rating': contrib.rating,
                'usage_count': contrib.usage_count,
                'improvement_type': contrib.improvement_type,
                'is_approved': contrib.is_approved,
                'similarity_keywords': contrib.similarity_keywords
            })
        
        return Response({
            'success': True,
            'contributions': contributions_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            },
            'filters': {
                'status': status_filter,
                'search': search_query
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing contributions: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def admin_approve_contribution(request):
    """Admin endpoint for approving a user contribution."""
    try:
        from core.mongodb_utils import connect_to_mongodb
        from core.feedback_models import UserContribution
        
        data = request.data
        contribution_id = data.get('contribution_id')
        action = data.get('action')  # 'approve' or 'reject'
        
        if not contribution_id or not action:
            return Response({
                'success': False,
                'error': 'contribution_id and action are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if action not in ['approve', 'reject']:
            return Response({
                'success': False,
                'error': 'action must be either "approve" or "reject"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        # Find and update contribution
        contribution = UserContribution.objects(id=contribution_id).first()
        if not contribution:
            return Response({
                'success': False,
                'error': 'Contribution not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update approval status
        contribution.is_approved = "approved" if action == "approve" else "rejected"
        contribution.save()
        
        logger.info(f"Contribution {contribution_id} {action}d by admin")
        
        return Response({
            'success': True,
            'message': f'Contribution {action}d successfully',
            'contribution_id': contribution_id,
            'new_status': contribution.is_approved
        })
        
    except Exception as e:
        logger.error(f"Error {action}ing contribution: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def admin_bulk_approve_contributions(request):
    """Admin endpoint for bulk approving/rejecting multiple contributions."""
    try:
        from core.mongodb_utils import connect_to_mongodb
        from core.feedback_models import UserContribution
        
        data = request.data
        contribution_ids = data.get('contribution_ids', [])
        action = data.get('action')  # 'approve' or 'reject'
        
        if not contribution_ids or not action:
            return Response({
                'success': False,
                'error': 'contribution_ids and action are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if action not in ['approve', 'reject']:
            return Response({
                'success': False,
                'error': 'action must be either "approve" or "reject"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Ensure MongoDB connection
        connect_to_mongodb()
        
        # Update multiple contributions
        new_status = "approved" if action == "approve" else "rejected"
        updated_count = UserContribution.objects(id__in=contribution_ids).update(
            set__is_approved=new_status
        )
        
        logger.info(f"Bulk {action}d {updated_count} contributions by admin")
        
        return Response({
            'success': True,
            'message': f'Successfully {action}d {updated_count} contributions',
            'updated_count': updated_count,
            'requested_count': len(contribution_ids)
        })
        
    except Exception as e:
        logger.error(f"Error bulk {action}ing contributions: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def admin_approve_all_pending(request):
    """Admin endpoint to approve all pending contributions (one-time fix)."""
    try:
        from core.mongodb_utils import approve_all_pending_contributions
        
        result = approve_all_pending_contributions()
        
        if result['success']:
            return Response({
                'success': True,
                'message': result['message'],
                'approved_count': result['approved_count'],
                'pending_count': result.get('pending_count', 0)
            })
        else:
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error approving all pending contributions: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# User Authentication Views
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User
import json

@csrf_exempt
def user_login(request):
    """Handle user login"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                return JsonResponse({
                    'success': False,
                    'message': 'Email and password are required'
                }, status=400)
            
            try:
                # Use filter().first() instead of get() for MongoDB compatibility
                user = User.objects.filter(email=email).first()
                if user and user.check_password(password):
                    # Store user info in session
                    request.session['user_id'] = str(user.id)  # Convert ObjectId to string
                    request.session['user_email'] = user.email
                    request.session['user_name'] = user.name
                    
                    # Track user login activity if available
                    if SESSION_TRACKING_AVAILABLE:
                        track_user_login(request, user)
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Login successful',
                        'user': {
                            'id': str(user.id),
                            'name': user.name,
                            'email': user.email,
                            'role': getattr(user, 'role', 'user')  # Get role, default to 'user' if not set
                        }
                    })
                elif user:
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid password'
                    }, status=401)
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'User not found'
                    }, status=404)
                    
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Authentication error: {str(e)}'
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Method not allowed'
    }, status=405)

@csrf_exempt
def user_create_account(request):
    """Handle user account creation"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            email = data.get('email')
            password = data.get('password')
            confirm_password = data.get('confirmPassword')
            
            # Validation
            if not all([name, email, password, confirm_password]):
                return JsonResponse({
                    'success': False,
                    'message': 'All fields are required'
                }, status=400)
            
            if password != confirm_password:
                return JsonResponse({
                    'success': False,
                    'message': 'Passwords do not match'
                }, status=400)
            
            if len(password) < 6:
                return JsonResponse({
                    'success': False,
                    'message': 'Password must be at least 6 characters long'
                }, status=400)
            
            # Check if user already exists
            existing_users = User.objects.filter(email=email)
            if existing_users.count() > 0:
                return JsonResponse({
                    'success': False,
                    'message': 'User with this email already exists'
                }, status=409)
            
            # Create new user
            user = User(name=name, email=email)
            user.set_password(password)
            user.save()
            
            # Store user info in session
            request.session['user_id'] = str(user.id)  # Convert ObjectId to string
            request.session['user_email'] = user.email
            request.session['user_name'] = user.name
            
            return JsonResponse({
                'success': True,
                'message': 'Account created successfully',
                'user': {
                    'id': str(user.id),
                    'name': user.name,
                    'email': user.email,
                    'role': getattr(user, 'role', 'user')  # Get role, default to 'user' if not set
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Method not allowed'
    }, status=405)

@csrf_exempt
def user_logout(request):
    """Handle user logout"""
    try:
        # Get user ID before clearing session
        user_id = request.session.get('user_id')
        
        # Track user logout activity if available
        if SESSION_TRACKING_AVAILABLE and user_id:
            track_user_logout(request, user_id)
        
        # Clear session
        request.session.flush()
        print(f"Logout successful for session: {request.session.session_key}")
        return JsonResponse({
            'success': True,
            'message': 'Logged out successfully'
        })
    except Exception as e:
        print(f"Logout error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Logout failed: {str(e)}'
        }, status=500)

def check_auth(request):
    """Check if user is authenticated"""
    try:
        user_id = request.session.get('user_id')
        print(f"Auth check - Session ID: {request.session.session_key}, User ID: {user_id}")
        
        if user_id:
            try:
                # Use filter().first() for MongoDB compatibility
                user = User.objects.filter(id=user_id).first()
                if user:
                    print(f"Auth check successful for user: {user.name}")
                    return JsonResponse({
                        'success': True,
                        'authenticated': True,
                        'user': {
                            'id': str(user.id),
                            'name': user.name,
                            'email': user.email,
                            'role': getattr(user, 'role', 'user')  # Get role, default to 'user' if not set
                        }
                    })
                else:
                    print(f"Auth check failed: User not found for ID {user_id}")
                    request.session.flush()
                    return JsonResponse({
                        'success': True,
                        'authenticated': False
                    })
            except Exception as e:
                print(f"Auth check error: {str(e)}")
                request.session.flush()
                return JsonResponse({
                    'success': True,
                    'authenticated': False
                })
        else:
            print("Auth check: No user ID in session")
            return JsonResponse({
                'success': True,
                'authenticated': False
            })
    except Exception as e:
        print(f"Auth check error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# User Statistics Views
@api_view(['GET'])
def get_live_user_count_view(request):
    """Get count of currently active users"""
    try:
        live_count = get_live_user_count()
        return Response({
            'success': True,
            'live_users': live_count,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def get_user_stats(request):
    """Get comprehensive user session statistics"""
    try:
        stats = get_user_session_stats()
        return Response({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def get_admin_dashboard_stats(request):
    """Get comprehensive admin dashboard statistics"""
    try:
        # Get user statistics
        user_stats = get_user_session_stats()
        
        # Get total users count
        try:
            if SESSION_TRACKING_AVAILABLE:
                from .session_utils import User
                total_users = User.objects.count()
            else:
                total_users = 0
        except Exception:
            total_users = 0
        
        # Get today's logins count
        try:
            if SESSION_TRACKING_AVAILABLE:
                from .session_utils import UserSession
                from datetime import datetime, timezone, timedelta
                today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                today_logins = UserSession.objects.filter(
                    login_time__gte=today_start
                ).count()
            else:
                today_logins = 0
        except Exception:
            today_logins = 0
        
        # Get pending questions count from UserContribution model
        try:
            from .feedback_models import UserContribution
            pending_questions = UserContribution.objects.filter(is_approved='pending').count()
        except Exception:
            pending_questions = 0
        
        # Get recent user registrations
        try:
            if SESSION_TRACKING_AVAILABLE:
                from .session_utils import User
                recent_users = User.objects.order_by('-created_at')[:10]
                recent_users_data = []
                for user in recent_users:
                    recent_users_data.append({
                        'name': user.name,
                        'email': user.email,
                        'created_at': user.created_at.isoformat() if hasattr(user.created_at, 'isoformat') else str(user.created_at)
                    })
            else:
                recent_users_data = []
        except Exception:
            recent_users_data = []
        
        # Get currently logged in users
        try:
            if SESSION_TRACKING_AVAILABLE:
                from .session_utils import UserSession
                logged_in_users = UserSession.objects.filter(is_active='active').order_by('-last_activity')[:10]
                logged_in_users_data = []
                for session in logged_in_users:
                    logged_in_users_data.append({
                        'name': session.user_name,
                        'email': session.user_email,
                        'login_time': session.login_time.isoformat() if hasattr(session.login_time, 'isoformat') else str(session.login_time),
                        'last_activity': session.last_activity.isoformat() if hasattr(session.last_activity, 'isoformat') else str(session.last_activity),
                        'ip_address': session.ip_address
                    })
            else:
                logged_in_users_data = []
        except Exception:
            logged_in_users_data = []
        
        dashboard_stats = {
            'live_users': user_stats.get('live_users', 0),
            'total_users': total_users,
            'pending_questions': pending_questions,
            'today_logins': today_logins,
            'total_sessions': user_stats.get('total_sessions', 0),
            'active_sessions': user_stats.get('active_sessions', 0),
            'recent_users': recent_users_data,
            'logged_in_users': logged_in_users_data
        }
        
        return Response({
            'success': True,
            'stats': dashboard_stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def get_user_activity(request):
    """Get user activity summary for the current user"""
    try:
        user_id = request.session.get('user_id')
        if not user_id:
            return Response({
                'success': False,
                'error': 'User not authenticated'
            }, status=401)
        
        # Get days parameter from query string
        days = request.GET.get('days', 7)
        try:
            days = int(days)
        except ValueError:
            days = 7
        
        activity_summary = get_user_activity_summary(user_id, days)
        return Response({
            'success': True,
            'activity': activity_summary,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

# User Sessions Management Views
@api_view(['GET'])
def get_user_sessions(request):
    """Get all user sessions with pagination and filtering"""
    try:
        from .session_utils import UserSession
        
        # Get query parameters
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        status_filter = request.GET.get('status', 'all')
        search_query = request.GET.get('search', '').lower()
        
        # Build query
        query = {}
        if status_filter != 'all':
            query['is_active'] = status_filter
        
        if search_query:
            # Search in user name or email - handle both MongoDB and Django
            try:
                # Try MongoDB first
                from mongoengine import Q
                search_filter = Q(user_name__icontains=search_query) | Q(user_email__icontains=search_query)
                
                # Apply status filter if specified
                if status_filter != 'all':
                    search_filter = search_filter & Q(is_active=status_filter)
                
                sessions = UserSession.objects.filter(search_filter).order_by('-login_time')
            except ImportError:
                # Fallback to Django Q
                from django.db.models import Q
                search_filter = Q(user_name__icontains=search_query) | Q(user_email__icontains=search_query)
                
                # Apply status filter if specified
                if status_filter != 'all':
                    search_filter = search_filter & Q(is_active=status_filter)
                
                sessions = UserSession.objects.filter(search_filter).order_by('-login_time')
        else:
            sessions = UserSession.objects.filter(**query).order_by('-login_time')
        
        # Pagination
        total_count = sessions.count()
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        page_sessions = sessions[start_index:end_index]
        
        # Convert to list of dictionaries
        sessions_data = []
        for session in page_sessions:
            sessions_data.append({
                'user_id': session.user_id,
                'user_name': session.user_name,
                'user_email': session.user_email,
                'session_key': session.session_key,
                'login_time': session.login_time.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'is_active': session.is_active,
                'ip_address': session.ip_address,
                'user_agent': session.user_agent,
                'logout_time': session.logout_time.isoformat() if session.logout_time else None
            })
        
        return Response({
            'success': True,
            'sessions': sessions_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
def terminate_user_session(request):
    """Terminate a specific user session"""
    try:
        data = request.data
        session_key = data.get('session_key')
        
        if not session_key:
            return Response({
                'success': False,
                'error': 'Session key is required'
            }, status=400)
        
        from .session_utils import UserSession
        
        # Find and terminate the session
        session = UserSession.objects.filter(session_key=session_key).first()
        if not session:
            return Response({
                'success': False,
                'error': 'Session not found'
            }, status=404)
        
        # Mark session as inactive
        session.is_active = 'inactive'
        session.logout_time = datetime.now(timezone.utc)
        session.save()
        
        # Also clear Django session if possible
        try:
            from django.contrib.sessions.models import Session
            django_session = Session.objects.filter(session_key=session_key).first()
            if django_session:
                django_session.delete()
        except Exception:
            pass  # Django session cleanup is optional
        
        return Response({
            'success': True,
            'message': 'Session terminated successfully'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
def cleanup_old_sessions(request):
    """Clean up old inactive sessions"""
    try:
        from .session_utils import cleanup_old_sessions
        
        cleaned_count = cleanup_old_sessions()
        
        return Response({
            'success': True,
            'cleaned_count': cleaned_count,
            'message': f'Cleaned up {cleaned_count} old sessions'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@api_view(['POST'])
@parser_classes([JSONParser])
def create_user_with_role(request):
    """Create a new user with role assignment"""
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['name', 'email', 'password', 'role']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate role
        valid_roles = ['admin', 'manager', 'user']
        if data['role'] not in valid_roles:
            return Response({
                'success': False,
                'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate email format
        import re
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, data['email']):
            return Response({
                'success': False,
                'error': 'Invalid email format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate password length
        if len(data['password']) < 6:
            return Response({
                'success': False,
                'error': 'Password must be at least 6 characters long'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if email already exists
        existing_user = User.objects.filter(email=data['email']).first()
        if existing_user:
            return Response({
                'success': False,
                'error': 'User with this email already exists'
            }, status=status.HTTP_409_CONFLICT)
        
        # Create new user
        user = User(
            name=data['name'],
            email=data['email'],
            role=data['role']
        )
        user.set_password(data['password'])
        user.save()
        
        logger.info(f"User created successfully: {user.name} ({user.email}) with role: {user.role}")
        
        return Response({
            'success': True,
            'message': f'User "{user.name}" created successfully with {user.role} role',
            'user': {
                'id': str(user.id),
                'name': user.name,
                'email': user.email,
                'role': user.role
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"User creation error: {str(e)}")
        return Response({
            'success': False,
            'error': f'Failed to create user: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['POST'])
@parser_classes([JSONParser])
def submit_feedback(request):
    """Handle user feedback and store in MongoDB for knowledge enhancement"""
    start_time = time.time()
    
    try:
        # Validate request data
        data = request.data
        
        required_fields = ['question', 'message', 'type']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return Response({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Prepare contribution data
        contribution_data = {
            'question': data.get('question', ''),
            'message': data.get('message', ''),
            'type': data.get('type', 'general'),
            'email': data.get('email', ''),
            'user_id': request.session.get('user_id', ''),
            'rating': data.get('rating', 0.0),
            'improvement_type': data.get('improvement_type', 'enhancement')
        }
        
        # Store in MongoDB
        result = store_user_contribution(contribution_data)
        
        if result['success']:
            logger.info(f"Successfully stored user feedback: {result['contribution_id']}")
            return Response({
                'success': True,
                'message': 'Thank you for your feedback! Your contribution has been stored and will help improve our knowledge base.',
                'contribution_id': result['contribution_id'],
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Failed to store user feedback: {result['error']}")
            return Response({
                'success': False,
                'error': result['error'],
                'processing_time': round(time.time() - start_time, 3)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        processing_time = round(time.time() - start_time, 3)
        logger.error(f"Unexpected error in submit_feedback: {str(e)}")
        return Response({
            'success': False,
            'error': 'An unexpected error occurred while processing your feedback',
            'processing_time': processing_time
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_feedback_analytics(request):
    """Get analytics for user contributions and feedback"""
    try:
        question_type = request.GET.get('question_type')
        analytics = get_contribution_analytics(question_type)
        
        return Response({
            'success': True,
            'analytics': analytics
        })
        
    except Exception as e:
        logger.error(f"Error getting feedback analytics: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_top_contributions_api(request):
    """Get top-rated user contributions"""
    try:
        limit = int(request.GET.get('limit', 10))
        contributions = get_top_contributions(limit)
        
        return Response({
            'success': True,
            'contributions': contributions,
            'count': len(contributions)
        })
        
    except Exception as e:
        logger.error(f"Error getting top contributions: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_questions_and_answers_api(request):
    """Get questions and answers from analytics"""
    try:
        question_type = request.GET.get('question_type')
        limit = int(request.GET.get('limit', 20))
        
        qa_pairs = get_questions_and_answers(question_type, limit)
        
        return Response({
            'success': True,
            'questions_and_answers': qa_pairs,
            'count': len(qa_pairs),
            'question_type': question_type or 'all'
        })
        
    except Exception as e:
        logger.error(f"Error getting questions and answers: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_top_rated_qa_api(request):
    """Get top-rated questions and answers"""
    try:
        question_type = request.GET.get('question_type')
        limit = int(request.GET.get('limit', 10))
        
        top_qa = get_top_rated_qa(question_type, limit)
        
        return Response({
            'success': True,
            'top_rated_qa': top_qa,
            'count': len(top_qa),
            'question_type': question_type or 'all'
        })
        
    except Exception as e:
        logger.error(f"Error getting top-rated Q&A: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_recent_qa_api(request):
    """Get recent questions and answers"""
    try:
        question_type = request.GET.get('question_type')
        limit = int(request.GET.get('limit', 10))
        
        recent_qa = get_recent_qa(question_type, limit)
        
        return Response({
            'success': True,
            'recent_qa': recent_qa,
            'count': len(recent_qa),
            'question_type': question_type or 'all'
        })
        
    except Exception as e:
        logger.error(f"Error getting recent Q&A: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def search_qa_api(request):
    """Search questions and answers by keyword"""
    try:
        keyword = request.GET.get('keyword', '')
        question_type = request.GET.get('question_type')
        
        if not keyword:
            return Response({
                'success': False,
                'error': 'Keyword parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        search_results = search_qa_by_keyword(keyword, question_type)
        
        return Response({
            'success': True,
            'search_results': search_results,
            'count': len(search_results),
            'keyword': keyword,
            'question_type': question_type or 'all'
        })
        
    except Exception as e:
        logger.error(f"Error searching Q&A: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
