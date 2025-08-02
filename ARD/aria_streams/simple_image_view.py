"""
간단한 이미지 뷰어 - Kafka에서 직접 이미지 가져오기
"""

from django.http import HttpResponse, JsonResponse
from django.views import View
from kafka import KafkaConsumer
import json
import base64
import os

class SimpleImageView(View):
    """간단한 이미지 뷰 - Kafka에서 직접 가져오기"""
    
    def get(self, request):
        """최근 이미지를 Kafka에서 가져와서 표시"""
        try:
            # Kafka 컨슈머 설정
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
            
            # 메타데이터 토픽에서 최근 이미지 정보 가져오기
            metadata_consumer = KafkaConsumer(
                'vrs-metadata-stream',
                bootstrap_servers=bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                consumer_timeout_ms=5000,
                auto_offset_reset='latest'
            )
            
            # 바이너리 토픽에서 실제 이미지 데이터 가져오기
            binary_consumer = KafkaConsumer(
                'vrs-binary-stream',
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=5000,
                auto_offset_reset='latest'
            )
            
            # 최근 메타데이터 가져오기
            latest_metadata = None
            for message in metadata_consumer:
                latest_metadata = message.value
                break
            
            if not latest_metadata:
                return JsonResponse({
                    'error': 'No image metadata found in Kafka',
                    'suggestion': 'Generate an image first using: POST /api/v1/aria/binary/test-message/'
                })
            
            # 해당하는 바이너리 데이터 가져오기
            frame_id = latest_metadata['frame_id']
            binary_data = None
            
            for message in binary_consumer:
                if message.key and message.key.decode('utf-8') == frame_id:
                    binary_data = message.value
                    break
            
            metadata_consumer.close()
            binary_consumer.close()
            
            if not binary_data:
                return JsonResponse({
                    'error': 'Binary data not found',
                    'frame_id': frame_id,
                    'metadata': latest_metadata
                })
            
            # 이미지 데이터 반환
            format_type = request.GET.get('format', 'raw')
            
            if format_type == 'base64':
                return JsonResponse({
                    'frame_id': frame_id,
                    'image_data': base64.b64encode(binary_data).decode('utf-8'),
                    'metadata': latest_metadata,
                    'size_bytes': len(binary_data)
                })
            elif format_type == 'info':
                return JsonResponse({
                    'frame_id': frame_id,
                    'metadata': latest_metadata,
                    'size_bytes': len(binary_data),
                    'image_url': f'/api/v1/aria/simple-image/?format=raw'
                })
            else:  # raw format - 실제 이미지 파일
                response = HttpResponse(binary_data, content_type='image/jpeg')
                response['Content-Length'] = len(binary_data)
                response['X-Frame-ID'] = frame_id
                response['Content-Disposition'] = f'inline; filename="{frame_id}.jpg"'
                return response
                
        except Exception as e:
            return JsonResponse({
                'error': f'Failed to get image: {str(e)}',
                'suggestion': 'Make sure Kafka is running and has image data'
            }, status=500)

class QuickImageGenerator(View):
    """빠른 이미지 생성기"""
    
    def post(self, request):
        """테스트 이미지를 빠르게 생성"""
        try:
            from common.kafka.binary_producer import BinaryKafkaProducer
            
            # 간단한 바이너리 프로듀서 사용
            producer = BinaryKafkaProducer()
            result = producer.send_test_binary_frame('quick-image')
            producer.close()
            
            if result['success']:
                frame_id = result['frame_id']
                return JsonResponse({
                    'success': True,
                    'message': '이미지 생성 완료!',
                    'frame_id': frame_id,
                    'view_urls': {
                        'image': f'/api/v1/aria/simple-image/?format=raw',
                        'base64': f'/api/v1/aria/simple-image/?format=base64',
                        'info': f'/api/v1/aria/simple-image/?format=info'
                    },
                    'metadata': result['metadata']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }, status=500)
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)