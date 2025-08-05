from django.db import models
from django.utils import timezone
import uuid

class AriaStreamingSession(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True)
    vrs_file_path = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=[
        ('READY', 'Ready'),
        ('STREAMING', 'Streaming'),
        ('COMPLETED', 'Completed')
    ], default='READY')
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Session {self.session_id}"

class UnifiedSensorData(models.Model):
    session = models.ForeignKey(AriaStreamingSession, on_delete=models.CASCADE)
    device_timestamp_ns = models.BigIntegerField()
    stream_id = models.CharField(max_length=20)
    stream_label = models.CharField(max_length=50)
    sensor_type = models.CharField(max_length=20)
    data_payload = models.JSONField()
    
    class Meta:
        ordering = ['device_timestamp_ns']
