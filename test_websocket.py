#!/usr/bin/env python3
"""
WebSocket client to test Aria real-time streaming
"""

import asyncio
import websockets
import json
from datetime import datetime

async def test_aria_websocket():
    """Test WebSocket connection to Aria streaming"""
    
    # WebSocket URLs to test
    websocket_urls = [
        "ws://127.0.0.1:8001/ws/aria-stream/",
        "ws://127.0.0.1:8001/ws/vrs-images/",
        "ws://127.0.0.1:8001/ws/aria-realtime/test_session/"
    ]
    
    for ws_url in websocket_urls:
        print(f"\n🔗 Testing WebSocket: {ws_url}")
        try:
            async with websockets.connect(ws_url) as websocket:
                print(f"✅ Connected to {ws_url}")
                
                # Send test message
                test_message = {
                    "type": "test_message",
                    "message": "Hello from test client",
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(test_message))
                print(f"📤 Sent: {test_message}")
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    print(f"📥 Received: {response_data}")
                except asyncio.TimeoutError:
                    print("⏰ No response received within 5 seconds")
                
        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
    
    print("\n🧪 Testing Aria command functionality...")
    try:
        async with websockets.connect("ws://127.0.0.1:8001/ws/aria-realtime/test_session/") as websocket:
            print("✅ Connected to Aria realtime consumer")
            
            # Test Aria command
            aria_command = {
                "type": "aria_command",
                "command": "start_recording",
                "params": {
                    "quality": "high",
                    "duration": 60
                }
            }
            
            await websocket.send(json.dumps(aria_command))
            print(f"📤 Sent Aria command: {aria_command}")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            print(f"📥 Aria command response: {response_data}")
            
            # Test data request
            data_request = {
                "type": "request_latest_data",
                "data_type": "vrs",
                "limit": 1
            }
            
            await websocket.send(json.dumps(data_request))
            print(f"📤 Sent data request: {data_request}")
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            print(f"📥 Data response: {response_data}")
            
    except Exception as e:
        print(f"❌ Aria functionality test failed: {str(e)}")

if __name__ == "__main__":
    print("🚀 Starting WebSocket tests for Aria streaming...")
    asyncio.run(test_aria_websocket())
    print("✨ WebSocket tests completed!")