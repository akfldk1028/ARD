"""
Stream Manager
Central orchestration of all streaming services
"""

import os
import logging
from typing import Dict, List, Optional
from .topic_manager import TopicManager

logger = logging.getLogger(__name__)


class StreamManager:
    """Central manager for all streaming services"""
    
    def __init__(self):
        # Get active streams from environment variable
        active_streams_env = os.getenv('ACTIVE_STREAMS', 'aria')
        self.active_streams = [s.strip() for s in active_streams_env.split(',')]
        
        self.producers = {}
        self.consumers = {}
        self.services = {}
        
        logger.info(f"StreamManager initialized with active streams: {self.active_streams}")
    
    def register_service(self, service_name: str, producer_class=None, consumer_class=None):
        """Register a streaming service"""
        if service_name not in self.active_streams:
            logger.info(f"Service '{service_name}' not in active streams, skipping registration")
            return
        
        self.services[service_name] = {
            'producer_class': producer_class,
            'consumer_class': consumer_class,
            'producer_instance': None,
            'consumer_instance': None
        }
        
        logger.info(f"Registered service '{service_name}'")
    
    def initialize_producers(self, bootstrap_servers: str = None):
        """Initialize producers for active services"""
        bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-all:9092')
        
        for service_name in self.active_streams:
            service_config = self.services.get(service_name)
            if not service_config or not service_config['producer_class']:
                logger.warning(f"No producer class registered for service '{service_name}'")
                continue
            
            try:
                producer_class = service_config['producer_class']
                producer_instance = producer_class(bootstrap_servers=bootstrap_servers)
                
                self.producers[service_name] = producer_instance
                service_config['producer_instance'] = producer_instance
                
                logger.info(f"Initialized producer for service '{service_name}'")
                
            except Exception as e:
                logger.error(f"Failed to initialize producer for '{service_name}': {e}")
    
    def initialize_consumers(self, bootstrap_servers: str = None):
        """Initialize consumers for active services"""
        bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-all:9092')
        
        for service_name in self.active_streams:
            service_config = self.services.get(service_name)
            if not service_config or not service_config['consumer_class']:
                logger.warning(f"No consumer class registered for service '{service_name}'")
                continue
            
            try:
                consumer_class = service_config['consumer_class']
                consumer_instance = consumer_class(
                    bootstrap_servers=bootstrap_servers,
                    consumer_group=f'{service_name}-django-consumer'
                )
                
                self.consumers[service_name] = consumer_instance
                service_config['consumer_instance'] = consumer_instance
                
                logger.info(f"Initialized consumer for service '{service_name}'")
                
            except Exception as e:
                logger.error(f"Failed to initialize consumer for '{service_name}': {e}")
    
    async def start_all_consumers(self):
        """Start all registered consumers"""
        tasks = []
        
        for service_name, consumer in self.consumers.items():
            if consumer:
                # Get topics for this service
                topics = list(TopicManager.get_topics_for_service(service_name).values())
                if topics:
                    task = consumer.start_consuming(topics)
                    tasks.append(task)
                    logger.info(f"Starting consumer for '{service_name}' with topics: {topics}")
        
        if tasks:
            import asyncio
            await asyncio.gather(*tasks)
        else:
            logger.warning("No consumers to start")
    
    def stop_all_consumers(self):
        """Stop all consumers"""
        for service_name, consumer in self.consumers.items():
            if consumer:
                consumer.stop_consuming()
                logger.info(f"Stopped consumer for '{service_name}'")
    
    def get_producer(self, service_name: str):
        """Get producer instance for service"""
        return self.producers.get(service_name)
    
    def get_consumer(self, service_name: str):
        """Get consumer instance for service"""
        return self.consumers.get(service_name)
    
    def get_active_services(self) -> List[str]:
        """Get list of active
         service names"""
        return self.active_streams.copy()
    
    def is_service_active(self, service_name: str) -> bool:
        """Check if service is active"""
        return service_name in self.active_streams
    
    def get_service_status(self) -> Dict[str, Dict]:
        """Get status of all services"""
        status = {}
        
        for service_name in self.active_streams:
            service_config = self.services.get(service_name, {})
            status[service_name] = {
                'registered': service_name in self.services,
                'producer_initialized': service_config.get('producer_instance') is not None,
                'consumer_initialized': service_config.get('consumer_instance') is not None,
                'topics': list(TopicManager.get_topics_for_service(service_name).values())
            }
        
        return status
    
    def cleanup(self):
        """Cleanup all resources"""
        # Stop consumers
        self.stop_all_consumers()
        
        # Close producers
        for service_name, producer in self.producers.items():
            if producer:
                producer.close()
                logger.info(f"Closed producer for '{service_name}'")
        
        # Clear instances
        self.producers.clear()
        self.consumers.clear()
        
        for service_config in self.services.values():
            service_config['producer_instance'] = None
            service_config['consumer_instance'] = None
        
        logger.info("StreamManager cleanup completed")


# Global instance
stream_manager = StreamManager()