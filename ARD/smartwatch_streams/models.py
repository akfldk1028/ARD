from django.db import models


class SmartwatchSession(models.Model):
    """Smartwatch streaming session"""
    session_id = models.CharField(max_length=100, unique=True)
    session_uid = models.UUIDField(unique=True)
    device_name = models.CharField(max_length=100, default='default-smartwatch')
    device_model = models.CharField(max_length=100, blank=True)
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
        return f"Smartwatch Session {self.session_id}"


class SensorData(models.Model):
    """Base sensor data from smartwatch"""
    session = models.ForeignKey(SmartwatchSession, on_delete=models.CASCADE, related_name='sensor_data')
    
    SENSOR_TYPES = [
        ('heart_rate', 'Heart Rate'),
        ('accelerometer', 'Accelerometer'),
        ('gyroscope', 'Gyroscope'),
        ('gps', 'GPS'),
        ('step_counter', 'Step Counter'),
        ('sleep', 'Sleep Tracking'),
        ('activity', 'Activity Recognition'),
    ]
    sensor_type = models.CharField(max_length=20, choices=SENSOR_TYPES)
    
    timestamp = models.DateTimeField()
    
    # Sensor values (flexible JSON structure)
    values = models.JSONField(default=dict)  # {x: 1.0, y: 2.0, z: 3.0} or {bpm: 75} etc.
    accuracy = models.FloatField(default=1.0)  # Sensor accuracy/confidence
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Kafka tracking
    kafka_offset = models.BigIntegerField(null=True, blank=True)
    kafka_partition = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['session', 'sensor_type', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.sensor_type} data at {self.timestamp}"


class ActivityData(models.Model):
    """Activity recognition and fitness data"""
    session = models.ForeignKey(SmartwatchSession, on_delete=models.CASCADE, related_name='activities')
    
    ACTIVITY_TYPES = [
        ('walking', 'Walking'),
        ('running', 'Running'),
        ('cycling', 'Cycling'),
        ('sitting', 'Sitting'),
        ('standing', 'Standing'),
        ('sleeping', 'Sleeping'),
        ('workout', 'Workout'),
        ('unknown', 'Unknown'),
    ]
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # seconds
    
    # Activity metrics
    steps = models.IntegerField(null=True, blank=True)
    calories = models.FloatField(null=True, blank=True)
    distance = models.FloatField(null=True, blank=True)  # meters
    avg_heart_rate = models.IntegerField(null=True, blank=True)
    
    confidence = models.FloatField(default=0.0)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.activity_type} from {self.start_time}"


class HealthMetrics(models.Model):
    """Health and wellness metrics"""
    session = models.ForeignKey(SmartwatchSession, on_delete=models.CASCADE, related_name='health_metrics')
    
    timestamp = models.DateTimeField()
    
    # Vital signs
    heart_rate = models.IntegerField(null=True, blank=True)
    blood_oxygen = models.FloatField(null=True, blank=True)  # SpO2 percentage
    stress_level = models.FloatField(null=True, blank=True)  # 0-100
    
    # Sleep data
    sleep_stage = models.CharField(max_length=20, null=True, blank=True)  # awake, light, deep, rem
    sleep_quality = models.FloatField(null=True, blank=True)  # 0-100
    
    # Additional metrics
    body_temperature = models.FloatField(null=True, blank=True)
    skin_conductance = models.FloatField(null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Health metrics at {self.timestamp}"