from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import render
from .models import AriaStreamingSession
from .serializers import AriaStreamingSessionSerializer
from .image_streaming_service import AriaImageStreaming
from .streaming_service import AriaUnifiedStreaming
from django.http import HttpResponse
import base64

class SimpleAriaSessionViewSet(viewsets.ModelViewSet):
    """간단한 테스트용 ViewSet"""
    queryset = AriaStreamingSession.objects.all()
    serializer_class = AriaStreamingSessionSerializer
    
    def list(self, request, *args, **kwargs):
        """간단한 세션 목록"""
        sessions = AriaStreamingSession.objects.all()
        data = []
        
        for session in sessions:
            session_data = {
                'session_id': str(session.session_id),
                'vrs_file_path': session.vrs_file_path,
                'status': session.status,
                'created_at': session.created_at.isoformat(),
                'test_urls': {
                    'stream_info': f"/api/v1/aria-sessions/simple/{session.session_id}/stream_info/",
                    'unified_stream': f"/api/v1/aria-sessions/simple/{session.session_id}/unified_stream/",
                    'streaming_test_page': f"/api/v1/aria-sessions/simple/{session.session_id}/streaming_test/",
                    'websocket_url': f"ws://127.0.0.1:8000/ws/aria-sessions/{session.session_id}/stream/"
                }
            }
            data.append(session_data)
        
        return Response({
            'count': len(data),
            'results': data
        })
    
    def retrieve(self, request, pk=None, *args, **kwargs):
        """세션 상세"""
        try:
            session = AriaStreamingSession.objects.get(session_id=pk)
            return Response({
                'session_id': str(session.session_id),
                'vrs_file_path': session.vrs_file_path,
                'status': session.status,
                'created_at': session.created_at.isoformat(),
                'message': 'Session found successfully'
            })
        except AriaStreamingSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
    
    @action(detail=True, methods=['get'])
    def stream_info(self, request, pk=None):
        """스트림 정보 조회 (모든 센서 포함)"""
        try:
            session = AriaStreamingSession.objects.get(session_id=pk)
            
            # 통합 스트리밍으로 모든 센서 확인
            streaming = AriaUnifiedStreaming()
            streaming.vrsfile = session.vrs_file_path
            streaming.create_data_provider()
            
            # ipynb 패턴: 실제 VRS 파일의 모든 스트림 확인
            stream_details = streaming.get_all_available_streams()
            
            # JSON 직렬화를 위해 StreamId를 문자열로 변환
            serializable_details = {}
            for label, info in stream_details.items():
                serializable_details[label] = {
                    'stream_id': str(info['stream_id']),
                    'data_count': info['data_count'],
                    'available': info['available']
                }
            
            return Response({
                'session_id': str(session.session_id),
                'vrs_file': session.vrs_file_path,
                'stream_details': serializable_details,
                'available_streams': [k for k, v in serializable_details.items() if v['available']]
            })
            
        except AriaStreamingSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    
    @action(detail=True, methods=['get'])
    def unified_stream(self, request, pk=None):
        """통합 스트리밍"""
        try:
            session = AriaStreamingSession.objects.get(session_id=pk)
            
            from .streaming_service import AriaUnifiedStreaming
            streaming = AriaUnifiedStreaming()
            streaming.vrsfile = session.vrs_file_path
            streaming.create_data_provider()
            
            count = int(request.query_params.get('count', 10))
            active_streams = request.query_params.get('streams', 'camera-rgb,camera-slam-left').split(',')
            
            results = streaming.process_unified_stream(
                active_streams=active_streams,
                max_count=count
            )
            
            return Response({
                'session_id': str(session.session_id),
                'unified_data': results,
                'total_items': len(results)
            })
            
        except AriaStreamingSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    
    @action(detail=True, methods=['get'])
    def streaming_test(self, request, pk=None):
        """실시간 스트리밍 테스트 페이지"""
        try:
            session = AriaStreamingSession.objects.get(session_id=pk)
            return render(request, 'aria_sessions/streaming_test.html', {
                'session_id': str(session.session_id)
            })
        except AriaStreamingSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
    
    @action(detail=True, methods=['get'])
    def streaming_frame(self, request, pk=None):
        """실시간 스트리밍 프레임 (이미지만)"""
        try:
            session = AriaStreamingSession.objects.get(session_id=pk)
            
            # 스트림 타입들 - 공식문서 패턴
            stream_types = request.GET.get('streams', 'camera-rgb').split(',')
            frame_idx = int(request.GET.get('frame', 0))
            
            # 통합 스트리밍 사용 (공식 deliver_queued_sensor_data 패턴)
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
                
        except AriaStreamingSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        except Exception as e:
            return HttpResponse(f'Frame error: {str(e)}', status=500)
    
    @action(detail=True, methods=['get'])
    def streaming_sensor(self, request, pk=None):
        """실시간 센서 데이터 스트리밍 (IMU, 자력계, 기압계)"""
        try:
            session = AriaStreamingSession.objects.get(session_id=pk)
            
            # 센서 타입들
            sensor_types = request.GET.get('sensors', 'imu-right,magnetometer,barometer').split(',')
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
                    
                    sensor_results.append(sensor_data)
            
            return Response({
                'session_id': str(session.session_id),
                'sensor_data': sensor_results,
                'total_samples': len(sensor_results),
                'sample_start': sample_idx,
                'requested_sensors': sensor_types
            })
                
        except AriaStreamingSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        except Exception as e:
            return Response({'error': f'Sensor error: {str(e)}'}, status=500)
    
    @action(detail=True, methods=['get'])
    def unified_stream_realtime(self, request, pk=None):
        """실시간 통합 스트리밍 (모든 데이터 타입)"""
        try:
            session = AriaStreamingSession.objects.get(session_id=pk)
            
            # 모든 스트림 타입 포함
            all_streams = [
                'camera-rgb', 'camera-slam-left', 'camera-slam-right', 'camera-eyetracking',
                'imu-right', 'imu-left', 'magnetometer', 'barometer', 'microphone'
            ]
            
            sample_idx = int(request.GET.get('sample', 0))
            max_samples = int(request.GET.get('max_samples', 20))
            include_images = request.GET.get('include_images', 'true').lower() == 'true'
            
            # 통합 스트리밍 사용
            streaming = AriaUnifiedStreaming()
            streaming.vrsfile = session.vrs_file_path
            streaming.create_data_provider()
            
            # 모든 데이터 타입 처리
            results = streaming.process_unified_stream(
                active_streams=all_streams,
                max_count=max_samples,
                include_images=include_images,
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
                        'sequence': result['sequence']
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
                        'sequence': result['sequence']
                    }
                    
                    # 센서별 실제 데이터 추가
                    for key in ['imu_data', 'magnetometer_data', 'barometer_data', 'audio_data']:
                        if key in result:
                            sensor_info[key.replace('_data', '')] = result[key]
                    
                    sensors.append(sensor_info)
            
            return Response({
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
                'include_images': include_images
            })
                
        except AriaStreamingSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)
        except Exception as e:
            return Response({'error': f'Unified stream error: {str(e)}'}, status=500)