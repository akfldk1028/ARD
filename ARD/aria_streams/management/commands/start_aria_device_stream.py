"""
Django management command for Aria Device Stream to Kafka
실시간 Aria 장비 데이터를 Kafka로 스트리밍하는 명령어
"""

import asyncio
import logging
from django.core.management.base import BaseCommand
from aria_streams.aria_device_producer import AriaDeviceKafkaProducer
import os

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start real-time Aria device streaming to Kafka'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--vrs-file',
            default='data/mps_samples/sample.vrs',
            help='VRS file path for simulation (default: data/mps_samples/sample.vrs)'
        )
        parser.add_argument(
            '--kafka-servers',
            default='ARD_KAFKA:9092',
            help='Kafka bootstrap servers (default: ARD_KAFKA:9092)'
        )
        parser.add_argument(
            '--duration',
            type=int,
            help='Duration to stream in seconds (optional, default: unlimited)'
        )
        parser.add_argument(
            '--fps',
            type=int,
            default=30,
            help='Target frames per second (default: 30)'
        )
        parser.add_argument(
            '--adaptive-quality',
            action='store_true',
            default=True,
            help='Enable adaptive quality control (default: enabled)'
        )
        parser.add_argument(
            '--rgb-only',
            action='store_true',
            help='Stream RGB camera only'
        )
        parser.add_argument(
            '--slam-only',
            action='store_true',
            help='Stream SLAM cameras only'
        )
        parser.add_argument(
            '--no-imu',
            action='store_true',
            help='Disable IMU streaming'
        )
        parser.add_argument(
            '--quality',
            type=int,
            default=90,
            help='JPEG compression quality (1-100, default: 90)'
        )
        parser.add_argument(
            '--replay',
            action='store_true',
            help='Enable VRS file replay (loop indefinitely)'
        )
        parser.add_argument(
            '--replay-count',
            type=int,
            help='Number of times to replay (default: infinite if --replay enabled)'
        )
        parser.add_argument(
            '--replay-delay',
            type=float,
            default=2.0,
            help='Delay between replays in seconds (default: 2.0)'
        )
    
    def handle(self, *args, **options):
        vrs_file = options['vrs_file']
        kafka_servers = options['kafka_servers']
        duration = options.get('duration')
        target_fps = options['fps']
        adaptive_quality = options['adaptive_quality']
        
        # Validate VRS file
        if not os.path.exists(vrs_file):
            self.stderr.write(f'❌ VRS file not found: {vrs_file}')
            return
        
        # Display configuration
        self.stdout.write('🚀 Starting Aria Real-Time Device Stream to Kafka')
        self.stdout.write('=' * 50)
        self.stdout.write(f'📁 VRS File: {vrs_file}')
        self.stdout.write(f'🔗 Kafka Servers: {kafka_servers}')
        self.stdout.write(f'🎯 Target FPS: {target_fps}')
        self.stdout.write(f'⏱️  Duration: {duration}s' if duration else '⏱️  Duration: Unlimited')
        self.stdout.write(f'🎛️  Adaptive Quality: {"Enabled" if adaptive_quality else "Disabled"}')
        self.stdout.write(f'🖼️  JPEG Quality: {options["quality"]}')
        self.stdout.write(f'🔄 VRS Replay: {"Enabled" if options["replay"] else "Disabled"}')
        if options['replay']:
            if options.get('replay_count'):
                self.stdout.write(f'📊 Replay Count: {options["replay_count"]} times')
            else:
                self.stdout.write(f'📊 Replay Count: Infinite')
            self.stdout.write(f'⏳ Replay Delay: {options["replay_delay"]}s')
        
        # Stream configuration based on options
        stream_config = {}
        if options['rgb_only']:
            stream_config = {
                'rgb': {'enabled': True},
                'slam_left': {'enabled': False},
                'slam_right': {'enabled': False},
                'imu': {'enabled': False}
            }
            self.stdout.write('📹 Streaming: RGB Camera Only')
        elif options['slam_only']:
            stream_config = {
                'rgb': {'enabled': False},
                'slam_left': {'enabled': True},
                'slam_right': {'enabled': True},
                'imu': {'enabled': False}
            }
            self.stdout.write('📹 Streaming: SLAM Cameras Only')
        else:
            stream_config = {
                'rgb': {'enabled': True},
                'slam_left': {'enabled': True},
                'slam_right': {'enabled': True},
                'imu': {'enabled': not options['no_imu']}
            }
            enabled_streams = []
            if stream_config['rgb']['enabled']:
                enabled_streams.append('RGB')
            if stream_config['slam_left']['enabled']:
                enabled_streams.append('SLAM-L/R')
            if stream_config['imu']['enabled']:
                enabled_streams.append('IMU')
            self.stdout.write(f'📹 Streaming: {", ".join(enabled_streams)}')
        
        self.stdout.write('=' * 50)
        
        # Create producer with custom configuration
        producer = AriaDeviceKafkaProducer(
            kafka_bootstrap_servers=kafka_servers,
            vrs_file_path=vrs_file,
            target_fps=target_fps,
            adaptive_quality=adaptive_quality,
            replay_enabled=options['replay'],
            replay_count=options.get('replay_count'),
            replay_delay=options['replay_delay']
        )
        
        # Apply stream configuration
        if stream_config:
            for stream_name, config in stream_config.items():
                if stream_name in producer.stream_config:
                    producer.stream_config[stream_name].update(config)
        
        # Apply quality settings
        for stream_name in ['rgb', 'slam_left', 'slam_right']:
            if stream_name in producer.stream_config:
                producer.stream_config[stream_name]['quality'] = options['quality']
        
        try:
            # Start streaming
            self.stdout.write('🔄 Initializing streaming...')
            
            async def run_streaming():
                await producer.start_real_time_streaming(duration)
            
            asyncio.run(run_streaming())
            
        except KeyboardInterrupt:
            self.stdout.write('\\n🛑 Streaming interrupted by user')
        except Exception as e:
            self.stderr.write(f'❌ Streaming error: {e}')
        finally:
            producer.close()
            self.stdout.write('✅ Aria device streaming stopped')
    
    def print_performance_stats(self, producer):
        """Print final performance statistics"""
        status = producer.get_stream_status()
        
        self.stdout.write('\\n📊 Final Performance Statistics:')
        self.stdout.write('-' * 30)
        self.stdout.write(f'Frames Sent: {status["frames_sent"]}')
        self.stdout.write(f'Bytes Sent: {status["bytes_sent"]:,}')
        self.stdout.write(f'Final FPS: {status["current_fps"]:.1f}')