"""
Unity Integration Views
Unity에서 실시간 이미지를 가져가는 간단한 API
"""

import base64
import json
import logging
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import time

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class UnityLatestFrameView(View):
    """
    Unity용 최신 프레임 API
    GET /api/unity/latest-frame/ → 최신 이미지 반환
    """
    
    def get(self, request):
        """최신 프레임을 Kafka에서 바로 가져와서 Unity에 전달"""
        try:
            # Kafka에서 최신 바이너리 프레임 가져오기
            frame_data = self._get_latest_frame_from_kafka()
            
            if not frame_data:
                return JsonResponse({
                    'success': False,
                    'error': 'No frames available',
                    'timestamp': datetime.now().isoformat()
                })
            
            return JsonResponse({
                'success': True,
                'frame_id': frame_data['frame_id'],
                'timestamp': frame_data['timestamp'],
                'image_data': frame_data['image_base64'],  # Base64 인코딩된 JPEG
                'size_bytes': frame_data['size_bytes'],
                'format': 'jpeg',
                'stream_type': frame_data.get('stream_type', 'rgb')
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting latest frame for Unity: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    def _get_latest_frame_from_kafka(self):
        """Kafka에서 최신 바이너리 프레임 가져오기"""
        try:
            # Kafka Consumer 생성 (최신 메시지만)
            consumer = KafkaConsumer(
                'vrs-binary-stream',
                bootstrap_servers=['ARD_KAFKA:9092'],
                auto_offset_reset='latest',
                consumer_timeout_ms=3000,  # 3초 타임아웃
                group_id=f'unity-api-{int(time.time())}',  # 유니크한 그룹 ID
                value_deserializer=lambda v: v,  # 바이너리 그대로
                key_deserializer=lambda k: k.decode('utf-8') if k else None
            )
            
            # 최신 메시지 1개 가져오기
            message_pack = consumer.poll(timeout_ms=3000, max_records=1)
            consumer.close()
            
            if not message_pack:
                logger.warning("No new messages in Kafka")
                return None
            
            # 첫 번째 메시지 처리
            for topic_partition, messages in message_pack.items():
                if messages:
                    message = messages[0]  # 최신 메시지
                    
                    # 바이너리 데이터를 Base64로 인코딩
                    image_base64 = base64.b64encode(message.value).decode('utf-8')
                    
                    return {
                        'frame_id': message.key or f'frame_{int(time.time())}',
                        'timestamp': datetime.now().isoformat(),
                        'image_base64': image_base64,
                        'size_bytes': len(message.value),
                        'stream_type': 'rgb'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting frame from Kafka: {e}")
            return None


@method_decorator(csrf_exempt, name='dispatch')
class UnityStreamingStatusView(View):
    """
    Unity용 스트리밍 상태 API
    GET /api/unity/status/ → 스트리밍 상태 확인
    """
    
    def get(self, request):
        """스트리밍 상태 반환"""
        try:
            # Kafka 토픽 상태 확인
            kafka_status = self._check_kafka_topics()
            
            return JsonResponse({
                'success': True,
                'streaming_active': kafka_status['has_messages'],
                'kafka_topics': kafka_status['topics'],
                'timestamp': datetime.now().isoformat(),
                'api_endpoints': {
                    'latest_frame': '/api/unity/latest-frame/',
                    'status': '/api/unity/status/',
                    'stream_info': '/api/unity/stream-info/'
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Error checking streaming status: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
    
    def _check_kafka_topics(self):
        """Kafka 토픽 상태 확인"""
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=['ARD_KAFKA:9092'],
                consumer_timeout_ms=1000
            )
            
            topics = consumer.list_consumer_group_offsets('test-group')
            available_topics = ['vrs-binary-stream', 'vrs-metadata-stream', 'vrs-frame-registry']
            
            # 토픽에 메시지가 있는지 확인
            has_messages = False
            for topic in available_topics:
                try:
                    partitions = consumer.partitions_for_topic(topic)
                    if partitions:
                        has_messages = True
                        break
                except:
                    continue
            
            consumer.close()
            
            return {
                'has_messages': has_messages,
                'topics': available_topics
            }
            
        except Exception as e:
            logger.error(f"❌ Error checking Kafka topics: {e}")
            return {
                'has_messages': False,
                'topics': []
            }


@method_decorator(csrf_exempt, name='dispatch')
class UnityStreamInfoView(View):
    """
    Unity용 스트림 정보 API
    GET /api/unity/stream-info/ → 스트림 세부 정보
    """
    
    def get(self, request):
        """스트림 세부 정보 반환"""
        try:
            return JsonResponse({
                'success': True,
                'stream_info': {
                    'supported_formats': ['jpeg'],
                    'supported_streams': ['rgb', 'slam_left', 'slam_right'],
                    'max_resolution': {'width': 2048, 'height': 2048},
                    'compression_quality': 90,
                    'typical_frame_size': '15-20KB'
                },
                'usage': {
                    'latest_frame': 'GET /api/unity/latest-frame/ → 최신 프레임',
                    'polling_recommended': '1-5 FPS (1초에 1-5번 요청)',
                    'response_format': 'JSON with base64 encoded JPEG'
                },
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })


@method_decorator(csrf_exempt, name='dispatch')
class UnityWebSocketInfoView(View):
    """
    Unity WebSocket 연결 정보 API
    GET /api/unity/websocket-info/ → WebSocket 연결 방법 안내
    """
    
    def get(self, request):
        """WebSocket 연결 정보 반환"""
        try:
            return JsonResponse({
                'success': True,
                'websocket_info': {
                    'websocket_url': 'ws://localhost:8000/ws/unity/stream/{session_id}/',
                    'websocket_protocol': 'ws',
                    'supported_messages': [
                        'start_streaming',
                        'stop_streaming', 
                        'configure_streams',
                        'client_performance',
                        'request_frame',
                        'ping'
                    ],
                    'response_types': [
                        'connection_established',
                        'streaming_started',
                        'real_time_frame',
                        'streaming_stopped',
                        'error',
                        'pong'
                    ]
                },
                'usage': {
                    'connection': 'Connect to ws://localhost:8000/ws/unity/stream/your-session-id/',
                    'start_streaming': 'Send: {"type": "start_streaming", "config": {"rgb": true, "quality": "medium"}}',
                    'real_time_frames': 'Receive: {"type": "real_time_frame", "image_data": "base64-jpeg", ...}'
                },
                'performance': {
                    'streaming_mode': 'Real-time Kafka to WebSocket',
                    'latency': '<100ms',
                    'max_fps': '30fps',
                    'frame_format': 'Base64 encoded JPEG'
                },
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })


# Unity C# 예제 코드 반환
class UnityExampleView(View):
    """Unity C# WebSocket 예제 코드"""
    
    def get(self, request):
        csharp_code = '''
// Unity C# WebSocket 실시간 스트리밍 예제
// Install: WebSocket Sharp or NativeWebSocket package
using System;
using UnityEngine;
using WebSocketSharp;
using Newtonsoft.Json;

public class AriaRealTimeStreaming : MonoBehaviour
{
    public string serverHost = "localhost";
    public int serverPort = 8000;
    public string sessionId = "unity-live-session";
    public RawImage targetImage;
    
    private WebSocket webSocket;
    private bool isStreaming = false;
    
    void Start()
    {
        string wsUrl = $"ws://{serverHost}:{serverPort}/ws/unity/stream/{sessionId}/";
        webSocket = new WebSocket(wsUrl);
        
        webSocket.OnOpen += (sender, e) => {
            Debug.Log("WebSocket connected!");
            StartStreaming();
        };
        
        webSocket.OnMessage += (sender, e) => {
            var data = JsonConvert.DeserializeObject<dynamic>(e.Data);
            string messageType = data.type;
            
            if (messageType == "real_time_frame")
            {
                // Base64 → Texture2D 변환
                string imageBase64 = data.image_data;
                byte[] imageBytes = Convert.FromBase64String(imageBase64);
                Texture2D texture = new Texture2D(2, 2);
                texture.LoadImage(imageBytes);
                
                // UI 업데이트 (메인 스레드에서)
                UnityMainThreadDispatcher.Instance().Enqueue(() => {
                    targetImage.texture = texture;
                });
                
                Debug.Log($"Frame: {data.frame_id} ({data.size_bytes} bytes)");
            }
        };
        
        webSocket.Connect();
    }
    
    void StartStreaming()
    {
        var command = new {
            type = "start_streaming",
            config = new { rgb = true, quality = "medium" }
        };
        webSocket.Send(JsonConvert.SerializeObject(command));
    }
    
    void OnDestroy()
    {
        webSocket?.Close();
    }
}

// Note: 실제 프로젝트에서는 UnityMainThreadDispatcher 구현 필요
// WebSocket Sharp 패키지 설치: Window > Package Manager > Add from Git URL
// https://github.com/sta/websocket-sharp.git
'''
        
        return HttpResponse(csharp_code, content_type='text/plain')