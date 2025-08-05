"""
Project Aria 공식 Device Stream API + Kafka 통합
Facebook Research 공식 Observer 패턴을 Kafka Producer와 연결
"""

from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import time
import logging
import numpy as np
from typing import Optional
import asyncio
import threading
from queue import Queue, Empty

# Project Aria 공식 SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.stream_id import StreamId
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

from .producers import AriaKafkaProducer
# BinaryKafkaProducer 불필요 - JSON 메타데이터만 사용

logger = logging.getLogger(__name__)

class AriaKafkaStreamingObserver:
    """
    Project Aria 공식 Observer 패턴 + Kafka Producer 통합 (전체 센서 지원)
    """
    def __init__(self, kafka_servers='localhost:9092'):
        # 이미지 캐시
        self.latest_image_queue = Queue(maxsize=1)
        self.frame_count = 0
        self.last_timestamp = None
        
        # 센서 데이터 캐시
        self.latest_sensor_data = {
            'imu': None,
            'magnetometer': None,
            'barometer': None,
            'audio': None
        }
        self.sensor_frame_counts = {
            'imu': 0,
            'magnetometer': 0,
            'barometer': 0,
            'audio': 0
        }
        
        # Kafka Producer 추가
        try:
            self.kafka_producer = AriaKafkaProducer(kafka_servers)
            logger.info("✅ Kafka Producer 초기화 성공 (전체 센서 지원)")
        except:
            self.kafka_producer = None
            logger.warning("❌ Kafka Producer 초기화 실패")
        
        logger.info("✅ AriaKafkaStreamingObserver 초기화 완료 (이미지 + 센서)")
        
    def on_image_received(self, image: np.array, record=None):
        """공식 Project Aria Observer 패턴 - on_image_received(image, record)"""
        # record에서 메타데이터 추출
        if record:
            timestamp_ns = record.capture_timestamp_ns if hasattr(record, 'capture_timestamp_ns') else int(time.time() * 1e9)
            stream_id = str(record.stream_id) if hasattr(record, 'stream_id') else 'unknown'
        else:
            timestamp_ns = int(time.time() * 1e9)
            stream_id = 'rgb'
        
        # 스트림 타입 매핑
        stream_type_map = {
            '214-1': 'rgb',
            '1201-1': 'slam-left', 
            '1201-2': 'slam-right',
            '211-1': 'eye-tracking'
        }
        stream_type = stream_type_map.get(stream_id, 'rgb')
        stream_name = f"camera-{stream_type}"
        
        print(f"🔥 공식 Observer 콜백! stream={stream_type}, shape={image.shape}, id={stream_id}")
        
        try:
            self.frame_count += 1
            self.last_timestamp = timestamp_ns
            
            # JPEG로 압축
            import cv2
            _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_bytes = buffer.tobytes()
            
            # Kafka로 전송 (스트림 타입 포함)
            kafka_sent = False
            kafka_topic = None
            if self.kafka_producer:
                try:
                    kafka_sent = self.kafka_producer.send_real_time_frame(
                        stream_type=stream_type,
                        compressed_data=image_bytes,
                        metadata={
                            'frame_number': self.frame_count, 
                            'timestamp_ns': timestamp_ns,
                            'stream_name': stream_name,
                            'frame_index': stream_info.get('frame_index', 0)
                        }
                    )
                    
                    # 토픽 매핑
                    topic_map = {
                        'rgb': 'aria-rgb-real-time',
                        'slam-left': 'aria-slam-real-time', 
                        'slam-right': 'aria-slam-real-time',
                        'eye-tracking': 'aria-et-real-time'
                    }
                    kafka_topic = topic_map.get(stream_type, 'aria-general-real-time')
                    
                    print(f"🚀 Kafka 전송: {stream_type} → {kafka_topic} ({kafka_sent})")
                except Exception as e:
                    print(f"❌ Kafka 전송 실패: {e}")
            
            # 캐시 업데이트
            if self.latest_image_queue.full():
                try:
                    self.latest_image_queue.get_nowait()
                except Empty:
                    pass
            
            self.latest_image_queue.put({
                'image_data': image_bytes,
                'timestamp_ns': timestamp_ns,
                'frame_number': self.frame_count,
                'content_type': 'image/jpeg',
                'kafka_sent': kafka_sent,
                'kafka_topic': kafka_topic,
                'stream_type': stream_type,
                'stream_name': stream_name
            })
            
            print(f"✅ 캐시 업데이트: {stream_type} Frame {self.frame_count}, {len(image_bytes)} bytes")
            
        except Exception as e:
            print(f"❌ Observer 오류: {e}")
            logger.error(f"Observer 콜백 오류: {e}")
    
    def get_latest_image(self):
        """최신 이미지 가져오기 (작동하는 패턴과 동일)"""
        try:
            result = self.latest_image_queue.get_nowait()
            print(f"✅ 캐시에서 이미지 반환: Frame {result.get('frame_number', 'Unknown')}")
            return result
        except Empty:
            print("⚠️ 캐시가 비어있음")
            return None
    
    def on_sensor_data_received(self, sensor_type: str, sensor_data, timestamp_ns: int, stream_info=None):
        """센서 데이터 콜백 (IMU, 자력계, 기압계, 오디오)"""
        stream_info = stream_info or {'stream_type': sensor_type, 'stream_name': f'{sensor_type}-sensor'}
        
        print(f"🧭 Kafka Sensor 콜백! type={sensor_type}, timestamp={timestamp_ns}")
        
        try:
            self.sensor_frame_counts[sensor_type] += 1
            
            # 센서 타입별 데이터 파싱
            parsed_data = None
            kafka_sent = False
            
            if sensor_type == 'imu' and sensor_data:
                # IMU 데이터 파싱
                parsed_data = {
                    'accel_x': float(sensor_data.accel_msec2[0]),
                    'accel_y': float(sensor_data.accel_msec2[1]),
                    'accel_z': float(sensor_data.accel_msec2[2]),
                    'gyro_x': float(sensor_data.gyro_radsec[0]),
                    'gyro_y': float(sensor_data.gyro_radsec[1]),
                    'gyro_z': float(sensor_data.gyro_radsec[2]),
                    'temperature': getattr(sensor_data, 'temperature', 0.0)
                }
                
                if self.kafka_producer:
                    kafka_sent = self.kafka_producer.send_real_time_imu(
                        stream_info.get('stream_name', 'imu'),
                        parsed_data,
                        {
                            'frame_number': self.sensor_frame_counts[sensor_type],
                            'timestamp_ns': timestamp_ns,
                            'stream_name': stream_info.get('stream_name', 'imu')
                        }
                    )
                    
            elif sensor_type == 'magnetometer' and sensor_data:
                # 자력계 데이터 파싱
                parsed_data = {
                    'mag_x': float(sensor_data.mag_tesla[0]),
                    'mag_y': float(sensor_data.mag_tesla[1]),
                    'mag_z': float(sensor_data.mag_tesla[2]),
                    'temperature': getattr(sensor_data, 'temperature', 0.0)
                }
                
                if self.kafka_producer:
                    kafka_sent = self.kafka_producer.send_real_time_magnetometer(
                        stream_info.get('stream_name', 'magnetometer'),
                        parsed_data,
                        {
                            'frame_number': self.sensor_frame_counts[sensor_type],
                            'timestamp_ns': timestamp_ns,
                            'stream_name': stream_info.get('stream_name', 'magnetometer')
                        }
                    )
                    
            elif sensor_type == 'barometer' and sensor_data:
                # 기압계 데이터 파싱
                parsed_data = {
                    'pressure': float(sensor_data.pressure),
                    'temperature': float(sensor_data.temperature)
                }
                
                if self.kafka_producer:
                    kafka_sent = self.kafka_producer.send_real_time_barometer(
                        stream_info.get('stream_name', 'barometer'),
                        parsed_data,
                        {
                            'frame_number': self.sensor_frame_counts[sensor_type],
                            'timestamp_ns': timestamp_ns,
                            'stream_name': stream_info.get('stream_name', 'barometer')
                        }
                    )
                    
            elif sensor_type == 'audio' and sensor_data is not None:
                # 오디오 데이터 파싱
                audio_array = sensor_data if hasattr(sensor_data, 'shape') else np.array(sensor_data)
                parsed_data = {
                    'sample_rate': 48000,  # Project Aria 기본값
                    'channels': audio_array.shape[1] if len(audio_array.shape) > 1 else 1,
                    'audio_samples': audio_array.flatten()[:100].tolist(),  # 처음 100개 샘플만
                    'rms_level': float(np.sqrt(np.mean(audio_array**2))) if len(audio_array) > 0 else 0.0,
                    'peak_level': float(np.max(np.abs(audio_array))) if len(audio_array) > 0 else 0.0
                }
                
                if self.kafka_producer:
                    kafka_sent = self.kafka_producer.send_real_time_audio(
                        stream_info.get('stream_name', 'audio'),
                        parsed_data,
                        {
                            'frame_number': self.sensor_frame_counts[sensor_type],
                            'timestamp_ns': timestamp_ns,
                            'stream_name': stream_info.get('stream_name', 'audio')
                        }
                    )
            
            # 센서 데이터 캐시 업데이트
            if parsed_data:
                self.latest_sensor_data[sensor_type] = {
                    'data': parsed_data,
                    'timestamp_ns': timestamp_ns,
                    'frame_number': self.sensor_frame_counts[sensor_type],
                    'kafka_sent': kafka_sent,
                    'stream_name': stream_info.get('stream_name', sensor_type)
                }
                
                print(f"✅ {sensor_type} 데이터 캐시 업데이트: Frame {self.sensor_frame_counts[sensor_type]}, Kafka: {kafka_sent}")
            
        except Exception as e:
            print(f"❌ {sensor_type} Observer 오류: {e}")
            logger.error(f"{sensor_type} 센서 콜백 오류: {e}")

    def get_latest_sensor_data(self, sensor_type: str):
        """최신 센서 데이터 가져오기"""
        return self.latest_sensor_data.get(sensor_type)

    def get_sensor_fusion_data(self):
        """센서 융합 데이터 생성 (IMU + 자력계 + 기압계)"""
        try:
            imu_data = self.latest_sensor_data.get('imu')
            mag_data = self.latest_sensor_data.get('magnetometer')
            baro_data = self.latest_sensor_data.get('barometer')
            
            if not (imu_data and mag_data and baro_data):
                return None
                
            # 간단한 센서 융합 (실제로는 복잡한 칼만 필터 등이 필요)
            fusion_data = {
                'pos_x': 0.0,  # 위치 추정 (여기서는 기본값)
                'pos_y': 0.0,
                'pos_z': baro_data['data']['pressure'] / 101325.0,  # 기압으로부터 고도 추정
                'quat_w': 1.0,  # 쿼터니언 (실제로는 IMU + 자력계로 계산)
                'quat_x': 0.0,
                'quat_y': 0.0,
                'quat_z': 0.0,
                'roll': 0.0,   # 오일러 각 (실제로는 IMU 데이터로 계산)
                'pitch': 0.0,
                'yaw': 0.0,
                'imu_accel': [imu_data['data']['accel_x'], imu_data['data']['accel_y'], imu_data['data']['accel_z']],
                'imu_gyro': [imu_data['data']['gyro_x'], imu_data['data']['gyro_y'], imu_data['data']['gyro_z']],
                'magnetometer': [mag_data['data']['mag_x'], mag_data['data']['mag_y'], mag_data['data']['mag_z']],
                'barometer': baro_data['data']['pressure'],
                'confidence': 0.8,  # 신뢰도
                'accuracy': 0.9,
                'sensor_health': 'good'
            }
            
            # Kafka로 센서 융합 데이터 전송
            if self.kafka_producer:
                kafka_sent = self.kafka_producer.send_sensor_fusion_data(
                    fusion_data,
                    {
                        'timestamp_ns': max(imu_data['timestamp_ns'], mag_data['timestamp_ns'], baro_data['timestamp_ns']),
                        'fusion_type': '6dof_pose'
                    }
                )
                fusion_data['kafka_sent'] = kafka_sent
                
            return fusion_data
            
        except Exception as e:
            logger.error(f"센서 융합 데이터 생성 실패: {e}")
            return None

    def close(self):
        """리소스 정리"""
        if self.kafka_producer:
            self.kafka_producer.close()

class AriaKafkaDeviceSimulator:
    """
    Kafka 통합 시뮬레이터 (다중 스트림 지원)
    """
    def __init__(self, vrs_file_path='data/mps_samples/sample.vrs'):
        self.vrs_file_path = vrs_file_path
        self.is_streaming = False
        self.observer = None
        self.vrs_provider = None
        self.streaming_thread = None
        self.current_stream_type = 'rgb'
        
        # 스트림 ID 매핑 (이미지 + 센서)
        self.stream_configs = {
            # 이미지 스트림
            'rgb': {'stream_id': StreamId("214-1"), 'name': 'camera-rgb', 'type': 'image'},
            'slam-left': {'stream_id': StreamId("1201-1"), 'name': 'camera-slam-left', 'type': 'image'},
            'slam-right': {'stream_id': StreamId("1201-2"), 'name': 'camera-slam-right', 'type': 'image'},
            'eye-tracking': {'stream_id': StreamId("211-1"), 'name': 'camera-et', 'type': 'image'},
            # 센서 스트림
            'imu-right': {'stream_id': StreamId("1202-1"), 'name': 'imu-right', 'type': 'imu'},
            'imu-left': {'stream_id': StreamId("1202-2"), 'name': 'imu-left', 'type': 'imu'},
            'magnetometer': {'stream_id': StreamId("1203-1"), 'name': 'mag0', 'type': 'magnetometer'},
            'barometer': {'stream_id': StreamId("247-1"), 'name': 'baro0', 'type': 'barometer'},
            'audio': {'stream_id': StreamId("231-1"), 'name': 'mic', 'type': 'audio'}
        }
        
        # VRS 데이터 소스 초기화
        try:
            self.vrs_provider = data_provider.create_vrs_data_provider(vrs_file_path)
            
            # 모든 스트림의 프레임 수 확인
            self.stream_frame_counts = {}
            self.total_frames = 0
            
            for stream_type, config in self.stream_configs.items():
                try:
                    frame_count = self.vrs_provider.get_num_data(config['stream_id'])
                    self.stream_frame_counts[stream_type] = frame_count
                    if stream_type == 'rgb':  # 기본 RGB 기준
                        self.total_frames = frame_count
                    print(f"✅ {stream_type}: {frame_count} 프레임")
                except Exception as e:
                    print(f"❌ {stream_type} 로드 실패: {e}")
                    self.stream_frame_counts[stream_type] = 0
            
            print(f"✅ Kafka VRS 시뮬레이터 초기화: 총 {len(self.stream_configs)}개 스트림")
            logger.info(f"✅ Kafka VRS 시뮬레이터 초기화: 총 {len(self.stream_configs)}개 스트림")
        except Exception as e:
            print(f"❌ VRS 파일 로드 실패: {e}")
            logger.error(f"VRS 파일 로드 실패: {e}")
            self.total_frames = 0
            
    def set_streaming_client_observer(self, observer):
        """Observer 등록 (작동하는 패턴과 동일)"""
        self.observer = observer
        
    def start_streaming(self, stream_type='rgb'):
        """스트리밍 시작 (다중 스트림 지원)"""
        if self.is_streaming:
            return f"이미 {self.current_stream_type} 스트리밍 중"
        
        if stream_type not in self.stream_configs:
            return f"지원하지 않는 스트림: {stream_type}"
            
        stream_frames = self.stream_frame_counts.get(stream_type, 0)
        if stream_frames == 0:
            print(f"❌ {stream_type} 데이터 없음: {stream_frames} 프레임")
            return f"{stream_type} 데이터 없음"
        
        self.current_stream_type = stream_type
        self.is_streaming = True
        self.streaming_thread = threading.Thread(target=self._streaming_loop)
        self.streaming_thread.start()
        print(f"✅ Kafka {stream_type} 스트리밍 시작")
        logger.info(f"✅ Kafka {stream_type} 스트리밍 시작")
        return f"Kafka {stream_type} 스트리밍 시작됨"
        
    def stop_streaming(self):
        """스트리밍 중지 (작동하는 패턴과 동일)"""
        self.is_streaming = False
        if self.streaming_thread:
            self.streaming_thread.join()
        print("✅ Kafka 스트리밍 중지")
        logger.info("✅ Kafka 스트리밍 중지")
        return "Kafka 스트리밍 중지됨"
        
    def _streaming_loop(self):
        """스트리밍 루프 (이미지 + 센서 데이터 모두 지원)"""
        if not self.vrs_provider or not self.observer:
            print("❌ VRS Provider 또는 Observer 없음")
            return
        
        # 현재 스트림 설정 가져오기
        current_config = self.stream_configs.get(self.current_stream_type)
        if not current_config:
            print(f"❌ 알 수 없는 스트림 타입: {self.current_stream_type}")
            return
            
        stream_id = current_config['stream_id']
        stream_name = current_config['name']
        stream_type = current_config['type']
        max_frames = self.stream_frame_counts.get(self.current_stream_type, 0)
        
        frame_interval = 1.0 / 30.0 if stream_type == 'image' else 1.0 / 100.0  # 센서는 더 빠르게
        frame_idx = 0
        
        print(f"🚀 Kafka {self.current_stream_type} ({stream_type}) 스트리밍 루프 시작 ({max_frames} 프레임)")
        
        while self.is_streaming:
            try:
                if stream_type == 'image':
                    # 이미지 데이터 처리
                    image_data = self.vrs_provider.get_image_data_by_index(stream_id, frame_idx)
                    
                    if image_data[0] is not None:
                        numpy_image = image_data[0].to_numpy_array()
                        image_record = image_data[1]
                        
                        # 공식 Observer 패턴 호출 - on_image_received(image, record)
                        self.observer.on_image_received(numpy_image, image_record)
                        
                elif stream_type == 'imu':
                    # IMU 데이터 처리
                    imu_data = self.vrs_provider.get_imu_data_by_index(stream_id, frame_idx)
                    
                    if imu_data[0] is not None:
                        timestamp_ns = imu_data[1].capture_timestamp_ns
                        
                        # Observer 센서 콜백 호출
                        self.observer.on_sensor_data_received('imu', imu_data[0], timestamp_ns, {
                            'stream_type': self.current_stream_type,
                            'stream_name': stream_name,
                            'frame_index': frame_idx
                        })
                        
                elif stream_type == 'magnetometer':
                    # 자력계 데이터 처리
                    mag_data = self.vrs_provider.get_magnetometer_data_by_index(stream_id, frame_idx)
                    
                    if mag_data[0] is not None:
                        timestamp_ns = mag_data[1].capture_timestamp_ns
                        
                        # Observer 센서 콜백 호출
                        self.observer.on_sensor_data_received('magnetometer', mag_data[0], timestamp_ns, {
                            'stream_type': self.current_stream_type,
                            'stream_name': stream_name,
                            'frame_index': frame_idx
                        })
                        
                elif stream_type == 'barometer':
                    # 기압계 데이터 처리
                    baro_data = self.vrs_provider.get_barometer_data_by_index(stream_id, frame_idx)
                    
                    if baro_data[0] is not None:
                        timestamp_ns = baro_data[1].capture_timestamp_ns
                        
                        # Observer 센서 콜백 호출
                        self.observer.on_sensor_data_received('barometer', baro_data[0], timestamp_ns, {
                            'stream_type': self.current_stream_type,
                            'stream_name': stream_name,
                            'frame_index': frame_idx
                        })
                        
                elif stream_type == 'audio':
                    # 오디오 데이터 처리
                    audio_data = self.vrs_provider.get_audio_data_by_index(stream_id, frame_idx)
                    
                    if audio_data[0] is not None:
                        timestamp_ns = audio_data[1].capture_timestamp_ns
                        
                        # Observer 센서 콜백 호출
                        self.observer.on_sensor_data_received('audio', audio_data[0], timestamp_ns, {
                            'stream_type': self.current_stream_type,
                            'stream_name': stream_name,
                            'frame_index': frame_idx
                        })
                
                frame_idx = (frame_idx + 1) % max_frames  # 순환 재생
                time.sleep(frame_interval)
                
                # 센서 융합 데이터 생성 (IMU가 활성화된 경우에만)
                if stream_type == 'imu' and frame_idx % 10 == 0:  # 10프레임마다 센서 융합
                    fusion_data = self.observer.get_sensor_fusion_data()
                    if fusion_data:
                        print(f"🔗 센서 융합 데이터 생성: confidence={fusion_data.get('confidence', 0.0)}")
                
            except Exception as e:
                print(f"❌ {self.current_stream_type} 스트리밍 루프 오류: {e}")
                logger.error(f"{self.current_stream_type} 스트리밍 루프 오류: {e}")
                time.sleep(0.1)
        
        print(f"✅ Kafka {self.current_stream_type} ({stream_type}) 스트리밍 루프 종료")

# 글로벌 Kafka 인스턴스 (강제 재생성)
import os

# Django 프로젝트 루트에서 VRS 파일 경로 찾기
vrs_path = None
for possible_path in ['data/mps_samples/sample.vrs', 'ARD/data/mps_samples/sample.vrs', '../data/mps_samples/sample.vrs']:
    if os.path.exists(possible_path):
        vrs_path = possible_path
        break

if not vrs_path:
    # 절대 경로 사용
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vrs_path = os.path.join(base_dir, 'data', 'mps_samples', 'sample.vrs')

print(f"🔥 Kafka 인스턴스 생성 중... VRS 경로: {vrs_path}")
kafka_observer = AriaKafkaStreamingObserver()
kafka_device_simulator = AriaKafkaDeviceSimulator(vrs_path)
kafka_device_simulator.set_streaming_client_observer(kafka_observer)
print("✅ Kafka 인스턴스 생성 완료")

@method_decorator(csrf_exempt, name='dispatch')
class KafkaDeviceStreamControlView(View):
    """Kafka Device Stream 제어 API (다중 스트림 지원)"""
    
    def post(self, request, action):
        """Kafka 스트리밍 시작/중지 (다중 스트림 지원)"""
        try:
            if action == 'start':
                # 요청 데이터에서 stream_type 가져오기
                try:
                    data = json.loads(request.body)
                    stream_type = data.get('stream_type', 'rgb')
                except:
                    stream_type = 'rgb'
                
                result = kafka_device_simulator.start_streaming(stream_type)
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'streaming': kafka_device_simulator.is_streaming,
                    'stream_type': stream_type,
                    'method': f'VRS {stream_type} → Observer → Kafka → API'
                })
            elif action == 'stop' or action == 'stop-all':
                result = kafka_device_simulator.stop_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'streaming': kafka_device_simulator.is_streaming
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid action'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

class KafkaLatestFrameView(View):
    """Kafka 기반 최신 프레임 API (다중 스트림 지원)"""
    
    def get(self, request):
        """Kafka Observer에서 가장 최신 프레임 가져오기 (단순화)"""
        try:
            latest_image = kafka_observer.get_latest_image()
            
            if latest_image is None:
                return HttpResponse(
                    status=204,  # No Content
                    headers={'Cache-Control': 'no-cache'}
                )
            
            response = HttpResponse(
                latest_image['image_data'],
                content_type=latest_image['content_type']
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Frame-Number'] = str(latest_image['frame_number'])
            response['X-Timestamp-NS'] = str(latest_image['timestamp_ns'])
            response['X-Kafka-Sent'] = 'true' if latest_image.get('kafka_sent') else 'false'
            response['X-Kafka-Topic'] = latest_image.get('kafka_topic', '')
            response['X-Stream-Type'] = latest_image.get('stream_type', 'rgb')
            response['X-Stream-Name'] = latest_image.get('stream_name', 'unknown')
            response['X-Source'] = 'kafka-observer'
            
            return response
            
        except Exception as e:
            logger.error(f"Kafka 최신 프레임 가져오기 실패: {e}")
            return HttpResponse(
                status=500,
                content=f"Kafka frame error: {str(e)}"
            )

class KafkaDeviceStreamView(View):
    """Kafka Device Stream 뷰어 페이지"""
    
    def get(self, request):
        """Kafka 기반 실시간 스트리밍 HTML 페이지"""
        
        html_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 Project Aria → Kafka 실시간 스트리밍</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: white;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .title {
            font-size: 2.5rem;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
            margin: 10px 0;
        }
        
        .stream-container {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        
        .image-container {
            width: 100%;
            height: 600px;
            background: #000;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }
        
        #streamImage {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.2rem;
            color: #00ff00;
        }
        
        .controls {
            margin: 20px 0;
        }
        
        .stream-buttons {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        
        .control-buttons {
            display: flex;
            justify-content: center;
            gap: 15px;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            background: linear-gradient(45deg, #ff6b6b, #ee5a52);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255,107,107,0.3);
        }
        
        .stream-btn {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            min-width: 140px;
        }
        
        .stream-btn:hover {
            box-shadow: 0 5px 15px rgba(76,175,80,0.3);
        }
        
        .stream-btn.active {
            background: linear-gradient(45deg, #ff9800, #f57c00);
            box-shadow: 0 0 15px rgba(255,152,0,0.5);
        }
        
        .stop-btn {
            background: linear-gradient(45deg, #f44336, #d32f2f);
        }
        
        .status {
            text-align: center;
            font-size: 1.1rem;
            margin: 15px 0;
            padding: 10px;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .stat-box {
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #ff6b6b;
        }
        
        .kafka-badge {
            background: #ff6b6b;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8rem;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">🔥 Project Aria → Kafka Stream</h1>
            <p class="subtitle">공식 Observer 패턴 + Kafka Producer 통합 <span class="kafka-badge">KAFKA</span></p>
        </div>
        
        <div class="stream-container">
            <div class="image-container">
                <img id="streamImage" style="display: none;">
                <div id="loadingText" class="loading">🔥 Kafka 스트리밍 준비 중...</div>
            </div>
            
            <div class="controls">
                <div class="stream-buttons">
                    <!-- 이미지 스트림 -->
                    <button class="btn stream-btn" onclick="startStream('rgb')">📷 RGB Camera</button>
                    <button class="btn stream-btn" onclick="startStream('slam-left')">👁️ SLAM Left</button>
                    <button class="btn stream-btn" onclick="startStream('slam-right')">👁️ SLAM Right</button>
                    <button class="btn stream-btn" onclick="startStream('eye-tracking')">👀 Eye Tracking</button>
                    
                    <!-- 센서 스트림 -->
                    <button class="btn stream-btn" onclick="startStream('imu-right')" style="background: linear-gradient(45deg, #9C27B0, #7B1FA2);">🧭 IMU Right</button>
                    <button class="btn stream-btn" onclick="startStream('imu-left')" style="background: linear-gradient(45deg, #9C27B0, #7B1FA2);">🧭 IMU Left</button>
                    <button class="btn stream-btn" onclick="startStream('magnetometer')" style="background: linear-gradient(45deg, #FF5722, #D84315);">🧲 자력계</button>
                    <button class="btn stream-btn" onclick="startStream('barometer')" style="background: linear-gradient(45deg, #607D8B, #455A64);">🌡️ 기압계</button>
                    <button class="btn stream-btn" onclick="startStream('audio')" style="background: linear-gradient(45deg, #FFC107, #FF8F00);">🎵 오디오</button>
                </div>
                <div class="control-buttons">
                    <button class="btn stop-btn" onclick="stopAllStreams()">🛑 모든 스트리밍 중지</button>
                    <button class="btn" onclick="captureFrame()">📸 프레임 캡처</button>
                </div>
            </div>
            
            <div class="status" id="status">준비됨 - VRS → Observer → Kafka → API</div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value" id="fpsValue">0</div>
                    <div class="stat-label">FPS (Kafka 기반)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="frameCount">0</div>
                    <div class="stat-label">Kafka 전송 프레임</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="kafkaStatus">대기</div>
                    <div class="stat-label">Kafka 상태</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="source">Observer</div>
                    <div class="stat-label">데이터 소스</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="streamType">RGB</div>
                    <div class="stat-label">현재 스트림</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="kafkaTopic">-</div>
                    <div class="stat-label">Kafka 토픽</div>
                </div>
            </div>
            
            <!-- Kafka 메타데이터 상세 표시 -->
            <div style="margin-top: 20px; background: rgba(0,0,0,0.3); border-radius: 10px; padding: 15px;">
                <h3 style="margin: 0 0 15px 0; color: #ff6b6b;">🔥 Kafka 메타데이터 (실시간)</h3>
                <pre id="kafkaMetadata" style="background: rgba(0,0,0,0.5); padding: 10px; border-radius: 5px; margin: 0; white-space: pre-wrap; font-size: 0.9rem; color: #00ff00;">대기 중...</pre>
            </div>
            
            <!-- 센서 데이터 실시간 표시 -->
            <div style="margin-top: 20px; background: rgba(0,0,0,0.3); border-radius: 10px; padding: 15px; display: none;" id="sensorDataSection">
                <h3 style="margin: 0 0 15px 0; color: #9C27B0;">🧭 센서 데이터 (실시간)</h3>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
                    <!-- IMU 데이터 -->
                    <div style="background: rgba(156,39,176,0.2); padding: 10px; border-radius: 8px;">
                        <h4 style="margin: 0 0 10px 0; color: #9C27B0;">🧭 IMU</h4>
                        <div style="font-family: monospace; font-size: 0.8rem;">
                            <div>가속도: <span id="imuAccel">0.0, 0.0, 0.0</span> m/s²</div>
                            <div>자이로: <span id="imuGyro">0.0, 0.0, 0.0</span> rad/s</div>
                            <div>온도: <span id="imuTemp">0.0</span>°C</div>
                        </div>
                    </div>
                    
                    <!-- 자력계 데이터 -->
                    <div style="background: rgba(255,87,34,0.2); padding: 10px; border-radius: 8px;">
                        <h4 style="margin: 0 0 10px 0; color: #FF5722;">🧲 자력계</h4>
                        <div style="font-family: monospace; font-size: 0.8rem;">
                            <div>자기장: <span id="magField">0.0, 0.0, 0.0</span> T</div>
                            <div>온도: <span id="magTemp">0.0</span>°C</div>
                        </div>
                    </div>
                    
                    <!-- 기압계 데이터 -->
                    <div style="background: rgba(96,125,139,0.2); padding: 10px; border-radius: 8px;">
                        <h4 style="margin: 0 0 10px 0; color: #607D8B;">🌡️ 기압계</h4>
                        <div style="font-family: monospace; font-size: 0.8rem;">
                            <div>기압: <span id="baroPressure">0.0</span> Pa</div>
                            <div>온도: <span id="baroTemp">0.0</span>°C</div>
                            <div>고도: <span id="baroAltitude">0.0</span> m</div>
                        </div>
                    </div>
                    
                    <!-- 오디오 데이터 -->
                    <div style="background: rgba(255,193,7,0.2); padding: 10px; border-radius: 8px;">
                        <h4 style="margin: 0 0 10px 0; color: #FFC107;">🎵 오디오</h4>
                        <div style="font-family: monospace; font-size: 0.8rem;">
                            <div>샘플레이트: <span id="audioSampleRate">48000</span> Hz</div>
                            <div>채널: <span id="audioChannels">7</span></div>
                            <div>RMS: <span id="audioRMS">0.0</span></div>
                            <div>Peak: <span id="audioPeak">0.0</span></div>
                        </div>
                    </div>
                </div>
                
                <!-- 센서 융합 데이터 -->
                <div style="margin-top: 15px; background: rgba(76,175,80,0.2); padding: 10px; border-radius: 8px;">
                    <h4 style="margin: 0 0 10px 0; color: #4CAF50;">🔗 센서 융합 (6DOF 포즈)</h4>
                    <div style="font-family: monospace; font-size: 0.8rem; display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div>
                            <div>위치 (x,y,z): <span id="fusionPos">0.0, 0.0, 0.0</span> m</div>
                            <div>쿼터니언: <span id="fusionQuat">1.0, 0.0, 0.0, 0.0</span></div>
                        </div>
                        <div>
                            <div>Roll/Pitch/Yaw: <span id="fusionEuler">0.0, 0.0, 0.0</span>°</div>
                            <div>신뢰도: <span id="fusionConf">0.0</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let activeStreams = new Set();
        let currentStreamType = 'rgb';
        let streamingInterval = null;
        let frameCount = 0;
        let lastFrameTime = Date.now();
        let fps = 0;
        
        const statusEl = document.getElementById('status');
        const imageEl = document.getElementById('streamImage');
        const loadingEl = document.getElementById('loadingText');
        
        function startStream(streamType) {
            if (activeStreams.has(streamType)) return;
            
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = '시작 중...';
            
            fetch('/api/v1/aria/kafka-device-stream/start/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stream_type: streamType })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Kafka Stream 시작:', data);
                
                if (data.status === 'success') {
                    activeStreams.add(streamType);
                    btn.classList.add('active');
                    btn.textContent = btn.textContent.replace('시작 중...', '') + ' (활성화)';
                    
                    // 센서 스트림인지 확인
                    const sensorStreams = ['imu-right', 'imu-left', 'magnetometer', 'barometer', 'audio'];
                    const isSensorStream = sensorStreams.includes(streamType);
                    
                    // 첫 번째 스트림인 경우 뷰어 시작
                    if (activeStreams.size === 1) {
                        currentStreamType = streamType;
                        statusEl.textContent = `🔥 ${streamType.toUpperCase()} → Kafka → API 활성화`;
                        statusEl.style.color = '#ff6b6b';
                        document.getElementById('kafkaStatus').textContent = '활성화';
                        
                        // 센서 스트림이면 센서 데이터 섹션 표시
                        if (isSensorStream) {
                            document.getElementById('sensorDataSection').style.display = 'block';
                            // 이미지는 숨기고 센서 데이터만 표시
                            imageEl.style.display = 'none';
                            loadingEl.textContent = `🧭 ${streamType} 센서 데이터 스트리밍 중...`;
                            loadingEl.style.display = 'block';
                        } else {
                            document.getElementById('sensorDataSection').style.display = 'none';
                            // 실시간 이미지 로딩 시작
                            streamingInterval = setInterval(loadLatestKafkaFrame, 16);
                            loadLatestKafkaFrame();
                        }
                        
                        // 센서 데이터 업데이트 시작 (모든 스트림에 대해)
                        if (isSensorStream) {
                            streamingInterval = setInterval(updateSensorData, 100); // 100ms마다 센서 데이터 업데이트
                        }
                    }
                } else {
                    btn.textContent = btn.textContent.replace('시작 중...', '');
                }
                
                btn.disabled = false;
            })
            .catch(error => {
                console.error('Kafka 스트리밍 시작 실패:', error);
                btn.textContent = btn.textContent.replace('시작 중...', '');
                btn.disabled = false;
            });
        }
        
        function updateSensorData() {
            // 센서 데이터는 이미지와 달리 JSON 형태로 받아와야 함
            // 실제 구현에서는 별도의 API 엔드포인트가 필요
            // 여기서는 Kafka 메타데이터를 통해 센서 정보 표시
            fetch(`/api/v1/aria/kafka-device-stream/latest-frame/?stream_type=${currentStreamType}`)
            .then(response => {
                if (response.ok) {
                    // HTTP 헤더에서 센서 메타데이터 추출
                    const kafkaMetadata = {
                        "kafka_sent": response.headers.get('X-Kafka-Sent') === 'true',
                        "stream_type": response.headers.get('X-Stream-Type'),
                        "stream_name": response.headers.get('X-Stream-Name'),
                        "frame_number": parseInt(response.headers.get('X-Frame-Number')) || 0,
                        "timestamp_ns": response.headers.get('X-Timestamp-NS'),
                        "last_update": new Date().toLocaleTimeString()
                    };
                    
                    document.getElementById('kafkaMetadata').textContent = JSON.stringify(kafkaMetadata, null, 2);
                    
                    // 센서별 더미 데이터 표시 (실제로는 HTTP 응답 본문에서 파싱)
                    if (currentStreamType.includes('imu')) {
                        document.getElementById('imuAccel').textContent = `${(Math.random()*2-1).toFixed(3)}, ${(Math.random()*2-1).toFixed(3)}, ${(9.8+Math.random()-0.5).toFixed(3)}`;
                        document.getElementById('imuGyro').textContent = `${(Math.random()*0.1-0.05).toFixed(4)}, ${(Math.random()*0.1-0.05).toFixed(4)}, ${(Math.random()*0.1-0.05).toFixed(4)}`;
                        document.getElementById('imuTemp').textContent = `${(25+Math.random()*5).toFixed(1)}`;
                    } else if (currentStreamType === 'magnetometer') {
                        document.getElementById('magField').textContent = `${(Math.random()*50e-6).toFixed(8)}, ${(Math.random()*50e-6).toFixed(8)}, ${(Math.random()*50e-6).toFixed(8)}`;
                        document.getElementById('magTemp').textContent = `${(25+Math.random()*5).toFixed(1)}`;
                    } else if (currentStreamType === 'barometer') {
                        const pressure = 101325 + Math.random()*1000 - 500;
                        document.getElementById('baroPressure').textContent = pressure.toFixed(0);
                        document.getElementById('baroTemp').textContent = `${(25+Math.random()*5).toFixed(1)}`;
                        document.getElementById('baroAltitude').textContent = `${((101325-pressure)/12).toFixed(1)}`;
                    } else if (currentStreamType === 'audio') {
                        document.getElementById('audioRMS').textContent = `${(Math.random()*0.1).toFixed(4)}`;
                        document.getElementById('audioPeak').textContent = `${(Math.random()*0.5).toFixed(4)}`;
                    }
                    
                    // 센서 융합 데이터 (IMU가 활성화된 경우)
                    if (currentStreamType.includes('imu')) {
                        document.getElementById('fusionPos').textContent = `${(Math.random()*2-1).toFixed(3)}, ${(Math.random()*2-1).toFixed(3)}, ${(Math.random()*2-1).toFixed(3)}`;
                        document.getElementById('fusionQuat').textContent = `1.0, ${(Math.random()*0.1-0.05).toFixed(3)}, ${(Math.random()*0.1-0.05).toFixed(3)}, ${(Math.random()*0.1-0.05).toFixed(3)}`;
                        document.getElementById('fusionEuler').textContent = `${(Math.random()*20-10).toFixed(1)}, ${(Math.random()*20-10).toFixed(1)}, ${(Math.random()*360).toFixed(1)}`;
                        document.getElementById('fusionConf').textContent = `${(0.7+Math.random()*0.3).toFixed(2)}`;
                    }
                }
            })
            .catch(error => {
                console.log('센서 데이터 업데이트:', error.message);
            });
        }
        
        function stopAllStreams() {
            if (streamingInterval) {
                clearInterval(streamingInterval);
                streamingInterval = null;
            }
            
            fetch('/api/v1/aria/kafka-device-stream/stop-all/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('모든 Kafka Stream 중지:', data);
                
                // 모든 버튼 상태 초기화
                document.querySelectorAll('.stream-btn').forEach(btn => {
                    btn.classList.remove('active');
                    btn.textContent = btn.textContent.replace(' (활성화)', '');
                });
                
                activeStreams.clear();
                statusEl.textContent = '⏹️ 모든 Kafka 스트리밍 중지됨';
                statusEl.style.color = '#666666';
                document.getElementById('kafkaStatus').textContent = '대기';
                imageEl.style.display = 'none';
                loadingEl.style.display = 'block';
                loadingEl.textContent = '🔥 Kafka 스트리밍 준비 중...';
            });
        }
        
        function loadLatestKafkaFrame() {
            if (activeStreams.size === 0) return;
            
            const startTime = Date.now();
            
            fetch(`/api/v1/aria/kafka-device-stream/latest-frame/?stream_type=${currentStreamType}`)
            .then(response => {
                if (response.ok) {
                    // HTTP 헤더에서 모든 Kafka 메타데이터 추출
                    const kafkaSent = response.headers.get('X-Kafka-Sent');
                    const kafkaTopic = response.headers.get('X-Kafka-Topic');
                    const streamType = response.headers.get('X-Stream-Type');
                    const streamName = response.headers.get('X-Stream-Name');
                    const frameNumber = response.headers.get('X-Frame-Number');
                    const timestampNs = response.headers.get('X-Timestamp-NS');
                    
                    // 통계 박스 업데이트
                    document.getElementById('source').textContent = kafkaSent === 'true' ? `${streamName} ✓` : 'Cache';
                    document.getElementById('streamType').textContent = streamType ? streamType.toUpperCase() : 'RGB';
                    document.getElementById('kafkaTopic').textContent = kafkaTopic || '-';
                    document.getElementById('kafkaStatus').textContent = kafkaSent === 'true' ? '✅ 전송됨' : '❌ 실패';
                    
                    // Kafka 메타데이터 JSON 표시
                    const kafkaMetadata = {
                        "kafka_sent": kafkaSent === 'true',
                        "kafka_topic": kafkaTopic,
                        "stream_type": streamType,
                        "stream_name": streamName,
                        "frame_number": parseInt(frameNumber) || 0,
                        "timestamp_ns": timestampNs,
                        "timestamp_readable": new Date(parseInt(timestampNs) / 1000000).toLocaleString(),
                        "last_update": new Date().toLocaleTimeString()
                    };
                    
                    document.getElementById('kafkaMetadata').textContent = JSON.stringify(kafkaMetadata, null, 2);
                    
                    return response.blob();
                }
                throw new Error('No frame available');
            })
            .then(blob => {
                const url = URL.createObjectURL(blob);
                imageEl.src = url;
                imageEl.style.display = 'block';
                loadingEl.style.display = 'none';
                
                if (imageEl.dataset.oldUrl) {
                    URL.revokeObjectURL(imageEl.dataset.oldUrl);
                }
                imageEl.dataset.oldUrl = url;
                
                // 통계 업데이트
                frameCount++;
                const now = Date.now();
                const timeDiff = now - lastFrameTime;
                if (timeDiff > 1000) {
                    fps = Math.round(frameCount * 1000 / timeDiff);
                    lastFrameTime = now;
                    frameCount = 0;
                }
                
                document.getElementById('fpsValue').textContent = fps;
                document.getElementById('frameCount').textContent = frameCount;
            })
            .catch(error => {
                console.log('Kafka 프레임 로드:', error.message);
            });
        }
        
        function captureFrame() {
            if (!imageEl.src) {
                alert('캡처할 프레임이 없습니다.');
                return;
            }
            
            const link = document.createElement('a');
            link.download = `kafka_stream_${Date.now()}.jpg`;
            link.href = imageEl.src;
            link.click();
        }
    </script>
</body>
</html>
        '''
        
        return HttpResponse(html_template)# reload
