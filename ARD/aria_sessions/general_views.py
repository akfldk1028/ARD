from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from .models import AriaStreamingSession
from .streaming_service import AriaUnifiedStreaming
import base64

def streaming_test_page(request):
    """일반 스트리밍 테스트 페이지 (세션 ID 없이 접근)"""
    return render(request, 'aria_sessions/streaming_test_v6.html', {
        'session_id': None  # 자동으로 세션 목록을 로드함
    })

def general_streaming_sensor(request):
    """일반 센서 데이터 스트리밍 (세션 자동 선택)"""
    try:
        # 첫 번째 available 세션 사용
        session = AriaStreamingSession.objects.filter(status='READY').first()
        if not session:
            return JsonResponse({'error': 'No available sessions'}, status=404)
        
        # 센서 타입들 (12개 센서 모두 지원)
        sensor_types = request.GET.get('sensors', 'imu-right,imu-left,magnetometer,barometer,microphone,gps,wps,bluetooth').split(',')
        sample_idx = int(request.GET.get('sample', 0))
        max_samples = int(request.GET.get('max_samples', 10))
        
        # 통합 스트리밍 사용
        streaming = AriaUnifiedStreaming()
        streaming.vrsfile = session.vrs_file_path
        streaming.create_data_provider()
        
        # 센서 데이터 처리 (이미지 제외)
        results = streaming.process_unified_stream(
            active_streams=sensor_types,
            max_count=max_samples,
            include_images=False,  # 센서 데이터만
            start_frame=sample_idx
        )
        
        # 센서 데이터만 필터링
        sensor_results = []
        for result in results:
            if result.get('has_sensor_data'):
                # 센서별 데이터 구조화
                sensor_data = {
                    'stream_label': result['stream_label'],
                    'sensor_type': result['sensor_type'],
                    'device_timestamp_ns': result['device_timestamp_ns'],
                    'sequence': result['sequence']
                }
                
                # 센서 타입별 데이터 추가
                if 'imu_data' in result:
                    sensor_data['imu'] = result['imu_data']
                if 'magnetometer_data' in result:
                    sensor_data['magnetometer'] = result['magnetometer_data']
                if 'barometer_data' in result:
                    sensor_data['barometer'] = result['barometer_data']
                if 'audio_data' in result:
                    sensor_data['audio'] = result['audio_data']
                if 'gps_data' in result:
                    sensor_data['gps'] = result['gps_data']
                if 'wps_data' in result:
                    sensor_data['wps'] = result['wps_data']
                if 'bluetooth_data' in result:
                    sensor_data['bluetooth'] = result['bluetooth_data']
                
                sensor_results.append(sensor_data)
        
        return JsonResponse({
            'session_id': str(session.session_id),
            'sensor_data': sensor_results,
            'total_samples': len(sensor_results),
            'sample_start': sample_idx,
            'requested_sensors': sensor_types
        })
            
    except Exception as e:
        import traceback
        error_detail = {
            'error': f'Sensor error: {str(e)}',
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"DEBUG: Sensor error: {error_detail}")  # 로그에 상세 에러 출력
        return JsonResponse(error_detail, status=500)

def general_unified_stream_realtime(request):
    """일반 통합 스트리밍 - 동시 4카메라 방식으로 리다이렉트"""
    try:
        # 동시 스트리밍 방식으로 전환 안내
        return JsonResponse({
            'message': '🔥 동시 4카메라 스트리밍으로 업그레이드됨',
            'new_endpoint': '/api/v1/aria-sessions/concurrent-multi-frames/',
            'page_url': '/api/v1/aria-sessions/concurrent-streaming-page/',
            'upgrade_info': {
                'old_method': 'VRS 직접 읽기 (느림)',
                'new_method': '공식 Observer 패턴 + deliver_queued_sensor_data (빠름)',
                'performance_gain': '10-100배 성능 향상',
                'concurrent_cameras': 4,
                'supported_cameras': ['rgb', 'slam-left', 'slam-right', 'eye-tracking']
            }
        })
        
    except Exception as e:
        import traceback
        error_detail = {
            'error': f'Unified stream error: {str(e)}',
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"DEBUG: Unified stream error: {error_detail}")
        return JsonResponse(error_detail, status=500)

def general_streaming_frame(request):
    """일반 스트리밍 프레임 (이미지만, 세션 자동 선택)"""
    try:
        # 첫 번째 available 세션 사용
        session = AriaStreamingSession.objects.filter(status='READY').first()
        if not session:
            return HttpResponse('No available sessions', status=404)
        
        # 스트림 타입들
        stream_types = request.GET.get('streams', 'camera-rgb').split(',')
        frame_idx = int(request.GET.get('frame', 0))
        
        # 통합 스트리밍 사용
        streaming = AriaUnifiedStreaming()
        streaming.vrsfile = session.vrs_file_path
        streaming.create_data_provider()
        
        # 프레임 인덱스 기반으로 특정 구간만 처리
        results = streaming.process_unified_stream(
            active_streams=stream_types,
            max_count=1,  # 1개 프레임만
            include_images=True,
            start_frame=frame_idx  # 특정 프레임부터 시작
        )
        
        if results:
            # 첫 번째 이미지가 있는 결과 반환
            for result in results:
                if result.get('image_data_base64'):
                    image_data = base64.b64decode(result['image_data_base64'])
                    
                    response = HttpResponse(image_data, content_type='image/jpeg')
                    response['Cache-Control'] = 'no-cache'
                    response['X-Frame-Number'] = str(frame_idx)
                    response['X-Stream-Type'] = result.get('stream_label', 'unknown')
                    response['X-Has-Image'] = 'true'
                    response['X-Sensor-Type'] = result.get('sensor_type', 'IMAGE')
                    return response
        
        return HttpResponse(status=204)  # No Content
            
    except Exception as e:
        import traceback
        error_detail = f'Frame error: {str(e)}\nTraceback: {traceback.format_exc()}'
        print(f"DEBUG: Frame error: {error_detail}")  # 로그에 상세 에러 출력
        return HttpResponse(error_detail, status=500)