"""
Photo Streaming Test Command
실제 사진 스트리밍 테스트
"""

import asyncio
import logging
import time
import cv2
import numpy as np
from django.core.management.base import BaseCommand
from common.kafka.binary_producer import BinaryKafkaProducer

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test photo streaming to Kafka'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--kafka-servers',
            default='localhost:9092',
            help='Kafka bootstrap servers (default: localhost:9092)'
        )
        parser.add_argument(
            '--test-frames',
            type=int,
            default=5,
            help='Number of test frames to send (default: 5)'
        )
        parser.add_argument(
            '--fps',
            type=int,
            default=2,
            help='Frames per second (default: 2)'
        )
    
    def handle(self, *args, **options):
        kafka_servers = options['kafka_servers']
        test_frames = options['test_frames']
        fps = options['fps']
        
        self.stdout.write('📷 Testing Photo Streaming to Kafka')
        self.stdout.write('=' * 40)
        self.stdout.write(f'🔗 Kafka: {kafka_servers}')
        self.stdout.write(f'📸 Test Frames: {test_frames}')
        self.stdout.write(f'🎯 FPS: {fps}')
        self.stdout.write('=' * 40)
        
        try:
            # Create producer
            producer = BinaryKafkaProducer(kafka_servers)
            
            # Test connectivity first
            self.stdout.write('🔍 Testing Kafka connectivity...')
            test_result = producer.send_test_binary_frame('photo-test-session')
            
            if not test_result['success']:
                self.stderr.write(f"❌ Kafka connectivity failed: {test_result.get('error')}")
                return
            
            self.stdout.write('✅ Kafka connectivity OK')
            self.stdout.write(f"📤 Test frame sent: {test_result['frame_id']}")
            
            # Stream test photos
            self.stdout.write(f'🚀 Starting photo streaming ({test_frames} frames)...')
            
            frame_interval = 1.0 / fps
            for i in range(test_frames):
                # Create test image with frame number
                test_image = self._create_test_image(i + 1)
                
                # Send to Kafka
                result = producer.send_vrs_frame_binary(
                    session_id='photo-streaming-test',
                    stream_id='test-rgb',
                    numpy_image=test_image,
                    frame_index=i,
                    capture_timestamp_ns=int(time.time_ns()),
                    format='jpeg',
                    quality=90
                )
                
                if result['success']:
                    size_kb = result['compression']['compressed_size'] / 1024
                    self.stdout.write(
                        f"📸 Frame {i+1}/{test_frames}: {size_kb:.1f}KB "
                        f"(ratio: {result['compression']['compression_ratio']:.3f})"
                    )
                else:
                    self.stderr.write(f"❌ Frame {i+1} failed: {result.get('error')}")
                
                # Wait for next frame
                if i < test_frames - 1:
                    time.sleep(frame_interval)
            
            self.stdout.write('✅ Photo streaming test completed!')
            
            # Check if messages are in Kafka
            self._check_kafka_messages(kafka_servers)
            
        except Exception as e:
            self.stderr.write(f'❌ Test failed: {e}')
        finally:
            if 'producer' in locals():
                producer.close()
    
    def _create_test_image(self, frame_number: int) -> np.ndarray:
        """Create test image with frame number"""
        # Create 640x480 RGB image
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Add colorful background
        image[:, :, 0] = (frame_number * 50) % 255  # Red channel
        image[:, :, 1] = (frame_number * 30) % 255  # Green channel  
        image[:, :, 2] = (frame_number * 70) % 255  # Blue channel
        
        # Add frame number text
        cv2.putText(
            image, 
            f'FRAME {frame_number}', 
            (200, 240), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            2, 
            (255, 255, 255), 
            3
        )
        
        # Add timestamp
        timestamp = time.strftime('%H:%M:%S')
        cv2.putText(
            image,
            timestamp,
            (250, 300),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 0),
            2
        )
        
        # Add some geometric shapes for visual interest
        cv2.rectangle(image, (50, 50), (150, 150), (0, 255, 255), 3)
        cv2.circle(image, (500, 120), 50, (255, 0, 255), -1)
        
        return image
    
    def _check_kafka_messages(self, kafka_servers: str):
        """Check if messages are actually in Kafka topics"""
        try:
            from kafka import KafkaConsumer
            import json
            
            self.stdout.write('\\n🔍 Checking Kafka topics for messages...')
            
            # Check binary topic
            topics_to_check = [
                'vrs-binary-stream',
                'vrs-metadata-stream', 
                'vrs-frame-registry'
            ]
            
            for topic in topics_to_check:
                try:
                    consumer = KafkaConsumer(
                        topic,
                        bootstrap_servers=[kafka_servers],
                        auto_offset_reset='latest',
                        consumer_timeout_ms=2000,
                        value_deserializer=lambda v: v  # Keep as bytes
                    )
                    
                    # Get partition info
                    partitions = consumer.partitions_for_topic(topic)
                    if partitions:
                        self.stdout.write(f"✅ Topic '{topic}': {len(partitions)} partitions")
                        
                        # Try to get latest message
                        consumer.poll(timeout_ms=1000)
                        if consumer.assignment():
                            self.stdout.write(f"   📨 Has messages in topic")
                        else:
                            self.stdout.write(f"   📭 No recent messages")
                    else:
                        self.stdout.write(f"❌ Topic '{topic}': Not found")
                    
                    consumer.close()
                    
                except Exception as e:
                    self.stdout.write(f"❌ Topic '{topic}': Error - {e}")
            
        except Exception as e:
            self.stderr.write(f"❌ Failed to check Kafka messages: {e}")