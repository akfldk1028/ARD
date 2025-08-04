"""
WebSocket Consumers for Real-Time Aria Streaming
Unity와 실시간 Aria 데이터 스트리밍을 위한 WebSocket 소비자
"""

import asyncio
import json
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import AriaSession
# Binary models removed - now using real-time streaming

logger = logging.getLogger(__name__)

class AriaRealTimeStreamConsumer(AsyncWebsocketConsumer):
    """
    Real-time Aria streaming WebSocket consumer for Unity
    
    Features:
    - Real-time frame notifications
    - Adaptive streaming based on client performance
    - Binary data access via REST API references
    - Stream control (start/stop/pause)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.streaming_active = False
        self.streaming_task = None
        self.client_performance = {
            'fps_capability': 30,
            'bandwidth_mbps': 10,
            'processing_latency_ms': 50
        }
        self.stream_config = {
            'rgb': True,
            'slam': True,
            'imu': False,
            'quality': 'auto'  # auto, high, medium, low
        }
    
    async def connect(self):
        """Handle WebSocket connection from Unity client"""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f"aria_stream_{self.session_id}"
        
        # Join the streaming group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        logger.info(f"🔗 Unity client connected to Aria stream: {self.session_id}")
        
        # Send connection acknowledgment
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'message': 'Connected to Aria real-time stream',
            'server_capabilities': {
                'max_fps': 30,
                'supported_streams': ['rgb', 'slam_left', 'slam_right', 'imu'],
                'supported_formats': ['jpeg', 'png'],
                'binary_api': True
            }
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"🔌 Unity client disconnected from Aria stream: {self.session_id}")
        
        # Stop streaming if active
        if self.streaming_active:
            await self.stop_streaming()
        
        # Leave the streaming group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
    
    async def receive(self, text_data):
        """Handle messages from Unity client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            logger.debug(f"📨 Received message: {message_type} from Unity client {self.session_id}")
            
            # Route message to appropriate handler
            handlers = {
                'start_streaming': self.handle_start_streaming,
                'stop_streaming': self.handle_stop_streaming,
                'configure_streams': self.handle_configure_streams,
                'client_performance': self.handle_client_performance,
                'request_frame': self.handle_request_frame,
                'ping': self.handle_ping
            }
            
            handler = handlers.get(message_type)
            if handler:
                await handler(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")
            await self.send_error(f"Server error: {str(e)}")
    
    async def handle_start_streaming(self, data):
        """Start real-time streaming to Unity"""
        if self.streaming_active:
            await self.send_error("Streaming already active")
            return
        
        # Apply streaming configuration
        config = data.get('config', {})
        self.stream_config.update(config)
        
        logger.info(f"🚀 Starting real-time streaming for Unity client {self.session_id}")
        logger.info(f"   Config: {self.stream_config}")
        
        # Start streaming task
        self.streaming_active = True
        self.streaming_task = asyncio.create_task(self.stream_frames_to_unity())
        
        await self.send(text_data=json.dumps({
            'type': 'streaming_started',
            'session_id': self.session_id,
            'config': self.stream_config,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_stop_streaming(self, data):
        """Stop real-time streaming"""
        if not self.streaming_active:
            await self.send_error("No active streaming to stop")
            return
        
        await self.stop_streaming()
        
        await self.send(text_data=json.dumps({
            'type': 'streaming_stopped',
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_configure_streams(self, data):
        """Configure streaming parameters"""
        config = data.get('config', {})
        self.stream_config.update(config)
        
        logger.info(f"⚙️ Updated stream config for {self.session_id}: {self.stream_config}")
        
        await self.send(text_data=json.dumps({
            'type': 'config_updated',
            'config': self.stream_config,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_client_performance(self, data):
        """Update client performance metrics for adaptive streaming"""
        performance = data.get('performance', {})
        self.client_performance.update(performance)
        
        logger.debug(f"📊 Updated client performance for {self.session_id}: {self.client_performance}")
        
        await self.send(text_data=json.dumps({
            'type': 'performance_updated',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_request_frame(self, data):
        """Handle specific frame request from Unity"""
        frame_id = data.get('frame_id')
        stream_type = data.get('stream_type', 'rgb')
        
        if not frame_id:
            await self.send_error("Missing frame_id")
            return
        
        # Get frame data
        frame_data = await self.get_frame_data(frame_id, stream_type)
        
        if frame_data:
            await self.send(text_data=json.dumps({
                'type': 'frame_data',
                'frame': frame_data,
                'timestamp': datetime.now().isoformat()
            }))
        else:
            await self.send_error(f"Frame not found: {frame_id}")
    
    async def handle_ping(self, data):
        """Handle ping for latency measurement"""
        client_timestamp = data.get('timestamp')
        
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'client_timestamp': client_timestamp,
            'server_timestamp': datetime.now().isoformat()
        }))
    
    async def stream_frames_to_unity(self):
        """Main streaming loop for Unity client - Real-time Kafka consumption"""
        logger.info(f"🎬 Starting real-time Kafka streaming loop for Unity client {self.session_id}")
        
        # Import Kafka consumer here to avoid Django issues
        from kafka import KafkaConsumer
        import base64
        import os
        
        frame_count = 0
        
        try:
            # Create Kafka consumer for real-time binary frames
            consumer = KafkaConsumer(
                'vrs-binary-stream',
                bootstrap_servers=[os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')],
                auto_offset_reset='latest',  # Only new messages
                consumer_timeout_ms=100,  # 100ms timeout for responsiveness
                group_id=f'unity-websocket-{self.session_id}-{int(asyncio.get_event_loop().time())}',
                value_deserializer=lambda v: v,  # Keep binary data as bytes
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                max_poll_records=1  # Process one frame at a time
            )
            
            logger.info(f"🔗 Unity WebSocket consumer connected to Kafka: {self.session_id}")
            
            while self.streaming_active:
                # Poll for new messages
                message_pack = consumer.poll(timeout_ms=100, max_records=1)
                
                if message_pack:
                    for topic_partition, messages in message_pack.items():
                        for message in messages:
                            if not self.streaming_active:
                                break
                                
                            # Process binary frame for Unity
                            await self.process_kafka_frame_for_unity(message)
                            frame_count += 1
                            
                            if frame_count % 10 == 0:  # Log every 10 frames
                                logger.debug(f"📊 Unity WebSocket: {frame_count} frames streamed to {self.session_id}")
                
                # Small delay to prevent CPU overload
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"❌ Error in Unity WebSocket streaming: {e}")
            await self.send_error(f"Streaming error: {str(e)}")
        finally:
            try:
                consumer.close()
                logger.info(f"🔌 Kafka consumer closed for Unity {self.session_id}")
            except:
                pass
    
    async def process_kafka_frame_for_unity(self, message):
        """Process Kafka frame and send directly to Unity via WebSocket"""
        import base64
        
        try:
            # Extract frame info from Kafka message
            frame_id = message.key or f'frame_{int(asyncio.get_event_loop().time())}'
            binary_data = message.value
            
            # Convert binary to base64 for JSON transmission
            image_base64 = base64.b64encode(binary_data).decode('utf-8')
            
            # Send real-time frame to Unity
            await self.send(text_data=json.dumps({
                'type': 'real_time_frame',
                'frame_id': frame_id,
                'timestamp': datetime.now().isoformat(),
                'image_data': image_base64,  # Base64 encoded JPEG
                'size_bytes': len(binary_data),
                'format': 'jpeg',
                'stream_type': 'rgb',
                'source': 'kafka_realtime',
                'kafka_offset': message.offset,
                'kafka_partition': message.partition
            }))
            
        except Exception as e:
            logger.error(f"❌ Error processing Kafka frame for Unity: {e}")

    async def send_frame_notification(self, frames):
        """Send frame notification to Unity with REST API references (legacy method)"""
        frame_notifications = []
        
        for frame in frames:
            frame_notifications.append({
                'frame_id': frame['frame_id'],
                'stream_type': frame['stream_type'],
                'timestamp': frame['timestamp'],
                'binary_api_url': f"/api/v1/aria/binary/frame/{frame['frame_id']}/data/",
                'metadata_api_url': f"/api/v1/aria/binary/frame/{frame['frame_id']}/metadata/",
                'size_bytes': frame.get('size_bytes'),
                'compression': frame.get('compression', {}),
                'image_width': frame.get('image_width'),
                'image_height': frame.get('image_height')
            })
        
        await self.send(text_data=json.dumps({
            'type': 'frame_notification',
            'frames': frame_notifications,
            'server_timestamp': datetime.now().isoformat(),
            'sequence_number': getattr(self, 'sequence_number', 0)
        }))
        
        # Increment sequence number
        self.sequence_number = getattr(self, 'sequence_number', 0) + 1
    
    def calculate_frame_interval(self):
        """Calculate optimal frame interval based on client performance"""
        client_fps = self.client_performance.get('fps_capability', 30)
        
        # Adaptive frame rate
        if self.stream_config.get('quality') == 'high':
            target_fps = min(30, client_fps)
        elif self.stream_config.get('quality') == 'medium':
            target_fps = min(20, client_fps)
        elif self.stream_config.get('quality') == 'low':
            target_fps = min(10, client_fps)
        else:  # auto
            # Automatically adapt based on client performance
            target_fps = min(client_fps, 30)
        
        return 1.0 / target_fps
    
    @database_sync_to_async
    def get_latest_frames(self):
        """Get latest frames from database"""
        frames = []
        
        # Get latest RGB frame if enabled
        if self.stream_config.get('rgb', True):
            rgb_frame = self.get_latest_frame_by_stream('rgb')
            if rgb_frame:
                frames.append(rgb_frame)
        
        # Get latest SLAM frames if enabled
        if self.stream_config.get('slam', True):
            slam_left = self.get_latest_frame_by_stream('slam_left')
            slam_right = self.get_latest_frame_by_stream('slam_right')
            if slam_left:
                frames.append(slam_left)
            if slam_right:
                frames.append(slam_right)
        
        return frames
    
    def get_latest_frame_by_stream(self, stream_type):
        """Get latest frame for specific stream type"""
        # TODO: Replace with real-time Kafka stream access
        logger.debug(f"Real-time streaming: {stream_type} frames from Kafka")
        return None
    
    @database_sync_to_async
    def get_frame_data(self, frame_id, stream_type):
        """Get specific frame data"""
        # TODO: Replace with real-time Kafka stream access
        logger.debug(f"Real-time streaming: frame {frame_id} from Kafka")
        return None
    
    async def stop_streaming(self):
        """Stop streaming task"""
        if self.streaming_task and not self.streaming_task.done():
            self.streaming_task.cancel()
            try:
                await self.streaming_task
            except asyncio.CancelledError:
                pass
        
        self.streaming_active = False
        self.streaming_task = None
        
        logger.info(f"🛑 Stopped streaming for Unity client {self.session_id}")
    
    async def send_error(self, message):
        """Send error message to Unity client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }))

class AriaControlConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for Aria device control commands
    """
    
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f"aria_control_{self.session_id}"
        
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        logger.info(f"🎮 Control client connected: {self.session_id}")
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"🎮 Control client disconnected: {self.session_id}")
    
    async def receive(self, text_data):
        """Handle control commands"""
        try:
            data = json.loads(text_data)
            command_type = data.get('type')
            
            # Route control commands
            if command_type == 'start_device_stream':
                await self.handle_start_device_stream(data)
            elif command_type == 'stop_device_stream':
                await self.handle_stop_device_stream(data)
            elif command_type == 'configure_device':
                await self.handle_configure_device(data)
            else:
                await self.send_error(f"Unknown control command: {command_type}")
                
        except Exception as e:
            await self.send_error(f"Control error: {str(e)}")
    
    async def handle_start_device_stream(self, data):
        """Start device streaming"""
        # This would integrate with AriaDeviceKafkaProducer
        await self.send(text_data=json.dumps({
            'type': 'device_stream_started',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_stop_device_stream(self, data):
        """Stop device streaming"""
        await self.send(text_data=json.dumps({
            'type': 'device_stream_stopped',
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_configure_device(self, data):
        """Configure device parameters"""
        config = data.get('config', {})
        
        await self.send(text_data=json.dumps({
            'type': 'device_configured',
            'config': config,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def send_error(self, message):
        """Send error message"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }))