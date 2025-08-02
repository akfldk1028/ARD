# ARD/aria_streams/raw_views.py

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min, Sum
from datetime import datetime, timedelta
import logging
import pandas as pd
import uuid

from .raw_models import RawEyeGazeData, RawHandTrackingData, RawSlamTrajectoryData
from .models import AriaSession
from .raw_serializers import (
    RawEyeGazeDataSerializer, RawHandTrackingDataSerializer, RawSlamTrajectoryDataSerializer,
    RawDataQuerySerializer, RawDataStatisticsSerializer
)

logger = logging.getLogger(__name__)


class RawEyeGazeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    MPS Eye Gaze 원본 데이터 ViewSet
    """
    queryset = RawEyeGazeData.objects.all()
    serializer_class = RawEyeGazeDataSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['data_source', 'session_uid', 'session']
    search_fields = ['session_uid', 'session__session_id']
    ordering_fields = ['tracking_timestamp_us', 'created_at']
    ordering = ['tracking_timestamp_us']
    
    def get_queryset(self):
        """쿼리셋 최적화"""
        return self.queryset.select_related('session')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Eye Gaze 원본 데이터 요약"""
        queryset = self.get_queryset()
        
        summary = {
            'total_records': queryset.count(),
            'unique_sessions': queryset.values('session_uid').distinct().count(),
            'timestamp_range': {
                'earliest': queryset.aggregate(Min('tracking_timestamp_us'))['tracking_timestamp_us__min'],
                'latest': queryset.aggregate(Max('tracking_timestamp_us'))['tracking_timestamp_us__max']
            },
            'depth_stats': {
                'min': queryset.aggregate(Min('depth_m'))['depth_m__min'],
                'max': queryset.aggregate(Max('depth_m'))['depth_m__max'],
                'avg': queryset.aggregate(Avg('depth_m'))['depth_m__avg']
            },
            'by_session': list(queryset.values('session_uid').annotate(count=Count('id')))
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['post'])
    def query(self, request):
        """고급 쿼리 기능"""
        serializer = RawDataQuerySerializer(data=request.data)
        if serializer.is_valid():
            queryset = self.get_queryset()
            
            # 필터 적용
            if serializer.validated_data.get('start_timestamp_us'):
                queryset = queryset.filter(tracking_timestamp_us__gte=serializer.validated_data['start_timestamp_us'])
            if serializer.validated_data.get('end_timestamp_us'):
                queryset = queryset.filter(tracking_timestamp_us__lte=serializer.validated_data['end_timestamp_us'])
            if serializer.validated_data.get('session_uid'):
                queryset = queryset.filter(session_uid=serializer.validated_data['session_uid'])
            
            # 제한
            limit = serializer.validated_data.get('limit', 100)
            queryset = queryset[:limit]
            
            result_serializer = self.get_serializer(queryset, many=True)
            return Response({
                'count': len(queryset),
                'results': result_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RawHandTrackingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    MPS Hand Tracking 원본 데이터 ViewSet
    """
    queryset = RawHandTrackingData.objects.all()
    serializer_class = RawHandTrackingDataSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['data_source', 'session']
    search_fields = ['session__session_id']
    ordering_fields = ['tracking_timestamp_us', 'created_at']
    ordering = ['tracking_timestamp_us']
    
    def get_queryset(self):
        """쿼리셋 최적화"""
        return self.queryset.select_related('session')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Hand Tracking 원본 데이터 요약"""
        queryset = self.get_queryset()
        
        # Calculate confidence statistics
        left_conf_stats = queryset.aggregate(
            min_conf=Min('left_tracking_confidence'),
            max_conf=Max('left_tracking_confidence'),
            avg_conf=Avg('left_tracking_confidence')
        )
        
        right_conf_stats = queryset.aggregate(
            min_conf=Min('right_tracking_confidence'),
            max_conf=Max('right_tracking_confidence'),
            avg_conf=Avg('right_tracking_confidence')
        )
        
        summary = {
            'total_records': queryset.count(),
            'timestamp_range': {
                'earliest': queryset.aggregate(Min('tracking_timestamp_us'))['tracking_timestamp_us__min'],
                'latest': queryset.aggregate(Max('tracking_timestamp_us'))['tracking_timestamp_us__max']
            },
            'confidence_stats': {
                'left_hand': left_conf_stats,
                'right_hand': right_conf_stats
            },
            'hand_detection': {
                'has_wrist_data': queryset.filter(
                    Q(tx_left_device_wrist__isnull=False) | Q(tx_right_device_wrist__isnull=False)
                ).count(),
                'has_palm_normals': queryset.filter(
                    Q(nx_left_palm_device__isnull=False) | Q(nx_right_palm_device__isnull=False)
                ).count()
            }
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['post'])
    def query(self, request):
        """고급 쿼리 기능"""
        serializer = RawDataQuerySerializer(data=request.data)
        if serializer.is_valid():
            queryset = self.get_queryset()
            
            # 필터 적용
            if serializer.validated_data.get('start_timestamp_us'):
                queryset = queryset.filter(tracking_timestamp_us__gte=serializer.validated_data['start_timestamp_us'])
            if serializer.validated_data.get('end_timestamp_us'):
                queryset = queryset.filter(tracking_timestamp_us__lte=serializer.validated_data['end_timestamp_us'])
            if serializer.validated_data.get('min_confidence'):
                min_conf = serializer.validated_data['min_confidence']
                queryset = queryset.filter(
                    Q(left_tracking_confidence__gte=min_conf) | Q(right_tracking_confidence__gte=min_conf)
                )
            
            # 제한
            limit = serializer.validated_data.get('limit', 100)
            queryset = queryset[:limit]
            
            result_serializer = self.get_serializer(queryset, many=True)
            return Response({
                'count': len(queryset),
                'results': result_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RawSlamTrajectoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    MPS SLAM Trajectory 원본 데이터 ViewSet
    """
    queryset = RawSlamTrajectoryData.objects.all()
    serializer_class = RawSlamTrajectoryDataSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['data_source', 'graph_uid', 'session']
    search_fields = ['graph_uid', 'session__session_id']
    ordering_fields = ['tracking_timestamp_us', 'created_at', 'quality_score']
    ordering = ['tracking_timestamp_us']
    
    def get_queryset(self):
        """쿼리셋 최적화"""
        return self.queryset.select_related('session')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """SLAM Trajectory 원본 데이터 요약"""
        queryset = self.get_queryset()
        
        summary = {
            'total_records': queryset.count(),
            'unique_graphs': queryset.values('graph_uid').distinct().count(),
            'timestamp_range': {
                'earliest': queryset.aggregate(Min('tracking_timestamp_us'))['tracking_timestamp_us__min'],
                'latest': queryset.aggregate(Max('tracking_timestamp_us'))['tracking_timestamp_us__max']
            },
            'quality_stats': {
                'min': queryset.aggregate(Min('quality_score'))['quality_score__min'],
                'max': queryset.aggregate(Max('quality_score'))['quality_score__max'],
                'avg': queryset.aggregate(Avg('quality_score'))['quality_score__avg']
            },
            'position_stats': {
                'x_range': {
                    'min': queryset.aggregate(Min('tx_world_device'))['tx_world_device__min'],
                    'max': queryset.aggregate(Max('tx_world_device'))['tx_world_device__max']
                },
                'y_range': {
                    'min': queryset.aggregate(Min('ty_world_device'))['ty_world_device__min'],
                    'max': queryset.aggregate(Max('ty_world_device'))['ty_world_device__max']
                },
                'z_range': {
                    'min': queryset.aggregate(Min('tz_world_device'))['tz_world_device__min'],
                    'max': queryset.aggregate(Max('tz_world_device'))['tz_world_device__max']
                }
            },
            'geo_available_count': queryset.filter(geo_available=1).count(),
            'by_graph': list(queryset.values('graph_uid').annotate(count=Count('id')))
        }
        
        return Response(summary)
    
    @action(detail=False, methods=['post'])
    def query(self, request):
        """고급 쿼리 기능"""
        serializer = RawDataQuerySerializer(data=request.data)
        if serializer.is_valid():
            queryset = self.get_queryset()
            
            # 필터 적용
            if serializer.validated_data.get('start_timestamp_us'):
                queryset = queryset.filter(tracking_timestamp_us__gte=serializer.validated_data['start_timestamp_us'])
            if serializer.validated_data.get('end_timestamp_us'):
                queryset = queryset.filter(tracking_timestamp_us__lte=serializer.validated_data['end_timestamp_us'])
            if serializer.validated_data.get('graph_uid'):
                queryset = queryset.filter(graph_uid=serializer.validated_data['graph_uid'])
            
            # 제한
            limit = serializer.validated_data.get('limit', 100)
            queryset = queryset[:limit]
            
            result_serializer = self.get_serializer(queryset, many=True)
            return Response({
                'count': len(queryset),
                'results': result_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def trajectory_path(self, request):
        """전체 궤적 경로 데이터"""
        queryset = self.get_queryset().order_by('tracking_timestamp_us')
        
        # 궤적 포인트만 추출
        trajectory_points = []
        for record in queryset:
            trajectory_points.append({
                'timestamp_us': record.tracking_timestamp_us,
                'position': {
                    'x': record.tx_world_device,
                    'y': record.ty_world_device,
                    'z': record.tz_world_device
                },
                'quality_score': record.quality_score
            })
        
        return Response({
            'total_points': len(trajectory_points),
            'trajectory': trajectory_points
        })


class RawDataStatsView(APIView):
    """
    Raw 데이터 전체 통계 뷰
    """
    
    def get(self, request):
        """전체 Raw 데이터 통계"""
        eye_gaze_count = RawEyeGazeData.objects.count()
        hand_tracking_count = RawHandTrackingData.objects.count()
        slam_trajectory_count = RawSlamTrajectoryData.objects.count()
        
        # 세션 통계
        session_count = AriaSession.objects.filter(
            Q(raw_eye_gaze__isnull=False) |
            Q(raw_hand_tracking__isnull=False) |
            Q(raw_slam_trajectory__isnull=False)
        ).distinct().count()
        
        # 타임스탬프 범위
        timestamp_stats = {}
        if eye_gaze_count > 0:
            eye_gaze_range = RawEyeGazeData.objects.aggregate(
                min_ts=Min('tracking_timestamp_us'),
                max_ts=Max('tracking_timestamp_us')
            )
            timestamp_stats['eye_gaze'] = eye_gaze_range
        
        if hand_tracking_count > 0:
            hand_tracking_range = RawHandTrackingData.objects.aggregate(
                min_ts=Min('tracking_timestamp_us'),
                max_ts=Max('tracking_timestamp_us')
            )
            timestamp_stats['hand_tracking'] = hand_tracking_range
        
        if slam_trajectory_count > 0:
            slam_range = RawSlamTrajectoryData.objects.aggregate(
                min_ts=Min('tracking_timestamp_us'),
                max_ts=Max('tracking_timestamp_us')
            )
            timestamp_stats['slam_trajectory'] = slam_range
        
        stats = {
            'eye_gaze': {
                'total': eye_gaze_count,
                'unique_sessions': RawEyeGazeData.objects.values('session_uid').distinct().count(),
                'data_source_distribution': list(RawEyeGazeData.objects.values('data_source').annotate(count=Count('id')))
            },
            'hand_tracking': {
                'total': hand_tracking_count,
                'data_source_distribution': list(RawHandTrackingData.objects.values('data_source').annotate(count=Count('id')))
            },
            'slam_trajectory': {
                'total': slam_trajectory_count,
                'unique_graphs': RawSlamTrajectoryData.objects.values('graph_uid').distinct().count(),
                'data_source_distribution': list(RawSlamTrajectoryData.objects.values('data_source').annotate(count=Count('id')))
            },
            'total_records': eye_gaze_count + hand_tracking_count + slam_trajectory_count,
            'session_count': session_count,
            'timestamp_ranges': timestamp_stats,
            'oldest_timestamp_us': min([
                ts_range.get('min_ts', float('inf')) 
                for ts_range in timestamp_stats.values() 
                if ts_range.get('min_ts') is not None
            ]) if timestamp_stats else None,
            'newest_timestamp_us': max([
                ts_range.get('max_ts', 0) 
                for ts_range in timestamp_stats.values() 
                if ts_range.get('max_ts') is not None
            ]) if timestamp_stats else None
        }
        
        return Response(stats)