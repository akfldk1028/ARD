#!/bin/bash

# ARD API 테스트 스크립트
# 모든 주요 API 엔드포인트를 자동으로 테스트합니다

set -e

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 설정
API_BASE="http://localhost:8000"
TIMEOUT=10

echo -e "${BLUE}🧪 ARD API 테스트 시작${NC}"
echo "================================="
echo ""

# 함수 정의
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3
    local data=$4
    
    echo -e "${CYAN}Testing:${NC} $description"
    echo -e "${YELLOW}$method${NC} $API_BASE$endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$API_BASE$endpoint" || echo -e "\n000")
    else
        response=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT \
            -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_BASE$endpoint" || echo -e "\n000")
    fi
    
    # HTTP 상태 코드 추출
    http_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | sed '$d')
    
    # 결과 표시
    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        echo -e "${GREEN}✅ SUCCESS ($http_code)${NC}"
        
        # JSON 형식으로 출력 (가능한 경우)
        if echo "$response_body" | python3 -m json.tool >/dev/null 2>&1; then
            echo "$response_body" | python3 -m json.tool | head -20
            if [ $(echo "$response_body" | wc -l) -gt 20 ]; then
                echo "... (truncated)"
            fi
        else
            echo "$response_body" | head -10
        fi
    else
        echo -e "${RED}❌ FAILED ($http_code)${NC}"
        echo "$response_body" | head -5
    fi
    
    echo ""
    echo "-----------------------------------"
    echo ""
}

# 시스템 상태 확인
echo -e "${BLUE}📊 시스템 상태 확인${NC}"
echo ""

# Docker 컨테이너 상태
echo "Docker 컨테이너 상태:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(ARD_KAFKA|ARD-BACKEND|ARD-POSTGRES)" || echo "ARD 컨테이너가 실행되지 않았습니다."
echo ""

# API 테스트 시작
echo -e "${BLUE}🚀 API 엔드포인트 테스트${NC}"
echo ""

# 1. 기본 API 엔드포인트들
test_endpoint "GET" "/api/v1/aria/" "API 루트 - 사용 가능한 엔드포인트 목록"

test_endpoint "GET" "/api/v1/aria/sessions/" "Aria 세션 목록 조회"

test_endpoint "GET" "/api/v1/aria/vrs-streams/" "VRS 스트림 데이터 조회"

test_endpoint "GET" "/api/v1/aria/eye-gaze/" "Eye Gaze 데이터 조회"

test_endpoint "GET" "/api/v1/aria/hand-tracking/" "Hand Tracking 데이터 조회"

test_endpoint "GET" "/api/v1/aria/slam-trajectory/" "SLAM Trajectory 데이터 조회"

test_endpoint "GET" "/api/v1/aria/kafka-status/" "Kafka Consumer 상태 조회"

# 2. 바이너리 스트리밍 API
echo -e "${BLUE}🔄 바이너리 스트리밍 API 테스트${NC}"
echo ""

test_endpoint "GET" "/api/v1/aria/binary/streaming/" "바이너리 스트리밍 서비스 상태"

test_endpoint "GET" "/api/v1/aria/binary/registry/" "바이너리 프레임 레지스트리 조회"

test_endpoint "GET" "/api/v1/aria/binary/metadata/" "바이너리 프레임 메타데이터 조회"

# 3. 테스트 메시지 전송
echo -e "${BLUE}📤 테스트 메시지 전송${NC}"
echo ""

test_data='{"session_id": "api-test-session", "test_type": "binary_frame"}'
test_endpoint "POST" "/api/v1/aria/binary/test-message/" "테스트 바이너리 프레임 전송" "$test_data"

# 4. 전송 후 데이터 확인
echo -e "${BLUE}📥 전송된 데이터 확인${NC}"
echo ""

sleep 2  # 데이터 처리 대기

test_endpoint "GET" "/api/v1/aria/binary/registry/" "바이너리 레지스트리 - 전송된 데이터 확인"

test_endpoint "GET" "/api/v1/aria/binary/metadata/" "바이너리 메타데이터 - 전송된 데이터 확인"

# 5. Kafka 토픽 모니터링 (선택사항)
echo -e "${BLUE}📊 Kafka 토픽 상태 (마지막 메시지 확인)${NC}"
echo ""

echo "Kafka 토픽 목록:"
docker exec ARD_KAFKA kafka-topics.sh --list --bootstrap-server localhost:9092 2>/dev/null || echo "Kafka 연결 실패"
echo ""

echo "VRS 메타데이터 토픽 메시지 수:"
docker exec ARD_KAFKA kafka-log-dirs.sh --bootstrap-server localhost:9092 --describe --json 2>/dev/null | grep -o '"size":[0-9]*' | head -3 || echo "토픽 정보 조회 실패"
echo ""

# 6. 성능 테스트 (간단한)
echo -e "${BLUE}⚡ 간단한 성능 테스트${NC}"
echo ""

echo "연속 5회 바이너리 프레임 전송 테스트:"
for i in {1..5}; do
    start_time=$(date +%s%N)
    
    response=$(curl -s -w "%{http_code}" --max-time 10 \
        -X POST \
        -H "Content-Type: application/json" \
        -d "{\"session_id\": \"perf-test-$i\", \"test_type\": \"binary_frame\"}" \
        "$API_BASE/api/v1/aria/binary/test-message/")
    
    end_time=$(date +%s%N)
    duration=$(($(($end_time - $start_time)) / 1000000))  # 밀리초 변환
    
    http_code=$(echo "$response" | tail -c 4)
    
    if [ "$http_code" = "200" ]; then
        echo -e "  $i. ${GREEN}✅ SUCCESS${NC} (${duration}ms)"
    else
        echo -e "  $i. ${RED}❌ FAILED${NC} ($http_code) (${duration}ms)"
    fi
done
echo ""

# 7. 요약 리포트
echo -e "${BLUE}📋 테스트 요약${NC}"
echo "================================="
echo ""
echo "🎯 주요 엔드포인트:"
echo "  • API 루트:           $API_BASE/api/v1/aria/"
echo "  • 바이너리 스트리밍:    $API_BASE/api/v1/aria/binary/streaming/"
echo "  • 테스트 메시지:       $API_BASE/api/v1/aria/binary/test-message/"
echo "  • Django Admin:       $API_BASE/admin/"
echo ""
echo "🔧 개발 도구:"
echo "  • 실시간 로그:         docker logs ARD-BACKEND -f"
echo "  • Kafka 로그:         docker logs ARD_KAFKA -f"
echo "  • DB 접속:           docker exec -it ARD-POSTGRES psql -U postgres -d ard_db"
echo ""
echo "📚 문서:"
echo "  • README.md:          빠른 시작 가이드"
echo "  • README/00_INDEX.md: 순차적 학습 가이드 (11개 문서)"
echo ""
echo -e "${GREEN}🎉 API 테스트 완료!${NC}"

# Unity 클라이언트 예시 (선택사항)
if [ "$1" = "--unity" ]; then
    echo ""
    echo -e "${BLUE}🎮 Unity 클라이언트 연동 가이드${NC}"
    echo "================================="
    echo ""
    echo "WebSocket 연결:"
    echo "  URL: ws://localhost:8000/ws/aria/stream/your-session-id/"
    echo ""
    echo "HTTP API 호출:"
    echo "  GET $API_BASE/api/v1/aria/vrs-streams/"
    echo "  GET $API_BASE/api/v1/aria/eye-gaze/"
    echo "  GET $API_BASE/api/v1/aria/hand-tracking/"
    echo ""
    echo "Unity C# 코드 예시는 README/ARDUnityClient.cs 참조"
fi