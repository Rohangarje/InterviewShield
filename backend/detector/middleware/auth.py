from django.http import JsonResponse
from django.shortcuts import redirect

def require_login(view_func):
    """Decorator for views - require session user"""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Authentication required'}, status=401)
            return redirect('/auth/login/')
        return view_func(request, *args, **kwargs)
    return wrapper
