from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import JsonResponse
from .models import AriaStreamingSession, UnifiedSensorData
from .serializers import AriaStreamingSessionSerializer, UnifiedSensorDataSerializer
from .streaming_service import AriaUnifiedStreaming
from .image_streaming_service import AriaImageStreaming

def test_view(request):
    """간단한 테스트 뷰"""
    return JsonResponse({
        'status': 'success',
        'message': 'aria_sessions app is working!',
        'available_endpoints': [
            '/api/v1/aria-sessions/sessions/',
            '/api/v1/aria-sessions/test/'
        ]
    })

class AriaStreamingSessionViewSet(viewsets.ModelViewSet):
    queryset = AriaStreamingSession.objects.all()
    serializer_class = AriaStreamingSessionSerializer
    
    def list(self, request, *args, **kwargs):
        """세션 목록 + 테스트 URL 제공"""
        response = super().list(request, *args, **kwargs)
        
        # 테스트 URL들 추가
        if hasattr(response.data, 'get') and response.data.get('results'):
            # Paginated response
            results = response.data['results']
        elif isinstance(response.data, list):
            # Non-paginated response
            results = response.data
        else:
            results = []
        
        for session_data in results:
            session_id = session_data['session_id']
            base_url = f"{request.build_absolute_uri('/').rstrip('/')}/api/v1/aria-sessions/sessions/{session_id}"
            
            session_data['test_urls'] = {
                'session_detail': f"{base_url}/",
                'stream_info': f"{base_url}/stream_info/",
                'unified_stream': f"{base_url}/unified_stream/?count=5",
                'image_stream_rgb': f"{base_url}/image_stream/?stream=camera-rgb&frame=0",
                'image_stream_rgb_base64': f"{base_url}/image_stream/?stream=camera-rgb&frame=0&base64=true",
                'all_streams_image': f"{base_url}/all_streams_image/?frame=1",
                'all_streams_image_base64': f"{base_url}/all_streams_image/?frame=1&base64=true",
                'start_streaming': f"{base_url}/start_streaming/"
            }
        
        return response
    
    @action(detail=True, methods=['post'])
    def start_streaming(self, request, pk=None):
        session = self.get_object()
        
        if session.status == 'STREAMING':
            return Response({'error': 'Already streaming'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 스트리밍 서비스 초기화
            streaming = AriaUnifiedStreaming()
            streaming.vrsfile = session.vrs_file_path
            streaming.create_data_provider()
            
            # 활성 스트림 설정
            active_streams = request.data.get('active_streams', ['camera-rgb', 'camera-slam-left', 'camera-slam-right'])
            max_count = request.data.get('max_count', 50)
            
            # 통합 스트리밍 실행
            results = streaming.process_unified_stream(
                active_streams=active_streams,
                max_count=max_count
            )
            
            # 데이터베이스에 저장
            for item in results:
                UnifiedSensorData.objects.create(
                    session=session,
                    device_timestamp_ns=item['device_timestamp_ns'],
                    stream_id=item['stream_id'],
                    stream_label=item['stream_label'],
                    sensor_type=item['sensor_type'],
                    data_payload=item
                )
            
            session.status = 'COMPLETED'
            session.save()
            
            return Response({
                'message': 'Streaming completed',
                'items_processed': len(results)
            })
            
        except Exception as e:
            session.status = 'ERROR'
            session.save()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def stream_data(self, request, pk=None):
        session = self.get_object()
        data = UnifiedSensorData.objects.filter(session=session).order_by('device_timestamp_ns')
        serializer = UnifiedSensorDataSerializer(data, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def unified_stream(self, request, pk=None):
        """실시간 통합 스트림 API"""
        session = self.get_object()
        
        try:
            streaming = AriaUnifiedStreaming()
            streaming.vrsfile = session.vrs_file_path
            streaming.create_data_provider()
            
            active_streams = request.query_params.get('streams', 'camera-rgb,camera-slam-left').split(',')
            max_count = int(request.query_params.get('count', 20))
            
            results = streaming.process_unified_stream(
                active_streams=active_streams,
                max_count=max_count
            )
            
            return Response({
                'session_id': str(session.session_id),
                'unified_data': results,
                'total_items': len(results)
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def image_stream(self, request, pk=None):
        """이미지 캐베어 스트리밍 API"""
        session = self.get_object()
        
        try:
            image_streaming = AriaImageStreaming()
            image_streaming.vrsfile = session.vrs_file_path
            
            # 쿼리 파라미터
            stream_name = request.query_params.get('stream', 'camera-rgb')
            frame_index = int(request.query_params.get('frame', 0))
            include_base64 = request.query_params.get('base64', 'false').lower() == 'true'
            
            # 이미지 데이터 조회
            image_data = image_streaming.get_image_by_index(stream_name, frame_index)
            
            # 응답 데이터 준비
            response_data = {
                'session_id': str(session.session_id),
                'stream_name': image_data['stream_name'],
                'stream_id': image_data['stream_id'],
                'frame_index': image_data['frame_index'],
                'image_shape': image_data['image_shape'],
                'capture_timestamp_ns': image_data['capture_timestamp_ns'],
                'frame_number': image_data['frame_number']
            }
            
            # Base64 인코딩 옵션
            if include_base64:
                image_base64 = image_streaming.convert_to_base64_jpeg(image_data['image_array'])
                response_data['image_base64'] = image_base64
                response_data['image_format'] = 'jpeg'
            
            return Response(response_data)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def all_streams_image(self, request, pk=None):
        """모든 스트림 동시 이미지 조회"""
        session = self.get_object()
        
        try:
            image_streaming = AriaImageStreaming()
            image_streaming.vrsfile = session.vrs_file_path
            
            frame_index = int(request.query_params.get('frame', 0))
            include_base64 = request.query_params.get('base64', 'false').lower() == 'true'
            
            # 모든 스트림 이미지 조회
            all_images = image_streaming.get_all_streams_by_index(frame_index)
            
            # Base64 인코딩 처리
            if include_base64:
                for stream_name, data in all_images.items():
                    if 'image_array' in data:
                        image_base64 = image_streaming.convert_to_base64_jpeg(data['image_array'])
                        data['image_base64'] = image_base64
                        data['image_format'] = 'jpeg'
                        # numpy array는 직렬화 불가
                        del data['image_array']
            else:
                # numpy array 제거
                for stream_name, data in all_images.items():
                    if 'image_array' in data:
                        del data['image_array']
            
            return Response({
                'session_id': str(session.session_id),
                'frame_index': frame_index,
                'streams': all_images
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def stream_info(self, request, pk=None):
        """스트림 정보 조회"""
        session = self.get_object()
        
        try:
            image_streaming = AriaImageStreaming()
            image_streaming.vrsfile = session.vrs_file_path
            
            stream_info = image_streaming.get_stream_info()
            
            return Response({
                'session_id': str(session.session_id),
                'vrs_file': session.vrs_file_path,
                'streams': stream_info
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UnifiedSensorDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UnifiedSensorData.objects.all()
    serializer_class = UnifiedSensorDataSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        session_id = self.request.query_params.get('session_id')
        if session_id:
            queryset = queryset.filter(session__session_id=session_id)
        return queryset.order_by('device_timestamp_ns')
