#!/usr/bin/env python3
"""
Simple test to verify the dual search system fixes
"""

import os
import sys
import django

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_qa.settings')
django.setup()

def test_imports():
    """Test if all imports work"""
    print("Testing imports...")
    try:
        from core.enhanced_search import enhanced_search_with_contributions
        from core.mongodb_utils import search_similar_contributions, connect_to_mongodb
        from core.feedback_models import UserContribution
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_mongodb_connection():
    """Test MongoDB connection"""
    print("Testing MongoDB connection...")
    try:
        from core.mongodb_utils import connect_to_mongodb
        success = connect_to_mongodb()
        if success:
            print("✅ MongoDB connection successful")
            return True
        else:
            print("❌ MongoDB connection failed")
            return False
    except Exception as e:
        print(f"❌ MongoDB connection error: {e}")
        return False

def test_contribution_search():
    """Test MongoDB contribution search"""
    print("Testing contribution search...")
    try:
        from core.mongodb_utils import search_similar_contributions
        results = search_similar_contributions("How to handle customer complaints?", limit=3)
        print(f"✅ Found {len(results)} contributions")
        return True
    except Exception as e:
        print(f"❌ Contribution search error: {e}")
        return False

def test_enhanced_search():
    """Test enhanced search"""
    print("Testing enhanced search...")
    try:
        from core.enhanced_search import enhanced_search_with_contributions
        result = enhanced_search_with_contributions(
            "How to handle customer complaints?", 
            k=3, 
            include_contributions=True, 
            contribution_limit=3
        )
        if result['success']:
            faiss_count = result['search_metadata']['faiss_count']
            contrib_count = result['search_metadata']['contribution_count']
            print(f"✅ Enhanced search successful - FAISS: {faiss_count}, Contributions: {contrib_count}")
            return True
        else:
            print(f"❌ Enhanced search failed: {result['error']}")
            return False
    except Exception as e:
        print(f"❌ Enhanced search error: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Testing Dual Search System Fixes")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_mongodb_connection,
        test_contribution_search,
        test_enhanced_search
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
        print()
    
    print("=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The dual search system is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
