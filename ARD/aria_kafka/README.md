# Kafka Streaming System for Project Aria

기존 공식문서 스트리밍을 유지하면서 Kafka를 통한 확장 가능한 스트리밍 시스템

## 시스템 구조

```
ARD/kafka/
├── config/            # Kafka 설정
├── producers/         # VRS 데이터 → Kafka 
├── consumers/         # Kafka → Django API
├── managers/          # Producer/Consumer 관리
├── utils/            # 데이터 제어 (터짐 방지)
├── views/            # REST API Views
└── tests/            # 테스트 코드
```

## Kafka 설치 (Windows WSL/Linux)

```bash
# 1. Kafka 다운로드
wget https://downloads.apache.org/kafka/3.6.0/kafka_2.13-3.6.0.tgz
tar -xzf kafka_2.13-3.6.0.tgz
cd kafka_2.13-3.6.0

# 2. Zookeeper 시작
bin/windows/zookeeper-server-start.bat config/zookeeper.properties

# 3. Kafka 서버 시작 (새 터미널)
bin/windows/kafka-server-start.bat config/server.properties

# 4. 토픽 생성
bash ARD/kafka/setup/kafka_setup.sh
```

## 사용법

### 1. Kafka 없이 API 테스트
```bash
# Django 서버 시작
python ARD/manage.py runserver

# API 테스트
python ARD/kafka/tests/test_kafka_streaming.py
```

### 2. 전체 시스템 실행
```bash
# 1. Kafka 서버 시작 (위 참조)

# 2. Django 서버 시작
python ARD/manage.py runserver

# 3. Kafka 스트리밍 시작
python ARD/manage.py start_kafka_streaming --fps 10

# 4. 개별 스트림만 시작
python ARD/manage.py start_kafka_streaming --streams camera-rgb imu-right
```

## API 엔드포인트

### 이미지 스트림
```
GET /api/v2/kafka-streams/images/camera-rgb/latest/
GET /api/v2/kafka-streams/images/camera-slam-left/latest/
GET /api/v2/kafka-streams/images/camera-slam-right/latest/
GET /api/v2/kafka-streams/images/camera-eyetracking/latest/
```

### 센서 스트림
```
GET /api/v2/kafka-streams/sensors/imu-right/latest/
GET /api/v2/kafka-streams/sensors/imu-left/latest/
GET /api/v2/kafka-streams/sensors/magnetometer/latest/
GET /api/v2/kafka-streams/sensors/barometer/latest/
GET /api/v2/kafka-streams/sensors/microphone/latest/
```

### 스트림 제어
```
POST /api/v2/kafka-streams/control/producer/start/{stream_name}/
POST /api/v2/kafka-streams/control/producer/stop/{stream_name}/
```

### 관리자 API
```
GET /api/v2/kafka-streams/admin/status/
GET /api/v2/kafka-streams/admin/health/
GET /api/v2/kafka-streams/admin/streams/
```

## 데이터 터짐 방지

- **레이트 리미팅**: 초당 100 메시지, 10MB 제한
- **스마트 샘플링**: 이미지 30%, 센서 10%
- **백프레셔**: 큐 가득찰 시 우선순위 기반 처리
- **압축**: gzip 압축으로 네트워크 효율

## 기존 시스템과의 호환성

- 기존 `/api/v1/aria-sessions/` API 유지
- 새로운 `/api/v2/kafka-streams/` API 추가
- 기존 VRS 처리 로직 재사용
- Project Aria 공식 SDK 활용

## 유지보수

### 로그 확인
```bash
# Kafka 로그
tail -f logs/server.log

# Django 로그  
tail -f django.log
```

### 성능 모니터링
```bash
# Kafka 토픽 상태
bin/kafka-topics.sh --describe --bootstrap-server localhost:9092

# Consumer 그룹 상태
bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list
```

### 문제 해결
- Kafka 연결 오류: 방화벽/포트 확인 (9092)
- 메모리 부족: JVM 힙 크기 조정
- 데이터 지연: 파티션 수 증가