#!/usr/bin/env python3
"""
Startup script for the PDF QA system
This script helps start the Django server with proper setup
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    try:
        import django
        print(f"✅ Django {django.get_version()}")
    except ImportError:
        print("❌ Django not found. Please install it first.")
        return False
    
    try:
        import rest_framework
        print("✅ Django REST Framework")
    except ImportError:
        print("❌ Django REST Framework not found. Please install it first.")
        return False
    
    return True

def check_database():
    """Check if database is properly set up"""
    print("\n🗄️  Checking database...")
    
    try:
        # Set Django environment
        project_dir = Path(__file__).resolve().parent
        sys.path.insert(0, str(project_dir))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_qa.settings')
        
        import django
        django.setup()
        
        from core.models import User
        user_count = User.objects.count()
        print(f"✅ Database connection successful. Found {user_count} users.")
        return True
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        print("💡 Try running: python setup_database.py")
        return False

def start_server():
    """Start the Django development server"""
    print("\n🚀 Starting Django server...")
    
    try:
        # Change to project directory
        project_dir = Path(__file__).resolve().parent
        os.chdir(project_dir)
        
        # Start the server
        print("🌐 Server will be available at: http://localhost:8000/")
        print("🔑 Login page: http://localhost:8000/")
        print("📝 Create account: http://localhost:8000/create-account/")
        print("🏠 Home page: http://localhost:8000/home/")
        print("\n⏹️  Press Ctrl+C to stop the server")
        print("-" * 50)
        
        subprocess.run([sys.executable, "manage.py", "runserver"], check=True)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start server: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    """Main function"""
    print("🚀 PDF QA System Startup")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Dependencies check failed. Please install required packages.")
        return
    
    # Check database
    if not check_database():
        print("\n❌ Database check failed. Please set up the database first.")
        return
    
    # Start server
    start_server()

if __name__ == "__main__":
    main()
