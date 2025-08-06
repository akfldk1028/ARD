"""
간단한 빠른 API - general_views를 그대로 복사
"""
from django.http import JsonResponse
from rest_framework.decorators import api_view
from .models import AriaStreamingSession
from .streaming_service import AriaUnifiedStreaming
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
def simple_fast_unified_stream(request):
    """general_unified_stream_realtime을 그대로 복사 - 작동 보장"""
    try:
        # 첫 번째 available 세션 사용
        session = AriaStreamingSession.objects.filter(status='READY').first()
        if not session:
            return JsonResponse({'error': 'No available sessions'}, status=404)
        
        # 모든 스트림 타입 포함 (12개 센서 모두)
        all_streams = [
            'camera-rgb', 'camera-slam-left', 'camera-slam-right', 'camera-eyetracking',
            'imu-right', 'imu-left', 'magnetometer', 'barometer', 'microphone',
            'gps', 'wps', 'bluetooth'
        ]
        
        sample_idx = int(request.GET.get('sample', 0))
        max_samples = int(request.GET.get('max_samples', 20))
        include_images = request.GET.get('include_images', 'true').lower() == 'true'
        
        # 통합 스트리밍 사용
        streaming = AriaUnifiedStreaming()
        streaming.vrsfile = session.vrs_file_path
        streaming.create_data_provider()
        
        # 균형있는 데이터 수집 사용 (이미지와 센서 데이터 모두 보장)
        if include_images:
            # 이미지 포함시: 균형있는 샘플링 사용
            results = streaming.get_balanced_stream_data(
                max_images=4,  # 4개 카메라에서 각각 1개씩
                max_sensors=max_samples - 4,  # 나머지를 센서로
                start_offset=sample_idx
            )
        else:
            # 센서만: 기존 방식 사용
            results = streaming.process_unified_stream(
                active_streams=all_streams,
                max_count=max_samples,
                include_images=False,
                start_frame=sample_idx
            )
        
        # 결과를 이미지와 센서 데이터로 분리
        images = []
        sensors = []
        
        for result in results:
            if result.get('has_image_data'):
                # 이미지 데이터는 base64 제외하고 메타데이터만
                image_info = {
                    'stream_label': result['stream_label'],
                    'sensor_type': result['sensor_type'],
                    'device_timestamp_ns': result['device_timestamp_ns'],
                    'image_shape': result.get('image_shape'),
                    'sequence': result['sequence'],
                    'data_source': 'simple_fast'  # 유일한 차이점
                }
                if include_images and 'image_data_base64' in result:
                    image_info['image_base64'] = result['image_data_base64']
                images.append(image_info)
                
            elif result.get('has_sensor_data'):
                # 센서 데이터
                sensor_info = {
                    'stream_label': result['stream_label'],
                    'sensor_type': result['sensor_type'],
                    'device_timestamp_ns': result['device_timestamp_ns'],
                    'sequence': result['sequence'],
                    'data_source': 'simple_fast'  # 유일한 차이점
                }
                
                # 센서별 실제 데이터 추가
                for key in ['imu_data', 'magnetometer_data', 'barometer_data', 'audio_data', 'gps_data', 'wps_data', 'bluetooth_data']:
                    if key in result:
                        sensor_info[key.replace('_data', '')] = result[key]
                
                sensors.append(sensor_info)
        
        return JsonResponse({
            'session_id': str(session.session_id),
            'unified_data': {
                'images': images,
                'sensors': sensors
            },
            'stats': {
                'total_items': len(results),
                'image_count': len(images),
                'sensor_count': len(sensors)
            },
            'sample_start': sample_idx,
            'include_images': include_images,
            'api_type': 'simple_fast'
        })
            
    except Exception as e:
        import traceback
        error_detail = {
            'error': f'Simple fast error: {str(e)}',
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"DEBUG: Simple fast error: {error_detail}")
        return JsonResponse(error_detail, status=500)