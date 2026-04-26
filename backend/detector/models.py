from django.db import models
from django.utils import timezone
import os

class InterviewSession(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user_id = models.CharField(max_length=100, db_index=True)
    username = models.CharField(max_length=100, default='anonymous')
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    resume = models.FileField(upload_to='resumes/%Y/%m/%d/', blank=True, null=True)
    resume_name = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        ordering = ['-start_time']
    
    def __str__(self):
        return f"Interview {self.id} - {self.username} ({self.status})"
    
    @property
    def duration_seconds(self):
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (timezone.now() - self.start_time).total_seconds()

class InterviewReport(models.Model):
    session = models.OneToOneField(InterviewSession, on_delete=models.CASCADE, related_name='report')
    generated_at = models.DateTimeField(default=timezone.now)
    total_detections = models.IntegerField(default=0)
    phone_detections = models.IntegerField(default=0)
    no_face_detections = models.IntegerField(default=0)
    multiple_face_detections = models.IntegerField(default=0)
    high_risk_count = models.IntegerField(default=0)
    medium_risk_count = models.IntegerField(default=0)
    low_risk_count = models.IntegerField(default=0)
    avg_phone_confidence = models.FloatField(default=0.0)
    cheating_percentage = models.FloatField(default=0.0)
    overall_risk = models.CharField(max_length=20, default='low')
    report_data = models.JSONField(default=dict, blank=True)
    report_html = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"Report for Interview {self.session.id}"

class DetectionLog(models.Model):
    STATUS_CHOICES = [
        ('normal_phone', 'Normal - Single Face w/ Phone'),
        ('normal_no_phone', 'Normal - Single Face'),
        ('no_face_phone', 'No Face - Phone Detected'),
        ('no_face_no_phone', 'No Face Detected'),
        ('multiple_faces_phone', 'Multiple Faces w/ Phone'),
        ('multiple_faces_no_phone', 'Multiple Faces'),
    ]
    
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, null=True, blank=True, related_name='detections')
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    face_count = models.IntegerField(default=0)
    image_base64 = models.TextField(blank=True, null=True)
    phone_detected = models.BooleanField(default=False)
    phone_confidence = models.FloatField(default=0.0)
    risk_score = models.CharField(max_length=20, default='low')
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.status} - {self.timestamp}"
