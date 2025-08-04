"""
Real-Time Consumer Management Command
실시간 스트리밍용 Consumer 관리
"""

import time
import signal
import sys
from django.core.management.base import BaseCommand
from aria_streams.real_time_consumer import AriaRealTimeConsumer

class Command(BaseCommand):
    help = 'Start real-time Kafka consumer for Unity streaming'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--kafka-servers',
            default='ARD_KAFKA:9092',
            help='Kafka bootstrap servers (default: ARD_KAFKA:9092)'
        )
        parser.add_argument(
            '--status-interval',
            type=int,
            default=10,
            help='Status logging interval in seconds (default: 10)'
        )
    
    def handle(self, *args, **options):
        kafka_servers = options['kafka_servers']
        status_interval = options['status_interval']
        
        self.stdout.write('🚀 Starting Real-Time Kafka Consumer for Unity')
        self.stdout.write('=' * 50)
        self.stdout.write(f'🔗 Kafka: {kafka_servers}')
        self.stdout.write(f'📊 Status Interval: {status_interval}s')
        self.stdout.write('=' * 50)
        
        # Create consumer
        consumer = AriaRealTimeConsumer(bootstrap_servers=kafka_servers)
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.stdout.write('\\n🛑 Received shutdown signal...')
            consumer.stop_consuming()
            self.stdout.write('✅ Real-time consumer stopped')
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Start consuming
            consumer.start_consuming()
            self.stdout.write('✅ Real-time consumer started')
            self.stdout.write('📡 Streaming Kafka → WebSocket → Unity')
            self.stdout.write('Press Ctrl+C to stop')
            
            # Status monitoring loop
            while consumer.is_consuming:
                time.sleep(status_interval)
                
                status = consumer.get_status()
                self.stdout.write(
                    f"📊 Status: {status['frames_processed']} frames | "
                    f"Uptime: {status['uptime_seconds']:.0f}s | "
                    f"Topics: {len(status['topics'])}"
                )
                
        except KeyboardInterrupt:
            self.stdout.write('\\n🛑 Interrupted by user')
        except Exception as e:
            self.stderr.write(f'❌ Consumer error: {e}')
        finally:
            consumer.stop_consuming()
            self.stdout.write('🔌 Real-time consumer shutdown complete')