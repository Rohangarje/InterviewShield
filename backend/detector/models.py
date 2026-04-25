from django.db import models
from django.utils import timezone

class DetectionLog(models.Model):
    STATUS_CHOICES = [
        ('normal_phone', 'Normal - Single Face w/ Phone'),
        ('normal_no_phone', 'Normal - Single Face'),
        ('no_face_phone', 'No Face - Phone Detected'),
        ('no_face_no_phone', 'No Face Detected'),
        ('multiple_faces_phone', 'Multiple Faces w/ Phone'),
        ('multiple_faces_no_phone', 'Multiple Faces'),
    ]
    
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
