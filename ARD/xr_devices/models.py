"""
다중 XR 기기 지원을 위한 확장 가능한 데이터 모델

미래 기기들:
- Meta Aria (현재)
- Google AR Glass 
- Apple Vision Pro
- Microsoft HoloLens
- Magic Leap
- Nreal/Xreal
- Vuzix
"""

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json
from enum import Enum


class XRDeviceType(models.TextChoices):
    """XR 기기 타입 정의"""
    META_ARIA = 'meta_aria', 'Meta Aria'
    GOOGLE_GLASS = 'google_glass', 'Google AR Glass'
    APPLE_VISION = 'apple_vision', 'Apple Vision Pro'
    HOLOLENS = 'hololens', 'Microsoft HoloLens'
    MAGIC_LEAP = 'magic_leap', 'Magic Leap'
    NREAL = 'nreal', 'Nreal/Xreal'
    VUZIX = 'vuzix', 'Vuzix Smart Glasses'
    CUSTOM = 'custom', 'Custom Device'


class DataFormat(models.TextChoices):
    """데이터 포맷 타입"""
    VRS = 'vrs', 'VRS (Meta)'
    GLTF = 'gltf', 'GLTF/GLB'
    JSON_STREAM = 'json_stream', 'JSON Stream'
    PROTOBUF = 'protobuf', 'Protocol Buffers'
    ROS_BAG = 'ros_bag', 'ROS Bag'
    CUSTOM_BINARY = 'custom_binary', 'Custom Binary'
    REALTIME_API = 'realtime_api', 'Real-time API'


class StreamingProtocol(models.TextChoices):
    """스트리밍 프로토콜"""
    KAFKA = 'kafka', 'Apache Kafka'
    MQTT = 'mqtt', 'MQTT'
    WEBSOCKET = 'websocket', 'WebSocket'
    GRPC = 'grpc', 'gRPC'
    REST_API = 'rest_api', 'REST API'
    CUSTOM = 'custom', 'Custom Protocol'


class XRDevice(models.Model):
    """XR 기기 정의"""
    name = models.CharField(max_length=100, unique=True)
    device_type = models.CharField(max_length=20, choices=XRDeviceType.choices)
    manufacturer = models.CharField(max_length=50)
    model_version = models.CharField(max_length=50)
    
    # 지원되는 데이터 포맷들
    supported_formats = models.JSONField(default=list)  # [VRS, JSON_STREAM, ...]
    preferred_protocol = models.CharField(max_length=20, choices=StreamingProtocol.choices)
    
    # 기기별 설정
    device_config = models.JSONField(default=dict)
    
    # 메타데이터
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'xr_devices'
        verbose_name = 'XR Device'
        verbose_name_plural = 'XR Devices'
    
    def __str__(self):
        return f"{self.name} ({self.device_type})"


class SensorType(models.TextChoices):
    """센서 타입 정의"""
    # 공통 센서들
    CAMERA_RGB = 'camera_rgb', 'RGB Camera'
    CAMERA_DEPTH = 'camera_depth', 'Depth Camera'
    CAMERA_IR = 'camera_ir', 'IR Camera'
    CAMERA_FISHEYE = 'camera_fisheye', 'Fisheye Camera'
    
    IMU = 'imu', 'IMU (Accelerometer + Gyroscope)'
    MAGNETOMETER = 'magnetometer', 'Magnetometer'
    BAROMETER = 'barometer', 'Barometer'
    GPS = 'gps', 'GPS'
    
    # 특수 센서들
    EYE_TRACKING = 'eye_tracking', 'Eye Tracking'
    HAND_TRACKING = 'hand_tracking', 'Hand Tracking'
    VOICE_RECOGNITION = 'voice_recognition', 'Voice Recognition'
    GESTURE_RECOGNITION = 'gesture_recognition', 'Gesture Recognition'
    
    # SLAM 관련
    SLAM = 'slam', 'SLAM'
    LIDAR = 'lidar', 'LiDAR'
    TOF = 'tof', 'Time of Flight'
    
    # 바이오메트릭
    HEART_RATE = 'heart_rate', 'Heart Rate'
    SKIN_CONDUCTANCE = 'skin_conductance', 'Skin Conductance'
    BODY_TEMPERATURE = 'body_temperature', 'Body Temperature'
    
    # 환경 센서
    AMBIENT_LIGHT = 'ambient_light', 'Ambient Light'
    MICROPHONE = 'microphone', 'Microphone'
    SPEAKER = 'speaker', 'Speaker'


class DeviceSensorCapability(models.Model):
    """기기별 센서 능력"""
    device = models.ForeignKey(XRDevice, on_delete=models.CASCADE, related_name='sensor_capabilities')
    sensor_type = models.CharField(max_length=30, choices=SensorType.choices)
    
    # 센서별 스펙
    resolution = models.CharField(max_length=50, blank=True)  # "1920x1080", "640x480"
    frequency_hz = models.FloatField(null=True, blank=True)  # 샘플링 주파수
    precision = models.CharField(max_length=50, blank=True)   # "16-bit", "32-bit float"
    
    # 센서별 설정
    sensor_config = models.JSONField(default=dict)
    
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'device_sensor_capabilities'
        unique_together = ('device', 'sensor_type')
        verbose_name = 'Device Sensor Capability'
        verbose_name_plural = 'Device Sensor Capabilities'
    
    def __str__(self):
        return f"{self.device.name} - {self.sensor_type}"


class DataParser(models.Model):
    """기기별 데이터 파서 정의"""
    device_type = models.CharField(max_length=20, choices=XRDeviceType.choices)
    data_format = models.CharField(max_length=20, choices=DataFormat.choices)
    
    # 파서 구현 정보
    parser_class = models.CharField(max_length=200)  # 'xr_devices.parsers.meta.AriaVRSParser'
    parser_version = models.CharField(max_length=20)
    
    # 파서별 설정
    parser_config = models.JSONField(default=dict)
    
    # 지원되는 센서들
    supported_sensors = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'data_parsers'
        unique_together = ('device_type', 'data_format')
        verbose_name = 'Data Parser'
        verbose_name_plural = 'Data Parsers'
    
    def __str__(self):
        return f"{self.device_type} - {self.data_format} Parser"


class StreamingSession(models.Model):
    """통합 스트리밍 세션 관리"""
    session_id = models.CharField(max_length=50, unique=True)
    device = models.ForeignKey(XRDevice, on_delete=models.CASCADE)
    
    # 세션 정보
    user_id = models.CharField(max_length=50, null=True, blank=True)
    session_name = models.CharField(max_length=100)
    
    # 스트리밍 설정
    streaming_protocol = models.CharField(max_length=20, choices=StreamingProtocol.choices)
    data_format = models.CharField(max_length=20, choices=DataFormat.choices)
    
    # 활성 센서들
    active_sensors = models.JSONField(default=list)
    
    # 세션 상태
    status = models.CharField(max_length=20, choices=[
        ('preparing', 'Preparing'),
        ('streaming', 'Streaming'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ], default='preparing')
    
    # 통계
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    total_frames_processed = models.BigIntegerField(default=0)
    total_data_size_mb = models.FloatField(default=0.0)
    
    # 메타데이터
    session_metadata = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'streaming_sessions'
        verbose_name = 'Streaming Session'
        verbose_name_plural = 'Streaming Sessions'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.device.name}"


class StreamingData(models.Model):
    """통합 스트리밍 데이터 저장"""
    session = models.ForeignKey(StreamingSession, on_delete=models.CASCADE, related_name='streaming_data')
    
    # 데이터 식별
    sensor_type = models.CharField(max_length=30, choices=SensorType.choices)
    frame_number = models.BigIntegerField()
    timestamp_ns = models.BigIntegerField()  # 나노초 단위
    
    # 범용 데이터 저장
    raw_data = models.BinaryField(null=True, blank=True)        # 바이너리 데이터 (이미지, 센서)
    structured_data = models.JSONField(null=True, blank=True)   # 구조화된 데이터 (JSON)
    
    # 메타데이터
    data_format = models.CharField(max_length=20, choices=DataFormat.choices)
    data_size_bytes = models.BigIntegerField(default=0)
    
    # 인덱싱을 위한 추가 필드들
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Generic Foreign Key를 통한 기기별 확장 가능
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    device_specific_data = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        db_table = 'streaming_data'
        verbose_name = 'Streaming Data'
        verbose_name_plural = 'Streaming Data'
        indexes = [
            models.Index(fields=['session', 'sensor_type', 'frame_number']),
            models.Index(fields=['timestamp_ns']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.session.session_id} - {self.sensor_type} #{self.frame_number}"


# Meta Aria 전용 확장 모델 (예시)
class AriaSpecificData(models.Model):
    """Meta Aria 기기 전용 데이터"""
    # VRS 파일 관련
    vrs_file_path = models.CharField(max_length=500, null=True, blank=True)
    stream_id = models.CharField(max_length=20)  # "214-1", "1201-1" 등
    
    # Aria 전용 메타데이터
    camera_calibration = models.JSONField(null=True, blank=True)
    transform_matrix = models.JSONField(null=True, blank=True)  # Sophus SE3
    
    # MPS (Machine Perception Services) 관련
    mps_data_path = models.CharField(max_length=500, null=True, blank=True)
    eye_gaze_confidence = models.FloatField(null=True, blank=True)
    hand_tracking_presence = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'aria_specific_data'
        verbose_name = 'Aria Specific Data'


# 미래 기기들을 위한 확장 모델 예시
class GoogleGlassSpecificData(models.Model):
    """Google AR Glass 전용 데이터 (미래 기기)"""
    # Google Glass 고유 필드들
    glass_model = models.CharField(max_length=50)
    android_version = models.CharField(max_length=20)
    
    # Google 생태계 관련
    assistant_interaction = models.JSONField(null=True, blank=True)
    maps_integration = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'google_glass_specific_data'
        verbose_name = 'Google Glass Specific Data'


class AppleVisionSpecificData(models.Model):
    """Apple Vision Pro 전용 데이터 (미래 기기)"""
    # Apple Vision Pro 고유 필드들
    vision_os_version = models.CharField(max_length=20)
    spatial_computing_data = models.JSONField(null=True, blank=True)
    
    # Apple 생태계 관련
    siri_integration = models.JSONField(null=True, blank=True)
    continuity_data = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'apple_vision_specific_data'
        verbose_name = 'Apple Vision Specific Data'