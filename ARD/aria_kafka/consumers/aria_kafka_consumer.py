"""
Kafka에서 Project Aria 데이터를 소비하는 Consumer
공식 패턴을 유지하며 Django 모델과 연결
"""
import json
import time
import base64
from typing import Dict, List, Optional
import asyncio
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import numpy as np
from PIL import Image
import io

from django.conf import settings
import django
if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
    django.setup()

from streams.models import (
    AriaSession, VRSStream, EyeGazeData, 
    HandTrackingData, SLAMTrajectoryData, KafkaConsumerStatus
)
from ..config.kafka_config import KafkaConfig


class AriaKafkaConsumer:
    """Project Aria Kafka 데이터 소비자"""
    
    def __init__(self, kafka_config: KafkaConfig = None):
        self.kafka_config = kafka_config or KafkaConfig()
        self.consumer = None
        self.is_running = False
        self.current_session = None
        
        # 토픽별 처리 함수 매핑
        self.topic_handlers = {
            'vrs-frames': self.handle_vrs_frame,
            'sensor-data': self.handle_sensor_data,
            'image-metadata': self.handle_image_metadata,
            'stream-camera-rgb': self.handle_rgb_stream,
            'stream-imu-right': self.handle_imu_stream,
        }
    
    def setup_kafka_consumer(self, topics: List[str]):
        """Kafka Consumer 초기화"""
        try:
            self.consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                group_id='aria-data-consumer',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                max_poll_records=self.kafka_config.max_batch_size,
                fetch_max_bytes=self.kafka_config.max_message_size
            )
            print(f"[OK] Kafka Consumer 연결 성공 - 토픽: {topics}")
            return True
        except Exception as e:
            print(f"[ERROR] Kafka Consumer 연결 실패: {e}")
            return False
    
    def get_or_create_session(self) -> AriaSession:
        """현재 세션 가져오기 또는 생성"""
        if not self.current_session:
            self.current_session = AriaSession.objects.create(
                session_name=f"kafka_stream_{int(time.time())}",
                session_type="kafka_streaming",
                metadata={'source': 'kafka_consumer', 'started_at': time.time()}
            )
            print(f"[OK] 새 세션 생성: {self.current_session.session_name}")
        
        return self.current_session
    
    async def handle_vrs_frame(self, message):
        """VRS 프레임 데이터 처리"""
        try:
            data = message.value
            session = self.get_or_create_session()
            
            # 이미지 데이터 디코딩
            image_data = None
            if 'image_data' in data:
                image_bytes = base64.b64decode(data['image_data'])
                image_data = image_bytes
            
            # VRSStream 모델에 저장 (기존 패턴 유지)
            vrs_stream = VRSStream.objects.create(
                session=session,
                stream_name=data.get('stream_name', ''),
                stream_id=data.get('stream_id', ''),
                capture_timestamp_ns=data.get('capture_timestamp_ns', 0),
                device_timestamp_ns=data.get('device_timestamp_ns', 0),
                image_data=image_data,
                image_shape=data.get('image_shape', []),
                frame_index=data.get('frame_index', 0),
                kafka_offset=message.offset,
                kafka_partition=message.partition,
                processing_metadata={
                    'topic': message.topic,
                    'processing_timestamp': data.get('processing_timestamp'),
                    'data_type': data.get('data_type', 'image')
                }
            )
            
            return vrs_stream
            
        except Exception as e:
            print(f"[ERROR] VRS 프레임 처리 오류: {e}")
            return None
    
    async def handle_sensor_data(self, message):
        """센서 데이터 처리"""
        try:
            data = message.value
            session = self.get_or_create_session()
            
            # 센서 타입에 따라 적절한 모델에 저장
            sensor_type = data.get('sensor_type', '')
            stream_label = data.get('stream_label', '')
            
            if 'imu' in stream_label.lower():
                # IMU 데이터를 SLAMTrajectoryData로 저장 (기존 패턴)
                slam_data = SLAMTrajectoryData.objects.create(
                    session=session,
                    tracking_timestamp_ns=data.get('device_timestamp_ns', 0),
                    transform_world_device_tx=0.0,  # IMU 데이터이므로 기본값
                    transform_world_device_ty=0.0,
                    transform_world_device_tz=0.0,
                    transform_world_device_qx=0.0,
                    transform_world_device_qy=0.0,
                    transform_world_device_qz=0.0,
                    transform_world_device_qw=1.0,
                    utc_timestamp_ns=data.get('host_timestamp_ns', 0),
                    kafka_offset=message.offset,
                    quality_score=1.0,
                    metadata={
                        'sensor_type': sensor_type,
                        'stream_label': stream_label,
                        'original_data_index': data.get('data_index', 0),
                        'source': 'kafka_imu_sensor'
                    }
                )
                return slam_data
            
            return None
            
        except Exception as e:
            print(f"[ERROR] 센서 데이터 처리 오류: {e}")
            return None
    
    async def handle_image_metadata(self, message):
        """이미지 메타데이터 처리"""
        try:
            data = message.value
            session = self.get_or_create_session()
            
            # 메타데이터를 VRSStream에 저장
            vrs_stream = VRSStream.objects.create(
                session=session,
                stream_name=data.get('stream_name', ''),
                stream_id=data.get('stream_id', ''),
                capture_timestamp_ns=data.get('capture_timestamp_ns', 0),
                device_timestamp_ns=data.get('device_timestamp_ns', 0),
                image_data=None,  # 메타데이터만
                image_shape=data.get('image_shape', []),
                frame_index=data.get('frame_index', 0),
                kafka_offset=message.offset,
                kafka_partition=message.partition,
                processing_metadata={
                    'topic': message.topic,
                    'data_type': 'metadata',
                    'original_data': data
                }
            )
            
            return vrs_stream
            
        except Exception as e:
            print(f"[ERROR] 이미지 메타데이터 처리 오류: {e}")
            return None
    
    async def handle_rgb_stream(self, message):
        """RGB 스트림 처리"""
        return await self.handle_vrs_frame(message)
    
    async def handle_imu_stream(self, message):
        """IMU 스트림 처리"""
        return await self.handle_sensor_data(message)
    
    async def consume_messages(self):
        """메시지 소비 루프"""
        if not self.consumer:
            print("[ERROR] Consumer가 초기화되지 않았습니다")
            return
        
        self.is_running = True
        print("[OK] Kafka 메시지 소비 시작...")
        
        message_count = 0
        
        try:
            while self.is_running:
                # 메시지 배치 가져오기
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                if not message_batch:
                    await asyncio.sleep(0.1)
                    continue
                
                # 각 토픽의 메시지 처리
                for topic_partition, messages in message_batch.items():
                    topic = topic_partition.topic
                    handler = self.topic_handlers.get(topic)
                    
                    if not handler:
                        print(f"[WARNING] 알 수 없는 토픽: {topic}")
                        continue
                    
                    for message in messages:
                        try:
                            result = await handler(message)
                            if result:
                                message_count += 1
                                
                                if message_count % 20 == 0:  # 20개마다 로그
                                    print(f"[OK] 처리됨: {message_count}개 메시지")
                                    
                        except Exception as e:
                            print(f"[ERROR] 메시지 처리 오류 ({topic}): {e}")
                
                # Consumer 상태 업데이트
                if message_count % 100 == 0:  # 100개마다 상태 업데이트
                    await self.update_consumer_status(message_count)
                    
        except KeyboardInterrupt:
            print("[INFO] 사용자 중단 요청")
        except Exception as e:
            print(f"[ERROR] Consumer 오류: {e}")
        finally:
            self.is_running = False
            print(f"[OK] Consumer 종료 - 총 {message_count}개 메시지 처리")
    
    async def update_consumer_status(self, message_count: int):
        """Consumer 상태 업데이트"""
        try:
            status, created = KafkaConsumerStatus.objects.get_or_create(
                consumer_id='aria-kafka-consumer',
                defaults={'is_active': True, 'messages_processed': 0}
            )
            
            status.is_active = self.is_running
            status.messages_processed = message_count
            status.last_heartbeat = time.time()
            status.error_count = 0  # 성공적으로 실행 중
            status.save()
            
        except Exception as e:
            print(f"[ERROR] Consumer 상태 업데이트 실패: {e}")
    
    def stop(self):
        """Consumer 중지"""
        self.is_running = False
        if self.consumer:
            self.consumer.close()


# 실행 함수
async def start_aria_kafka_consumer():
    """Aria Kafka Consumer 시작"""
    consumer = AriaKafkaConsumer()
    
    # 모든 토픽 구독
    topics = ['vrs-frames', 'sensor-data', 'image-metadata', 'stream-camera-rgb', 'stream-imu-right']
    
    if not consumer.setup_kafka_consumer(topics):
        return
    
    print("Aria Kafka Consumer 시작 중...")
    await consumer.consume_messages()


if __name__ == "__main__":
    asyncio.run(start_aria_kafka_consumer())