#!/bin/bash

# ========================================
# Project Aria + Django Kafka 설치 스크립트
# Ubuntu/Debian 기준
# ========================================

echo "🔥 Project Aria Django + Kafka 설치 시작..."

# 1. Java 설치 (Kafka 필수)
echo "📦 Java 11 설치 중..."
sudo apt update
sudo apt install -y openjdk-11-jdk

# Java 버전 확인
java -version
echo "JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64" | sudo tee -a /etc/environment
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64

# 2. Kafka 다운로드 및 설치
echo "🚀 Kafka 2.8.0 다운로드 중..."
cd /opt
sudo wget https://downloads.apache.org/kafka/2.8.0/kafka_2.13-2.8.0.tgz
sudo tar -xzf kafka_2.13-2.8.0.tgz
sudo mv kafka_2.13-2.8.0 kafka
sudo chown -R $USER:$USER /opt/kafka

# 3. Kafka 설정 파일 수정 (Project Aria용)
echo "⚙️ Kafka 설정 최적화..."

# Zookeeper 설정
cat > /opt/kafka/config/zookeeper.properties << 'EOF'
# Zookeeper configuration for Project Aria
dataDir=/tmp/zookeeper
clientPort=2181
maxClientCnxns=0
admin.enableServer=false
EOF

# Kafka Server 설정 (대용량 데이터 처리 최적화)
cat > /opt/kafka/config/server.properties << 'EOF'
# Project Aria Kafka Configuration
broker.id=0
listeners=PLAINTEXT://localhost:9092
advertised.listeners=PLAINTEXT://localhost:9092
num.network.threads=8
num.io.threads=16
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

# Log configuration for large messages (VRS data)
log.dirs=/tmp/kafka-logs
num.partitions=3
num.recovery.threads.per.data.dir=2
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1

# Message size limits for Project Aria VRS files
message.max.bytes=10485760
replica.fetch.max.bytes=10485760
fetch.message.max.bytes=10485760

# Log retention for real-time streaming
log.retention.hours=24
log.segment.bytes=1073741824
log.retention.check.interval.ms=300000

# Zookeeper connection
zookeeper.connect=localhost:2181
zookeeper.connection.timeout.ms=18000

# Group coordinator settings
group.initial.rebalance.delay.ms=0
EOF

# 4. Systemd 서비스 생성
echo "🎯 Systemd 서비스 생성..."

# Zookeeper 서비스
sudo tee /etc/systemd/system/zookeeper.service > /dev/null << 'EOF'
[Unit]
Description=Apache Zookeeper server
Documentation=http://zookeeper.apache.org
Requires=network.target remote-fs.target
After=network.target remote-fs.target

[Service]
Type=simple
ExecStart=/opt/kafka/bin/zookeeper-server-start.sh /opt/kafka/config/zookeeper.properties
ExecStop=/opt/kafka/bin/zookeeper-server-stop.sh
Restart=on-abnormal
User=kafka
Group=kafka

[Install]
WantedBy=multi-user.target
EOF

# Kafka 서비스
sudo tee /etc/systemd/system/kafka.service > /dev/null << 'EOF'
[Unit]
Description=Apache Kafka Server
Documentation=http://kafka.apache.org/documentation.html
Requires=zookeeper.service
After=zookeeper.service

[Service]
Type=simple
ExecStart=/opt/kafka/bin/kafka-server-start.sh /opt/kafka/config/server.properties
ExecStop=/opt/kafka/bin/kafka-server-stop.sh
Restart=on-abnormal
User=kafka
Group=kafka

[Install]
WantedBy=multi-user.target
EOF

# 5. Kafka 사용자 생성
echo "🔐 Kafka 사용자 생성..."
sudo useradd kafka -m
sudo usermod -aG sudo kafka
sudo chown -R kafka:kafka /opt/kafka

# 6. 시스템 서비스 등록 및 시작
echo "🚀 Kafka 서비스 시작..."
sudo systemctl daemon-reload
sudo systemctl enable zookeeper
sudo systemctl enable kafka
sudo systemctl start zookeeper
sleep 5
sudo systemctl start kafka

# 7. Python Kafka 라이브러리 설치
echo "🐍 Python Kafka 라이브러리 설치..."
pip install kafka-python confluent-kafka

# 8. 서비스 상태 확인
echo "✅ 서비스 상태 확인..."
sudo systemctl status zookeeper --no-pager
sudo systemctl status kafka --no-pager

# 9. Project Aria 전용 토픽 생성
echo "📂 Project Aria 토픽 생성..."
/opt/kafka/bin/kafka-topics.sh --create --topic vrs-raw-stream --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
/opt/kafka/bin/kafka-topics.sh --create --topic aria-imu-real-time --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
/opt/kafka/bin/kafka-topics.sh --create --topic aria-rgb-real-time --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
/opt/kafka/bin/kafka-topics.sh --create --topic aria-slam-real-time --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
/opt/kafka/bin/kafka-topics.sh --create --topic aria-sensor-fusion --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
/opt/kafka/bin/kafka-topics.sh --create --topic aria-analytics-real-time --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1

# 10. 토픽 목록 확인
echo "📋 생성된 토픽 목록:"
/opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# 11. 테스트 메시지 전송
echo "🧪 테스트 메시지 전송..."
echo "Test message from Project Aria setup" | /opt/kafka/bin/kafka-console-producer.sh --topic vrs-raw-stream --bootstrap-server localhost:9092

echo ""
echo "🎉 =================================="
echo "🎉 Kafka 설정 완료!"
echo "🎉 =================================="
echo ""
echo "📍 접속 정보:"
echo "   - Zookeeper: localhost:2181"
echo "   - Kafka Broker: localhost:9092"
echo ""
echo "🔧 관리 명령어:"
echo "   sudo systemctl start/stop/restart zookeeper"
echo "   sudo systemctl start/stop/restart kafka"
echo "   sudo systemctl status zookeeper"
echo "   sudo systemctl status kafka"
echo ""
echo "📂 주요 토픽:"
echo "   - vrs-raw-stream: VRS 원본 데이터"
echo "   - aria-imu-real-time: IMU 실시간 데이터" 
echo "   - aria-rgb-real-time: RGB 카메라 스트림"
echo "   - aria-slam-real-time: SLAM 카메라 스트림"
echo ""
echo "🔥 이제 Django에서 Kafka Producer/Consumer를 사용할 수 있습니다!"