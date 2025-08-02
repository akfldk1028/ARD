import asyncio
import json
import logging
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from django.utils import timezone
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)


class BaseKafkaConsumer:
    """Base Kafka consumer for all streaming services"""
    
    def __init__(self, service_name: str, bootstrap_servers: str = 'kafka-all:9092', 
                 consumer_group: str = None):
        self.service_name = service_name
        self.bootstrap_servers = bootstrap_servers
        self.consumer_group = consumer_group or f'{service_name}-consumer-group'
        self.consumers = {}
        self.is_consuming = False
        self.topic_handlers = {}  # To be defined by subclasses
        
    def create_consumer(self, topics: List[str]) -> KafkaConsumer:
        """Create Kafka consumer for specified topics"""
        return KafkaConsumer(
            *topics,
            bootstrap_servers=[self.bootstrap_servers],
            group_id=self.consumer_group,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            consumer_timeout_ms=30000,
            max_poll_records=10,
            api_version=(0, 10, 1),
            reconnect_backoff_ms=50,
            reconnect_backoff_max_ms=1000,
            request_timeout_ms=305000,
            heartbeat_interval_ms=3000,
            session_timeout_ms=10000
        )
    
    def register_handler(self, topic: str, handler: Callable):
        """Register message handler for a topic"""
        self.topic_handlers[topic] = handler
        logger.info(f"Registered handler for topic '{topic}' in service '{self.service_name}'")
    
    async def start_consuming(self, topics: List[str] = None):
        """Start consuming messages from specified topics"""
        if not topics:
            topics = list(self.topic_handlers.keys())
            
        if not topics:
            logger.warning(f"No topics specified for service '{self.service_name}'")
            return
        
        logger.info(f"Starting Kafka consumer for service '{self.service_name}' on topics: {topics}")
        
        try:
            consumer = self.create_consumer(topics)
            self.consumers[self.service_name] = consumer
            self.is_consuming = True
            
            # Consume messages in loop
            while self.is_consuming:
                try:
                    message_batch = consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_batch.items():
                        topic = topic_partition.topic
                        
                        for message in messages:
                            await self.process_message(topic, message)
                    
                    # Small delay to prevent CPU spinning
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"Error processing messages for '{self.service_name}': {e}")
                    await asyncio.sleep(1)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Failed to start consumer for '{self.service_name}': {e}")
        finally:
            self.stop_consuming()
    
    async def process_message(self, topic: str, message):
        """Process individual message"""
        try:
            # Get handler for topic
            handler = self.topic_handlers.get(topic)
            if not handler:
                logger.warning(f"No handler found for topic '{topic}' in service '{self.service_name}'")
                return
            
            # Prepare message data
            message_data = {
                'topic': topic,
                'partition': message.partition,
                'offset': message.offset,
                'key': message.key,
                'value': message.value,
                'timestamp': message.timestamp,
                'headers': dict(message.headers) if message.headers else {}
            }
            
            # Call handler
            if asyncio.iscoroutinefunction(handler):
                await handler(message_data)
            else:
                handler(message_data)
                
            logger.debug(f"Processed message from topic '{topic}', offset: {message.offset}")
            
        except Exception as e:
            logger.error(f"Error processing message from topic '{topic}': {e}")
    
    def stop_consuming(self):
        """Stop consuming messages"""
        self.is_consuming = False
        
        for service, consumer in self.consumers.items():
            try:
                consumer.close()
                logger.info(f"Closed consumer for service '{service}'")
            except Exception as e:
                logger.error(f"Error closing consumer for '{service}': {e}")
        
        self.consumers.clear()
        logger.info(f"Stopped consuming for service '{self.service_name}'")
    
    def __del__(self):
        """Cleanup on destruction"""
        self.stop_consuming()