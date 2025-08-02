import asyncio
import json
import logging
import base64
import uuid
from datetime import datetime
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from channels.db import database_sync_to_async
from common.kafka.base_consumer import BaseKafkaConsumer
from .models import WebcamSession, WebcamFrame, WebcamAnalysis
from typing import Dict, Any

logger = logging.getLogger(__name__)


class WebcamKafkaConsumer(BaseKafkaConsumer):
    """Webcam Kafka consumer for processing video streams and analysis"""
    
    def __init__(self, bootstrap_servers: str = 'kafka-all:9092', 
                 consumer_group: str = 'webcam-django-consumer'):
        super().__init__('webcam', bootstrap_servers, consumer_group)
        
        # Register topic handlers
        self.register_handler('webcam.video.frame', self.handle_video_frame)
        self.register_handler('webcam.analysis.motion', self.handle_motion_detection)
        self.register_handler('webcam.analysis.face', self.handle_face_detection)
        self.register_handler('webcam.analysis.activity', self.handle_activity_recognition)
    
    @database_sync_to_async
    def get_or_create_session(self, session_id: str) -> WebcamSession:
        """Get or create webcam session"""
        session, created = WebcamSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                'session_uid': uuid.uuid4(),
                'device_name': 'default-webcam',
                'status': 'ACTIVE',
                'metadata': {'created_by': 'kafka_consumer'}
            }
        )
        
        if created:
            logger.info(f"Created new webcam session: {session_id}")
        
        return session
    
    async def handle_video_frame(self, message_data: Dict[str, Any]):
        """Handle webcam video frame messages"""
        try:
            message = message_data['value']
            
            # Parse message data
            session_id = message.get('session_id')
            frame_id = message.get('frame_id')
            timestamp_str = message.get('timestamp')
            width = message.get('width', 0)
            height = message.get('height', 0)
            fps = message.get('fps', 30.0)
            frame_format = message.get('format', 'RGB')
            
            if not session_id or not frame_id:
                logger.warning("Missing session_id or frame_id in video frame message")
                return
            
            # Get or create session
            session = await self.get_or_create_session(session_id)
            
            # Parse timestamp
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            # Create frame record
            await self.create_webcam_frame(
                session=session,
                frame_id=frame_id,
                timestamp=timestamp,
                width=width,
                height=height,
                fps=fps,
                format=frame_format,
                kafka_offset=message_data['offset'],
                kafka_partition=message_data['partition']
            )
            
            logger.debug(f"Processed webcam frame: {frame_id} for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing video frame message: {e}")
    
    async def handle_motion_detection(self, message_data: Dict[str, Any]):
        """Handle motion detection analysis messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            frame_id = message.get('frame_id')
            timestamp_str = message.get('timestamp')
            confidence = message.get('confidence', 0.0)
            results = message.get('results', {})
            
            if not session_id:
                logger.warning("Missing session_id in motion detection message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            # Get associated frame if exists
            frame = None
            if frame_id:
                frame = await self.get_webcam_frame(session, frame_id)
            
            # Create analysis record
            await self.create_webcam_analysis(
                session=session,
                frame=frame,
                analysis_type='motion',
                timestamp=timestamp,
                confidence=confidence,
                results=results,
                metadata=message.get('metadata', {})
            )
            
            logger.debug(f"Processed motion detection for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing motion detection message: {e}")
    
    async def handle_face_detection(self, message_data: Dict[str, Any]):
        """Handle face detection analysis messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            frame_id = message.get('frame_id')
            timestamp_str = message.get('timestamp')
            confidence = message.get('confidence', 0.0)
            results = message.get('results', {})
            
            if not session_id:
                logger.warning("Missing session_id in face detection message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            frame = None
            if frame_id:
                frame = await self.get_webcam_frame(session, frame_id)
            
            await self.create_webcam_analysis(
                session=session,
                frame=frame,
                analysis_type='face',
                timestamp=timestamp,
                confidence=confidence,
                results=results,
                metadata=message.get('metadata', {})
            )
            
            logger.debug(f"Processed face detection for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing face detection message: {e}")
    
    async def handle_activity_recognition(self, message_data: Dict[str, Any]):
        """Handle activity recognition messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            timestamp_str = message.get('timestamp')
            confidence = message.get('confidence', 0.0)
            results = message.get('results', {})
            
            if not session_id:
                logger.warning("Missing session_id in activity recognition message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            await self.create_webcam_analysis(
                session=session,
                frame=None,
                analysis_type='activity',
                timestamp=timestamp,
                confidence=confidence,
                results=results,
                metadata=message.get('metadata', {})
            )
            
            logger.debug(f"Processed activity recognition for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing activity recognition message: {e}")
    
    @database_sync_to_async
    def create_webcam_frame(self, session, frame_id, timestamp, width, height, 
                           fps, format, kafka_offset, kafka_partition):
        """Create webcam frame record"""
        return WebcamFrame.objects.create(
            session=session,
            frame_id=frame_id,
            timestamp=timestamp,
            width=width,
            height=height,
            fps=fps,
            format=format,
            kafka_offset=kafka_offset,
            kafka_partition=kafka_partition
        )
    
    @database_sync_to_async
    def get_webcam_frame(self, session, frame_id):
        """Get webcam frame by ID"""
        try:
            return WebcamFrame.objects.get(session=session, frame_id=frame_id)
        except WebcamFrame.DoesNotExist:
            return None
    
    @database_sync_to_async
    def create_webcam_analysis(self, session, frame, analysis_type, timestamp, 
                              confidence, results, metadata):
        """Create webcam analysis record"""
        return WebcamAnalysis.objects.create(
            session=session,
            frame=frame,
            analysis_type=analysis_type,
            timestamp=timestamp,
            confidence=confidence,
            results=results,
            metadata=metadata
        )