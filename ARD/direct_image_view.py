"""
직접 이미지 뷰어 - 간단하고 확실한 방법
사용자가 바로 이미지를 볼 수 있도록 하는 최단 경로
"""

from django.http import HttpResponse, JsonResponse
from django.views import View
from kafka import KafkaConsumer
import json
import os
import logging
import time

logger = logging.getLogger(__name__)

class DirectImageView(View):
    """직접 이미지 보기 - 가장 간단한 방법"""
    
    def get(self, request):
        """Kafka에서 최신 이미지를 가져와서 바로 표시"""
        try:
            # Kafka 설정
            bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'ARD_KAFKA:9092')
            
            # 바이너리 토픽에서 직접 최신 이미지 가져오기  
            consumer = KafkaConsumer(
                'vrs-binary-stream',
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=5000,  # 5초 기다림
                auto_offset_reset='earliest',  # 처음부터 읽기
                enable_auto_commit=False,
                max_poll_records=10  # 최대 10개만 확인
            )
            
            # 최신 메시지 찾기
            latest_image = None
            latest_key = None
            message_count = 0
            
            logger.info(f"Looking for latest image in Kafka...")
            
            for message in consumer:
                if message.value and len(message.value) > 1000:  # 이미지 크기 확인
                    latest_image = message.value
                    latest_key = message.key.decode('utf-8') if message.key else 'unknown'
                    message_count += 1
                    logger.info(f"Found image: {latest_key}, size: {len(latest_image)} bytes")
                    break  # 첫 번째 이미지를 찾으면 바로 사용
            
            consumer.close()
            
            if latest_image:
                # 이미지 반환
                response = HttpResponse(latest_image, content_type='image/jpeg')
                response['Content-Length'] = len(latest_image)
                response['X-Frame-ID'] = latest_key
                response['Content-Disposition'] = f'inline; filename="{latest_key}.jpg"'
                response['Cache-Control'] = 'no-cache'
                logger.info(f"Serving image: {latest_key}, {len(latest_image)} bytes")
                return response
            else:
                # 이미지가 없으면 테스트 이미지 생성하고 반환
                logger.warning("No image found in Kafka, generating test image...")
                return self._generate_and_serve_test_image()
                
        except Exception as e:
            logger.error(f"Direct image view failed: {e}")
            return JsonResponse({
                'error': f'Failed to get image: {str(e)}',
                'suggestion': 'Make sure Kafka is running with binary data'
            }, status=500)
    
    def _generate_and_serve_test_image(self):
        """테스트 이미지 생성 후 바로 반환"""
        try:
            from common.kafka.binary_producer import BinaryKafkaProducer
            import numpy as np
            
            # 테스트 이미지 생성
            producer = BinaryKafkaProducer()
            result = producer.send_test_binary_frame('direct-test-session')
            producer.close()
            
            if result['success'] and 'binary_data' in result:
                binary_data = result['binary_data']
                frame_id = result['frame_id']
                
                response = HttpResponse(binary_data, content_type='image/jpeg')
                response['Content-Length'] = len(binary_data)
                response['X-Frame-ID'] = frame_id
                response['Content-Disposition'] = f'inline; filename="{frame_id}.jpg"'
                response['X-Generated'] = 'true'
                
                logger.info(f"Generated and serving test image: {frame_id}, {len(binary_data)} bytes")
                return response
            else:
                return JsonResponse({
                    'error': 'Failed to generate test image',
                    'details': result
                }, status=500)
                
        except Exception as e:
            logger.error(f"Test image generation failed: {e}")
            return JsonResponse({
                'error': f'Test image generation failed: {str(e)}'
            }, status=500)

class VRSImageView(View):
    """실제 VRS 샘플 데이터에서 이미지 가져오기"""
    
    def get(self, request):
        """VRS 샘플 파일에서 실제 이미지 추출하고 표시"""
        try:
            from aria_streams.vrs_binary_reader import VRSBinaryReader
            
            # VRS 샘플 파일 경로
            vrs_path = "/mnt/d/Data/05_CGXR/250728_ARD/ARD/data/mps_samples/sample.vrs"
            
            if not os.path.exists(vrs_path):
                return JsonResponse({
                    'error': 'VRS sample file not found',
                    'path': vrs_path
                }, status=404)
            
            # VRS 리더로 실제 이미지 추출
            reader = VRSBinaryReader(vrs_path)
            
            # 첫 번째 RGB 이미지 가져오기
            frame_data = reader.get_first_rgb_frame()
            
            if frame_data and 'binary_data' in frame_data:
                binary_data = frame_data['binary_data']
                
                response = HttpResponse(binary_data, content_type='image/jpeg')
                response['Content-Length'] = len(binary_data)
                response['X-VRS-Frame'] = f"frame_{frame_data.get('frame_index', 0)}"
                response['X-Image-Size'] = f"{frame_data.get('width', 0)}x{frame_data.get('height', 0)}"
                frame_index = frame_data.get('frame_index', 0)
                response['Content-Disposition'] = f'inline; filename="vrs_frame_{frame_index}.jpg"'
                
                logger.info(f"Serving VRS image: frame {frame_data.get('frame_index', 0)}, {len(binary_data)} bytes")
                return response
            else:
                return JsonResponse({
                    'error': 'No image data found in VRS file',
                    'vrs_path': vrs_path
                }, status=404)
                
        except Exception as e:
            logger.error(f"VRS image extraction failed: {e}")
            return JsonResponse({
                'error': f'VRS image extraction failed: {str(e)}',
                'suggestion': 'Check VRS file and projectaria_tools installation'
            }, status=500)