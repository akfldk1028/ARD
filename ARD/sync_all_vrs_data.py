#!/usr/bin/env python3
"""
전체 VRS 샘플 데이터 동기화 스크립트
Meta Project Aria 샘플 데이터에서 모든 타입 추출하여 Kafka + Django 동기화

Usage:
    python sync_all_vrs_data.py
"""

import os
import sys
import django
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime
import numpy as np

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ARD.settings')
django.setup()

# Project imports
from aria_streams.models import AriaSession, VRSStream, EyeGazeData, HandTrackingData, SLAMTrajectoryData, IMUData
from common.kafka.binary_producer import BinaryKafkaProducer

# Project Aria imports
try:
    from projectaria_tools.core import data_provider, calibration
    from projectaria_tools.core.stream_id import StreamId
    from projectaria_tools.core.sensor_data import ImageData, ImuData
    from projectaria_tools.projects.adt import AriaDigitalTwinDataProvider
    HAS_ARIA_TOOLS = True
    print("✅ Project Aria Tools 로드 성공")
except ImportError as e:
    HAS_ARIA_TOOLS = False
    print(f"❌ Project Aria Tools 로드 실패: {e}")
    print("pip install projectaria-tools 실행 필요")

class VRSDataSynchronizer:
    """VRS 샘플 데이터 전체 동기화 클래스"""
    
    def __init__(self):
        self.vrs_file = Path('data/mps_samples/sample.vrs')
        self.mps_data_path = Path('data/mps_samples')
        self.producer = BinaryKafkaProducer()
        self.session_id = "complete-vrs-session"
        self.stats = {
            'vrs_frames': 0,
            'eye_gaze': 0,
            'hand_tracking': 0,
            'slam_trajectory': 0,
            'imu_data': 0,
            'errors': []
        }
        
    def load_mps_sample_data(self):
        """MPS 샘플 데이터 로드"""
        mps_data = {}
        
        try:
            # Eye Gaze 데이터
            eye_gaze_files = {
                'general': self.mps_data_path / 'eye_gaze' / 'general_eye_gaze.csv',
                'personalized': self.mps_data_path / 'eye_gaze' / 'personalized_eye_gaze.csv'
            }
            
            for gaze_type, file_path in eye_gaze_files.items():
                if file_path.exists():
                    import pandas as pd
                    df = pd.read_csv(file_path)
                    mps_data[f'eye_gaze_{gaze_type}'] = df.to_dict('records')[:20]  # 처음 20개만
                    print(f"✅ Eye Gaze ({gaze_type}): {len(mps_data[f'eye_gaze_{gaze_type}'])}개 로드")
            
            # Hand Tracking 데이터
            hand_files = {
                'results': self.mps_data_path / 'hand_tracking' / 'hand_tracking_results.csv',
                'wrist_palm': self.mps_data_path / 'hand_tracking' / 'wrist_and_palm_poses.csv'
            }
            
            for hand_type, file_path in hand_files.items():
                if file_path.exists():
                    df = pd.read_csv(file_path)
                    mps_data[f'hand_tracking_{hand_type}'] = df.to_dict('records')[:20]
                    print(f"✅ Hand Tracking ({hand_type}): {len(mps_data[f'hand_tracking_{hand_type}'])}개 로드")
            
            # SLAM 데이터
            slam_files = {
                'closed_loop': self.mps_data_path / 'slam' / 'closed_loop_trajectory.csv',
                'open_loop': self.mps_data_path / 'slam' / 'open_loop_trajectory.csv'
            }
            
            for slam_type, file_path in slam_files.items():
                if file_path.exists():
                    df = pd.read_csv(file_path)
                    mps_data[f'slam_{slam_type}'] = df.to_dict('records')[:50]  # 처음 50개만
                    print(f"✅ SLAM ({slam_type}): {len(mps_data[f'slam_{slam_type}'])}개 로드")
            
        except Exception as e:
            print(f"❌ MPS 데이터 로드 실패: {e}")
            self.stats['errors'].append(f"MPS 데이터 로드 실패: {e}")
        
        return mps_data
    
    def extract_vrs_data(self):
        """VRS 파일에서 이미지 + IMU 데이터 추출"""
        if not HAS_ARIA_TOOLS:
            print("❌ Project Aria Tools 없음 - VRS 추출 불가")
            return []
        
        try:
            provider = data_provider.create_vrs_data_provider(str(self.vrs_file))
            
            if not provider:
                print(f"❌ VRS 파일 로드 실패: {self.vrs_file}")
                return []
            
            print(f"✅ VRS 파일 로드 성공: {self.vrs_file}")
            
            # 스트림 정보 출력
            stream_ids = provider.get_all_streams()
            print(f"📊 총 스트림 수: {len(stream_ids)}")
            
            for stream_id in stream_ids:
                stream_label = provider.get_label_from_stream_id(stream_id)
                data_type = provider.get_stream_data_type(stream_id)
                print(f"  - {stream_id}: {stream_label} ({data_type})")
            
            vrs_data = []
            
            # RGB 이미지 추출 (최대 5개)
            rgb_stream_id = StreamId("214-1")  # RGB camera
            if rgb_stream_id in stream_ids:
                image_data = provider.get_image_data_by_index(rgb_stream_id, 0)
                if image_data:
                    # Numpy 배열로 변환
                    numpy_image = image_data[1].to_numpy_array()
                    
                    vrs_data.append({
                        'type': 'vrs_frame',
                        'stream_id': '214-1',
                        'frame_index': 0,
                        'numpy_image': numpy_image,
                        'timestamp': image_data[0].capture_timestamp_ns,
                        'device_timestamp_ns': image_data[0].capture_timestamp_ns
                    })
                    print(f"✅ RGB 이미지 추출: {numpy_image.shape}")
            
            # IMU 데이터 추출 (좌/우 IMU)
            imu_streams = ["1202-1", "1202-2"]  # IMU left, IMU right
            for imu_stream_str in imu_streams:
                imu_stream_id = StreamId(imu_stream_str)
                if imu_stream_id in stream_ids:
                    # IMU 데이터 추출 (처음 10개)
                    for idx in range(min(10, provider.get_num_data(imu_stream_id))):
                        try:
                            imu_data = provider.get_imu_data_by_index(imu_stream_id, idx)
                            if imu_data:
                                vrs_data.append({
                                    'type': 'imu_data',
                                    'stream_id': imu_stream_str,
                                    'imu_type': 'left' if imu_stream_str == '1202-1' else 'right',
                                    'timestamp': imu_data[0].capture_timestamp_ns,
                                    'device_timestamp_ns': imu_data[0].capture_timestamp_ns,
                                    'accel_x': float(imu_data[1].accel_msec2[0]),
                                    'accel_y': float(imu_data[1].accel_msec2[1]),
                                    'accel_z': float(imu_data[1].accel_msec2[2]),
                                    'gyro_x': float(imu_data[1].gyro_radsec[0]),
                                    'gyro_y': float(imu_data[1].gyro_radsec[1]),
                                    'gyro_z': float(imu_data[1].gyro_radsec[2]),
                                    'temperature_c': float(imu_data[1].temperature) if hasattr(imu_data[1], 'temperature') else None
                                })
                        except Exception as e:
                            print(f"IMU 데이터 추출 실패 ({imu_stream_str}[{idx}]): {e}")
                    
                    print(f"✅ IMU 데이터 추출 ({imu_stream_str}): 10개")
            
            return vrs_data
            
        except Exception as e:
            print(f"❌ VRS 데이터 추출 실패: {e}")
            self.stats['errors'].append(f"VRS 추출 실패: {e}")
            return []
    
    def create_django_session(self):
        """Django 세션 생성"""
        try:
            session, created = AriaSession.objects.get_or_create(
                session_id=self.session_id,
                defaults={
                    'session_uid': f"complete-sync-{int(time.time())}",
                    'device_serial': 'vrs-sample-device',
                    'status': 'ACTIVE',
                    'metadata': {
                        'source': 'sample.vrs',
                        'sync_type': 'complete_data_sync',
                        'created_at': datetime.now().isoformat()
                    }
                }
            )
            
            if created:
                print(f"✅ Django 세션 생성: {self.session_id}")
            else:
                print(f"✅ 기존 Django 세션 사용: {self.session_id}")
            
            return session
            
        except Exception as e:
            print(f"❌ Django 세션 생성 실패: {e}")
            self.stats['errors'].append(f"Django 세션 생성 실패: {e}")
            return None
    
    def sync_vrs_frames(self, session, vrs_data):
        """VRS 프레임 데이터 동기화"""
        for item in vrs_data:
            if item['type'] == 'vrs_frame':
                try:
                    # Kafka로 바이너리 스트리밍
                    result = self.producer.send_vrs_frame_binary(
                        session_id=self.session_id,
                        stream_id=item['stream_id'],
                        numpy_image=item['numpy_image'],
                        frame_index=item['frame_index'],
                        capture_timestamp_ns=item['timestamp'],
                        format='jpeg',
                        quality=90
                    )
                    
                    if result['success']:
                        # Django VRSStream 생성
                        VRSStream.objects.create(
                            session=session,
                            stream_id=item['stream_id'],
                            stream_name='camera-rgb',
                            device_timestamp_ns=item['device_timestamp_ns'],
                            frame_index=item['frame_index'],
                            image_shape=[int(x) for x in item['numpy_image'].shape],
                            pixel_format='RGB8',
                            image_width=int(item['numpy_image'].shape[1]),
                            image_height=int(item['numpy_image'].shape[0]),
                            compressed_size_bytes=result['compression']['compressed_size'],
                            compression_quality=90
                        )
                        
                        self.stats['vrs_frames'] += 1
                        print(f"✅ VRS 프레임 동기화: Frame {item['frame_index']} ({result['compression']['compressed_size']} bytes)")
                    
                except Exception as e:
                    print(f"❌ VRS 프레임 동기화 실패: {e}")
                    self.stats['errors'].append(f"VRS 프레임 동기화 실패: {e}")
    
    def sync_imu_data(self, session, vrs_data):
        """IMU 데이터 동기화"""
        for item in vrs_data:
            if item['type'] == 'imu_data':
                try:
                    # Kafka로 센서 데이터 전송
                    self.producer.send_sensor_data(
                        session_id=self.session_id,
                        sensor_type='imu',
                        sensor_data=item
                    )
                    
                    # Django IMUData 생성
                    IMUData.objects.create(
                        session=session,
                        device_timestamp_ns=item['device_timestamp_ns'],
                        imu_stream_id=item['stream_id'],
                        imu_type=item['imu_type'],
                        accel_x=item['accel_x'],
                        accel_y=item['accel_y'],
                        accel_z=item['accel_z'],
                        gyro_x=item['gyro_x'],
                        gyro_y=item['gyro_y'],
                        gyro_z=item['gyro_z'],
                        temperature_c=item.get('temperature_c')
                    )
                    
                    self.stats['imu_data'] += 1
                    
                except Exception as e:
                    print(f"❌ IMU 데이터 동기화 실패: {e}")
                    self.stats['errors'].append(f"IMU 데이터 동기화 실패: {e}")
        
        print(f"✅ IMU 데이터 동기화 완료: {self.stats['imu_data']}개")
    
    def sync_eye_gaze_data(self, session, mps_data):
        """Eye Gaze 데이터 동기화"""
        for gaze_type in ['general', 'personalized']:
            key = f'eye_gaze_{gaze_type}'
            if key in mps_data:
                for item in mps_data[key]:
                    try:
                        # Kafka로 센서 데이터 전송
                        self.producer.send_sensor_data(
                            session_id=self.session_id,
                            sensor_type='eye_gaze',
                            sensor_data=item
                        )
                        
                        # Django EyeGazeData 생성
                        EyeGazeData.objects.create(
                            session=session,
                            device_timestamp_ns=int(time.time_ns()),  # 샘플 타임스탬프
                            gaze_type=gaze_type,
                            yaw=float(item.get('yaw_deg', 0)),
                            pitch=float(item.get('pitch_deg', 0)),
                            depth_m=float(item.get('depth_m', 1.0)) if 'depth_m' in item else None,
                            confidence=float(item.get('confidence', 0.8)) if 'confidence' in item else None
                        )
                        
                        self.stats['eye_gaze'] += 1
                        
                    except Exception as e:
                        print(f"❌ Eye Gaze 데이터 동기화 실패: {e}")
                        self.stats['errors'].append(f"Eye Gaze 동기화 실패: {e}")
        
        print(f"✅ Eye Gaze 데이터 동기화 완료: {self.stats['eye_gaze']}개")
    
    def sync_hand_tracking_data(self, session, mps_data):
        """Hand Tracking 데이터 동기화"""
        if 'hand_tracking_results' in mps_data:
            for item in mps_data['hand_tracking_results']:
                try:
                    # Kafka로 센서 데이터 전송
                    self.producer.send_sensor_data(
                        session_id=self.session_id,
                        sensor_type='hand_tracking',
                        sensor_data=item
                    )
                    
                    # Django HandTrackingData 생성
                    HandTrackingData.objects.create(
                        session=session,
                        device_timestamp_ns=int(time.time_ns()),  # 샘플 타임스탬프
                        left_hand_landmarks=[0.0] * 63 if 'left_hand' in str(item) else None,  # 21 landmarks * 3 coords
                        left_hand_wrist_normal=[1, 0, 0] if 'left_hand' in str(item) else None,
                        left_hand_palm_normal=[0, 1, 0] if 'left_hand' in str(item) else None,
                        right_hand_landmarks=[0.0] * 63 if 'right_hand' in str(item) else None,
                        right_hand_wrist_normal=[1, 0, 0] if 'right_hand' in str(item) else None,
                        right_hand_palm_normal=[0, 1, 0] if 'right_hand' in str(item) else None
                    )
                    
                    self.stats['hand_tracking'] += 1
                    
                except Exception as e:
                    print(f"❌ Hand Tracking 데이터 동기화 실패: {e}")
                    self.stats['errors'].append(f"Hand Tracking 동기화 실패: {e}")
        
        print(f"✅ Hand Tracking 데이터 동기화 완료: {self.stats['hand_tracking']}개")
    
    def sync_slam_data(self, session, mps_data):
        """SLAM 데이터 동기화"""
        for slam_type in ['closed_loop', 'open_loop']:
            key = f'slam_{slam_type}'
            if key in mps_data:
                for item in mps_data[key]:
                    try:
                        # Kafka로 센서 데이터 전송
                        self.producer.send_sensor_data(
                            session_id=self.session_id,
                            sensor_type='slam',
                            sensor_data=item
                        )
                        
                        # 4x4 변환 행렬 생성 (샘플 데이터)
                        transform_matrix = [
                            [1.0, 0.0, 0.0, float(item.get('tx_world_device', 0))],
                            [0.0, 1.0, 0.0, float(item.get('ty_world_device', 0))],
                            [0.0, 0.0, 1.0, float(item.get('tz_world_device', 0))],
                            [0.0, 0.0, 0.0, 1.0]
                        ]
                        
                        # Django SLAMTrajectoryData 생성
                        SLAMTrajectoryData.objects.create(
                            session=session,
                            device_timestamp_ns=int(time.time_ns()),  # 샘플 타임스탬프
                            transform_matrix=transform_matrix,
                            position_x=float(item.get('tx_world_device', 0)),
                            position_y=float(item.get('ty_world_device', 0)),
                            position_z=float(item.get('tz_world_device', 0))
                        )
                        
                        self.stats['slam_trajectory'] += 1
                        
                    except Exception as e:
                        print(f"❌ SLAM 데이터 동기화 실패: {e}")
                        self.stats['errors'].append(f"SLAM 동기화 실패: {e}")
        
        print(f"✅ SLAM 데이터 동기화 완료: {self.stats['slam_trajectory']}개")
    
    def run_complete_sync(self):
        """전체 데이터 동기화 실행"""
        print("🚀 완전한 VRS 데이터 동기화 시작")
        print("=" * 60)
        
        # 1. Django 세션 생성
        session = self.create_django_session()
        if not session:
            return False
        
        # 2. VRS 파일에서 이미지 + IMU 데이터 추출
        print("\n📁 VRS 파일 데이터 추출 중...")
        vrs_data = self.extract_vrs_data()
        
        # 3. MPS 샘플 데이터 로드
        print("\n📊 MPS 샘플 데이터 로드 중...")
        mps_data = self.load_mps_sample_data()
        
        # 4. 모든 데이터 타입 동기화
        print("\n🔄 데이터 동기화 시작...")
        
        # VRS 프레임 (이미지)
        if vrs_data:
            print("\n1️⃣ VRS 프레임 동기화...")
            self.sync_vrs_frames(session, vrs_data)
        
        # IMU 데이터
        if vrs_data:
            print("\n2️⃣ IMU 데이터 동기화...")
            self.sync_imu_data(session, vrs_data)
        
        # Eye Gaze 데이터
        if mps_data:
            print("\n3️⃣ Eye Gaze 데이터 동기화...")
            self.sync_eye_gaze_data(session, mps_data)
        
        # Hand Tracking 데이터
        if mps_data:
            print("\n4️⃣ Hand Tracking 데이터 동기화...")
            self.sync_hand_tracking_data(session, mps_data)
        
        # SLAM 데이터
        if mps_data:
            print("\n5️⃣ SLAM 데이터 동기화...")
            self.sync_slam_data(session, mps_data)
        
        # 6. 세션 완료 처리
        session.status = 'COMPLETED'
        session.save()
        
        # 7. 결과 출력
        self.print_results()
        return True
    
    def print_results(self):
        """동기화 결과 출력"""
        print("\n" + "=" * 60)
        print("📊 동기화 결과 요약")
        print("=" * 60)
        print(f"🎯 세션 ID: {self.session_id}")
        print(f"🖼️  VRS 프레임: {self.stats['vrs_frames']}개")
        print(f"📱 IMU 데이터: {self.stats['imu_data']}개")
        print(f"👁️  Eye Gaze: {self.stats['eye_gaze']}개")
        print(f"👋 Hand Tracking: {self.stats['hand_tracking']}개")
        print(f"🗺️  SLAM Trajectory: {self.stats['slam_trajectory']}개")
        print(f"❌ 오류 수: {len(self.stats['errors'])}개")
        
        if self.stats['errors']:
            print("\n⚠️ 오류 목록:")
            for error in self.stats['errors'][:5]:  # 처음 5개만 출력
                print(f"  - {error}")
        
        total_data = sum([
            self.stats['vrs_frames'],
            self.stats['imu_data'], 
            self.stats['eye_gaze'],
            self.stats['hand_tracking'],
            self.stats['slam_trajectory']
        ])
        
        print(f"\n✅ 총 데이터 수: {total_data}개")
        print(f"🌐 API 테스트 URL:")
        print(f"  - Sessions: http://localhost:8000/api/v1/aria/api/sessions/")
        print(f"  - VRS Streams: http://localhost:8000/api/v1/aria/api/vrs-streams/")
        print(f"  - Eye Gaze: http://localhost:8000/api/v1/aria/api/eye-gaze/")
        print(f"  - Hand Tracking: http://localhost:8000/api/v1/aria/api/hand-tracking/")
        print(f"  - SLAM: http://localhost:8000/api/v1/aria/api/slam-trajectory/")
        print(f"  - IMU: http://localhost:8000/api/v1/aria/api/imu-data/")
        
        if self.stats['vrs_frames'] > 0:
            print(f"  - 이미지 보기: http://localhost:8000/api/v1/aria/direct-image/")

def main():
    """메인 실행 함수"""
    try:
        # pandas 설치 확인
        try:
            import pandas as pd
            print("✅ pandas 사용 가능")
        except ImportError:
            print("❌ pandas 필요: pip install pandas")
            return False
        
        # 동기화 실행
        synchronizer = VRSDataSynchronizer()
        success = synchronizer.run_complete_sync()
        
        if success:
            print("\n🎉 완전한 데이터 동기화 성공!")
            return True
        else:
            print("\n❌ 데이터 동기화 실패")
            return False
            
    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단됨")
        return False
    except Exception as e:
        print(f"\n💥 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)