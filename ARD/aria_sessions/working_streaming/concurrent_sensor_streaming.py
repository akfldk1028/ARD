"""
동시 센서 스트리밍 - Project Aria 공식 Observer 패턴 구현
IMU, 자력계, 기압계, 오디오 센서 동시 지원
"""

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import time
import logging
import threading
from queue import Queue, Empty
from typing import Dict, Optional
import numpy as np

# Project Aria 공식 SDK
try:
    from projectaria_tools.core import data_provider
    from projectaria_tools.core.sensor_data import TimeDomain, TimeQueryOptions
    from projectaria_tools.core.stream_id import RecordableTypeId, StreamId
    ARIA_SDK_AVAILABLE = True
except ImportError:
    ARIA_SDK_AVAILABLE = False

from aria_sessions.models import AriaStreamingSession

logger = logging.getLogger(__name__)

def safe_float(value, default=None):
    """NaN과 Infinity를 안전하게 처리하는 float 변환"""
    try:
        float_val = float(value)
        if math.isnan(float_val) or math.isinf(float_val):
            return default
        return float_val
    except (ValueError, TypeError, OverflowError):
        return default

import math

class ConcurrentSensorObserver:
    """
    Project Aria 공식 Observer 패턴 구현 - 센서 동시 지원
    """
    def __init__(self):
        # 센서별 데이터 저장 (공식 패턴)
        self.sensor_data = {}  # sensor_type -> latest_data
        self.sensor_counts = {}  # sensor_type -> count
        self.sensor_queues = {}  # sensor_type -> Queue
        
        # 센서 매핑은 동적으로 생성됨
        self.sensor_mappings = {}
        
        # 기본 센서들 Queue 초기화
        basic_sensors = ['imu_left', 'imu_right', 'magnetometer', 'barometer', 'audio']
        for sensor_type in basic_sensors:
            self.sensor_queues[sensor_type] = Queue(maxsize=10)  # 센서는 더 많은 데이터
            self.sensor_counts[sensor_type] = 0
        
        print("✅ ConcurrentSensorObserver 초기화 - 5개 센서 동시 지원")
    
    def on_sensor_data_received(self, sensor_type: str, sensor_data, timestamp_ns: int, sensor_config: dict):
        """
        공식 Observer 패턴 콜백 - 센서 데이터 처리
        """
        try:
            # 동적으로 센서 타입 추가
            if sensor_type not in self.sensor_queues:
                self.sensor_queues[sensor_type] = Queue(maxsize=10)
                self.sensor_counts[sensor_type] = 0
                print(f"🆕 새로운 센서 타입 추가: {sensor_type}")
            
            # 센서 카운트 증가
            self.sensor_counts[sensor_type] = self.sensor_counts[sensor_type] + 1
            
            # 센서별 데이터 파싱
            parsed_data = None
            
            if sensor_type.startswith('imu') and sensor_data:
                # IMU 데이터 파싱
                parsed_data = {
                    'accelerometer': {
                        'x': float(sensor_data.accel_msec2[0]),
                        'y': float(sensor_data.accel_msec2[1]),
                        'z': float(sensor_data.accel_msec2[2]),
                        'unit': 'm/s²'
                    },
                    'gyroscope': {
                        'x': float(sensor_data.gyro_radsec[0]),
                        'y': float(sensor_data.gyro_radsec[1]),
                        'z': float(sensor_data.gyro_radsec[2]),
                        'unit': 'rad/s'
                    },
                    'temperature': {
                        'value': safe_float(getattr(sensor_data, 'temperature', 0.0)),
                        'unit': '°C'
                    }
                }
                
            elif sensor_type == 'magnetometer' and sensor_data:
                # 자력계 데이터 파싱
                parsed_data = {
                    'magnetic_field': {
                        'x': float(sensor_data.mag_tesla[0]),
                        'y': float(sensor_data.mag_tesla[1]),
                        'z': float(sensor_data.mag_tesla[2]),
                        'unit': 'Tesla'
                    },
                    'temperature': {
                        'value': safe_float(sensor_data.temperature),
                        'unit': '°C'
                    }
                }
                
            elif sensor_type == 'barometer' and sensor_data:
                # 기압계 데이터 파싱
                parsed_data = {
                    'pressure': {
                        'value': float(sensor_data.pressure),
                        'unit': 'Pascal'
                    },
                    'temperature': {
                        'value': safe_float(sensor_data.temperature),
                        'unit': '°C'
                    },
                    'altitude': {
                        'value': (101325.0 - float(sensor_data.pressure)) / 12.0,  # 근사 고도 계산
                        'unit': 'm'
                    }
                }
                
            elif sensor_type == 'audio' and sensor_data:
                # 오디오 데이터 파싱 (메타데이터만)
                try:
                    audio_blocks = sensor_data.audio_blocks
                    total_samples = sum(len(block.data) for block in audio_blocks) if audio_blocks else 0
                    
                    parsed_data = {
                        'audio_info': {
                            'blocks': len(audio_blocks) if audio_blocks else 0,
                            'total_samples': total_samples,
                            'channels': audio_blocks[0].num_channels if audio_blocks else 0,
                            'sample_rate': 48000  # Project Aria 기본값
                        },
                        'levels': {
                            'rms': 0.0,  # 실제 계산은 생략 (성능상)
                            'peak': 0.0
                        }
                    }
                except:
                    parsed_data = {'audio_info': {'error': 'parsing failed'}}
            
            if parsed_data:
                # Queue에 센서 데이터 저장
                if self.sensor_queues[sensor_type].full():
                    try:
                        self.sensor_queues[sensor_type].get_nowait()
                    except Empty:
                        pass
                
                sensor_item = {
                    'sensor_data': parsed_data,
                    'timestamp_ns': timestamp_ns,
                    'frame_number': self.sensor_counts[sensor_type],
                    'sensor_type': sensor_type,
                    'sensor_name': sensor_config.get('name', sensor_type)
                }
                
                self.sensor_queues[sensor_type].put(sensor_item)
                self.sensor_data[sensor_type] = sensor_item
                
                print(f"🧭 [{sensor_type}] Frame {self.sensor_counts[sensor_type]}")
                
        except Exception as e:
            logger.error(f"센서 Observer 콜백 오류 [{sensor_type}]: {e}")
    
    def get_latest_sensor_data(self, sensor_type: str) -> Optional[dict]:
        """특정 센서의 최신 데이터 반환"""
        try:
            return self.sensor_queues[sensor_type].get_nowait()
        except Empty:
            return None
    
    def get_all_latest_sensors(self) -> Dict[str, dict]:
        """모든 센서의 최신 데이터 반환"""
        result = {}
        for sensor_type in self.sensor_queues.keys():
            latest = self.get_latest_sensor_data(sensor_type)
            if latest:
                result[sensor_type] = latest
        return result


class ConcurrentSensorStreaming:
    """
    Project Aria 공식 deliver_queued_sensor_data 기반 동시 센서 스트리밍
    """
    def __init__(self, vrs_file_path: str):
        self.vrs_file_path = vrs_file_path
        self.provider = None
        self.observer = ConcurrentSensorObserver()
        self.is_streaming = False
        self.streaming_thread = None
        
        # VRS 프로바이더 초기화
        try:
            self.provider = data_provider.create_vrs_data_provider(vrs_file_path)
            if not self.provider:
                raise Exception("Invalid VRS data provider")
            print(f"✅ VRS 센서 프로바이더 생성: {vrs_file_path}")
        except Exception as e:
            logger.error(f"VRS 초기화 실패: {e}")
            raise
    
    def setup_concurrent_sensor_options(self):
        """
        공식 deliver_queued_sensor_data 옵션 설정 - 센서 동시 (ipynb 패턴 기반)
        """
        # Step 1: 공식 패턴 - 기본 옵션 획득
        options = self.provider.get_default_deliver_queued_options()
        
        # Step 2: 시간 범위 설정
        options.set_truncate_first_device_time_ns(int(1e8))  # 0.1초 후
        options.set_truncate_last_device_time_ns(int(1e9))   # 1초 전 (ipynb 패턴)
        
        # Step 3: 모든 센서 비활성화 후 센서만 활성화
        options.deactivate_stream_all()
        
        # Step 4: ipynb 패턴 - RecordableTypeId로 센서 활성화
        try:
            # IMU 센서들 (ipynb 패턴)
            imu_stream_ids = options.get_stream_ids(RecordableTypeId.SLAM_IMU_DATA)
            print(f"✅ IMU 스트림 발견: {len(imu_stream_ids)}개")
            for stream_id in imu_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 10)  # ipynb와 동일
                print(f"✅ IMU {stream_id} 활성화")
        except Exception as e:
            print(f"❌ IMU 활성화 실패: {e}")
            
        try:
            # 자력계 (RecordableTypeId로 검색)
            mag_stream_ids = options.get_stream_ids(RecordableTypeId.MAGNETOMETER_DATA)
            print(f"✅ 자력계 스트림 발견: {len(mag_stream_ids)}개")
            for stream_id in mag_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 10)
                print(f"✅ 자력계 {stream_id} 활성화")
        except Exception as e:
            print(f"❌ 자력계 활성화 실패: {e}")
            
        try:
            # 기압계 (RecordableTypeId로 검색)
            baro_stream_ids = options.get_stream_ids(RecordableTypeId.BAROMETER_DATA)
            print(f"✅ 기압계 스트림 발견: {len(baro_stream_ids)}개")
            for stream_id in baro_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 10)
                print(f"✅ 기압계 {stream_id} 활성화")
        except Exception as e:
            print(f"❌ 기압계 활성화 실패: {e}")
            
        try:
            # 오디오 (RecordableTypeId로 검색)
            audio_stream_ids = options.get_stream_ids(RecordableTypeId.AUDIO_DATA)
            print(f"✅ 오디오 스트림 발견: {len(audio_stream_ids)}개")
            for stream_id in audio_stream_ids:
                options.activate_stream(stream_id)
                options.set_subsample_rate(stream_id, 20)  # 오디오는 더 빠르므로
                print(f"✅ 오디오 {stream_id} 활성화")
        except Exception as e:
            print(f"❌ 오디오 활성화 실패: {e}")
        
        return options
    
    def start_concurrent_sensor_streaming(self):
        """동시 센서 스트리밍 시작"""
        if self.is_streaming:
            return "이미 센서 스트리밍 중"
        
        self.is_streaming = True
        self.streaming_thread = threading.Thread(target=self._concurrent_sensor_loop)
        self.streaming_thread.daemon = True
        self.streaming_thread.start()
        
        print("🧭 동시 센서 스트리밍 시작")
        return "동시 센서 스트리밍 시작됨"
    
    def stop_sensor_streaming(self):
        """센서 스트리밍 중지"""
        self.is_streaming = False
        if self.streaming_thread:
            self.streaming_thread.join(timeout=5.0)
        print("⏹️ 동시 센서 스트리밍 중지")
        return "센서 스트리밍 중지됨"
    
    def _concurrent_sensor_loop(self):
        """
        공식 deliver_queued_sensor_data 이터레이터 기반 동시 센서 스트리밍 루프 + 순환 재생
        """
        replay_count = 0
        
        while self.is_streaming:
            try:
                replay_count += 1
                print(f"🔄 센서 순환 재생 시작 - {replay_count}회차")
                
                # 공식 옵션 설정
                options = self.setup_concurrent_sensor_options()
                
                # 공식 이터레이터 생성
                iterator = self.provider.deliver_queued_sensor_data(options)
                
                print(f"🧭 공식 센서 이터레이터 시작 ({replay_count}회차)")
                
                # 스트림 ID -> sensor_type 매핑 생성 (동적 검색)
                stream_to_sensor = {}
                
                # 실제 VRS 파일에서 모든 스트림 확인하고 매핑
                all_streams = self.provider.get_all_streams()
                for stream_id in all_streams:
                    try:
                        label = self.provider.get_label_from_stream_id(stream_id)
                        print(f"🔍 스트림 발견: {stream_id} -> {label}")
                        
                        # 라벨 기반으로 센서 타입 결정
                        if 'imu' in label.lower():
                            sensor_name = label.replace('camera-', '').replace('-', '_')
                            stream_to_sensor[str(stream_id)] = (sensor_name, {'name': sensor_name, 'type': 'imu'})
                        elif 'mag' in label.lower() or 'magnetometer' in label.lower():
                            stream_to_sensor[str(stream_id)] = ('magnetometer', {'name': 'magnetometer', 'type': 'magnetometer'})
                        elif 'baro' in label.lower() or 'barometer' in label.lower():
                            stream_to_sensor[str(stream_id)] = ('barometer', {'name': 'barometer', 'type': 'barometer'})
                        elif 'mic' in label.lower() or 'audio' in label.lower():
                            stream_to_sensor[str(stream_id)] = ('audio', {'name': 'audio', 'type': 'audio'})
                    except Exception as e:
                        print(f"❌ 스트림 {stream_id} 처리 실패: {e}")
                
                print(f"🧭 센서 매핑 생성: {len(stream_to_sensor)}개 스트림")
                
                sensor_count_in_cycle = 0
                
                for sensor_data in iterator:
                    if not self.is_streaming:
                        break
                    
                    # 센서 데이터 정보 추출
                    stream_id = str(sensor_data.stream_id())
                    sensor_type_str = str(sensor_data.sensor_data_type())
                    
                    # 센서 데이터만 처리
                    if stream_id in stream_to_sensor:
                        sensor_type, sensor_config = stream_to_sensor[stream_id]
                        try:
                            timestamp_ns = sensor_data.get_time_ns(TimeDomain.DEVICE_TIME)
                            
                            # 센서별 데이터 추출 및 Observer 호출
                            if sensor_type_str == 'SensorDataType.IMU':
                                imu_data = sensor_data.imu_data()
                                self.observer.on_sensor_data_received(sensor_type, imu_data, timestamp_ns, sensor_config)
                                
                            elif sensor_type_str == 'SensorDataType.MAGNETOMETER':
                                mag_data = sensor_data.magnetometer_data()
                                self.observer.on_sensor_data_received(sensor_type, mag_data, timestamp_ns, sensor_config)
                                
                            elif sensor_type_str == 'SensorDataType.BAROMETER':
                                baro_data = sensor_data.barometer_data()
                                self.observer.on_sensor_data_received(sensor_type, baro_data, timestamp_ns, sensor_config)
                                
                            elif sensor_type_str == 'SensorDataType.AUDIO':
                                audio_data, record = sensor_data.audio_data_and_record()
                                self.observer.on_sensor_data_received(sensor_type, audio_data, timestamp_ns, sensor_config)
                            
                            sensor_count_in_cycle += 1
                            
                        except Exception as e:
                            logger.error(f"센서 처리 오류 [{sensor_type}]: {e}")
                
                print(f"✅ {replay_count}회차 센서 순환 완료 (총 {sensor_count_in_cycle} 센서 데이터)")
                
                # 스트리밍이 계속 활성화되어 있으면 자동으로 다시 시작
                if self.is_streaming:
                    print("🔄 센서 데이터 끝 - 처음부터 다시 재생")
                    time.sleep(0.1)  # 짧은 대기 후 재시작
                    
            except Exception as e:
                logger.error(f"동시 센서 스트리밍 루프 오류 ({replay_count}회차): {e}")
                print(f"❌ 센서 스트리밍 오류 ({replay_count}회차): {e}")
                
                # 오류 발생시 잠시 대기 후 재시도
                if self.is_streaming:
                    print("⏳ 3초 후 센서 재시도...")
                    time.sleep(3)
        
        print(f"⏹️ 동시 센서 스트리밍 루프 종료 (총 {replay_count}회차 재생)")


# 글로벌 인스턴스
concurrent_sensor_streaming = None

def get_concurrent_sensor_streaming():
    """글로벌 동시 센서 스트리밍 인스턴스 획득"""
    global concurrent_sensor_streaming
    
    if concurrent_sensor_streaming is None:
        # 첫 번째 available 세션 사용
        session = AriaStreamingSession.objects.filter(status='READY').first()
        if not session:
            raise Exception("No available streaming session")
        
        concurrent_sensor_streaming = ConcurrentSensorStreaming(session.vrs_file_path)
    
    return concurrent_sensor_streaming


@method_decorator(csrf_exempt, name='dispatch')
class ConcurrentSensorControlView(View):
    """동시 센서 스트리밍 제어 API"""
    
    def post(self, request, action):
        """센서 스트리밍 제어"""
        try:
            streaming = get_concurrent_sensor_streaming()
            
            if action == 'start':
                result = streaming.start_concurrent_sensor_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'method': '공식 deliver_queued_sensor_data + Observer',
                    'sensors': list(streaming.observer.sensor_mappings.keys()),
                    'streaming': streaming.is_streaming
                })
                
            elif action == 'stop':
                result = streaming.stop_sensor_streaming()
                return JsonResponse({
                    'status': 'success',
                    'message': result,
                    'streaming': streaming.is_streaming
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


class ConcurrentSensorDataView(View):
    """동시 센서 최신 데이터 API"""
    
    def get(self, request):
        """모든 센서의 최신 데이터를 JSON으로 반환"""
        try:
            streaming = get_concurrent_sensor_streaming()
            all_sensors = streaming.observer.get_all_latest_sensors()
            
            return JsonResponse({
                'status': 'success',
                'method': '공식 Sensor Observer 패턴',
                'sensors': all_sensors,
                'sensor_count': len(all_sensors),
                'total_frames': sum(streaming.observer.sensor_counts.values())
            })
            
        except Exception as e:
            logger.error(f"센서 데이터 가져오기 실패: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class ConcurrentSensorPageView(View):
    """동시 센서 스트리밍 페이지"""
    
    def get(self, request):
        """동시 센서 스트리밍 HTML 페이지"""
        
        html_template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧭 동시 센서 스트리밍</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: white;
        }
        
        .container {
            max-width: 1600px;
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
        
        .sensors-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .sensor-box {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        
        .sensor-title {
            text-align: center;
            font-size: 1.2rem;
            margin-bottom: 15px;
            color: #e74c3c;
        }
        
        .sensor-data {
            font-family: monospace;
            font-size: 0.9rem;
            line-height: 1.6;
        }
        
        .controls {
            text-align: center;
            margin: 20px 0;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 0 10px;
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(39,174,96,0.3);
        }
        
        .stop-btn {
            background: linear-gradient(45deg, #e74c3c, #c0392b);
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
            color: #e74c3c;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">🧭 동시 센서 스트리밍</h1>
            <p>Project Aria 공식 Observer 패턴 + deliver_queued_sensor_data</p>
        </div>
        
        <div class="sensors-grid">
            <div class="sensor-box">
                <div class="sensor-title">🧭 IMU Right</div>
                <div class="sensor-data" id="imu-right-data">대기 중...</div>
            </div>
            
            <div class="sensor-box">
                <div class="sensor-title">🧭 IMU Left</div>
                <div class="sensor-data" id="imu-left-data">대기 중...</div>
            </div>
            
            <div class="sensor-box">
                <div class="sensor-title">🧲 자력계</div>
                <div class="sensor-data" id="magnetometer-data">대기 중...</div>
            </div>
            
            <div class="sensor-box">
                <div class="sensor-title">🌡️ 기압계</div>
                <div class="sensor-data" id="barometer-data">대기 중...</div>
            </div>
            
            <div class="sensor-box">
                <div class="sensor-title">🎵 오디오</div>
                <div class="sensor-data" id="audio-data">대기 중...</div>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn" onclick="startSensorStreaming()">🚀 센서 스트리밍 시작</button>
            <button class="btn stop-btn" onclick="stopSensorStreaming()">🛑 센서 스트리밍 중지</button>
        </div>
        
        <div class="status" id="status">준비됨 - 공식 Sensor Observer 패턴</div>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value" id="totalSensors">0</div>
                <div class="stat-label">총 센서 데이터</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="activeSensors">0</div>
                <div class="stat-label">활성 센서</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="sensorFps">0</div>
                <div class="stat-label">센서 FPS</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="replayCount">0</div>
                <div class="stat-label">🔄 순환 재생</div>
            </div>
        </div>
    </div>

    <script>
        let sensorStreamingInterval = null;
        let sensorCount = 0;
        let lastSensorTime = Date.now();
        let streamingStartTime = null;
        let replayCount = 0;
        
        function startSensorStreaming() {
            fetch('/api/v1/aria-sessions/concurrent-sensor/start/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('센서 스트리밍 시작:', data);
                
                if (data.status === 'success') {
                    document.getElementById('status').textContent = '🧭 동시 센서 스트리밍 활성화 (순환 재생)';
                    
                    // 스트리밍 시작 시간 기록
                    streamingStartTime = Date.now();
                    replayCount = 1;
                    document.getElementById('replayCount').textContent = replayCount;
                    
                    // 센서 데이터 로딩 시작
                    sensorStreamingInterval = setInterval(loadSensorData, 200); // 200ms마다
                    loadSensorData();
                }
            })
            .catch(error => {
                console.error('센서 스트리밍 시작 실패:', error);
            });
        }
        
        function loadSensorData() {
            fetch('/api/v1/aria-sessions/concurrent-sensor-data/')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    const sensors = data.sensors;
                    
                    // 각 센서 데이터 업데이트 (실제 키 이름 사용)
                    updateSensorDisplay('imu_right', sensors['imu_right']);
                    updateSensorDisplay('imu_left', sensors['imu_left']);
                    updateSensorDisplay('magnetometer', sensors['magnetometer']);
                    updateSensorDisplay('barometer', sensors['barometer']);
                    updateSensorDisplay('audio', sensors['audio']);
                    
                    // 디버깅: 실제 센서 키들 확인
                    console.log('실제 센서 키들:', Object.keys(sensors));
                    
                    // 통계 업데이트
                    document.getElementById('totalSensors').textContent = data.total_frames;
                    document.getElementById('activeSensors').textContent = Object.keys(sensors).length;
                    
                    sensorCount += Object.keys(sensors).length;
                }
            })
            .catch(error => {
                console.log('센서 데이터 로드:', error.message);
            });
        }
        
        function updateSensorDisplay(sensorType, sensorData) {
            console.log(`🔍 updateSensorDisplay 호출: ${sensorType}`, sensorData);
            
            let element;
            
            // 실제 센서 타입에 맞게 HTML 엘리먼트 매핑
            if (sensorType === 'imu_left') {
                element = document.getElementById('imu-left-data');
            } else if (sensorType === 'imu_right') {
                element = document.getElementById('imu-right-data');
            } else if (sensorType === 'magnetometer') {
                element = document.getElementById('magnetometer-data');
            } else if (sensorType === 'barometer') {
                element = document.getElementById('barometer-data');
            } else if (sensorType === 'audio') {
                element = document.getElementById('audio-data');
            }
            
            console.log(`🎯 Element found: ${element ? 'YES' : 'NO'}, SensorData: ${sensorData ? 'YES' : 'NO'}`);
            
            if (!element || !sensorData) {
                console.log(`❌ 종료: element=${!!element}, sensorData=${!!sensorData}`);
                return;
            }
            
            let displayText = '';
            const data = sensorData.sensor_data;
            
            if (sensorType.startsWith('imu')) {
                const accel = data.accelerometer;
                const gyro = data.gyroscope;
                displayText = `🔥 LIVE 데이터
가속도: ${accel.x.toFixed(3)}, ${accel.y.toFixed(3)}, ${accel.z.toFixed(3)} ${accel.unit}
자이로: ${gyro.x.toFixed(4)}, ${gyro.y.toFixed(4)}, ${gyro.z.toFixed(4)} ${gyro.unit}
온도: ${data.temperature.value || 'N/A'}°C
Frame: ${sensorData.frame_number}`;
            } else if (sensorType === 'magnetometer') {
                const mag = data.magnetic_field;
                displayText = `🔥 LIVE 데이터
자기장: ${mag.x.toFixed(8)}, ${mag.y.toFixed(8)}, ${mag.z.toFixed(8)} ${mag.unit}
온도: ${data.temperature.value}${data.temperature.unit}
Frame: ${sensorData.frame_number}`;
            } else if (sensorType === 'barometer') {
                displayText = `🔥 LIVE 데이터
기압: ${data.pressure.value.toFixed(0)} ${data.pressure.unit}
온도: ${data.temperature.value}${data.temperature.unit}
고도: ${data.altitude.value.toFixed(1)} ${data.altitude.unit}
Frame: ${sensorData.frame_number}`;
            } else if (sensorType === 'audio') {
                const audio = data.audio_info;
                displayText = `🔥 LIVE 데이터
블록: ${audio.blocks}
샘플: ${audio.total_samples}
채널: ${audio.channels}
샘플레이트: ${audio.sample_rate} Hz
Frame: ${sensorData.frame_number}`;
            }
            
            console.log(`✅ HTML 업데이트 완료: ${sensorType} -> ${displayText.substring(0, 50)}...`);
            element.textContent = displayText;
        }
        
        function stopSensorStreaming() {
            if (sensorStreamingInterval) {
                clearInterval(sensorStreamingInterval);
                sensorStreamingInterval = null;
            }
            
            fetch('/api/v1/aria-sessions/concurrent-sensor/stop/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                console.log('센서 스트리밍 중지:', data);
                
                document.getElementById('status').textContent = '⏹️ 센서 스트리밍 중지됨';
                
                // 모든 센서 데이터 초기화
                ['imu-right', 'imu-left', 'magnetometer', 'barometer', 'audio'].forEach(sensor => {
                    document.getElementById(sensor + '-data').textContent = '대기 중...';
                });
            });
        }
        
        // 센서 통계 업데이트
        setInterval(() => {
            const now = Date.now();
            const timeDiff = now - lastSensorTime;
            
            if (timeDiff > 1000) {
                const fps = Math.round(sensorCount * 1000 / timeDiff);
                document.getElementById('sensorFps').textContent = fps;
                
                // 순환 재생 감지
                if (streamingStartTime) {
                    const currentReplay = Math.floor((now - streamingStartTime) / 30000); // 30초마다 사이클
                    if (currentReplay > replayCount - 1) {
                        replayCount = currentReplay + 1;
                        document.getElementById('replayCount').textContent = replayCount;
                        console.log(`🔄 센서 순환 재생 ${replayCount}회차 감지`);
                    }
                }
                
                lastSensorTime = now;
                sensorCount = 0;
            }
        }, 1000);
    </script>
</body>
</html>
        '''
        
        return HttpResponse(html_template)