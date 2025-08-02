# Django ARD API Docker Image
FROM python:3.10-slim

# 환경 변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    gcc \
    g++ \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY ARD/ /app/ARD/
COPY CLAUDE.md /app/

# Django 정적 파일 수집
WORKDIR /app/ARD
RUN python manage.py collectstatic --noinput || true

# Django 포트 노출
EXPOSE 8000

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/aria/api/sessions/ || exit 1

# 시작 스크립트 생성
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# 시작 명령
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "/app/ARD/manage.py", "runserver", "0.0.0.0:8000"]