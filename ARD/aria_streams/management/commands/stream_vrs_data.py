import asyncio
import logging
from django.core.management.base import BaseCommand
from aria_streams.vrs_reader import VRSKafkaStreamer
import os

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Stream VRS and MPS data to Kafka'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--vrs-file',
            required=True,
            help='Path to VRS file'
        )
        parser.add_argument(
            '--mps-data-path',
            required=True,
            help='Path to MPS sample data directory'
        )
        parser.add_argument(
            '--duration',
            type=int,
            help='Duration to stream in seconds (optional)'
        )
        parser.add_argument(
            '--kafka-servers',
            default='kafka-all:9092',
            help='Kafka bootstrap servers'
        )
        parser.add_argument(
            '--stream-type',
            choices=['vrs', 'mps', 'both'],
            default='both',
            help='Type of data to stream'
        )
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Loop streaming continuously (repeat the VRS file)'
        )
        parser.add_argument(
            '--loop-delay',
            type=int,
            default=2,
            help='Delay between loops in seconds (default: 2)'
        )
    
    def handle(self, *args, **options):
        vrs_file = options['vrs_file']
        mps_data_path = options['mps_data_path']
        
        # Validate paths
        if not os.path.exists(vrs_file):
            self.stderr.write(f'VRS file not found: {vrs_file}')
            return
        
        if not os.path.exists(mps_data_path):
            self.stderr.write(f'MPS data path not found: {mps_data_path}')
            return
        
        self.stdout.write(f'Starting data streaming...')
        self.stdout.write(f'VRS file: {vrs_file}')
        self.stdout.write(f'MPS data: {mps_data_path}')
        
        streamer = VRSKafkaStreamer(
            vrs_file_path=vrs_file,
            mps_data_path=mps_data_path,
            kafka_bootstrap_servers=options['kafka_servers']
        )
        
        try:
            # Loop streaming if requested
            loop_streaming = options.get('loop', False)
            loop_delay = options.get('loop_delay', 2)
            
            if loop_streaming:
                self.stdout.write('🔄 Loop streaming enabled - will repeat VRS file continuously')
            
            async def run_streaming_session():
                # Create tasks based on stream type
                tasks = []
                
                if options['stream_type'] in ['vrs', 'both']:
                    tasks.append(streamer.stream_vrs_data(options.get('duration')))
                    
                if options['stream_type'] in ['mps', 'both']:
                    tasks.append(streamer.stream_mps_data(options.get('duration')))
                
                # Run streaming tasks
                await asyncio.gather(*tasks)
            
            async def run_with_loop():
                loop_count = 0
                while True:
                    loop_count += 1
                    if loop_streaming:
                        self.stdout.write(f'🚀 Starting streaming loop #{loop_count}')
                    
                    await run_streaming_session()
                    
                    if not loop_streaming:
                        break
                        
                    self.stdout.write(f'✅ Loop #{loop_count} completed. Waiting {loop_delay}s before next loop...')
                    await asyncio.sleep(loop_delay)
            
            asyncio.run(run_with_loop())
            
        except KeyboardInterrupt:
            self.stdout.write('\nStopping data streaming...')
            streamer.stop_streaming()
        except Exception as e:
            self.stderr.write(f'Streaming error: {e}')
        finally:
            streamer.close()
            self.stdout.write('Data streaming stopped.')