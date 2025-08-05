"""
WebSocket Consumer for real-time Aria streaming
공식문서 패턴을 따른 실시간 스트리밍
"""
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import AriaStreamingSession
from .streaming_service import AriaUnifiedStreaming
from .image_streaming_service import AriaImageStreaming

class AriaStreamingConsumer(AsyncWebsocketConsumer):
    """실시간 Aria 스트리밍 WebSocket Consumer"""
    
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f'aria_stream_{self.session_id}'
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # 연결 성공 메시지
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': f'Connected to session {self.session_id}',
            'session_id': self.session_id
        }))
    
    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """클라이언트로부터 메시지 수신"""
        try:
            data = json.loads(text_data)
            command = data.get('command', '')
            
            if command == 'start_streaming':
                await self.start_streaming(data)
            elif command == 'stop_streaming':
                await self.stop_streaming()
            elif command == 'get_frame':
                await self.get_single_frame(data)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
    
    async def start_streaming(self, config):
        """실시간 스트리밍 시작 - 공식문서 패턴"""
        try:
            # 세션 정보 조회
            session = await self.get_session()
            if not session:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Session not found'
                }))
                return
            
            # 스트리밍 설정
            stream_config = {
                'active_streams': config.get('streams', ['camera-rgb', 'camera-slam-left']),
                'fps': config.get('fps', 2),  # 초당 프레임 수
                'max_frames': config.get('max_frames', 100),
                'include_images': config.get('include_images', True)
            }
            
            # 비동기 스트리밍 시작
            await self.stream_data(session, stream_config)
            
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Streaming error: {str(e)}'
            }))
    
    async def stream_data(self, session, config):
        """실제 데이터 스트리밍"""
        try:
            # 스트리밍 서비스 초기화 (동기 함수를 비동기로 실행)
            streaming_data = await asyncio.get_event_loop().run_in_executor(
                None, self.setup_streaming, session.vrs_file_path, config
            )
            
            if not streaming_data:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Failed to setup streaming'
                }))
                return
            
            # 스트리밍 시작 알림
            await self.send(text_data=json.dumps({
                'type': 'streaming_started',
                'session_id': str(session.session_id),
                'config': config,
                'total_frames': len(streaming_data)
            }))
            
            # 프레임별 스트리밍
            fps = config['fps']
            frame_interval = 1.0 / fps
            
            for i, frame_data in enumerate(streaming_data):
                # 스트리밍 중단 체크
                if not hasattr(self, 'streaming_active'):
                    break
                
                # 프레임 데이터 전송
                await self.send(text_data=json.dumps({
                    'type': 'frame_data',
                    'frame_number': i,
                    'timestamp': frame_data.get('device_timestamp_ns'),
                    'stream_label': frame_data.get('stream_label'),
                    'sensor_type': frame_data.get('sensor_type'),
                    'data': frame_data
                }))
                
                # FPS 제어
                await asyncio.sleep(frame_interval)
            
            # 스트리밍 완료
            await self.send(text_data=json.dumps({
                'type': 'streaming_completed',
                'total_frames_sent': len(streaming_data)
            }))
            
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Streaming failed: {str(e)}'
            }))
    
    def setup_streaming(self, vrs_file_path, config):
        """스트리밍 데이터 준비 (동기 함수)"""
        try:
            streaming = AriaUnifiedStreaming()
            streaming.vrsfile = vrs_file_path
            streaming.create_data_provider()
            
            # 통합 스트림 데이터 생성
            results = streaming.process_unified_stream(
                active_streams=config['active_streams'],
                max_count=config['max_frames'],
                include_images=config['include_images']
            )
            
            return results
            
        except Exception as e:
            print(f"Setup streaming error: {e}")
            return None
    
    async def stop_streaming(self):
        """스트리밍 중지"""
        self.streaming_active = False
        await self.send(text_data=json.dumps({
            'type': 'streaming_stopped',
            'message': 'Streaming stopped'
        }))
    
    async def get_single_frame(self, config):
        """단일 프레임 조회"""
        try:
            session = await self.get_session()
            if not session:
                return
            
            frame_index = config.get('frame', 0)
            stream_name = config.get('stream', 'camera-rgb')
            
            # 이미지 스트리밍 서비스 사용
            frame_data = await asyncio.get_event_loop().run_in_executor(
                None, self.get_frame_data, session.vrs_file_path, stream_name, frame_index
            )
            
            await self.send(text_data=json.dumps({
                'type': 'single_frame',
                'data': frame_data
            }))
            
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Frame error: {str(e)}'
            }))
    
    def get_frame_data(self, vrs_file_path, stream_name, frame_index):
        """프레임 데이터 조회 (동기 함수)"""
        try:
            image_streaming = AriaImageStreaming()
            image_streaming.vrsfile = vrs_file_path
            
            frame_data = image_streaming.get_image_by_index(stream_name, frame_index)
            
            # numpy array 제거 (JSON 직렬화 불가)
            if 'image_array' in frame_data:
                # Base64로 변환
                image_base64 = image_streaming.convert_to_base64_jpeg(frame_data['image_array'])
                frame_data['image_base64'] = image_base64
                del frame_data['image_array']
            
            return frame_data
            
        except Exception as e:
            return {'error': str(e)}
    
    @database_sync_to_async
    def get_session(self):
        """세션 조회 (비동기 DB 액세스)"""
        try:
            return AriaStreamingSession.objects.get(session_id=self.session_id)
        except AriaStreamingSession.DoesNotExist:
            return None