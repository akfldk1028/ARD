import asyncio
import json
import logging
import uuid
from datetime import datetime
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from channels.db import database_sync_to_async
from common.kafka.base_consumer import BaseKafkaConsumer
from .models import SmartwatchSession, SensorData, ActivityData, HealthMetrics
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SmartwatchKafkaConsumer(BaseKafkaConsumer):
    """Smartwatch Kafka consumer for processing sensor data and health metrics"""
    
    def __init__(self, bootstrap_servers: str = 'kafka-all:9092',
                 consumer_group: str = 'smartwatch-django-consumer'):
        super().__init__('smartwatch', bootstrap_servers, consumer_group)
        
        # Register topic handlers
        self.register_handler('smartwatch.sensor.heart_rate', self.handle_heart_rate)
        self.register_handler('smartwatch.sensor.accelerometer', self.handle_accelerometer)
        self.register_handler('smartwatch.sensor.gyroscope', self.handle_gyroscope)
        self.register_handler('smartwatch.sensor.gps', self.handle_gps)
        self.register_handler('smartwatch.sensor.steps', self.handle_step_counter)
        self.register_handler('smartwatch.health.metrics', self.handle_health_metrics)
        self.register_handler('smartwatch.health.activity', self.handle_activity_recognition)
    
    @database_sync_to_async
    def get_or_create_session(self, session_id: str) -> SmartwatchSession:
        """Get or create smartwatch session"""
        session, created = SmartwatchSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                'session_uid': uuid.uuid4(),
                'device_name': 'default-smartwatch',
                'device_model': 'Generic Smartwatch',
                'status': 'ACTIVE',
                'metadata': {'created_by': 'kafka_consumer'}
            }
        )
        
        if created:
            logger.info(f"Created new smartwatch session: {session_id}")
        
        return session
    
    async def handle_heart_rate(self, message_data: Dict[str, Any]):
        """Handle heart rate sensor messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            timestamp_str = message.get('timestamp')
            values = message.get('values', {})
            accuracy = message.get('accuracy', 1.0)
            metadata = message.get('metadata', {})
            
            if not session_id:
                logger.warning("Missing session_id in heart rate message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            await self.create_sensor_data(
                session=session,
                sensor_type='heart_rate',
                timestamp=timestamp,
                values=values,
                accuracy=accuracy,
                metadata=metadata,
                kafka_offset=message_data['offset'],
                kafka_partition=message_data['partition']
            )
            
            logger.debug(f"Processed heart rate data for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing heart rate message: {e}")
    
    async def handle_accelerometer(self, message_data: Dict[str, Any]):
        """Handle accelerometer sensor messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            timestamp_str = message.get('timestamp')
            values = message.get('values', {})
            accuracy = message.get('accuracy', 1.0)
            metadata = message.get('metadata', {})
            
            if not session_id:
                logger.warning("Missing session_id in accelerometer message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            await self.create_sensor_data(
                session=session,
                sensor_type='accelerometer',
                timestamp=timestamp,
                values=values,
                accuracy=accuracy,
                metadata=metadata,
                kafka_offset=message_data['offset'],
                kafka_partition=message_data['partition']
            )
            
            logger.debug(f"Processed accelerometer data for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing accelerometer message: {e}")
    
    async def handle_gyroscope(self, message_data: Dict[str, Any]):
        """Handle gyroscope sensor messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            timestamp_str = message.get('timestamp')
            values = message.get('values', {})
            accuracy = message.get('accuracy', 1.0)
            metadata = message.get('metadata', {})
            
            if not session_id:
                logger.warning("Missing session_id in gyroscope message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            await self.create_sensor_data(
                session=session,
                sensor_type='gyroscope', 
                timestamp=timestamp,
                values=values,
                accuracy=accuracy,
                metadata=metadata,
                kafka_offset=message_data['offset'],
                kafka_partition=message_data['partition']
            )
            
            logger.debug(f"Processed gyroscope data for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing gyroscope message: {e}")
    
    async def handle_gps(self, message_data: Dict[str, Any]):
        """Handle GPS sensor messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            timestamp_str = message.get('timestamp')
            values = message.get('values', {})
            accuracy = message.get('accuracy', 1.0)
            metadata = message.get('metadata', {})
            
            if not session_id:
                logger.warning("Missing session_id in GPS message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            await self.create_sensor_data(
                session=session,
                sensor_type='gps',
                timestamp=timestamp,
                values=values,
                accuracy=accuracy,
                metadata=metadata,
                kafka_offset=message_data['offset'],
                kafka_partition=message_data['partition']
            )
            
            logger.debug(f"Processed GPS data for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing GPS message: {e}")
    
    async def handle_step_counter(self, message_data: Dict[str, Any]):
        """Handle step counter messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            timestamp_str = message.get('timestamp')
            values = message.get('values', {})
            accuracy = message.get('accuracy', 1.0)
            metadata = message.get('metadata', {})
            
            if not session_id:
                logger.warning("Missing session_id in step counter message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            await self.create_sensor_data(
                session=session,
                sensor_type='step_counter',
                timestamp=timestamp,
                values=values,
                accuracy=accuracy,
                metadata=metadata,
                kafka_offset=message_data['offset'],
                kafka_partition=message_data['partition']
            )
            
            logger.debug(f"Processed step counter data for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing step counter message: {e}")
    
    async def handle_health_metrics(self, message_data: Dict[str, Any]):
        """Handle health metrics messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            timestamp_str = message.get('timestamp')
            heart_rate = message.get('heart_rate')
            blood_oxygen = message.get('blood_oxygen')
            stress_level = message.get('stress_level')
            sleep_stage = message.get('sleep_stage')
            body_temperature = message.get('body_temperature')
            metadata = message.get('metadata', {})
            
            if not session_id:
                logger.warning("Missing session_id in health metrics message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            
            await self.create_health_metrics(
                session=session,
                timestamp=timestamp,
                heart_rate=heart_rate,
                blood_oxygen=blood_oxygen,
                stress_level=stress_level,
                sleep_stage=sleep_stage,
                body_temperature=body_temperature,
                metadata=metadata
            )
            
            logger.debug(f"Processed health metrics for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing health metrics message: {e}")
    
    async def handle_activity_recognition(self, message_data: Dict[str, Any]):
        """Handle activity recognition messages"""
        try:
            message = message_data['value']
            
            session_id = message.get('session_id')
            timestamp_str = message.get('timestamp')
            activity_type = message.get('activity_type')
            confidence = message.get('confidence', 0.0)
            duration = message.get('duration')
            start_time_str = message.get('start_time')
            calories_burned = message.get('calories_burned')
            metadata = message.get('metadata', {})
            
            if not session_id or not activity_type:
                logger.warning("Missing session_id or activity_type in activity recognition message")
                return
            
            session = await self.get_or_create_session(session_id)
            timestamp = parse_datetime(timestamp_str) if timestamp_str else timezone.now()
            start_time = parse_datetime(start_time_str) if start_time_str else timestamp
            
            await self.create_activity_data(
                session=session,
                activity_type=activity_type,
                start_time=start_time,
                end_time=timestamp,
                duration=duration,
                confidence=confidence,
                calories=calories_burned,
                metadata=metadata
            )
            
            logger.debug(f"Processed activity recognition for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Error processing activity recognition message: {e}")
    
    @database_sync_to_async
    def create_sensor_data(self, session, sensor_type, timestamp, values, accuracy,
                          metadata, kafka_offset, kafka_partition):
        """Create sensor data record"""
        return SensorData.objects.create(
            session=session,
            sensor_type=sensor_type,
            timestamp=timestamp,
            values=values,
            accuracy=accuracy,
            metadata=metadata,
            kafka_offset=kafka_offset,
            kafka_partition=kafka_partition
        )
    
    @database_sync_to_async
    def create_health_metrics(self, session, timestamp, heart_rate, blood_oxygen,
                             stress_level, sleep_stage, body_temperature, metadata):
        """Create health metrics record"""
        return HealthMetrics.objects.create(
            session=session,
            timestamp=timestamp,
            heart_rate=heart_rate,
            blood_oxygen=blood_oxygen,
            stress_level=stress_level,
            sleep_stage=sleep_stage,
            body_temperature=body_temperature,
            metadata=metadata
        )
    
    @database_sync_to_async
    def create_activity_data(self, session, activity_type, start_time, end_time,
                            duration, confidence, calories, metadata):
        """Create activity data record"""
        return ActivityData.objects.create(
            session=session,
            activity_type=activity_type,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            confidence=confidence,
            calories=calories,
            metadata=metadata
        )