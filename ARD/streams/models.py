from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone

class AriaSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    session_uid = models.UUIDField()
    device_serial = models.CharField(max_length=50)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'), 
        ('ERROR', 'Error')
    ], default='ACTIVE')
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'aria_sessions'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.device_serial}"

class VRSStream(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='vrs_streams')
    stream_id = models.CharField(max_length=20)  # e.g., "214-1" for RGB
    stream_name = models.CharField(max_length=50)  # e.g., "camera-rgb"
    timestamp = models.DateTimeField(default=timezone.now)
    device_timestamp_ns = models.BigIntegerField()
    frame_index = models.IntegerField()
    image_shape = models.JSONField()  # [height, width, channels]
    pixel_format = models.CharField(max_length=20)
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'vrs_streams'
        indexes = [
            models.Index(fields=['session', 'stream_name', 'device_timestamp_ns']),
            models.Index(fields=['timestamp'])
        ]
    
    def __str__(self):
        return f"{self.stream_name} - Frame {self.frame_index}"

class EyeGazeData(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='eye_gaze_data')
    timestamp = models.DateTimeField(default=timezone.now)
    device_timestamp_ns = models.BigIntegerField()
    gaze_type = models.CharField(max_length=20, choices=[
        ('general', 'General'),
        ('personalized', 'Personalized')
    ])
    gaze_vector_x = models.FloatField()
    gaze_vector_y = models.FloatField() 
    gaze_vector_z = models.FloatField()
    depth_m = models.FloatField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'eye_gaze_data'
        indexes = [
            models.Index(fields=['session', 'gaze_type', 'device_timestamp_ns']),
            models.Index(fields=['timestamp'])
        ]
    
    def __str__(self):
        return f"EyeGaze {self.gaze_type} - {self.session.session_id}"

class HandTrackingData(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='hand_tracking_data')
    timestamp = models.DateTimeField(default=timezone.now)
    device_timestamp_ns = models.BigIntegerField()
    left_hand_landmarks = models.JSONField(null=True, blank=True)  # 21 landmarks
    left_hand_wrist_normal = models.JSONField(null=True, blank=True)  # [x, y, z]
    left_hand_palm_normal = models.JSONField(null=True, blank=True)  # [x, y, z]
    right_hand_landmarks = models.JSONField(null=True, blank=True) # 21 landmarks
    right_hand_wrist_normal = models.JSONField(null=True, blank=True)  # [x, y, z]
    right_hand_palm_normal = models.JSONField(null=True, blank=True)  # [x, y, z]
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'hand_tracking_data'
        indexes = [
            models.Index(fields=['session', 'device_timestamp_ns']),
            models.Index(fields=['timestamp'])
        ]
    
    def __str__(self):
        return f"HandTracking - {self.session.session_id}"

class SLAMTrajectoryData(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='slam_trajectory_data')
    timestamp = models.DateTimeField(default=timezone.now)
    device_timestamp_ns = models.BigIntegerField()
    transform_matrix = models.JSONField()  # 4x4 SE3 transform matrix
    position_x = models.FloatField()  # Extracted from transform for indexing
    position_y = models.FloatField()
    position_z = models.FloatField()
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'slam_trajectory_data'
        indexes = [
            models.Index(fields=['session', 'device_timestamp_ns']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['position_x', 'position_y', 'position_z'])
        ]
    
    def __str__(self):
        return f"SLAM Pose - {self.session.session_id}"

class SLAMPointCloud(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='slam_point_clouds')
    timestamp = models.DateTimeField(default=timezone.now)
    points = models.JSONField()  # Array of 3D points
    point_count = models.IntegerField()
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'slam_point_clouds'
        indexes = [
            models.Index(fields=['session', 'timestamp']),
            models.Index(fields=['point_count'])
        ]
    
    def __str__(self):
        return f"SLAM Points ({self.point_count}) - {self.session.session_id}"

class AnalyticsResult(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE, related_name='analytics_results')
    timestamp = models.DateTimeField(default=timezone.now)
    analysis_type = models.CharField(max_length=50)  # e.g., "gaze_heatmap", "hand_gesture"
    result_data = models.JSONField()
    confidence_score = models.FloatField(null=True, blank=True)
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'analytics_results'
        indexes = [
            models.Index(fields=['session', 'analysis_type', 'timestamp']),
            models.Index(fields=['confidence_score'])
        ]
    
    def __str__(self):
        return f"Analytics {self.analysis_type} - {self.session.session_id}"

class KafkaConsumerStatus(models.Model):
    consumer_group = models.CharField(max_length=100)
    topic = models.CharField(max_length=100)
    partition = models.IntegerField()
    last_offset = models.BigIntegerField()
    last_processed_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('ERROR', 'Error')
    ], default='ACTIVE')
    error_message = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'kafka_consumer_status'
        unique_together = ['consumer_group', 'topic', 'partition']
        indexes = [
            models.Index(fields=['status', 'last_processed_at'])
        ]
    
    def __str__(self):
        return f"{self.consumer_group} - {self.topic}:{self.partition}"
