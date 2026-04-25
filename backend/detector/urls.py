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
    
    # Legacy endpoints (backward compatibility)
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('detect/', views.detect, name='detect'),
    path('analytics/', views.analytics_view, name='analytics'),
]
