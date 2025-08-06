"""
VRS Kafka 스트리밍 REST API Views
Observer 패턴과 공식 문서 패턴을 따른 깔끔한 API 구조
"""
import asyncio
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.http import JsonResponse
from django.utils import timezone
from asgiref.sync import sync_to_async
from .models import AriaStreamingSession
from .serializers import AriaStreamingSessionSerializer
from .vrs_kafka_integration import VRSKafkaStreamingService
import logging

logger = logging.getLogger(__name__)

# Global streaming services registry
ACTIVE_STREAMING_SERVICES = {}


class VRSKafkaStreamingViewSet(viewsets.ModelViewSet):
    """VRS Kafka 스트리밍 API ViewSet"""
    
    queryset = AriaStreamingSession.objects.all()
    serializer_class = AriaStreamingSessionSerializer
    lookup_field = 'session_id'
    
    @action(detail=True, methods=['post'], url_path='kafka-start')
    async def start_kafka_streaming(self, request, session_id=None):
        """VRS Kafka 스트리밍 시작"""
        try:
            session = await sync_to_async(self.get_object)()
            
            # Check if already streaming
            if session_id in ACTIVE_STREAMING_SERVICES:
                return Response({
                    'error': 'Streaming already active for this session',
                    'session_id': session_id
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get streaming configuration from request
            stream_config = {
                'active_streams': request.data.get('active_streams', [
                    'camera-rgb', 'camera-slam-left', 'camera-slam-right',
                    'imu-right', 'imu-left', 'magnetometer', 'barometer'
                ]),
                'max_frames': request.data.get('max_frames', 1000),
                'include_images': request.data.get('include_images', True)
            }
            
            # Create streaming service
            streaming_service = VRSKafkaStreamingService(
                session_id=str(session.session_id),
                vrs_file_path=session.vrs_file_path
            )
            
            # Start streaming
            success = await streaming_service.start_streaming(stream_config)
            
            if success:
                ACTIVE_STREAMING_SERVICES[session_id] = streaming_service
                
                # Update session status
                session.status = 'STREAMING'
                await sync_to_async(session.save)()
                
                return Response({
                    'message': 'VRS Kafka streaming started successfully',
                    'session_id': session_id,
                    'stream_config': stream_config,
                    'streaming_status': streaming_service.get_streaming_status()
                })
            else:
                return Response({
                    'error': 'Failed to start VRS streaming',
                    'session_id': session_id
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error starting Kafka streaming: {e}")
            return Response({
                'error': str(e),
                'session_id': session_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='kafka-stop')
    async def stop_kafka_streaming(self, request, session_id=None):
        """VRS Kafka 스트리밍 중지"""
        try:
            streaming_service = ACTIVE_STREAMING_SERVICES.get(session_id)
            
            if not streaming_service:
                return Response({
                    'error': 'No active streaming for this session',
                    'session_id': session_id
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Stop streaming
            final_stats = await streaming_service.stop_streaming()
            
            # Remove from active services
            del ACTIVE_STREAMING_SERVICES[session_id]
            
            # Update session status
            session = await sync_to_async(self.get_object)()
            session.status = 'COMPLETED'
            await sync_to_async(session.save)()
            
            return Response({
                'message': 'VRS Kafka streaming stopped successfully',
                'session_id': session_id,
                'final_stats': final_stats
            })
            
        except Exception as e:
            logger.error(f"Error stopping Kafka streaming: {e}")
            return Response({
                'error': str(e),
                'session_id': session_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='kafka-status')
    async def get_kafka_streaming_status(self, request, session_id=None):
        """VRS Kafka 스트리밍 상태 조회"""
        try:
            streaming_service = ACTIVE_STREAMING_SERVICES.get(session_id)
            
            if streaming_service:
                # Active streaming
                status_data = streaming_service.get_streaming_status()
                health_data = await streaming_service.get_health_status()
                
                return Response({
                    'session_id': session_id,
                    'active': True,
                    'streaming_status': status_data,
                    'health_status': health_data
                })
            else:
                # No active streaming
                return Response({
                    'session_id': session_id,
                    'active': False,
                    'message': 'No active streaming for this session'
                })
                
        except Exception as e:
            logger.error(f"Error getting streaming status: {e}")
            return Response({
                'error': str(e),
                'session_id': session_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='kafka-health')
    async def kafka_health_check(self, request):
        """전체 Kafka 시스템 건강 상태 확인"""
        try:
            active_sessions = list(ACTIVE_STREAMING_SERVICES.keys())
            health_reports = {}
            
            for session_id, service in ACTIVE_STREAMING_SERVICES.items():
                try:
                    health_data = await service.get_health_status()
                    health_reports[session_id] = health_data
                except Exception as e:
                    health_reports[session_id] = {
                        'error': str(e),
                        'status': 'error'
                    }
            
            return Response({
                'kafka_system_status': 'healthy' if active_sessions else 'idle',
                'active_sessions_count': len(active_sessions),
                'active_sessions': active_sessions,
                'health_reports': health_reports,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error in Kafka health check: {e}")
            return Response({
                'kafka_system_status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
def streaming_test_endpoint(request):
    """
    테스트 엔드포인트: http://127.0.0.1:8000/api/v1/aria-sessions/streaming-test/
    GET: 스트리밍 상태 확인
    POST: 테스트 스트리밍 실행
    """
    try:
        if request.method == 'GET':
            # 현재 상태 확인
            active_sessions = list(ACTIVE_STREAMING_SERVICES.keys())
            
            return JsonResponse({
                'status': 'success',
                'message': 'VRS Kafka streaming test endpoint',
                'active_streaming_sessions': active_sessions,
                'active_count': len(active_sessions),
                'timestamp': timezone.now().isoformat(),
                'endpoints': {
                    'start_test': 'POST /api/v1/aria-sessions/streaming-test/',
                    'session_start': 'POST /api/v1/aria-sessions/sessions/{session_id}/kafka-start/',
                    'session_stop': 'POST /api/v1/aria-sessions/sessions/{session_id}/kafka-stop/',
                    'session_status': 'GET /api/v1/aria-sessions/sessions/{session_id}/kafka-status/',
                    'health_check': 'GET /api/v1/aria-sessions/sessions/kafka-health/'
                }
            })
        
        elif request.method == 'POST':
            # 테스트 스트리밍 실행
            
            # 기본 세션 찾기 또는 생성
            try:
                session = AriaStreamingSession.objects.filter(
                    vrs_file_path__contains='sample.vrs'
                ).first()
                
                if not session:
                    # 테스트용 세션 생성
                    session = AriaStreamingSession.objects.create(
                        vrs_file_path='ARD/aria_sessions/data/sample.vrs',
                        status='READY'
                    )
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'error': f'Session error: {str(e)}',
                    'timestamp': timezone.now().isoformat()
                }, status=500)
            
            session_id = str(session.session_id)
            
            # 이미 스트리밍 중인지 확인
            if session_id in ACTIVE_STREAMING_SERVICES:
                existing_service = ACTIVE_STREAMING_SERVICES[session_id]
                status_data = existing_service.get_streaming_status()
                
                return JsonResponse({
                    'message': 'Test streaming already active',
                    'session_id': session_id,
                    'streaming_status': status_data
                })
            
            # 간단한 테스트 응답 (async 제거)
            return JsonResponse({
                'status': 'success',
                'message': 'Test VRS Kafka streaming endpoint - async functionality needs setup',
                'session_id': session_id,
                'note': 'Full async streaming requires proper ASGI setup',
                'available_endpoints': {
                    'session_detail': f'/api/v1/aria-sessions/kafka/sessions/{session_id}/',
                    'basic_streaming': f'/api/v1/aria-sessions/simple/{session_id}/start_streaming/'
                }
            })
        
    except Exception as e:
        logger.error(f"Error in streaming test endpoint: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)


@api_view(['GET'])
def kafka_topics_info(request):
    """Kafka 토픽 정보 조회"""
    try:
        import sys
        import os
        # Add ARD directory to path
        ard_path = os.path.dirname(os.path.dirname(__file__))
        if ard_path not in sys.path:
            sys.path.append(ard_path)
        from common.kafka.vrs_kafka_producer import VRSKafkaProducer
        
        producer = VRSKafkaProducer()
        topics = producer.get_vrs_topics()
        stream_mappings = producer.get_stream_id_mappings()
        
        return JsonResponse({
            'kafka_topics': topics,
            'stream_id_mappings': stream_mappings,
            'topics_count': len(topics),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting Kafka topics info: {e}")
        return JsonResponse({
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)