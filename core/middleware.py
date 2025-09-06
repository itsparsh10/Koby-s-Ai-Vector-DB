from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

class AuthenticationMiddleware:
    """Middleware to redirect unauthenticated users to login page"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs that don't require authentication
        self.public_urls = [
            '/',
            '/login/',
            '/create-account/',
            '/api/auth/login/',
            '/api/auth/register/',
            '/api/auth/logout/',
            '/api/auth/check/',
            '/static/',
            '/admin/',
        ]
        
        # URLs that are always allowed
        self.always_allowed = [
            '/api/health/',
            '/api/documents/',
            '/api/ask/',
        ]
    
    def __call__(self, request):
        # Check if user is authenticated
        user_id = request.session.get('user_id')
        
        # Get current path
        current_path = request.path
        
        # Allow public URLs and always allowed URLs
        if any(current_path.startswith(url) for url in self.public_urls + self.always_allowed):
            response = self.get_response(request)
            return response
        
        # If user is not authenticated and trying to access protected page
        if not user_id and current_path == '/home/':
            # Redirect to login page
            return redirect('/')
        
        # If user is authenticated and trying to access login/register pages
        if user_id and current_path in ['/', '/login/', '/create-account/']:
            # Redirect to home page
            return redirect('/home/')
        
        response = self.get_response(request)
        return response
