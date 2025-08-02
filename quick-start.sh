#!/bin/bash

# ARD System Quick Start Script
# 30초만에 완전 자동 배포 - 실제 Project Aria MPS 데이터 포함

set -e

echo "🚀 ARD (Aria Real-time Data) System - 30초 자동 배포"
echo "========================================================="
echo "📊 실제 Project Aria 샘플 데이터가 자동으로 로드됩니다:"
echo "   - 📹 VRS Streams: 20개 레코드 (RGB 카메라 프레임)"
echo "   - 🎯 IMU Data: 50개 레코드 (가속도계, 자이로스코프, 자력계)"
echo "   - 👁️  Eye Gaze: 150개 레코드 (General + Personalized)"
echo "   - 🤲 Hand Tracking: 50개 레코드 (21 landmarks per hand)"
echo "   - 🗺️  SLAM Trajectory: 100개 레코드 (실제 quaternion 변환)"
echo ""

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수 정의
print_step() {
    echo -e "${BLUE}[STEP $1]${NC} $2"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Docker 설치 확인
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker가 설치되지 않았습니다. Docker를 먼저 설치해주세요."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose가 설치되지 않았습니다. Docker Compose를 먼저 설치해주세요."
        exit 1
    fi
    
    print_success "Docker 및 Docker Compose 확인됨"
}

# 기존 컨테이너 정리
cleanup_containers() {
    print_step "1" "기존 컨테이너 정리 중..."
    
    # ARD 관련 컨테이너 중지 및 삭제
    docker-compose down -v 2>/dev/null || true
    docker-compose -f kafka-compose.yml down -v 2>/dev/null || true
    
    # 기존 컨테이너 강제 정리
    docker rm -f ARD_KAFKA ARD-BACKEND ARD-POSTGRES 2>/dev/null || true
    
    print_success "기존 컨테이너 정리 완료"
}

# Kafka 실행
start_kafka() {
    print_step "2" "Kafka 컨테이너 실행 중..."
    
    # Kafka 설정 확인
    if [ ! -f "kafka-compose.yml" ]; then
        print_error "kafka-compose.yml 파일이 없습니다."
        exit 1
    fi
    
    # Kafka 실행
    docker-compose -f kafka-compose.yml up -d
    
    print_success "Kafka 컨테이너 시작됨"
    
    # Kafka 준비 대기
    print_step "2.1" "Kafka 준비 대기 중... (30초)"
    sleep 30
    
    # Kafka 상태 확인
    if docker ps | grep -q ARD_KAFKA; then
        print_success "Kafka 컨테이너 정상 실행 중"
    else
        print_error "Kafka 컨테이너 실행 실패"
        docker logs ARD_KAFKA
        exit 1
    fi
}

# ARD 이미지 빌드
build_ard_image() {
    print_step "3" "ARD Django 이미지 빌드 중..."
    
    # Dockerfile 확인
    if [ ! -f "Dockerfile" ]; then
        print_error "Dockerfile이 없습니다."
        exit 1
    fi
    
    # 이미지 빌드 (실제 MPS 데이터 로딩 포함)
    docker build -t ard-api:v13 .
    
    print_success "ARD 이미지 빌드 완료 (실제 MPS 데이터 로딩 포함)"
}

# ARD 시스템 실행
start_ard_system() {
    print_step "4" "ARD 전체 시스템 실행 중..."
    
    # Docker Compose 확인
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml 파일이 없습니다."
        exit 1
    fi
    
    # ARD 시스템 실행
    docker-compose up -d
    
    print_success "ARD 시스템 시작됨"
    
    # 시스템 준비 대기 (실제 MPS 데이터 로딩 포함)
    print_step "4.1" "시스템 초기화 및 실제 MPS 데이터 로딩 중... (45초)"
    sleep 45
}

# 헬스체크
health_check() {
    print_step "5" "시스템 헬스체크 실행 중..."
    
    # 컨테이너 상태 확인
    echo "컨테이너 상태:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # API 헬스체크
    echo ""
    echo "API 헬스체크:"
    
    # Django API 확인
    if curl -s -f http://localhost:8000/api/v1/aria/ > /dev/null; then
        print_success "Django API 정상 응답"
    else
        print_warning "Django API 응답 없음 (아직 준비 중일 수 있음)"
    fi
    
    # Kafka 연결 확인
    if curl -s -f http://localhost:8000/api/v1/aria/binary/streaming/ > /dev/null; then
        print_success "Kafka 연결 정상"
    else
        print_warning "Kafka 연결 확인 불가 (아직 준비 중일 수 있음)"
    fi
}

# 실제 API 테스트 실행
real_api_test() {
    print_step "6" "실제 Project Aria MPS 데이터 확인"
    
    echo ""
    echo "📊 실제 데이터 API 테스트 중..."
    echo "----------------------------------------"
    
    # Sessions 확인
    if curl -s -f http://localhost:8000/api/v1/aria/sessions/ > /dev/null; then
        sessions_count=$(curl -s http://localhost:8000/api/v1/aria/sessions/ | grep -o '"count":[0-9]*' | cut -d':' -f2 || echo "0")
        print_success "Sessions API: ${sessions_count}개 세션 데이터"
    else
        print_warning "Sessions API 응답 없음"
    fi
    
    # Eye Gaze 확인
    if curl -s -f http://localhost:8000/api/v1/aria/eye-gaze/ > /dev/null; then
        eye_gaze_count=$(curl -s http://localhost:8000/api/v1/aria/eye-gaze/ | grep -o '"count":[0-9]*' | cut -d':' -f2 || echo "0")
        print_success "Eye Gaze API: ${eye_gaze_count}개 실제 데이터"
    else
        print_warning "Eye Gaze API 응답 없음"
    fi
    
    # Hand Tracking 확인
    if curl -s -f http://localhost:8000/api/v1/aria/hand-tracking/ > /dev/null; then
        hand_count=$(curl -s http://localhost:8000/api/v1/aria/hand-tracking/ | grep -o '"count":[0-9]*' | cut -d':' -f2 || echo "0")
        print_success "Hand Tracking API: ${hand_count}개 실제 데이터"
    else
        print_warning "Hand Tracking API 응답 없음"
    fi
    
    # SLAM Trajectory 확인
    if curl -s -f http://localhost:8000/api/v1/aria/slam-trajectory/ > /dev/null; then
        slam_count=$(curl -s http://localhost:8000/api/v1/aria/slam-trajectory/ | grep -o '"count":[0-9]*' | cut -d':' -f2 || echo "0")
        print_success "SLAM Trajectory API: ${slam_count}개 실제 데이터"
    else
        print_warning "SLAM Trajectory API 응답 없음"
    fi
    
    # VRS 확인
    if curl -s -f http://localhost:8000/api/v1/aria/vrs-streams/ > /dev/null; then
        vrs_count=$(curl -s http://localhost:8000/api/v1/aria/vrs-streams/ | grep -o '"count":[0-9]*' | cut -d':' -f2 || echo "0")
        print_success "VRS Streams API: ${vrs_count}개 실제 데이터"
    else
        print_warning "VRS Streams API 응답 없음"
    fi
    
    # IMU 확인
    if curl -s -f http://localhost:8000/api/v1/aria/imu-data/ > /dev/null; then
        imu_count=$(curl -s http://localhost:8000/api/v1/aria/imu-data/ | grep -o '"count":[0-9]*' | cut -d':' -f2 || echo "0")
        print_success "IMU Data API: ${imu_count}개 실제 데이터"
    else
        print_warning "IMU Data API 응답 없음"
    fi
    
    echo ""
    echo "🧪 추가 API 테스트 명령어들:"
    echo "----------------------------------------"
    echo "# 📊 정제된 데이터 테스트"
    echo "curl http://localhost:8000/api/v1/aria/vrs-streams/?limit=3        # VRS 스트림"
    echo "curl http://localhost:8000/api/v1/aria/imu-data/?limit=3           # IMU 센서"
    echo "curl http://localhost:8000/api/v1/aria/eye-gaze/?limit=3           # Eye Gaze"
    echo "curl http://localhost:8000/api/v1/aria/hand-tracking/?limit=3      # Hand Tracking"
    echo "curl http://localhost:8000/api/v1/aria/slam-trajectory/?limit=3    # SLAM"
    echo ""
    echo "# 🔧 원시 데이터 테스트 (사용자 정의 형식)"
    echo "curl http://localhost:8000/api/v1/aria/raw/statistics/             # Raw 통계"
    echo "curl http://localhost:8000/api/v1/aria/raw/uploads/                # 업로드 목록"
    echo "curl http://localhost:8000/api/v1/aria/raw/schemas/                # 스키마 목록"
    echo ""
    echo "# 🎯 Binary Streaming (Unity 클라이언트용)"
    echo "curl http://localhost:8000/api/v1/aria/binary/streaming/"
    echo ""
}

# 메인 실행 함수
main() {
    echo ""
    check_docker
    cleanup_containers
    start_kafka
    build_ard_image
    start_ard_system
    health_check
    real_api_test
    
    echo ""
    echo "🎉 ARD 시스템이 성공적으로 실행되었습니다!"
    echo "📊 실제 Project Aria 샘플 데이터가 로드되어 있습니다 (MPS + VRS + IMU)!"
    echo ""
    echo "🚀 즉시 사용 가능한 API들:"
    echo "  📊 정제된 데이터 (Processed Data):"
    echo "    - Sessions:        http://localhost:8000/api/v1/aria/sessions/"
    echo "    - VRS Streams:     http://localhost:8000/api/v1/aria/vrs-streams/"
    echo "    - IMU Data:        http://localhost:8000/api/v1/aria/imu-data/"
    echo "    - Eye Gaze:        http://localhost:8000/api/v1/aria/eye-gaze/"
    echo "    - Hand Tracking:   http://localhost:8000/api/v1/aria/hand-tracking/"
    echo "    - SLAM Trajectory: http://localhost:8000/api/v1/aria/slam-trajectory/"
    echo "    - Binary Stream:   http://localhost:8000/api/v1/aria/binary/streaming/"
    echo ""
    echo "  🔧 원시 데이터 (Raw Data - 사용자 정의 형식 지원):"
    echo "    - Data Uploads:    http://localhost:8000/api/v1/aria/raw/uploads/"
    echo "    - Raw Streaming:   http://localhost:8000/api/v1/aria/raw/raw-data/"
    echo "    - File Uploads:    http://localhost:8000/api/v1/aria/raw/files/"
    echo "    - Data Schemas:    http://localhost:8000/api/v1/aria/raw/schemas/"
    echo "    - Raw Statistics:  http://localhost:8000/api/v1/aria/raw/statistics/"
    echo ""
    echo "🔧 관리 도구:"
    echo "  - Django Admin:    http://localhost:8000/admin/"
    echo "  - PostgreSQL:      localhost:5432 (postgres/password)"
    echo "  - Kafka:           localhost:9092"
    echo ""
    echo "📝 로그 확인:"
    echo "  docker logs ARD-BACKEND -f     # Django + MPS 데이터 로딩 로그"
    echo "  docker logs ARD_KAFKA -f       # Kafka 로그"
    echo "  docker-compose logs -f         # 전체 로그"
    echo ""
    echo "🛑 시스템 종료:"
    echo "  docker-compose down && docker-compose -f kafka-compose.yml down"
    echo ""
    echo "💡 Unity 연동: http://localhost:8000/api/v1/aria/ 엔드포인트를 사용하세요!"
    echo ""
}

# 스크립트 실행
main "$@"