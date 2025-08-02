from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from .models import SmartwatchSession, SensorData, HealthMetrics
from .serializers import (
    SmartwatchSessionSerializer, 
    SensorDataSerializer, 
    HealthMetricsSerializer
)
from .producers import SmartwatchKafkaProducer

logger = logging.getLogger(__name__)

class SmartwatchSessionViewSet(viewsets.ModelViewSet):
    queryset = SmartwatchSession.objects.all()
    serializer_class = SmartwatchSessionSerializer
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        session = self.get_object()
        session.ended_at = timezone.now()
        session.status = 'COMPLETED'
        session.save()
        return Response({'status': 'session ended'})

class SensorDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SensorData.objects.all()
    serializer_class = SensorDataSerializer
    ordering = ['-timestamp']
    filterset_fields = ['session', 'sensor_type']

class HealthMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HealthMetrics.objects.all()
    serializer_class = HealthMetricsSerializer
    ordering = ['-timestamp']
    filterset_fields = ['session', 'metric_type']

class StreamingControlView(APIView):
    def get(self, request):
        return JsonResponse({
            'status': 'available',
            'service': 'smartwatch',
            'timestamp': timezone.now().isoformat()
        })

    def post(self, request):
        return JsonResponse({
            'status': 'streaming started',
            'service': 'smartwatch',
            'timestamp': timezone.now().isoformat()
        })

class TestMessageView(APIView):
    def post(self, request):
        try:
            producer = SmartwatchKafkaProducer()
            success = producer.send_test_sensor_data()
            producer.close()
            
            if success:
                return JsonResponse({
                    'status': 'success',
                    'message': 'Test smartwatch data sent',
                    'timestamp': timezone.now().isoformat()
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to send test data'
                }, status=500)
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)