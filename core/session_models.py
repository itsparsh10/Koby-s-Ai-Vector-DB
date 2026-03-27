from django.db import models


class DjangoUserSession(models.Model):
    """Django model for tracking user login sessions."""
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
    """Django model for tracking user activities."""
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

UserSession = DjangoUserSession
UserActivity = DjangoUserActivity
