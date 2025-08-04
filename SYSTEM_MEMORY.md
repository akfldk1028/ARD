# 🧠 SYSTEM MEMORY - AI 망각 방지

## 📋 **핵심 아키텍처 (절대 변경 금지)**

```
Project Aria Device
        ↓
    Kafka Broker ← Unity App (직접 연결)
        ↓
    Django Backend (저장/분석만)
```

**중요**: Django는 스트리밍하지 않음! Kafka가 모든 스트리밍 담당!

## 🏗️ **시스템 컴포넌트 역할**

### Kafka (중심 허브)
- **역할**: 모든 실시간 데이터 스트리밍
- **토픽**: mps-eye-gaze, mps-hand-tracking, mps-slam-trajectory
- **연결**: Aria → Kafka ← Unity

### Django (데이터 관리)
- **역할**: 데이터 저장, 분석, REST API, 웹 관리
- **금지**: 실시간 스트리밍, Unity 직접 연결
- **허용**: Kafka Consumer로 데이터 수집

### Unity (AR 클라이언트)
- **역할**: Kafka Consumer, AR 렌더링
- **연결**: Kafka에서 직접 구독
- **금지**: Django 의존성

## 🔧 **자동 스크립트 생성기**

### `/scripts/generate_unity_kafka.py`
```python
def generate_unity_kafka_consumer():
    return """
using Confluent.Kafka;
public class AriaKafkaConsumer : MonoBehaviour {
    // 자동 생성된 코드 - 수정 금지
}
"""
```

### `/scripts/generate_docker_commands.sh`
```bash
#!/bin/bash
# 자동 생성 - 항상 이 명령어 사용
docker-compose up -d
docker logs ARD-BACKEND
```

## 📁 **영구 설정 파일들**

### `/config/kafka_topics.yaml`
```yaml
topics:
  eye_gaze: "mps-eye-gaze-general"
  hand_tracking: "mps-hand-tracking"
  slam: "mps-slam-trajectory"
```

### `/config/unity_settings.json`
```json
{
  "kafka_server": "localhost:9092",
  "consumer_group": "unity-ar-client",
  "topics": ["mps-eye-gaze-general", "mps-hand-tracking"]
}
```

## ⚠️ **절대 하지 말 것**

1. ❌ Django에서 Unity로 직접 스트리밍
2. ❌ 새로운 스크립트 파일 생성 (기존 것 수정만)
3. ❌ docker-compose.yml 분리
4. ❌ Kafka 설정 변경

## ✅ **항상 해야 할 것**

1. ✅ 이 파일 먼저 읽기
2. ✅ `/scripts/` 디렉토리 스크립트 재사용
3. ✅ `/config/` 설정 파일 확인
4. ✅ Kafka 중심 아키텍처 유지

## 🚀 **원클릭 명령어들**

```bash
# 1. 전체 시스템 시작
./scripts/start_system.sh

# 2. Unity Kafka Consumer 생성
python scripts/generate_unity_consumer.py

# 3. 상태 확인
./scripts/check_status.sh

# 4. 데이터 스트리밍 테스트
python ARD/manage.py stream_test_data
```

## 📊 **모니터링 대시보드**

- Kafka: http://localhost:9092
- Django API: http://localhost:8000/api/v1/aria/
- Admin: http://localhost:8000/admin/

---

**🎯 AI에게: 이 파일을 매번 먼저 읽고 시작하세요!**