#!/usr/bin/env python3
"""
Database Setup Script for PDF QA System
This script helps initialize the database and create the first user.
Supports both MongoDB and SQLite fallback.
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

# Set Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_qa.settings')
django.setup()

try:
    from core.models import User, MongoDBUser
    print("✅ Models imported successfully")
except Exception as e:
    print(f"❌ Error importing models: {e}")
    sys.exit(1)

def create_superuser():
    """Create a superuser account"""
    try:
        # Check if superuser already exists
        existing_users = User.objects.filter(email='admin@example.com')
        if existing_users.count() > 0:
            print("Superuser already exists!")
            return
        
        # Create superuser
        admin_user = User(
            name='Admin User',
            email='admin@example.com'
        )
        admin_user.set_password('admin123')
        admin_user.save()
        
        print("✅ Superuser created successfully!")
        print("Email: admin@example.com")
        print("Password: admin123")
        print("\n⚠️  IMPORTANT: Change these credentials after first login!")
        
    except Exception as e:
        print(f"❌ Error creating superuser: {e}")

def check_database_connection():
    """Check if database connection is working"""
    try:
        # Try to count users
        user_count = User.objects.count()
        
        # Check which model we're using
        if isinstance(User, type(MongoDBUser)):
            print(f"✅ MongoDB connection successful! Found {user_count} users.")
            print("📊 Database: MongoDB")
        else:
            print(f"✅ SQLite connection successful! Found {user_count} users.")
            print("📊 Database: SQLite")
        
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_user_operations():
    """Test basic user operations"""
    try:
        # Create a test user
        test_user = User(
            name='Test User',
            email='test@example.com'
        )
        test_user.set_password('test123')
        test_user.save()
        
        print("✅ User creation test passed")
        
        # Test password verification
        if test_user.check_password('test123'):
            print("✅ Password verification test passed")
        else:
            print("❌ Password verification test failed")
        
        # Test user retrieval
        retrieved_user = User.objects.get(email='test@example.com')
        print(f"✅ User retrieval test passed: {retrieved_user.name}")
        
        # Clean up test user
        test_user.delete()
        print("✅ User deletion test passed")
        
        return True
        
    except Exception as e:
        print(f"❌ User operations test failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Database Setup for PDF QA System")
    print("=" * 50)
    
    # Check database connection
    if not check_database_connection():
        print("\n❌ Cannot proceed without database connection.")
        print("Please check your database settings and try again.")
        return
    
    # Test user operations
    print("\n🧪 Testing user operations...")
    if not test_user_operations():
        print("\n❌ User operations test failed.")
        return
    
    # Create superuser
    print("\n📝 Creating superuser account...")
    create_superuser()
    
    print("\n🎉 Setup completed!")
    print("\nNext steps:")
    print("1. Start the Django server: python manage.py runserver")
    print("2. Visit http://localhost:8000/login/ to test login")
    print("3. Visit http://localhost:8000/create-account/ to test registration")

if __name__ == "__main__":
    main()
