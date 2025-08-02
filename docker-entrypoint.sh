#!/bin/bash

# Django Docker 시작 스크립트

set -e

echo "Starting Django ARD Application..."
echo "Current working directory: $(pwd)"
echo "Files in /app:"
ls -la /app/
echo "Files in /app/ARD:"
ls -la /app/ARD/ || echo "ARD directory not found"

# 데이터베이스 마이그레이션 대기  
DB_ENGINE=${DB_ENGINE:-django.db.backends.postgresql}

if [[ "$DB_ENGINE" == *"sqlite"* ]]; then
    echo "Using SQLite database - skipping connection check"
else
    echo "Waiting for PostgreSQL database to be ready..."
    until python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'postgres'),
        port=int(os.getenv('DB_PORT', 5432)),
        user=os.getenv('DB_USER', 'postgres'), 
        password=os.getenv('DB_PASSWORD', 'password'),
        database=os.getenv('DB_NAME', 'ard_db')
    )
    conn.close()
    exit(0)
except Exception as e:
    print(f'DB connection failed: {e}')
    exit(1)
" 2>/dev/null; do
        echo "Database is unavailable - sleeping for 2 seconds"
        sleep 2
    done
    echo "Database is ready!"
fi
echo "Running Django migrations..."
cd /app/ARD && python manage.py migrate --no-input

echo "Collecting static files..."
cd /app/ARD && python manage.py collectstatic --no-input || true

echo "📥 Downloading MPS sample data..."
cd /app/ARD && python manage.py download_sample_data || echo "⚠️ Sample data download failed - continuing without sample data"

echo "📊 Loading sample data into database..."
cd /app/ARD && python manage.py load_real_sample_data --data-path data/mps_samples || echo "⚠️ Sample data loading failed - check if data exists"

echo "Django setup completed successfully!"

echo "Django setup completed successfully! Starting Django server..."

# Kafka Consumer는 Raw 데이터 테이블 생성 후 수동으로 시작
echo "Kafka Consumer startup skipped - start manually after Raw tables are created"
# cd /app/ARD && python manage.py start_kafka_consumer --bootstrap-servers ${KAFKA_BOOTSTRAP_SERVERS:-host.docker.internal:9092} &

echo "Django server and Kafka consumer starting..."

# 메인 프로세스 실행
exec "$@"