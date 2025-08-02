"""
Binary Kafka Consumer for efficient image/video processing
Handles metadata/binary topic coordination with ID linking
"""

import json
import logging
import os
from typing import Dict, Any, Optional, Callable
import numpy as np
from kafka import KafkaConsumer
from kafka.errors import KafkaError

# OpenCV for optimal image processing
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    print("Warning: OpenCV not available in binary consumer. Falling back to PIL.")
    from PIL import Image
    import io
from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class BinaryKafkaConsumer:
    """
    High-performance binary data consumer with metadata coordination
    
    Features:
    - Separate metadata and binary topic consumption
    - ID-based metadata-binary linking
    - Configurable image decompression
    - Handler registration for different data types
    """
    
    def __init__(self, 
                 bootstrap_servers=None,
                 consumer_group='aria-binary-consumer',
                 max_workers=4):
        self.bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka-all:9092')
        self.consumer_group = consumer_group
        self.max_workers = max_workers
        
        # Consumer instances
        self.metadata_consumer = None
        self.binary_consumer = None
        self.registry_consumer = None
        self.sensor_consumer = None
        
        # Topic configuration
        self.topics = {
            'metadata': 'vrs-metadata-stream',
            'binary': 'vrs-binary-stream',
            'registry': 'vrs-frame-registry', 
            'sensor': 'mps-sensor-stream'
        }
        
        # Handler registry for different message types
        self.handlers = {
            'vrs_frame_binary': self._default_frame_handler,
            'mps_eye_gaze': self._default_sensor_handler,
            'mps_slam': self._default_sensor_handler,
            'mps_hand_tracking': self._default_sensor_handler,
        }
        
        # Frame linking cache (frame_id -> metadata/binary)
        self.frame_cache = {}
        self.cache_lock = threading.Lock()
        
        # Processing stats
        self.stats = {
            'frames_processed': 0,
            'sensors_processed': 0,
            'linking_success': 0,
            'linking_failed': 0,
            'last_processed': None
        }
        
        self.is_consuming = False
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def _create_consumer(self, topics: list, value_deserializer=None) -> KafkaConsumer:
        """Create optimized Kafka consumer"""
        return KafkaConsumer(
            *topics,
            bootstrap_servers=[self.bootstrap_servers],
            group_id=self.consumer_group,
            value_deserializer=value_deserializer,
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            # Performance settings
            fetch_min_bytes=1024,          # Wait for at least 1KB
            fetch_max_wait_ms=500,         # Max wait 500ms
            max_partition_fetch_bytes=10485760,  # 10MB max per partition
            # Auto-commit settings
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            # Session management
            session_timeout_ms=30000,
            heartbeat_interval_ms=3000,
            # Offset management
            auto_offset_reset='latest',
            # Error handling
            reconnect_backoff_ms=50,
            reconnect_backoff_max_ms=1000
        )
    
    def register_handler(self, data_type: str, handler: Callable[[Dict[str, Any]], None]):
        """Register custom handler for specific data types"""
        self.handlers[data_type] = handler
        logger.info(f"Registered handler for data type: {data_type}")
    
    def decompress_image_binary(self, binary_data: bytes, compression_info: Dict[str, Any]) -> np.ndarray:
        """
        Decompress binary image data back to numpy array
        
        Args:
            binary_data: Compressed image bytes
            compression_info: Compression metadata from producer
            
        Returns:
            np.ndarray: Decompressed image
        """
        try:
            format_type = compression_info.get('format', 'jpeg')
            
            if format_type == 'raw':
                # Raw numpy bytes
                shape = compression_info['shape']
                dtype = compression_info['dtype']
                return np.frombuffer(binary_data, dtype=dtype).reshape(shape)
            else:
                # Compressed formats (jpeg, png, webp)
                np_array = np.frombuffer(binary_data, dtype=np.uint8)
                
                if HAS_OPENCV:
                    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
                    if image is None:
                        raise ValueError(f"Failed to decode {format_type} image")
                else:
                    # Fallback to PIL for decoding
                    from PIL import Image
                    import io
                    image_pil = Image.open(io.BytesIO(binary_data))
                    image = np.array(image_pil)
                
                return image
                
        except Exception as e:
            logger.error(f"Image decompression failed: {e}")
            raise
    
    def _link_frame_data(self, frame_id: str, data_type: str, data: Any) -> Optional[Dict[str, Any]]:
        """
        Link metadata and binary data using frame_id
        
        Returns complete frame data when both metadata and binary are available
        """
        with self.cache_lock:
            if frame_id not in self.frame_cache:
                self.frame_cache[frame_id] = {}
            
            self.frame_cache[frame_id][data_type] = data
            
            # Check if we have both metadata and binary
            frame_data = self.frame_cache[frame_id]
            if 'metadata' in frame_data and 'binary' in frame_data:
                # Complete frame available
                complete_frame = {
                    'frame_id': frame_id,
                    'metadata': frame_data['metadata'],
                    'binary_data': frame_data['binary'],
                    'linked_at': datetime.utcnow().isoformat()
                }
                
                # Clean up cache
                del self.frame_cache[frame_id]
                
                self.stats['linking_success'] += 1
                return complete_frame
            
            return None
    
    def _default_frame_handler(self, complete_frame: Dict[str, Any]):
        """Default handler for complete VRS frames"""
        frame_id = complete_frame['frame_id']
        metadata = complete_frame['metadata']
        binary_data = complete_frame['binary_data']
        
        try:
            # Decompress image
            image = self.decompress_image_binary(
                binary_data, 
                metadata['compression']
            )
            
            logger.info(f"Processed frame {frame_id}: {image.shape} "
                       f"({metadata['compression']['compressed_size']} bytes)")
            
            # Here you would typically:
            # 1. Save to database
            # 2. Trigger real-time processing
            # 3. Forward to other services
            # 4. Update UI/dashboard
            
            self.stats['frames_processed'] += 1
            self.stats['last_processed'] = datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.error(f"Frame processing failed for {frame_id}: {e}")
    
    def _default_sensor_handler(self, sensor_data: Dict[str, Any]):
        """Default handler for sensor data"""
        sensor_type = sensor_data.get('sensor_type', 'unknown')
        sensor_id = sensor_data.get('sensor_id', 'unknown')
        
        logger.debug(f"Processed sensor data: {sensor_type} ({sensor_id})")
        
        # Here you would typically:
        # 1. Save to database
        # 2. Trigger analytics
        # 3. Update real-time dashboards
        
        self.stats['sensors_processed'] += 1
    
    def _consume_metadata(self):
        """Consume metadata topic"""
        try:
            self.metadata_consumer = self._create_consumer(
                [self.topics['metadata']], 
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            logger.info("Started metadata consumer")
            
            for message in self.metadata_consumer:
                if not self.is_consuming:
                    break
                
                try:
                    frame_id = message.key
                    metadata = message.value
                    
                    # Link with binary data
                    complete_frame = self._link_frame_data(frame_id, 'metadata', metadata)
                    
                    if complete_frame:
                        # Both metadata and binary available - process
                        handler = self.handlers.get(
                            metadata.get('data_type', 'vrs_frame_binary'),
                            self._default_frame_handler
                        )
                        self.executor.submit(handler, complete_frame)
                    
                except Exception as e:
                    logger.error(f"Metadata processing error: {e}")
                    
        except Exception as e:
            logger.error(f"Metadata consumer error: {e}")
        finally:
            if self.metadata_consumer:
                self.metadata_consumer.close()
    
    def _consume_binary(self):
        """Consume binary topic"""
        try:
            self.binary_consumer = self._create_consumer(
                [self.topics['binary']],
                value_deserializer=None  # Raw bytes
            )
            
            logger.info("Started binary consumer")
            
            for message in self.binary_consumer:
                if not self.is_consuming:
                    break
                
                try:
                    frame_id = message.key
                    binary_data = message.value
                    
                    # Link with metadata
                    complete_frame = self._link_frame_data(frame_id, 'binary', binary_data)
                    
                    if complete_frame:
                        # Both metadata and binary available - process
                        metadata = complete_frame['metadata']
                        handler = self.handlers.get(
                            metadata.get('data_type', 'vrs_frame_binary'),
                            self._default_frame_handler
                        )
                        self.executor.submit(handler, complete_frame)
                    
                except Exception as e:
                    logger.error(f"Binary processing error: {e}")
                    
        except Exception as e:
            logger.error(f"Binary consumer error: {e}")
        finally:
            if self.binary_consumer:
                self.binary_consumer.close()
    
    def _consume_sensor(self):
        """Consume sensor data topic"""
        try:
            self.sensor_consumer = self._create_consumer(
                [self.topics['sensor']],
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            logger.info("Started sensor consumer")
            
            for message in self.sensor_consumer:
                if not self.is_consuming:
                    break
                
                try:
                    sensor_data = message.value
                    data_type = sensor_data.get('data_type', 'unknown')
                    
                    handler = self.handlers.get(data_type, self._default_sensor_handler)
                    self.executor.submit(handler, sensor_data)
                    
                except Exception as e:
                    logger.error(f"Sensor processing error: {e}")
                    
        except Exception as e:
            logger.error(f"Sensor consumer error: {e}")
        finally:
            if self.sensor_consumer:
                self.sensor_consumer.close()
    
    def start_consuming(self):
        """Start consuming from all topics in parallel"""
        if self.is_consuming:
            logger.warning("Consumer already running")
            return
        
        self.is_consuming = True
        logger.info(f"Starting binary consumer group: {self.consumer_group}")
        
        # Start consumers in separate threads
        self.executor.submit(self._consume_metadata)
        self.executor.submit(self._consume_binary)
        self.executor.submit(self._consume_sensor)
        
        logger.info("All consumers started")
    
    def stop_consuming(self):
        """Stop all consumers"""
        logger.info("Stopping binary consumers...")
        self.is_consuming = False
        
        # Close consumers
        if self.metadata_consumer:
            self.metadata_consumer.close()
        if self.binary_consumer:
            self.binary_consumer.close()
        if self.sensor_consumer:
            self.sensor_consumer.close()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        logger.info("All binary consumers stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        with self.cache_lock:
            cache_size = len(self.frame_cache)
        
        return {
            **self.stats,
            'cache_size': cache_size,
            'is_consuming': self.is_consuming
        }