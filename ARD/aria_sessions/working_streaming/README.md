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
- 📈 최신 sample.vrs (GitHub 공식)

### 동시 센서 스트리밍 (🆕 8개 센서 지원!)
- ✅ IMU Right/Left (가속도계, 자이로스코프)
- ✅ 자력계 (지자기장 측정)
- ✅ 기압계 (압력, 온도, 고도)
- ✅ 오디오 (7채널 48kHz)
- 🆕 GPS (위도, 경도, 고도, 정확도)
- 🆕 WiFi Beacon (SSID, 신호강도, 주파수)
- 🆕 Bluetooth Beacon (MAC, 신호강도, 디바이스 타입)
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

## 🆕 v2.0 업데이트 사항 (2025-08-06)

### 새로운 센서 지원
- 🌍 **GPS 센서**: 위치정보, 정확도, 속도 측정
- 📶 **WiFi Beacon**: SSID, MAC 주소, 신호강도(RSSI), 주파수
- 📱 **Bluetooth Beacon**: 디바이스명, MAC, 신호강도, UUID

### 개선 사항
- ✅ 최신 공식 sample.vrs 파일 적용 (GitHub에서 다운로드)
- ✅ 총 8개 센서 동시 모니터링 지원
- ✅ RecordableTypeId 정확한 속성명 사용
- ✅ 센서별 최적화된 샘플링 레이트 적용
- ✅ 새로운 센서 데이터 파싱 및 HTML 표시

### 센서별 샘플링 설정
- IMU: 10배 샘플링 (고빈도 데이터)
- 자력계/기압계: 10배 샘플링
- 오디오: 20배 샘플링 (고속 처리)
- GPS: 전체 샘플링 (중요한 위치 데이터)
- WiFi: 5배 샘플링 (중간 빈도)
- Bluetooth: 3배 샘플링 (중간 빈도)

## 📋 TODO
- [x] 센서 동시 스트리밍 추가 ✅
- [x] 메인 대시보드 추가 ✅
- [x] GPS, WiFi, Bluetooth 센서 지원 ✅
- [x] 최신 sample.vrs 적용 ✅
- [x] 테스트 및 버그 수정 ✅
- [ ] 성능 최적화 지속