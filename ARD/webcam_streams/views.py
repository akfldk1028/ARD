from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import WebcamSession, WebcamFrame, WebcamAnalysis
from .serializers import WebcamSessionSerializer, WebcamFrameSerializer, WebcamAnalysisSerializer


class WebcamSessionViewSet(viewsets.ModelViewSet):
    """Webcam session management API"""
    queryset = WebcamSession.objects.all()
    serializer_class = WebcamSessionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'device_name']
    search_fields = ['session_id', 'device_name']
    ordering_fields = ['started_at', 'ended_at']
    ordering = ['-started_at']

    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        """End webcam session"""
        session = self.get_object()
        session.status = 'COMPLETED'
        session.save()
        return Response({'status': 'session ended'})


class WebcamFrameViewSet(viewsets.ReadOnlyModelViewSet):
    """Webcam frame data API"""
    queryset = WebcamFrame.objects.all()
    serializer_class = WebcamFrameSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['session', 'format', 'width', 'height']
    search_fields = ['frame_id']
    ordering_fields = ['timestamp', 'created_at']
    ordering = ['-timestamp']


class WebcamAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """Webcam analysis results API"""
    queryset = WebcamAnalysis.objects.all()
    serializer_class = WebcamAnalysisSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['session', 'analysis_type', 'confidence']
    search_fields = ['analysis_type']
    ordering_fields = ['timestamp', 'confidence']
    ordering = ['-timestamp']

    @action(detail=False, methods=['get'])
    def motion_alerts(self, request):
        """Get recent motion detection alerts"""
        alerts = self.queryset.filter(
            analysis_type='motion',
            confidence__gte=0.7
        ).order_by('-timestamp')[:10]
        
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)