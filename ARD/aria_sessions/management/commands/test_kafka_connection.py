"""
Kafka 연결 및 Project Aria 스트리밍 테스트
패키지 충돌 문제 해결
"""
import os
import sys
import time
import json
import asyncio
import base64
from django.core.management.base import BaseCommand
from django.conf import settings

# kafka-python 라이브러리 import
import kafka
from kafka import KafkaProducer, KafkaConsumer

# Project Aria tools import
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions  
from projectaria_tools.core.stream_id import RecordableTypeId, StreamId


class Command(BaseCommand):
    help = 'Kafka와 Project Aria VRS 데이터 연결 테스트'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-type',
            type=str,
            choices=['kafka-only', 'vrs-only', 'integration'],
            default='kafka-only',
            help='테스트 타입'
        )

    def handle(self, *args, **options):
        test_type = options['test_type']
        
        self.stdout.write(f"=== {test_type} 테스트 시작 ===")
        
        if test_type == 'kafka-only':
            self.test_kafka_only()
        elif test_type == 'vrs-only':
            self.test_vrs_only()
        else:
            asyncio.run(self.test_integration())

    def test_kafka_only(self):
        """Kafka 연결만 테스트"""
        self.stdout.write("1. Kafka Producer 테스트...")
        
        try:
            producer = KafkaProducer(
                bootstrap_servers=['localhost:9092'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            test_data = {
                'test': 'kafka_connection',
                'timestamp': time.time(),
                'message': 'Hello from Django!'
            }
            
            future = producer.send('vrs-frames', value=test_data)
            result = future.get(timeout=10)
            
            self.stdout.write(self.style.SUCCESS(f"Producer OK: {result.topic}:{result.partition}:{result.offset}"))
            producer.close()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Producer 오류: {e}"))
            return
        
        self.stdout.write("\\n2. Kafka Consumer 테스트...")
        
        try:
            consumer = KafkaConsumer(
                'vrs-frames',
                bootstrap_servers=['localhost:9092'],
                group_id='test-group',
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                consumer_timeout_ms=3000
            )
            
            message_count = 0
            for message in consumer:
                self.stdout.write(f"수신: {message.topic}:{message.partition}:{message.offset}")
                self.stdout.write(f"데이터: {message.value}")
                message_count += 1
                if message_count >= 1:
                    break
            
            consumer.close()
            self.stdout.write(self.style.SUCCESS("Consumer OK"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Consumer 오류: {e}"))

    def test_vrs_only(self):
        """VRS 데이터 읽기만 테스트"""
        self.stdout.write("VRS 데이터 프로바이더 테스트...")
        
        # VRS 파일 경로
        vrs_file = os.path.join(settings.BASE_DIR, 'data', 'mps_samples', 'sample.vrs')
        
        if not os.path.exists(vrs_file):
            self.stdout.write(self.style.ERROR(f"VRS 파일 없음: {vrs_file}"))
            return
        
        try:
            # ipynb 패턴으로 데이터 프로바이더 생성
            print(f"Creating data provider from {vrs_file}")
            provider = data_provider.create_vrs_data_provider(vrs_file)
            
            if not provider:
                self.stdout.write(self.style.ERROR("Invalid vrs data provider"))
                return
            
            # ipynb와 동일한 스트림 매핑
            stream_mappings = {
                "camera-slam-left": StreamId("1201-1"),
                "camera-slam-right": StreamId("1201-2"),
                "camera-rgb": StreamId("214-1"),
                "camera-eyetracking": StreamId("211-1"),
            }
            
            self.stdout.write("\\n=== 스트림 정보 ===")
            for stream_name, stream_id in stream_mappings.items():
                num_frames = provider.get_num_data(stream_id)
                if num_frames > 0:
                    config = provider.get_image_configuration(stream_id)
                    self.stdout.write(f"{stream_name}: {num_frames}프레임, {config.image_width}x{config.image_height}")
                else:
                    self.stdout.write(f"{stream_name}: 데이터 없음")
            
            # 첫 번째 RGB 이미지 테스트
            rgb_stream_id = StreamId("214-1")
            if provider.get_num_data(rgb_stream_id) > 0:
                image_data = provider.get_image_data_by_index(rgb_stream_id, 0)
                if image_data[0]:
                    image_array = image_data[0].to_numpy_array()
                    self.stdout.write(f"RGB 이미지 테스트: shape={image_array.shape}")
                    self.stdout.write(self.style.SUCCESS("VRS 데이터 읽기 성공"))
                else:
                    self.stdout.write(self.style.ERROR("RGB 이미지 데이터 없음"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"VRS 테스트 오류: {e}"))

    async def test_integration(self):
        """통합 테스트 - VRS + Kafka"""
        self.stdout.write("\\n=== 통합 테스트: VRS -> Kafka ===")
        
        # VRS 파일 경로
        vrs_file = os.path.join(settings.BASE_DIR, 'data', 'mps_samples', 'sample.vrs')
        
        try:
            # 1. VRS 데이터 프로바이더 생성
            provider = data_provider.create_vrs_data_provider(vrs_file)
            if not provider:
                self.stdout.write(self.style.ERROR("VRS Provider 생성 실패"))
                return
            
            # 2. Kafka Producer 생성
            producer = KafkaProducer(
                bootstrap_servers=['localhost:9092'],
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                max_request_size=10485760  # 10MB
            )
            
            # 3. RGB 이미지 1개 Kafka로 전송
            rgb_stream_id = StreamId("214-1")
            if provider.get_num_data(rgb_stream_id) > 0:
                image_data = provider.get_image_data_by_index(rgb_stream_id, 0)
                if image_data[0]:
                    image_array = image_data[0].to_numpy_array()
                    
                    # 이미지를 base64로 인코딩
                    from PIL import Image
                    import io
                    
                    pil_image = Image.fromarray(image_array)
                    buffer = io.BytesIO()
                    pil_image.save(buffer, format='JPEG', quality=70)
                    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                    # Kafka 메시지 구성
                    kafka_data = {
                        'stream_name': 'camera-rgb',
                        'stream_id': str(rgb_stream_id),
                        'capture_timestamp_ns': image_data[1].capture_timestamp_ns,
                        'image_shape': list(image_array.shape),
                        'image_data': image_base64,
                        'data_type': 'integration_test',
                        'processing_timestamp': time.time()
                    }
                    
                    # Kafka로 전송
                    future = producer.send('stream-camera-rgb', value=kafka_data)
                    result = future.get(timeout=10)
                    
                    self.stdout.write(self.style.SUCCESS(
                        f"통합 테스트 성공: VRS RGB -> Kafka {result.topic}:{result.partition}:{result.offset}"
                    ))
                    self.stdout.write(f"이미지 크기: {image_array.shape}, 압축 후: {len(image_base64)} bytes")
            
            producer.close()
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"통합 테스트 오류: {e}"))
        
        self.stdout.write(self.style.SUCCESS("모든 테스트 완료"))