# ARD (Aria Real-time Data) System

실시간 AR 데이터 처리를 위한 Django + Kafka 시스템입니다.

## 🚀 **원클릭 실행** (30초)

```bash
git clone <your-repo-url>
cd ARD_Backend
docker-compose up -d
```

**완료!** 🎉 브라우저에서 확인: http://localhost:8000/api/v1/aria/

## 🔥 **즉시 테스트**

```bash
# 340개 실제 데이터 확인
curl http://localhost:8000/api/v1/aria/api/sessions/
curl http://localhost:8000/api/v1/aria/api/eye-gaze/?limit=3
curl http://localhost:8000/api/v1/aria/api/hand-tracking/?limit=3
curl http://localhost:8000/api/v1/aria/api/slam-trajectory/?limit=3

# Raw MPS 원본 데이터 확인
curl http://localhost:8000/api/v1/aria/raw/eye-gaze/?limit=2
curl http://localhost:8000/api/v1/aria/raw/statistics/

# Binary VRS 이미지 데이터 확인 (VRS 스트리밍 후)
curl http://localhost:8000/api/v1/aria/binary/api/registry/?limit=3
curl http://localhost:8000/api/v1/aria/binary/api/metadata/?limit=3

# Kafka 테스트
curl -X POST http://localhost:8000/api/v1/aria/test-message/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message"}'
```

## 📊 **자동 설정되는 것들**

✅ **Meta Project Aria 샘플 데이터 자동 다운로드**  
✅ **340개 실제 AR 데이터 포인트 로드**  
✅ **PostgreSQL + Kafka + Django 모든 컨테이너 자동 실행**  
✅ **REST API 즉시 사용 가능**  

## 💡 **주요 기능**

- **Eye Gaze Tracking**: 190개 데이터 (General + Personalized)
- **Hand Tracking**: 50개 실제 손 추적 데이터  
- **SLAM Trajectory**: 100개 위치 추적 데이터
- **3계층 API**: Raw/General/Binary 데이터 지원
- **Kafka Streaming**: 실시간 데이터 스트리밍 지원
- **확장 가능**: 스마트워치, 웹캠 등 다른 디바이스 쉽게 추가

## 🛠️ **VRS 이미지 스트리밍 활성화**

**방법 1: 자동 시작 (권장)**
```bash
# docker-entrypoint.sh에서 VRS 스트리밍 라인 주석 해제 후
docker-compose restart backend
```

**방법 2: 수동 시작**
```bash
# 컨테이너 안에서 VRS 스트리밍 시작
docker exec ARD-BACKEND python /app/ARD/manage.py stream_vrs_data \
  --vrs-file /app/ARD/data/mps_samples/sample.vrs \
  --mps-data-path /app/ARD/data/mps_samples \
  --duration 60 \
  --stream-type vrs \
  --kafka-servers ARD_KAFKA:9092

# VRS 스트림 데이터 확인
curl http://localhost:8000/api/v1/aria/api/vrs-streams/
```

## 🛠️ **개발자 명령어**

```bash
# 컨테이너 상태 확인
docker ps

# 로그 확인
docker logs ARD-BACKEND

# 컨테이너 재시작
docker-compose restart

# 전체 정리
docker-compose down
```

## 📚 **API 문서**

- **메인 API**: http://localhost:8000/api/v1/aria/api/
- **Raw 데이터**: http://localhost:8000/api/v1/aria/raw/
- **바이너리 스트리밍**: http://localhost:8000/api/v1/aria/binary/
- **Django Admin**: http://localhost:8000/admin/

---

**🎯 한 줄 실행으로 모든 AR 데이터 API가 준비됩니다!**