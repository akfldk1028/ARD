"""
Project Aria VRS 데이터를 Kafka로 스트리밍하는 Producer
공식 ipynb 패턴과 streaming_service.py를 통합하여 구현
"""
import os
import sys
import json
import time
import asyncio
import base64
from typing import Dict, List, Optional, Tuple
import numpy as np
from kafka import KafkaProducer
from kafka.errors import KafkaError

from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions  
from projectaria_tools.core.stream_id import RecordableTypeId, StreamId

from ..config.kafka_config import KafkaConfig
from ..utils.data_controller import DataFlowController


class AriaKafkaStreamer:
    """Project Aria VRS 데이터를 Kafka로 스트리밍"""
    
    def __init__(self, kafka_config: KafkaConfig = None):
        self.kafka_config = kafka_config or KafkaConfig()
        self.producer = None
        self.provider = None
        self.data_controller = DataFlowController()
        
        # ipynb 코드와 동일한 스트림 매핑
        self.stream_mappings = {
            "camera-slam-left": StreamId("1201-1"),
            "camera-slam-right": StreamId("1201-2"), 
            "camera-rgb": StreamId("214-1"),
            "camera-eyetracking": StreamId("211-1"),
        }
        
        # 센서 스트림 매핑
        self.sensor_streams = {
            "imu-right": None,  # RecordableTypeId.SLAM_IMU_DATA로 찾기
            "imu-left": None,
            "magnetometer": None,
        }
        
    def setup_kafka_producer(self):
        """Kafka Producer 초기화"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                max_request_size=self.kafka_config.max_message_size,
                compression_type=self.kafka_config.compression_type,
                buffer_memory=self.kafka_config.buffer_memory,
                batch_size=self.kafka_config.max_batch_size,
                linger_ms=10,  # 약간의 배치 지연으로 효율성 향상
            )
            print("[OK] Kafka Producer 연결 성공")
            return True
        except Exception as e:
            print(f"[ERROR] Kafka Producer 연결 실패: {e}")
            return False
    
    def setup_vrs_provider(self, vrs_file_path: str):
        """ipynb 패턴으로 VRS 데이터 프로바이더 생성"""
        if not os.path.exists(vrs_file_path):
            print(f"[ERROR] VRS 파일을 찾을 수 없습니다: {vrs_file_path}")
            return False
            
        print(f"Creating data provider from {vrs_file_path}")
        self.provider = data_provider.create_vrs_data_provider(vrs_file_path)
        if not self.provider:
            print("Invalid vrs data provider")
            return False
            
        # 센서 스트림 ID 찾기 (ipynb 패턴)
        self._discover_sensor_streams()
        print("[OK] VRS 데이터 프로바이더 생성 완료")
        return True
    
    def _discover_sensor_streams(self):
        """센서 스트림 자동 발견 (ipynb 패턴)"""
        if not self.provider:
            return
            
        streams = self.provider.get_all_streams()
        for stream_id in streams:
            label = self.provider.get_label_from_stream_id(stream_id)
            
            # IMU 스트림 찾기
            if "imu" in label.lower():
                self.sensor_streams[label] = stream_id
                print(f"발견된 센서: {label} -> {stream_id}")
    
    def process_image_frame(self, stream_name: str, stream_id: StreamId, frame_index: int) -> Optional[Dict]:
        """ipynb 패턴으로 이미지 프레임 처리"""
        try:
            # ipynb와 동일한 방식으로 이미지 데이터 가져오기
            image_data = self.provider.get_image_data_by_index(stream_id, frame_index)
            if not image_data or not image_data[0]:
                return None
                
            image_array = image_data[0].to_numpy_array()
            capture_timestamp_ns = image_data[1].capture_timestamp_ns
            
            # 이미지를 base64로 인코딩 (메모리 효율적)
            from PIL import Image
            import io
            
            # numpy array를 PIL Image로 변환
            if len(image_array.shape) == 2:  # 그레이스케일
                pil_image = Image.fromarray(image_array, mode='L')
            else:  # RGB
                pil_image = Image.fromarray(image_array)
            
            # JPEG로 압축하여 크기 줄이기
            buffer = io.BytesIO()
            pil_image.save(buffer, format='JPEG', quality=80)
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return {
                'stream_name': stream_name,
                'stream_id': str(stream_id),
                'frame_index': frame_index,
                'capture_timestamp_ns': capture_timestamp_ns,
                'device_timestamp_ns': capture_timestamp_ns,  # ipynb 패턴
                'image_shape': list(image_array.shape),
                'image_data': image_base64,
                'data_type': 'image',
                'processing_timestamp': time.time()
            }
            
        except Exception as e:
            print(f"[ERROR] 이미지 프레임 처리 오류 ({stream_name}): {e}")
            return None
    
    def process_sensor_data(self, stream_id: StreamId, data_index: int) -> Optional[Dict]:
        """센서 데이터 처리 (ipynb 패턴)"""
        try:
            # ipynb 패턴으로 센서 데이터 가져오기
            sensor_data = self.provider.get_sensor_data_by_index(stream_id, data_index)
            if not sensor_data:
                return None
            
            label = self.provider.get_label_from_stream_id(stream_id)
            device_timestamp = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
            host_timestamp = sensor_data.get_time_ns(TimeDomain.HOST_TIME)
            
            return {
                'stream_name': label,
                'stream_id': str(stream_id),
                'data_index': data_index,
                'device_timestamp_ns': device_timestamp,
                'host_timestamp_ns': host_timestamp,
                'sensor_type': str(sensor_data.sensor_data_type()),
                'data_type': 'sensor',
                'processing_timestamp': time.time()
            }
            
        except Exception as e:
            print(f"[ERROR] 센서 데이터 처리 오류: {e}")
            return None
    
    async def stream_balanced_data_to_kafka(self, max_images=4, max_sensors=10, start_offset=0):
        """균형잡힌 데이터를 Kafka로 스트리밍 (기존 패턴 유지)"""
        if not self.provider or not self.producer:
            print("[ERROR] Provider 또는 Producer가 초기화되지 않았습니다")
            return
        
        print(f"Kafka로 균형잡힌 데이터 스트리밍 시작 (이미지: {max_images}, 센서: {max_sensors})")
        
        # 이미지 데이터 스트리밍
        image_count = 0
        for stream_name, stream_id in self.stream_mappings.items():
            if image_count >= max_images:
                break
                
            num_frames = self.provider.get_num_data(stream_id)
            if num_frames == 0:
                continue
                
            frame_index = min(start_offset, num_frames - 1)
            frame_data = self.process_image_frame(stream_name, stream_id, frame_index)
            
            if frame_data:
                # 데이터 플로우 컨트롤
                await self.data_controller.wait_if_needed()
                
                # Kafka 토픽으로 전송
                topic_map = {
                    'camera-rgb': 'stream-camera-rgb',
                    'camera-slam-left': 'vrs-frames',
                    'camera-slam-right': 'vrs-frames',
                    'camera-eyetracking': 'image-metadata'
                }
                
                topic = topic_map.get(stream_name, 'vrs-frames')
                
                try:
                    future = self.producer.send(topic, value=frame_data, key=stream_name.encode())
                    result = future.get(timeout=10)
                    print(f"[OK] {stream_name} -> {topic}: {result.partition}:{result.offset}")
                    image_count += 1
                    
                except Exception as e:
                    print(f"[ERROR] Kafka 전송 실패 ({stream_name}): {e}")
        
        # 센서 데이터 스트리밍 (ipynb 패턴 활용)
        sensor_count = 0
        for sensor_label, stream_id in self.sensor_streams.items():
            if not stream_id or sensor_count >= max_sensors:
                continue
                
            num_data = self.provider.get_num_data(stream_id)
            if num_data == 0:
                continue
                
            data_index = min(start_offset, num_data - 1)
            sensor_data = self.process_sensor_data(stream_id, data_index)
            
            if sensor_data:
                await self.data_controller.wait_if_needed()
                
                try:
                    future = self.producer.send('sensor-data', value=sensor_data, key=sensor_label.encode())
                    result = future.get(timeout=10)
                    print(f"[OK] {sensor_label} -> sensor-data: {result.partition}:{result.offset}")
                    sensor_count += 1
                    
                except Exception as e:
                    print(f"[ERROR] 센서 데이터 Kafka 전송 실패 ({sensor_label}): {e}")
        
        print(f"스트리밍 완료: 이미지 {image_count}개, 센서 {sensor_count}개")
    
    async def stream_continuous_data(self, duration_seconds: int = 60):
        """연속 데이터 스트리밍 (ipynb deliver_queued_sensor_data 패턴)"""
        if not self.provider or not self.producer:
            print("[ERROR] Provider 또는 Producer가 초기화되지 않았습니다")
            return
        
        print(f"연속 데이터 스트리밍 시작 ({duration_seconds}초)")
        
        # ipynb 패턴: deliver_queued_sensor_data 사용
        options = self.provider.get_default_deliver_queued_options()
        
        # 시작/종료 시간 설정 (duration_seconds만큼)
        rgb_stream_id = StreamId("214-1")
        start_time = self.provider.get_first_time_ns(rgb_stream_id, TimeDomain.DEVICE_TIME)
        end_time = start_time + (duration_seconds * 1_000_000_000)  # nanoseconds
        
        options.set_truncate_first_device_time_ns(start_time)
        options.set_truncate_last_device_time_ns(end_time)
        
        # 데이터가 너무 많지 않도록 샘플링 설정
        slam_stream_ids = options.get_stream_ids(RecordableTypeId.SLAM_CAMERA_DATA)
        imu_stream_ids = options.get_stream_ids(RecordableTypeId.SLAM_IMU_DATA)
        
        for stream_id in slam_stream_ids:
            options.activate_stream(stream_id)
            options.set_subsample_rate(stream_id, 5)  # 5프레임 중 1개
            
        for stream_id in imu_stream_ids:
            options.activate_stream(stream_id)
            options.set_subsample_rate(stream_id, 20)  # 20개 중 1개
        
        # RGB 스트림도 활성화
        rgb_streams = options.get_stream_ids(RecordableTypeId.RGB_CAMERA_DATA)
        for stream_id in rgb_streams:
            options.activate_stream(stream_id)
            options.set_subsample_rate(stream_id, 10)  # 10프레임 중 1개
        
        # ipynb 패턴: iterator 생성
        iterator = self.provider.deliver_queued_sensor_data(options)
        
        message_count = 0
        for sensor_data in iterator:
            # 데이터 플로우 컨트롤
            await self.data_controller.wait_if_needed()
            
            label = self.provider.get_label_from_stream_id(sensor_data.stream_id())
            sensor_type = sensor_data.sensor_data_type()
            device_timestamp = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
            host_timestamp = sensor_data.get_time_ns(TimeDomain.HOST_TIME)
            
            kafka_data = {
                'stream_label': label,
                'stream_id': str(sensor_data.stream_id()),
                'sensor_type': str(sensor_type),
                'device_timestamp_ns': device_timestamp,
                'host_timestamp_ns': host_timestamp,
                'data_type': 'continuous_sensor',
                'processing_timestamp': time.time(),
                'message_index': message_count
            }
            
            # 토픽 선택
            topic = 'sensor-data'
            if 'camera' in label:
                if 'rgb' in label:
                    topic = 'stream-camera-rgb'
                else:
                    topic = 'vrs-frames'
            elif 'imu' in label:
                topic = 'stream-imu-right' if 'right' in label else 'sensor-data'
            
            try:
                future = self.producer.send(topic, value=kafka_data, key=label.encode())
                result = future.get(timeout=5)
                message_count += 1
                
                if message_count % 50 == 0:  # 50개마다 로그
                    print(f"[OK] 전송됨: {message_count}개 메시지 - 최신: {label} -> {topic}")
                    
            except Exception as e:
                print(f"[ERROR] Kafka 전송 실패 ({label}): {e}")
                
        print(f"연속 스트리밍 완료: 총 {message_count}개 메시지 전송")
    
    def get_stream_summary(self) -> Dict:
        """스트림 요약 정보 (ipynb 패턴)"""
        if not self.provider:
            return {}
        
        summary = {}
        
        # 이미지 스트림 정보
        for stream_name, stream_id in self.stream_mappings.items():
            num_frames = self.provider.get_num_data(stream_id)
            if num_frames > 0:
                config = self.provider.get_image_configuration(stream_id)
                start_time = self.provider.get_first_time_ns(stream_id, TimeDomain.DEVICE_TIME)
                end_time = self.provider.get_last_time_ns(stream_id, TimeDomain.DEVICE_TIME)
                
                summary[stream_name] = {
                    'stream_id': str(stream_id),
                    'num_frames': num_frames,
                    'image_width': config.image_width,
                    'image_height': config.image_height,
                    'nominal_rate_hz': config.nominal_rate_hz,
                    'start_time_ns': start_time,
                    'end_time_ns': end_time,
                    'duration_seconds': (end_time - start_time) / 1_000_000_000
                }
        
        # 센서 스트림 정보
        for sensor_name, stream_id in self.sensor_streams.items():
            if stream_id:
                num_data = self.provider.get_num_data(stream_id)
                if num_data > 0:
                    summary[sensor_name] = {
                        'stream_id': str(stream_id),
                        'num_data': num_data
                    }
        
        return summary
    
    def close(self):
        """리소스 정리"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            print("[OK] Kafka Producer 종료")


# 사용 예시
async def main():
    """테스트 실행"""
    streamer = AriaKafkaStreamer()
    
    # VRS 파일 경로 (프로젝트 샘플 데이터)
    vrs_file = "D:/Data/05_CGXR/ARD/ARD_Backend/ARD/data/mps_samples/sample.vrs"
    
    # 초기화
    if not streamer.setup_kafka_producer():
        return
    
    if not streamer.setup_vrs_provider(vrs_file):
        return
    
    # 스트림 요약 출력
    summary = streamer.get_stream_summary()
    print("\n=== 스트림 요약 ===")
    for name, info in summary.items():
        print(f"{name}: {info}")
    
    # 균형잡힌 데이터 스트리밍
    await streamer.stream_balanced_data_to_kafka(max_images=4, max_sensors=6)
    
    # 연속 데이터 스트리밍 (10초)
    await streamer.stream_continuous_data(duration_seconds=10)
    
    # 정리
    streamer.close()

if __name__ == "__main__":
    asyncio.run(main())