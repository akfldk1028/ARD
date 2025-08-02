# Project Aria 데이터 필드 완전 참조 가이드

## 📚 개요

Project Aria 시스템에서 생성되는 모든 데이터 타입과 필드에 대한 완전한 참조 문서입니다.

## 🎥 VRS (Video Recording Storage) 데이터

### VRS Stream 구조
VRS 파일은 Project Aria 안경에서 수집되는 원본 센서 데이터를 저장합니다.

## 🎯 Project Aria 하드웨어 센서 구조

**Project Aria 안경은 물리적으로 4개의 서로 다른 카메라 센서를 탑재**하고 있으며, 각각 다른 목적과 사양을 가집니다:

#### 📹 RGB 카메라 (Stream ID: "214-1") - **컬러 센서**
- **물리적 센서**: 고해상도 컬러 이미지 센서 (실제 RGB 센서)
- **해상도**: 1408x1408 픽셀 (정사각형)
- **용도**: 고화질 컬러 영상 녹화, AR 오버레이용
- **프레임 레이트**: ~30fps
- **픽셀 포맷**: **RGB24** (3채널 컬러)
- **데이터 특성**: 항상 컬러 데이터

#### 🔍 SLAM 카메라 (Stream ID: "1201-1", "1201-2") - **흑백 센서**
- **물리적 센서**: 2개의 흑백 이미지 센서 (스테레오 쌍)
- **해상도**: 640x480 픽셀 (VGA)
- **용도**: 공간 추적 및 SLAM 처리 (깊이 인식)
- **구성**: Left ("1201-1") + Right ("1201-2") 스테레오 비전
- **프레임 레이트**: ~30fps
- **픽셀 포맷**: **GRAY8** (1채널 흑백)
- **데이터 특성**: 항상 흑백 데이터 (컬러 정보 불필요)

#### 👁️ Eye Tracking 카메라 (Stream ID: "211-1") - **흑백 센서**
- **물리적 센서**: 저해상도 흑백 이미지 센서
- **해상도**: 320x240 픽셀 (QVGA)
- **용도**: 눈동자 추적용 (적외선 조명 사용)
- **프레임 레이트**: ~30fps
- **픽셀 포맷**: **GRAY8** (1채널 흑백)
- **데이터 특성**: 항상 흑백 데이터 (눈동자 윤곽 추적만 필요)

### 🔧 왜 이렇게 설계되었나?

1. **RGB 카메라**: 사용자가 보는 실제 세상을 컬러로 기록 → **컬러 센서 필수**
2. **SLAM 카메라**: 공간의 특징점과 깊이만 필요 → **흑백으로 충분, 처리 속도 빠름**
3. **Eye Tracking**: 눈동자 경계선만 감지 → **흑백으로 충분, 적외선 조명과 조합**

**즉, pixel_format은 Project Aria가 "마음대로" 정하는게 아니라, 각 센서의 물리적 특성과 용도에 따라 고정**되어 있습니다!

### VRS API 응답 필드 설명

#### 기본 정보 필드
| 필드명 | 타입 | 설명 | 예시 값 |
|--------|------|------|---------|
| `id` | Integer | Django 데이터베이스 고유 ID | 20 |
| `session` | Integer | 연결된 AriaSession ID (외래키) | 3 |
| `timestamp` | DateTime | API 저장 시간 (ISO 8601) | "2025-07-30T02:21:31.922862Z" |
| `kafka_offset` | BigInteger | Kafka 메시지 오프셋 (스트리밍 추적용) | 4 |

#### VRS 스트림 정보 필드
| 필드명 | 타입 | 설명 | 예시 값 |
|--------|------|------|---------|
| `device_timestamp_ns` | BigInteger | 장비 내부 나노초 타임스탬프 | 1762509394333332 |
| `stream_id` | String | 스트림 식별자 | "211-1" (Eye Tracking) |
| `stream_name` | String | 스트림 이름 | "camera-eye-tracking" |
| `frame_index` | Integer | 프레임 순서 번호 (0부터 시작) | 4 |
| `image_shape` | JSON Array | 이미지 크기 [높이, 너비, 채널] | [320, 240, 1] |
| `pixel_format` | String | 픽셀 데이터 포맷 | "GRAY8" (흑백), "RGB24" (컬러) |

#### 세션 정보 (Computed Field)
| 필드명 | 타입 | 설명 | 예시 값 |
|--------|------|------|---------|
| `session_info` | JSON Object | 연결된 세션 정보 | {"session_id": "real_mps_sample_001", "device_serial": "REAL_MPS_DEVICE"} |

### Stream ID 별 상세 설명

#### 📹 RGB 카메라 ("214-1")
```json
{
  "stream_id": "214-1",
  "stream_name": "camera-rgb", 
  "image_shape": [1408, 1408, 3],
  "pixel_format": "RGB24"
}
```
- **해상도**: 1408x1408 픽셀 (정사각형)
- **용도**: 고해상도 컬러 영상 녹화
- **채널**: 3 (RGB)
- **데이터 크기**: ~6MB/프레임

#### 🔍 SLAM 카메라 Left ("1201-1")
```json
{
  "stream_id": "1201-1",
  "stream_name": "camera-slam-left",
  "image_shape": [640, 480, 1], 
  "pixel_format": "GRAY8"
}
```
- **해상도**: 640x480 픽셀 (VGA)
- **용도**: 왼쪽 SLAM 카메라 (스테레오 비전)
- **채널**: 1 (흑백)
- **데이터 크기**: ~300KB/프레임

#### 🔍 SLAM 카메라 Right ("1201-2")
```json
{
  "stream_id": "1201-2", 
  "stream_name": "camera-slam-right",
  "image_shape": [640, 480, 1],
  "pixel_format": "GRAY8"
}
```
- **해상도**: 640x480 픽셀 (VGA)
- **용도**: 오른쪽 SLAM 카메라 (스테레오 비전)
- **채널**: 1 (흑백)
- **데이터 크기**: ~300KB/프레임

#### 👁️ Eye Tracking 카메라 ("211-1")
```json
{
  "stream_id": "211-1",
  "stream_name": "camera-eye-tracking",
  "image_shape": [320, 240, 1],
  "pixel_format": "GRAY8"
}
```
- **해상도**: 320x240 픽셀 (QVGA)  
- **용도**: 시선 추적 데이터 수집
- **채널**: 1 (흑백)
- **데이터 크기**: ~75KB/프레임

### VRS 데이터 활용 예시

#### Unity에서 VRS 스트림 분류
```csharp
public void ProcessVRSStream(VRSStreamData stream) {
    switch(stream.stream_id) {
        case "214-1":
            // RGB 영상 텍스처로 변환
            ProcessRGBFrame(stream.image_shape);
            break;
        case "1201-1":
        case "1201-2": 
            // SLAM 스테레오 처리
            ProcessSLAMFrame(stream);
            break;
        case "211-1":
            // Eye Tracking 보조 데이터
            ProcessEyeTrackingFrame(stream);
            break;
    }
}
```

#### API 쿼리 예시
```bash
# 특정 스트림만 조회
GET /api/streams/api/vrs-streams/?stream_id=214-1

# RGB 카메라만 조회  
GET /api/streams/api/vrs-streams/?stream_name=camera-rgb

# 최근 프레임만 조회 (페이징)
GET /api/streams/api/vrs-streams/?ordering=-frame_index&limit=10
```

---

## 🧠 MPS (Machine Perception Services) 데이터

MPS는 VRS 원본 데이터를 AI로 처리하여 의미 있는 정보를 추출합니다.

## 👁️ Eye Gaze 데이터

### 📄 General vs Personalized
- **General**: 일반적인 시선 추적 모델 (개인화 없음)
- **Personalized**: 개별 사용자에게 맞춤화된 시선 추적 모델

### General Eye Gaze 필드 (`general_eye_gaze.csv`)

| 필드명 | 타입 | 단위 | 설명 | 예시 값 |
|--------|------|------|------|---------|
| `tracking_timestamp_us` | Integer | 마이크로초 | MPS 처리 타임스탬프 | 1762509261 |
| `left_yaw_rads_cpf` | Float | 라디안 | 왼쪽 눈 요 각도 (좌우) | -0.047913 |
| `right_yaw_rads_cpf` | Float | 라디안 | 오른쪽 눈 요 각도 (좌우) | 0.093653 |
| `pitch_rads_cpf` | Float | 라디안 | 시선 피치 각도 (상하) | -0.211534 |
| `depth_m` | Float | 미터 | 시선 응시 깊이 | 0.454284 |
| `left_yaw_low_rads_cpf` | Float | 라디안 | 왼쪽 눈 요 각도 하한값 | -0.066353 |
| `right_yaw_low_rads_cpf` | Float | 라디안 | 오른쪽 눈 요 각도 하한값 | 0.074133 |
| `pitch_low_rads_cpf` | Float | 라디안 | 피치 각도 하한값 | -0.235690 |
| `left_yaw_high_rads_cpf` | Float | 라디안 | 왼쪽 눈 요 각도 상한값 | -0.029949 |
| `right_yaw_high_rads_cpf` | Float | 라디안 | 오른쪽 눈 요 각도 상한값 | 0.114763 |
| `pitch_high_rads_cpf` | Float | 라디안 | 피치 각도 상한값 | -0.169129 |
| `tx_left_eye_cpf` | Float | 미터 | 왼쪽 눈 X 위치 | 0.0315 |
| `ty_left_eye_cpf` | Float | 미터 | 왼쪽 눈 Y 위치 | 0.0 |
| `tz_left_eye_cpf` | Float | 미터 | 왼쪽 눈 Z 위치 | 0.0 |
| `tx_right_eye_cpf` | Float | 미터 | 오른쪽 눈 X 위치 | -0.0315 |
| `ty_right_eye_cpf` | Float | 미터 | 오른쪽 눈 Y 위치 | 0.0 |
| `tz_right_eye_cpf` | Float | 미터 | 오른쪽 눈 Z 위치 | 0.0 |
| `session_uid` | String | UUID | 세션 고유 식별자 | dfd2b9a5-a57b-41e1-989f-01a5d2059860 |

### Personalized Eye Gaze 필드 (`personalized_eye_gaze.csv`)
- **구조**: General과 동일
- **차이점**: 개인별 보정 적용으로 더 정확한 시선 추적
- **신뢰도**: 일반적으로 General보다 높은 정확도

### Eye Gaze Summary (`summary.json`)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `GazeInference.status` | String | 시선 추론 상태 ("SUCCESS", "FAILED") |
| `InSessionCalibration.start_time_us` | Integer | 보정 시작 시간 (마이크로초) |
| `InSessionCalibration.end_time_us` | Integer | 보정 종료 시간 (마이크로초) |
| `InSessionCalibration.params` | Array | 보정 매개변수 (6개 값) |
| `InSessionCalibration.num_detections` | Integer | 감지된 시선 포인트 수 |
| `InSessionCalibration.diopter_delta` | Float | 디옵터 변화량 |
| `CalibrationCorrection.generalized_error_rads_stats` | Object | 일반 오차 통계 (평균, 표준편차, 분위수) |
| `CalibrationCorrection.calibrated_error_rads_stats` | Object | 보정 후 오차 통계 |
| `version` | String | MPS 버전 |

---

## 🤲 Hand Tracking 데이터

### Hand Tracking Results 필드 (`hand_tracking_results.csv`)

#### 기본 정보
| 필드명 | 타입 | 설명 | 예시 값 |
|--------|------|------|---------|
| `tracking_timestamp_us` | Integer | MPS 처리 타임스탬프 (마이크로초) | 1762609162 |
| `left_tracking_confidence` | Float | 왼손 추적 신뢰도 (0~1) | 0.999297 |
| `right_tracking_confidence` | Float | 오른손 추적 신뢰도 (0~1) | -1 (없음) |

#### 왼손 21개 관절 좌표
| 필드 패턴 | 타입 | 설명 | 관절 ID |
|-----------|------|------|---------|
| `tx_left_landmark_{0-20}_device` | Float | 왼손 관절 X 좌표 (미터) | 0=손목, 1-4=엄지, 5-8=검지, 9-12=중지, 13-16=약지, 17-20=새끼 |
| `ty_left_landmark_{0-20}_device` | Float | 왼손 관절 Y 좌표 (미터) | 동일 |
| `tz_left_landmark_{0-20}_device` | Float | 왼손 관절 Z 좌표 (미터) | 동일 |

#### 오른손 21개 관절 좌표
| 필드 패턴 | 타입 | 설명 |
|-----------|------|------|
| `tx_right_landmark_{0-20}_device` | Float | 오른손 관절 X 좌표 (미터) |
| `ty_right_landmark_{0-20}_device` | Float | 오른손 관절 Y 좌표 (미터) |
| `tz_right_landmark_{0-20}_device` | Float | 오른손 관절 Z 좌표 (미터) |

#### 손목 포즈 정보
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `tx_left_device_wrist` | Float | 왼손 손목 위치 X (미터) |
| `ty_left_device_wrist` | Float | 왼손 손목 위치 Y (미터) |
| `tz_left_device_wrist` | Float | 왼손 손목 위치 Z (미터) |
| `qx_left_device_wrist` | Float | 왼손 손목 회전 쿼터니언 X |
| `qy_left_device_wrist` | Float | 왼손 손목 회전 쿼터니언 Y |
| `qz_left_device_wrist` | Float | 왼손 손목 회전 쿼터니언 Z |
| `qw_left_device_wrist` | Float | 왼손 손목 회전 쿼터니언 W |

#### 손바닥/손목 노멀 벡터
| 필드명 | 타입 | 설명 |
|--------|------|------|
| `nx_left_palm_device` | Float | 왼손 손바닥 노멀 벡터 X |
| `ny_left_palm_device` | Float | 왼손 손바닥 노멀 벡터 Y |
| `nz_left_palm_device` | Float | 왼손 손바닥 노멀 벡터 Z |
| `nx_left_wrist_device` | Float | 왼손 손목 노멀 벡터 X |
| `ny_left_wrist_device` | Float | 왼손 손목 노멀 벡터 Y |
| `nz_left_wrist_device` | Float | 왼손 손목 노멀 벡터 Z |

### Wrist and Palm Poses 필드 (`wrist_and_palm_poses.csv`)

**간소화된 손 추적 데이터** (관절 좌표 없이 손목/손바닥만)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `tracking_timestamp_us` | Integer | 타임스탬프 (마이크로초) |
| `left_tracking_confidence` | Float | 왼손 신뢰도 |
| `tx_left_wrist_device` | Float | 왼손 손목 X 위치 |
| `ty_left_wrist_device` | Float | 왼손 손목 Y 위치 |
| `tz_left_wrist_device` | Float | 왼손 손목 Z 위치 |
| `tx_left_palm_device` | Float | 왼손 손바닥 X 위치 |
| `ty_left_palm_device` | Float | 왼손 손바닥 Y 위치 |
| `tz_left_palm_device` | Float | 왼손 손바닥 Z 위치 |
| (오른손 동일 패턴) | | |

### Hand Tracking Summary (`summary.json`)

| 필드명 | 설명 |
|--------|------|
| `mean_confidence` | 평균 추적 신뢰도 |
| `total_frames` | 총 프레임 수 |
| `valid_frame_fraction` | 유효 프레임 비율 |
| `valid_pose_frame_fraction_left_hand` | 왼손 유효 포즈 비율 |
| `valid_pose_frame_fraction_right_hand` | 오른손 유효 포즈 비율 |

---

## 🗺️ SLAM (Simultaneous Localization and Mapping) 데이터

### Trajectory 데이터

#### Closed Loop Trajectory (`closed_loop_trajectory.csv`)
**루프 클로저 적용된 최적화된 궤적**

| 필드명 | 타입 | 단위 | 설명 | 예시 값 |
|--------|------|------|------|---------|
| `graph_uid` | String | UUID | SLAM 그래프 고유 식별자 | 31ebacab-fcac-b027-908f-880f29dc7b64 |
| `tracking_timestamp_us` | Integer | 마이크로초 | 추적 타임스탬프 | 1763475767 |
| `utc_timestamp_ns` | Integer | 나노초 | UTC 절대 시간 | 1694815246654918709 |
| `tx_world_device` | Float | 미터 | 월드 좌표계에서 장비 X 위치 | 0.962793 |
| `ty_world_device` | Float | 미터 | 월드 좌표계에서 장비 Y 위치 | 0.596484 |
| `tz_world_device` | Float | 미터 | 월드 좌표계에서 장비 Z 위치 | 0.031522 |
| `qx_world_device` | Float | 무차원 | 장비 회전 쿼터니언 X | 0.575436 |
| `qy_world_device` | Float | 무차원 | 장비 회전 쿼터니언 Y | 0.461931 |
| `qz_world_device` | Float | 무차원 | 장비 회전 쿼터니언 Z | -0.517368 |
| `qw_world_device` | Float | 무차원 | 장비 회전 쿼터니언 W | 0.433386 |
| `device_linear_velocity_x_device` | Float | m/s | 선형 속도 X | -0.001260 |
| `device_linear_velocity_y_device` | Float | m/s | 선형 속도 Y | 0.007821 |
| `device_linear_velocity_z_device` | Float | m/s | 선형 속도 Z | 0.002019 |
| `angular_velocity_x_device` | Float | rad/s | 각속도 X | 0.000000 |
| `angular_velocity_y_device` | Float | rad/s | 각속도 Y | 0.000000 |
| `angular_velocity_z_device` | Float | rad/s | 각속도 Z | 0.000000 |
| `gravity_x_world` | Float | m/s² | 중력 벡터 X | 0.000000 |
| `gravity_y_world` | Float | m/s² | 중력 벡터 Y | -0.000000 |
| `gravity_z_world` | Float | m/s² | 중력 벡터 Z | -9.810000 |
| `quality_score` | Float | 0~1 | 추적 품질 점수 | 1.0 |
| `geo_available` | Integer | Boolean | GPS 정보 사용 가능 여부 | 0 |
| `tx_ecef_device` | Float | 미터 | ECEF 좌표계 X | 0.064919 |
| `ty_ecef_device` | Float | 미터 | ECEF 좌표계 Y | 0.723464 |
| `tz_ecef_device` | Float | 미터 | ECEF 좌표계 Z | -0.861910 |
| `qx_ecef_device` | Float | 무차원 | ECEF 회전 쿼터니언 X | -0.001076 |
| `qy_ecef_device` | Float | 무차원 | ECEF 회전 쿼터니언 Y | -0.002869 |
| `qz_ecef_device` | Float | 무차원 | ECEF 회전 쿼터니언 Z | 0.000211 |
| `qw_ecef_device` | Float | 무차원 | ECEF 회전 쿼터니언 W | 0.999995 |

#### Open Loop Trajectory (`open_loop_trajectory.csv`)
**루프 클로저 미적용 원시 궤적** (필드 구조 동일, 정확도 낮음)

### 3D Point Cloud 데이터

#### Semi-Dense Points (`semidense_points.csv.gz`)
**SLAM으로 재구성된 3D 포인트 클라우드**

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `uid` | Integer | 포인트 고유 ID |
| `graph_uid` | String | SLAM 그래프 ID |
| `px_world` | Float | 월드 좌표 X (미터) |
| `py_world` | Float | 월드 좌표 Y (미터) |
| `pz_world` | Float | 월드 좌표 Z (미터) |
| `inv_dist_std` | Float | 역거리 표준편차 |
| `dist_std` | Float | 거리 표준편차 |

#### Semi-Dense Observations (`semidense_observations.csv.gz`)
**포인트 관측 데이터**

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `uid` | Integer | 관측 고유 ID |
| `frame_tracking_timestamp_us` | Integer | 프레임 타임스탬프 |
| `camera_serial` | String | 카메라 시리얼 번호 |
| `u` | Float | 이미지 좌표 U (픽셀) |
| `v` | Float | 이미지 좌표 V (픽셀) |

### Online Calibration (`online_calibration.jsonl`)
**실시간 센서 보정 정보** (JSON Lines 형식)

#### IMU 보정
| 필드명 | 설명 |
|--------|------|
| `ImuCalibrations.Gyroscope.TimeOffsetSec_Device_Gyro` | 자이로스코프 시간 오프셋 |
| `ImuCalibrations.Gyroscope.Bias.Offset` | 자이로스코프 바이어스 [X,Y,Z] |
| `ImuCalibrations.Accelerometer.Bias.Offset` | 가속도계 바이어스 [X,Y,Z] |
| `ImuCalibrations.T_Device_Imu.Translation` | IMU 위치 오프셋 |
| `ImuCalibrations.T_Device_Imu.UnitQuaternion` | IMU 회전 오프셋 |

#### 카메라 보정
| 필드명 | 설명 |
|--------|------|
| `CameraCalibrations.Projection.Params` | 카메라 내부 매개변수 (15개 값) |
| `CameraCalibrations.T_Device_Camera.Translation` | 카메라 위치 오프셋 |
| `CameraCalibrations.T_Device_Camera.UnitQuaternion` | 카메라 회전 오프셋 |
| `CameraCalibrations.SerialNumber` | 카메라 시리얼 번호 |
| `CameraCalibrations.Label` | 카메라 라벨 (camera-slam-left/right, camera-rgb) |

### SLAM Summary (`summary.json`)

| 컴포넌트 | 설명 |
|----------|------|
| `VRS Health Check` | VRS 파일 무결성 검사 |
| `SLAM.status` | SLAM 처리 상태 |
| `SLAM.info` | 녹화 시간, 궤적 길이, 보정 통계 |
| `Aligner` | 궤적 정렬 상태 |
| `Optimization` | 최적화 프로세스 상태 |
| `SemiDense Tracker` | 포인트 추적 통계 |

---

## 🎮 Unity AR 개발에서의 활용

### 실시간 데이터 플로우
```
VRS Stream → MPS Processing → CSV Data → Django API → Unity C# Client
```

### 데이터 활용 예시

#### Eye Gaze
```csharp
// 시선 기반 UI 포커싱
Vector3 gazeDirection = new Vector3(data.yaw, data.pitch, 1.0f);
RaycastHit hit;
if (Physics.Raycast(eyePosition, gazeDirection, out hit)) {
    FocusObject(hit.collider.gameObject);
}
```

#### Hand Tracking
```csharp
// 손가락 제스처 인식
foreach (var landmark in handData.left_hand_landmarks) {
    Vector3 jointPos = new Vector3(landmark.x, landmark.y, landmark.z);
    handJoints[landmark.id].transform.position = jointPos;
}
```

#### SLAM Trajectory
```csharp
// AR 객체 공간 정합
Matrix4x4 worldTransform = new Matrix4x4();
worldTransform.SetTRS(
    new Vector3(slam.tx_world_device, slam.ty_world_device, slam.tz_world_device),
    new Quaternion(slam.qx_world_device, slam.qy_world_device, slam.qz_world_device, slam.qw_world_device),
    Vector3.one
);
```

---

## 📊 데이터 품질 및 성능 지표

### Eye Gaze 품질
- **일반 모델 오차**: ~3.0° (평균)
- **개인화 모델 오차**: ~1.0° (평균)
- **신뢰도 임계값**: >0.7 권장

### Hand Tracking 품질
- **평균 신뢰도**: 99.97%
- **유효 프레임**: 85.5%
- **관절 정확도**: ~1cm (근거리)

### SLAM 품질
- **위치 정확도**: ~1mm (평균)
- **회전 정확도**: ~0.01° (평균)
- **궤적 길이**: 7.62m (샘플)
- **처리 시간**: 1분 2초 (샘플)

---

## 🔧 API 엔드포인트 매핑

| MPS 데이터 | Django API 엔드포인트 | 주요 필드 |
|------------|----------------------|-----------|
| Eye Gaze CSV | `/api/streams/api/eye-gaze/` | `yaw`, `pitch`, `depth_m`, `gaze_type` |
| Hand Tracking CSV | `/api/streams/api/hand-tracking/` | `left_hand_landmarks`, `right_hand_landmarks` |
| SLAM Trajectory CSV | `/api/streams/api/slam-trajectory/` | `transform_matrix`, `position_x/y/z` |
| VRS Streams | `/api/streams/api/vrs-streams/` | `stream_id`, `frame_index`, `image_shape` |
| Sessions | `/api/streams/api/sessions/` | `session_id`, `device_serial`, `metadata` |

이 문서는 Project Aria ARD 시스템에서 사용되는 모든 데이터 필드의 완전한 참조 가이드입니다. Unity AR 개발 시 이 정보를 활용하여 정확한 데이터 처리 및 시각화가 가능합니다.