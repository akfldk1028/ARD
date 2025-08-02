# Project Aria Data Fields Reference

Meta Project Aria AR 안경에서 생성되는 실제 센서 데이터 구조와 Django API 변환 과정 참조 가이드

## 📊 데이터 변환 파이프라인 개요

```
Project Aria Device → VRS Files + MPS Processing → CSV Files → Django API → JSON Response
```

---

## 🎯 SLAM Trajectory Data

### CSV 원본 구조 (`closed_loop_trajectory.csv`)
```csv
graph_uid,tracking_timestamp_us,utc_timestamp_ns,tx_world_device,ty_world_device,tz_world_device,qx_world_device,qy_world_device,qz_world_device,qw_world_device,...
31ebacab-fcac-b027-908f-880f29dc7b64,1763475767,1694815246654918709,0.962793,0.596484,0.031522,0.575435558,0.461931317,-0.517368036,0.433386309,...
```

### 주요 필드 설명
- **`tx_world_device`, `ty_world_device`, `tz_world_device`**: 월드 좌표계에서의 디바이스 위치 (미터 단위)
- **`qx_world_device`, `qy_world_device`, `qz_world_device`, `qw_world_device`**: 회전을 나타내는 쿼터니온
- **`tracking_timestamp_us`**: 추적 타임스탬프 (마이크로초)
- **`quality_score`**: SLAM 품질 점수 (0.0-1.0)

### Django API 변환 결과
```json
{
  "position_x": 0.962793,
  "position_y": 0.596484,
  "position_z": 0.031522,
  "transform_matrix": [
    [-0.035287, -0.621576, -0.782559, 0.234595],
    [-0.114660, -0.775358, 0.621026, -1.035831],
    [-0.992778, 0.111643, -0.043910, -0.005809],
    [0.0, 0.0, 0.0, 1.0]
  ],
  "device_timestamp_ns": 1763475767000
}
```

**변환 과정:**
1. **위치 추출**: `tx,ty,tz` → `position_x,y,z`
2. **SE3 변환**: 쿼터니온 + 위치 → 4x4 변환 행렬
3. **타임스탬프**: 마이크로초 → 나노초 변환

---

## 👁️ Eye Gaze Data

### CSV 원본 구조 (`general_eye_gaze.csv`)
```csv
tracking_timestamp_us,left_yaw_rads_cpf,right_yaw_rads_cpf,pitch_rads_cpf,depth_m,left_yaw_low_rads_cpf,right_yaw_low_rads_cpf,pitch_low_rads_cpf,...
1762509261,-0.047912582755088806,0.0936531126499176,-0.21153444051742554,0.4542842905544307,-0.06635325402021408,0.0741325095295906,-0.2356899827718735,...
```

### 주요 필드 설명
- **`left_yaw_rads_cpf`, `right_yaw_rads_cpf`**: 좌우 눈의 수평 시선 각도 (라디안)
- **`pitch_rads_cpf`**: 수직 시선 각도 (라디안)
- **`depth_m`**: 시선 집중 거리 (미터)
- **`tracking_timestamp_us`**: 추적 타임스탬프 (마이크로초)

### Django API 변환 결과
```json
{
  "yaw": -0.533633,
  "pitch": -14.676973,
  "depth_m": 0.323291,
  "gaze_type": "general",
  "gaze_direction": {
    "x": -0.512,
    "y": -0.994,
    "z": 0.858
  },
  "device_timestamp_ns": 1762509261000
}
```

**변환 과정:**
1. **시선 방향 계산**: 좌우 눈 yaw 평균값 사용
2. **구면 좌표**: Yaw/Pitch → 3D 방향 벡터 변환
3. **단위 일관성**: 라디안 유지, 거리는 미터 단위

---

## ✋ Hand Tracking Data

### CSV 원본 구조 (`hand_tracking_results.csv`)
```csv
tracking_timestamp_us,left_tracking_confidence,tx_left_landmark_0_device,ty_left_landmark_0_device,tz_left_landmark_0_device,tx_left_landmark_1_device,...
1762609162,0.999297,0.0645505,-0.248817,0.250956,0.0615564,-0.305363,0.297861,0.0704205,-0.321074,0.315893,...
```

### 주요 필드 설명
- **`tx_left_landmark_N_device`, `ty_left_landmark_N_device`, `tz_left_landmark_N_device`**: N번째 랜드마크의 3D 좌표 (미터)
- **`left_tracking_confidence`, `right_tracking_confidence`**: 추적 신뢰도 (0.0-1.0)
- **`nx_left_palm_device`, `ny_left_palm_device`, `nz_left_palm_device`**: 손바닥 법선 벡터
- **21개 랜드마크**: 손목(0) + 엄지(1-4) + 검지(5-8) + 중지(9-12) + 약지(13-16) + 새끼(17-20)

### Django API 변환 결과
```json
{
  "left_hand_landmarks": [
    {"x": 0.0645505, "y": -0.248817, "z": 0.250956, "id": 0},
    {"x": 0.0615564, "y": -0.305363, "z": 0.297861, "id": 1},
    ...
  ],
  "left_hand_wrist_normal": [-0.0223908, -0.551633, -0.833786],
  "left_hand_palm_normal": [0.0766851, -0.523496, -0.84857],
  "has_left_hand": true,
  "device_timestamp_ns": 1762609162000
}
```

**변환 과정:**
1. **랜드마크 구조화**: 21개 좌표 → ID와 함께 JSON 배열
2. **신뢰도 기반 필터링**: confidence < 0.5 시 null 처리
3. **법선 벡터**: 손목/손바닥 방향 벡터 추출

---

## 🔄 IMU Data (추가)

### VRS 파일에서 직접 추출
- **가속도**: `accel_x`, `accel_y`, `accel_z` (m/s²)  
- **자이로스코프**: `gyro_x`, `gyro_y`, `gyro_z` (rad/s)
- **온도**: `temperature_c` (섭씨)
- **샘플링**: ~1000Hz → 100Hz로 다운샘플링

---

## 📈 데이터 품질 및 특징

### SLAM Trajectory
- **정확도**: 센티미터 단위 위치 추적
- **커버리지**: 실내/실외 환경에서 연속 추적
- **품질 점수**: 대부분 0.9+ 높은 신뢰도

### Eye Gaze  
- **범위**: Yaw ±180°, Pitch ±90°
- **깊이**: 0.3m ~ 5m+ 가변 거리
- **정확도**: 일반 모드 vs 개인화 모드

### Hand Tracking
- **감지율**: 손이 시야에 있을 때 99%+ 신뢰도
- **랜드마크**: MediaPipe 호환 21포인트 구조
- **좌표계**: 디바이스 중심 3D 좌표

---

## 🛠️ 기술적 구현 세부사항

### 데이터 파이프라인
1. **VRS 스트림**: 원시 센서 데이터 (RGB, SLAM, IMU, Eye tracking)
2. **MPS 처리**: Meta의 기계 지각 서비스로 고급 데이터 추출
3. **CSV 출력**: 분석 가능한 구조화된 데이터
4. **Django 모델**: PostgreSQL에 최적화된 스키마
5. **REST API**: DRF로 필터링/페이지네이션 지원

### 좌표계 정보
- **World 좌표계**: SLAM이 구축하는 글로벌 좌표
- **Device 좌표계**: AR 안경 중심의 로컬 좌표  
- **CPF (Central Pupil Frame)**: 시선 추적용 눈 중앙 좌표계

### 성능 최적화
- **샘플링**: 고주파 데이터의 다운샘플링
- **인덱싱**: 타임스탬프 기반 시계열 쿼리 최적화
- **압축**: 벡터 데이터의 JSON 압축 저장

---

## 📚 참고 문서

- **Project Aria Tools**: https://facebookresearch.github.io/projectaria_tools/
- **MPS Documentation**: Meta Machine Perception Services 공식 문서
- **VRS Format**: Virtual Reality Service 파일 포맷 명세
- **MediaPipe Hands**: 21-point hand landmark 모델

---

*Generated: 2025-07-30*  
*ARD System v1.0 - Real-time AR Data Processing*