"""
Kafka 스트리밍 테스트 Django Management Command
"""
import asyncio
import os
import sys
from django.core.management.base import BaseCommand
from django.conf import settings

# kafka 모듈을 import 경로에 추가
sys.path.append(os.path.join(settings.BASE_DIR, 'kafka'))

from kafka.producers.aria_kafka_producer import AriaKafkaStreamer
from kafka.consumers.aria_kafka_consumer import AriaKafkaConsumer


class Command(BaseCommand):
    help = 'Project Aria VRS 데이터를 Kafka로 스트리밍 테스트'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            choices=['producer', 'consumer', 'both'],
            default='both',
            help='실행 모드: producer, consumer, 또는 both'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=30,
            help='스트리밍 지속 시간 (초)'
        )
        parser.add_argument(
            '--max-images',
            type=int,
            default=4,
            help='최대 이미지 개수'
        )
        parser.add_argument(
            '--max-sensors',
            type=int,
            default=6,
            help='최대 센서 데이터 개수'
        )

    def handle(self, *args, **options):
        mode = options['mode']
        duration = options['duration']
        max_images = options['max_images']
        max_sensors = options['max_sensors']
        
        self.stdout.write(f"Kafka 스트리밍 테스트 시작 - 모드: {mode}")
        
        if mode == 'producer':
            asyncio.run(self.test_producer(duration, max_images, max_sensors))
        elif mode == 'consumer':
            asyncio.run(self.test_consumer())
        else:  # both
            asyncio.run(self.test_both(duration, max_images, max_sensors))

    async def test_producer(self, duration: int, max_images: int, max_sensors: int):
        """Producer 테스트"""
        self.stdout.write("=== Producer 테스트 시작 ===")
        
        streamer = AriaKafkaStreamer()
        
        # VRS 파일 경로
        vrs_file = os.path.join(settings.BASE_DIR, 'data', 'mps_samples', 'sample.vrs')
        
        try:
            # 초기화
            if not streamer.setup_kafka_producer():
                self.stdout.write(self.style.ERROR("Kafka Producer 초기화 실패"))
                return
            
            if not streamer.setup_vrs_provider(vrs_file):
                self.stdout.write(self.style.ERROR("VRS Provider 초기화 실패"))
                return
            
            # 스트림 요약 출력
            summary = streamer.get_stream_summary()
            self.stdout.write("\\n=== 스트림 요약 ===")
            for name, info in summary.items():
                self.stdout.write(f"{name}: {info}")
            
            # 균형잡힌 데이터 스트리밍
            self.stdout.write(f"\\n균형잡힌 데이터 스트리밍 (이미지: {max_images}, 센서: {max_sensors})")
            await streamer.stream_balanced_data_to_kafka(
                max_images=max_images, 
                max_sensors=max_sensors
            )
            
            # 연속 데이터 스트리밍
            self.stdout.write(f"\\n연속 데이터 스트리밍 ({duration}초)")
            await streamer.stream_continuous_data(duration_seconds=duration)
            
            self.stdout.write(self.style.SUCCESS("Producer 테스트 완료"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Producer 테스트 오류: {e}"))
        finally:
            streamer.close()

    async def test_consumer(self):
        """Consumer 테스트"""
        self.stdout.write("=== Consumer 테스트 시작 ===")
        
        consumer = AriaKafkaConsumer()
        topics = ['vrs-frames', 'sensor-data', 'image-metadata', 'stream-camera-rgb', 'stream-imu-right']
        
        try:
            if not consumer.setup_kafka_consumer(topics):
                self.stdout.write(self.style.ERROR("Kafka Consumer 초기화 실패"))
                return
            
            self.stdout.write("Consumer 시작 중... (Ctrl+C로 중지)")
            await consumer.consume_messages()
            
        except KeyboardInterrupt:
            self.stdout.write("\\n사용자 중단 요청")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Consumer 테스트 오류: {e}"))
        finally:
            consumer.stop()

    async def test_both(self, duration: int, max_images: int, max_sensors: int):
        """Producer와 Consumer 동시 테스트"""
        self.stdout.write("=== Producer + Consumer 통합 테스트 ===")
        
        # Consumer를 백그라운드에서 시작
        consumer = AriaKafkaConsumer()
        topics = ['vrs-frames', 'sensor-data', 'image-metadata', 'stream-camera-rgb', 'stream-imu-right']
        
        try:
            if not consumer.setup_kafka_consumer(topics):
                self.stdout.write(self.style.ERROR("Consumer 초기화 실패"))
                return
            
            # Consumer 백그라운드 태스크 시작
            consumer_task = asyncio.create_task(consumer.consume_messages())
            
            # 잠시 대기 후 Producer 시작
            await asyncio.sleep(2)
            
            # Producer 테스트 실행
            await self.test_producer(duration, max_images, max_sensors)
            
            # 추가로 5초 더 Consumer 실행
            self.stdout.write("\\nConsumer 5초 더 실행 중...")
            await asyncio.sleep(5)
            
            self.stdout.write(self.style.SUCCESS("통합 테스트 완료"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"통합 테스트 오류: {e}"))
        finally:
            consumer.stop()
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await consumer_task
                except asyncio.CancelledError:
                    pass