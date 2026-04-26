from django.urls import path
from . import views

urlpatterns = [
    # HTML Pages
    path('', views.home, name='home'),
    path('auth/login/', views.login_page_view, name='login_page'),
    path('auth/signup/', views.signup_page_view, name='signup_page'),
    
    # API Endpoints
    path('api/auth/login/', views.login_view, name='api_login'),
    path('api/auth/signup/', views.signup_view, name='api_signup'),
    path('api/auth/logout/', views.logout_view, name='api_logout'),
    path('api/detect/', views.detect, name='api_detect'),
    path('api/analytics/', views.analytics_view, name='api_analytics'),
    
    # Interview Endpoints
    path('api/interview/start/', views.start_interview, name='api_interview_start'),
    path('api/interview/end/', views.end_interview, name='api_interview_end'),
    path('api/interview/list/', views.list_interviews, name='api_interview_list'),
    path('api/interview/<int:interview_id>/report/', views.get_report, name='api_interview_report'),
    path('api/interview/<int:interview_id>/detections/', views.get_interview_detections, name='api_interview_detections'),
    path('api/resume/upload/', views.upload_resume, name='api_resume_upload'),
    path('api/resume/get/', views.get_resume, name='api_resume_get'),
    path('api/logs/', views.session_logs, name='api_session_logs'),
    
    # Legacy endpoints (backward compatibility)
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('detect/', views.detect, name='detect'),
    path('analytics/', views.analytics_view, name='analytics'),
]
