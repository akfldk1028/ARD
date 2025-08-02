# ARD/aria_streams/raw_serializers.py

from rest_framework import serializers
from django.db.models import Q, Count, Avg, Max, Min, Sum
from .raw_models import RawEyeGazeData, RawHandTrackingData, RawSlamTrajectoryData
from .models import AriaSession


class RawEyeGazeDataSerializer(serializers.ModelSerializer):
    """
    MPS Eye Gaze 원본 데이터 시리얼라이저
    """
    session_info = serializers.SerializerMethodField()
    raw_data_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = RawEyeGazeData
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
    
    def get_session_info(self, obj):
        """세션 기본 정보"""
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial,
            'status': obj.session.status
        }
    
    def get_raw_data_summary(self, obj):
        """원본 데이터 요약"""
        return {
            'data_source': obj.data_source,
            'timestamp_us': obj.tracking_timestamp_us,
            'session_uid': obj.session_uid,
            'has_left_eye': bool(obj.tx_left_eye_cpf),
            'has_right_eye': bool(obj.tx_right_eye_cpf),
            'depth_available': bool(obj.depth_m)
        }


class RawHandTrackingDataSerializer(serializers.ModelSerializer):
    """
    MPS Hand Tracking 원본 데이터 시리얼라이저
    """
    session_info = serializers.SerializerMethodField()
    raw_data_summary = serializers.SerializerMethodField()
    landmark_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = RawHandTrackingData
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
    
    def get_session_info(self, obj):
        """세션 기본 정보"""
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial,
            'status': obj.session.status
        }
    
    def get_raw_data_summary(self, obj):
        """원본 데이터 요약"""
        return {
            'data_source': obj.data_source,
            'timestamp_us': obj.tracking_timestamp_us,
            'left_confidence': obj.left_tracking_confidence,
            'right_confidence': obj.right_tracking_confidence,
            'has_wrist_data': bool(obj.tx_left_device_wrist or obj.tx_right_device_wrist)
        }
    
    def get_landmark_summary(self, obj):
        """랜드마크 데이터 요약"""
        # Count available landmarks for left hand
        left_landmarks = sum(1 for i in range(21) 
                           if getattr(obj, f'tx_left_landmark_{i}_device', None) is not None)
        
        # Count available landmarks for right hand  
        right_landmarks = sum(1 for i in range(21)
                            if getattr(obj, f'tx_right_landmark_{i}_device', None) is not None)
        
        return {
            'left_landmarks_count': left_landmarks,
            'right_landmarks_count': right_landmarks,
            'total_landmarks': left_landmarks + right_landmarks,
            'has_palm_normals': bool(obj.nx_left_palm_device or obj.nx_right_palm_device)
        }


class RawSlamTrajectoryDataSerializer(serializers.ModelSerializer):
    """
    MPS SLAM Trajectory 원본 데이터 시리얼라이저
    """
    session_info = serializers.SerializerMethodField()
    raw_data_summary = serializers.SerializerMethodField()
    trajectory_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = RawSlamTrajectoryData
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
    
    def get_session_info(self, obj):
        """세션 기본 정보"""
        return {
            'session_id': obj.session.session_id,
            'device_serial': obj.session.device_serial,
            'status': obj.session.status
        }
    
    def get_raw_data_summary(self, obj):
        """원본 데이터 요약"""
        return {
            'data_source': obj.data_source,
            'timestamp_us': obj.tracking_timestamp_us,
            'graph_uid': obj.graph_uid,
            'quality_score': obj.quality_score,
            'geo_available': bool(obj.geo_available)
        }
    
    def get_trajectory_summary(self, obj):
        """궤적 데이터 요약"""
        # Calculate position magnitude
        position_magnitude = (obj.tx_world_device**2 + obj.ty_world_device**2 + obj.tz_world_device**2)**0.5
        
        # Calculate velocity magnitude
        velocity_magnitude = (obj.device_linear_velocity_x_device**2 + 
                            obj.device_linear_velocity_y_device**2 + 
                            obj.device_linear_velocity_z_device**2)**0.5
        
        return {
            'position': {
                'x': obj.tx_world_device,
                'y': obj.ty_world_device,
                'z': obj.tz_world_device,
                'magnitude': round(position_magnitude, 3)
            },
            'velocity_magnitude': round(velocity_magnitude, 3),
            'gravity_magnitude': round((obj.gravity_x_world**2 + obj.gravity_y_world**2 + obj.gravity_z_world**2)**0.5, 3),
            'has_ecef_data': bool(obj.tx_ecef_device)
        }


class RawDataQuerySerializer(serializers.Serializer):
    """
    원시 데이터 고급 쿼리용 시리얼라이저
    """
    data_type = serializers.ChoiceField(
        choices=[
            ('eye_gaze', 'Eye Gaze'),
            ('hand_tracking', 'Hand Tracking'),
            ('slam_trajectory', 'SLAM Trajectory')
        ],
        required=False,
        help_text="Filter by raw data type"
    )
    data_source = serializers.CharField(required=False, help_text="Filter by data source")
    start_timestamp_us = serializers.IntegerField(required=False, help_text="Start timestamp filter (microseconds)")
    end_timestamp_us = serializers.IntegerField(required=False, help_text="End timestamp filter (microseconds)")
    session_uid = serializers.CharField(required=False, help_text="Filter by session UID")
    graph_uid = serializers.CharField(required=False, help_text="Filter by SLAM graph UID")
    min_confidence = serializers.FloatField(required=False, help_text="Minimum tracking confidence")
    limit = serializers.IntegerField(default=100, max_value=1000, help_text="Result limit")
    
    def validate(self, attrs):
        """쿼리 검증"""
        start_time = attrs.get('start_timestamp_us')
        end_time = attrs.get('end_timestamp_us')
        
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError("Start timestamp must be before end timestamp")
        
        min_confidence = attrs.get('min_confidence')
        if min_confidence and (min_confidence < 0 or min_confidence > 1):
            raise serializers.ValidationError("Confidence must be between 0 and 1")
        
        return attrs


class RawDataStatisticsSerializer(serializers.Serializer):
    """
    원시 데이터 통계 시리얼라이저
    """
    eye_gaze = serializers.DictField(read_only=True)
    hand_tracking = serializers.DictField(read_only=True)
    slam_trajectory = serializers.DictField(read_only=True)
    total_records = serializers.IntegerField(read_only=True)
    oldest_timestamp_us = serializers.IntegerField(read_only=True)
    newest_timestamp_us = serializers.IntegerField(read_only=True)
    session_count = serializers.IntegerField(read_only=True)