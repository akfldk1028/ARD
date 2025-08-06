"""
Project Aria VRS 데이터와 Kafka 연결 테스트
공식 ipynb 패턴을 유지하며 구현
"""
import asyncio
import os
import sys
import time
from django.core.management.base import BaseCommand
from django.conf import settings

# kafka 모듈을 import 경로에 추가
kafka_path = os.path.join(os.path.dirname(settings.BASE_DIR), 'kafka')
if kafka_path not in sys.path:
    sys.path.append(kafka_path)

try:
    from kafka.producers.aria_kafka_producer import AriaKafkaStreamer
    from kafka.consumers.aria_kafka_consumer import AriaKafkaConsumer
except ImportError as e:
    print(f"Kafka 모듈 import 오류: {e}")
    print("kafka 폴더가 올바른 위치에 있는지 확인하세요")


class Command(BaseCommand):
    help = 'Project Aria VRS 데이터를 Kafka로 스트리밍 테스트 (공식 패턴 유지)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            choices=['producer', 'consumer', 'summary'],
            default='summary',
            help='실행 모드: producer, consumer, 또는 summary'
        )
        parser.add_argument(
            '--images',
            type=int,
            default=2,
            help='스트리밍할 이미지 개수'
        )
        parser.add_argument(
            '--sensors',
            type=int,
            default=3,
            help='스트리밍할 센서 데이터 개수'
        )

    def handle(self, *args, **options):
        mode = options['mode']
        max_images = options['images']
        max_sensors = options['sensors']
        
        self.stdout.write(f"=== Kafka-Aria 연결 테스트 시작 ===")
        self.stdout.write(f"모드: {mode}, 이미지: {max_images}개, 센서: {max_sensors}개")
        
        if mode == 'summary':
            asyncio.run(self.test_summary())
        elif mode == 'producer':
            asyncio.run(self.test_producer(max_images, max_sensors))
        elif mode == 'consumer':
            asyncio.run(self.test_consumer())

    async def test_summary(self):
        """스트림 요약 정보만 확인"""
        self.stdout.write("\\n=== VRS 데이터 요약 정보 ===")
        
        try:
            from kafka.producers.aria_kafka_producer import AriaKafkaStreamer
            
            streamer = AriaKafkaStreamer()
            
            # VRS 파일 경로
            vrs_file = os.path.join(settings.BASE_DIR, 'data', 'mps_samples', 'sample.vrs')
            
            if not os.path.exists(vrs_file):
                self.stdout.write(self.style.ERROR(f"VRS 파일을 찾을 수 없습니다: {vrs_file}"))
                return
            
            # VRS Provider만 초기화
            if not streamer.setup_vrs_provider(vrs_file):
                self.stdout.write(self.style.ERROR("VRS Provider 초기화 실패"))
                return
            
            # 스트림 요약 출력
            summary = streamer.get_stream_summary()
            for name, info in summary.items():
                self.stdout.write(f"  {name}: {info}")
            
            self.stdout.write(self.style.SUCCESS("\\n요약 정보 확인 완료"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"요약 테스트 오류: {e}"))

    async def test_producer(self, max_images: int, max_sensors: int):
        """Producer 테스트"""
        self.stdout.write("\\n=== Kafka Producer 테스트 ===")
        
        try:
            from kafka.producers.aria_kafka_producer import AriaKafkaStreamer
            
            streamer = AriaKafkaStreamer()
            
            # VRS 파일 경로
            vrs_file = os.path.join(settings.BASE_DIR, 'data', 'mps_samples', 'sample.vrs')
            
            # 초기화
            if not streamer.setup_kafka_producer():
                self.stdout.write(self.style.ERROR("Kafka Producer 초기화 실패"))
                return
            
            if not streamer.setup_vrs_provider(vrs_file):
                self.stdout.write(self.style.ERROR("VRS Provider 초기화 실패"))
                return
            
            # 균형잡힌 데이터 스트리밍
            self.stdout.write(f"균형잡힌 데이터 스트리밍 시작...")
            await streamer.stream_balanced_data_to_kafka(
                max_images=max_images, 
                max_sensors=max_sensors
            )
            
            self.stdout.write(self.style.SUCCESS("Producer 테스트 완료"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Producer 테스트 오류: {e}"))
        finally:
            if 'streamer' in locals():
                streamer.close()

    async def test_consumer(self):
        """Consumer 테스트 (5초간)"""
        self.stdout.write("\\n=== Kafka Consumer 테스트 ===")
        
        try:
            from kafka.consumers.aria_kafka_consumer import AriaKafkaConsumer
            
            consumer = AriaKafkaConsumer()
            topics = ['vrs-frames', 'sensor-data', 'stream-camera-rgb']
            
            if not consumer.setup_kafka_consumer(topics):
                self.stdout.write(self.style.ERROR("Consumer 초기화 실패"))
                return
            
            self.stdout.write("Consumer 5초간 실행...")
            
            # 5초 타임아웃으로 Consumer 실행
            consumer_task = asyncio.create_task(consumer.consume_messages())
            
            try:
                await asyncio.wait_for(consumer_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.stdout.write("5초 타임아웃 - Consumer 테스트 완료")
                consumer.stop()
                consumer_task.cancel()
            
            self.stdout.write(self.style.SUCCESS("Consumer 테스트 완료"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Consumer 테스트 오류: {e}"))
        finally:
            if 'consumer' in locals():
                consumer.stop()