from django.db import models
import mongoengine
from mongoengine import Document, StringField, DateTimeField
from datetime import datetime, timezone
import os

# MongoDB Session Models
class MongoDBUserSession(Document):
    """MongoDB model for tracking user login sessions"""
    user_id = StringField(required=True)
    user_email = StringField(required=True)
    user_name = StringField(required=True)
    session_key = StringField(required=True, unique=True)
    login_time = DateTimeField(default=lambda: datetime.now(timezone.utc))
    last_activity = DateTimeField(default=lambda: datetime.now(timezone.utc))
    is_active = StringField(default='active', choices=['active', 'inactive'])
    ip_address = StringField(max_length=45)  # IPv6 support
    user_agent = StringField(max_length=500)
    logout_time = DateTimeField(required=False)  # Make this optional
    
    meta = {
        'collection': 'user_sessions',
        'indexes': [
            'user_id',
            'session_key',
            'is_active',
            'last_activity'
        ]
    }
    
    def __str__(self):
        return f"{self.user_name} - {self.session_key}"

class MongoDBUserActivity(Document):
    """MongoDB model for tracking user activities"""
    user_id = StringField(required=True)
    user_email = StringField(required=True)
    activity_type = StringField(required=True, choices=[
        'login', 'logout', 'search', 'image_search', 'voice_search', 'page_view'
    ])
    activity_data = StringField(max_length=1000)  # JSON string for additional data
    timestamp = DateTimeField(default=lambda: datetime.now(timezone.utc))
    ip_address = StringField(max_length=45)
    user_agent = StringField(max_length=500)
    
    meta = {
        'collection': 'user_activities',
        'indexes': [
            'user_id',
            'activity_type',
            'timestamp'
        ]
    }
    
    def __str__(self):
        return f"{self.user_email} - {self.activity_type} - {self.timestamp}"

# Django Session Models (fallback)
class DjangoUserSession(models.Model):
    """Django model for tracking user login sessions (fallback)"""
    user_id = models.CharField(max_length=100)
    user_email = models.CharField(max_length=254)
    user_name = models.CharField(max_length=100)
    session_key = models.CharField(max_length=100, unique=True)
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], default='active')
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    logout_time = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'user_sessions'
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['session_key']),
            models.Index(fields=['is_active']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"{self.user_name} - {self.session_key}"

class DjangoUserActivity(models.Model):
    """Django model for tracking user activities (fallback)"""
    user_id = models.CharField(max_length=100)
    user_email = models.CharField(max_length=254)
    activity_type = models.CharField(max_length=20, choices=[
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('search', 'Search'),
        ('image_search', 'Image Search'),
        ('voice_search', 'Voice Search'),
        ('page_view', 'Page View')
    ])
    activity_data = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'user_activities'
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user_email} - {self.activity_type} - {self.timestamp}"

# Set the appropriate models based on database availability
try:
    # Test MongoDB connection
    from pdf_qa.settings import MONGODB_HOST, MONGODB_PORT, MONGODB_DB, MONGODB_USERNAME, MONGODB_PASSWORD
    
    # Connect to MongoDB with proper authentication if credentials are provided
    if MONGODB_USERNAME and MONGODB_PASSWORD:
        mongoengine.connect(
            db=MONGODB_DB,
            host=f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DB}"
        )
    else:
        mongoengine.connect(
            db=MONGODB_DB,
            host=MONGODB_HOST,
            port=MONGODB_PORT
        )
    
    # Test if we can actually use MongoDB
    MongoDBUserSession.objects.count()
    
    UserSession = MongoDBUserSession
    UserActivity = MongoDBUserActivity
    print("✅ Using MongoDB models for session tracking")
    
except Exception as e:
    print(f"⚠️ MongoDB not available, using Django models for session tracking: {e}")
    UserSession = DjangoUserSession
    UserActivity = DjangoUserActivity
