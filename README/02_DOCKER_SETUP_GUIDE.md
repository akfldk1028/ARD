# 02. Docker 설치 및 실행 가이드

> **📖 문서 가이드**: [00_INDEX.md](00_INDEX.md) | **이전**: [01_ARD_SYSTEM_ARCHITECTURE.md](01_ARD_SYSTEM_ARCHITECTURE.md) | **다음**: [03_API_STRUCTURE_REFERENCE.md](03_API_STRUCTURE_REFERENCE.md)  
> **카테고리**: 시스템 이해 및 설치 | **난이도**: ⭐⭐ | **예상 시간**: 10분

## 🎯 개요

ARD 시스템을 Docker로 완전히 실행하는 방법을 설명합니다. 자동 샘플 데이터 다운로드와 바이너리 스트리밍을 포함한 완전한 시스템을 구축할 수 있습니다.

## 🚀 빠른 시작 (3분)

### 자동화 스크립트 사용 (권장)
```bash
# 전체 시스템 자동 설치 및 실행
bash quick-start.sh
```

### 수동 설치
```bash
# 1. Kafka 컨테이너 실행
docker-compose -f kafka-compose.yml up -d

# 2. ARD 이미지 빌드 및 실행
docker build -t ard-api:v10 .
docker-compose up -d

# 3. API 테스트
bash test-api.sh
```

## 🏗️ 시스템 구성

### 컨테이너 구조

| 컨테이너명 | 이미지 | 포트 | 역할 |
|-----------|-------|------|------|
| **ARD_KAFKA** | bitnami/kafka:latest | 9092 | 실시간 스트리밍 |
| **ARD-BACKEND** | ard-api:v10 | 8000 | Django REST API |
| **ARD-POSTGRES** | postgres:15-alpine | 5432 | 데이터베이스 |

### 네트워크 구성
```yaml
# Docker Compose 네트워크
networks:
  - ard-network (Django ↔ PostgreSQL)
  - kafka-network (Kafka 전용)
  - 250728_ard_kafka-network (컨테이너 간 연결)
```

## 📦 상세 설치 과정

### 1. 사전 요구사항
```bash
# Docker 설치 확인
docker --version
docker-compose --version

# 최소 시스템 요구사항
# - 메모리: 4GB 이상
# - 디스크: 2GB 이상
# - CPU: 2 cores 이상
```

### 2. Kafka 컨테이너 실행
```bash
# kafka-compose.yml 실행
docker-compose -f kafka-compose.yml up -d

# 실행 확인
docker ps | grep ARD_KAFKA

# Kafka 준비 대기 (30초)
sleep 30
```

**Kafka 설정 하이라이트:**
- **컨테이너명**: `ARD_KAFKA` (일관된 네이밍)
- **KRaft 모드**: Zookeeper 없이 단독 실행
- **네트워크**: 컨테이너 간 통신 `ARD_KAFKA:9092`
- **외부 접근**: `localhost:9092`

### 3. ARD 시스템 빌드 및 실행
```bash
# Django 이미지 빌드 (ard-api:v10)
docker build -t ard-api:v10 .

# 전체 시스템 실행
docker-compose up -d

# 시스템 초기화 대기 (60초)
sleep 60
```

**빌드 과정에서 자동 실행되는 작업:**
- ✅ Python 패키지 설치
- ✅ Django 마이그레이션
- ✅ 정적 파일 수집
- ✅ **자동 샘플 데이터 다운로드** (첫 실행시)
- ✅ Kafka Consumer 백그라운드 시작

### 4. 실행 상태 확인
```bash
# 모든 컨테이너 상태 확인
docker ps --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"

# 결과 예시:
# ARD_KAFKA      Up 2 minutes              0.0.0.0:9092->9092/tcp
# ARD-BACKEND    Up 2 minutes (healthy)    0.0.0.0:8000->8000/tcp
# ARD-POSTGRES   Up 2 minutes (healthy)    0.0.0.0:5432->5432/tcp
```

## 🧪 기능 테스트

### API 엔드포인트 테스트
```bash
# 1. API 루트 확인
curl http://localhost:8000/api/v1/aria/

# 2. 바이너리 스트리밍 상태
curl http://localhost:8000/api/v1/aria/binary/streaming/

# 3. 바이너리 프레임 전송 테스트
curl -X POST http://localhost:8000/api/v1/aria/binary/test-message/ \
  -H "Content-Type: application/json" \
  -d '{"session_id": "docker-test", "test_type": "binary_frame"}'
```

### 성공적인 응답 예시
```json
{
  "status": "success",
  "message": "Test binary frame sent",
  "result": {
    "success": true,
    "frame_id": "docker-test_214-1_1_1754112272353173084",
    "compression": {
      "format": "jpeg",
      "compression_ratio": 0.30,
      "original_size": 921600,
      "compressed_size": 275163
    },
    "kafka_results": {
      "metadata": {"partition": 0, "offset": 1},
      "binary": {"partition": 0, "offset": 1},
      "registry": {"partition": 0, "offset": 1}
    }
  }
}
```

## 🔧 고급 설정

### 환경 변수 설정
```bash
# docker-compose.yml의 환경변수
environment:
  - DEBUG=1
  - ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,backend
  - DB_HOST=postgres
  - KAFKA_BOOTSTRAP_SERVERS=ARD_KAFKA:9092
  - KAFKA_GROUP_ID=ard-consumer-group
```

### 볼륨 마운팅
```yaml
volumes:
  # 개발 코드 실시간 반영
  - ./ARD:/app/ARD
  # 샘플 데이터 영구 저장
  - ./ARD/data:/app/ARD/data
```

### 자동 샘플 데이터 다운로드
**docker-entrypoint.sh에서 자동 실행:**
```bash
📥 Checking sample data...
📥 Downloading Project Aria sample data (first run)...
✅ Sample data downloaded successfully!
```

**다운로드되는 데이터:**
- `sample.vrs` - Project Aria VRS 샘플 파일
- `slam_v1_1_0.zip` - SLAM 데이터
- `eye_gaze_v3_1_0.zip` - 시선 추적 데이터
- `hand_tracking_v2_0_0.zip` - 손 추적 데이터

## 🛠️ 트러블슈팅

### 일반적인 문제 해결

**1. Kafka 연결 실패**
```bash
# 증상: "NoBrokersAvailable" 에러
# 해결: Kafka 재시작
docker restart ARD_KAFKA
sleep 30
```

**2. 바이너리 스트리밍 타임아웃**
```bash
# 증상: KafkaTimeoutError
# 해결: 네트워크 설정 확인
docker network ls | grep kafka
docker inspect ARD-BACKEND | grep NetworkMode
```

**3. 샘플 데이터 다운로드 실패**
```bash
# 수동 다운로드
docker exec ARD-BACKEND python /app/ARD/manage.py download_sample_data
```

**4. 포트 충돌**
```bash
# 포트 사용 확인
netstat -tlnp | grep -E "(8000|9092|5432)"

# 포트 변경 (docker-compose.yml 수정)
ports:
  - "8001:8000"  # Django
  - "9093:9092"  # Kafka
```

### 로그 확인
```bash
# Django 애플리케이션 로그
docker logs ARD-BACKEND -f

# Kafka 로그
docker logs ARD_KAFKA -f

# PostgreSQL 로그
docker logs ARD-POSTGRES -f

# 전체 시스템 로그
docker-compose logs -f
```

## 📊 성능 및 모니터링

### 시스템 리소스 사용량
```bash
# 컨테이너별 리소스 사용량
docker stats ARD-BACKEND ARD_KAFKA ARD-POSTGRES

# 디스크 사용량
docker system df

# 네트워크 트래픽 모니터링
docker exec ARD-BACKEND ss -tuln
```

### Kafka 토픽 모니터링
```bash
# 토픽 목록
docker exec ARD_KAFKA kafka-topics.sh --list --bootstrap-server localhost:9092

# 메타데이터 토픽 메시지 확인
docker exec ARD_KAFKA kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic vrs-metadata-stream \
  --from-beginning
```

## 🔄 업데이트 및 재배포

### 코드 변경 후 재배포
```bash
# 이미지 재빌드
docker build -t ard-api:v10 . --no-cache

# 서비스 재시작
docker-compose down
docker-compose up -d
```

### 데이터베이스 초기화
```bash
# 완전 초기화 (데이터 삭제)
docker-compose down -v
docker-compose up -d
```

## 🚀 프로덕션 배포

### 보안 설정
```yaml
# 프로덕션 환경변수
environment:
  - DEBUG=0
  - SECRET_KEY=your-secret-key
  - ALLOWED_HOSTS=your-domain.com
```

### 리소스 제한
```yaml
# 컨테이너 리소스 제한
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '0.5'
```

---

## ✅ 성공 기준

시스템이 정상적으로 설치되었다면:

1. **✅ 모든 컨테이너 실행 중**: ARD_KAFKA, ARD-BACKEND, ARD-POSTGRES
2. **✅ API 응답 정상**: `curl http://localhost:8000/api/v1/aria/`
3. **✅ 바이너리 스트리밍 동작**: 테스트 메시지 전송 성공
4. **✅ 샘플 데이터 존재**: `ARD/data/mps_samples/` 폴더 생성
5. **✅ Kafka 토픽 생성**: 11개 토픽 자동 생성

**🎉 이제 ARD 시스템이 완전히 준비되었습니다!**

**다음 단계**: [03_API_STRUCTURE_REFERENCE.md](03_API_STRUCTURE_REFERENCE.md)에서 API 사용법을 배워보세요.