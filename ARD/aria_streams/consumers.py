import asyncio
import json
import logging
import os
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import (
    AriaSession, VRSStream, EyeGazeData, 
    HandTrackingData, SLAMTrajectoryData, 
    SLAMPointCloud, AnalyticsResult, KafkaConsumerStatus,
    IMUData
)
from .producers import AriaKafkaProducer
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)

class AriaKafkaConsumer:
    def __init__(self, bootstrap_servers=None, consumer_group='aria-django-consumer-v2'):
        self.bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
        self.consumer_group = consumer_group
        self.consumers = {}
        self.is_consuming = False
        
        self.topic_handlers = {
            'vrs-raw-stream': self.handle_vrs_frame,
            'imu-data': self.handle_imu_data,
            'mps-eye-gaze-general': self.handle_eye_gaze,
            'mps-eye-gaze-personalized': self.handle_eye_gaze,
            'mps-hand-tracking': self.handle_hand_tracking,
            'mps-slam-trajectory': self.handle_slam_trajectory,
            'mps-slam-points': self.handle_slam_points,
            'analytics-real-time': self.handle_analytics,
            # VRS Observer → Kafka → API 파이프라인
            'real-time-frames': self.handle_real_time_vrs_frame,
            # 바이너리 스트리밍 토픽들 (간소화)
            'vrs-frame-registry': self.handle_binary_registry_simple,
            'vrs-metadata-stream': self.handle_binary_metadata_simple,
            'vrs-binary-stream': self.handle_binary_data_simple
        }
    
    def create_consumer(self, topics: list) -> KafkaConsumer:
        """Create Kafka consumer for specified topics"""
        
        def smart_deserializer(v):
            """Smart deserializer that handles both JSON and binary data"""
            if v is None:
                return None
            try:
                # Try to decode as UTF-8 and parse as JSON
                return json.loads(v.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                # Return raw bytes for binary data
                return v
        
        return KafkaConsumer(
            *topics,
            bootstrap_servers=[self.bootstrap_servers],
            group_id=self.consumer_group,
            value_deserializer=smart_deserializer,
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='latest',  # Only process new messages
            enable_auto_commit=True,
            auto_commit_interval_ms=1000
        )
    
    async def start_consuming(self, topics: Optional[list] = None):
        """Start consuming from specified topics"""
        if topics is None:
            topics = list(self.topic_handlers.keys())
        
        self.is_consuming = True
        consumer = self.create_consumer(topics)
        
        logger.info(f"Started consuming from topics: {topics}")
        
        try:
            while self.is_consuming:
                message_batch = consumer.poll(timeout_ms=1000)
                
                for topic_partition, messages in message_batch.items():
                    topic = topic_partition.topic
                    
                    for message in messages:
                        try:
                            await self.process_message(topic, message)
                            
                            # Update consumer status
                            await self.update_consumer_status(
                                topic, 
                                topic_partition.partition,
                                message.offset
                            )
                            
                        except Exception as e:
                            logger.error(f"Error processing message from {topic}: {e}")
                            await self.update_consumer_status(
                                topic,
                                topic_partition.partition, 
                                message.offset,
                                error=str(e)
                            )
                
                await asyncio.sleep(0.01)  # Small delay to prevent CPU overload
                
        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            consumer.close()
            self.is_consuming = False
    
    async def process_message(self, topic: str, message):
        """Process individual Kafka message"""
        handler = self.topic_handlers.get(topic)
        if handler:
            # Check if data is bytes (binary data) or dict (JSON data)
            if isinstance(message.value, bytes) and topic == 'vrs-binary-stream':
                logger.info(f"🚀 Processing binary message: topic={topic}, size={len(message.value)}, key={message.key}")
                # Pass both data, offset, and key for binary messages
                await handler(message.value, message.offset, message.key)
            elif isinstance(message.value, dict):
                if topic in ['vrs-frame-registry', 'vrs-metadata-stream']:
                    logger.debug(f"📄 Processing metadata: topic={topic}, frame_id={message.value.get('frame_id', 'N/A')}")
                await handler(message.value, message.offset)
            else:
                logger.warning(f"Unexpected data type for topic {topic}: {type(message.value)}")
        else:
            logger.warning(f"No handler for topic: {topic}")
    
    async def handle_vrs_frame(self, data: Dict[str, Any], offset: int):
        """Handle VRS frame data"""
        try:
            session = await self.get_or_create_session(data)
            
            # frame_data에서 실제 데이터 추출
            frame_data = data.get('frame_data', {})
            
            vrs_stream = VRSStream(
                session=session,
                stream_id=frame_data.get('stream_name', 'unknown'),
                stream_name=frame_data.get('stream_name', 'unknown'),
                device_timestamp_ns=frame_data.get('capture_timestamp_ns', 0),
                frame_index=frame_data.get('frame_index', 0),
                image_shape=frame_data.get('image_shape', []),
                pixel_format=frame_data.get('pixel_format', 'unknown'),
                kafka_offset=offset,
                
                # 실제 이미지 데이터 필드들 추가
                image_data=frame_data.get('image_data'),
                image_width=frame_data.get('image_width'),
                image_height=frame_data.get('image_height'),
                original_size_bytes=frame_data.get('original_size_bytes'),
                compressed_size_bytes=frame_data.get('compressed_size_bytes'),
                compression_quality=frame_data.get('compression_quality')
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, vrs_stream.save
            )
            
            logger.debug(f"Saved VRS frame: {data['frame_data']['stream_name']}")
            
        except Exception as e:
            logger.error(f"Error handling VRS frame: {e}")
    
    async def handle_imu_data(self, data: Dict[str, Any], offset: int):
        """Handle IMU data"""
        try:
            session = await self.get_or_create_session(data)
            
            # Determine IMU type from name
            imu_name = data.get('imu_name', 'unknown')
            imu_type = 'left' if 'left' in imu_name.lower() else 'right'
            
            imu_data = IMUData(
                session=session,
                device_timestamp_ns=data.get('device_timestamp_ns', 0),
                imu_stream_id=data.get('imu_stream_id', 'unknown'),
                imu_type=imu_type,
                accel_x=data.get('accel_x', 0.0),
                accel_y=data.get('accel_y', 0.0),
                accel_z=data.get('accel_z', 0.0),
                gyro_x=data.get('gyro_x', 0.0),
                gyro_y=data.get('gyro_y', 0.0),
                gyro_z=data.get('gyro_z', 0.0),
                temperature_c=data.get('temperature_c'),
                kafka_offset=offset
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, imu_data.save
            )
            
            logger.debug(f"Saved IMU data: {imu_type}")
            
        except Exception as e:
            logger.error(f"Error handling IMU data: {e}")
    
    async def handle_eye_gaze(self, data: Dict[str, Any], offset: int):
        """Handle eye gaze data"""
        try:
            session = await self.get_or_create_session(data)
            
            # Extract gaze type from topic or data
            gaze_type = 'general'
            if 'personalized' in data.get('data_type', ''):
                gaze_type = 'personalized'
            
            eye_gaze = EyeGazeData(
                session=session,
                device_timestamp_ns=data.get('tracking_timestamp_ns', 0),
                gaze_type=gaze_type,
                yaw=data.get('yaw', 0.0),
                pitch=data.get('pitch', 0.0),
                depth_m=data.get('depth'),
                confidence=data.get('confidence'),
                kafka_offset=offset
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, eye_gaze.save
            )
            
            logger.debug(f"Saved eye gaze data: {gaze_type}")
            
        except Exception as e:
            logger.error(f"Error handling eye gaze: {e}")
    
    async def handle_hand_tracking(self, data: Dict[str, Any], offset: int):
        """Handle hand tracking data"""
        try:
            session = await self.get_or_create_session(data)
            
            left_hand = data.get('left_hand')
            right_hand = data.get('right_hand')
            
            hand_tracking = HandTrackingData(
                session=session,
                device_timestamp_ns=data.get('tracking_timestamp_ns', 0),
                left_hand_landmarks=left_hand.get('landmarks') if left_hand else None,
                left_hand_wrist_normal=left_hand.get('wrist_palm_normal', {}).get('wrist_normal') if left_hand else None,
                left_hand_palm_normal=left_hand.get('wrist_palm_normal', {}).get('palm_normal') if left_hand else None,
                right_hand_landmarks=right_hand.get('landmarks') if right_hand else None,
                right_hand_wrist_normal=right_hand.get('wrist_palm_normal', {}).get('wrist_normal') if right_hand else None,
                right_hand_palm_normal=right_hand.get('wrist_palm_normal', {}).get('palm_normal') if right_hand else None,
                kafka_offset=offset
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, hand_tracking.save
            )
            
            logger.debug("Saved hand tracking data")
            
        except Exception as e:
            logger.error(f"Error handling hand tracking: {e}")
    
    async def handle_slam_trajectory(self, data: Dict[str, Any], offset: int):
        """Handle SLAM trajectory data"""
        try:
            session = await self.get_or_create_session(data)
            
            transform_matrix = data.get('transform_world_device', [])
            
            # Extract position for indexing
            position_x = transform_matrix[0][3] if transform_matrix and len(transform_matrix) > 0 and len(transform_matrix[0]) > 3 else 0.0
            position_y = transform_matrix[1][3] if transform_matrix and len(transform_matrix) > 1 and len(transform_matrix[1]) > 3 else 0.0 
            position_z = transform_matrix[2][3] if transform_matrix and len(transform_matrix) > 2 and len(transform_matrix[2]) > 3 else 0.0
            
            slam_trajectory = SLAMTrajectoryData(
                session=session,
                device_timestamp_ns=data.get('tracking_timestamp_ns', 0),
                transform_matrix=transform_matrix,
                position_x=position_x,
                position_y=position_y,
                position_z=position_z,
                kafka_offset=offset
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, slam_trajectory.save
            )
            
            logger.debug("Saved SLAM trajectory data")
            
        except Exception as e:
            logger.error(f"Error handling SLAM trajectory: {e}")
    
    async def handle_slam_points(self, data: Dict[str, Any], offset: int):
        """Handle SLAM point cloud data"""
        try:
            session = await self.get_or_create_session(data)
            
            points = data['points']
            
            slam_points = SLAMPointCloud(
                session=session,
                points=points,
                point_count=len(points) if points else 0,
                kafka_offset=offset
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, slam_points.save
            )
            
            logger.debug(f"Saved SLAM point cloud: {len(points)} points")
            
        except Exception as e:
            logger.error(f"Error handling SLAM points: {e}")
    
    async def handle_analytics(self, data: Dict[str, Any], offset: int):
        """Handle analytics results"""
        try:
            session = await self.get_or_create_session(data)
            
            analytics = AnalyticsResult(
                session=session,
                analysis_type=data.get('analysis_type', 'unknown'),
                result_data=data.get('result_data', {}),
                confidence_score=data.get('confidence_score'),
                kafka_offset=offset
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, analytics.save
            )
            
            logger.debug(f"Saved analytics result: {data.get('analysis_type')}")
            
        except Exception as e:
            logger.error(f"Error handling analytics: {e}")
    
    async def handle_binary_registry(self, data: Dict[str, Any], offset: int):
        """Handle binary frame registry entries"""
        try:
            # Binary models no longer needed - direct VRS streaming
            
            def _get_or_create_registry():
                registry, created = BinaryFrameRegistry.objects.get_or_create(
                    frame_id=data.get('frame_id'),
                    defaults={
                        'session_id': data.get('session_id'), 
                        'stream_id': data.get('stream_id'),
                        'frame_index': data.get('frame_index'),
                        'metadata_offset': data.get('metadata_offset'),
                        'binary_offset': data.get('binary_offset'),
                        'compression_format': data.get('compression_format'),
                        'size_bytes': data.get('compressed_size'),
                        'compression_ratio': data.get('compression_ratio'),
                        'status': 'PENDING'
                    }
                )
                return registry, created
            
            registry, created = await asyncio.get_event_loop().run_in_executor(
                None, _get_or_create_registry
            )
            
            if created:
                logger.debug(f"✅ Binary registry created: {data.get('frame_id')}")
            else:
                logger.debug(f"📋 Binary registry exists: {data.get('frame_id')}")
            
        except Exception as e:
            logger.error(f"❌ Error handling binary registry: {e}")
    
    async def handle_binary_metadata(self, data: Dict[str, Any], offset: int):
        """Handle binary frame metadata"""
        try:
            # Binary models no longer needed
            
            frame_id = data.get('frame_id')
            
            # First, get or create the registry entry
            def _get_or_create_registry():
                registry, created = BinaryFrameRegistry.objects.get_or_create(
                    frame_id=frame_id,
                    defaults={
                        'session_id': data.get('session_id', 'unknown'),
                        'stream_id': data.get('stream_id', 'unknown'),
                        'frame_index': data.get('frame_index', 0),
                        'metadata_offset': offset,
                        'compression_format': data.get('compression_format'),
                        'compression_ratio': data.get('compression_ratio'),
                    }
                )
                return registry
            
            registry = await asyncio.get_event_loop().run_in_executor(None, _get_or_create_registry)
            
            # Create metadata with correct fields
            metadata = BinaryFrameMetadata(
                registry=registry,
                frame_id=frame_id,
                session_id=data.get('session_id', 'unknown'),
                stream_id=data.get('stream_id', 'unknown'),
                frame_index=data.get('frame_index', 0),
                capture_timestamp_ns=data.get('capture_timestamp_ns', 0),
                device_timestamp_ns=data.get('device_timestamp_ns', data.get('capture_timestamp_ns', 0)),
                image_width=data.get('width', data.get('image_width', 0)),
                image_height=data.get('height', data.get('image_height', 0)),
                compression_format=data.get('compression_format', 'jpeg'),
                compression_quality=data.get('compression_quality', 90),
                original_size_bytes=data.get('original_size', data.get('original_size_bytes', 0)),
                compressed_size_bytes=data.get('compressed_size', data.get('compressed_size_bytes', 0)),
                compression_ratio=data.get('compression_ratio', 0.0)
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, metadata.save
            )
            
            logger.debug(f"✅ Binary metadata: {frame_id}")
            
        except Exception as e:
            logger.error(f"❌ Error handling binary metadata: {e}")
    
    async def handle_binary_data(self, data: bytes, offset: int, key: str = None):
        """Handle raw binary image data and link with registry using frame_id from key"""
        try:
            # Binary models no longer needed - direct VRS streaming
            
            def _link_binary_data_by_key():
                frame_id = key if key else None
                if not frame_id:
                    logger.warning(f"No frame_id key provided for binary data ({len(data)} bytes)")
                    return None
                
                logger.info(f"🔍 Processing binary data: key={frame_id}, size={len(data)} bytes, offset={offset}")
                
                try:
                    # Find registry entry by exact frame_id match
                    registry = BinaryFrameRegistry.objects.get(
                        frame_id=frame_id,
                        status='PENDING'
                    )
                    
                    logger.info(f"📋 Found registry entry: {registry.id} for {frame_id}")
                    
                    # Create binary reference entry
                    binary_ref = BinaryFrameReference.objects.create(
                        registry=registry,
                        frame_id=frame_id,
                        kafka_topic='vrs-binary-stream',
                        kafka_offset=offset,
                        storage_type='KAFKA',
                        size_bytes=len(data)
                    )
                    
                    # Update registry status to LINKED
                    registry.binary_offset = offset
                    registry.status = 'LINKED'
                    registry.linked_at = timezone.now()
                    registry.save()
                    
                    logger.info(f"✅ Binary data linked: {frame_id} ({len(data)} bytes) -> Registry ID: {registry.id}")
                    return frame_id
                    
                except BinaryFrameRegistry.DoesNotExist:
                    logger.warning(f"❌ No PENDING registry found for frame_id: {frame_id}")
                    # Show available PENDING entries for debugging
                    pending_count = BinaryFrameRegistry.objects.filter(status='PENDING').count()
                    logger.warning(f"   Available PENDING entries: {pending_count}")
                    if pending_count > 0:
                        recent_pending = BinaryFrameRegistry.objects.filter(status='PENDING').order_by('-created_at')[:3]
                        for rp in recent_pending:
                            logger.warning(f"   Sample PENDING: {rp.frame_id}")
                    return None
                except Exception as e:
                    logger.error(f"❌ Error linking binary data for {frame_id}: {e}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    return None
            
            frame_id = await asyncio.get_event_loop().run_in_executor(None, _link_binary_data_by_key)
            
        except Exception as e:
            logger.error(f"❌ Error handling binary data: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    async def get_or_create_session(self, data: Dict[str, Any]) -> AriaSession:
        """Get or create Aria session from message data"""
        # Extract session info from data or use default
        session_id = data.get('session_id', 'default-session')
        device_serial = data.get('device_serial', 'unknown-device')
        
        def _get_or_create():
            session, created = AriaSession.objects.get_or_create(
                session_id=session_id,
                defaults={
                    'session_uid': uuid.uuid4(),
                    'device_serial': device_serial,
                    'status': 'ACTIVE'
                }
            )
            return session
        
        return await asyncio.get_event_loop().run_in_executor(None, _get_or_create)
    
    async def update_consumer_status(self, topic: str, partition: int, offset: int, error: str = None):
        """Update consumer status in database"""
        def _update_status():
            status_obj, created = KafkaConsumerStatus.objects.update_or_create(
                consumer_group=self.consumer_group,
                topic=topic,
                partition=partition,
                defaults={
                    'last_offset': offset,
                    'last_processed_at': timezone.now(),
                    'status': 'ERROR' if error else 'ACTIVE',
                    'error_message': error
                }
            )
            return status_obj
        
        await asyncio.get_event_loop().run_in_executor(None, _update_status)
    
    def stop_consuming(self):
        """Stop consuming messages"""
        self.is_consuming = False
    
    def close(self):
        """Close all consumers"""
        for consumer in self.consumers.values():
            consumer.close()
        self.consumers.clear()


# WebSocket Consumers for real-time bidirectional communication

class AriaRealtimeConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for bidirectional real-time Aria communication
    Supports both receiving data from Aria and sending commands to Aria
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.user_group = None
        self.aria_producer = None
        self.streaming_task = None
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.user_group = f"aria_session_{self.session_id}"
        
        # Join session group
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()
        
        # Initialize Kafka producer for sending commands to Aria
        self.aria_producer = AriaKafkaProducer()
        
        logger.info(f"WebSocket connected for session: {self.session_id}")
        
        # Send welcome message
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'message': 'Connected to Aria real-time stream'
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"WebSocket disconnected for session: {self.session_id}, code: {close_code}")
        
        # Stop streaming task if running
        if self.streaming_task and not self.streaming_task.done():
            self.streaming_task.cancel()
        
        # Leave session group
        if self.user_group:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
    
    async def receive(self, text_data):
        """Handle messages from WebSocket client (Unity)"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            logger.info(f"Received WebSocket message: {message_type} for session {self.session_id}")
            
            if message_type == 'aria_command':
                await self.handle_aria_command(data)
            elif message_type == 'start_streaming':
                await self.handle_start_streaming(data)
            elif message_type == 'stop_streaming':
                await self.handle_stop_streaming(data)
            elif message_type == 'game_feedback':
                await self.handle_game_feedback(data)
            elif message_type == 'request_latest_data':
                await self.handle_data_request(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")
            await self.send_error(f"Server error: {str(e)}")
    
    async def handle_aria_command(self, data):
        """Handle commands to be sent to Aria device"""
        command = data.get('command')
        params = data.get('params', {})
        
        try:
            if command == 'start_recording':
                await self.send_to_aria_device({
                    'action': 'start_recording',
                    'quality': params.get('quality', 'high'),
                    'duration': params.get('duration', 300)
                })
            elif command == 'stop_recording':
                await self.send_to_aria_device({'action': 'stop_recording'})
            elif command == 'adjust_brightness':
                brightness = params.get('brightness', 50)
                await self.send_to_aria_device({
                    'action': 'set_brightness',
                    'value': brightness
                })
            elif command == 'set_framerate':
                framerate = params.get('framerate', 30)
                await self.send_to_aria_device({
                    'action': 'set_framerate',
                    'value': framerate
                })
            else:
                await self.send_error(f"Unknown Aria command: {command}")
                return
            
            # Send confirmation to Unity
            await self.send(text_data=json.dumps({
                'type': 'command_sent',
                'command': command,
                'status': 'success',
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error sending Aria command: {str(e)}")
            await self.send_error(f"Failed to send command: {str(e)}")
    
    async def handle_start_streaming(self, data):
        """Start real-time data streaming"""
        stream_types = data.get('stream_types', ['vrs', 'eye_gaze', 'hand_tracking'])
        interval = data.get('interval', 0.1)  # 100ms default
        
        if self.streaming_task and not self.streaming_task.done():
            await self.send_error("Streaming already active")
            return
        
        # Start streaming task
        self.streaming_task = asyncio.create_task(
            self.stream_data_loop(stream_types, interval)
        )
        
        await self.send(text_data=json.dumps({
            'type': 'streaming_started',
            'stream_types': stream_types,
            'interval': interval,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_stop_streaming(self, data):
        """Stop real-time data streaming"""
        if self.streaming_task and not self.streaming_task.done():
            self.streaming_task.cancel()
            self.streaming_task = None
            
            await self.send(text_data=json.dumps({
                'type': 'streaming_stopped',
                'timestamp': datetime.now().isoformat()
            }))
        else:
            await self.send_error("No active streaming to stop")
    
    async def handle_game_feedback(self, data):
        """Handle game feedback to be sent to Aria"""
        feedback_type = data.get('feedback_type')
        payload = data.get('payload', {})
        
        # Send haptic feedback, visual cues, etc. to Aria
        await self.send_to_aria_device({
            'action': 'game_feedback',
            'feedback_type': feedback_type,
            'payload': payload
        })
    
    async def handle_data_request(self, data):
        """Handle request for latest data"""
        data_type = data.get('data_type', 'vrs')
        limit = data.get('limit', 1)
        
        try:
            if data_type == 'vrs':
                latest_data = await self.get_latest_vrs_data(limit)
            elif data_type == 'eye_gaze':
                latest_data = await self.get_latest_eye_gaze_data(limit)
            elif data_type == 'hand_tracking':
                latest_data = await self.get_latest_hand_tracking_data(limit)
            elif data_type == 'slam':
                latest_data = await self.get_latest_slam_data(limit)
            elif data_type == 'imu':
                latest_data = await self.get_latest_imu_data(limit)
            else:
                await self.send_error(f"Unknown data type: {data_type}")
                return
            
            await self.send(text_data=json.dumps({
                'type': 'data_response',
                'data_type': data_type,
                'data': latest_data,
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            await self.send_error(f"Failed to fetch data: {str(e)}")
    
    async def stream_data_loop(self, stream_types, interval):
        """Continuous data streaming loop"""
        try:
            while True:
                for stream_type in stream_types:
                    try:
                        if stream_type == 'vrs':
                            data = await self.get_latest_vrs_data(1)
                        elif stream_type == 'eye_gaze':
                            data = await self.get_latest_eye_gaze_data(1)
                        elif stream_type == 'hand_tracking':
                            data = await self.get_latest_hand_tracking_data(1)
                        elif stream_type == 'slam':
                            data = await self.get_latest_slam_data(1)
                        elif stream_type == 'imu':
                            data = await self.get_latest_imu_data(1)
                        else:
                            continue
                        
                        if data:
                            await self.send(text_data=json.dumps({
                                'type': 'stream_data',
                                'stream_type': stream_type,
                                'data': data,
                                'timestamp': datetime.now().isoformat()
                            }))
                    except Exception as e:
                        logger.error(f"Error streaming {stream_type}: {str(e)}")
                
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info(f"Streaming cancelled for session: {self.session_id}")
        except Exception as e:
            logger.error(f"Error in streaming loop: {str(e)}")
    
    async def send_to_aria_device(self, command):
        """Send command to Aria device via Kafka"""
        try:
            await self.aria_producer.send_aria_command(self.session_id, command)
            logger.info(f"Sent command to Aria device: {command}")
        except Exception as e:
            logger.error(f"Failed to send command to Aria: {str(e)}")
            raise
    
    async def send_error(self, message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }))
    
    # Database query methods
    @database_sync_to_async
    def get_latest_vrs_data(self, limit):
        """Get latest VRS stream data"""
        return list(VRSStream.objects.filter(
            image_data__isnull=False
        ).order_by('-timestamp').values(
            'id', 'stream_name', 'timestamp', 'image_data',
            'image_width', 'image_height', 'compression_quality'
        )[:limit])
    
    @database_sync_to_async
    def get_latest_eye_gaze_data(self, limit):
        """Get latest eye gaze data"""
        return list(EyeGazeData.objects.order_by('-timestamp').values(
            'id', 'timestamp', 'gaze_type', 'yaw', 'pitch', 'depth_m', 'confidence'
        )[:limit])
    
    @database_sync_to_async
    def get_latest_hand_tracking_data(self, limit):
        """Get latest hand tracking data"""
        return list(HandTrackingData.objects.order_by('-timestamp').values(
            'id', 'timestamp', 'left_hand_landmarks', 'right_hand_landmarks'
        )[:limit])
    
    @database_sync_to_async
    def get_latest_slam_data(self, limit):
        """Get latest SLAM trajectory data"""
        return list(SLAMTrajectoryData.objects.order_by('-timestamp').values(
            'id', 'timestamp', 'position_x', 'position_y', 'position_z', 'transform_matrix'
        )[:limit])
    
    @database_sync_to_async
    def get_latest_imu_data(self, limit):
        """Get latest IMU data"""
        return list(IMUData.objects.order_by('-timestamp').values(
            'id', 'timestamp', 'imu_type', 'accel_x', 'accel_y', 'accel_z',
            'gyro_x', 'gyro_y', 'gyro_z', 'temperature_c'
        )[:limit])


class AriaStreamConsumer(AsyncWebsocketConsumer):
    """
    Simplified WebSocket consumer for general Aria streaming
    """
    
    async def connect(self):
        self.group_name = "aria_general_stream"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        await self.send(text_data=json.dumps({
            'type': 'connected',
            'message': 'Connected to Aria general stream'
        }))
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            # Echo back for testing
            await self.send(text_data=json.dumps({
                'type': 'echo',
                'message': f"Received: {data}",
                'timestamp': datetime.now().isoformat()
            }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))


class VRSImageConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer specifically for VRS image streaming
    """
    
    async def connect(self):
        self.group_name = "vrs_image_stream"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Start image streaming
        self.streaming_task = asyncio.create_task(self.stream_vrs_images())
    
    async def disconnect(self, close_code):
        if hasattr(self, 'streaming_task'):
            self.streaming_task.cancel()
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
    
    async def receive(self, text_data):
        # Handle control messages (start/stop streaming, etc.)
        try:
            data = json.loads(text_data)
            if data.get('action') == 'stop_streaming':
                if hasattr(self, 'streaming_task'):
                    self.streaming_task.cancel()
        except json.JSONDecodeError:
            pass
    
    async def stream_vrs_images(self):
        """Stream VRS images at regular intervals"""
        try:
            while True:
                try:
                    # Get latest VRS image
                    latest_image = await self.get_latest_vrs_image()
                    if latest_image:
                        await self.send(text_data=json.dumps({
                            'type': 'vrs_image',
                            'data': latest_image,
                            'timestamp': datetime.now().isoformat()
                        }))
                except Exception as e:
                    logger.error(f"Error streaming VRS image: {str(e)}")
                
                await asyncio.sleep(0.5)  # 2 FPS
                
        except asyncio.CancelledError:
            logger.info("VRS image streaming cancelled")
    
    @database_sync_to_async
    def get_latest_vrs_image(self):
        """Get latest VRS image data"""
        try:
            latest = VRSStream.objects.filter(
                image_data__isnull=False
            ).order_by('-timestamp').first()
            
            if latest:
                return {
                    'id': latest.id,
                    'stream_name': latest.stream_name,
                    'timestamp': latest.timestamp.isoformat(),
                    'image_data': latest.image_data,
                    'image_width': latest.image_width,
                    'image_height': latest.image_height,
                    'compression_quality': latest.compression_quality
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching VRS image: {str(e)}")
            return None

    async def handle_real_time_vrs_frame(self, data: Dict[str, Any], offset: int):
        """
        VRS Observer → Kafka → API 파이프라인 핸들러
        실시간 VRS 이미지+메타데이터 처리 (동기화)
        """
        try:
            # VRS 실시간 프레임 데이터 추출
            metadata = data.get('metadata', {})
            image_hex = data.get('image_data', '')
            
            if not image_hex:
                logger.warning("❌ VRS 프레임에 이미지 데이터 없음")
                return False
            
            # Hex string을 bytes로 변환
            try:
                image_bytes = bytes.fromhex(image_hex)
            except ValueError:
                logger.error("❌ VRS 이미지 데이터 hex 변환 실패")
                return False
            
            # VRS 프레임 정보 로깅
            frame_id = metadata.get('frame_id', 'unknown')
            stream_type = metadata.get('stream_type', 'unknown')
            frame_index = metadata.get('frame_index', 0)
            image_size = len(image_bytes)
            
            logger.info(f"🎬 VRS→Kafka→API: {stream_type} Frame {frame_index} ({image_size} bytes)")
            
            # 데이터베이스에 VRS 스트림 저장 (선택적)
            def _save_vrs_stream():
                session, _ = AriaSession.objects.get_or_create(
                    session_id=metadata.get('session_id', 'kafka-vrs-stream'),
                    defaults={'status': 'active', 'device_type': 'VRS Observer'}
                )
                
                vrs_stream = VRSStream.objects.create(
                    session=session,
                    stream_id=metadata.get('stream_id', 'unknown'),
                    timestamp=timezone.now(),
                    frame_number=frame_index,
                    device_timestamp_ns=metadata.get('timestamp_ns', 0),
                    kafka_offset=offset,
                    # 추가 VRS 메타데이터
                    metadata=metadata
                )
                return vrs_stream
            
            # 데이터베이스 저장 (비동기)
            vrs_stream = await asyncio.get_event_loop().run_in_executor(
                None, _save_vrs_stream
            )
            
            logger.debug(f"✅ VRS 스트림 저장 완료: {frame_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ VRS 실시간 프레임 처리 실패: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False
