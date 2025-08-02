# 01. ARD 시스템 아키텍처

> **📖 문서 가이드**: [00_INDEX.md](00_INDEX.md) | **다음**: [02_DOCKER_SETUP_GUIDE.md](02_DOCKER_SETUP_GUIDE.md)  
> **카테고리**: 시스템 이해 및 설치 | **난이도**: ⭐⭐ | **예상 시간**: 15분

## 🎯 시스템 개요

**ARD (Aria Real-time Data) 시스템**
- Project Aria AR 안경의 멀티 센서 데이터를 실시간으로 처리
- Django REST API 백엔드 + Unity AR 클라이언트 구조
- Kafka 기반 실시간 스트리밍 파이프라인

---

## 🏗️ 전체 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Project Aria  │────│  Django Backend │────│   Unity Client  │
│   AR 안경        │    │   (REST API)    │    │   (AR 앱)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         │              ┌─────────────────┐                │
         └──────────────│ Kafka Streaming │────────────────┘
                        │   (실시간 처리)  │
                        └─────────────────┘
```

---

## 📡 데이터 플로우 아키텍처

### 1️⃣ Project Aria → VRS 파일
```
Project Aria 하드웨어 (4개 센서)
├── RGB 카메라 ("214-1")      → 1408x1408 RGB24 (컬러)
├── SLAM Left ("1201-1")      → 640x480 GRAY8 (흑백)  
├── SLAM Right ("1201-2")     → 640x480 GRAY8 (흑백)
└── Eye Tracking ("211-1")    → 320x240 GRAY8 (흑백)
                    ↓
              VRS 통합 파일
```

### 2️⃣ VRS → Kafka 스트리밍
```python
# VRSKafkaStreamer (vrs_reader.py)
async def stream_vrs_data():
    for stream_name, stream_id in self.stream_ids.items():
        # 모든 센서 데이터를 하나의 토픽으로 통합
        producer.send('vrs-raw-stream', {
            'stream_id': stream_id,      # "214-1", "1201-1", etc.
            'stream_name': stream_name,  # "camera-rgb", etc.
            'pixel_format': format,      # "RGB24", "GRAY8"
            'frame_data': data
        })
```

### 3️⃣ Kafka → Django Database
```python
# AriaKafkaConsumer (consumers.py)
topic_handlers = {
    'vrs-raw-stream': handle_vrs_frame,           # 통합 VRS 처리
    'mps-eye-gaze-general': handle_eye_gaze,      # 시선 추적
    'mps-hand-tracking': handle_hand_tracking,    # 손 추적
    'mps-slam-trajectory': handle_slam_trajectory # 공간 추적
}

def handle_vrs_frame(message):
    # Stream ID 기반 분류 저장
    VRSStream.objects.create(
        stream_id=message['stream_id'],
        stream_name=message['stream_name'],
        pixel_format=message['pixel_format']
    )
```

---

## 🗄️ Django 데이터 모델 구조

### 핵심 5개 모델
```python
# 1. 세션 관리
AriaSession
├── session_id: "real_mps_sample_001" 
├── device_serial: "REAL_MPS_DEVICE"
└── status: "ACTIVE" | "COMPLETED"

# 2. VRS 원본 스트림 (통합)
VRSStream  
├── stream_id: "214-1" | "1201-1" | "1201-2" | "211-1"
├── stream_name: "camera-rgb" | "camera-slam-left" 
├── pixel_format: "RGB24" | "GRAY8"
└── image_shape: [height, width, channels]

# 3. 시선 추적 (MPS 처리)
EyeGazeData
├── yaw, pitch: 시선 각도 (도)
├── depth_m: 응시 깊이 (미터)
└── gaze_type: "general" | "personalized"

# 4. 손 추적 (MPS 처리)  
HandTrackingData
├── left_hand_landmarks: [21개 관절 좌표]
├── right_hand_landmarks: [21개 관절 좌표]
└── palm/wrist_normal: 손바닥/손목 방향벡터

# 5. 공간 추적 (MPS 처리)
SLAMTrajectoryData
├── transform_matrix: 4x4 SE3 변환행렬
└── position_x/y/z: 빠른 쿼리용 위치 추출
```

---

## 🔄 REST API 엔드포인트

### ViewSet 기반 전문적 API 구조
```
http://localhost:8000/api/streams/api/

├── /sessions/           → AriaSessionViewSet
├── /vrs-streams/        → VRSStreamViewSet (통합 스트림)
├── /eye-gaze/          → EyeGazeDataViewSet  
├── /hand-tracking/     → HandTrackingDataViewSet
├── /slam-trajectory/   → SLAMTrajectoryDataViewSet
└── /kafka-status/      → StreamingControlView
```

### 고급 쿼리 지원
```bash
# Stream ID 기반 필터링
GET /vrs-streams/?stream_id=214-1           # RGB만
GET /vrs-streams/?stream_id=1201-1          # SLAM Left만

# 센서 타입별 필터링  
GET /vrs-streams/?stream_name=camera-rgb    # RGB 카메라
GET /vrs-streams/?pixel_format=GRAY8        # 흑백 센서만

# 시간순 정렬 + 페이징
GET /vrs-streams/?ordering=-frame_index&limit=10
```

---

## 🎮 Unity 클라이언트 아키텍처

### Stream ID 기반 센서 분류 처리
```csharp
// ARDUnityClient.cs - 핵심 로직
public void ProcessVRSData(VRSStreamData data) 
{
    switch(data.stream_id) 
    {
        case "214-1":   // RGB 카메라
            ProcessRGBFrame(data);      // 메인 AR 디스플레이
            break;
            
        case "1201-1":  // SLAM Left
        case "1201-2":  // SLAM Right  
            ProcessSLAMFrame(data);     // 공간 추적 & 깊이 인식
            break;
            
        case "211-1":   // Eye Tracking
            ProcessEyeFrame(data);      // 시선 기반 UI 포커싱
            break;
    }
}
```

### 실시간 데이터 구독 시스템
```csharp
// 이벤트 기반 실시간 처리
public static event Action<EyeGazeData[]> OnEyeGazeDataReceived;
public static event Action<HandTrackingData[]> OnHandTrackingDataReceived;
public static event Action<SlamTrajectoryData[]> OnSlamTrajectoryDataReceived;

// 30fps 실시간 데이터 풀링
IEnumerator FetchRealtimeData() {
    while (true) {
        yield return FetchEyeGazeData();      // 시선 추적
        yield return FetchHandTrackingData(); // 손 추적  
        yield return FetchSLAMData();         // 공간 추적
        yield return new WaitForSeconds(0.033f); // ~30fps
    }
}
```

---

## 🌊 실시간 스트리밍 파이프라인

### Kafka Topics 구조
```python
KAFKA_TOPICS = {
    # VRS 원본 스트림 (통합)
    'vrs-raw-stream': 'vrs-raw-stream',
    
    # MPS 처リ된 데이터 (분리)
    'mps-eye-gaze-general': 'mps-eye-gaze-general',
    'mps-eye-gaze-personalized': 'mps-eye-gaze-personalized', 
    'mps-hand-tracking': 'mps-hand-tracking',
    'mps-slam-trajectory': 'mps-slam-trajectory',
    'analytics-real-time': 'analytics-real-time'
}
```

### 스트리밍 명령어
```bash
# VRS 파일을 Kafka로 실시간 스트리밍
python manage.py stream_vrs_data \
    --vrs-file sample.vrs \
    --mps-data-path mps_samples \
    --duration 60

# Django Kafka 컨슈머 시작  
python manage.py start_kafka_consumer
```

---

## 🐳 Docker 컨테이너 환경

### 서비스 구성
```yaml
services:
  django-ard:              # Django API 서버
    ports: ["8000:8000"]
    depends_on: [postgres]
    
  postgres:                # PostgreSQL DB
    image: postgres:15-alpine
    
  redis:                   # Redis 캐시 (선택적)
    image: redis:7-alpine
    
# Kafka는 외부에서 수동 실행 (host.docker.internal:9092)
```

### 완전 자동화 배포
```bash
# 1. 전체 시스템 시작
docker-compose up -d

# 2. 샘플 데이터 로드
docker exec django-ard python manage.py load_sample_data_fixed

# 3. Unity 클라이언트 연결
# ARDUnityClient.cs → API Base URL: http://localhost:8000
```

---

## 📊 시스템 성능 및 최적화

### 데이터 처리 성능
- **VRS 프레임**: 4개 센서 통합 처리
- **실시간 스트리밍**: ~30fps (33ms 간격)  
- **API 응답**: <200ms (페이징/필터링 적용)
- **Unity 동기화**: 30Hz 실시간 데이터 구독

### 데이터베이스 최적화
```python
# 성능 인덱스
indexes = [
    models.Index(fields=['session', 'stream_id', 'device_timestamp_ns']),
    models.Index(fields=['stream_name', 'frame_index']),
    models.Index(fields=['timestamp'])
]

# 쿼리 최적화 (prefetch_related)
queryset = VRSStream.objects.prefetch_related('session').select_related()
```

---

## 🚀 핵심 기술적 혁신

### 1. **통합 VRS 스트리밍**
- 4개 센서를 하나의 Kafka 토픽으로 통합
- Stream ID 기반 센서 자동 분류
- Pixel Format 자동 인식 (RGB24/GRAY8)

### 2. **Django REST Framework 전문화**
- ViewSet 기반 CRUD 자동화
- 고급 필터링/페이징/정렬 지원
- Computed Fields (duration, gaze_direction 등)

### 3. **Unity 실시간 연동**
- 이벤트 기반 데이터 구독
- Stream ID 기반 센서별 처리 분기
- 30fps 실시간 AR 데이터 시각화

### 4. **Docker 완전 자동화**
- 원클릭 배포 환경
- Health Check 기반 의존성 관리
- 샘플 데이터 자동 로딩

---

## 💡 실제 활용 시나리오

### AR 앱 개발 예시
```csharp
// Unity에서 실제 AR 기능 구현
void Update() {
    // 1. 시선 기반 UI 포커싱
    if (eyeGazeData != null) {
        Vector3 gazeDirection = eyeGazeData.gaze_direction;
        FocusUIElement(gazeDirection);
    }
    
    // 2. 손 제스처 인식
    if (handData.has_left_hand) {
        ProcessHandGesture(handData.left_hand_landmarks);
    }
    
    // 3. 공간 추적 기반 AR 객체 배치
    if (slamData != null) {
        Matrix4x4 worldTransform = slamData.transform_matrix;
        PlaceARObject(worldTransform);
    }
}
```

---

## 🎯 시스템의 핵심 가치

✅ **완전한 통합**: VRS → MPS → API → Unity 전체 파이프라인  
✅ **실시간 성능**: 30fps 실시간 멀티센서 데이터 처리  
✅ **확장성**: 마이크로서비스 아키텍처 준비  
✅ **개발 효율성**: Docker 원클릭 배포 + 샘플 데이터  
✅ **Production Ready**: Django REST Framework 전문 구조  

**→ Project Aria AR 앱 개발을 위한 완전한 백엔드 인프라**