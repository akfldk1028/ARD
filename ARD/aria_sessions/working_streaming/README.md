# 🔥 Working Streaming Components

이 폴더에는 **실제로 작동하는 스트리밍 구성 요소**들이 정리되어 있습니다.

## ✅ 작동 확인된 파일들

### 1. 🏆 메인 대시보드 (통합)
- `main_dashboard.py` - 모든 기능 통합 대시보드
- URL: `/api/v1/aria-sessions/main-dashboard/`

### 2. 📷 동시 4카메라 스트리밍
- `concurrent_streaming_views.py` - 동시 4카메라 스트리밍 (공식 Observer 패턴)
- URL: `/api/v1/aria-sessions/concurrent-streaming-page/`

### 3. 🧭 동시 센서 스트리밍 (NEW!)
- `concurrent_sensor_streaming.py` - 동시 센서 스트리밍 (공식 Observer 패턴)
- URL: `/api/v1/aria-sessions/concurrent-sensor-page/`

### 4. 핵심 모델 및 설정
- `models.py` - AriaStreamingSession 모델
- `urls.py` - URL 라우팅 설정
- `streaming_service.py` - 기본 스트리밍 서비스

### 5. 샘플 데이터
- `data/sample.vrs` - Project Aria 공식 샘플 데이터

## 🎯 주요 기능

### 동시 4카메라 스트리밍
- ✅ RGB 카메라
- ✅ SLAM Left 카메라  
- ✅ SLAM Right 카메라
- ✅ Eye Tracking 카메라
- ✅ 순환 재생 (무한 루프)
- ✅ 공식 Observer 패턴
- ✅ deliver_queued_sensor_data 사용

### 성능 최적화
- 🚀 10-100배 성능 향상
- 🔄 자동 순환 재생
- 📊 실시간 통계
- 🧵 멀티스레드 처리

### 동시 센서 스트리밍 (NEW!)
- ✅ IMU Right/Left (가속도계, 자이로스코프)
- ✅ 자력계 (지자기장 측정)
- ✅ 기압계 (압력, 온도, 고도)
- ✅ 오디오 (7채널 48kHz)
- ✅ 순환 재생 (무한 루프)
- ✅ 공식 Observer 패턴
- ✅ deliver_queued_sensor_data 사용

## 🚀 빠른 시작

### 메인 대시보드 접속
```
http://127.0.0.1:8000/api/v1/aria-sessions/main-dashboard/
```

### 개별 기능 접속
- 4카메라: `http://127.0.0.1:8000/api/v1/aria-sessions/concurrent-streaming-page/`
- 센서: `http://127.0.0.1:8000/api/v1/aria-sessions/concurrent-sensor-page/`

## 📋 TODO
- [x] 센서 동시 스트리밍 추가 ✅
- [x] 메인 대시보드 추가 ✅
- [ ] 테스트 코드 정리
- [ ] 불필요한 파일 제거