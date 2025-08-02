from django.db import models
from django.contrib.auth.models import User


class WebcamSession(models.Model):
    """Webcam streaming session"""
    session_id = models.CharField(max_length=100, unique=True)
    session_uid = models.UUIDField(unique=True)
    device_name = models.CharField(max_length=100, default='default-webcam')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    metadata = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"Webcam Session {self.session_id}"


class WebcamFrame(models.Model):
    """Webcam video frame data"""
    session = models.ForeignKey(WebcamSession, on_delete=models.CASCADE, related_name='frames')
    frame_id = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    
    # Frame metadata
    width = models.IntegerField()
    height = models.IntegerField()
    fps = models.FloatField(default=30.0)
    format = models.CharField(max_length=10, default='RGB')
    
    # File paths or base64 data
    frame_path = models.CharField(max_length=500, null=True, blank=True)
    thumbnail_path = models.CharField(max_length=500, null=True, blank=True)
    
    # Kafka tracking
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    kafka_partition = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Frame {self.frame_id} at {self.timestamp}"


class WebcamAnalysis(models.Model):
    """Webcam analysis results (motion detection, face detection, etc.)"""
    session = models.ForeignKey(WebcamSession, on_delete=models.CASCADE, related_name='analyses')
    frame = models.ForeignKey(WebcamFrame, on_delete=models.CASCADE, related_name='analyses', null=True, blank=True)
    
    ANALYSIS_TYPES = [
        ('motion', 'Motion Detection'),
        ('face', 'Face Detection'),
        ('object', 'Object Detection'),
        ('activity', 'Activity Recognition'),
    ]
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES)
    
    timestamp = models.DateTimeField()
    confidence = models.FloatField(default=0.0)
    
    # Analysis results
    results = models.JSONField(default=dict)  # Detection boxes, features, etc.
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.analysis_type} analysis at {self.timestamp}"