"""
Kafka 스트리밍 Django Views - 체계적인 URL 구조
"""
import os
import time
from typing import Dict, List, Optional, Any
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
import json
import base64
import logging

from ..managers.stream_manager import get_global_manager, AriaStreamManager
from ..consumers.streaming_consumer import get_global_consumer

logger = logging.getLogger(__name__)

# VRS 파일 경로 자동 감지
def get_vrs_file_path():
    """VRS 파일 경로 자동 감지"""
    possible_paths = [
        'data/mps_samples/sample.vrs',
        'ARD/data/mps_samples/sample.vrs',
        '../data/mps_samples/sample.vrs',
        os.path.join(settings.BASE_DIR, 'data', 'mps_samples', 'sample.vrs'),
        os.path.join(settings.BASE_DIR, 'aria_sessions', 'data', 'sample.vrs')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    logger.warning("VRS 파일을 찾을 수 없습니다")
    return None

# 전역 매니저 초기화
STREAM_MANAGER = get_global_manager(get_vrs_file_path())

class BaseKafkaView(View):
    """기본 Kafka View 클래스"""
    
    def dispatch(self, request, *args, **kwargs):
        """공통 헤더 설정"""
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(response, '__setitem__'):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With'
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    
    def options(self, request, *args, **kwargs):
        """CORS preflight 처리"""
        return HttpResponse()

@method_decorator(csrf_exempt, name='dispatch')
class ImageStreamView(BaseKafkaView):
    """이미지 스트림 API"""
    
    def get(self, request, stream_name, action='latest', count=1):
        """
        이미지 스트림 데이터 조회
        
        URL: /api/v2/kafka-streams/images/{stream_name}/latest/
        URL: /api/v2/kafka-streams/images/{stream_name}/recent/{count}/
        """
        try:
            # 지원되는 이미지 스트림 확인
            image_streams = STREAM_MANAGER.get_image_streams()
            if stream_name not in image_streams:
                return JsonResponse({
                    'error': f'지원하지 않는 이미지 스트림: {stream_name}',
                    'supported_streams': image_streams
                }, status=400)
            
            if action == 'latest':
                # 최신 이미지 데이터
                data = STREAM_MANAGER.get_latest_data(stream_name)
                if not data:
                    return JsonResponse({
                        'stream_name': stream_name,
                        'data': None,
                        'message': 'No data available'
                    }, status=204)
                
                return JsonResponse({
                    'stream_name': stream_name,
                    'data': data,
                    'timestamp': time.time()
                })
            
            elif action == 'recent':
                # 최근 N개 이미지 데이터
                count = int(count)
                if count > 100:  # 최대 100개 제한
                    count = 100
                
                data_list = STREAM_MANAGER.get_recent_data(stream_name, count)
                
                return JsonResponse({
                    'stream_name': stream_name,
                    'data': data_list,
                    'count': len(data_list),
                    'requested_count': count,
                    'timestamp': time.time()
                })
            
            else:
                return JsonResponse({
                    'error': f'지원하지 않는 액션: {action}',
                    'supported_actions': ['latest', 'recent']
                }, status=400)
            
        except Exception as e:
            logger.error(f"이미지 스트림 오류 ({stream_name}): {e}")
            return JsonResponse({
                'error': str(e),
                'stream_name': stream_name
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ImageFrameView(BaseKafkaView):
    """이미지 프레임 직접 반환 (JPEG)"""
    
    def get(self, request, stream_name):
        """
        이미지 프레임 직접 반환
        
        URL: /api/v2/kafka-streams/images/{stream_name}/frame/
        """
        try:
            image_streams = STREAM_MANAGER.get_image_streams()
            if stream_name not in image_streams:
                return HttpResponse('Unsupported image stream', status=400)
            
            # 최신 이미지 데이터 가져오기
            data = STREAM_MANAGER.get_latest_data(stream_name)
            if not data or not data.get('data', {}).get('data', {}).get('image_base64'):
                return HttpResponse(status=204)  # No Content
            
            # Base64 이미지 디코딩
            image_base64 = data['data']['data']['image_base64']
            image_bytes = base64.b64decode(image_base64)
            
            # JPEG 이미지로 반환
            response = HttpResponse(image_bytes, content_type='image/jpeg')
            response['Cache-Control'] = 'no-cache'
            response['X-Stream-Name'] = stream_name
            response['X-Timestamp'] = str(data.get('timestamp', 0))
            response['X-Frame-Shape'] = ','.join(map(str, data['data']['data'].get('shape', [])))
            
            return response
            
        except Exception as e:
            logger.error(f"이미지 프레임 오류 ({stream_name}): {e}")
            return HttpResponse(f'Frame error: {str(e)}', status=500)

@method_decorator(csrf_exempt, name='dispatch')
class SensorStreamView(BaseKafkaView):
    """센서 스트림 API"""
    
    def get(self, request, stream_name, action='latest', count=1):
        """
        센서 스트림 데이터 조회
        
        URL: /api/v2/kafka-streams/sensors/{stream_name}/latest/
        URL: /api/v2/kafka-streams/sensors/{stream_name}/recent/{count}/
        """
        try:
            # 지원되는 센서 스트림 확인
            sensor_streams = STREAM_MANAGER.get_sensor_streams()
            if stream_name not in sensor_streams:
                return JsonResponse({
                    'error': f'지원하지 않는 센서 스트림: {stream_name}',
                    'supported_streams': sensor_streams
                }, status=400)
            
            if action == 'latest':
                # 최신 센서 데이터
                data = STREAM_MANAGER.get_latest_data(stream_name)
                if not data:
                    return JsonResponse({
                        'stream_name': stream_name,
                        'data': None,
                        'message': 'No data available'
                    }, status=204)
                
                return JsonResponse({
                    'stream_name': stream_name,
                    'data': data,
                    'timestamp': time.time()
                })
            
            elif action == 'recent':
                # 최근 N개 센서 데이터
                count = int(count)
                if count > 100:  # 최대 100개 제한
                    count = 100
                
                data_list = STREAM_MANAGER.get_recent_data(stream_name, count)
                
                return JsonResponse({
                    'stream_name': stream_name,
                    'data': data_list,
                    'count': len(data_list),
                    'requested_count': count,
                    'timestamp': time.time()
                })
            
            else:
                return JsonResponse({
                    'error': f'지원하지 않는 액션: {action}',
                    'supported_actions': ['latest', 'recent']
                }, status=400)
            
        except Exception as e:
            logger.error(f"센서 스트림 오류 ({stream_name}): {e}")
            return JsonResponse({
                'error': str(e),
                'stream_name': stream_name
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class StreamControlView(BaseKafkaView):
    """스트림 제어 API"""
    
    def post(self, request, action, stream_name=None):
        """
        스트림 제어
        
        URL: /api/v2/kafka-streams/control/producer/start/{stream_name}/
        URL: /api/v2/kafka-streams/control/producer/stop/{stream_name}/
        URL: /api/v2/kafka-streams/control/producer/start-all/
        URL: /api/v2/kafka-streams/control/producer/stop-all/
        """
        try:
            # 요청 데이터 파싱
            try:
                data = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                data = {}
            
            fps = float(data.get('fps', 10.0))
            duration = data.get('duration')  # None 또는 초 단위
            
            if action == 'start' and stream_name:
                # 개별 스트림 시작
                success = STREAM_MANAGER.start_producer_stream(stream_name, fps, duration)
                
                return JsonResponse({
                    'action': 'start',
                    'stream_name': stream_name,
                    'success': success,
                    'fps': fps,
                    'duration': duration,
                    'message': f'Stream {"started" if success else "failed to start"}'
                })
            
            elif action == 'stop' and stream_name:
                # 개별 스트림 중지
                success = STREAM_MANAGER.stop_producer_stream(stream_name)
                
                return JsonResponse({
                    'action': 'stop',
                    'stream_name': stream_name,
                    'success': success,
                    'message': f'Stream {"stopped" if success else "failed to stop"}'
                })
            
            elif action == 'start-all':
                # 모든 스트림 시작
                results = STREAM_MANAGER.start_all_streams(fps)
                
                return JsonResponse({
                    'action': 'start-all',
                    'results': results,
                    'fps': fps,
                    'duration': duration,
                    'total_streams': len(results),
                    'successful_streams': sum(results.values())
                })
            
            elif action == 'stop-all':
                # 모든 스트림 중지
                results = STREAM_MANAGER.stop_all_streams()
                
                return JsonResponse({
                    'action': 'stop-all',
                    'results': results,
                    'total_streams': len(results),
                    'successful_streams': sum(results.values())
                })
            
            else:
                return JsonResponse({
                    'error': f'지원하지 않는 액션: {action}',
                    'supported_actions': ['start', 'stop', 'start-all', 'stop-all']
                }, status=400)
            
        except Exception as e:
            logger.error(f"스트림 제어 오류 ({action}): {e}")
            return JsonResponse({
                'error': str(e),
                'action': action,
                'stream_name': stream_name
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class UnifiedStreamView(BaseKafkaView):
    """통합 스트림 API"""
    
    def get(self, request, mode='realtime'):
        """
        통합 스트림 데이터 조회
        
        URL: /api/v2/kafka-streams/unified/realtime/
        URL: /api/v2/kafka-streams/unified/batch/{count}/
        """
        try:
            if mode == 'realtime':
                # 실시간 통합 데이터 (모든 스트림의 최신 데이터)
                all_streams = STREAM_MANAGER.supported_streams.keys()
                
                unified_data = {
                    'images': {},
                    'sensors': {},
                    'timestamp': time.time(),
                    'total_streams': len(all_streams)
                }
                
                for stream_name in all_streams:
                    stream_info = STREAM_MANAGER.get_stream_info(stream_name)
                    latest_data = STREAM_MANAGER.get_latest_data(stream_name)
                    
                    stream_data = {
                        'data': latest_data,
                        'status': stream_info.status,
                        'last_update': stream_info.last_update
                    }
                    
                    if stream_info.type == 'image':
                        unified_data['images'][stream_name] = stream_data
                    else:
                        unified_data['sensors'][stream_name] = stream_data
                
                return JsonResponse(unified_data)
            
            elif mode.startswith('batch'):
                # 배치 데이터 (최근 N개)
                count = int(request.GET.get('count', 10))
                if count > 100:
                    count = 100
                
                all_streams = STREAM_MANAGER.supported_streams.keys()
                
                batch_data = {
                    'images': {},
                    'sensors': {},
                    'count': count,
                    'timestamp': time.time()
                }
                
                for stream_name in all_streams:
                    stream_info = STREAM_MANAGER.get_stream_info(stream_name)
                    recent_data = STREAM_MANAGER.get_recent_data(stream_name, count)
                    
                    stream_data = {
                        'data': recent_data,
                        'status': stream_info.status,
                        'actual_count': len(recent_data)
                    }
                    
                    if stream_info.type == 'image':
                        batch_data['images'][stream_name] = stream_data
                    else:
                        batch_data['sensors'][stream_name] = stream_data
                
                return JsonResponse(batch_data)
            
            else:
                return JsonResponse({
                    'error': f'지원하지 않는 모드: {mode}',
                    'supported_modes': ['realtime', 'batch']
                }, status=400)
            
        except Exception as e:
            logger.error(f"통합 스트림 오류 ({mode}): {e}")
            return JsonResponse({
                'error': str(e),
                'mode': mode
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class AdminView(BaseKafkaView):
    """관리자 API"""
    
    def get(self, request, info_type='status'):
        """
        관리자 정보 조회
        
        URL: /api/v2/kafka-streams/admin/status/
        URL: /api/v2/kafka-streams/admin/stats/
        URL: /api/v2/kafka-streams/admin/health/
        URL: /api/v2/kafka-streams/admin/streams/
        """
        try:
            if info_type == 'status':
                # 전체 상태
                all_streams_info = STREAM_MANAGER.get_all_streams_info()
                
                return JsonResponse({
                    'streams': {
                        name: {
                            'name': info.name,
                            'type': info.type,
                            'status': info.status,
                            'producer_active': info.producer_active,
                            'consumer_active': info.consumer_active,
                            'message_count': info.message_count,
                            'last_update': info.last_update
                        }
                        for name, info in all_streams_info.items()
                    },
                    'summary': {
                        'total_streams': len(all_streams_info),
                        'active_streams': len([info for info in all_streams_info.values() if info.status == 'active']),
                        'image_streams': len(STREAM_MANAGER.get_image_streams()),
                        'sensor_streams': len(STREAM_MANAGER.get_sensor_streams())
                    },
                    'timestamp': time.time()
                })
            
            elif info_type == 'stats':
                # 시스템 통계
                return JsonResponse({
                    'system_stats': STREAM_MANAGER.get_system_stats(),
                    'timestamp': time.time()
                })
            
            elif info_type == 'health':
                # 헬스 체크
                return JsonResponse(STREAM_MANAGER.health_check())
            
            elif info_type == 'streams':
                # 스트림 목록
                return JsonResponse({
                    'supported_streams': {
                        'images': STREAM_MANAGER.get_image_streams(),
                        'sensors': STREAM_MANAGER.get_sensor_streams(),
                        'all': list(STREAM_MANAGER.supported_streams.keys())
                    },
                    'stream_details': {
                        name: {
                            'type': details['type'],
                            'priority': details['priority'],
                            'sample_rate': details['sample_rate']
                        }
                        for name, details in STREAM_MANAGER.supported_streams.items()
                    },
                    'timestamp': time.time()
                })
            
            else:
                return JsonResponse({
                    'error': f'지원하지 않는 정보 타입: {info_type}',
                    'supported_types': ['status', 'stats', 'health', 'streams']
                }, status=400)
            
        except Exception as e:
            logger.error(f"관리자 API 오류 ({info_type}): {e}")
            return JsonResponse({
                'error': str(e),
                'info_type': info_type
            }, status=500)