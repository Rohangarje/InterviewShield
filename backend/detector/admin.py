from django.contrib import admin
from .models import DetectionLog

@admin.register(DetectionLog)
class DetectionLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'status', 'face_count', 'phone_detected', 'risk_score']
    list_filter = ['status', 'phone_detected', 'risk_score', 'timestamp']
    search_fields = ['status', 'risk_score']
    date_hierarchy = 'timestamp'
