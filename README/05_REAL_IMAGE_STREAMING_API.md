# ARD 실제 이미지 스트리밍 API 가이드

## 🎯 개요

Project Aria 실제 이미지 데이터를 Base64 JPEG로 스트리밍하는 완전한 Docker 기반 시스템입니다.

## 🐳 Docker 실행 방법

### 1. 시스템 시작
```bash
# Kafka 시작 (별도로 이미 실행 중)
docker run -d --name kafka-all -p 9092:9092 bashj79/kafka-kraft

# ARD 전체 스택 시작
docker-compose up -d
```

### 2. 실행 중인 서비스 확인
```bash
docker-compose ps
```

**실행되는 컨테이너들:**
- `ard-django-api:8000` - API 서버 + 자동 Kafka Consumer
- `ard-postgres:5432` - PostgreSQL 데이터베이스
- `ard-redis:6379` - Redis 캐싱
- `kafka-all:9092` - Kafka 메시징

## 🚀 전체 API 엔드포인트 목록

### 베이스 URL
```
http://127.0.0.1:8000/api/streams/api/
```

### 📋 모든 API URL 목록

#### 🏠 세션 관리
```http
GET    /api/streams/api/sessions/                           # 세션 목록
POST   /api/streams/api/sessions/                           # 세션 생성  
GET    /api/streams/api/sessions/{id}/                      # 세션 상세
PUT    /api/streams/api/sessions/{id}/                      # 세션 수정
DELETE /api/streams/api/sessions/{id}/                      # 세션 삭제
POST   /api/streams/api/sessions/{id}/end_session/          # 세션 종료
GET    /api/streams/api/sessions/{id}/statistics/           # 세션 통계
```

#### 🖼️ VRS 이미지 스트림
```http
GET    /api/streams/api/vrs-streams/                        # VRS 스트림 목록
GET    /api/streams/api/vrs-streams/{id}/                   # VRS 스트림 상세
GET    /api/streams/api/vrs-streams/stream_summary/         # 스트림 요약 통계
```

#### 👁️ 시선 추적 데이터
```http
GET    /api/streams/api/eye-gaze/                           # 시선 데이터 목록
GET    /api/streams/api/eye-gaze/{id}/                      # 시선 데이터 상세
GET    /api/streams/api/eye-gaze/gaze_heatmap/              # 시선 히트맵
```

#### 🤲 손 추적 데이터
```http
GET    /api/streams/api/hand-tracking/                      # 손 추적 목록
GET    /api/streams/api/hand-tracking/{id}/                 # 손 추적 상세
GET    /api/streams/api/hand-tracking/hand_statistics/      # 손 추적 통계
```

#### 🗺️ SLAM 궤적 데이터
```http
GET    /api/streams/api/slam-trajectory/                    # SLAM 궤적 목록
GET    /api/streams/api/slam-trajectory/{id}/               # SLAM 궤적 상세
GET    /api/streams/api/slam-trajectory/trajectory_path/    # 전체 궤적 경로
```

#### 📳 IMU 센서 데이터
```http
GET    /api/streams/api/imu-data/                           # IMU 데이터 목록
GET    /api/streams/api/imu-data/{id}/                      # IMU 데이터 상세
```

#### 🔧 Kafka 상태 모니터링
```http
GET    /api/streams/api/kafka-status/                       # Kafka 상태 목록
GET    /api/streams/api/kafka-status/{id}/                  # Kafka 상태 상세
GET    /api/streams/api/kafka-status/health_check/          # Kafka 헬스체크
```

#### 🎮 스트리밍 제어
```http
GET    /api/streams/api/streaming/                          # 스트리밍 상태 확인
POST   /api/streams/api/streaming/                          # 스트리밍 시작
DELETE /api/streams/api/streaming/                          # 스트리밍 중단
```

#### 🧪 테스트 메시지
```http
POST   /api/streams/api/test-message/                       # 테스트 메시지 전송
```

### 🔗 주요 사용 예시 URL

#### VRS 이미지 스트림 활용
```http
# 특정 이미지 가져오기
GET /api/streams/api/vrs-streams/3592/

# 최신 이미지 하나만
GET /api/streams/api/vrs-streams/?image_data__isnull=false&limit=1&ordering=-id

# 메타데이터만 확인
GET /api/streams/api/vrs-streams/?fields=id,stream_name,image_width,image_height,timestamp&limit=10

# 이미지 데이터가 있는 것만
GET /api/streams/api/vrs-streams/?image_data__isnull=false

# RGB 스트림만
GET /api/streams/api/vrs-streams/?stream_name=rgb

# 시간 범위 필터
GET /api/streams/api/vrs-streams/?start_time=2025-07-30T15:00:00Z&end_time=2025-07-30T16:00:00Z

# 최신 순 정렬
GET /api/streams/api/vrs-streams/?ordering=-timestamp

# 페이지네이션
GET /api/streams/api/vrs-streams/?page=1&page_size=5

//"http://127.0.0.1:8000/api/streams/api/vrs-streams/?i
      mage_data__isnull=false&limit=1&ordering=-id" | head
      -5
```

#### 시선 추적 활용
```http
# 높은 신뢰도 시선 데이터만
GET /api/streams/api/eye-gaze/?min_confidence=0.8

# 일반 시선 추적만
GET /api/streams/api/eye-gaze/?gaze_type=general

# 개인화된 시선 추적만
GET /api/streams/api/eye-gaze/?gaze_type=personalized

# 시선 히트맵 데이터
GET /api/streams/api/eye-gaze/gaze_heatmap/

# 특정 세션 시선 데이터
GET /api/streams/api/eye-gaze/?session=1
```

#### 손 추적 활용
```http
# 왼손 감지된 것만
GET /api/streams/api/hand-tracking/?has_left_hand=true

# 오른손 감지된 것만
GET /api/streams/api/hand-tracking/?has_right_hand=true

# 양손 모두 감지된 것만
GET /api/streams/api/hand-tracking/?has_left_hand=true&has_right_hand=true

# 손 추적 통계
GET /api/streams/api/hand-tracking/hand_statistics/
```

#### SLAM 궤적 활용
```http
# 위치 범위 필터
GET /api/streams/api/slam-trajectory/?x_min=-1.0&x_max=1.0&y_min=-1.0&y_max=1.0

# 전체 궤적 경로
GET /api/streams/api/slam-trajectory/trajectory_path/

# 최근 위치 데이터
GET /api/streams/api/slam-trajectory/?ordering=-timestamp&limit=10
```

#### IMU 센서 활용
```http
# 가속도 데이터만
GET /api/streams/api/imu-data/?imu_type=accel

# 자이로스코프 데이터만
GET /api/streams/api/imu-data/?imu_type=gyro

# 가속도 크기 범위 필터
GET /api/streams/api/imu-data/?acceleration_min=9.0&acceleration_max=11.0

# 최신 IMU 데이터
GET /api/streams/api/imu-data/?ordering=-timestamp&limit=20
```

#### 세션 관리 활용
```http
# 실행 중인 세션만
GET /api/streams/api/sessions/?status=running

# 특정 세션 통계
GET /api/streams/api/sessions/1/statistics/

# 세션 종료
POST /api/streams/api/sessions/1/end_session/
```

#### Kafka 모니터링 활용
```http
# 활성 Consumer만
GET /api/streams/api/kafka-status/?status=active

# 에러 상태 Consumer
GET /api/streams/api/kafka-status/?status=error

# Kafka 전체 헬스체크
GET /api/streams/api/kafka-status/health_check/
```

#### 스트리밍 제어 활용
```http
# 현재 스트리밍 상태 확인
GET /api/streams/api/streaming/

# VRS 데이터만 60초 스트리밍
POST /api/streams/api/streaming/
Content-Type: application/json
{"duration": 60, "stream_type": "vrs"}

# MPS 데이터만 30초 스트리밍  
POST /api/streams/api/streaming/
Content-Type: application/json
{"duration": 30, "stream_type": "mps"}

# 모든 데이터 120초 스트리밍
POST /api/streams/api/streaming/
Content-Type: application/json
{"duration": 120, "stream_type": "all"}

# 스트리밍 중단
DELETE /api/streams/api/streaming/
```

## 📸 핵심 API 응답 예시

### VRS 이미지 데이터 응답
```json
{
  "id": 3592,
  "session": 1,
  "stream_name": "rgb",
  "timestamp": "2025-07-30T16:05:11Z",
  "image_data": "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAUDBAQEAwUEBAQFBQ...",
  "image_width": 1408,
  "image_height": 1408,
  "original_size_bytes": 5947392,
  "compressed_size_bytes": 423868,
  "compression_quality": 85
}
```

### 시선 추적 데이터 응답
```json
{
  "id": 501,
  "session": 1,
  "timestamp": "2025-07-30T16:05:15Z",
  "gaze_type": "general",
  "yaw": 15.5,
  "pitch": -8.2,
  "depth_m": 2.3,
  "confidence": 0.92,
  "gaze_direction": {"x": 0.267, "y": -0.143, "z": 0.953}
}
```

### 손 추적 데이터 응답
```json
{
  "id": 301,
  "session": 1,
  "timestamp": "2025-07-30T16:05:20Z",
  "left_hand_landmarks": [[0.1, 0.2, 0.3], [0.15, 0.22, 0.31]],
  "has_left_hand": true,
  "has_right_hand": false
}
```

### SLAM 궤적 데이터 응답
```json
{
  "id": 201,
  "session": 1,
  "timestamp": "2025-07-30T16:05:25Z",
  "transform_matrix": [[0.998, -0.052, 0.035, 1.25], [0.053, 0.999, -0.018, -0.68]],
  "position": {"x": 1.25, "y": -0.68, "z": 0.15}
}
```

### IMU 센서 데이터 응답
```json
{
  "id": 1001,
  "session": 1,
  "timestamp": "2025-07-30T16:05:30Z",
  "imu_type": "accel",
  "accel_x": 0.15, "accel_y": -9.81, "accel_z": 0.08,
  "acceleration_magnitude": 9.82,
  "temperature_c": 35.2
}
```

## 🖼️ 지원되는 이미지 스트림

| Stream Name | Stream ID | 해상도 | 형식 | 설명 |
|------------|-----------|--------|------|------|
| `rgb` | `214-1` | 1408x1408 | RGB24 | 메인 컬러 카메라 |
| `slam_left` | `1201-1` | 640x480 | GRAY8 | 왼쪽 SLAM 카메라 |
| `slam_right` | `1201-2` | 640x480 | GRAY8 | 오른쪽 SLAM 카메라 |
| `eye_tracking` | `211-1` | 320x240 | GRAY8 | 시선 추적 카메라 |

## 📋 API 요약 테이블

| API 카테고리 | 엔드포인트 | 주요 기능 | 특별 액션 |
|-------------|-----------|----------|-----------|
| 🏠 **세션 관리** | `/api/sessions/` | 세션 CRUD, 통계 | `end_session/`, `statistics/` |
| 🖼️ **VRS 이미지** | `/api/vrs-streams/` | 실제 이미지 스트리밍 | `stream_summary/` |
| 👁️ **시선 추적** | `/api/eye-gaze/` | 시선 방향, 신뢰도 | `gaze_heatmap/` |
| 🤲 **손 추적** | `/api/hand-tracking/` | 손 랜드마크, 포즈 | `hand_statistics/` |
| 🗺️ **SLAM 궤적** | `/api/slam-trajectory/` | 3D 위치, 변환 행렬 | `trajectory_path/` |
| 📳 **IMU 센서** | `/api/imu-data/` | 가속도, 자이로 데이터 | 없음 |
| 🔧 **Kafka 상태** | `/api/kafka-status/` | Consumer 모니터링 | `health_check/` |
| 🎮 **스트리밍 제어** | `/api/streaming/` | VRS/MPS 스트리밍 | 없음 |
| 🧪 **테스트** | `/api/test-message/` | Kafka 테스트 메시지 | 없음 |

## 🔗 공통 쿼리 파라미터

**모든 API에서 사용 가능:**
```http
# 페이지네이션
?page=1&page_size=20

# 정렬
?ordering=-timestamp        # 최신 순
?ordering=id               # ID 순

# 검색 (해당되는 경우)
?search=keyword

# 세션 필터
?session=1

# 시간 범위 필터
?start_time=2025-07-30T15:00:00Z&end_time=2025-07-30T16:00:00Z
```



## 🔧 데이터 스트리밍 명령어

### VRS 파일에서 실제 이미지 스트리밍

```bash
# 컨테이너 내부에서 실행
docker exec -it ard-django-api bash

# VRS 데이터 스트리밍 (이미지 포함)
python manage.py stream_vrs_data \
  --vrs-file /app/ARD/data/mps_samples/sample.vrs \
  --mps-data-path /app/ARD/data/mps_samples \
  --duration 60 \
  --stream-type vrs \
  --kafka-servers host.docker.internal:9092
```

### Consumer 상태 확인

```bash
# Consumer 로그 확인
docker logs ard-django-api | grep -i consumer

# Kafka 토픽 확인
docker exec kafka-all /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --list
```


## 🔍 디버깅 및 문제 해결

### 1. 이미지 데이터가 NULL인 경우
```bash
# Consumer 실행 상태 확인
docker logs ard-django-api | tail -20

# 새로운 데이터 스트리밍
docker exec -it ard-django-api python manage.py stream_vrs_data \
  --vrs-file /app/ARD/data/mps_samples/sample.vrs \
  --mps-data-path /app/ARD/data/mps_samples \
  --duration 10 --stream-type vrs
```

### 2. Out of Memory 해결
```http
# 한 번에 하나씩만 요청
GET /api/streams/api/vrs-streams/3592/

# 메타데이터만 먼저 확인
GET /api/streams/api/vrs-streams/?fields=id,stream_name&limit=10
```

### 3. 컨테이너 재시작
```bash
docker-compose down
docker-compose up -d
```

## 📈 성능 특징

- **이미지 압축**: JPEG 85% 품질
- **RGB 이미지**: 5.9MB → 424KB (Base64)
- **SLAM 이미지**: 더 작은 크기 (흑백)
- **자동 Consumer**: 백그라운드에서 실시간 처리
- **메모리 최적화**: 필요시 개별 이미지 로드

## 🎯 주요 장점

✅ **실제 Project Aria 이미지** - 메타데이터가 아닌 실제 이미지  
✅ **Docker 완전 패키징** - 어디서든 쉬운 배포  
✅ **자동 Consumer** - 수동 실행 불필요  
✅ **메모리 효율적** - 개별 이미지 로드 지원  
✅ **Unity 통합 준비** - Base64 JPEG 형식  
✅ **실시간 스트리밍** - Kafka 기반 실시간 데이터  

## 🔗 관련 문서

- `CLAUDE.md` - 전체 프로젝트 가이드
- `ARD_CLASS_BASED_API_STRUCTURE.md` - 상세 API 문서
- `docker-compose.yml` - Docker 설정
- `CLASS_BASED_REFACTORING_SUMMARY.md` - API 구조 요약