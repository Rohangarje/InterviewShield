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
from .models import DetectionLog, InterviewSession, InterviewReport
from .yolo_detector import YOLODetector
from .utils.auth import create_user, authenticate_user, update_user_resume, get_user_resume

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
            
            # Find active interview session for this user
            user_id = request.session.get('user_id')
            active_session = None
            if user_id:
                active_session = InterviewSession.objects.filter(
                    user_id=user_id, status='active'
                ).first()
            
            # Save Django model with session link
            log = DetectionLog.objects.create(
                session=active_session,
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

# ================= INTERVIEW MANAGEMENT =================

@csrf_exempt
def start_interview(request):
    """Start a new interview session for the logged-in user"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    user_id = request.session.get('user_id')
    username = request.session.get('username', 'anonymous')
    
    if not user_id:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    # End any existing active interview
    InterviewSession.objects.filter(user_id=user_id, status='active').update(
        status='completed', end_time=timezone.now()
    )
    
    # Create new interview session
    session = InterviewSession.objects.create(
        user_id=user_id,
        username=username,
        status='active'
    )
    
    return JsonResponse({
        'interview_id': session.id,
        'start_time': session.start_time.isoformat(),
        'status': session.status,
        'message': 'Interview started successfully'
    })

@csrf_exempt
def end_interview(request):
    """End the active interview session and generate report"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    user_id = request.session.get('user_id')
    username = request.session.get('username', 'anonymous')
    
    if not user_id:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        session = InterviewSession.objects.get(user_id=user_id, status='active')
    except InterviewSession.DoesNotExist:
        return JsonResponse({'error': 'No active interview session found'}, status=404)
    
    # End the session
    session.status = 'completed'
    session.end_time = timezone.now()
    session.save()
    
    # Generate report
    report = generate_interview_report(session)
    
    return JsonResponse({
        'interview_id': session.id,
        'end_time': session.end_time.isoformat(),
        'duration_seconds': int(session.duration_seconds),
        'status': session.status,
        'report': {
            'id': report.id,
            'overall_risk': report.overall_risk,
            'total_detections': report.total_detections,
            'phone_detections': report.phone_detections,
            'no_face_detections': report.no_face_detections,
            'cheating_percentage': report.cheating_percentage,
            'generated_at': report.generated_at.isoformat()
        },
        'message': 'Interview ended and report generated'
    })

def generate_interview_report(session):
    """Generate a comprehensive report for an interview session"""
    detections = DetectionLog.objects.filter(session=session)
    total = detections.count()
    
    if total == 0:
        return InterviewReport.objects.create(
            session=session,
            total_detections=0,
            overall_risk='low',
            report_data={'message': 'No detection data recorded during this session'}
        )
    
    # Aggregate statistics
    phone_count = detections.filter(phone_detected=True).count()
    no_face_count = detections.filter(status__startswith='no_face').count()
    multiple_face_count = detections.filter(status__startswith='multiple_faces').count()
    high_risk = detections.filter(risk_score='high').count()
    medium_risk = detections.filter(risk_score='medium').count()
    low_risk = detections.filter(risk_score='low').count()
    
    avg_phone_conf = detections.filter(phone_detected=True).aggregate(avg=Avg('phone_confidence'))['avg'] or 0.0
    cheating_pct = round((high_risk / total * 100), 1)
    
    # Determine overall risk
    if cheating_pct >= 30 or phone_count > 5:
        overall_risk = 'high'
    elif cheating_pct >= 10 or phone_count > 2:
        overall_risk = 'medium'
    else:
        overall_risk = 'low'
    
    # Build timeline
    timeline = []
    for d in detections.order_by('timestamp')[:100]:
        timeline.append({
            'time': d.timestamp.strftime('%H:%M:%S'),
            'status': d.status,
            'face_count': d.face_count,
            'phone_detected': d.phone_detected,
            'risk_score': d.risk_score
        })
    
    # Risk breakdown by time segments
    risk_timeline = []
    segment_size = max(1, total // 20) if total > 20 else 1
    sorted_dets = list(detections.order_by('timestamp'))
    for i in range(0, len(sorted_dets), segment_size):
        segment = sorted_dets[i:i+segment_size]
        high_in_segment = sum(1 for d in segment if d.risk_score == 'high')
        risk_timeline.append({
            'segment': i // segment_size + 1,
            'high_risk_count': high_in_segment,
            'total': len(segment)
        })
    
    report_data = {
        'duration_seconds': int(session.duration_seconds),
        'detection_rate': round(total / max(session.duration_seconds, 1) * 60, 2),  # per minute
        'timeline': timeline,
        'risk_timeline': risk_timeline,
        'incidents': {
            'phone_detections': phone_count,
            'no_face_periods': no_face_count,
            'multiple_faces': multiple_face_count,
        },
        'recommendation': _get_recommendation(overall_risk, cheating_pct, phone_count)
    }
    
    # Generate HTML report
    report_html = _generate_report_html(session, report_data, detections)
    
    report = InterviewReport.objects.create(
        session=session,
        total_detections=total,
        phone_detections=phone_count,
        no_face_detections=no_face_count,
        multiple_face_detections=multiple_face_count,
        high_risk_count=high_risk,
        medium_risk_count=medium_risk,
        low_risk_count=low_risk,
        avg_phone_confidence=round(avg_phone_conf, 2),
        cheating_percentage=cheating_pct,
        overall_risk=overall_risk,
        report_data=report_data,
        report_html=report_html
    )
    
    return report

def _get_recommendation(risk, cheating_pct, phone_count):
    if risk == 'high':
        return "HIGH RISK: Significant cheating indicators detected. Multiple phone detections and/or extended no-face periods observed. Strong recommendation to disqualify."
    elif risk == 'medium':
        return "MEDIUM RISK: Some suspicious activity detected. Review flagged segments manually. Candidate may require additional verification."
    else:
        return "LOW RISK: Session appears normal. Candidate maintained proper posture throughout the interview. No significant anomalies."

def _generate_report_html(session, data, detections):
    risk_colors = {'high': '#ef4444', 'medium': '#f97316', 'low': '#22c55e'}
    risk_bg = {'high': 'rgba(239,68,68,0.1)', 'medium': 'rgba(249,115,22,0.1)', 'low': 'rgba(34,197,94,0.1)'}
    
    html = f"""
    <div style="font-family: 'Inter', sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; background: #0f0f23; color: #e2e8f0;">
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="color: #60a5fa; font-size: 2rem; margin-bottom: 0.5rem;">Interview Report</h1>
            <p style="opacity: 0.8;">Candidate: <strong>{session.username}</strong> | Interview #{session.id}</p>
            <p style="opacity: 0.6; font-size: 0.9rem;">{session.start_time.strftime('%Y-%m-%d %H:%M')} - {session.end_time.strftime('%H:%M') if session.end_time else 'Ongoing'}</p>
        </div>
        
        <div style="background: {risk_bg.get(session.report.overall_risk if hasattr(session, 'report') else 'low', 'rgba(34,197,94,0.1)')}; 
                    border: 1px solid {risk_colors.get(session.report.overall_risk if hasattr(session, 'report') else 'low', '#22c55e')}; 
                    border-radius: 16px; padding: 1.5rem; margin-bottom: 2rem; text-align: center;">
            <h2 style="color: {risk_colors.get(session.report.overall_risk if hasattr(session, 'report') else 'low', '#22c55e')}; margin-bottom: 0.5rem;">
                Overall Risk: {(session.report.overall_risk if hasattr(session, 'report') else 'low').upper()}
            </h2>
            <p>{data.get('recommendation', '')}</p>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
            <div style="background: rgba(20,20,40,0.8); border-radius: 12px; padding: 1.5rem; text-align: center;">
                <div style="font-size: 2rem; font-weight: 700; color: #60a5fa;">{data.get('duration_seconds', 0)//60}m</div>
                <div style="opacity: 0.8; font-size: 0.9rem;">Duration</div>
            </div>
            <div style="background: rgba(20,20,40,0.8); border-radius: 12px; padding: 1.5rem; text-align: center;">
                <div style="font-size: 2rem; font-weight: 700; color: #f97316;">{data['incidents']['phone_detections']}</div>
                <div style="opacity: 0.8; font-size: 0.9rem;">Phone Detections</div>
            </div>
            <div style="background: rgba(20,20,40,0.8); border-radius: 12px; padding: 1.5rem; text-align: center;">
                <div style="font-size: 2rem; font-weight: 700; color: #ef4444;">{data['incidents']['no_face_periods']}</div>
                <div style="opacity: 0.8; font-size: 0.9rem;">No Face Events</div>
            </div>
            <div style="background: rgba(20,20,40,0.8); border-radius: 12px; padding: 1.5rem; text-align: center;">
                <div style="font-size: 2rem; font-weight: 700; color: #a78bfa;">{len(data.get('timeline', []))}</div>
                <div style="opacity: 0.8; font-size: 0.9rem;">Total Detections</div>
            </div>
        </div>
        
        <div style="background: rgba(20,20,40,0.8); border-radius: 16px; padding: 1.5rem; margin-bottom: 2rem;">
            <h3 style="color: #60a5fa; margin-bottom: 1rem;">Timeline</h3>
            <div style="max-height: 400px; overflow-y: auto;">
    """
    
    for item in data.get('timeline', [])[:50]:
        color = risk_colors.get(item['risk_score'], '#6b7280')
        html += f"""
                <div style="display: flex; align-items: center; padding: 0.5rem; border-left: 3px solid {color}; margin-bottom: 0.5rem; background: rgba(255,255,255,0.02); border-radius: 0 8px 8px 0;">
                    <span style="width: 80px; font-family: monospace; opacity: 0.7;">{item['time']}</span>
                    <span style="flex: 1;">{item['status'].replace('_', ' ').title()}</span>
                    <span style="color: {color}; font-weight: 600;">{item['risk_score'].upper()}</span>
                </div>
        """
    
    html += """
            </div>
        </div>
        
        <div style="text-align: center; opacity: 0.5; font-size: 0.85rem; margin-top: 2rem;">
            Generated by InterviewShield AI Proctoring System
        </div>
    </div>
    """
    return html

def list_interviews(request):
    """List all interview sessions for the logged-in user"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    sessions = InterviewSession.objects.filter(user_id=user_id).order_by('-start_time')
    data = []
    for s in sessions:
        has_report = hasattr(s, 'report')
        data.append({
            'id': s.id,
            'start_time': s.start_time.isoformat(),
            'end_time': s.end_time.isoformat() if s.end_time else None,
            'status': s.status,
            'duration_seconds': int(s.duration_seconds),
            'has_resume': bool(s.resume),
            'has_report': has_report,
            'overall_risk': s.report.overall_risk if has_report else None,
            'cheating_percentage': s.report.cheating_percentage if has_report else None,
        })
    
    return JsonResponse({'interviews': data})

def get_report(request, interview_id):
    """Get detailed report for a specific interview"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        session = InterviewSession.objects.get(id=interview_id, user_id=user_id)
        report = InterviewReport.objects.get(session=session)
    except (InterviewSession.DoesNotExist, InterviewReport.DoesNotExist):
        return JsonResponse({'error': 'Interview or report not found'}, status=404)
    
    return JsonResponse({
        'interview_id': session.id,
        'start_time': session.start_time.isoformat(),
        'end_time': session.end_time.isoformat() if session.end_time else None,
        'duration_seconds': int(session.duration_seconds),
        'resume_url': session.resume.url if session.resume else None,
        'report': {
            'generated_at': report.generated_at.isoformat(),
            'overall_risk': report.overall_risk,
            'total_detections': report.total_detections,
            'phone_detections': report.phone_detections,
            'no_face_detections': report.no_face_detections,
            'multiple_face_detections': report.multiple_face_detections,
            'high_risk_count': report.high_risk_count,
            'medium_risk_count': report.medium_risk_count,
            'low_risk_count': report.low_risk_count,
            'avg_phone_confidence': report.avg_phone_confidence,
            'cheating_percentage': report.cheating_percentage,
            'data': report.report_data,
            'html': report.report_html
        }
    })

def get_interview_detections(request, interview_id):
    """Get detection logs for a specific interview"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        session = InterviewSession.objects.get(id=interview_id, user_id=user_id)
    except InterviewSession.DoesNotExist:
        return JsonResponse({'error': 'Interview not found'}, status=404)
    
    detections = DetectionLog.objects.filter(session=session).order_by('timestamp')
    data = []
    for d in detections:
        data.append({
            'id': d.id,
            'timestamp': d.timestamp.isoformat(),
            'status': d.status,
            'face_count': d.face_count,
            'phone_detected': d.phone_detected,
            'phone_confidence': d.phone_confidence,
            'risk_score': d.risk_score,
        })
    
    return JsonResponse({
        'interview_id': session.id,
        'detections': data,
        'count': len(data)
    })

@csrf_exempt
def upload_resume(request):
    """Upload resume (PDF or image) for the current user"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    user_id = request.session.get('user_id')
    username = request.session.get('username')
    if not user_id or not username:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    if 'resume' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    file = request.FILES['resume']
    
    # Validate file type
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if file.content_type not in allowed_types:
        return JsonResponse({
            'error': f'Invalid file type. Allowed: PDF, JPG, PNG. Got: {file.content_type}'
        }, status=400)
    
    # Validate file size (max 10MB)
    if file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Max 10MB.'}, status=400)
    
    # Get active interview or create detached upload
    session = InterviewSession.objects.filter(user_id=user_id, status='active').first()
    
    if session:
        # Save to active interview
        session.resume = file
        session.resume_name = file.name
        session.save()
        file_url = session.resume.url
    else:
        # Save to a temporary session or just return URL
        temp_session = InterviewSession.objects.create(
            user_id=user_id,
            username=username,
            status='cancelled',
            resume=file,
            resume_name=file.name
        )
        file_url = temp_session.resume.url
    
    # Update MongoDB user record
    update_user_resume(username, file_url)
    
    return JsonResponse({
        'message': 'Resume uploaded successfully',
        'filename': file.name,
        'url': file_url,
        'size': file.size,
        'type': file.content_type
    })

def get_resume(request):
    """Get resume info for the current user"""
    user_id = request.session.get('user_id')
    username = request.session.get('username')
    if not user_id or not username:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    # Check Django sessions
    sessions = InterviewSession.objects.filter(
        user_id=user_id, 
        resume__isnull=False
    ).exclude(resume='').order_by('-start_time')
    
    if sessions.exists():
        latest = sessions.first()
        return JsonResponse({
            'has_resume': True,
            'filename': latest.resume_name,
            'url': latest.resume.url,
            'uploaded_at': latest.start_time.isoformat(),
            'interview_id': latest.id
        })
    
    # Check MongoDB
    mongo_resume = get_user_resume(username)
    if mongo_resume:
        return JsonResponse({
            'has_resume': True,
            'url': mongo_resume,
            'source': 'mongodb'
        })
    
    return JsonResponse({'has_resume': False})
