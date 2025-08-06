#!/bin/bash
# Kafka 로컬 설치 스크립트 (개발/테스트용)

echo "=== Apache Kafka 로컬 설치 (개발용) ==="

# 설치 디렉토리
KAFKA_DIR="$HOME/kafka"
KAFKA_VERSION="3.6.0"
SCALA_VERSION="2.13"
KAFKA_ARCHIVE="kafka_${SCALA_VERSION}-${KAFKA_VERSION}.tgz"
KAFKA_URL="https://downloads.apache.org/kafka/${KAFKA_VERSION}/${KAFKA_ARCHIVE}"

# 1. Java 확인
echo "1. Java 버전 확인..."
if ! command -v java &> /dev/null; then
    echo "[ERROR] Java가 설치되어 있지 않습니다."
    echo "Java 17+ 설치 필요"
    exit 1
fi

JAVA_VERSION=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | cut -d'.' -f1)
if [ "$JAVA_VERSION" -lt 17 ]; then
    echo "[ERROR] Java 17 이상 필요 (현재: $JAVA_VERSION)"
    exit 1
fi

echo "[OK] Java 버전: $(java -version 2>&1 | head -n 1)"

# 2. Kafka 다운로드
echo -e "\n2. Kafka 다운로드..."
mkdir -p $KAFKA_DIR
cd $KAFKA_DIR

if [ ! -f "$KAFKA_ARCHIVE" ]; then
    echo "다운로드 중: $KAFKA_URL"
    wget $KAFKA_URL
else
    echo "[OK] 이미 다운로드됨: $KAFKA_ARCHIVE"
fi

# 3. 압축 해제
echo -e "\n3. 압축 해제..."
tar -xzf $KAFKA_ARCHIVE
KAFKA_HOME="$KAFKA_DIR/kafka_${SCALA_VERSION}-${KAFKA_VERSION}"
echo "[OK] 설치 위치: $KAFKA_HOME"

# 4. 설정 파일 수정 (개발용 최적화)
echo -e "\n4. 개발용 설정..."
cd $KAFKA_HOME

# server.properties 백업 및 수정
cp config/server.properties config/server.properties.backup

# 개발용 설정 적용
cat > config/server.properties << EOF
# 기본 설정
broker.id=0
listeners=PLAINTEXT://localhost:9092
advertised.listeners=PLAINTEXT://localhost:9092
log.dirs=/tmp/kafka-logs

# KRaft 모드 설정 (Zookeeper 불필요)
process.roles=broker,controller
node.id=1
controller.quorum.voters=1@localhost:9093
listeners=PLAINTEXT://localhost:9092,CONTROLLER://localhost:9093
inter.broker.listener.name=PLAINTEXT
advertised.listeners=PLAINTEXT://localhost:9092
controller.listener.names=CONTROLLER

# 로그 설정
log.retention.hours=24
log.segment.bytes=1073741824
log.retention.check.interval.ms=300000

# 성능 설정 (개발용)
num.network.threads=8
num.io.threads=8
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

# 압축
compression.type=gzip

# 개발 편의 설정
auto.create.topics.enable=true
delete.topic.enable=true
EOF

echo "[OK] server.properties 설정 완료"

# 5. 시작 스크립트 생성
echo -e "\n5. 시작 스크립트 생성..."
cat > $KAFKA_HOME/start-kafka.sh << 'EOF'
#!/bin/bash
KAFKA_HOME=$(dirname "$0")

echo "=== Kafka 시작 (KRaft 모드) ==="

# 클러스터 ID 생성
if [ ! -f "$KAFKA_HOME/.cluster_id" ]; then
    echo "클러스터 ID 생성..."
    KAFKA_CLUSTER_ID=$($KAFKA_HOME/bin/kafka-storage.sh random-uuid)
    echo $KAFKA_CLUSTER_ID > $KAFKA_HOME/.cluster_id
    
    echo "로그 디렉토리 포맷..."
    $KAFKA_HOME/bin/kafka-storage.sh format -t $KAFKA_CLUSTER_ID -c $KAFKA_HOME/config/server.properties
fi

# Kafka 시작
echo "Kafka 서버 시작..."
$KAFKA_HOME/bin/kafka-server-start.sh $KAFKA_HOME/config/server.properties
EOF

chmod +x $KAFKA_HOME/start-kafka.sh

cat > $KAFKA_HOME/stop-kafka.sh << 'EOF'
#!/bin/bash
KAFKA_HOME=$(dirname "$0")

echo "Kafka 종료..."
$KAFKA_HOME/bin/kafka-server-stop.sh
echo "완료"
EOF

chmod +x $KAFKA_HOME/stop-kafka.sh

# 6. 토픽 생성 스크립트
cat > $KAFKA_HOME/create-topics.sh << 'EOF'
#!/bin/bash
KAFKA_HOME=$(dirname "$0")

create_topic() {
    TOPIC=$1
    PARTITIONS=$2
    echo "토픽 생성: $TOPIC (파티션: $PARTITIONS)"
    $KAFKA_HOME/bin/kafka-topics.sh --create --topic $TOPIC --bootstrap-server localhost:9092 --partitions $PARTITIONS --replication-factor 1 --if-not-exists
}

echo "=== Project Aria 토픽 생성 ==="

# 메인 토픽
create_topic "vrs-frames" 3
create_topic "sensor-data" 3
create_topic "image-metadata" 3

# 스트림별 토픽
create_topic "stream-camera-rgb" 2
create_topic "stream-camera-slam-left" 2
create_topic "stream-camera-slam-right" 2
create_topic "stream-camera-eyetracking" 2
create_topic "stream-imu-right" 1
create_topic "stream-imu-left" 1
create_topic "stream-magnetometer" 1
create_topic "stream-barometer" 1
create_topic "stream-microphone" 1

echo -e "\n토픽 목록:"
$KAFKA_HOME/bin/kafka-topics.sh --list --bootstrap-server localhost:9092
EOF

chmod +x $KAFKA_HOME/create-topics.sh

# 7. 환경 변수 설정
echo -e "\n6. 환경 변수 설정..."
cat > $KAFKA_HOME/kafka-env.sh << EOF
export KAFKA_HOME="$KAFKA_HOME"
export PATH="\$KAFKA_HOME/bin:\$PATH"
alias kafka-start="$KAFKA_HOME/start-kafka.sh"
alias kafka-stop="$KAFKA_HOME/stop-kafka.sh"
alias kafka-topics="$KAFKA_HOME/create-topics.sh"
EOF

echo "[OK] 환경 설정 파일 생성됨"

# 8. 완료 메시지
echo -e "\n=== 설치 완료 ==="
echo "Kafka 홈: $KAFKA_HOME"
echo ""
echo "사용법:"
echo "  1. source $KAFKA_HOME/kafka-env.sh"
echo "  2. kafka-start    # Kafka 시작"
echo "  3. kafka-topics   # 토픽 생성"
echo "  4. kafka-stop     # Kafka 종료"
echo ""
echo "또는 직접 실행:"
echo "  $KAFKA_HOME/start-kafka.sh"
echo ""
echo "나중에 Docker 배포시 docker-compose.kafka.yml 사용"