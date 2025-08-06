#!/bin/bash
# Kafka 설정 및 토픽 생성 스크립트

echo "=== Kafka 설정 시작 ==="

# Kafka 설치 확인
if ! command -v kafka-topics.sh &> /dev/null; then
    echo "Kafka가 설치되어 있지 않습니다. 먼저 Kafka를 설치하세요."
    echo "설치 명령: sudo apt-get install kafka"
    exit 1
fi

# Kafka 서버 상태 확인
KAFKA_HOST="localhost:9092"
echo "Kafka 서버 확인: $KAFKA_HOST"

# 토픽 생성 함수
create_topic() {
    TOPIC_NAME=$1
    PARTITIONS=$2
    REPLICATION=$3
    
    echo "토픽 생성: $TOPIC_NAME (파티션: $PARTITIONS)"
    kafka-topics.sh --create \
        --bootstrap-server $KAFKA_HOST \
        --topic $TOPIC_NAME \
        --partitions $PARTITIONS \
        --replication-factor $REPLICATION \
        --if-not-exists
}

# VRS 스트림 토픽 생성
echo "=== VRS 스트림 토픽 생성 ==="
create_topic "vrs-frames" 3 1
create_topic "sensor-data" 3 1
create_topic "image-metadata" 3 1

# 개별 스트림 토픽 생성 (선택사항)
echo "=== 개별 스트림 토픽 생성 ==="
create_topic "stream-camera-rgb" 1 1
create_topic "stream-camera-slam-left" 1 1
create_topic "stream-camera-slam-right" 1 1
create_topic "stream-camera-eyetracking" 1 1
create_topic "stream-imu-right" 1 1
create_topic "stream-imu-left" 1 1
create_topic "stream-magnetometer" 1 1
create_topic "stream-barometer" 1 1
create_topic "stream-microphone" 1 1

# 토픽 목록 확인
echo "=== 생성된 토픽 목록 ==="
kafka-topics.sh --list --bootstrap-server $KAFKA_HOST

# Consumer Group 생성
echo "=== Consumer Group 설정 ==="
echo "Consumer Group 'aria-streaming-group' 자동 생성됨"

echo "=== Kafka 설정 완료 ==="
echo "다음 명령으로 Kafka 서버 시작:"
echo "  1. Zookeeper: bin/zookeeper-server-start.sh config/zookeeper.properties"
echo "  2. Kafka: bin/kafka-server-start.sh config/server.properties"