from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.reverse import reverse
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.db.models import Q, Count, Avg, Max, Min
from datetime import datetime, timedelta
import threading
import asyncio
import logging

from .models import (
    AriaSession, VRSStream, EyeGazeData, 
    HandTrackingData, SLAMTrajectoryData,
    SLAMPointCloud, AnalyticsResult, KafkaConsumerStatus,
    IMUData
)
from .raw_models import RawEyeGazeData, RawHandTrackingData, RawSlamTrajectoryData
from .serializers import (
    AriaSessionSerializer, VRSStreamSerializer, EyeGazeDataSerializer,
    HandTrackingDataSerializer, SLAMTrajectoryDataSerializer,
    SLAMPointCloudSerializer, AnalyticsResultSerializer, 
    KafkaConsumerStatusSerializer, StreamingControlSerializer,
    TestMessageSerializer, EyeGazeStreamingSerializer, HandTrackingStreamingSerializer,
    IMUDataSerializer
)
from .producers import AriaKafkaProducer
from .vrs_reader import VRSKafkaStreamer
from kafka import KafkaConsumer
import base64
import uuid
from projectaria_tools.core import mps

logger = logging.getLogger(__name__)

# 전역 스트리밍 상태 관리
streaming_status = {
    'is_streaming': False,
    'current_streams': [],
    'last_started': None,
    'message_count': 0
}


class AriaSessionViewSet(viewsets.ModelViewSet):
    """
    Aria 세션 관리 ViewSet
    - 세션 생성, 조회, 수정, 삭제
    - 세션별 스트림 데이터 통계
    """
    queryset = AriaSession.objects.all()
    serializer_class = AriaSessionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'device_serial']
    search_fields = ['session_id', 'device_serial']
    ordering_fields = ['started_at', 'ended_at']
    ordering = ['-started_at']
    
    def get_queryset(self):
        """커스텀 쿼리셋 - prefetch로 성능 최적화"""
        return super().get_queryset().prefetch_related(
            'vrs_streams', 'eye_gaze_data', 'hand_tracking_data',
            'slam_trajectory_data', 'slam_point_clouds', 'analytics_results'
        )
    
    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        """세션 종료"""
        session = self.get_object()
        if session.status == 'COMPLETED':
            return Response(
                {'detail': '이미 완료된 세션입니다.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session.ended_at = timezone.now()
        session.status = 'COMPLETED'
        session.save()
        
        return Response({
            'detail': '세션이 종료되었습니다.',
            'ended_at': session.ended_at,
            'duration': (session.ended_at - session.started_at).total_seconds()
        })
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """세션별 상세 통계"""
        session = self.get_object()
        
        # 시간대별 데이터 분포
        time_ranges = []
        current = session.started_at
        end_time = session.ended_at or timezone.now()
        
        while current < end_time:
            next_time = current + timedelta(minutes=10)
            range_data = {
                'start': current,
                'end': min(next_time, end_time),
                'vrs_count': session.vrs_streams.filter(
                    timestamp__range=(current, next_time)
                ).count(),
                'gaze_count': session.eye_gaze_data.filter(
                    timestamp__range=(current, next_time)
                ).count()
            }
            time_ranges.append(range_data)
            current = next_time
        
        return Response({
            'session_id': session.session_id,
            'total_duration': (end_time - session.started_at).total_seconds(),
            'time_ranges': time_ranges,
            'stream_distribution': {
                'vrs_streams': session.vrs_streams.values('stream_name').annotate(
                    count=Count('id')
                ),
                'gaze_types': session.eye_gaze_data.values('gaze_type').annotate(
                    count=Count('id')
                )
            }
        })


class VRSStreamViewSet(viewsets.ReadOnlyModelViewSet):
    """
    VRS 스트림 데이터 ViewSet (읽기 전용)
    - 스트림별 필터링 및 검색
    - 시간 범위 필터링
    """
    queryset = VRSStream.objects.all()
    serializer_class = VRSStreamSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['session', 'stream_name', 'pixel_format']
    search_fields = ['stream_name', 'session__session_id']
    ordering_fields = ['timestamp', 'device_timestamp_ns', 'frame_index']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('session')
        
        # 시간 범위 필터링
        start_time = self.request.query_params.get('start_time')
        end_time = self.request.query_params.get('end_time')
        
        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)
        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def stream_summary(self, request):
        """스트림별 요약 통계"""
        summary = self.get_queryset().values('stream_name').annotate(
            total_frames=Count('id'),
            latest_frame=Max('timestamp'),
            avg_fps=Count('id') / (
                (Max('timestamp') - Min('timestamp')).total_seconds() or 1
            )
        ).order_by('-total_frames')
        
        return Response(summary)


class IMUDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    IMU 데이터 ViewSet (읽기 전용)
    - IMU 타입별 필터링 (left/right)
    - 가속도/자이로 데이터 조회
    - 실시간 모션 분석
    """
    queryset = IMUData.objects.all()
    serializer_class = IMUDataSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['session', 'imu_type', 'imu_stream_id']
    search_fields = ['session__session_id', 'imu_type']
    ordering_fields = ['timestamp', 'device_timestamp_ns']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('session')
        
        # 시간 범위 필터링
        start_time = self.request.query_params.get('start_time')
        end_time = self.request.query_params.get('end_time')
        
        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)
        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)
            
        # 가속도/자이로 임계값 필터링
        min_accel = self.request.query_params.get('min_acceleration')
        min_gyro = self.request.query_params.get('min_angular_velocity')
        
        if min_accel:
            # SQL에서 벡터 크기 계산
            queryset = queryset.extra(
                where=["SQRT(accel_x*accel_x + accel_y*accel_y + accel_z*accel_z) >= %s"],
                params=[float(min_accel)]
            )
        if min_gyro:
            queryset = queryset.extra(
                where=["SQRT(gyro_x*gyro_x + gyro_y*gyro_y + gyro_z*gyro_z) >= %s"],
                params=[float(min_gyro)]
            )
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def motion_analysis(self, request):
        """IMU 모션 분석 - 가속도/자이로 통계"""
        session_id = request.query_params.get('session')
        imu_type = request.query_params.get('imu_type', 'left')
        
        queryset = self.get_queryset()
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        
        queryset = queryset.filter(imu_type=imu_type)
        
        if not queryset.exists():
            return Response({'detail': 'No IMU data found'}, status=404)
        
        # 통계 계산
        stats = queryset.aggregate(
            accel_x_avg=Avg('accel_x'),
            accel_y_avg=Avg('accel_y'),
            accel_z_avg=Avg('accel_z'),
            accel_x_max=Max('accel_x'),
            accel_y_max=Max('accel_y'),
            accel_z_max=Max('accel_z'),
            gyro_x_avg=Avg('gyro_x'),
            gyro_y_avg=Avg('gyro_y'),
            gyro_z_avg=Avg('gyro_z'),
            gyro_x_max=Max('gyro_x'),
            gyro_y_max=Max('gyro_y'),
            gyro_z_max=Max('gyro_z'),
            temp_avg=Avg('temperature_c'),
            temp_max=Max('temperature_c'),
            temp_min=Min('temperature_c'),
            sample_count=Count('id')
        )
        
        return Response({
            'imu_type': imu_type,
            'session': session_id,
            'sample_count': stats['sample_count'],
            'acceleration_stats': {
                'x_avg': round(stats['accel_x_avg'], 4),
                'y_avg': round(stats['accel_y_avg'], 4), 
                'z_avg': round(stats['accel_z_avg'], 4),
                'x_max': round(stats['accel_x_max'], 4),
                'y_max': round(stats['accel_y_max'], 4),
                'z_max': round(stats['accel_z_max'], 4)
            },
            'gyroscope_stats': {
                'x_avg': round(stats['gyro_x_avg'], 4),
                'y_avg': round(stats['gyro_y_avg'], 4),
                'z_avg': round(stats['gyro_z_avg'], 4),
                'x_max': round(stats['gyro_x_max'], 4),
                'y_max': round(stats['gyro_y_max'], 4),
                'z_max': round(stats['gyro_z_max'], 4)
            },
            'temperature_stats': {
                'avg': round(stats['temp_avg'], 2) if stats['temp_avg'] else None,
                'max': round(stats['temp_max'], 2) if stats['temp_max'] else None,
                'min': round(stats['temp_min'], 2) if stats['temp_min'] else None
            }
        })


class EyeGazeDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Eye Gaze 데이터 ViewSet
    - Gaze 타입별 필터링
    - 시간 범위 및 정확도 필터링
    """
    queryset = EyeGazeData.objects.all()
    serializer_class = EyeGazeDataSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['session', 'gaze_type']
    ordering_fields = ['timestamp', 'device_timestamp_ns', 'confidence']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('session')
        
        # 정확도 필터링
        min_confidence = self.request.query_params.get('min_confidence')
        if min_confidence:
            queryset = queryset.filter(confidence__gte=float(min_confidence))
            
        # 깊이 범위 필터링
        min_depth = self.request.query_params.get('min_depth')
        max_depth = self.request.query_params.get('max_depth')
        
        if min_depth:
            queryset = queryset.filter(depth_m__gte=float(min_depth))
        if max_depth:
            queryset = queryset.filter(depth_m__lte=float(max_depth))
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def gaze_heatmap(self, request):
        """시선 히트맵 데이터"""
        session_id = request.query_params.get('session')
        gaze_type = request.query_params.get('gaze_type', 'general')
        
        queryset = self.get_queryset()
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        
        queryset = queryset.filter(gaze_type=gaze_type)
        
        # 시선 방향 데이터 집계
        gaze_data = []
        for gaze in queryset[:1000]:  # 최대 1000개 샘플
            gaze_data.append({
                'yaw': gaze.yaw,
                'pitch': gaze.pitch,
                'depth': gaze.depth_m,
                'timestamp': gaze.timestamp
            })
        
        return Response({
            'gaze_type': gaze_type,
            'total_samples': len(gaze_data),
            'gaze_data': gaze_data
        })


class HandTrackingDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Hand Tracking 데이터 ViewSet
    - 손 존재 여부 필터링
    - 랜드마크 데이터 조회
    """
    queryset = HandTrackingData.objects.all()
    serializer_class = HandTrackingDataSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['session']
    ordering_fields = ['timestamp', 'device_timestamp_ns']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('session')
        
        # 손 존재 필터링
        has_left = self.request.query_params.get('has_left_hand')
        has_right = self.request.query_params.get('has_right_hand')
        
        if has_left == 'true':
            queryset = queryset.filter(left_hand_landmarks__isnull=False)
        elif has_left == 'false':
            queryset = queryset.filter(left_hand_landmarks__isnull=True)
            
        if has_right == 'true':
            queryset = queryset.filter(right_hand_landmarks__isnull=False)
        elif has_right == 'false':
            queryset = queryset.filter(right_hand_landmarks__isnull=True)
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def hand_statistics(self, request):
        """손 추적 통계"""
        queryset = self.get_queryset()
        
        stats = {
            'total_frames': queryset.count(),
            'left_hand_detected': queryset.filter(
                left_hand_landmarks__isnull=False
            ).count(),
            'right_hand_detected': queryset.filter(
                right_hand_landmarks__isnull=False
            ).count(),
            'both_hands_detected': queryset.filter(
                left_hand_landmarks__isnull=False,
                right_hand_landmarks__isnull=False
            ).count()
        }
        
        return Response(stats)


class SLAMTrajectoryDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    SLAM Trajectory 데이터 ViewSet
    - 위치 기반 필터링
    - 경로 추적 및 분석
    """
    queryset = SLAMTrajectoryData.objects.all()
    serializer_class = SLAMTrajectoryDataSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['session']
    ordering_fields = ['timestamp', 'device_timestamp_ns']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('session')
        
        # 위치 범위 필터링
        x_min = self.request.query_params.get('x_min')
        x_max = self.request.query_params.get('x_max')
        y_min = self.request.query_params.get('y_min')
        y_max = self.request.query_params.get('y_max')
        z_min = self.request.query_params.get('z_min')
        z_max = self.request.query_params.get('z_max')
        
        if x_min: queryset = queryset.filter(position_x__gte=float(x_min))
        if x_max: queryset = queryset.filter(position_x__lte=float(x_max))
        if y_min: queryset = queryset.filter(position_y__gte=float(y_min))
        if y_max: queryset = queryset.filter(position_y__lte=float(y_max))
        if z_min: queryset = queryset.filter(position_z__gte=float(z_min))
        if z_max: queryset = queryset.filter(position_z__lte=float(z_max))
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def trajectory_path(self, request):
        """궤적 경로 데이터"""
        session_id = request.query_params.get('session')
        limit = int(request.query_params.get('limit', 1000))
        
        queryset = self.get_queryset()
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        
        trajectory_points = []
        for point in queryset.order_by('device_timestamp_ns')[:limit]:
            trajectory_points.append({
                'timestamp': point.timestamp,
                'position': {
                    'x': point.position_x,
                    'y': point.position_y,
                    'z': point.position_z
                },
                'transform_matrix': point.transform_matrix
            })
        
        return Response({
            'total_points': len(trajectory_points),
            'trajectory': trajectory_points
        })


class StreamingControlView(APIView):
    """
    스트리밍 제어 통합 View
    - VRS/MPS 스트리밍 시작/중지
    - 스트리밍 상태 조회
    - 직접 DB 저장 (Kafka 우회)
    """
    
    def get(self, request):
        """스트리밍 상태 조회"""
        return Response({
            'status': 'success',
            'data': streaming_status,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def post(self, request):
        """스트리밍 시작"""
        serializer = StreamingControlSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        if streaming_status['is_streaming']:
            return Response({
                'status': 'error',
                'message': '이미 스트리밍이 진행 중입니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        duration = serializer.validated_data['duration']
        stream_type = serializer.validated_data['stream_type']
        
        def start_streaming():
            try:
                vrs_file = "/app/ARD/data/mps_samples/sample.vrs"
                mps_data_path = "/app/ARD/data/mps_samples"
                
                streamer = VRSKafkaStreamer(vrs_file, mps_data_path)
                
                # 스트리밍 상태 업데이트
                streaming_status['is_streaming'] = True
                streaming_status['current_streams'] = ['vrs', 'mps'] if stream_type == 'all' else [stream_type]
                streaming_status['last_started'] = datetime.utcnow().isoformat()
                
                # 스트리밍 실행
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                tasks = []
                if stream_type in ['vrs', 'all']:
                    tasks.append(streamer.stream_vrs_data(duration))
                if stream_type in ['mps', 'all']:
                    tasks.append(streamer.stream_mps_data(duration))
                
                async def run_tasks():
                    await asyncio.gather(*tasks)
                
                loop.run_until_complete(run_tasks())


                # 스트리밍 완료 후 상태 리셋
                streaming_status['is_streaming'] = False
                streaming_status['current_streams'] = []
                
                streamer.close()
                
            except Exception as e:
                streaming_status['is_streaming'] = False
                streaming_status['current_streams'] = []
                logger.error(f"VRS streaming error: {e}")
        
        # 백그라운드에서 스트리밍 실행
        thread = threading.Thread(target=start_streaming)
        thread.daemon = True
        thread.start()
        
        return Response({
            'status': 'success',
            'message': f'{stream_type} 데이터 스트리밍을 시작했습니다.',
            'duration': duration,
            'stream_type': stream_type,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def delete(self, request):
        """스트리밍 중지"""
        if not streaming_status['is_streaming']:
            return Response({
                'status': 'error',
                'message': '진행 중인 스트리밍이 없습니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        streaming_status['is_streaming'] = False
        streaming_status['current_streams'] = []
        
        return Response({
            'status': 'success',
            'message': '스트리밍이 중지되었습니다.',
            'timestamp': datetime.utcnow().isoformat()
        })


class DirectMPSImportView(APIView):
    """
    MPS 데이터 직접 임포트 View (Kafka 우회)
    - Eye Gaze, Hand Tracking, SLAM 데이터를 Django DB에 직접 저장
    - Kafka 연결 문제 해결용
    """
    
    def post(self, request):
        """MPS 데이터 직접 임포트 실행"""
        try:
            # 1. 기존 MPS 세션 삭제
            deleted_count = AriaSession.objects.filter(session_id__contains='mps').delete()
            
            # 2. 새 세션 생성
            session = AriaSession.objects.create(
                session_id='mps-direct-view',
                session_uid=uuid.uuid4(),
                device_serial='aria-view-device',
                status='COMPLETED',
                metadata={
                    'source': 'views_direct_import',
                    'method': 'DirectMPSImportView',
                    'bypass_kafka': True,
                    'import_time': datetime.utcnow().isoformat()
                }
            )
            
            # 3. Eye Gaze 데이터 임포트 (일반 + Raw)
            eye_gaze_count = self._import_eye_gaze_to_db(session)
            raw_eye_gaze_count = self._import_raw_eye_gaze_to_db(session)
            
            # 4. SLAM 데이터 임포트 (일반 + Raw)
            slam_count = self._import_slam_to_db(session)
            raw_slam_count = self._import_raw_slam_to_db(session)
            
            return Response({
                'status': 'success',
                'message': 'MPS 데이터 직접 임포트 완료',
                'data': {
                    'session_id': session.session_id,
                    'processed_data': {
                        'eye_gaze_count': eye_gaze_count,
                        'slam_count': slam_count
                    },
                    'raw_data': {
                        'raw_eye_gaze_count': raw_eye_gaze_count,
                        'raw_slam_count': raw_slam_count
                    },
                    'total_count': eye_gaze_count + slam_count + raw_eye_gaze_count + raw_slam_count,
                    'deleted_old_sessions': deleted_count[0] if deleted_count else 0
                },
                'test_urls': {
                    'processed_apis': {
                        'sessions': '/api/v1/aria/api/sessions/',
                        'eye_gaze': '/api/v1/aria/api/eye-gaze/',
                        'slam_trajectory': '/api/v1/aria/api/slam-trajectory/'
                    },
                    'raw_apis': {
                        'raw_eye_gaze': '/api/v1/aria/raw/eye-gaze/',
                        'raw_slam_trajectory': '/api/v1/aria/raw/slam-trajectory/',
                        'raw_statistics': '/api/v1/aria/raw/statistics/'
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"MPS 직접 임포트 실패: {e}")
            return Response({
                'status': 'error',
                'message': f'MPS 임포트 실패: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _import_eye_gaze_to_db(self, session):
        """Eye Gaze 데이터 직접 DB 저장"""
        try:
            count = 0
            
            # General Eye Gaze
            general_path = "/app/ARD/data/mps_samples/eye_gaze/general_eye_gaze.csv"
            general_gazes = mps.read_eyegaze(general_path)
            
            for gaze in general_gazes[::60]:  # 60개마다 1개씩
                EyeGazeData.objects.create(
                    session=session,
                    device_timestamp_ns=int(gaze.tracking_timestamp.total_seconds() * 1e9),
                    gaze_type='general',
                    yaw=float(gaze.yaw * 180 / 3.14159),
                    pitch=float(gaze.pitch * 180 / 3.14159),
                    depth_m=float(gaze.depth) if gaze.depth else 1.0,
                    confidence=0.95
                )
                count += 1
                if count >= 25:
                    break
            
            # Personalized Eye Gaze
            personalized_path = "/app/ARD/data/mps_samples/eye_gaze/personalized_eye_gaze.csv"
            personalized_gazes = mps.read_eyegaze(personalized_path)
            
            for gaze in personalized_gazes[::80]:  # 80개마다 1개씩
                EyeGazeData.objects.create(
                    session=session,
                    device_timestamp_ns=int(gaze.tracking_timestamp.total_seconds() * 1e9),
                    gaze_type='personalized',
                    yaw=float(gaze.yaw * 180 / 3.14159),
                    pitch=float(gaze.pitch * 180 / 3.14159),
                    depth_m=float(gaze.depth) if gaze.depth else 1.0,
                    confidence=0.98
                )
                count += 1
                if count >= 40:
                    break
            
            return count
            
        except Exception as e:
            logger.error(f"Eye Gaze 직접 저장 실패: {e}")
            return 0
    
    def _import_slam_to_db(self, session):
        """SLAM 데이터 직접 DB 저장"""
        try:
            slam_path = "/app/ARD/data/mps_samples/slam/closed_loop_trajectory.csv"
            slam_poses = mps.read_closed_loop_trajectory(slam_path)
            
            count = 0
            for pose in slam_poses[::1200]:  # 1200개마다 1개씩
                try:
                    # SE3 변환 추출
                    transform = pose.transform_world_device
                    translation = transform.translation()
                    
                    # 간단한 변환 행렬 (회전은 단위행렬로 근사)
                    transform_matrix = [
                        [1.0, 0.0, 0.0, float(translation[0])],
                        [0.0, 1.0, 0.0, float(translation[1])],
                        [0.0, 0.0, 1.0, float(translation[2])],
                        [0.0, 0.0, 0.0, 1.0]
                    ]
                    
                    SLAMTrajectoryData.objects.create(
                        session=session,
                        device_timestamp_ns=int(pose.tracking_timestamp.total_seconds() * 1e9),
                        transform_matrix=transform_matrix,
                        position_x=float(translation[0]),
                        position_y=float(translation[1]),
                        position_z=float(translation[2])
                    )
                    count += 1
                    if count >= 40:
                        break
                        
                except Exception as e:
                    continue  # 개별 항목 실패 시 스킵
            
            return count
            
        except Exception as e:
            logger.error(f"SLAM 직접 저장 실패: {e}")
            return 0
    
    def _import_raw_eye_gaze_to_db(self, session):
        """Raw Eye Gaze 데이터 직접 DB 저장 (원본 CSV 필드)"""
        try:
            # 기존 Raw 데이터 삭제
            RawEyeGazeData.objects.filter(session__session_id__contains='mps').delete()
            
            count = 0
            
            # General Eye Gaze Raw 데이터
            general_path = "/app/ARD/data/mps_samples/eye_gaze/general_eye_gaze.csv"
            import pandas as pd
            df = pd.read_csv(general_path)
            
            for idx, row in df.head(30).iterrows():  # 30개만
                try:
                    RawEyeGazeData.objects.create(
                        session=session,
                        tracking_timestamp_us=int(row['tracking_timestamp_us']),
                        left_yaw_rads_cpf=float(row['left_yaw_rads_cpf']),
                        right_yaw_rads_cpf=float(row['right_yaw_rads_cpf']),
                        pitch_rads_cpf=float(row['pitch_rads_cpf']),
                        depth_m=float(row['depth_m']),
                        left_yaw_low_rads_cpf=float(row['left_yaw_low_rads_cpf']),
                        right_yaw_low_rads_cpf=float(row['right_yaw_low_rads_cpf']),
                        pitch_low_rads_cpf=float(row['pitch_low_rads_cpf']),
                        left_yaw_high_rads_cpf=float(row['left_yaw_high_rads_cpf']),
                        right_yaw_high_rads_cpf=float(row['right_yaw_high_rads_cpf']),
                        pitch_high_rads_cpf=float(row['pitch_high_rads_cpf']),
                        tx_left_eye_cpf=float(row['tx_left_eye_cpf']),
                        ty_left_eye_cpf=float(row['ty_left_eye_cpf']),
                        tz_left_eye_cpf=float(row['tz_left_eye_cpf']),
                        tx_right_eye_cpf=float(row['tx_right_eye_cpf']),
                        ty_right_eye_cpf=float(row['ty_right_eye_cpf']),
                        tz_right_eye_cpf=float(row['tz_right_eye_cpf']),
                        session_uid=row['session_uid'],
                        data_source='general_eye_gaze_csv'
                    )
                    count += 1
                except Exception as e:
                    continue  # 개별 행 실패 시 스킵
            
            return count
            
        except Exception as e:
            logger.error(f"Raw Eye Gaze 직접 저장 실패: {e}")
            return 0
    
    def _import_raw_slam_to_db(self, session):
        """Raw SLAM 데이터 직접 DB 저장 (원본 CSV 필드)"""
        try:
            # 기존 Raw SLAM 데이터 삭제
            RawSlamTrajectoryData.objects.filter(session__session_id__contains='mps').delete()
            
            count = 0
            
            # SLAM Raw 데이터
            slam_path = "/app/ARD/data/mps_samples/slam/closed_loop_trajectory.csv"
            import pandas as pd
            df = pd.read_csv(slam_path)
            
            for idx, row in df.head(25).iterrows():  # 25개만
                try:
                    RawSlamTrajectoryData.objects.create(
                        session=session,
                        tracking_timestamp_ns=int(row['tracking_timestamp_ns']),
                        tx_world_device=float(row['tx_world_device']),
                        ty_world_device=float(row['ty_world_device']),
                        tz_world_device=float(row['tz_world_device']),
                        qx_world_device=float(row['qx_world_device']),
                        qy_world_device=float(row['qy_world_device']),
                        qz_world_device=float(row['qz_world_device']),
                        qw_world_device=float(row['qw_world_device']),
                        data_source='closed_loop_trajectory_csv'
                    )
                    count += 1
                except Exception as e:
                    continue  # 개별 행 실패 시 스킵
            
            return count
            
        except Exception as e:
            logger.error(f"Raw SLAM 직접 저장 실패: {e}")
            return 0


class TestMessageView(APIView):
    """테스트 메시지 전송 View"""
    
    def post(self, request):
        serializer = TestMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            topic = serializer.validated_data['topic']
            message = serializer.validated_data['message']
            
            producer = AriaKafkaProducer()
            
            test_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'message': message,
                'data_type': 'test_api',
                'source': 'django_class_based_view'
            }
            
            future = producer._get_producer().send(topic, value=test_data)
            result = future.get(timeout=10)
            producer.close()
            
            streaming_status['message_count'] += 1
            
            return Response({
                'status': 'success',
                'message': '테스트 메시지가 성공적으로 전송되었습니다.',
                'topic': topic,
                'kafka_result': {
                    'topic': result.topic,
                    'partition': result.partition,
                    'offset': result.offset
                },
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'메시지 전송 실패: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class KafkaConsumerStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Kafka Consumer 상태 모니터링 ViewSet
    """
    queryset = KafkaConsumerStatus.objects.all()
    serializer_class = KafkaConsumerStatusSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['consumer_group', 'topic', 'status']
    ordering_fields = ['last_processed_at', 'last_offset']
    ordering = ['-last_processed_at']
    
    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """Consumer 건강 상태 체크"""
        now = timezone.now()
        recent_threshold = now - timedelta(minutes=5)
        
        total_consumers = self.get_queryset().count()
        active_consumers = self.get_queryset().filter(status='ACTIVE').count()
        recent_active = self.get_queryset().filter(
            status='ACTIVE',
            last_processed_at__gte=recent_threshold
        ).count()
        
        health_status = 'healthy' if recent_active == active_consumers else 'warning'
        if active_consumers == 0:
            health_status = 'critical'
        
        return Response({
            'health_status': health_status,
            'total_consumers': total_consumers,
            'active_consumers': active_consumers,
            'recent_active_consumers': recent_active,
            'last_check': now.isoformat()
        })


def api_root_html(request):
    """
    HTML 버전의 API Root 페이지
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ARD (Aria Real-time Data) API v1</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            h2 { color: #666; margin-top: 30px; }
            .api-section { margin: 20px 0; }
            .api-link { display: block; padding: 8px 12px; margin: 4px 0; 
                       background: #f5f5f5; border-radius: 4px; text-decoration: none; 
                       color: #007cba; }
            .api-link:hover { background: #e8e8e8; }
            .description { color: #888; font-size: 14px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <h1>🎯 ARD (Aria Real-time Data) API v1</h1>
        <p class="description">Meta Project Aria Real-time Data Processing System</p>
        
        <div class="api-section">
            <h2>📊 Processed Data APIs (일반 사용자용)</h2>
            <a href="/api/v1/aria/sessions/" class="api-link">Sessions (세션 관리)</a>
            <a href="/api/v1/aria/eye-gaze/" class="api-link">Eye Gaze (정제된 시선 데이터)</a>
            <a href="/api/v1/aria/hand-tracking/" class="api-link">Hand Tracking (정제된 핸드 트래킹)</a>
            <a href="/api/v1/aria/slam-trajectory/" class="api-link">SLAM Trajectory (정제된 SLAM 궤적)</a>
            <a href="/api/v1/aria/vrs-streams/" class="api-link">VRS Streams (비디오 스트림)</a>
            <a href="/api/v1/aria/imu-data/" class="api-link">IMU Data (관성 센서)</a>
            <a href="/api/v1/aria/kafka-status/" class="api-link">Kafka Status (스트리밍 상태)</a>
        </div>
        
        <div class="api-section">
            <h2>🔧 Raw Data APIs (MPS 원본 데이터)</h2>
            <a href="/api/v1/aria/raw/statistics/" class="api-link">Raw Statistics (원본 데이터 통계)</a>
            <a href="/api/v1/aria/raw/eye-gaze/" class="api-link">Raw Eye Gaze (MPS 원본 시선)</a>
            <a href="/api/v1/aria/raw/hand-tracking/" class="api-link">Raw Hand Tracking (MPS 원본 핸드)</a>
            <a href="/api/v1/aria/raw/slam-trajectory/" class="api-link">Raw SLAM Trajectory (MPS 원본 SLAM)</a>
        </div>
        
        <div class="api-section">
            <h2>📦 Binary Data APIs (고성능 스트리밍)</h2>
            <a href="/api/v1/aria/binary/registry/" class="api-link">Binary Registry (바이너리 레지스트리)</a>
            <a href="/api/v1/aria/binary/metadata/" class="api-link">Binary Metadata (바이너리 메타데이터)</a>
            <a href="/api/v1/aria/binary/streaming/" class="api-link">Binary Streaming (스트리밍 제어)</a>
            <a href="/api/v1/aria/binary/analytics/" class="api-link">Binary Analytics (바이너리 분석)</a>
        </div>
        
        <div class="api-section">
            <h2>🎮 Control APIs (시스템 제어)</h2>
            <a href="/api/v1/aria/streaming/" class="api-link">Streaming Control (스트리밍 제어)</a>
            <a href="/api/v1/aria/test-message/" class="api-link">Test Message (테스트 메시지)</a>
            <a href="/api/v1/aria/binary/test-message/" class="api-link">Binary Test (바이너리 테스트)</a>
        </div>
        
        <div class="api-section">
            <h2>💡 Quick Examples</h2>
            <a href="/api/v1/aria/eye-gaze/" class="api-link">Processed Eye Gaze (정제된 시선 데이터)</a>
            <a href="/api/v1/aria/raw/eye-gaze/" class="api-link">Raw Eye Gaze with All Fields (모든 원본 필드)</a>
            <a href="/api/v1/aria/raw/statistics/" class="api-link">Raw Data Statistics (원본 데이터 통계)</a>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)

@api_view(['GET'])
def api_root(request, format=None):
    """
    ARD (Aria Real-time Data) API Root
    - Processed Data APIs: 일반 사용자용 정제된 데이터
    - Raw Data APIs: 고급 사용자용 MPS 원본 데이터  
    - Binary Data APIs: 고성능 바이너리 스트리밍
    """
    return Response({
        '🎯 ARD Aria Streams API v1': {
            'description': 'Meta Project Aria Real-time Data Processing System',
            'version': '1.0',
            'documentation': request.build_absolute_uri('/api/v1/aria/'),
        },
        
        '📊 Processed Data APIs (일반 사용자용)': {
            'sessions': request.build_absolute_uri('/api/v1/aria/api/sessions/'),
            'eye-gaze': request.build_absolute_uri('/api/v1/aria/api/eye-gaze/'),
            'hand-tracking': request.build_absolute_uri('/api/v1/aria/api/hand-tracking/'),
            'slam-trajectory': request.build_absolute_uri('/api/v1/aria/api/slam-trajectory/'),
            'vrs-streams': request.build_absolute_uri('/api/v1/aria/api/vrs-streams/'),
            'imu-data': request.build_absolute_uri('/api/v1/aria/api/imu-data/'),
            'kafka-status': request.build_absolute_uri('/api/v1/aria/api/kafka-status/'),
        },
        
        '🔧 Raw Data APIs (MPS 원본 데이터)': {
            'raw-statistics': request.build_absolute_uri('/api/v1/aria/raw/statistics/'),
            'raw-eye-gaze': request.build_absolute_uri('/api/v1/aria/raw/eye-gaze/'),
            'raw-hand-tracking': request.build_absolute_uri('/api/v1/aria/raw/hand-tracking/'),
            'raw-slam-trajectory': request.build_absolute_uri('/api/v1/aria/raw/slam-trajectory/'),
        },
        
        '📦 Binary Data APIs (고성능 스트리밍)': {
            'binary-registry': request.build_absolute_uri('/api/v1/aria/binary/api/registry/'),
            'binary-metadata': request.build_absolute_uri('/api/v1/aria/binary/api/metadata/'),
            'binary-streaming': request.build_absolute_uri('/api/v1/aria/binary/streaming/'),
            'binary-analytics': request.build_absolute_uri('/api/v1/aria/binary/analytics/'),
        },
        
        '🎮 Control APIs (시스템 제어)': {
            'streaming-control': request.build_absolute_uri('/api/v1/aria/streaming/'),
            'test-message': request.build_absolute_uri('/api/v1/aria/test-message/'),
            'binary-test': request.build_absolute_uri('/api/v1/aria/binary/test-message/'),
        },
        
        '💡 Quick Examples': {
            'processed_eye_gaze': request.build_absolute_uri('/api/v1/aria/eye-gaze/'),
            'raw_eye_gaze_with_all_fields': request.build_absolute_uri('/api/v1/aria/raw/eye-gaze/'),
            'binary_frame_access': request.build_absolute_uri('/api/v1/aria/binary/data/{frame_id}/'),
            'raw_statistics': request.build_absolute_uri('/api/v1/aria/raw/statistics/'),
            'vrs_image_view': request.build_absolute_uri('/api/v1/aria/simple-image/'),
        }
    })


class SimpleImageView(APIView):
    """간단한 VRS 이미지 뷰 - Kafka에서 직접 가져오기"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """최근 VRS 이미지를 Kafka에서 가져와서 표시"""
        try:
            import os
            import json
            
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
            
            # 메타데이터 토픽에서 최근 이미지 정보 가져오기
            metadata_consumer = KafkaConsumer(
                'vrs-metadata-stream',
                bootstrap_servers=bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=3000,
                auto_offset_reset='earliest'
            )
            
            # 바이너리 토픽에서 실제 이미지 데이터 가져오기  
            binary_consumer = KafkaConsumer(
                'vrs-binary-stream',
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=3000,
                auto_offset_reset='earliest'
            )
            
            # 최근 메타데이터 가져오기
            latest_metadata = None
            for message in metadata_consumer:
                latest_metadata = message.value
            
            if not latest_metadata:
                return Response({
                    'error': 'No VRS image found in Kafka',
                    'suggestion': 'Generate VRS image: POST /api/v1/aria/binary/test-message/'
                })
            
            # 해당하는 바이너리 데이터 가져오기
            frame_id = latest_metadata['frame_id']
            binary_data = None
            
            for message in binary_consumer:
                if message.key and message.key.decode('utf-8') == frame_id:
                    binary_data = message.value
                    break
            
            metadata_consumer.close()
            binary_consumer.close()
            
            if not binary_data:
                return Response({
                    'error': 'VRS binary data not found',
                    'frame_id': frame_id,
                    'metadata': latest_metadata
                })
            
            # 이미지 데이터 반환
            format_type = request.GET.get('format', 'raw')
            
            if format_type == 'base64':
                return Response({
                    'frame_id': frame_id,
                    'image_data': base64.b64encode(binary_data).decode('utf-8'),
                    'metadata': latest_metadata,
                    'size_bytes': len(binary_data),
                    'source': 'VRS sample.vrs file'
                })
            elif format_type == 'info':
                return Response({
                    'frame_id': frame_id,
                    'metadata': latest_metadata,
                    'size_bytes': len(binary_data),
                    'source': 'VRS sample.vrs RGB camera stream (214-1)',
                    'image_url': f'/api/v1/aria/simple-image/?format=raw',
                    'base64_url': f'/api/v1/aria/simple-image/?format=base64'
                })
            else:  # raw format - 실제 이미지 파일
                response = HttpResponse(binary_data, content_type='image/jpeg')
                response['Content-Length'] = len(binary_data)
                response['X-Frame-ID'] = frame_id
                response['X-VRS-Source'] = 'sample.vrs RGB stream'
                response['Content-Disposition'] = f'inline; filename="{frame_id}.jpg"'
                return response
                
        except Exception as e:
            return Response({
                'error': f'Failed to get VRS image: {str(e)}',
                'suggestion': 'Make sure Kafka is running and has VRS image data'
            }, status=500)


class QuickImageGenerator(APIView):
    """빠른 VRS 이미지 생성기"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """VRS에서 새 이미지를 빠르게 생성"""
        try:
            from common.kafka.binary_producer import BinaryKafkaProducer
            
            producer = BinaryKafkaProducer()
            result = producer.send_test_binary_frame('vrs-quick-image')
            producer.close()
            
            if result['success']:
                return Response({
                    'success': True,
                    'message': 'VRS 이미지 생성 완료!',
                    'frame_id': result['frame_id'],
                    'source': 'VRS sample.vrs RGB camera',
                    'view_urls': {
                        'image': '/api/v1/aria/simple-image/?format=raw',
                        'base64': '/api/v1/aria/simple-image/?format=base64', 
                        'info': '/api/v1/aria/simple-image/?format=info'
                    },
                    'metadata': result['metadata']
                })
            else:
                return Response({
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }, status=500)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=500)


class DirectImageView(APIView):
    """직접 이미지 보기 - 가장 간단한 방법"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Kafka에서 최신 이미지를 가져와서 바로 표시"""
        try:
            import os
            from kafka import KafkaConsumer
            import json
            
            # Kafka 설정
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
            
            # 바이너리 토픽에서 모든 이미지를 읽어서 가장 최신 것 선택  
            consumer = KafkaConsumer(
                'vrs-binary-stream',
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=3000,  # 3초 기다림
                auto_offset_reset='earliest',  # 처음부터 읽기
                enable_auto_commit=False,
                max_poll_records=50  # 최대 50개 확인
            )
            
            # 모든 이미지를 수집해서 가장 최신 것 선택
            all_images = []
            
            logger.info(f"Collecting all images from Kafka...")
            
            for message in consumer:
                if message.value and len(message.value) > 1000:  # 이미지 크기 확인
                    key = message.key.decode('utf-8') if message.key else 'unknown'
                    all_images.append({
                        'key': key,
                        'data': message.value,
                        'timestamp': message.timestamp,
                        'offset': message.offset
                    })
                    logger.info(f"Found image: {key}, size: {len(message.value)} bytes, offset: {message.offset}")
            
            # 가장 최신 이미지 선택 (가장 높은 offset)
            latest_image = None
            latest_key = None
            
            if all_images:
                # offset이 가장 높은 것이 가장 최신
                latest_msg = max(all_images, key=lambda x: x['offset'])
                latest_image = latest_msg['data']
                latest_key = latest_msg['key']
                logger.info(f"Selected latest image: {latest_key}, size: {len(latest_image)} bytes")
            
            consumer.close()
            
            if latest_image:
                # 이미지 반환
                response = HttpResponse(latest_image, content_type='image/jpeg')
                response['Content-Length'] = len(latest_image)
                response['X-Frame-ID'] = latest_key
                response['Content-Disposition'] = f'inline; filename="{latest_key}.jpg"'
                response['Cache-Control'] = 'no-cache'
                logger.info(f"Serving image: {latest_key}, {len(latest_image)} bytes")
                return response
            else:
                # 이미지가 없으면 테스트 이미지 생성하고 반환
                logger.warning("No image found in Kafka, generating test image...")
                return self._generate_and_serve_test_image()
                
        except Exception as e:
            logger.error(f"Direct image view failed: {e}")
            return Response({
                'error': f'Failed to get image: {str(e)}',
                'suggestion': 'Make sure Kafka is running with binary data'
            }, status=500)
    
    def _generate_and_serve_test_image(self):
        """테스트 이미지 생성 후 바로 반환"""
        try:
            from common.kafka.binary_producer import BinaryKafkaProducer
            
            # 테스트 이미지 생성
            producer = BinaryKafkaProducer()
            result = producer.send_test_binary_frame('direct-test-session')
            producer.close()
            
            if result['success'] and 'binary_data' in result:
                binary_data = result['binary_data']
                frame_id = result['frame_id']
                
                response = HttpResponse(binary_data, content_type='image/jpeg')
                response['Content-Length'] = len(binary_data)
                response['X-Frame-ID'] = frame_id
                response['Content-Disposition'] = f'inline; filename="{frame_id}.jpg"'
                response['X-Generated'] = 'true'
                
                logger.info(f"Generated and serving test image: {frame_id}, {len(binary_data)} bytes")
                return response
            else:
                return Response({
                    'error': 'Failed to generate test image',
                    'details': result
                }, status=500)
                
        except Exception as e:
            logger.error(f"Test image generation failed: {e}")
            return Response({
                'error': f'Test image generation failed: {str(e)}'
            }, status=500)


class ImageMetadataListView(APIView):
    """이미지 메타데이터 목록 - 클릭하면 이미지 보기"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Kafka에서 모든 이미지 메타데이터 목록 가져오기"""
        try:
            import os
            from kafka import KafkaConsumer
            import json
            from datetime import datetime
            
            # Kafka 설정
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
            
            # 메타데이터 토픽에서 모든 이미지 정보 가져오기
            consumer = KafkaConsumer(
                'vrs-metadata-stream',
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=3000,
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            metadata_list = []
            
            for message in consumer:
                metadata = message.value
                if metadata.get('data_type') == 'vrs_frame_binary':
                    # 타임스탬프를 읽기 쉽게 변환
                    try:
                        timestamp_iso = metadata.get('timestamp', '')
                        if timestamp_iso:
                            dt = datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
                            readable_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            readable_time = 'Unknown'
                    except:
                        readable_time = 'Invalid'
                    
                    metadata_item = {
                        'frame_id': metadata.get('frame_id'),
                        'session_id': metadata.get('session_id'),
                        'stream_id': metadata.get('stream_id'),
                        'frame_index': metadata.get('frame_index'),
                        'image_size': f"{metadata.get('image_width', 0)}x{metadata.get('image_height', 0)}",
                        'timestamp': readable_time,
                        'compressed_size': metadata.get('compression', {}).get('compressed_size', 0),
                        'compression_ratio': round(metadata.get('compression', {}).get('compression_ratio', 0), 3),
                        'image_url': f'/api/v1/aria/image-by-id/{metadata.get("frame_id")}/',
                        'is_real_vrs': 'real-vrs-session' in metadata.get('session_id', ''),
                        'capture_timestamp_ns': metadata.get('capture_timestamp_ns')
                    }
                    metadata_list.append(metadata_item)
            
            consumer.close()
            
            # 타임스탬프 순으로 정렬 (최신 먼저)
            metadata_list.sort(key=lambda x: x.get('capture_timestamp_ns', 0), reverse=True)
            
            return Response({
                'success': True,
                'total_images': len(metadata_list),
                'images': metadata_list,
                'instructions': {
                    'how_to_view': 'Click on image_url to view the actual image',
                    'real_vrs_data': 'Items with is_real_vrs=true are from actual VRS sample.vrs file',
                    'test_data': 'Items with is_real_vrs=false are generated test images'
                }
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to get metadata: {str(e)}',
                'suggestion': 'Make sure Kafka is running with metadata'
            }, status=500)


class ImageByIdView(APIView):
    """특정 Frame ID로 이미지 가져오기"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, frame_id):
        """Frame ID로 특정 이미지 반환"""
        try:
            import os
            from kafka import KafkaConsumer
            
            # Kafka 설정
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
            
            # 바이너리 토픽에서 해당 Frame ID 찾기
            consumer = KafkaConsumer(
                'vrs-binary-stream',
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=5000,
                auto_offset_reset='earliest',
                enable_auto_commit=False
            )
            
            target_image = None
            
            logger.info(f"Looking for image with frame_id: {frame_id}")
            
            for message in consumer:
                if message.key and message.key.decode('utf-8') == frame_id:
                    if message.value and len(message.value) > 1000:
                        target_image = message.value
                        logger.info(f"Found target image: {frame_id}, size: {len(target_image)} bytes")
                        break
            
            consumer.close()
            
            if target_image:
                response = HttpResponse(target_image, content_type='image/jpeg')
                response['Content-Length'] = len(target_image)
                response['X-Frame-ID'] = frame_id
                response['Content-Disposition'] = f'inline; filename="{frame_id}.jpg"'
                response['Cache-Control'] = 'no-cache'
                return response
            else:
                return Response({
                    'error': f'Image not found for frame_id: {frame_id}',
                    'suggestion': 'Check if the frame_id exists in the image list'
                }, status=404)
                
        except Exception as e:
            logger.error(f"Image by ID view failed: {e}")
            return Response({
                'error': f'Failed to get image: {str(e)}'
            }, status=500)