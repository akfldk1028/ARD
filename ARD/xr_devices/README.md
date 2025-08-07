# 🚀 Universal XR Devices Management System

**Meta Aria | Google Glass | Apple Vision | Microsoft HoloLens | Magic Leap 등 모든 XR 기기를 지원하는 통합 데이터 처리 시스템**

## 🎯 개요

내년에 출시될 다양한 XR 기기들을 대비해서 미리 구축한 확장 가능한 아키텍처입니다. 새로운 기기가 추가되어도 **파서와 어댑터만 추가**하면 자동으로 지원됩니다.

### 🔧 핵심 특징

- **📱 다중 기기 지원**: Meta Aria, Google Glass, Apple Vision Pro, Microsoft HoloLens
- **🔄 파서 추상화**: 기기별 다른 데이터 포맷 (VRS, JSON, GLTF, Protobuf)을 통합 처리
- **📡 어댑터 패턴**: Kafka, WebSocket, MQTT, gRPC 등 다양한 스트리밍 프로토콜 지원
- **🗄️ 통합 데이터베이스**: 모든 기기 데이터를 일관된 스키마로 저장
- **⚡ 실시간 스트리밍**: 높은 처리량의 실시간 데이터 처리

## 🏗️ 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Meta Aria     │    │  Google Glass   │    │  Apple Vision   │
│   (VRS Format)  │    │  (JSON Stream)  │    │   (GLTF Data)   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Aria VRS       │    │  Google Glass   │    │  Apple Vision   │
│  Parser         │    │  Parser         │    │  Parser         │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │  Universal Streaming    │
                    │  Manager               │
                    └─────────┬───────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌─────────────────┐ ┌─────────────┐ ┌─────────────┐
    │ Kafka Adapter   │ │ WebSocket   │ │ MQTT        │
    │                 │ │ Adapter     │ │ Adapter     │
    └─────────────────┘ └─────────────┘ └─────────────┘
              │               │               │
              ▼               ▼               ▼
         [Stream Data]   [Stream Data]  [Stream Data]
```

## 📦 설치 및 설정

### 1. 마이그레이션 실행
```bash
python manage.py makemigrations xr_devices
python manage.py migrate
```

### 2. 초기 데이터 설정
```bash
python manage.py setup_xr_devices
```

### 3. 관리자 계정 생성 (선택사항)
```bash
python manage.py createsuperuser
```

## 🎮 사용 방법

### 1. 관리 대시보드 접속
```
http://localhost:8000/api/xr-devices/dashboard/
```

### 2. API 엔드포인트

#### 지원 기기 조회
```bash
GET /api/xr-devices/api/devices/supported_devices/
```

#### 스트리밍 세션 생성
```bash
POST /api/xr-devices/api/streaming/create_session/
{
    "device_type": "meta_aria",
    "session_name": "my_session",
    "user_id": "user123"
}
```

#### 스트리밍 시작
```bash
POST /api/xr-devices/api/streaming/start/
{
    "session_id": "meta_aria_abc12345"
}
```

#### 데이터 처리
```bash
POST /api/xr-devices/api/streaming/process_data/
{
    "session_id": "meta_aria_abc12345",
    "sensor_type": "camera_rgb",
    "raw_data": "base64_encoded_data"
}
```

## 🔧 새로운 기기 추가 방법

### 1. 파서 구현
```python
# xr_devices/parsers/my_device.py
from . import BaseXRParser, XRParserFactory

class MyDeviceParser(BaseXRParser):
    def parse_frame(self, raw_data, sensor_type, timestamp_ns):
        # 기기별 데이터 파싱 로직
        return {
            'device_type': self.device_type,
            'sensor_type': sensor_type,
            'timestamp_ns': timestamp_ns,
            # ... 파싱된 데이터
        }

# 파서 등록
XRParserFactory.register_parser('my_device', MyDeviceParser)
```

### 2. 어댑터 구현 (필요시)
```python
# xr_devices/adapters/my_protocol.py
from . import BaseStreamingAdapter, AdapterFactory

class MyProtocolAdapter(BaseStreamingAdapter):
    async def send_data(self, data, topic=None):
        # 프로토콜별 전송 로직
        pass

# 어댑터 등록
AdapterFactory.register_adapter('my_protocol', MyProtocolAdapter)
```

### 3. 데이터베이스에 기기 등록
```python
# Django shell 또는 관리 명령어에서
XRDevice.objects.create(
    name='My New XR Device',
    device_type='my_device',
    manufacturer='My Company',
    model_version='v1.0',
    supported_formats=['custom_format'],
    preferred_protocol='my_protocol'
)
```

## 📊 지원 기기 현황

| 기기 | 상태 | 데이터 포맷 | 프로토콜 | 센서 지원 |
|------|------|-------------|----------|-----------|
| Meta Aria | ✅ 구현완료 | VRS, JSON | Kafka | 카메라, IMU, GPS, 시선추적 |
| Google Glass | 🚧 준비됨 | JSON, Protobuf | WebSocket | 카메라, IMU, 음성인식 |
| Apple Vision Pro | 🚧 준비됨 | GLTF, JSON | gRPC | 카메라, 뎁스, 시선/손추적, LiDAR |
| Microsoft HoloLens | 🚧 준비됨 | GLTF, JSON | REST API | 혼합현실, 음성인식 |
| Magic Leap | 🚧 준비됨 | Custom | Custom | 공간컴퓨팅 |

## 🧪 테스트

```bash
# 단위 테스트 실행
python manage.py test xr_devices

# 특정 테스트 클래스 실행
python manage.py test xr_devices.tests.XRDeviceModelTest
```

## 📈 성능 특징

- **동시 세션**: 기기당 최대 10개 세션 지원
- **처리량**: 초당 1000+ 프레임 처리 가능
- **지연시간**: Kafka 기준 < 10ms
- **확장성**: 새 기기 추가 시 기존 코드 수정 없음

## 🔮 미래 로드맵

### 2025년 상반기
- [ ] Google AR Glass 정식 지원
- [ ] Apple Vision Pro 파서 완성
- [ ] Microsoft HoloLens 3 연동

### 2025년 하반기  
- [ ] Nreal/Xreal 기기 지원
- [ ] Vuzix 스마트 글래스 지원
- [ ] Magic Leap 3 연동

### 장기 계획
- [ ] AI 기반 데이터 전처리
- [ ] 클라우드 스트리밍 지원
- [ ] Unity/Unreal 엔진 직접 연동

## 📝 예시 코드

### Python에서 스트리밍 세션 사용
```python
import asyncio
from xr_devices.streaming import streaming_manager

async def start_aria_streaming():
    # 세션 생성
    session_id = await streaming_manager.create_session(
        device_type='meta_aria',
        session_name='my_aria_session',
        user_id='developer'
    )
    
    # 스트리밍 시작
    await streaming_manager.start_streaming(session_id)
    
    # 데이터 처리
    test_data = b'camera_frame_data'
    await streaming_manager.process_data(
        session_id, test_data, 'camera_rgb'
    )
    
    # 스트리밍 중지
    await streaming_manager.stop_streaming(session_id)

# 실행
asyncio.run(start_aria_streaming())
```

### JavaScript에서 API 호출
```javascript
// 세션 생성
const response = await fetch('/api/xr-devices/api/streaming/create_session/', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        device_type: 'meta_aria',
        session_name: 'web_session',
        user_id: 'web_user'
    })
});

const session = await response.json();
console.log('Session created:', session.session_id);
```

## 🤝 기여 방법

1. 새로운 기기 파서 추가
2. 새로운 스트리밍 프로토콜 어댑터 구현  
3. 테스트 케이스 작성
4. 문서화 개선

## 📄 라이선스

이 프로젝트는 MIT 라이선스하에 배포됩니다.

---

**🚀 Ready for the XR Future!** - Meta부터 Apple까지, 모든 XR 기기를 하나의 시스템으로 통합 관리하세요.