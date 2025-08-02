from rest_framework import serializers
from .models import WebcamSession, WebcamFrame, WebcamAnalysis


class WebcamSessionSerializer(serializers.ModelSerializer):
    """Webcam session serializer"""
    duration = serializers.SerializerMethodField()
    frame_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WebcamSession
        fields = [
            'id', 'session_id', 'session_uid', 'device_name',
            'started_at', 'ended_at', 'status', 'metadata',
            'duration', 'frame_count'
        ]
        read_only_fields = ['session_uid']
    
    def get_duration(self, obj):
        """Calculate session duration"""
        if obj.ended_at and obj.started_at:
            return (obj.ended_at - obj.started_at).total_seconds()
        return None
    
    def get_frame_count(self, obj):
        """Get total frame count"""
        return obj.frames.count()


class WebcamFrameSerializer(serializers.ModelSerializer):
    """Webcam frame serializer"""
    session_id = serializers.CharField(source='session.session_id', read_only=True)
    
    class Meta:
        model = WebcamFrame
        fields = [
            'id', 'session', 'session_id', 'frame_id', 'timestamp',
            'width', 'height', 'fps', 'format',
            'frame_path', 'thumbnail_path',
            'kafka_offset', 'kafka_partition', 'created_at'
        ]


class WebcamAnalysisSerializer(serializers.ModelSerializer):
    """Webcam analysis serializer"""
    session_id = serializers.CharField(source='session.session_id', read_only=True)
    frame_id = serializers.CharField(source='frame.frame_id', read_only=True)
    
    class Meta:
        model = WebcamAnalysis
        fields = [
            'id', 'session', 'session_id', 'frame', 'frame_id',
            'analysis_type', 'timestamp', 'confidence',
            'results', 'metadata', 'created_at'
        ]