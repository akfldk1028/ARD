#!/bin/bash

# ARD Docker 실행 스크립트

set -e

echo "🐳 ARD Docker 환경 설정 및 실행"
echo "=================================="

# 현재 디렉토리 확인
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml 파일을 찾을 수 없습니다."
    echo "   ARD 프로젝트 루트 디렉토리에서 실행해주세요."
    exit 1
fi

# Docker 및 Docker Compose 설치 확인
if ! command -v docker &> /dev/null; then
    echo "❌ Docker가 설치되지 않았습니다."
    echo "   https://docs.docker.com/get-docker/ 에서 Docker를 설치해주세요."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose가 설치되지 않았습니다."
    exit 1
fi

# 선택지 메뉴
echo "원하는 작업을 선택하세요:"
echo "1) 전체 서비스 시작 (Django + PostgreSQL + Redis)"
echo "2) Django만 시작 (외부 DB 사용)"
echo "3) 서비스 중지"
echo "4) 로그 확인"
echo "5) 컨테이너 상태 확인"
echo "6) Unity API 테스트 실행"
echo "7) 전체 정리 (컨테이너 + 볼륨 삭제)"

read -p "선택 (1-7): " choice

case $choice in
    1)
        echo "🚀 전체 서비스 시작..."
        
        # 이미지 빌드
        echo "📦 Docker 이미지 빌드 중..."
        docker-compose build django-ard
        
        # 서비스 시작
        echo "▶️ 서비스 시작 중..."
        docker-compose up -d
        
        # 서비스 상태 확인
        echo "⏳ 서비스 시작 대기 중..."
        sleep 10
        
        echo "📊 서비스 상태:"
        docker-compose ps
        
        echo "🌐 서비스 접근 URL:"
        echo "  - Django API: http://localhost:8000"
        echo "  - Django Admin: http://localhost:8000/admin/"
        echo "  - DRF API Browser: http://localhost:8000/api/streams/api/"
        echo "  - PostgreSQL: localhost:5432"
        echo "  - Redis: localhost:6379"
        
        echo "📝 로그 확인: docker-compose logs -f django-ard"
        ;;
        
    2)
        echo "🚀 Django 서비스만 시작..."
        
        # Django 이미지 빌드
        docker-compose build django-ard
        
        # Django만 시작
        docker-compose up -d django-ard
        
        echo "📊 Django 서비스 상태:"
        docker-compose ps django-ard
        
        echo "🌐 Django API: http://localhost:8000"
        ;;
        
    3)
        echo "⏹️ 서비스 중지 중..."
        docker-compose down
        echo "✅ 서비스가 중지되었습니다."
        ;;
        
    4)
        echo "📋 서비스 로그:"
        docker-compose logs -f
        ;;
        
    5)
        echo "📊 컨테이너 상태:"
        docker-compose ps
        
        echo -e "\n🔍 상세 정보:"
        docker-compose exec django-ard python ARD/manage.py check || echo "Django 서비스가 실행 중이지 않습니다."
        ;;
        
    6)
        echo "🎮 Unity API 테스트 실행..."
        
        # Python 가상환경에서 테스트 실행
        if [ -d "myenv" ]; then
            echo "📦 가상환경 활성화 중..."
            source myenv/bin/activate
            python unity_api_test.py http://localhost:8000
        else
            echo "📦 시스템 Python으로 테스트 실행..."
            python3 unity_api_test.py http://localhost:8000
        fi
        ;;
        
    7)
        echo "🗑️ 전체 정리 중..."
        
        read -p "⚠️  모든 컨테이너와 볼륨을 삭제합니다. 계속하시겠습니까? (y/N): " confirm
        
        if [[ $confirm =~ ^[Yy]$ ]]; then
            docker-compose down -v --remove-orphans
            docker system prune -f
            echo "✅ 전체 정리가 완료되었습니다."
        else
            echo "❌ 정리가 취소되었습니다."
        fi
        ;;
        
    *)
        echo "❌ 잘못된 선택입니다. 1-7 중에서 선택해주세요."
        exit 1
        ;;
esac

echo -e "\n🎉 작업이 완료되었습니다!"