# ARD (Aria Real-time Data) System

실시간 AR 데이터 처리를 위한 Django + Kafka 시스템입니다. **이중 API 구조**로 Project Aria 정제된 데이터와 사용자 정의 원시 데이터를 모두 지원합니다.

## 🎯 **핵심 특징**

### 📊 **정제된 데이터 API** - 사용하기 쉬운 표준 형식
- **Project Aria MPS 데이터**: Eye Gaze, Hand Tracking, SLAM Trajectory
- **실시간 스트리밍**: VRS, IMU, Binary 데이터  
- **표준화된 형식**: 개발자 친화적인 JSON 구조

### 🔧 **원시 데이터 API** - 완전한 유연성 지원
- **모든 형식 지원**: CSV, JSON, XML, Binary, Protocol Buffers, HDF5, Parquet
- **파일 업로드**: VRS, CSV, Binary 파일 직접 업로드
- **사용자 정의 스키마**: 자신만의 데이터 구조 정의
- **변환 추적**: Raw → Processed 데이터 변환 기록

## 🚀 빠른 시작 (30초)

### 🚀 자동 실행 (추천)
```bash
# 1. Kafka 시작
docker-compose -f kafka-compose.yml up -d

# 2. ARD 시스템 시작 (자동으로 실제 MPS 데이터 로드됨)
docker-compose up -d

# 3. API 테스트
curl http://localhost:8000/api/v1/aria/sessions/
```

### 🔧 개별 컨테이너 실행 (수동 제어)

#### 1️⃣ PostgreSQL 데이터베이스
```bash
# PostgreSQL 컨테이너 실행
docker run -d \
  --name ARD-POSTGRES \
  --network ard-network \
  -e POSTGRES_DB=ard_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15
```

#### 2️⃣ Kafka (KRaft 모드 - Zookeeper 불필요)
```bash
# Kafka 컨테이너 시작 (최신 KRaft 모드)
docker run -d \
  --name ARD_KAFKA \
  --network kafka-network \
  -e KAFKA_ENABLE_KRAFT=yes \
  -e KAFKA_CFG_PROCESS_ROLES=broker,controller \
  -e KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e KAFKA_CFG_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093 \
  -e KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT \
  -e KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://ARD_KAFKA:9092 \
  -e KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@ARD_KAFKA:9093 \
  -e KAFKA_CFG_NODE_ID=1 \
  -e KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=true \
  -e KAFKA_CFG_LOG_RETENTION_HOURS=24 \
  -e ALLOW_PLAINTEXT_LISTENER=yes \
  -p 9092:9092 \
  -v kafka_data:/bitnami/kafka \
  bitnami/kafka:latest
```

💡 **참고**: 최신 Kafka는 **KRaft 모드**로 Zookeeper 없이 실행됩니다!

#### 3️⃣ ARD Django API 서버
```bash
# ARD 이미지 빌드
docker build -t ard-api:v13 .

# ARD 컨테이너 실행
docker run -d \
  --name ARD-BACKEND \
  --network ard-network \
  -e DEBUG=1 \
  -e DB_HOST=postgres \
  -e DB_PORT=5432 \
  -e DB_NAME=ard_db \
  -e DB_USER=postgres \
  -e DB_PASSWORD=password \
  -e KAFKA_BOOTSTRAP_SERVERS=ARD_KAFKA:9092 \
  -e KAFKA_GROUP_ID=ard-consumer-group \
  -p 8000:8000 \
  -v ard_data:/app/ARD/data \
  -v ard_logs:/app/logs \
  ard-api:v13
```

#### 4️⃣ 네트워크 및 볼륨 생성 (위 명령어들 실행 전에)
```bash
# Docker 네트워크 생성
docker network create ard-network
docker network create kafka-network

# Docker 볼륨 생성
docker volume create postgres_data
docker volume create kafka_data
docker volume create ard_data
docker volume create ard_logs
```

#### 5️⃣ 실제 사용 중인 컨테이너 실행 순서 (CMD 창에서 바로 실행)
```cmd
REM 네트워크 및 볼륨 생성
docker network create ard-network
docker network create kafka-network
docker volume create postgres_data
docker volume create kafka_data
docker volume create ard_data
docker volume create ard_logs

REM PostgreSQL 시작
docker run -d --name ARD-POSTGRES --network ard-network -e POSTGRES_DB=ard_db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -v postgres_data:/var/lib/postgresql/data postgres:15-alpine

REM Kafka 시작 (KRaft 모드)
docker run -d --name ARD_KAFKA --network kafka-network -e KAFKA_ENABLE_KRAFT=yes -e KAFKA_CFG_PROCESS_ROLES=broker,controller -e KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER -e KAFKA_CFG_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093 -e KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT -e KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://ARD_KAFKA:9092 -e KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@ARD_KAFKA:9093 -e KAFKA_CFG_NODE_ID=1 -e KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=true -e ALLOW_PLAINTEXT_LISTENER=yes -p 9092:9092 -v kafka_data:/bitnami/kafka bitnami/kafka:latest

REM 30초 대기 (Kafka 준비 시간)
timeout /t 30

REM ARD 이미지 빌드 및 실행
docker build -t ard-api:v13 .
docker run -d --name ARD-BACKEND --network ard-network --network kafka-network -e DEBUG=1 -e DB_HOST=postgres -e KAFKA_BOOTSTRAP_SERVERS=ARD_KAFKA:9092 -p 8000:8000 -v ard_data:/app/ARD/data -v ard_logs:/app/logs ard-api:v13
```

#### 6️⃣ Linux/Mac 사용자용 스크립트
```bash
#!/bin/bash
# 네트워크 및 볼륨 생성
docker network create ard-network
docker network create kafka-network
docker volume create postgres_data kafka_data ard_data ard_logs

# PostgreSQL 시작
docker run -d --name ARD-POSTGRES --network ard-network -e POSTGRES_DB=ard_db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -v postgres_data:/var/lib/postgresql/data postgres:15-alpine

# Kafka 시작 (KRaft 모드)
docker run -d --name ARD_KAFKA --network kafka-network -e KAFKA_ENABLE_KRAFT=yes -e KAFKA_CFG_PROCESS_ROLES=broker,controller -e KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER -e KAFKA_CFG_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093 -e KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT -e KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://ARD_KAFKA:9092 -e KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=1@ARD_KAFKA:9093 -e KAFKA_CFG_NODE_ID=1 -e KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=true -e ALLOW_PLAINTEXT_LISTENER=yes -p 9092:9092 -v kafka_data:/bitnami/kafka bitnami/kafka:latest

# 30초 대기
sleep 30

# ARD 이미지 빌드 및 실행
docker build -t ard-api:v13 .
docker run -d --name ARD-BACKEND --network ard-network --network kafka-network -e DEBUG=1 -e DB_HOST=postgres -e KAFKA_BOOTSTRAP_SERVERS=ARD_KAFKA:9092 -p 8000:8000 -v ard_data:/app/ARD/data -v ard_logs:/app/logs ard-api:v13
```

**그게 다입니다!** 🎉

## 📋 시스템 요구사항

- **Docker** & **Docker Compose**
- **포트**: 8000 (Django), 5432 (PostgreSQL), 9092 (Kafka)
- **RAM**: 최소 4GB 권장

## 🎯 제공되는 실제 데이터

시스템 시작 시 **Meta Project Aria 샘플 데이터**가 자동으로 로드됩니다:

### 📊 정제된 데이터 (Processed Data)
- **👁️ Eye Gaze**: 150개 레코드 (General 100 + Personalized 50)
- **🤲 Hand Tracking**: 50개 레코드 (21개 landmarks per hand)  
- **🗺️ SLAM Trajectory**: 100개 레코드 (실제 quaternion → matrix 변환)
- **📹 VRS Streams**: 20개 RGB 카메라 프레임
- **🎯 IMU Data**: 50개 센서 레코드 (가속도계, 자이로스코프, 자력계)
- **📱 Session**: "실제-MPS-데이터" 세션

### 🔧 원시 데이터 (Raw Data) - 즉시 사용 가능
- **빈 상태로 시작**: 사용자가 직접 업로드
- **예시 스키마 제공**: CSV, JSON, Custom 형식 템플릿
- **파일 업로드 지원**: VRS, CSV, Binary 파일 처리

## 📡 REST API 엔드포인트

### 📊 **정제된 데이터 API** - `/api/v1/aria/`

사용하기 쉬운 표준화된 Project Aria 데이터

```bash
# 세션 관리
GET http://localhost:8000/api/v1/aria/sessions/

# Eye Gaze 데이터 (정제된 형식)
GET http://localhost:8000/api/v1/aria/eye-gaze/
GET http://localhost:8000/api/v1/aria/eye-gaze/?gaze_type=personalized
GET http://localhost:8000/api/v1/aria/eye-gaze/?min_confidence=0.95

# Hand Tracking 데이터 (JSON landmarks)
GET http://localhost:8000/api/v1/aria/hand-tracking/
GET http://localhost:8000/api/v1/aria/hand-tracking/?has_left_hand=true

# SLAM Trajectory 데이터 (4x4 matrix)
GET http://localhost:8000/api/v1/aria/slam-trajectory/
GET http://localhost:8000/api/v1/aria/slam-trajectory/?x_min=-1.0&x_max=1.0

# VRS & IMU 스트림 데이터
GET http://localhost:8000/api/v1/aria/vrs-streams/
GET http://localhost:8000/api/v1/aria/imu-data/

# Binary 스트리밍 (Unity용)
GET http://localhost:8000/api/v1/aria/binary/streaming/
```

### 🔧 **원시 데이터 API** - `/api/v1/aria/raw/`

완전한 유연성을 지원하는 사용자 정의 데이터

```bash
# 데이터 업로드 관리
GET  http://localhost:8000/api/v1/aria/raw/uploads/          # 업로드 목록
POST http://localhost:8000/api/v1/aria/raw/uploads/          # 새 데이터 업로드
GET  http://localhost:8000/api/v1/aria/raw/uploads/formats/  # 지원 형식 목록

# 원시 스트림 데이터
GET  http://localhost:8000/api/v1/aria/raw/raw-data/         # Raw 스트림 목록  
POST http://localhost:8000/api/v1/aria/raw/raw-data/query/   # 고급 쿼리

# 파일 업로드
GET  http://localhost:8000/api/v1/aria/raw/files/            # 업로드된 파일 목록
POST http://localhost:8000/api/v1/aria/raw/files/upload/     # VRS/CSV 파일 업로드

# 데이터 스키마 관리
GET  http://localhost:8000/api/v1/aria/raw/schemas/          # 스키마 목록
POST http://localhost:8000/api/v1/aria/raw/schemas/          # 커스텀 스키마 생성
GET  http://localhost:8000/api/v1/aria/raw/schemas/popular/  # 인기 스키마

# 통합 통계
GET  http://localhost:8000/api/v1/aria/raw/statistics/       # 전체 Raw 데이터 통계
```

# SLAM Trajectory 데이터 (4x4 transformation matrix)
GET http://localhost:8000/api/v1/aria/slam-trajectory/
GET http://localhost:8000/api/v1/aria/slam-trajectory/trajectory_path/

# VRS Stream & IMU 데이터
GET http://localhost:8000/api/v1/aria/vrs-streams/
GET http://localhost:8000/api/v1/aria/imu-data/
```

### 🔍 특수 기능 APIs
```bash
# 실시간 이진 스트리밍 (Unity 클라이언트용)
GET http://localhost:8000/api/v1/aria/binary/streaming/

# Kafka 상태 모니터링
GET http://localhost:8000/api/v1/aria/kafka-status/
```

## 📈 API 응답 예시

### 📊 정제된 데이터 API 응답

#### Eye Gaze 데이터 (정제된 형식)
```json
{
  "id": 300,
  "session": 2,
  "gaze_type": "personalized",
  "yaw": -1.71,
  "pitch": -10.65,
  "depth_m": 0.38,
  "confidence": 0.98,
  "gaze_direction": {
    "x": -0.029,
    "y": -0.185,
    "z": 0.982
  }
}
```

#### Hand Tracking 데이터 (21 landmarks)
```json
{
  "id": 50,
  "left_hand_landmarks": [
    [0.090, -0.151, 0.352],
    [0.103, -0.177, 0.428],
    // ... 21개 landmarks
  ],
  "right_hand_landmarks": [
    [0.161, -0.156, 0.310],
    // ... 21개 landmarks
  ],
  "has_left_hand": true,
  "has_right_hand": true
}
```

#### SLAM Trajectory 데이터 (4x4 transform matrix)
```json
{
  "id": 100,
  "transform_matrix": [
    [0.036, 0.980, -0.195, 0.963],
    [0.086, -0.197, -0.977, 0.596],
    [-0.996, 0.018, -0.091, 0.031],
    [0.0, 0.0, 0.0, 1.0]
  ],
  "position": {
    "x": 0.963,
    "y": 0.596,
    "z": 0.031
  }
}
```

#### VRS Stream 데이터 (RGB 카메라)
```json
{
  "id": 15,
  "stream_id": "214-1",
  "stream_name": "camera-rgb",
  "frame_index": 450,
  "image_shape": [1408, 1408, 3],
  "pixel_format": "RGB24",
  "image_width": 1408,
  "image_height": 1408,
  "compression_quality": 90
}
```

#### IMU 데이터 (센서)
```json
{
  "id": 25,
  "imu_type": "left",
  "accel_x": 0.123,
  "accel_y": -9.801,
  "accel_z": 0.045,
  "gyro_x": 0.001,
  "gyro_y": -0.002,
  "gyro_z": 0.003,
  "acceleration_magnitude": 9.805,
  "angular_velocity_magnitude": 0.0037
}
```

### 🔧 원시 데이터 API 응답

#### 데이터 업로드 (사용자 정의 형식)
```json
{
  "id": 123,
  "upload_name": "custom-sensor-data",
  "data_type": "sensor_readings",
  "data_source": "custom_device",
  "data_format": "csv",
  "content_type": "text/csv",
  "data_content": [
    {"timestamp": "2025-01-01T10:00:00Z", "temperature": 25.4, "humidity": 60.2},
    {"timestamp": "2025-01-01T10:01:00Z", "temperature": 25.6, "humidity": 59.8}
  ],
  "data_size_bytes": 1024,
  "record_count": 2,
  "processing_status": "ready",
  "is_public": false,
  "upload_info": {
    "size_mb": 0.001,
    "created_ago_minutes": 5,
    "processing_time_seconds": 2.3
  }
}
```

#### Raw 스트림 데이터 (실시간)
```json
{
  "id": 456,
  "data_type": "eye_tracking",
  "data_source": "tobii_pro",
  "data_format": "json",
  "data_content": {
    "left_eye": {"x": 0.45, "y": 0.32, "pupil_diameter": 3.2},
    "right_eye": {"x": 0.47, "y": 0.31, "pupil_diameter": 3.1},
    "timestamp_us": 1640995200000000,
    "confidence": 0.95
  },
  "processing_status": "RAW",
  "data_size_bytes": 512
}
```

#### 파일 업로드 응답
```json
{
  "id": 789,
  "original_filename": "aria_session_data.vrs",
  "file_type": "vrs",
  "file_size_bytes": 104857600,
  "file_hash": "a1b2c3d4e5f6...",
  "processing_status": "processed",
  "records_extracted": 1500,
  "storage_path": "uploads/a1b2c3d4_aria_session_data.vrs",
  "metadata": {
    "duration_seconds": 300,
    "streams": ["rgb", "slam_left", "slam_right"],
    "device_id": "aria-device-001"
  }
}
```

#### 데이터 스키마 (커스텀)
```json
{
  "id": 101,
  "schema_name": "IoT Sensor Schema v2.1",
  "data_format": "json",
  "schema_definition": {
    "type": "object",
    "properties": {
      "device_id": {"type": "string"},
      "timestamp": {"type": "string", "format": "date-time"},
      "sensors": {
        "type": "object",
        "properties": {
          "temperature": {"type": "number", "minimum": -40, "maximum": 85},
          "humidity": {"type": "number", "minimum": 0, "maximum": 100},
          "pressure": {"type": "number"}
        }
      }
    }
  },
  "usage_count": 47,
  "is_public": true,
  "description": "Standard IoT sensor data format with validation"
}
```

## 🔧 고급 사용법

### 📊 정제된 데이터 활용

#### 시간 범위 필터링
```bash
# 최근 1시간 Eye Gaze 데이터
curl "http://localhost:8000/api/v1/aria/eye-gaze/?start_time=2025-01-01T09:00:00Z&end_time=2025-01-01T10:00:00Z"

# 높은 신뢰도 데이터만
curl "http://localhost:8000/api/v1/aria/eye-gaze/?min_confidence=0.9"

# 특정 손 추적 데이터
curl "http://localhost:8000/api/v1/aria/hand-tracking/?has_left_hand=true&has_right_hand=false"
```

#### SLAM 궤적 분석
```bash
# 특정 위치 범위 필터링
curl "http://localhost:8000/api/v1/aria/slam-trajectory/?x_min=-1.0&x_max=1.0&y_min=-1.0&y_max=1.0"

# 전체 궤적 경로 가져오기
curl http://localhost:8000/api/v1/aria/slam-trajectory/trajectory_path/
```

### 🔧 원시 데이터 활용

#### CSV 데이터 업로드
```bash
curl -X POST http://localhost:8000/api/v1/aria/raw/uploads/ \
  -H "Content-Type: application/json" \
  -d '{
    "upload_name": "센서 데이터 배치 1",
    "data_type": "sensor_readings",
    "data_source": "arduino_mega",
    "data_format": "csv",
    "data_content": [
      {"timestamp": "2025-01-01T10:00:00Z", "temp": 25.4, "humidity": 60.2},
      {"timestamp": "2025-01-01T10:01:00Z", "temp": 25.6, "humidity": 59.8}
    ],
    "metadata": {"device_model": "Arduino Mega 2560", "firmware": "v2.1"}
  }'
```

#### JSON 실시간 스트림
```bash
curl -X POST http://localhost:8000/api/v1/aria/raw/raw-data/ \
  -H "Content-Type: application/json" \
  -d '{
    "data_type": "eye_tracking_custom",
    "data_source": "tobii_pro_x3",
    "data_format": "json",
    "data_content": {
      "left_pupil": {"x": 0.45, "y": 0.32, "diameter": 3.2},
      "right_pupil": {"x": 0.47, "y": 0.31, "diameter": 3.1},
      "gaze_point": {"x": 1920, "y": 1080},
      "confidence": 0.95
    }
  }'
```

#### 고급 쿼리 사용
```bash
curl -X POST http://localhost:8000/api/v1/aria/raw/raw-data/query/ \
  -H "Content-Type: application/json" \
  -d '{
    "data_type": "sensor_readings",
    "data_format": "json",
    "start_time": "2025-01-01T00:00:00Z",
    "end_time": "2025-01-01T23:59:59Z",
    "limit": 100
  }'
```

#### 파일 업로드 (VRS, CSV, Binary)
```bash
# VRS 파일 업로드
curl -X POST http://localhost:8000/api/v1/aria/raw/files/upload/ \
  -F "file=@aria_session.vrs" \
  -F "file_type=vrs" \
  -F "metadata={\"session_duration\": 300, \"device_id\": \"aria-001\"}"

# CSV 파일 업로드
curl -X POST http://localhost:8000/api/v1/aria/raw/files/upload/ \
  -F "file=@sensor_data.csv" \
  -F "file_type=csv" \
  -F "metadata={\"columns\": [\"timestamp\", \"temp\", \"humidity\"]}"
```

### 🎯 데이터 스키마 관리

#### 커스텀 스키마 생성
```bash
curl -X POST http://localhost:8000/api/v1/aria/raw/schemas/ \
  -H "Content-Type: application/json" \
  -d '{
    "schema_name": "IoT 센서 표준 v3.0",
    "data_format": "json",
    "schema_definition": {
      "type": "object",
      "required": ["device_id", "timestamp", "readings"],
      "properties": {
        "device_id": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "readings": {
          "type": "object",
          "properties": {
            "temperature": {"type": "number", "minimum": -40, "maximum": 85},
            "humidity": {"type": "number", "minimum": 0, "maximum": 100}
          }
        }
      }
    },
    "description": "IoT 센서를 위한 표준 JSON 스키마",
    "is_public": true
  }'
```

### 개발 모드로 실행
```bash
# 코드 변경사항 실시간 반영
docker-compose -f docker-compose.dev.yml up -d
```

### 로그 확인
```bash
# ARD 백엔드 로그
docker logs ARD-BACKEND -f

# Kafka 로그
docker logs ARD_KAFKA -f

# PostgreSQL 로그
docker logs ARD-POSTGRES -f
```

### 데이터 재로드
```bash
# 컨테이너 내에서 실제 MPS 데이터 재로드
docker exec ARD-BACKEND python manage.py load_real_sample_data --clear-existing
```

## 🛠️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Unity Client  │───▶│  Django REST    │───▶│   PostgreSQL    │
│   (Optional)    │    │      API        │    │    Database     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Apache Kafka    │
                       │ (Real-time)     │
                       └─────────────────┘
```

**핵심 구성요소:**
- **Django**: REST API 서버 (포트 8000)
- **PostgreSQL**: 메인 데이터베이스 (포트 5432) 
- **Apache Kafka**: 실시간 스트리밍 (포트 9092)
- **Project Aria Tools**: MPS 데이터 처리

## 🐛 문제 해결

### 포트 충돌
```bash
# 사용 중인 포트 확인
lsof -i :8000
lsof -i :5432
lsof -i :9092

# 충돌 시 포트 변경
# docker-compose.yml에서 "8001:8000" 형태로 수정
```


## 📚 데이터 구조

### Project Aria MPS 데이터 소스
- **Eye Gaze**: `data/mps_samples/eye_gaze/general_eye_gaze.csv`
- **Hand Tracking**: `data/mps_samples/hand_tracking/hand_tracking_results.csv`
- **SLAM**: `data/mps_samples/slam/closed_loop_trajectory.csv`

### API 필터링 옵션
```bash
# 시간 범위 필터링
?start_time=2025-01-01T00:00:00Z&end_time=2025-01-02T00:00:00Z

# 페이지네이션
?page=1&page_size=20

# 정렬
?ordering=-timestamp

# 검색
?search=keyword
```

## 🔑 환경 변수

시스템은 다음 환경 변수들을 자동으로 설정합니다:

```bash
# Django 설정
DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,backend

# 데이터베이스 설정  
DB_ENGINE=django.db.backends.postgresql
DB_HOST=postgres
DB_PORT=5432
DB_NAME=ard_db
DB_USER=postgres
DB_PASSWORD=password

# Kafka 설정
KAFKA_BOOTSTRAP_SERVERS=ARD_KAFKA:9092
KAFKA_GROUP_ID=ard-consumer-group
```
