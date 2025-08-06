"""
Project Aria 공식 Observer 패턴을 정확히 구현
deliver_queued_sensor_data를 Observer 스타일로 래핑
"""
import os
import time
import json
import asyncio
from typing import Dict, Any, Optional
import numpy as np

# 기존 common kafka 사용 (패키지 충돌 방지)
from common.kafka.binary_producer import BinaryKafkaProducer
from common.kafka.base_producer import BaseKafkaProducer

# Project Aria tools (ipynb 패턴)
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions  
from projectaria_tools.core.stream_id import RecordableTypeId, StreamId


class AriaKafkaStreamingObserver:
    """
    공식 StreamingClientObserver 패턴을 모방한 Kafka Observer
    실제 하드웨어 Observer와 동일한 인터페이스
    """
    
    def __init__(self, session_id: str = 'aria-streaming-session'):
        self.session_id = session_id
        
        # 공식 패턴: 이미지를 카메라 ID별로 저장
        self.images = {}
        self.imu_data = []
        
        # Kafka 연결
        self.binary_producer = BinaryKafkaProducer(bootstrap_servers='localhost:9092')
        self.base_producer = AriaKafkaProducer()
        
        # 스트리밍 상태
        self.is_streaming = False
        self.message_count = 0
        
        print("[OK] AriaKafkaStreamingObserver 초기화 완료")
    
    def on_image_received(self, image: np.array, camera_id: str, capture_timestamp_ns: int, stream_id: str):
        """
        공식 Observer 패턴: on_image_received 구현
        실제 하드웨어 콜백과 동일한 시그니처
        """
        if not self.is_streaming:
            return
        
        try:
            # 공식 패턴: 카메라 ID별로 이미지 저장
            self.images[camera_id] = image
            
            # Kafka로 전송 (기존 binary_producer 활용)
            result = self.binary_producer.send_vrs_frame_binary(
                session_id=self.session_id,
                stream_id=stream_id,
                numpy_image=image,
                frame_index=self.message_count,
                capture_timestamp_ns=capture_timestamp_ns,
                format='jpeg',
                quality=75  # 스트리밍에 적합한 품질
            )
            
            if result.get('success'):
                self.message_count += 1
                
                # 스트리밍다운 로그 (실시간 느낌)
                if self.message_count % 5 == 0:
                    print(f"[STREAMING] {camera_id}: {self.message_count}개 전송됨 ({result['binary_size']} bytes)")
            
        except Exception as e:
            print(f"[ERROR] on_image_received 오류 ({camera_id}): {e}")
    
    def on_imu_received(self, imu_data: Dict, sensor_label: str, timestamp_ns: int):
        """
        공식 Observer 패턴: IMU 데이터 수신 콜백
        """
        if not self.is_streaming:
            return
        
        try:
            # 공식 패턴: IMU 데이터 수집
            self.imu_data.append(imu_data)
            
            # 센서 데이터를 Kafka로 전송
            sensor_message = {
                'sensor_type': 'imu',
                'sensor_label': sensor_label,
                'timestamp_ns': timestamp_ns,
                'data': imu_data,
                'sequence': len(self.imu_data)
            }
            
            success = self.base_producer.send_message('sensor', sensor_message, key=sensor_label)
            
            if success and len(self.imu_data) % 10 == 0:
                print(f"[STREAMING] {sensor_label}: {len(self.imu_data)}개 센서 데이터 전송")
            
        except Exception as e:
            print(f"[ERROR] on_imu_received 오류 ({sensor_label}): {e}")
    
    def start_streaming(self):
        """공식 패턴: 스트리밍 시작"""
        self.is_streaming = True
        self.message_count = 0
        self.images = {}
        self.imu_data = []
        print(f"[OK] Observer 스트리밍 시작 - 세션: {self.session_id}")
    
    def stop_streaming(self):
        """공식 패턴: 스트리밍 중지"""
        self.is_streaming = False
        print(f"[OK] Observer 스트리밍 중지 - 총 {self.message_count}개 이미지, {len(self.imu_data)}개 센서")
    
    def close(self):
        """리소스 정리"""
        self.binary_producer.close()
        self.base_producer.close()


class AriaKafkaProducer(BaseKafkaProducer):
    """Aria용 Kafka Producer (기존 common/kafka 확장)"""
    
    def __init__(self):
        super().__init__(service_name='aria_observer_streaming', bootstrap_servers='localhost:9092')
        
        self.topics = {
            'sensor': 'sensor-data',
            'metadata': 'image-metadata',
            'imu': 'stream-imu-right'
        }


class AriaVRSStreamingManager:
    """
    공식 StreamingManager 패턴을 모방한 VRS 스트리밍 매니저
    deliver_queued_sensor_data를 Observer로 연결
    """
    
    def __init__(self, vrs_file_path: str):
        self.vrs_file_path = vrs_file_path
        self.provider = None
        self.observer = None
        
        # 공식 패턴: 스트림 매핑
        self.stream_mappings = {
            "camera-slam-left": StreamId("1201-1"),
            "camera-slam-right": StreamId("1201-2"),
            "camera-rgb": StreamId("214-1"),
            "camera-eyetracking": StreamId("211-1"),
        }
    
    def initialize_streaming(self):
        """스트리밍 초기화 (공식 패턴)"""
        try:
            # ipynb 패턴: VRS 프로바이더 생성
            print(f"Creating data provider from {self.vrs_file_path}")
            self.provider = data_provider.create_vrs_data_provider(self.vrs_file_path)
            
            if not self.provider:
                print("Invalid vrs data provider")
                return False
            
            # Observer 생성
            self.observer = AriaKafkaStreamingObserver()
            
            print("[OK] 스트리밍 매니저 초기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 스트리밍 초기화 실패: {e}")
            return False
    
    async def start_streaming(self, duration_seconds: int = 20):
        """
        공식 패턴: 스트리밍 시작
        deliver_queued_sensor_data로 연속 데이터 생성하여 Observer 콜백 호출
        """
        if not self.provider or not self.observer:
            print("[ERROR] 스트리밍이 초기화되지 않음")
            return
        
        print(f"연속 스트리밍 시작 ({duration_seconds}초) - 공식 Observer 패턴")
        
        # Observer 스트리밍 시작 (공식 패턴)
        self.observer.start_streaming()
        
        try:
            # ipynb 패턴: deliver_queued_sensor_data 설정
            options = self.provider.get_default_deliver_queued_options()
            
            # 시간 범위 설정
            rgb_stream_id = StreamId("214-1")
            start_time = self.provider.get_first_time_ns(rgb_stream_id, TimeDomain.DEVICE_TIME)
            end_time = start_time + (duration_seconds * 1_000_000_000)
            
            options.set_truncate_first_device_time_ns(start_time)
            options.set_truncate_last_device_time_ns(end_time)
            
            # 스트림 활성화 및 샘플링 (다중 스트리밍 최적화)
            slam_stream_ids = options.get_stream_ids(RecordableTypeId.SLAM_CAMERA_DATA)
            imu_stream_ids = options.get_stream_ids(RecordableTypeId.SLAM_IMU_DATA)
            
            print("활성화된 스트림:")
            
            # SLAM 카메라 (moderate sampling)
            for stream_id in slam_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 10)  # 10개 중 1개
                label = self.provider.get_label_from_stream_id(stream_id)
                print(f"  {label}: 1/10 샘플링")
            
            # IMU (heavy sampling to prevent overflow)
            for stream_id in imu_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 50)  # 50개 중 1개
                label = self.provider.get_label_from_stream_id(stream_id)
                print(f"  {label}: 1/50 샘플링")
            
            # RGB 카메라 (light sampling - 고화질이므로)
            try:
                rgb_stream_ids = options.get_stream_ids(RecordableTypeId.RGB_CAMERA_DATA)
                for stream_id in rgb_stream_ids:
                    options.activate_stream(stream_id)
                    options.set_subsample_rate(stream_id, 15)  # 15개 중 1개
                    print(f"  camera-rgb: 1/15 샘플링")
            except:
                print("  [WARNING] RGB_CAMERA_DATA RecordableTypeId 없음")
            
            # deliver_queued_sensor_data로 연속 데이터 스트림 생성
            iterator = self.provider.deliver_queued_sensor_data(options)
            
            print("\\n연속 스트리밍 시작...")
            frame_count = 0
            
            for sensor_data in iterator:
                if not self.observer.is_streaming:
                    break
                
                stream_id = sensor_data.stream_id()
                stream_label = self.provider.get_label_from_stream_id(stream_id)
                device_timestamp = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
                
                # 이미지 스트림 처리
                if 'camera' in stream_label:
                    try:
                        # 해당 프레임의 이미지 데이터 가져오기
                        # frame_count를 index로 사용하여 순차적 접근
                        num_frames = self.provider.get_num_data(stream_id)
                        frame_idx = frame_count % num_frames  # 순환
                        
                        image_data = self.provider.get_image_data_by_index(stream_id, frame_idx)
                        if image_data and image_data[0]:
                            image_array = image_data[0].to_numpy_array()
                            
                            # 공식 Observer 콜백 호출
                            self.observer.on_image_received(
                                image=image_array,
                                camera_id=stream_label,
                                capture_timestamp_ns=device_timestamp,
                                stream_id=str(stream_id)
                            )
                            
                            frame_count += 1
                    except Exception as e:
                        print(f"[ERROR] 이미지 처리 오류 ({stream_label}): {e}")
                
                # IMU 센서 처리
                elif 'imu' in stream_label:
                    try:
                        # IMU 데이터 구성
                        imu_dict = {
                            'stream_id': str(stream_id),
                            'device_timestamp_ns': device_timestamp,
                            'host_timestamp_ns': sensor_data.get_time_ns(TimeDomain.HOST_TIME),
                            'sensor_type': str(sensor_data.sensor_data_type())
                        }
                        
                        # 공식 Observer 콜백 호출
                        self.observer.on_imu_received(imu_dict, stream_label, device_timestamp)
                        
                    except Exception as e:
                        print(f"[ERROR] IMU 처리 오류 ({stream_label}): {e}")
                
                # 스트리밍 속도 조절 (실시간 느낌)
                await asyncio.sleep(0.1)  # 100ms 간격
                
        except Exception as e:
            print(f"[ERROR] 스트리밍 오류: {e}")
        finally:
            self.stop_streaming()
    
    def stop_streaming(self):
        """공식 패턴: 스트리밍 중지"""
        if self.observer:
            self.observer.stop_streaming()
            self.observer.close()
        
        print("[OK] 스트리밍 매니저 중지")


async def test_official_observer_pattern():
    """공식 Observer 패턴 테스트"""
    print("=== 공식 Observer 패턴 스트리밍 테스트 ===")
    
    vrs_file = "data/mps_samples/sample.vrs"
    
    if not os.path.exists(vrs_file):
        print(f"[ERROR] VRS 파일 없음: {vrs_file}")
        return
    
    # 공식 패턴: StreamingManager 생성
    streaming_manager = AriaVRSStreamingManager(vrs_file)
    
    if not streaming_manager.initialize_streaming():
        print("[ERROR] 스트리밍 매니저 초기화 실패")
        return
    
    print("\\n공식 Observer 패턴으로 15초간 다중 스트리밍...")
    
    # 공식 패턴: 스트리밍 시작
    await streaming_manager.start_streaming(duration_seconds=15)
    
    print("\\n[SUCCESS] 공식 Observer 패턴 스트리밍 완료!")


# Aria용 BaseKafkaProducer 확장
class AriaKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__(service_name='aria_official_observer', bootstrap_servers='localhost:9092')
        
        self.topics = {
            'sensor': 'sensor-data',
            'metadata': 'image-metadata',
            'imu': 'stream-imu-right'
        }


if __name__ == "__main__":
    asyncio.run(test_official_observer_pattern())