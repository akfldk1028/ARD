from rest_framework import serializers
from .models import SmartwatchSession, SensorData, HealthMetrics

class SmartwatchSessionSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()
    
    class Meta:
        model = SmartwatchSession
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
    
    def get_duration_seconds(self, obj):
        if obj.ended_at and obj.created_at:
            return (obj.ended_at - obj.created_at).total_seconds()
        return None

class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        fields = '__all__'
        read_only_fields = ('timestamp',)

class HealthMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthMetrics
        fields = '__all__'
        read_only_fields = ('timestamp',)