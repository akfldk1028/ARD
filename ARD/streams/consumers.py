import asyncio
import json
import logging
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import (
    AriaSession, VRSStream, EyeGazeData, 
    HandTrackingData, SLAMTrajectoryData, 
    SLAMPointCloud, AnalyticsResult, KafkaConsumerStatus
)
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)

class AriaKafkaConsumer:
    def __init__(self, bootstrap_servers='localhost:9092', consumer_group='aria-django-consumer'):
        self.bootstrap_servers = bootstrap_servers
        self.consumer_group = consumer_group
        self.consumers = {}
        self.is_consuming = False
        
        self.topic_handlers = {
            'vrs-raw-stream': self.handle_vrs_frame,
            'mps-eye-gaze-general': self.handle_eye_gaze,
            'mps-eye-gaze-personalized': self.handle_eye_gaze,
            'mps-hand-tracking': self.handle_hand_tracking,
            'mps-slam-trajectory': self.handle_slam_trajectory,
            'mps-slam-points': self.handle_slam_points,
            'analytics-real-time': self.handle_analytics
        }
    
    def create_consumer(self, topics: list) -> KafkaConsumer:
        """Create Kafka consumer for specified topics"""
        return KafkaConsumer(
            *topics,
            bootstrap_servers=[self.bootstrap_servers],
            group_id=self.consumer_group,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='latest',
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
            await handler(message.value, message.offset)
        else:
            logger.warning(f"No handler for topic: {topic}")
    
    async def handle_vrs_frame(self, data: Dict[str, Any], offset: int):
        """Handle VRS frame data"""
        try:
            session = await self.get_or_create_session(data)
            
            vrs_stream = VRSStream(
                session=session,
                stream_id=data['frame_data']['stream_name'],
                stream_name=data['frame_data']['stream_name'],
                device_timestamp_ns=data['frame_data']['capture_timestamp_ns'],
                frame_index=data['frame_data']['frame_index'],
                image_shape=data['frame_data']['image_shape'],
                pixel_format=data['frame_data']['pixel_format'],
                kafka_offset=offset
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, vrs_stream.save
            )
            
            logger.debug(f"Saved VRS frame: {data['frame_data']['stream_name']}")
            
        except Exception as e:
            logger.error(f"Error handling VRS frame: {e}")
    
    async def handle_eye_gaze(self, data: Dict[str, Any], offset: int):
        """Handle eye gaze data"""
        try:
            session = await self.get_or_create_session(data)
            
            gaze_vector = data['gaze_vector']
            gaze_type = data['data_type'].split('_')[-1]  # 'general' or 'personalized'
            
            eye_gaze = EyeGazeData(
                session=session,
                device_timestamp_ns=data['device_timestamp_ns'],
                gaze_type=gaze_type,
                gaze_vector_x=gaze_vector[0] if gaze_vector else 0.0,
                gaze_vector_y=gaze_vector[1] if gaze_vector else 0.0,
                gaze_vector_z=gaze_vector[2] if gaze_vector else 0.0,
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
                device_timestamp_ns=data['device_timestamp_ns'],
                left_hand_landmarks=left_hand['landmarks'] if left_hand else None,
                left_hand_wrist_normal=left_hand['wrist_palm_normal']['wrist_normal'] if left_hand and left_hand['wrist_palm_normal'] else None,
                left_hand_palm_normal=left_hand['wrist_palm_normal']['palm_normal'] if left_hand and left_hand['wrist_palm_normal'] else None,
                right_hand_landmarks=right_hand['landmarks'] if right_hand else None,
                right_hand_wrist_normal=right_hand['wrist_palm_normal']['wrist_normal'] if right_hand and right_hand['wrist_palm_normal'] else None,
                right_hand_palm_normal=right_hand['wrist_palm_normal']['palm_normal'] if right_hand and right_hand['wrist_palm_normal'] else None,
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
            
            transform_matrix = data['transform_world_device']
            
            # Extract position for indexing
            position_x = transform_matrix[0][3] if transform_matrix else 0.0
            position_y = transform_matrix[1][3] if transform_matrix else 0.0 
            position_z = transform_matrix[2][3] if transform_matrix else 0.0
            
            slam_trajectory = SLAMTrajectoryData(
                session=session,
                device_timestamp_ns=data['device_timestamp_ns'],
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
