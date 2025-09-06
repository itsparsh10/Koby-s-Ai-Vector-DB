from django.urls import path
from core.views import (
    ask, health_check, list_documents, image_search, create_account,
    admin_dashboard_stats, admin_upload_pdf, admin_create_user, 
    admin_list_users, admin_reindex_documents, admin_list_contributions,
    admin_approve_contribution, admin_bulk_approve_contributions, admin_approve_all_pending,
    user_login, user_create_account, user_logout, check_auth, get_live_user_count, 
    get_user_stats, get_user_activity, get_user_sessions, terminate_user_session, 
    cleanup_old_sessions, get_admin_dashboard_stats, submit_feedback, get_feedback_analytics, 
    get_top_contributions_api, get_questions_and_answers_api, get_top_rated_qa_api, 
    get_recent_qa_api, search_qa_api, create_user_with_role
)

urlpatterns = [
    path("ask/", ask, name="ask"),
    path("image-search/", image_search, name="image_search"),
    path("health/", health_check, name="health_check"),
    path("documents/", list_documents, name="list_documents"),
    path("create-account/", create_account, name="create_account"),
    
    # User Authentication endpoints
    path("auth/login/", user_login, name="user_login"),
    path("auth/register/", user_create_account, name="user_register"),
    path("auth/logout/", user_logout, name="user_logout"),
    path("auth/check/", check_auth, name="check_auth"),
    path("auth/create-user/", create_user_with_role, name="create_user_with_role"),
    
    # User Statistics endpoints
    path("auth/live-users/", get_live_user_count, name="live_user_count"),
    path("auth/stats/", get_user_stats, name="user_stats"),
    path("auth/dashboard-stats/", get_admin_dashboard_stats, name="admin_dashboard_stats"),
    path("auth/activity/", get_user_activity, name="user_activity"),
    
    # User Sessions Management endpoints
    path("auth/sessions/", get_user_sessions, name="get_user_sessions"),
    path("auth/terminate-session/", terminate_user_session, name="terminate_user_session"),
    path("auth/cleanup-sessions/", cleanup_old_sessions, name="cleanup_old_sessions"),
    
    # Admin endpoints
    path("admin/dashboard-stats/", admin_dashboard_stats, name="admin_dashboard_stats"),
    path("admin/upload-pdf/", admin_upload_pdf, name="admin_upload_pdf"),
    path("admin/create-user/", admin_create_user, name="admin_create_user"),
    path("admin/list-users/", admin_list_users, name="admin_list_users"),
    path("admin/reindex-documents/", admin_reindex_documents, name="admin_reindex_documents"),
    
    # Admin contribution management endpoints
    path("admin/contributions/", admin_list_contributions, name="admin_list_contributions"),
    path("admin/contributions/approve/", admin_approve_contribution, name="admin_approve_contribution"),
    path("admin/contributions/bulk-approve/", admin_bulk_approve_contributions, name="admin_bulk_approve_contributions"),
    path("admin/contributions/approve-all-pending/", admin_approve_all_pending, name="admin_approve_all_pending"),
    
    # Feedback and User Contributions endpoints
    path("feedback/", submit_feedback, name="submit_feedback"),
    path("feedback/analytics/", get_feedback_analytics, name="get_feedback_analytics"),
    path("feedback/top-contributions/", get_top_contributions_api, name="get_top_contributions"),
    
    # Questions and Answers endpoints
    path("feedback/questions-answers/", get_questions_and_answers_api, name="get_questions_and_answers"),
    path("feedback/top-rated-qa/", get_top_rated_qa_api, name="get_top_rated_qa"),
    path("feedback/recent-qa/", get_recent_qa_api, name="get_recent_qa"),
    path("feedback/search-qa/", search_qa_api, name="search_qa"),
]
