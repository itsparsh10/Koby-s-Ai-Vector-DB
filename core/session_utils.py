from datetime import datetime, timedelta, timezone
import json

# Import session models with error handling
try:
    from .session_models import UserSession, UserActivity
    from .models import User
    SESSION_MODELS_AVAILABLE = True
    SESSION_TRACKING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Session models not available: {e}")
    SESSION_MODELS_AVAILABLE = False
    SESSION_TRACKING_AVAILABLE = False
    # Create dummy classes to prevent errors
    class DummyUserSession:
        def __init__(self, **kwargs):
            pass
        def save(self):
            pass
        @classmethod
        def objects(cls):
            return DummyQuerySet()
    
    class DummyQuerySet:
        def filter(self, **kwargs):
            return self
        def first(self):
            return None
        def count(self):
            return 0
        def delete(self):
            pass
    
    class DummyUserActivity:
        def __init__(self, **kwargs):
            pass
        def save(self):
            pass
        @classmethod
        def objects(cls):
            return DummyQuerySet()
    
    UserSession = DummyUserSession
    UserActivity = DummyUserActivity
    User = None

def get_client_ip(request):
    """Get client IP address from request"""
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    except Exception:
        return 'unknown'

def get_user_agent(request):
    """Get user agent from request"""
    try:
        return request.META.get('HTTP_USER_AGENT', '')
    except Exception:
        return 'unknown'

def track_user_login(request, user):
    """Track user login activity"""
    if not SESSION_MODELS_AVAILABLE:
        print("⚠️ Session tracking not available")
        return False
        
    try:
        # Ensure session is created and has a key
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        if not session_key:
            print("❌ Failed to get session key")
            return False

        # Get client information
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Create session record
        session_record = UserSession(
            user_id=str(user.id),
            user_email=user.email,
            user_name=user.name,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=user_agent
        )
        session_record.save()

        # Create activity record
        activity_record = UserActivity(
            user_id=str(user.id),
            user_email=user.email,
            activity_type='login',
            ip_address=ip_address,
            user_agent=user_agent
        )
        activity_record.save()
        
        print(f"✅ Login tracked for user: {user.email} with session: {session_key}")
        return True
        
    except Exception as e:
        print(f"❌ Error tracking login: {str(e)}")
        return False

def track_user_logout(request, user_id):
    """Track user logout activity"""
    if not SESSION_MODELS_AVAILABLE:
        print("⚠️ Session tracking not available")
        return False
        
    try:
        # Update session record
        session_record = UserSession.objects.filter(
            user_id=str(user_id),
            session_key=request.session.session_key
        ).first()
        
        if session_record:
            session_record.is_active = 'inactive'
            session_record.logout_time = datetime.now(timezone.utc)
            session_record.save()
        
        # Create activity record
        if User:
            user = User.objects.filter(id=user_id).first()
            if user:
                activity_record = UserActivity(
                    user_id=str(user_id),
                    user_email=user.email,
                    activity_type='logout',
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                activity_record.save()
        
        print(f"✅ Logout tracked for user ID: {user_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error tracking logout: {str(e)}")
        return False

def track_user_activity(request, user_id, activity_type, activity_data=None):
    """Track user activity"""
    if not SESSION_MODELS_AVAILABLE:
        print("⚠️ Session tracking not available")
        return False
        
    try:
        if User:
            user = User.objects.filter(id=user_id).first()
            if user:
                # Update last activity in session
                session_record = UserSession.objects.filter(
                    user_id=str(user_id),
                    session_key=request.session.session_key,
                    is_active='active'
                ).first()
                
                if session_record:
                    session_record.last_activity = datetime.now(timezone.utc)
                    session_record.save()
                
                # Create activity record
                activity_record = UserActivity(
                    user_id=str(user_id),
                    user_email=user.email,
                    activity_type=activity_type,
                    activity_data=json.dumps(activity_data) if activity_data else None,
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                activity_record.save()
                
                print(f"✅ Activity tracked: {user.email} - {activity_type}")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error tracking activity: {str(e)}")
        return False

def get_live_user_count():
    """Get count of currently active users"""
    if not SESSION_MODELS_AVAILABLE:
        return 0
        
    try:
        # Get users active in the last 30 minutes
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        active_sessions = UserSession.objects.filter(
            is_active='active',
            last_activity__gte=cutoff_time
        )
        
        return active_sessions.count()
        
    except Exception as e:
        print(f"❌ Error getting live user count: {str(e)}")
        return 0

def get_user_session_stats():
    """Get comprehensive user session statistics"""
    if not SESSION_MODELS_AVAILABLE:
        return {
            'total_sessions': 0,
            'active_sessions': 0,
            'today_sessions': 0,
            'live_users': 0
        }
        
    try:
        total_sessions = UserSession.objects.count()
        active_sessions = UserSession.objects.filter(is_active='active').count()
        today_sessions = UserSession.objects.filter(
            login_time__gte=datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        ).count()
        
        return {
            'total_sessions': total_sessions,
            'active_sessions': active_sessions,
            'today_sessions': today_sessions,
            'live_users': get_live_user_count()
        }
        
    except Exception as e:
        print(f"❌ Error getting session stats: {str(e)}")
        return {
            'total_sessions': 0,
            'active_sessions': 0,
            'today_sessions': 0,
            'live_users': 0
        }

def cleanup_old_sessions():
    """Clean up old inactive sessions (older than 24 hours)"""
    if not SESSION_MODELS_AVAILABLE:
        return 0
        
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        old_sessions = UserSession.objects.filter(
            is_active='inactive',
            logout_time__lt=cutoff_time
        )
        
        count = old_sessions.count()
        old_sessions.delete()
        
        print(f"✅ Cleaned up {count} old sessions")
        return count
        
    except Exception as e:
        print(f"❌ Error cleaning up sessions: {str(e)}")
        return 0

def get_user_activity_summary(user_id, days=7):
    """Get user activity summary for the last N days"""
    if not SESSION_MODELS_AVAILABLE:
        return {
            'total_activities': 0,
            'activity_breakdown': {},
            'period_days': days
        }
        
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        activities = UserActivity.objects.filter(
            user_id=str(user_id),
            timestamp__gte=cutoff_time
        ).order_by('-timestamp')
        
        # Group by activity type
        activity_summary = {}
        for activity in activities:
            activity_type = activity.activity_type
            if activity_type not in activity_summary:
                activity_summary[activity_type] = 0
            activity_summary[activity_type] += 1
        
        return {
            'total_activities': activities.count(),
            'activity_breakdown': activity_summary,
            'period_days': days
        }
        
    except Exception as e:
        print(f"❌ Error getting user activity summary: {str(e)}")
        return {
            'total_activities': 0,
            'activity_breakdown': {},
            'period_days': days
        }
