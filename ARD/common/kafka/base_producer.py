import json
import time
from kafka import KafkaProducer
from kafka.errors import KafkaError
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseKafkaProducer:
    """Base Kafka producer for all streaming services"""
    
    def __init__(self, service_name: str, bootstrap_servers: str = 'kafka-all:9092'):
        self.service_name = service_name
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.topics = {}  # To be defined by subclasses
        
    def _get_producer(self):
        """Lazy initialization of producer"""
        if self.producer is None:
            self.producer = KafkaProducer(
                bootstrap_servers=[self.bootstrap_servers],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                retries=3,
                acks=1,
                request_timeout_ms=10000,
                metadata_max_age_ms=60000,
                max_block_ms=5000,
                api_version=(0, 10, 1),
                connections_max_idle_ms=300000,
                reconnect_backoff_ms=50,
                reconnect_backoff_max_ms=1000
            )
        return self.producer
    
    def send_message(self, topic_key: str, message: Dict[str, Any], key: Optional[str] = None):
        """
        Send message to Kafka topic
        
        Args:
            topic_key: Key in self.topics dict
            message: Message payload
            key: Optional message key for partitioning
        """
        if topic_key not in self.topics:
            logger.error(f"Topic key '{topic_key}' not found for service '{self.service_name}'")
            return False
            
        topic = self.topics[topic_key]
        
        # Add service metadata
        enriched_message = {
            **message,
            'service': self.service_name,
            'producer_timestamp': datetime.utcnow().isoformat(),
        }
        
        try:
            producer = self._get_producer()
            future = producer.send(topic, value=enriched_message, key=key)
            
            # Block until message is sent (optional - can be made async)
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Message sent to {topic}: partition={record_metadata.partition}, offset={record_metadata.offset}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send message to {topic}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to {topic}: {e}")
            return False
    
    def send_batch(self, messages: list):
        """Send multiple messages efficiently"""
        try:
            producer = self._get_producer()
            
            for msg_data in messages:
                topic_key = msg_data.get('topic_key')
                message = msg_data.get('message')
                key = msg_data.get('key')
                
                if topic_key and message:
                    self.send_message(topic_key, message, key)
            
            producer.flush()  # Ensure all messages are sent
            return True
            
        except Exception as e:
            logger.error(f"Failed to send batch messages: {e}")
            return False
    
    def close(self):
        """Close producer connection"""
        if self.producer:
            self.producer.close()
            self.producer = None
            logger.info(f"Closed Kafka producer for service '{self.service_name}'")
    
    def __del__(self):
        """Cleanup on destruction"""
        self.close()