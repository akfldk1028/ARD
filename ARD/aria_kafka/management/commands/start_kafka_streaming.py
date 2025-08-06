"""
Django Management Command - Kafka 스트리밍 시작
"""
import os
import sys
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

# Kafka 시스템 import
from kafka.consumers.streaming_consumer import get_global_consumer
from kafka.managers.stream_manager import get_global_manager

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Kafka 스트리밍 시스템 시작'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vrs-file',
            type=str,
            help='VRS 파일 경로',
            default='ARD/data/mps_samples/sample.vrs'
        )
        parser.add_argument(
            '--fps',
            type=float,
            help='프레임 레이트',
            default=10.0
        )
        parser.add_argument(
            '--streams',
            nargs='+',
            help='시작할 스트림 목록 (기본: 모두)',
            default=None
        )
        parser.add_argument(
            '--consumer-only',
            action='store_true',
            help='Consumer만 시작'
        )
        parser.add_argument(
            '--producer-only',
            action='store_true',
            help='Producer만 시작'
        )

    def handle(self, *args, **options):
        vrs_file = options['vrs_file']
        fps = options['fps']
        streams = options['streams']
        consumer_only = options['consumer_only']
        producer_only = options['producer_only']
        
        # VRS 파일 경로 확인
        if not os.path.isabs(vrs_file):
            vrs_file = os.path.join(settings.BASE_DIR, '..', vrs_file)
        
        if not os.path.exists(vrs_file) and not consumer_only:
            self.stdout.write(self.style.ERROR(f'VRS 파일을 찾을 수 없습니다: {vrs_file}'))
            return
        
        try:
            # Consumer 시작
            if not producer_only:
                self.stdout.write('Kafka Consumer 시작...')
                consumer = get_global_consumer()
                self.stdout.write(self.style.SUCCESS('✓ Consumer 시작됨'))
            
            # Producer 시작
            if not consumer_only:
                self.stdout.write(f'Kafka Producer 시작 (VRS: {vrs_file})...')
                manager = get_global_manager(vrs_file)
                
                if streams:
                    # 특정 스트림만 시작
                    for stream_name in streams:
                        success = manager.start_producer_stream(stream_name, fps)
                        if success:
                            self.stdout.write(self.style.SUCCESS(f'✓ {stream_name} 스트림 시작됨'))
                        else:
                            self.stdout.write(self.style.ERROR(f'✗ {stream_name} 스트림 시작 실패'))
                else:
                    # 모든 스트림 시작
                    results = manager.start_all_streams(fps)
                    for stream_name, success in results.items():
                        if success:
                            self.stdout.write(self.style.SUCCESS(f'✓ {stream_name} 스트림 시작됨'))
                        else:
                            self.stdout.write(self.style.ERROR(f'✗ {stream_name} 스트림 시작 실패'))
            
            self.stdout.write(self.style.SUCCESS('\n=== Kafka 스트리밍 시스템 실행 중 ==='))
            self.stdout.write('Ctrl+C로 종료하세요.')
            
            # 계속 실행
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stdout.write('\n\n종료 중...')
                if not consumer_only:
                    manager.close()
                self.stdout.write(self.style.SUCCESS('Kafka 스트리밍 종료됨'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'오류 발생: {str(e)}'))
            import traceback
            traceback.print_exc()