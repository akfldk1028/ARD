"""
Binary Kafka Producer for efficient image/video streaming
Optimized for Project Aria VRS data with metadata/binary separation
"""

import json
import time
import uuid
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, Union
import numpy as np
from kafka import KafkaProducer
from kafka.errors import KafkaError

# OpenCV for optimal image compression and processing
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    print("Warning: OpenCV not available. Falling back to PIL.")
    from PIL import Image
    import io

logger = logging.getLogger(__name__)

class BinaryKafkaProducer:
    """
    High-performance binary data producer with metadata separation
    
    Architecture:
    - Metadata Topic: JSON with frame info, IDs, timestamps
    - Binary Topic: Raw bytes with compression
    - Registry Topic: ID mapping for metadata-binary linking
    """
    
    def __init__(self, bootstrap_servers=None):
        self.bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
        self.producer = None
        
        # Topic configuration
        self.topics = {
            'metadata': 'vrs-metadata-stream',
            'binary': 'vrs-binary-stream', 
            'registry': 'vrs-frame-registry',
            'sensor': 'mps-sensor-stream'
        }
        
        # Compression settings
        self.compression_config = {
            'jpeg_quality': 90,
            'png_compression': 6,
            'webp_quality': 85
        }
        
    def _get_producer(self) -> KafkaProducer:
        """Lazy initialization with simplified settings for reliability"""
        if self.producer is None:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=[self.bootstrap_servers],
                    # Simplified settings for stability
                    value_serializer=None,  # Raw bytes for binary topic
                    key_serializer=lambda k: k.encode('utf-8') if isinstance(k, str) else k,
                    # Basic reliability settings
                    retries=3,
                    acks=1,
                    request_timeout_ms=10000,
                    api_version=(0, 10),  # Explicit API version
                    # Connection timeout
                    connections_max_idle_ms=60000,
                    reconnect_backoff_ms=100,
                    max_request_size=5242880,  # 5MB max message
                    batch_size=16384,  # 16KB batches
                    linger_ms=10
                )
                logger.info(f"✅ Kafka producer connected to {self.bootstrap_servers}")
            except Exception as e:
                logger.error(f"❌ Failed to create Kafka producer: {e}")
                raise
        return self.producer
    
    def generate_frame_id(self, session_id: str, stream_id: str, frame_index: int) -> str:
        """Generate unique frame ID for metadata-binary linking"""
        timestamp = int(time.time_ns())
        return f"{session_id}_{stream_id}_{frame_index}_{timestamp}"
    
    def compress_image_binary(self, 
                            numpy_image: np.ndarray, 
                            format: str = 'jpeg',
                            quality: Optional[int] = None) -> tuple[bytes, Dict[str, Any]]:
        """
        Compress numpy image to binary format
        
        Returns:
            tuple: (compressed_bytes, compression_info)
        """
        try:
            if format.lower() == 'raw':
                # Raw numpy bytes (no compression)
                return numpy_image.tobytes(), {
                    'format': 'raw',
                    'original_size': numpy_image.nbytes,
                    'compressed_size': numpy_image.nbytes,
                    'compression_ratio': 1.0,
                    'dtype': str(numpy_image.dtype),
                    'shape': numpy_image.shape
                }
            
            if HAS_OPENCV:
                # Use OpenCV for optimal compression
                if format.lower() == 'jpeg':
                    quality = quality or self.compression_config['jpeg_quality']
                    success, buffer = cv2.imencode('.jpg', numpy_image, 
                                                 [cv2.IMWRITE_JPEG_QUALITY, quality])
                elif format.lower() == 'png':
                    compression = quality or self.compression_config['png_compression']
                    success, buffer = cv2.imencode('.png', numpy_image,
                                                 [cv2.IMWRITE_PNG_COMPRESSION, compression])
                elif format.lower() == 'webp':
                    quality = quality or self.compression_config['webp_quality']
                    success, buffer = cv2.imencode('.webp', numpy_image,
                                                 [cv2.IMWRITE_WEBP_QUALITY, quality])
                else:
                    raise ValueError(f"Unsupported format with OpenCV: {format}")
                
                if not success:
                    raise ValueError(f"Failed to encode image in {format} format")
                compressed_bytes = buffer.tobytes()
                
            else:
                # Fallback to PIL for compression
                from PIL import Image
                import io
                
                # Convert numpy to PIL Image
                if len(numpy_image.shape) == 3:
                    pil_image = Image.fromarray(numpy_image)
                else:
                    pil_image = Image.fromarray(numpy_image, 'L')
                
                # Compress using PIL
                buffer_io = io.BytesIO()
                if format.lower() == 'jpeg':
                    quality = quality or self.compression_config['jpeg_quality']
                    pil_image.save(buffer_io, format='JPEG', quality=quality)
                elif format.lower() == 'png':
                    pil_image.save(buffer_io, format='PNG')
                elif format.lower() == 'webp':
                    quality = quality or self.compression_config['webp_quality']
                    pil_image.save(buffer_io, format='WEBP', quality=quality)
                else:
                    raise ValueError(f"Unsupported format: {format}")
                
                compressed_bytes = buffer_io.getvalue()
            
            compression_info = {
                'format': format.lower(),
                'original_size': numpy_image.nbytes,
                'compressed_size': len(compressed_bytes),
                'compression_ratio': len(compressed_bytes) / numpy_image.nbytes,
                'quality': quality,
                'shape': numpy_image.shape,
                'dtype': str(numpy_image.dtype)
            }
            
            return compressed_bytes, compression_info
            
        except Exception as e:
            logger.error(f"Image compression failed: {e}")
            raise
    
    def send_vrs_frame_binary(self, 
                            session_id: str,
                            stream_id: str, 
                            numpy_image: np.ndarray,
                            frame_index: int,
                            capture_timestamp_ns: int,
                            format: str = 'jpeg',
                            quality: Optional[int] = None) -> Dict[str, Any]:
        """
        Send VRS frame using binary streaming architecture
        
        Flow:
        1. Generate unique frame ID
        2. Compress image to binary
        3. Send metadata to metadata topic
        4. Send binary to binary topic  
        5. Send registry entry for ID linking
        
        Returns:
            dict: Operation result with frame_id and metadata
        """
        
        frame_id = self.generate_frame_id(session_id, stream_id, frame_index)
        timestamp_iso = datetime.utcnow().isoformat()
        
        try:
            # Step 1: Compress image
            binary_data, compression_info = self.compress_image_binary(
                numpy_image, format, quality
            )
            
            # Step 2: Prepare metadata
            metadata = {
                'frame_id': frame_id,
                'session_id': session_id,
                'stream_id': stream_id,
                'frame_index': frame_index,
                'timestamp': timestamp_iso,
                'capture_timestamp_ns': capture_timestamp_ns,
                'device_timestamp_ns': capture_timestamp_ns,
                'image_width': int(numpy_image.shape[1]),
                'image_height': int(numpy_image.shape[0]),
                'channels': int(numpy_image.shape[2]) if len(numpy_image.shape) > 2 else 1,
                'compression': compression_info,
                'data_type': 'vrs_frame_binary'
            }
            
            # Step 3: Registry entry for ID linking
            registry_entry = {
                'frame_id': frame_id,
                'session_id': session_id,
                'stream_id': stream_id,
                'frame_index': frame_index,
                'capture_timestamp_ns': capture_timestamp_ns,
                'metadata_topic': self.topics['metadata'],
                'binary_topic': self.topics['binary'],
                'metadata_offset': None,  # Will be filled by consumer
                'binary_offset': None,    # Will be filled by consumer
                'compression_format': format,
                'compressed_size': len(binary_data),
                'compression_ratio': compression_info.get('compression_ratio'),
                'created_at': timestamp_iso,
                'size_bytes': len(binary_data)
            }
            
            producer = self._get_producer()
            
            # Step 4: Send to all three topics (parallel)
            futures = []
            
            # Metadata topic (JSON)
            metadata_future = producer.send(
                self.topics['metadata'],
                key=frame_id,
                value=json.dumps(metadata).encode('utf-8')
            )
            futures.append(('metadata', metadata_future))
            
            # Binary topic (Raw bytes)
            binary_future = producer.send(
                self.topics['binary'],
                key=frame_id.encode('utf-8'),
                value=binary_data
            )
            futures.append(('binary', binary_future))
            
            # Registry topic (JSON)
            registry_future = producer.send(
                self.topics['registry'],
                key=frame_id,
                value=json.dumps(registry_entry).encode('utf-8')
            )
            futures.append(('registry', registry_future))
            
            # Step 5: Wait for all sends to complete
            results = {}
            for topic_name, future in futures:
                try:
                    record_metadata = future.get(timeout=30)
                    results[topic_name] = {
                        'partition': record_metadata.partition,
                        'offset': record_metadata.offset,
                        'timestamp': record_metadata.timestamp
                    }
                except Exception as e:
                    logger.error(f"Failed to send to {topic_name}: {e}")
                    results[topic_name] = {'error': str(e)}
            
            logger.info(f"Binary frame sent: {frame_id} ({compression_info['compressed_size']} bytes)")
            
            return {
                'success': True,
                'frame_id': frame_id,
                'metadata': metadata,
                'compression': compression_info,
                'binary_size': len(binary_data),  # Size instead of raw data
                'kafka_results': results
            }
            
        except Exception as e:
            logger.error(f"Failed to send binary VRS frame: {e}")
            return {
                'success': False,
                'error': str(e),
                'frame_id': frame_id
            }
    
    def send_sensor_data(self, 
                        session_id: str,
                        sensor_type: str,
                        sensor_data: Dict[str, Any]) -> bool:
        """Send sensor data (eye gaze, SLAM, etc.) to sensor topic"""
        
        message = {
            'sensor_id': str(uuid.uuid4()),
            'session_id': session_id,
            'sensor_type': sensor_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': sensor_data,
            'data_type': f'mps_{sensor_type}'
        }
        
        try:
            producer = self._get_producer()
            future = producer.send(
                self.topics['sensor'],
                key=message['sensor_id'],
                value=json.dumps(message).encode('utf-8')
            )
            
            record_metadata = future.get(timeout=10)
            logger.debug(f"Sensor data sent: {sensor_type} to partition {record_metadata.partition}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send sensor data: {e}")
            return False
    
    def send_test_binary_frame(self, session_id: str = 'test-binary-session') -> Dict[str, Any]:
        """Send test binary frame for debugging"""
        
        # Create test image (640x480 RGB)
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        # Add some pattern for visual verification
        if HAS_OPENCV:
            cv2.rectangle(test_image, (100, 100), (540, 380), (0, 255, 0), 3)
            cv2.putText(test_image, 'TEST BINARY FRAME', (150, 250), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        else:
            # Simple pattern without OpenCV
            test_image[100:380, 100:540] = [0, 255, 0]  # Green rectangle
        
        return self.send_vrs_frame_binary(
            session_id=session_id,
            stream_id='214-1',  # RGB camera
            numpy_image=test_image,
            frame_index=1,
            capture_timestamp_ns=int(time.time_ns()),
            format='jpeg',
            quality=90
        )
    
    def close(self):
        """Close producer connection"""
        if self.producer:
            self.producer.close()
            logger.info("Binary Kafka producer closed")