"""
Django management command for testing VRS replay functionality
VRS 파일 반복 재생(replay) 기능 테스트 명령어
"""

import asyncio
import logging
from django.core.management.base import BaseCommand
from aria_streams.aria_device_producer import AriaDeviceKafkaProducer
import os

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test VRS replay functionality with various configurations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--vrs-file',
            default='data/mps_samples/sample.vrs',
            help='VRS file path for testing (default: data/mps_samples/sample.vrs)'
        )
        parser.add_argument(
            '--kafka-servers',
            default='ARD_KAFKA:9092',
            help='Kafka bootstrap servers (default: ARD_KAFKA:9092)'
        )
        parser.add_argument(
            '--replay-count',
            type=int,
            default=3,
            help='Number of replay cycles to test (default: 3)'
        )
        parser.add_argument(
            '--replay-delay',
            type=float,
            default=1.0,
            help='Delay between replays in seconds (default: 1.0)'
        )
        parser.add_argument(
            '--fps',
            type=int,
            default=10,
            help='Target frames per second for testing (default: 10)'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=30,
            help='Duration per cycle in seconds (default: 30)'
        )
        parser.add_argument(
            '--speed-test',
            action='store_true',
            help='Test different streaming speeds (0.5x, 1x, 2x, 5x)'
        )
    
    def handle(self, *args, **options):
        vrs_file = options['vrs_file']
        kafka_servers = options['kafka_servers']
        replay_count = options['replay_count']
        replay_delay = options['replay_delay']
        target_fps = options['fps']
        duration = options['duration']
        speed_test = options['speed_test']
        
        # Validate VRS file
        if not os.path.exists(vrs_file):
            self.stderr.write(f'❌ VRS file not found: {vrs_file}')
            return
        
        self.stdout.write('🧪 Starting VRS Replay Functionality Test')
        self.stdout.write('=' * 60)
        
        if speed_test:
            self.stdout.write('🎯 Testing different streaming speeds...')
            asyncio.run(self._test_different_speeds(vrs_file, kafka_servers, duration))
        else:
            self.stdout.write('🔄 Testing replay functionality...')
            asyncio.run(self._test_replay_functionality(
                vrs_file, kafka_servers, replay_count, replay_delay, target_fps, duration
            ))
    
    async def _test_replay_functionality(self, vrs_file, kafka_servers, replay_count, 
                                       replay_delay, target_fps, duration):
        """Test basic replay functionality"""
        
        self.stdout.write(f'📁 VRS File: {vrs_file}')
        self.stdout.write(f'🔗 Kafka Servers: {kafka_servers}')
        self.stdout.write(f'🔄 Replay Count: {replay_count}')
        self.stdout.write(f'⏳ Replay Delay: {replay_delay}s')
        self.stdout.write(f'🎯 Target FPS: {target_fps}')
        self.stdout.write(f'⏱️ Duration per cycle: {duration}s')
        self.stdout.write('-' * 40)
        
        # Create producer with replay enabled
        producer = AriaDeviceKafkaProducer(
            kafka_bootstrap_servers=kafka_servers,
            vrs_file_path=vrs_file,
            target_fps=target_fps,
            adaptive_quality=True,
            replay_enabled=True,
            replay_count=replay_count,
            replay_delay=replay_delay
        )
        
        try:
            self.stdout.write('🚀 Starting replay test...')
            await producer.start_real_time_streaming(duration)
            
            # Get final status
            status = producer.get_stream_status()
            self.stdout.write('\\n📊 Test Results:')
            self.stdout.write('-' * 30)
            self.stdout.write(f'Total Cycles Completed: {producer.current_replay}')
            self.stdout.write(f'Total Frames Sent: {status["frames_sent"]}')
            self.stdout.write(f'Total Bytes Sent: {status["bytes_sent"]:,}')
            self.stdout.write(f'Final FPS: {status["current_fps"]:.1f}')
            
            if producer.current_replay == replay_count:
                self.stdout.write('✅ Replay test PASSED - All cycles completed')
            else:
                self.stdout.write(f'⚠️ Replay test PARTIAL - Only {producer.current_replay}/{replay_count} cycles completed')
            
        except KeyboardInterrupt:
            self.stdout.write('\\n🛑 Test interrupted by user')
        except Exception as e:
            self.stderr.write(f'❌ Test failed: {e}')
        finally:
            producer.close()
            self.stdout.write('✅ Replay test completed')
    
    async def _test_different_speeds(self, vrs_file, kafka_servers, duration):
        """Test different streaming speeds"""
        
        speeds = [0.5, 1.0, 2.0, 5.0]
        results = []
        
        for speed in speeds:
            self.stdout.write(f'\\n🎯 Testing {speed}x speed...')
            self.stdout.write('-' * 30)
            
            target_fps = int(10 * speed)  # Base 10 FPS * speed multiplier
            
            producer = AriaDeviceKafkaProducer(
                kafka_bootstrap_servers=kafka_servers,
                vrs_file_path=vrs_file,
                target_fps=target_fps,
                adaptive_quality=True,
                replay_enabled=False  # Single cycle for speed test
            )
            
            try:
                start_time = asyncio.get_event_loop().time()
                await producer.start_real_time_streaming(duration)
                end_time = asyncio.get_event_loop().time()
                
                actual_duration = end_time - start_time
                status = producer.get_stream_status()
                actual_fps = status.get('current_fps', 0)
                
                results.append({
                    'speed': speed,
                    'target_fps': target_fps,
                    'actual_fps': actual_fps,
                    'duration': actual_duration,
                    'frames_sent': status.get('frames_sent', 0),
                    'bytes_sent': status.get('bytes_sent', 0)
                })
                
                self.stdout.write(f'Target FPS: {target_fps}, Actual FPS: {actual_fps:.1f}')
                self.stdout.write(f'Duration: {actual_duration:.1f}s')
                self.stdout.write(f'Frames Sent: {status.get("frames_sent", 0)}')
                
            except Exception as e:
                self.stderr.write(f'❌ Speed test {speed}x failed: {e}')
                results.append({
                    'speed': speed,
                    'error': str(e)
                })
            finally:
                producer.close()
        
        # Print summary
        self.stdout.write('\\n📊 Speed Test Summary:')
        self.stdout.write('=' * 50)
        self.stdout.write(f'{"Speed":<8} {"Target FPS":<12} {"Actual FPS":<12} {"Frames":<8} {"Status":<10}')
        self.stdout.write('-' * 50)
        
        for result in results:
            if 'error' in result:
                self.stdout.write(f'{result["speed"]}x{"":<6} {"N/A":<12} {"N/A":<12} {"0":<8} {"ERROR":<10}')
            else:
                fps_ratio = result['actual_fps'] / result['target_fps'] if result['target_fps'] > 0 else 0
                status = '✅ GOOD' if fps_ratio > 0.8 else '⚠️ SLOW'
                
                self.stdout.write(
                    f'{result["speed"]}x{"":<6} '
                    f'{result["target_fps"]:<12} '
                    f'{result["actual_fps"]:.1f}{"":<8} '
                    f'{result["frames_sent"]:<8} '
                    f'{status:<10}'
                )
        
        self.stdout.write('\\n✅ Speed test completed')

# Test commands to run:
# python ARD/manage.py test_vrs_replay
# python ARD/manage.py test_vrs_replay --replay-count 5 --fps 15
# python ARD/manage.py test_vrs_replay --speed-test
# python ARD/manage.py test_vrs_replay --replay-count 2 --replay-delay 0.5 --duration 20