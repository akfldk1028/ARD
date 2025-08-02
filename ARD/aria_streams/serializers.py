from rest_framework import serializers
from django.utils import timezone
from .models import (
    AriaSession, VRSStream, EyeGazeData, 
    HandTrackingData, SLAMTrajectoryData,
    SLAMPointCloud, AnalyticsResult, KafkaConsumerStatus,
    IMUData
)
from .binary_models import (
    BinaryFrameRegistry, BinaryFrameMetadata, BinaryFrameReference,
    SensorDataBinary, BinaryStreamingStats
)


class AriaSessionSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()
    stream_counts = serializers.SerializerMethodField()
    
    class Meta:
        model = AriaSession
        fields = [
            'id', 'session_id', 'session_uid', 'device_serial',
            'started_at', 'ended_at', 'status', 'metadata',
            'duration', 'stream_counts'
        ]
        read_only_fields = ['session_uid', 'started_at']
    
    def get_duration(self, obj):
        """세션 지속 시간 계산"""
        end_time = obj.ended_at or timezone.now()
        duration = end_time - obj.started_at
        return duration.total_seconds()
    
    def get_stream_counts(self, obj):
        """각 스트림별 데이터 수 반환"""
        return {
            'vrs_frames': obj.vrs_streams.count(),
            'imu_data': obj.imu_data.count(),
            'eye_gaze': obj.eye_gaze_data.count(),
            'hand_tracking': obj.hand_tracking_data.count(),
            'slam_trajectory': obj.slam_trajectory_data.count(),
            'slam_points': obj.slam_point_clouds.count(),
            'analytics': obj.analytics_results.count()
        }


class VRSStreamSerializer(serializers.ModelSerializer):
    session_info = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    kafka_frame_id = serializers.SerializerMethodField()
    
    class Meta:
        model = VRSStream
        fields = [
            'id', 'session', 'stream_id', 'stream_name', 'timestamp',
            'device_timestamp_ns', 'frame_index', 'image_shape', 
            'pixel_format', 'kafka_offset', 'session_info',
            # 실제 이미지 데이터 필드들 추가
            'image_data', 'image_width', 'image_height',
            'original_size_bytes', 'compressed_size_bytes', 'compression_quality',
            # 바이너리 이미지 연결 필드들
            'image_url', 'kafka_frame_id'
        ]
        read_only_fields = ['timestamp']
    
    def get_session_info(self, obj):
        """세션 기본 정보"""
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial
        }
    
    def get_kafka_frame_id(self, obj):
        """실제 Kafka Frame ID 찾기 (실시간 매칭)"""
        from kafka import KafkaConsumer
        import json
        import os
        
        session_id = obj.session.session_id
        capture_timestamp = obj.device_timestamp_ns
        frame_index = obj.frame_index
        
        try:
            # Kafka에서 실제 Frame ID 찾기
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
            consumer = KafkaConsumer(
                'vrs-metadata-stream',
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=2000,
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            # 세션과 타임스탬프로 매칭되는 실제 Frame ID 찾기
            for message in consumer:
                metadata = message.value
                if (metadata.get('session_id') == session_id and 
                    metadata.get('data_type') == 'vrs_frame_binary'):
                    
                    # 타임스탬프 또는 프레임 인덱스로 매칭
                    if (metadata.get('capture_timestamp_ns') == capture_timestamp or
                        metadata.get('frame_index') == frame_index):
                        consumer.close()
                        return metadata.get('frame_id')
            
            consumer.close()
            
        except Exception:
            # 오류 시 fallback
            pass
        
        # Fallback: 예상 Frame ID 생성
        return f"{session_id}_{obj.stream_id}_{frame_index}_{capture_timestamp}"
    
    def get_image_url(self, obj):
        """바이너리 이미지 URL 생성"""
        frame_id = self.get_kafka_frame_id(obj)
        return f"/api/v1/aria/image-by-id/{frame_id}/"


class IMUDataSerializer(serializers.ModelSerializer):
    session_info = serializers.SerializerMethodField()
    acceleration_magnitude = serializers.SerializerMethodField()
    angular_velocity_magnitude = serializers.SerializerMethodField()
    temperature_c = serializers.SerializerMethodField()
    
    class Meta:
        model = IMUData
        fields = [
            'id', 'session', 'timestamp', 'device_timestamp_ns', 
            'imu_stream_id', 'imu_type', 'accel_x', 'accel_y', 'accel_z',
            'gyro_x', 'gyro_y', 'gyro_z', 'temperature_c', 'kafka_offset',
            'session_info', 'acceleration_magnitude', 'angular_velocity_magnitude'
        ]
        read_only_fields = ['timestamp']
    
    def get_session_info(self, obj):
        """세션 기본 정보"""
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial
        }
    
    def get_acceleration_magnitude(self, obj):
        """가속도 벡터 크기 계산 (m/s²)"""
        import math
        return math.sqrt(obj.accel_x**2 + obj.accel_y**2 + obj.accel_z**2)
    
    def get_angular_velocity_magnitude(self, obj):
        """각속도 벡터 크기 계산 (rad/s)"""
        import math
        return math.sqrt(obj.gyro_x**2 + obj.gyro_y**2 + obj.gyro_z**2)
    
    def get_temperature_c(self, obj):
        """온도 값 (NaN 처리)"""
        import math
        if obj.temperature_c is None or math.isnan(obj.temperature_c):
            return None
        return obj.temperature_c


class EyeGazeDataSerializer(serializers.ModelSerializer):
    session_info = serializers.SerializerMethodField()
    gaze_direction = serializers.SerializerMethodField()
    
    class Meta:
        model = EyeGazeData
        fields = [
            'id', 'session', 'timestamp', 'device_timestamp_ns',
            'gaze_type', 'yaw', 'pitch', 'depth_m', 'confidence',
            'kafka_offset', 'session_info', 'gaze_direction'
        ]
        read_only_fields = ['timestamp']
    
    def get_session_info(self, obj):
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial
        }
    
    def get_gaze_direction(self, obj):
        """Yaw/Pitch를 방향 벡터로 변환"""
        import math
        yaw_rad = math.radians(obj.yaw)
        pitch_rad = math.radians(obj.pitch)
        
        # 구면 좌표계를 직교 좌표계로 변환
        x = math.cos(pitch_rad) * math.sin(yaw_rad)
        y = math.sin(pitch_rad)
        z = math.cos(pitch_rad) * math.cos(yaw_rad)
        
        return {'x': x, 'y': y, 'z': z}


class HandTrackingDataSerializer(serializers.ModelSerializer):
    session_info = serializers.SerializerMethodField()
    has_left_hand = serializers.SerializerMethodField()
    has_right_hand = serializers.SerializerMethodField()
    
    class Meta:
        model = HandTrackingData
        fields = [
            'id', 'session', 'timestamp', 'device_timestamp_ns',
            'left_hand_landmarks', 'left_hand_wrist_normal', 'left_hand_palm_normal',
            'right_hand_landmarks', 'right_hand_wrist_normal', 'right_hand_palm_normal',
            'kafka_offset', 'session_info', 'has_left_hand', 'has_right_hand'
        ]
        read_only_fields = ['timestamp']
    
    def get_session_info(self, obj):
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial
        }
    
    def get_has_left_hand(self, obj):
        return obj.left_hand_landmarks is not None
    
    def get_has_right_hand(self, obj):
        return obj.right_hand_landmarks is not None


class SLAMTrajectoryDataSerializer(serializers.ModelSerializer):
    session_info = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    
    class Meta:
        model = SLAMTrajectoryData
        fields = [
            'id', 'session', 'timestamp', 'device_timestamp_ns',
            'transform_matrix', 'position_x', 'position_y', 'position_z',
            'kafka_offset', 'session_info', 'position'
        ]
        read_only_fields = ['timestamp', 'position_x', 'position_y', 'position_z']
    
    def get_session_info(self, obj):
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial
        }
    
    def get_position(self, obj):
        return {
            'x': obj.position_x,
            'y': obj.position_y,
            'z': obj.position_z
        }


class SLAMPointCloudSerializer(serializers.ModelSerializer):
    session_info = serializers.SerializerMethodField()
    
    class Meta:
        model = SLAMPointCloud
        fields = [
            'id', 'session', 'timestamp', 'points', 'point_count',
            'kafka_offset', 'session_info'
        ]
        read_only_fields = ['timestamp', 'point_count']
    
    def get_session_info(self, obj):
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial
        }


class AnalyticsResultSerializer(serializers.ModelSerializer):
    session_info = serializers.SerializerMethodField()
    
    class Meta:
        model = AnalyticsResult
        fields = [
            'id', 'session', 'timestamp', 'analysis_type',
            'result_data', 'confidence_score', 'kafka_offset', 'session_info'
        ]
        read_only_fields = ['timestamp']
    
    def get_session_info(self, obj):
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial
        }


class KafkaConsumerStatusSerializer(serializers.ModelSerializer):
    last_processed_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = KafkaConsumerStatus
        fields = [
            'id', 'consumer_group', 'topic', 'partition',
            'last_offset', 'last_processed_at', 'status',
            'error_message', 'last_processed_ago'
        ]
        read_only_fields = ['last_processed_at']
    
    def get_last_processed_ago(self, obj):
        """마지막 처리 후 경과 시간"""
        if obj.last_processed_at:
            diff = timezone.now() - obj.last_processed_at
            return diff.total_seconds()
        return None


# 스트리밍 제어를 위한 시리얼라이저
class StreamingControlSerializer(serializers.Serializer):
    duration = serializers.IntegerField(min_value=1, max_value=3600, default=60)
    stream_type = serializers.ChoiceField(
        choices=['all', 'vrs', 'mps'], 
        default='all'
    )
    
    def validate_duration(self, value):
        """지속 시간 유효성 검사"""
        if value > 600:  # 10분 제한
            raise serializers.ValidationError("최대 스트리밍 시간은 600초입니다.")
        return value


class TestMessageSerializer(serializers.Serializer):
    topic = serializers.CharField(max_length=100, default='test-topic')
    message = serializers.CharField(max_length=1000)
    
    def validate_topic(self, value):
        """토픽명 유효성 검사"""
        if not value.replace('-', '').replace('_', '').isalnum():
            raise serializers.ValidationError("토픽명은 영문, 숫자, 하이픈, 언더스코어만 사용 가능합니다.")
        return value


class EyeGazeStreamingSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=['general', 'personalized'], default='general')
    duration = serializers.IntegerField(min_value=1, max_value=300, default=30)


class HandTrackingStreamingSerializer(serializers.Serializer):
    duration = serializers.IntegerField(min_value=1, max_value=300, default=30)


# Binary streaming serializers

class BinaryFrameRegistrySerializer(serializers.ModelSerializer):
    processing_time = serializers.SerializerMethodField()
    size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = BinaryFrameRegistry
        fields = [
            'id', 'frame_id', 'session_id', 'stream_id', 'frame_index',
            'metadata_topic', 'binary_topic', 'registry_topic',
            'metadata_offset', 'binary_offset', 'registry_offset',
            'status', 'created_at', 'linked_at', 'processed_at',
            'size_bytes', 'compression_format', 'compression_ratio',
            'error_message', 'retry_count', 'processing_time', 'size_mb'
        ]
        read_only_fields = ['created_at', 'linked_at', 'processed_at']
    
    def get_processing_time(self, obj):
        """Processing time in seconds"""
        if obj.processed_at and obj.created_at:
            return (obj.processed_at - obj.created_at).total_seconds()
        return None
    
    def get_size_mb(self, obj):
        """Size in megabytes"""
        if obj.size_bytes:
            return round(obj.size_bytes / (1024 * 1024), 2)
        return None


class BinaryFrameMetadataSerializer(serializers.ModelSerializer):
    registry_info = serializers.SerializerMethodField()
    resolution = serializers.SerializerMethodField()
    compression_info = serializers.SerializerMethodField()
    
    class Meta:
        model = BinaryFrameMetadata
        fields = [
            'id', 'frame_id', 'session_id', 'stream_id', 'frame_index',
            'timestamp', 'capture_timestamp_ns', 'device_timestamp_ns',
            'image_width', 'image_height', 'channels',
            'compression_format', 'compression_quality',
            'original_size_bytes', 'compressed_size_bytes', 'compression_ratio',
            'data_type', 'is_processed', 'processed_at',
            'registry_info', 'resolution', 'compression_info'
        ]
        read_only_fields = ['timestamp', 'processed_at']
    
    def get_registry_info(self, obj):
        """Registry status information"""
        if hasattr(obj, 'registry'):
            return {
                'status': obj.registry.status,
                'created_at': obj.registry.created_at,
                'retry_count': obj.registry.retry_count
            }
        return None
    
    def get_resolution(self, obj):
        """Image resolution info"""
        return f"{obj.image_width}x{obj.image_height}x{obj.channels}"
    
    def get_compression_info(self, obj):
        """Detailed compression information"""
        return {
            'format': obj.compression_format,
            'quality': obj.compression_quality,
            'ratio': obj.compression_ratio,
            'original_mb': round(obj.original_size_bytes / (1024 * 1024), 2),
            'compressed_mb': round(obj.compressed_size_bytes / (1024 * 1024), 2),
            'saved_mb': round((obj.original_size_bytes - obj.compressed_size_bytes) / (1024 * 1024), 2)
        }


class BinaryFrameReferenceSerializer(serializers.ModelSerializer):
    registry_info = serializers.SerializerMethodField()
    storage_info = serializers.SerializerMethodField()
    access_info = serializers.SerializerMethodField()
    
    class Meta:
        model = BinaryFrameReference
        fields = [
            'id', 'frame_id', 'kafka_topic', 'kafka_partition', 'kafka_offset', 'kafka_timestamp',
            'storage_type', 'storage_path', 'size_bytes', 'content_type', 'checksum',
            'is_available', 'expires_at', 'access_count', 'last_accessed', 'created_at',
            'registry_info', 'storage_info', 'access_info'
        ]
        read_only_fields = ['created_at', 'last_accessed']
    
    def get_registry_info(self, obj):
        """Registry status information"""
        if hasattr(obj, 'registry'):
            return {
                'status': obj.registry.status,
                'session_id': obj.registry.session_id,
                'stream_id': obj.registry.stream_id
            }
        return None
    
    def get_storage_info(self, obj):
        """Storage backend information"""
        return {
            'type': obj.storage_type,
            'location': f"{obj.kafka_topic}:{obj.kafka_partition}:{obj.kafka_offset}" if obj.storage_type == 'KAFKA' else obj.storage_path,
            'size_mb': round(obj.size_bytes / (1024 * 1024), 2) if obj.size_bytes else None,
            'content_type': obj.content_type
        }
    
    def get_access_info(self, obj):
        """Access statistics"""
        return {
            'access_count': obj.access_count,
            'last_accessed': obj.last_accessed,
            'is_available': obj.is_available,
            'expires_at': obj.expires_at
        }


class SensorDataBinarySerializer(serializers.ModelSerializer):
    metadata_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = SensorDataBinary
        fields = [
            'id', 'sensor_id', 'session_id', 'sensor_type',
            'timestamp', 'device_timestamp_ns',
            'binary_data_topic', 'binary_data_offset',
            'metadata', 'is_processed', 'processed_at',
            'metadata_summary'
        ]
        read_only_fields = ['timestamp', 'processed_at']
    
    def get_metadata_summary(self, obj):
        """Metadata summary for quick overview"""
        if obj.metadata:
            summary = {'keys': list(obj.metadata.keys())}
            if 'imu_name' in obj.metadata:
                summary['imu_name'] = obj.metadata['imu_name']
            if 'accel_x' in obj.metadata:
                summary['acceleration'] = {
                    'x': obj.metadata.get('accel_x'),
                    'y': obj.metadata.get('accel_y'),
                    'z': obj.metadata.get('accel_z')
                }
            return summary
        return None


class BinaryStreamingStatsSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()
    efficiency_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = BinaryStreamingStats
        fields = [
            'id', 'session_id', 'stream_type',
            'total_frames', 'processed_frames', 'failed_frames',
            'total_bytes', 'compressed_bytes', 'average_compression_ratio',
            'frames_per_second', 'bytes_per_second',
            'started_at', 'last_frame_at', 'completed_at',
            'status', 'error_message',
            'duration_seconds', 'efficiency_metrics'
        ]
        read_only_fields = ['started_at', 'last_frame_at', 'completed_at']
    
    def get_duration_seconds(self, obj):
        """Calculate streaming duration"""
        end_time = obj.completed_at or timezone.now()
        if obj.started_at:
            return (end_time - obj.started_at).total_seconds()
        return None
    
    def get_efficiency_metrics(self, obj):
        """Calculate efficiency metrics"""
        metrics = {}
        
        if obj.total_frames > 0:
            metrics['success_rate'] = (obj.processed_frames / obj.total_frames) * 100
            metrics['failure_rate'] = (obj.failed_frames / obj.total_frames) * 100
        
        if obj.total_bytes and obj.compressed_bytes:
            metrics['compression_efficiency'] = (1 - obj.compressed_bytes / obj.total_bytes) * 100
            metrics['total_mb'] = round(obj.total_bytes / (1024 * 1024), 2)
            metrics['compressed_mb'] = round(obj.compressed_bytes / (1024 * 1024), 2)
            metrics['saved_mb'] = round((obj.total_bytes - obj.compressed_bytes) / (1024 * 1024), 2)
        
        return metrics


# Binary streaming control serializers

class BinaryStreamingControlSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=100, required=False)
    duration_seconds = serializers.IntegerField(min_value=1, max_value=300, default=30)
    streams = serializers.ListField(
        child=serializers.ChoiceField(choices=['rgb', 'slam_left', 'slam_right', 'eye_tracking']),
        default=['rgb']
    )
    compression_format = serializers.ChoiceField(choices=['jpeg', 'png', 'webp', 'raw'], default='jpeg')
    compression_quality = serializers.IntegerField(min_value=1, max_value=100, default=90)
    
    def validate_duration_seconds(self, value):
        if value > 300:  # 5 minutes max
            raise serializers.ValidationError("Maximum streaming duration is 300 seconds")
        return value


class BinaryTestMessageSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=100, default='test-binary-session')
    format = serializers.ChoiceField(choices=['jpeg', 'png', 'webp', 'raw'], default='jpeg')
    quality = serializers.IntegerField(min_value=1, max_value=100, default=90)


class BinaryFrameAccessSerializer(serializers.Serializer):
    format = serializers.ChoiceField(choices=['raw', 'base64', 'info'], default='raw')
    cache = serializers.BooleanField(default=True)


