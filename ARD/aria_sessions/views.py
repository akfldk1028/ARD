"""
Core views for Aria Sessions app
For streaming functionality, use working_streaming components
"""
from rest_framework import viewsets
from django.http import JsonResponse
from .models import AriaStreamingSession, UnifiedSensorData
from .serializers import AriaStreamingSessionSerializer, UnifiedSensorDataSerializer

def test_view(request):
    """Simple test view"""
    return JsonResponse({
        'status': 'success',
        'message': 'aria_sessions app is working!',
        'available_endpoints': [
            '/api/v1/aria-sessions/sessions/',
            '/api/v1/aria-sessions/main-dashboard/',
            '/api/v1/aria-sessions/concurrent-streaming-page/',
            '/api/v1/aria-sessions/concurrent-sensor-page/'
        ]
    })

class AriaStreamingSessionViewSet(viewsets.ModelViewSet):
    """Basic ViewSet for managing Aria sessions"""
    queryset = AriaStreamingSession.objects.all()
    serializer_class = AriaStreamingSessionSerializer

class UnifiedSensorDataViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for reading unified sensor data"""
    queryset = UnifiedSensorData.objects.all()
    serializer_class = UnifiedSensorDataSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        session_id = self.request.query_params.get('session_id')
        if session_id:
            queryset = queryset.filter(session__session_id=session_id)
        return queryset.order_by('device_timestamp_ns')