#!/bin/bash
# Kafka 토픽 생성 스크립트

echo "=== Kafka 토픽 생성 ==="

# Kafka 컨테이너 확인
if ! docker ps | grep -q kafka-aria; then
    echo "[ERROR] Kafka 컨테이너가 실행 중이지 않습니다."
    echo "먼저 ./start_kafka.sh 실행하세요."
    exit 1
fi

# 토픽 생성 함수
create_topic() {
    TOPIC_NAME=$1
    PARTITIONS=$2
    echo "토픽 생성: $TOPIC_NAME (파티션: $PARTITIONS)"
    
    docker exec kafka-aria kafka-topics.sh \
        --create \
        --topic $TOPIC_NAME \
        --bootstrap-server localhost:9092 \
        --partitions $PARTITIONS \
        --replication-factor 1 \
        --if-not-exists \
        2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "[OK] $TOPIC_NAME 생성됨"
    else
        echo "[INFO] $TOPIC_NAME 이미 존재하거나 오류"
    fi
}

echo -e "\n=== 메인 토픽 생성 ==="
create_topic "vrs-frames" 3
create_topic "sensor-data" 3
create_topic "image-metadata" 3

echo -e "\n=== 개별 스트림 토픽 생성 ==="
# 이미지 스트림
create_topic "stream-camera-rgb" 2
create_topic "stream-camera-slam-left" 2
create_topic "stream-camera-slam-right" 2
create_topic "stream-camera-eyetracking" 2

# 센서 스트림
create_topic "stream-imu-right" 1
create_topic "stream-imu-left" 1
create_topic "stream-magnetometer" 1
create_topic "stream-barometer" 1
create_topic "stream-microphone" 1

echo -e "\n=== 생성된 토픽 목록 ==="
docker exec kafka-aria kafka-topics.sh --list --bootstrap-server localhost:9092

echo -e "\n=== 토픽 상세 정보 ==="
docker exec kafka-aria kafka-topics.sh --describe --bootstrap-server localhost:9092 --topic vrs-frames

echo -e "\n=== 토픽 생성 완료 ==="