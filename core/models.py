from django.db import models
from django.contrib.auth.hashers import make_password, check_password
import mongoengine
from mongoengine import Document, StringField, DateTimeField
from datetime import datetime
import os

# MongoDB Connection
try:
    from pdf_qa.settings import MONGODB_HOST, MONGODB_PORT, MONGODB_DB, MONGODB_USERNAME, MONGODB_PASSWORD
    
    # Connect to MongoDB
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
    print(f"✅ Connected to MongoDB: {MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DB}")
except Exception as e:
    print(f"⚠️ MongoDB connection failed: {e}")
    print("Falling back to SQLite for User model")

# MongoDB User Model
class MongoDBUser(Document):
    """MongoDB User model using mongoengine"""
    name = StringField(required=True, max_length=100)
    email = StringField(required=True, unique=True, max_length=254)
    password = StringField(required=True, max_length=128)
    role = StringField(required=True, max_length=20, default='user', choices=['admin', 'manager', 'user'])
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'users',
        'indexes': ['email']
    }
    
    def set_password(self, raw_password):
        """Hash and set the password"""
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        """Check if the provided password matches"""
        return check_password(raw_password, self.password)
    
    def save(self, *args, **kwargs):
        """Override save to update updated_at"""
        self.updated_at = datetime.now()
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return self.email

# Django User Model (fallback)
class User(models.Model):
    """Django User model for SQLite (fallback)"""
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('user', 'User'),
    ]
    
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def set_password(self, raw_password):
        """Hash and set the password"""
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        """Check if the provided password matches"""
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return self.email

# Use MongoDB User by default, fallback to Django User if MongoDB fails
try:
    # Test MongoDB connection
    MongoDBUser.objects.count()
    User = MongoDBUser
    print("✅ Using MongoDB User model")
except Exception as e:
    print(f"⚠️ MongoDB not available, using Django User model: {e}")
    # User is already set to Django User model
