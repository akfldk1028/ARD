#!/usr/bin/env python3
"""
Simple WebSocket test client to debug connection issues
"""
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://127.0.0.1:8000/ws/aria-sessions/555e9dd7-da2f-4446-9a9a-31cffc23df0c/stream/"
    
    try:
        print(f"Connecting to {uri}")
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            
            # Wait for connection message
            greeting = await websocket.recv()
            print(f"Received: {greeting}")
            
            # Send start streaming command
            start_command = {
                "command": "start_streaming",
                "streams": ["camera-rgb"],
                "fps": 1,
                "max_frames": 3,
                "include_images": True
            }
            
            await websocket.send(json.dumps(start_command))
            print(f"Sent: {start_command}")
            
            # Receive messages
            for i in range(10):  # Listen for 10 messages
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    print(f"[{i+1}] Type: {data.get('type')}, Frame: {data.get('frame_number', 'N/A')}")
                    
                    if data.get('type') == 'streaming_completed':
                        break
                        
                except asyncio.TimeoutError:
                    print("Timeout waiting for message")
                    break
                    
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())