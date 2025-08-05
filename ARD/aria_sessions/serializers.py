from rest_framework import serializers
from .models import AriaStreamingSession, UnifiedSensorData

class AriaStreamingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AriaStreamingSession
        fields = '__all__'
        read_only_fields = ('session_id', 'created_at')

class UnifiedSensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnifiedSensorData
        fields = '__all__'