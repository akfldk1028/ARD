#!/bin/bash
# Kafka Docker 설치 스크립트 - Apache 공식 이미지 사용

echo "=== Apache Kafka Docker 설치 ==="

# 1. Docker 실행 확인
echo "1. Docker 상태 확인..."
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker가 설치되어 있지 않습니다."
    echo "Docker Desktop 설치: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Docker 실행 중인지 확인
if ! docker info > /dev/null 2>&1; then
    echo "[ERROR] Docker가 실행되고 있지 않습니다."
    echo "Docker Desktop을 시작하세요."
    exit 1
fi

echo "[OK] Docker 실행 중"

# 2. 최신 Kafka Docker 이미지 Pull
echo -e "\n2. Apache Kafka 공식 이미지 다운로드..."
echo "JVM 기반 이미지 (권장):"
docker pull apache/kafka:latest

echo -e "\nNative 이미지 (실험적):"
docker pull apache/kafka-native:latest

# 3. Kafka 실행 (단일 노드)
echo -e "\n3. Kafka 컨테이너 실행..."
echo "다음 명령으로 Kafka를 시작할 수 있습니다:"
echo ""
echo "# JVM 버전 (권장):"
echo "docker run -d --name kafka-server -p 9092:9092 apache/kafka:latest"
echo ""
echo "# Native 버전 (빠른 시작):"
echo "docker run -d --name kafka-server-native -p 9092:9092 apache/kafka-native:latest"
echo ""

# 4. Docker Compose 파일 생성
echo -e "\n4. Docker Compose 파일 생성..."
cat > docker-compose.kafka.yml << 'EOF'
version: '3.8'

services:
  kafka:
    image: apache/kafka:latest
    container_name: kafka-aria
    ports:
      - "9092:9092"
    environment:
      # Kafka 기본 설정
      KAFKA_NODE_ID: 1
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092'
      KAFKA_LISTENERS: 'PLAINTEXT://kafka:29092,CONTROLLER://kafka:29093,PLAINTEXT_HOST://0.0.0.0:9092'
      KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka:29093'
      KAFKA_PROCESS_ROLES: 'broker,controller'
      
      # 로그 설정
      KAFKA_LOG_DIRS: '/tmp/kafka-logs'
      KAFKA_LOG_RETENTION_HOURS: 24
      KAFKA_LOG_SEGMENT_BYTES: 1073741824
      
      # 성능 설정
      KAFKA_COMPRESSION_TYPE: 'gzip'
      KAFKA_MAX_REQUEST_SIZE: 10485760  # 10MB
      
    volumes:
      - kafka-data:/tmp/kafka-logs
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions.sh", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 10s
      retries: 5

volumes:
  kafka-data:
    driver: local
EOF

echo "[OK] docker-compose.kafka.yml 생성됨"

# 5. 실행 스크립트 생성
echo -e "\n5. 실행 스크립트 생성..."
cat > start_kafka.sh << 'EOF'
#!/bin/bash
echo "Starting Kafka with Docker Compose..."
docker-compose -f docker-compose.kafka.yml up -d

echo "Waiting for Kafka to be ready..."
sleep 10

echo "Checking Kafka status..."
docker ps | grep kafka-aria

echo -e "\nKafka is running on localhost:9092"
echo "To view logs: docker logs -f kafka-aria"
echo "To stop: docker-compose -f docker-compose.kafka.yml down"
EOF

chmod +x start_kafka.sh

cat > stop_kafka.sh << 'EOF'
#!/bin/bash
echo "Stopping Kafka..."
docker-compose -f docker-compose.kafka.yml down
echo "Kafka stopped."
EOF

chmod +x stop_kafka.sh

echo "[OK] 실행 스크립트 생성됨"

echo -e "\n=== 설치 완료 ==="
echo "사용법:"
echo "  시작: ./start_kafka.sh"
echo "  중지: ./stop_kafka.sh"
echo "  로그: docker logs -f kafka-aria"
echo ""
echo "토픽 생성은 create_topics.sh 실행"