"""
Real Aria Device Streaming Command with VRS Fallback
실제 Aria 장비 스트리밍 + VRS 샘플 fallback
"""

import asyncio
import logging
import os
from django.core.management.base import BaseCommand
from aria_streams.aria_real_device_stream import AriaRealDeviceStreamer

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start real Aria device streaming with VRS fallback'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--device-ip',
            help='Device IP address for Wi-Fi streaming'
        )
        parser.add_argument(
            '--streaming-mode',
            choices=['usb', 'wifi'],
            default='usb',
            help='Streaming mode: usb or wifi (default: usb)'
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
            '--force-vrs',
            action='store_true',
            help='Force VRS simulation mode (skip device detection)'
        )
        parser.add_argument(
            '--vrs-file',
            default='data/mps_samples/sample.vrs',
            help='VRS file for fallback mode (default: data/mps_samples/sample.vrs)'
        )
        parser.add_argument(
            '--fps',
            type=int,
            default=30,
            help='Target FPS for VRS simulation (default: 30)'
        )
    
    def handle(self, *args, **options):
        device_ip = options.get('device_ip')
        streaming_mode = options['streaming_mode']
        kafka_servers = options['kafka_servers']
        duration = options.get('duration')
        force_vrs = options['force_vrs']
        vrs_file = options['vrs_file']
        target_fps = options['fps']
        
        # Display configuration
        self.stdout.write('🚀 Starting Aria Real-Time Streaming')
        self.stdout.write('=' * 50)
        
        if force_vrs:
            self.stdout.write('🔧 Mode: VRS Simulation (Forced)')
        else:
            self.stdout.write(f'📡 Mode: {streaming_mode.upper()} Device Stream')
            if streaming_mode == 'wifi' and device_ip:
                self.stdout.write(f'🌐 Device IP: {device_ip}')
        
        self.stdout.write(f'🔗 Kafka: {kafka_servers}')
        self.stdout.write(f'⏱️  Duration: {duration}s' if duration else '⏱️  Duration: Unlimited')
        self.stdout.write('=' * 50)
        
        try:
            if force_vrs:
                # 강제 VRS 모드
                self._run_vrs_simulation(vrs_file, kafka_servers, duration, target_fps)
            else:
                # 실제 장비 연결 시도 → VRS fallback
                self._run_with_fallback(
                    device_ip, streaming_mode, kafka_servers, 
                    duration, vrs_file, target_fps
                )
                
        except KeyboardInterrupt:
            self.stdout.write('\\n🛑 Streaming interrupted by user')
        except Exception as e:
            self.stderr.write(f'❌ Streaming error: {e}')
    
    def _run_with_fallback(self, device_ip, streaming_mode, kafka_servers, 
                          duration, vrs_file, target_fps):
        """실제 장비 연결 시도 후 VRS fallback"""
        
        async def try_real_device():
            streamer = AriaRealDeviceStreamer(
                kafka_bootstrap_servers=kafka_servers,
                device_ip=device_ip,
                streaming_mode=streaming_mode
            )
            
            # 장비 연결 시도
            self.stdout.write('🔍 Attempting to connect to Aria device...')
            
            if await streamer.connect_to_device():
                self.stdout.write('✅ Connected to real Aria device!')
                self.stdout.write('📡 Starting real-time device streaming...')
                
                await streamer.start_real_time_streaming(duration)
                return True
            else:
                self.stdout.write('❌ Failed to connect to real Aria device')
                return False
        
        # 실제 장비 연결 시도
        try:
            device_connected = asyncio.run(try_real_device())
            
            if device_connected:
                self.stdout.write('✅ Real device streaming completed')
                return
                
        except Exception as e:
            self.stdout.write(f'❌ Device connection failed: {e}')
        
        # VRS fallback
        self.stdout.write('🔄 Falling back to VRS simulation...')
        self._run_vrs_simulation(vrs_file, kafka_servers, duration, target_fps)
    
    def _run_vrs_simulation(self, vrs_file, kafka_servers, duration, target_fps):
        """VRS 시뮬레이션 실행"""
        
        # VRS 파일 존재 확인
        if not os.path.exists(vrs_file):
            self.stderr.write(f'❌ VRS file not found: {vrs_file}')
            return
        
        self.stdout.write('📁 VRS Simulation Mode')
        self.stdout.write(f'📄 File: {vrs_file}')
        self.stdout.write(f'🎯 Target FPS: {target_fps}')
        self.stdout.write('🔄 Starting VRS simulation...')
        
        # VRS 기반 시뮬레이션 실행
        from aria_streams.aria_device_producer import AriaDeviceKafkaProducer
        
        async def run_vrs_simulation():
            producer = AriaDeviceKafkaProducer(
                kafka_bootstrap_servers=kafka_servers,
                vrs_file_path=vrs_file,
                target_fps=target_fps,
                adaptive_quality=True
            )
            
            try:
                await producer.start_real_time_streaming(duration)
            finally:
                producer.close()
        
        asyncio.run(run_vrs_simulation())
        self.stdout.write('✅ VRS simulation completed')
    
    def print_device_detection_help(self):
        """장비 감지 도움말 출력"""
        self.stdout.write('\\n🔧 Device Detection Help:')
        self.stdout.write('-' * 30)
        self.stdout.write('USB Mode:')
        self.stdout.write('  - Connect Aria glasses via USB cable')
        self.stdout.write('  - Ensure device drivers are installed')
        self.stdout.write('')
        self.stdout.write('Wi-Fi Mode:')
        self.stdout.write('  - Connect glasses and computer to same network')
        self.stdout.write('  - Use --device-ip <IP_ADDRESS>')
        self.stdout.write('')
        self.stdout.write('VRS Simulation:')
        self.stdout.write('  - Use --force-vrs to skip device detection')
        self.stdout.write('  - Specify custom VRS file with --vrs-file')