# ARD Class-Based API Structure - 완전 구현 버전

이 문서는 Project Aria ARD 시스템의 완전히 구현된 클래스 기반 Django REST API 구조를 설명합니다.

## 🎯 시스템 개요

**ARD (Aria Real-time Data)** 시스템은 Project Aria 안경에서 수집되는 모든 AR 데이터를 실시간으로 처리하고 Unity 클라이언트에게 API로 제공하는 완전한 백엔드 솔루션입니다.

## 🏗️ 아키텍처 개요

### Core Design Principles
- **Class-Based ViewSets**: 전문적인 DRF ViewSet 구조로 CRUD 자동화
- **Real-time Streaming**: Kafka를 통한 실시간 VRS/MPS 데이터 스트리밍
- **Docker Containerization**: 완전 자동화된 컨테이너 환경
- **Unity Integration**: C# 클라이언트를 위한 최적화된 API 설계
- **Project Aria Compatibility**: Meta의 공식 MPS 데이터 구조 완벽 지원

## 📁 완전 구현된 파일 구조

```
ARD/
├── 🐳 Docker 구성
│   ├── Dockerfile                     # Django 컨테이너 설정
│   ├── docker-compose.yml             # 전체 서비스 오케스트레이션
│   └── docker-entrypoint.sh           # 자동 초기화 스크립트
│
├── 🎮 Unity 연동
│   ├── ARDUnityClient.cs              # C# 클라이언트 코드
│   ├── unity_api_test.py              # API 테스트 스크립트
│   └── DOCKER_UNITY_SETUP.md          # Unity 연동 가이드
│
├── 📚 문서화
│   ├── PROJECT_ARIA_DATA_FIELDS_REFERENCE.md  # 완전한 필드 참조
│   ├── CLASS_BASED_REFACTORING_SUMMARY.md     # 리팩토링 요약
│   ├── DOCKER_SETUP_COMPLETE.md              # Docker 설정 가이드
│   └── CLAUDE.md                              # 프로젝트 개발 가이드
│
└── ARD/streams/                        # 🎯 Core Django App
    ├── 📊 데이터 모델
    │   └── models.py                   # 5개 주요 모델 (완전 구현)
    │
    ├── 🔄 API 레이어
    │   ├── serializers.py              # DRF 시리얼라이저 (모든 computed fields 포함)
    │   ├── views.py                    # ViewSet 기반 API (필터링/페이징)
    │   ├── urls.py                     # DRF Router 기반 URL 구성
    │   └── admin.py                    # 고급 Django Admin (시각화 포함)
    │
    ├── 🌊 스트리밍 시스템  
    │   ├── producers.py                # Kafka 프로듀서 (VRS/MPS 전송)
    │   ├── consumers.py                # Kafka 컨슈머 (실시간 저장)
    │   └── vrs_reader.py               # VRS 파일 스트리밍
    │
    └── 🛠️ 관리 명령어
        └── management/commands/
            ├── start_kafka_consumer.py      # Kafka 컨슈머 실행
            ├── stream_vrs_data.py           # VRS 스트리밍 명령
            ├── download_sample_data.py      # 샘플 데이터 다운로드
            ├── load_sample_data_fixed.py    # 실제 MPS CSV 로드
            └── test_class_based_api.py      # API 테스트 자동화
```

## 🗄️ 데이터 모델 구조

### 1. AriaSession (세션 관리)
```python
class AriaSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    session_uid = models.UUIDField()
    device_serial = models.CharField(max_length=50)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'), 
        ('ERROR', 'Error')
    ])
    metadata = models.JSONField(default=dict)
```

### 2. VRSStream (원본 영상 프레임)
```python
class VRSStream(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE)
    stream_id = models.CharField(max_length=20)  # "214-1", "1201-1", etc.
    stream_name = models.CharField(max_length=50)  # "camera-rgb", etc.
    device_timestamp_ns = models.BigIntegerField()
    frame_index = models.IntegerField()
    image_shape = models.JSONField()  # [height, width, channels]
    pixel_format = models.CharField(max_length=20)  # "RGB24", "GRAY8"
    kafka_offset = models.BigIntegerField(null=True)
```

### 3. EyeGazeData (시선 추적)
```python
class EyeGazeData(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE)
    device_timestamp_ns = models.BigIntegerField()
    gaze_type = models.CharField(max_length=20, choices=[
        ('general', 'General'),
        ('personalized', 'Personalized')
    ])
    yaw = models.FloatField()  # 시선 수평 각도 (도)
    pitch = models.FloatField()  # 시선 수직 각도 (도)
    depth_m = models.FloatField(null=True)  # 응시 깊이 (미터)
    confidence = models.FloatField(null=True)
    kafka_offset = models.BigIntegerField(null=True)
```

### 4. HandTrackingData (손 추적)
```python
class HandTrackingData(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE)
    device_timestamp_ns = models.BigIntegerField()
    left_hand_landmarks = models.JSONField(null=True)  # 21개 관절 좌표
    left_hand_wrist_normal = models.JSONField(null=True)  # [x, y, z]
    left_hand_palm_normal = models.JSONField(null=True)  # [x, y, z]
    right_hand_landmarks = models.JSONField(null=True) # 21개 관절 좌표
    right_hand_wrist_normal = models.JSONField(null=True)
    right_hand_palm_normal = models.JSONField(null=True)
    kafka_offset = models.BigIntegerField(null=True)
```

### 5. SLAMTrajectoryData (공간 위치 추적)
```python
class SLAMTrajectoryData(models.Model):
    session = models.ForeignKey(AriaSession, on_delete=models.CASCADE)
    device_timestamp_ns = models.BigIntegerField()
    transform_matrix = models.JSONField()  # 4x4 SE3 변환 행렬
    position_x = models.FloatField()  # 빠른 인덱싱을 위한 추출
    position_y = models.FloatField()
    position_z = models.FloatField()
    kafka_offset = models.BigIntegerField(null=True)
```

## 🔄 API 엔드포인트 구조

### RESTful API 설계
```
http://localhost:8000/api/streams/api/
```

| 엔드포인트 | HTTP 메소드 | 설명 | ViewSet |
|------------|-------------|------|---------|
| `/sessions/` | GET, POST, PUT, DELETE | AR 세션 관리 | AriaSessionViewSet |
| `/vrs-streams/` | GET, POST | VRS 원본 프레임 | VRSStreamViewSet |
| `/eye-gaze/` | GET, POST | 시선 추적 데이터 | EyeGazeDataViewSet |
| `/hand-tracking/` | GET, POST | 손 추적 데이터 | HandTrackingDataViewSet |
| `/slam-trajectory/` | GET, POST | 공간 위치 데이터 | SLAMTrajectoryDataViewSet |
| `/kafka-status/` | GET | 실시간 스트리밍 상태 | StreamingControlView |

### 고급 쿼리 기능

#### 필터링
```
GET /api/streams/api/eye-gaze/?session=3&gaze_type=personalized
GET /api/streams/api/hand-tracking/?has_left_hand=true
GET /api/streams/api/slam-trajectory/?position_x_min=0.5&position_x_max=1.0
```

#### 정렬 & 페이징
```
GET /api/streams/api/sessions/?ordering=-started_at&limit=10&offset=20
GET /api/streams/api/vrs-streams/?stream_name=camera-rgb&ordering=frame_index
```

#### 날짜 범위 필터
```
GET /api/streams/api/sessions/?started_at_after=2025-07-01&started_at_before=2025-07-31
```

## 🧩 시리얼라이저 구조

### Computed Fields 지원
```python
class AriaSessionSerializer(serializers.ModelSerializer):
    # 계산된 필드들
    duration = serializers.SerializerMethodField()
    stream_counts = serializers.SerializerMethodField()
    
    def get_duration(self, obj):
        if obj.ended_at and obj.started_at:
            return (obj.ended_at - obj.started_at).total_seconds()
        return (timezone.now() - obj.started_at).total_seconds()
    
    def get_stream_counts(self, obj):
        return {
            'vrs_frames': obj.vrs_streams.count(),
            'eye_gaze': obj.eye_gaze_data.count(),
            'hand_tracking': obj.hand_tracking_data.count(),
            'slam_trajectory': obj.slam_trajectory_data.count(),
        }

class EyeGazeDataSerializer(serializers.ModelSerializer):
    session_info = serializers.SerializerMethodField()
    gaze_direction = serializers.SerializerMethodField()
    
    def get_gaze_direction(self, obj):
        # 시선 방향을 3D 벡터로 변환
        import math
        yaw_rad = math.radians(obj.yaw)
        pitch_rad = math.radians(obj.pitch)
        
        x = math.sin(yaw_rad) * math.cos(pitch_rad)
        y = math.sin(pitch_rad)
        z = math.cos(yaw_rad) * math.cos(pitch_rad)
        
        return {'x': x, 'y': y, 'z': z}

class HandTrackingDataSerializer(serializers.ModelSerializer):
    has_left_hand = serializers.SerializerMethodField()
    has_right_hand = serializers.SerializerMethodField()
    
    def get_has_left_hand(self, obj):
        return obj.left_hand_landmarks is not None and len(obj.left_hand_landmarks) > 0
```

## 🎛️ Django Admin 인터페이스

### 시각적 데이터 디스플레이
```python
class AriaSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'device_serial', 'status', 'started_at', 
                   'duration_display', 'data_counts_display']
    list_filter = ['status', 'device_serial', 'started_at']
    
    def duration_display(self, obj):
        duration = obj.duration if hasattr(obj, 'duration') else None
        if duration:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "진행 중"
    duration_display.short_description = "Duration"
    
    def data_counts_display(self, obj):
        counts = {
            'VRS': obj.vrs_streams.count(),
            'Eye': obj.eye_gaze_data.count(),
            'Hand': obj.hand_tracking_data.count(),
            'SLAM': obj.slam_trajectory_data.count()
        }
        return format_html(
            '<span style="color: blue;">VRS: {}</span> | '
            '<span style="color: green;">Eye: {}</span> | '
            '<span style="color: orange;">Hand: {}</span> | '
            '<span style="color: red;">SLAM: {}</span>',
            counts['VRS'], counts['Eye'], counts['Hand'], counts['SLAM']
        )

class EyeGazeDataAdmin(admin.ModelAdmin):
    def gaze_direction_display(self, obj):
        return format_html(
            '<span style="color: blue;">Yaw: {:.2f}°</span><br>'
            '<span style="color: green;">Pitch: {:.2f}°</span><br>'
            '<span style="color: orange;">Depth: {:.3f}m</span>',
            obj.yaw, obj.pitch, obj.depth_m or 0
        )
```

## 🌊 실시간 스트리밍 아키텍처

### Kafka 기반 데이터 플로우
```
Project Aria Device → VRS File → VRSKafkaStreamer → Kafka Topics → AriaKafkaConsumer → Django Database → REST API → Unity Client
```

### Kafka Topics 구조
```python
KAFKA_TOPICS = {
    'vrs_raw_stream': 'vrs-raw-stream',              # 원본 영상 프레임
    'mps_eye_gaze_general': 'mps-eye-gaze-general',  # 일반 시선 추적
    'mps_eye_gaze_personalized': 'mps-eye-gaze-personalized',  # 개인화 시선
    'mps_hand_tracking': 'mps-hand-tracking',        # 손 추적
    'mps_slam_trajectory': 'mps-slam-trajectory',    # SLAM 궤적
    'mps_slam_points': 'mps-slam-points',            # 3D 포인트 클라우드
    'analytics_real_time': 'analytics-real-time'     # 실시간 분석
}
```

### VRS 스트리밍 명령어
```bash
# VRS 파일을 Kafka로 스트리밍
python manage.py stream_vrs_data \
    --vrs-file /path/to/sample.vrs \
    --mps-data-path /path/to/mps_samples \
    --stream-type both \
    --duration 60 \
    --kafka-servers host.docker.internal:9092

# 실시간 Kafka 컨슈머 시작
python manage.py start_kafka_consumer
```

## 🐳 Docker 컨테이너 구성

### 서비스 구성
```yaml
services:
  django-ard:           # Django API 서버
    build: .
    ports: ["8000:8000"]
    depends_on: [postgres]
    
  postgres:             # PostgreSQL 데이터베이스
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ard_db
      
  redis:                # Redis 캐시 (선택적)
    image: redis:7-alpine
    
  # Kafka는 외부에서 수동 실행
```

### 자동 초기화 프로세스
```bash
# docker-entrypoint.sh에서 자동 실행
1. 데이터베이스 연결 대기
2. Django 마이그레이션 실행
3. 정적 파일 수집
4. 샘플 데이터 다운로드
5. Django 서버 시작
```

## 🎮 Unity 클라이언트 연동

### C# 클라이언트 구조
```csharp
public class ARDUnityClient : MonoBehaviour 
{
    [Header("API Configuration")]
    public string apiBaseUrl = "http://localhost:8000/api/streams/api";
    
    // 이벤트 시스템
    public event Action<EyeGazeData> OnEyeGazeReceived;
    public event Action<HandTrackingData> OnHandTrackingReceived;
    public event Action<SLAMTrajectoryData> OnSLAMTrajectoryReceived;
    
    // 실시간 데이터 구독
    void Start() {
        StartCoroutine(SubscribeToRealTimeData());
    }
    
    IEnumerator SubscribeToRealTimeData() {
        while (true) {
            yield return StartCoroutine(FetchEyeGazeData());
            yield return StartCoroutine(FetchHandTrackingData());
            yield return StartCoroutine(FetchSLAMData());
            yield return new WaitForSeconds(0.033f); // ~30fps
        }
    }
}
```

### Unity 데이터 모델
```csharp
[System.Serializable]
public class EyeGazeData {
    public int id;
    public float yaw;
    public float pitch;
    public float depth_m;
    public string gaze_type;
    public Vector3 gaze_direction;
    public SessionInfo session_info;
}

[System.Serializable]
public class HandTrackingData {
    public int id;
    public List<Landmark> left_hand_landmarks;
    public List<Landmark> right_hand_landmarks;
    public Vector3 left_hand_wrist_normal;
    public Vector3 left_hand_palm_normal;
    public bool has_left_hand;
    public bool has_right_hand;
}
```

## 📊 실제 데이터 로딩 시스템

### MPS 샘플 데이터 로더
```bash
# 실제 Project Aria MPS CSV 파일을 정확한 필드로 로드
python manage.py load_sample_data_fixed \
    --data-type all \
    --limit 100

# 특정 데이터 타입만 로드
python manage.py load_sample_data_fixed --data-type eye_gaze --limit 50
python manage.py load_sample_data_fixed --data-type hand_tracking --limit 30
python manage.py load_sample_data_fixed --data-type slam --limit 20
```

### CSV 필드 매핑
```python
# Eye Gaze 실제 필드 → Django 모델
{
    'tracking_timestamp_us': 'device_timestamp_ns * 1000',
    'left_yaw_rads_cpf': 'yaw (라디안→도 변환)',
    'right_yaw_rads_cpf': 'yaw (평균값)',
    'pitch_rads_cpf': 'pitch (라디안→도 변환)',
    'depth_m': 'depth_m',
    'session_uid': 'metadata'
}

# Hand Tracking 21개 관절 매핑
{
    'tx_left_landmark_{0-20}_device': 'left_hand_landmarks[i].x',
    'ty_left_landmark_{0-20}_device': 'left_hand_landmarks[i].y', 
    'tz_left_landmark_{0-20}_device': 'left_hand_landmarks[i].z',
    'nx_left_palm_device': 'left_hand_palm_normal[0]',
    'ny_left_palm_device': 'left_hand_palm_normal[1]',
    'nz_left_palm_device': 'left_hand_palm_normal[2]'
}
```

## 🧪 테스트 및 검증

### API 테스트 자동화
```python
# management/commands/test_class_based_api.py
class Command(BaseCommand):
    def test_all_endpoints(self):
        endpoints = [
            '/api/streams/api/sessions/',
            '/api/streams/api/vrs-streams/',
            '/api/streams/api/eye-gaze/',
            '/api/streams/api/hand-tracking/',
            '/api/streams/api/slam-trajectory/',
            '/api/streams/api/kafka-status/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            assert response.status_code == 200
            self.stdout.write(f'✅ {endpoint}: {len(response.json())} items')
```

### 데이터 품질 검증
```python
def validate_eye_gaze_data(self):
    """시선 데이터 품질 검증"""
    invalid_data = EyeGazeData.objects.filter(
        models.Q(yaw__lt=-180) | models.Q(yaw__gt=180) |
        models.Q(pitch__lt=-90) | models.Q(pitch__gt=90)
    )
    assert invalid_data.count() == 0

def validate_hand_landmarks(self):
    """손 랜드마크 구조 검증"""
    for hand_data in HandTrackingData.objects.all():
        if hand_data.left_hand_landmarks:
            assert len(hand_data.left_hand_landmarks) == 21
            for landmark in hand_data.left_hand_landmarks:
                assert 'id' in landmark and 'x' in landmark
```

## 🚀 배포 및 실행 가이드

### 개발 환경 시작
```bash
# 1. Docker 서비스 시작
docker-compose up -d

# 2. 샘플 데이터 로드 (최초 1회)
docker exec ard-django-api python manage.py load_sample_data_fixed --limit 50

# 3. API 확인
curl http://localhost:8000/api/streams/api/

# 4. Django Admin 접속
# http://localhost:8000/admin/ (superuser 생성 필요)
```

### Unity 프로젝트 연동
```bash
# 1. Unity 프로젝트에 ARDUnityClient.cs 추가
# 2. API Base URL 설정: http://localhost:8000/api/streams/api
# 3. 실시간 데이터 구독 시작
# 4. AR 시각화 구현
```

## 📈 성능 및 최적화

### 데이터베이스 인덱스
```python
# 주요 쿼리 최적화를 위한 인덱스
class Meta:
    indexes = [
        models.Index(fields=['session', 'device_timestamp_ns']),
        models.Index(fields=['timestamp']),
        models.Index(fields=['position_x', 'position_y', 'position_z']),  # SLAM
        models.Index(fields=['session', 'gaze_type', 'device_timestamp_ns']),  # Eye Gaze
    ]
```

### API 성능 최적화
```python
# ViewSet에서 prefetch_related 사용
class AriaSessionViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return AriaSession.objects.prefetch_related(
            'vrs_streams', 'eye_gaze_data', 
            'hand_tracking_data', 'slam_trajectory_data'
        )

# 페이지네이션 설정
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100
}
```

## 🔮 확장 가능한 아키텍처

### 추가 가능한 기능들
1. **실시간 WebSocket API**: Socket.IO를 통한 실시간 푸시
2. **데이터 분석 API**: Pandas/NumPy 기반 분석 엔드포인트
3. **머신러닝 통합**: TensorFlow/PyTorch 모델 서빙
4. **다중 기기 지원**: 여러 Aria 기기 동시 처리
5. **클라우드 스토리지**: AWS S3/GCS 연동
6. **모니터링**: Prometheus/Grafana 메트릭

### 마이크로서비스 확장
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Django API    │    │  Data Analysis  │    │  ML Inference   │
│   (Core CRUD)   │    │   Service       │    │    Service      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  Message Queue  │
                    │   (Kafka/RMQ)   │
                    └─────────────────┘
```

---

## 💡 핵심 성과 요약

✅ **완전한 클래스 기반 API**: ViewSet 기반 전문적 REST API
✅ **실시간 스트리밍**: Kafka 기반 VRS/MPS 데이터 처리
✅ **Docker 완전 자동화**: 원클릭 배포 환경
✅ **Unity 즉시 연동**: C# 클라이언트와 실시간 통신
✅ **Project Aria 호환**: Meta 공식 데이터 구조 지원
✅ **확장 가능한 설계**: 마이크로서비스 아키텍처 준비

**ARD 시스템은 Project Aria AR 앱 개발을 위한 완전한 백엔드 인프라를 제공합니다.**