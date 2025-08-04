"""
Test Unity WebSocket Connection
실제로 WebSocket이 동작하는지 테스트
"""

import asyncio
import websockets
import json
import time
from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test Unity WebSocket real-time streaming'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--host',
            default='localhost',
            help='WebSocket server host (default: localhost)'
        )
        parser.add_argument(
            '--port', 
            type=int,
            default=8000,
            help='WebSocket server port (default: 8000)'
        )
        parser.add_argument(
            '--session-id',
            default='unity-test-session',
            help='Test session ID (default: unity-test-session)'
        )
        
    def handle(self, *args, **options):
        host = options['host']
        port = options['port']
        session_id = options['session_id']
        
        self.stdout.write('🎮 Unity WebSocket Test Client Starting...')
        self.stdout.write('=' * 50)
        self.stdout.write(f'🌐 Host: {host}:{port}')
        self.stdout.write(f'🎯 Session: {session_id}')
        self.stdout.write('Press Ctrl+C to stop')
        self.stdout.write('=' * 50)
        
        # Run async WebSocket client
        asyncio.run(self.test_websocket_connection(host, port, session_id))
    
    async def test_websocket_connection(self, host, port, session_id):
        """Test WebSocket connection and streaming"""
        ws_url = f"ws://{host}:{port}/ws/unity/stream/{session_id}/"
        
        try:
            self.stdout.write(f"🔗 Connecting to: {ws_url}")
            
            async with websockets.connect(ws_url) as websocket:
                self.stdout.write("✅ WebSocket connected successfully!")
                
                # Send start streaming command
                start_command = {
                    'type': 'start_streaming',
                    'config': {
                        'rgb': True,
                        'slam': False,
                        'quality': 'medium'
                    }
                }
                
                await websocket.send(json.dumps(start_command))
                self.stdout.write("📤 Sent start streaming command")
                
                # Listen for messages
                frame_count = 0
                start_time = time.time()
                
                try:
                    async for message in websocket:
                        data = json.loads(message)
                        message_type = data.get('type')
                        
                        if message_type == 'connection_established':
                            self.stdout.write("🎯 Connection established")
                            self.stdout.write(f"   Server capabilities: {data.get('server_capabilities', {})}")
                            
                        elif message_type == 'streaming_started':
                            self.stdout.write("🚀 Streaming started")
                            self.stdout.write(f"   Config: {data.get('config', {})}")
                            
                        elif message_type == 'real_time_frame':
                            frame_count += 1
                            frame_id = data.get('frame_id', 'unknown')
                            size_bytes = data.get('size_bytes', 0)
                            size_kb = size_bytes / 1024 if size_bytes else 0
                            
                            # Show frame info every 5 frames
                            if frame_count % 5 == 0:
                                elapsed = time.time() - start_time
                                fps = frame_count / elapsed if elapsed > 0 else 0
                                
                                self.stdout.write(
                                    f"📸 Frame {frame_count}: {frame_id} "
                                    f"({size_kb:.1f}KB) - {fps:.1f} fps"
                                )
                            
                            # Test for 50 frames then stop
                            if frame_count >= 50:
                                self.stdout.write(f"🎉 Received {frame_count} frames successfully!")
                                
                                # Send stop command
                                stop_command = {'type': 'stop_streaming'}
                                await websocket.send(json.dumps(stop_command))
                                self.stdout.write("🛑 Sent stop streaming command")
                                break
                        
                        elif message_type == 'streaming_stopped':
                            self.stdout.write("✅ Streaming stopped")
                            break
                            
                        elif message_type == 'error':
                            self.stderr.write(f"❌ Server error: {data.get('message')}")
                            break
                            
                        else:
                            self.stdout.write(f"📨 Message: {message_type}")
                
                except websockets.exceptions.ConnectionClosed:
                    self.stdout.write("🔌 WebSocket connection closed")
                    
        except ConnectionRefusedError:
            self.stderr.write("❌ Connection refused - is the Django server running?")
        except Exception as e:
            self.stderr.write(f"❌ Error: {e}")