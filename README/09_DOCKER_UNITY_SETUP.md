# ARD Docker + Unity 연동 가이드

Unity에서 ARD API를 통해 실시간 AR 데이터를 받아오기 위한 완전한 Docker 설정 가이드입니다.

## 🐳 Docker 구성

### 파일 구조
```
ARD/
├── Dockerfile                      # Django 앱 Docker 이미지
├── docker-compose.yml              # 전체 서비스 오케스트레이션
├── docker-entrypoint.sh            # Django 시작 스크립트
├── docker-run.sh                   # Docker 실행 편의 스크립트
├── unity_api_test.py               # Unity 연동 테스트 스크립트
├── ARDUnityClient.cs               # Unity C# 클라이언트
└── DOCKER_UNITY_SETUP.md           # 이 문서
```

### 서비스 구성
- **django-ard**: Django REST API 서버 (포트 8000)
- **postgres**: PostgreSQL 데이터베이스 (포트 5432)
- **redis**: Redis 캐시 서버 (포트 6379)
- **외부 Kafka**: 사용자가 수동으로 실행 (포트 9092)

## 🚀 실행 방법

### 1. 전체 서비스 시작
```bash
# 편의 스크립트 사용 (권장)
./docker-run.sh
# 메뉴에서 1번 선택: 전체 서비스 시작

# 또는 직접 docker-compose 사용
docker-compose up -d
```

### 2. Django만 시작 (외부 DB 사용시)
```bash
./docker-run.sh
# 메뉴에서 2번 선택: Django만 시작

# 또는 직접 실행
docker-compose up -d django-ard
```

### 3. Unity API 테스트
```bash
./docker-run.sh
# 메뉴에서 6번 선택: Unity API 테스트

# 또는 직접 실행
python unity_api_test.py http://localhost:8000
```

## 🌐 API 엔드포인트

### Unity에서 사용할 주요 엔드포인트

#### 스트리밍 제어
```http
# 스트리밍 시작
POST /api/streams/api/streaming/
Content-Type: application/json
{
    "duration": 60,
    "stream_type": "all"
}

# 스트리밍 상태 확인
GET /api/streams/api/streaming/

# 스트리밍 중지
DELETE /api/streams/api/streaming/
```

#### 실시간 데이터 조회
```http
# Eye Gaze 데이터
GET /api/streams/api/eye-gaze/?ordering=-timestamp&page_size=10

# Hand Tracking 데이터
GET /api/streams/api/hand-tracking/?ordering=-timestamp&page_size=10

# SLAM Trajectory 데이터
GET /api/streams/api/slam-trajectory/?ordering=-timestamp&page_size=10
```

#### 시각화용 데이터
```http
# 시선 히트맵
GET /api/streams/api/eye-gaze/gaze_heatmap/?gaze_type=general

# SLAM 궤적 경로
GET /api/streams/api/slam-trajectory/trajectory_path/?limit=100
```

## 🎮 Unity 통합

### 1. Unity 클라이언트 설정
1. `ARDUnityClient.cs`를 Unity 프로젝트에 추가
2. Newtonsoft.Json 패키지 설치: `Window > Package Manager > Unity Registry > Newtonsoft Json`
3. 빈 GameObject에 `ARDUnityClient` 스크립트 추가

### 2. Unity 클라이언트 사용법
```csharp
// GameObject에 ARDUnityClient 컴포넌트 추가
public class ARDataVisualizer : MonoBehaviour
{
    private void OnEnable()
    {
        // 이벤트 구독
        ARDUnityClient.OnEyeGazeDataReceived += HandleEyeGazeData;
        ARDUnityClient.OnHandTrackingDataReceived += HandleHandTrackingData;
        ARDUnityClient.OnSlamTrajectoryDataReceived += HandleSlamTrajectoryData;
    }
    
    private void OnDisable()
    {
        // 이벤트 구독 해제
        ARDUnityClient.OnEyeGazeDataReceived -= HandleEyeGazeData;
        ARDUnityClient.OnHandTrackingDataReceived -= HandleHandTrackingData;
        ARDUnityClient.OnSlamTrajectoryDataReceived -= HandleSlamTrajectoryData;
    }
    
    private void HandleEyeGazeData(EyeGazeData[] gazeData)
    {
        foreach (var gaze in gazeData)
        {
            // Unity에서 시선 데이터 시각화
            Vector3 gazeDirection = new Vector3(
                gaze.gaze_direction.x,
                gaze.gaze_direction.y,
                gaze.gaze_direction.z
            );
            
            // 시선 방향에 따른 UI 업데이트 또는 3D 오브젝트 조작
            Debug.Log($"Gaze Direction: {gazeDirection}, Confidence: {gaze.confidence}");
        }
    }
    
    private void HandleSlamTrajectoryData(SlamTrajectoryData[] trajectoryData)
    {
        foreach (var point in trajectoryData)
        {
            // Unity에서 SLAM 궤적 시각화
            Vector3 position = new Vector3(
                point.position.x,
                point.position.y,
                point.position.z
            );
            
            // 3D 공간에서 궤적 렌더링
            Debug.Log($"SLAM Position: {position}");
        }
    }
}
```

### 3. Unity 시각화 예제
```csharp
public class GazeVisualizer : MonoBehaviour
{
    [SerializeField] private LineRenderer gazeRay;
    [SerializeField] private Transform gazeTarget;
    
    private void HandleEyeGazeData(EyeGazeData[] gazeData)
    {
        if (gazeData.Length > 0)
        {
            var latestGaze = gazeData[0];
            Vector3 direction = new Vector3(
                latestGaze.gaze_direction.x,
                latestGaze.gaze_direction.y,
                latestGaze.gaze_direction.z
            );
            
            // 시선 방향 시각화
            gazeRay.SetPosition(0, Vector3.zero);
            gazeRay.SetPosition(1, direction * 5f);
            
            // 시선 타겟 위치 업데이트
            gazeTarget.position = direction * latestGaze.depth_m;
        }
    }
}
```

## 🔧 개발 워크플로우

### 1. 개발 환경 설정
```bash
# 1. Kafka 수동 실행 (사용자가 별도 실행)
# 2. ARD Docker 서비스 시작
./docker-run.sh
# 메뉴에서 1번 선택

# 3. API 연결 테스트
curl http://localhost:8000/api/streams/api/sessions/
```

### 2. Unity 개발 사이클
```bash
# 1. 스트리밍 시작
curl -X POST http://localhost:8000/api/streams/api/streaming/ \
  -H "Content-Type: application/json" \
  -d '{"duration": 60, "stream_type": "all"}'

# 2. Unity에서 실시간 데이터 수신 및 시각화 개발

# 3. API 테스트 스크립트로 데이터 플로우 검증
python unity_api_test.py
```

### 3. 디버깅
```bash
# Django 로그 확인
docker-compose logs -f django-ard

# 컨테이너 내부 접속
docker-compose exec django-ard bash

# Django shell 접속
docker-compose exec django-ard python ARD/manage.py shell
```

## 📊 데이터 플로우

```
Project Aria Device → VRS File → Django VRS Reader → Kafka Topics → Django Consumer → PostgreSQL → REST API → Unity
```

### 실시간 데이터 흐름
1. **샘플 데이터 스트리밍**: Django가 VRS 파일을 읽어 Kafka로 스트리밍
2. **Kafka Consumer**: Django Consumer가 Kafka 메시지를 받아 DB 저장  
3. **REST API**: Unity가 Django REST API를 통해 실시간 데이터 조회
4. **Unity 시각화**: Unity에서 AR 데이터를 3D 환경에 시각화

### Unity에서 처리할 데이터 타입
- **Eye Gaze**: 시선 방향(yaw, pitch), 깊이, 신뢰도
- **Hand Tracking**: 손 랜드마크, 손목/손바닥 노멀 벡터
- **SLAM Trajectory**: 3D 위치, 변환 행렬, 궤적 경로
- **VRS Streams**: RGB/SLAM 카메라 프레임 정보

## 🚨 문제 해결

### 일반적인 문제들

#### Docker 빌드 실패
```bash
# Docker 이미지 재빌드
docker-compose build --no-cache django-ard

# Docker 시스템 정리
docker system prune -f
```

#### API 연결 실패
```bash
# 컨테이너 상태 확인
docker-compose ps

# Django 서비스 로그 확인
docker-compose logs django-ard

# 네트워크 연결 테스트
curl -I http://localhost:8000
```

#### Unity 연결 문제
1. **CORS 설정**: Django CORS 설정 확인
2. **포트 충돌**: 8000번 포트 사용 여부 확인
3. **방화벽**: Windows/Linux 방화벽 설정 확인

#### 데이터 수신 없음
```bash
# Kafka 연결 상태 확인
docker-compose exec django-ard python ARD/manage.py shell
>>> from streams.producers import AriaKafkaProducer
>>> producer = AriaKafkaProducer()

# 스트리밍 상태 확인
curl http://localhost:8000/api/streams/api/streaming/
```

## 🎯 Unity 개발 팁

### 성능 최적화
- **데이터 수신 주기**: 100ms (10 FPS) 권장
- **배치 크기**: 요청당 10-20개 데이터 권장
- **메모리 관리**: 오래된 데이터는 정기적으로 정리
- **스레딩**: Unity Main Thread에서 UI 업데이트만 수행

### 실시간 시각화
- **Interpolation**: 데이터 포인트 간 보간으로 부드러운 애니메이션
- **LOD**: 거리에 따른 디테일 조절
- **Culling**: 화면 밖 오브젝트 렌더링 제외
- **Pooling**: 오브젝트 풀링으로 GC 압박 감소

### 에러 핸들링
- **네트워크 재연결**: 연결 끊어짐 시 자동 재연결
- **데이터 검증**: 받은 데이터의 유효성 검사
- **Fallback UI**: API 연결 실패 시 사용자에게 안내
- **로깅**: 상세한 로그로 디버깅 지원

## 🏁 결론

이 Docker + Unity 설정을 통해 Project Aria의 실시간 AR 데이터를 Unity에서 안정적으로 시각화할 수 있습니다. 

**핵심 장점**:
- ✅ **완전한 컨테이너화**: 환경 독립적 배포
- ✅ **실시간 스트리밍**: Kafka 기반 고성능 데이터 파이프라인  
- ✅ **Unity 친화적**: C# 클라이언트와 이벤트 시스템
- ✅ **확장 가능**: 마이크로서비스 아키텍처
- ✅ **개발 친화적**: 핫 리로드와 디버깅 지원