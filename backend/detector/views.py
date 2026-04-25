import cv2
import numpy as np
import base64
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from .models import DetectionLog
from .yolo_detector import YOLODetector
from .utils.auth import create_user, authenticate_user

# Global instances (loaded once)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
yolo_detector = YOLODetector()

def home(request):
    if not request.session.get('user_id'):
        return redirect('/auth/login/')
    return render(request, 'detector/index.html')

def login_page_view(request):
    """Serve login page (GET request)"""
    if request.session.get('user_id'):
        return redirect('/')
    return render(request, 'detector/auth/login.html')

def signup_page_view(request):
    """Serve signup page (GET request)"""
    if request.session.get('user_id'):
        return redirect('/')
    return render(request, 'detector/auth/signup.html')

@csrf_exempt
def signup_view(request):
    """Handle signup - POST returns JSON, GET returns form"""
    if request.method == 'POST':
        try:
            if not request.body:
                return JsonResponse({'error': 'Empty request body'}, status=400)
            
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                return JsonResponse({'error': f'Invalid JSON: {str(e)}'}, status=400)
            
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            if not all([username, email, password]):
                return JsonResponse({'error': 'All fields required'}, status=400)
            if len(password) < 6:
                return JsonResponse({'error': 'Password must be 6+ chars'}, status=400)
            
            try:
                user_id = create_user(username, email, password)
                if user_id:
                    return JsonResponse({'message': 'Account created! Please login.'})
                return JsonResponse({'error': 'Username already taken'}, status=400)
            except Exception as auth_err:
                return JsonResponse({'error': f'Signup error: {str(auth_err)}'}, status=500)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
    
    # GET request - serve signup form
    if request.session.get('user_id'):
        return redirect('/')
    return render(request, 'detector/auth/signup.html')

@csrf_exempt
def login_view(request):
    """Handle login - POST returns JSON, GET returns form"""
    if request.method == 'POST':
        try:
            if not request.body:
                return JsonResponse({'error': 'Empty request body'}, status=400)
            
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                return JsonResponse({'error': f'Invalid JSON: {str(e)}'}, status=400)
            
            username = data.get('username', '').strip()
            password = data.get('password', '')
            
            if not username or not password:
                return JsonResponse({'error': 'Username and password required'}, status=400)
            
            try:
                user = authenticate_user(username, password)
                if user:
                    request.session['user_id'] = str(user['_id'])
                    request.session['username'] = username
                    return JsonResponse({'message': 'Login success', 'username': username})
                return JsonResponse({'error': 'Invalid username/password'}, status=401)
            except Exception as auth_err:
                return JsonResponse({'error': f'Authentication error: {str(auth_err)}'}, status=500)
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
    
    # GET request - serve login form
    if request.session.get('user_id'):
        return redirect('/')
    return render(request, 'detector/auth/login.html')

@csrf_exempt
def logout_view(request):
    request.session.flush()
    return JsonResponse({'message': 'Logged out successfully'})

def analytics_view(request):
    # Get recent data (last 30 days)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    logs = DetectionLog.objects.filter(timestamp__gte=start_date)
    total_sessions = logs.count()
    
    # Categories as per task - count based on compound statuses
    normal_count = logs.filter(status__startswith='normal').count()
    noface_count = logs.filter(status__startswith='no_face').count()
    mobile_count = logs.filter(phone_detected=True).count()
    high_risk_count = logs.filter(risk_score='high').count()
    cheating_pct = round((high_risk_count / total_sessions * 100), 1) if total_sessions > 0 else 0
    
    # Summary
    summary = {
        'total_sessions': total_sessions,
        'normal': normal_count,
        'no_face': noface_count,
        'mobile_detected': mobile_count,
        'cheating_pct': cheating_pct,
        'avg_phone_conf': round(logs.filter(phone_detected=True).aggregate(avg=Avg('phone_confidence'))['avg'] or 0, 2),
    }
    
    # Pie chart: distribution %
    pie_data = {
        'labels': ['Normal', 'No Face', 'Mobile Detected', 'Other'],
        'data': [
            round(normal_count / total_sessions * 100, 1) if total_sessions else 0,
            round(noface_count / total_sessions * 100, 1) if total_sessions else 0,
            round(mobile_count / total_sessions * 100, 1) if total_sessions else 0,
            round((total_sessions - normal_count - noface_count - mobile_count) / total_sessions * 100, 1) if total_sessions else 0
        ]
    }
    
    # Bar chart: absolute counts
    bar_data = {
        'labels': ['Normal', 'No Face', 'Mobile', 'High Risk'],
        'data': [normal_count, noface_count, mobile_count, high_risk_count]
    }
    
    # Line chart: daily trends (group by date)
    daily_data = defaultdict(lambda: defaultdict(int))
    for log in logs:
        date_str = log.timestamp.strftime('%Y-%m-%d')
        daily_data[date_str]['normal'] += 1 if log.status.startswith('normal') else 0
        daily_data[date_str]['no_face'] += 1 if log.status.startswith('no_face') else 0
        daily_data[date_str]['mobile'] += 1 if log.phone_detected else 0
    
    dates = sorted(daily_data.keys())
    line_data = {
        'labels': dates,
        'datasets': {
            'normal': [daily_data[d]['normal'] for d in dates],
            'no_face': [daily_data[d]['no_face'] for d in dates],
            'mobile': [daily_data[d]['mobile'] for d in dates]
        }
    }
    
    return JsonResponse({
        'summary': summary,
        'pie': pie_data,
        'bar': bar_data,
        'line': line_data,
        'updated': timezone.now().isoformat()
    })

@csrf_exempt
def detect(request):
    if request.method == 'POST':
        try:
            # Get base64 image from request
            if not request.body:
                return JsonResponse({'error': 'Empty request body'}, status=400)
            
            data = json.loads(request.body)
            img_base64 = data.get('image')
            
            if not img_base64:
                return JsonResponse({'error': 'No image provided'}, status=400)
            
            # Decode base64 to numpy array
            try:
                if ',' in img_base64:
                    img_data = base64.b64decode(img_base64.split(',')[1])
                else:
                    img_data = base64.b64decode(img_base64)
            except Exception as e:
                return JsonResponse({'error': f'Invalid base64 image: {str(e)}'}, status=400)
            
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return JsonResponse({'error': 'Failed to decode image'}, status=400)
            
            # FACE DETECTION (existing)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            face_count = len(faces)
            
            if face_count == 0:
                face_status = 'no_face'
                face_alert = 'No face detected!'
            elif face_count > 1:
                face_status = 'multiple_faces'
                face_alert = 'Multiple faces!'
            else:
                face_status = 'normal'
                face_alert = 'Single face OK'
            
            # YOLO PHONE DETECTION (NEW)
            phone_result = yolo_detector.detect_phone(frame)
            
            # COMBINED RISK ASSESSMENT
            risk_score = 'low'
            overall_alert = face_alert
            cheating_indicators = []
            
            if phone_result['phone_detected']:
                risk_score = 'high'
                overall_alert = '🚨 MOBILE PHONE DETECTED - CHEATING!'
                cheating_indicators.append('Mobile')
            
            if face_status != 'normal':
                risk_score = 'high' if risk_score == 'high' else 'medium'
                cheating_indicators.append(face_status.replace('_', ' '))
            
            # Save Django model
            log = DetectionLog.objects.create(
                status=f"{face_status}_{'phone' if phone_result['phone_detected'] else 'no_phone'}",
                face_count=face_count,
                phone_detected=phone_result['phone_detected'],
                phone_confidence=phone_result['confidence'],
                risk_score=risk_score,
                image_base64=img_base64[:1000] + '...'
            )
            
            # === MONGO DB SAVE ===
            from .utils.mongo_client import insert_detection_log
            username = data.get('username', 'anonymous')
            mongo_doc = {
                'username': username,
                'status': risk_score,
                'timestamp': timezone.now().isoformat(),
                'face_count': face_count,
                'phone_detected': phone_result['phone_detected'],
                'risk_score': risk_score,
                'django_log_id': log.id
            }
            mongo_id = insert_detection_log(mongo_doc)
            
            return JsonResponse({
                'face_status': face_status,
                'face_count': face_count,
                'phone_detected': phone_result['phone_detected'],
                'phone_confidence': round(phone_result['confidence'], 2),
                'risk_score': risk_score,
                'alert': overall_alert,
                'indicators': cheating_indicators,
                'log_id': log.id,
                'mongo_id': str(mongo_id) if mongo_id else None
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'POST required'}, status=405)
