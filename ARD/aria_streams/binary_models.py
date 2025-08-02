"""
Binary streaming models for efficient metadata/binary data separation
Optimized for Project Aria VRS data with ID linking system
"""

from django.db import models
from django.utils import timezone
import uuid

class BinaryFrameRegistry(models.Model):
    """
    Registry for linking metadata and binary data using unique frame IDs
    Central coordination point for binary streaming architecture
    """
    
    frame_id = models.CharField(max_length=200, unique=True, db_index=True)
    session_id = models.CharField(max_length=100, db_index=True)
    stream_id = models.CharField(max_length=20)  # e.g., "214-1" for RGB
    frame_index = models.IntegerField()
    
    # Kafka topic information
    metadata_topic = models.CharField(max_length=100, default='vrs-metadata-stream')
    binary_topic = models.CharField(max_length=100, default='vrs-binary-stream')
    registry_topic = models.CharField(max_length=100, default='vrs-frame-registry')
    
    # Kafka offsets for tracking
    metadata_offset = models.BigIntegerField(null=True, blank=True)
    binary_offset = models.BigIntegerField(null=True, blank=True)
    registry_offset = models.BigIntegerField(null=True, blank=True)
    
    # Processing status
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),           # Waiting for metadata/binary
        ('LINKED', 'Linked'),             # Both metadata and binary available
        ('PROCESSED', 'Processed'),       # Successfully processed
        ('FAILED', 'Failed'),             # Processing failed
        ('EXPIRED', 'Expired'),           # Cache expired
    ], default='PENDING')
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    linked_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Data info
    size_bytes = models.BigIntegerField(null=True, blank=True)
    compression_format = models.CharField(max_length=20, null=True, blank=True)
    compression_ratio = models.FloatField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'binary_frame_registry'
        indexes = [
            models.Index(fields=['session_id', 'stream_id', 'frame_index']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['frame_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Frame {self.frame_id} ({self.status})"

class BinaryFrameMetadata(models.Model):
    """
    Metadata for binary frames (stored separately from binary data)
    Contains all frame information except the actual image bytes
    """
    
    # Link to registry
    registry = models.OneToOneField(BinaryFrameRegistry, on_delete=models.CASCADE, 
                                  related_name='metadata')
    
    # Frame identification  
    frame_id = models.CharField(max_length=200, db_index=True)
    session_id = models.CharField(max_length=100)
    stream_id = models.CharField(max_length=20)
    frame_index = models.IntegerField()
    
    # Timestamps
    timestamp = models.DateTimeField(default=timezone.now)
    capture_timestamp_ns = models.BigIntegerField()
    device_timestamp_ns = models.BigIntegerField()
    
    # Image properties
    image_width = models.IntegerField()
    image_height = models.IntegerField()
    channels = models.IntegerField(default=3)
    
    # Compression information (JSON-like fields)
    compression_format = models.CharField(max_length=20)  # jpeg, png, webp, raw
    compression_quality = models.IntegerField(null=True, blank=True)
    original_size_bytes = models.BigIntegerField()
    compressed_size_bytes = models.BigIntegerField()
    compression_ratio = models.FloatField()
    
    # Data type classification
    data_type = models.CharField(max_length=50, default='vrs_frame_binary')
    
    # Processing flags
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'binary_frame_metadata'
        indexes = [
            models.Index(fields=['session_id', 'stream_id', 'frame_index']),
            models.Index(fields=['frame_id']),
            models.Index(fields=['capture_timestamp_ns']),
            models.Index(fields=['compression_format']),
        ]
        ordering = ['-capture_timestamp_ns']
    
    def __str__(self):
        return f"Metadata {self.frame_id} ({self.image_width}x{self.image_height})"

class BinaryFrameReference(models.Model):
    """
    Reference to binary data stored in Kafka/external storage
    Contains access information but not the actual binary data
    """
    
    # Link to registry
    registry = models.OneToOneField(BinaryFrameRegistry, on_delete=models.CASCADE,
                                  related_name='binary_ref')
    
    # Frame identification
    frame_id = models.CharField(max_length=200, db_index=True)
    
    # Storage location
    kafka_topic = models.CharField(max_length=100)
    kafka_partition = models.IntegerField(null=True, blank=True)
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    kafka_timestamp = models.BigIntegerField(null=True, blank=True)
    
    # Alternative storage (for future S3/file system support)
    storage_type = models.CharField(max_length=20, choices=[
        ('KAFKA', 'Kafka Topic'),
        ('S3', 'S3 Bucket'),
        ('FILE', 'File System'),
        ('CACHE', 'Redis Cache'),
    ], default='KAFKA')
    
    storage_path = models.TextField(null=True, blank=True)  # S3 key, file path, etc.
    
    # Data properties
    size_bytes = models.BigIntegerField()
    content_type = models.CharField(max_length=50, default='application/octet-stream')
    checksum = models.CharField(max_length=64, null=True, blank=True)  # SHA-256
    
    # Access information
    is_available = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    access_count = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'binary_frame_reference'
        indexes = [
            models.Index(fields=['frame_id']),
            models.Index(fields=['kafka_topic', 'kafka_offset']),
            models.Index(fields=['storage_type', 'is_available']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Binary ref {self.frame_id} ({self.storage_type})"

class SensorDataBinary(models.Model):
    """
    Binary sensor data (IMU, etc.) with optimized storage
    For high-frequency sensor data that may benefit from binary storage
    """
    
    sensor_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    session_id = models.CharField(max_length=100, db_index=True)
    sensor_type = models.CharField(max_length=50)  # imu_data, etc.
    
    # Timestamps
    timestamp = models.DateTimeField(default=timezone.now)
    device_timestamp_ns = models.BigIntegerField()
    
    # Binary data reference (for high-frequency data)
    binary_data_topic = models.CharField(max_length=100, null=True, blank=True)
    binary_data_offset = models.BigIntegerField(null=True, blank=True)
    
    # Metadata (JSON for flexibility)
    metadata = models.JSONField(default=dict)
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'sensor_data_binary'
        indexes = [
            models.Index(fields=['session_id', 'sensor_type', 'device_timestamp_ns']),
            models.Index(fields=['sensor_id']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-device_timestamp_ns']
    
    def __str__(self):
        return f"Sensor {self.sensor_type} - {self.session_id}"

class BinaryStreamingStats(models.Model):
    """
    Statistics and monitoring for binary streaming operations
    """
    
    session_id = models.CharField(max_length=100, db_index=True)
    stream_type = models.CharField(max_length=50)  # vrs_frames, sensors, etc.
    
    # Counters
    total_frames = models.IntegerField(default=0)
    processed_frames = models.IntegerField(default=0)
    failed_frames = models.IntegerField(default=0)
    
    # Size statistics
    total_bytes = models.BigIntegerField(default=0)
    compressed_bytes = models.BigIntegerField(default=0)
    average_compression_ratio = models.FloatField(default=0.0)
    
    # Performance metrics
    frames_per_second = models.FloatField(default=0.0)
    bytes_per_second = models.BigIntegerField(default=0)
    
    # Time tracking
    started_at = models.DateTimeField(default=timezone.now)
    last_frame_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ], default='ACTIVE')
    
    error_message = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'binary_streaming_stats'
        indexes = [
            models.Index(fields=['session_id', 'stream_type']),
            models.Index(fields=['status', 'started_at']),
        ]
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Stats {self.session_id} - {self.stream_type} ({self.status})"