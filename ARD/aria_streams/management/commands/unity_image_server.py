"""
Unity Image Server - 지속적으로 테스트 이미지 생성
Unity 테스트용으로 계속 새로운 이미지를 Kafka에 보내는 서버
"""

import asyncio
import time
import signal
import sys
from django.core.management.base import BaseCommand
from common.kafka.binary_producer import BinaryKafkaProducer
import cv2
import numpy as np

class Command(BaseCommand):
    help = 'Unity testing - continuously generate test images to Kafka'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fps',
            type=int,
            default=2,
            help='Images per second (default: 2)'
        )
        parser.add_argument(
            '--kafka-servers',
            default='localhost:9092',
            help='Kafka servers (default: localhost:9092)'
        )
    
    def handle(self, *args, **options):
        fps = options['fps']
        kafka_servers = options['kafka_servers']
        
        self.stdout.write('🎮 Unity Image Server Starting...')
        self.stdout.write('=' * 40)
        self.stdout.write(f'🎯 FPS: {fps}')
        self.stdout.write(f'🔗 Kafka: {kafka_servers}')
        self.stdout.write('Press Ctrl+C to stop')
        self.stdout.write('=' * 40)
        
        # Signal handlers
        def signal_handler(signum, frame):
            self.stdout.write('\\n🛑 Stopping Unity image server...')
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            producer = BinaryKafkaProducer(kafka_servers)
            frame_count = 0
            interval = 1.0 / fps
            
            while True:
                # 동적 테스트 이미지 생성
                test_image = self._create_dynamic_image(frame_count)
                
                # Kafka로 전송
                result = producer.send_vrs_frame_binary(
                    session_id='unity-live-test',
                    stream_id='unity-rgb',
                    numpy_image=test_image,
                    frame_index=frame_count,
                    capture_timestamp_ns=int(time.time_ns()),
                    format='jpeg',
                    quality=90
                )
                
                if result['success']:
                    size_kb = result['compression']['compressed_size'] / 1024
                    self.stdout.write(
                        f"📸 Unity Frame {frame_count}: {size_kb:.1f}KB "
                        f"(time: {time.strftime('%H:%M:%S')})"
                    )
                else:
                    self.stderr.write(f"❌ Frame {frame_count} failed")
                
                frame_count += 1
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.stdout.write('\\n✅ Unity image server stopped')
        except Exception as e:
            self.stderr.write(f'❌ Error: {e}')
        finally:
            if 'producer' in locals():
                producer.close()
    
    def _create_dynamic_image(self, frame_count: int) -> np.ndarray:
        """동적 테스트 이미지 생성"""
        # 640x480 이미지 생성
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 시간에 따라 변하는 배경색
        t = time.time()
        bg_r = int((np.sin(t * 0.5) + 1) * 127)
        bg_g = int((np.sin(t * 0.3) + 1) * 127)  
        bg_b = int((np.sin(t * 0.7) + 1) * 127)
        
        image[:, :] = [bg_r, bg_g, bg_b]
        
        # 프레임 번호 (큰 글씨)
        cv2.putText(
            image, 
            f'FRAME {frame_count}', 
            (150, 200), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            2, 
            (255, 255, 255), 
            4
        )
        
        # 현재 시간
        current_time = time.strftime('%H:%M:%S')
        cv2.putText(
            image,
            current_time,
            (200, 280),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 0),
            3
        )
        
        # Unity 텍스트
        cv2.putText(
            image,
            'FOR UNITY',
            (220, 350),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 255, 255),
            2
        )
        
        # 움직이는 원
        center_x = int(320 + 200 * np.sin(t * 2))
        center_y = int(240 + 100 * np.cos(t * 1.5))
        cv2.circle(image, (center_x, center_y), 30, (255, 0, 255), -1)
        
        # 진행 바
        progress_width = int((frame_count % 100) * 4)
        cv2.rectangle(image, (120, 400), (120 + progress_width, 420), (0, 255, 0), -1)
        cv2.rectangle(image, (120, 400), (520, 420), (255, 255, 255), 2)
        
        return image