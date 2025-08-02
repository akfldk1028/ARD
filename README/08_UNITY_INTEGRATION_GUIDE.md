# 08. Unity ARD 통합 가이드

> **📖 문서 가이드**: [00_INDEX.md](00_INDEX.md) | **이전**: [07_PROJECT_ARIA_DATA_FIELDS.md](07_PROJECT_ARIA_DATA_FIELDS.md) | **다음**: [09_DOCKER_UNITY_SETUP.md](09_DOCKER_UNITY_SETUP.md)  
> **카테고리**: Unity 클라이언트 연동 | **난이도**: ⭐⭐⭐⭐ | **예상 시간**: 25분

Project Aria 실시간 데이터를 Unity에서 활용하는 완전한 가이드입니다.

## 🎯 개요

Unity에서 ARD API를 통해 다음 데이터를 실시간으로 받아와 활용하는 방법을 제공합니다:
- 📸 **RGB 이미지** - 1408x1408 Base64 JPEG
- 👁️ **시선 추적** - Yaw/Pitch 각도와 3D 벡터
- 🤲 **손 추적** - 21개 랜드마크 좌표
- 🗺️ **SLAM 궤적** - 3D 위치와 변환 행렬
- 📳 **IMU 센서** - 가속도/자이로스코프

## 🏗️ 아키텍처 구조

```
Unity Client
├── ARDManager (메인 매니저)
├── ARDApiClient (HTTP 통신)
├── Data Models (데이터 구조)
├── Processors (데이터 처리)
└── UI Components (시각화)
```

## 📦 필수 Unity 패키지

```json
{
  "dependencies": {
    "com.unity.nuget.newtonsoft-json": "3.2.1",
    "com.unity.ui": "2.0.0",
    "com.unity.ugui": "1.0.0"
  }
}
```

## 🔧 코드 구조

### 1. ARD API 클라이언트 (ARDApiClient.cs)

```csharp
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json;

[System.Serializable]
public class ARDConfig
{
    public string baseUrl = "http://127.0.0.1:8000/api/v1/aria";
    public int timeoutSeconds = 10;
    public int refreshRateMs = 100; // 10 FPS
}

public class ARDApiClient : MonoBehaviour
{
    [Header("API Configuration")]
    public ARDConfig config = new ARDConfig();
    
    [Header("Debug")]
    public bool enableDebugLogs = true;
    
    // Events
    public System.Action<VRSImageData> OnImageReceived;
    public System.Action<EyeGazeData> OnEyeGazeReceived;
    public System.Action<HandTrackingData> OnHandTrackingReceived;
    public System.Action<SLAMTrajectoryData> OnSLAMReceived;
    public System.Action<IMUData> OnIMUReceived;
    public System.Action<string> OnError;
    
    private bool isRunning = false;
    
    void Start()
    {
        StartStreaming();
    }
    
    void OnDestroy()
    {
        StopStreaming();
    }
    
    public void StartStreaming()
    {
        if (!isRunning)
        {
            isRunning = true;
            StartCoroutine(StreamingLoop());
            LogDebug("ARD streaming started");
        }
    }
    
    public void StopStreaming()
    {
        isRunning = false;
        LogDebug("ARD streaming stopped");
    }
    
    private IEnumerator StreamingLoop()
    {
        while (isRunning)
        {
            // 병렬로 모든 데이터 요청
            var imageCoroutine = StartCoroutine(FetchLatestImage());
            var gazeCoroutine = StartCoroutine(FetchLatestEyeGaze());
            var handCoroutine = StartCoroutine(FetchLatestHandTracking());
            var slamCoroutine = StartCoroutine(FetchLatestSLAM());
            var imuCoroutine = StartCoroutine(FetchLatestIMU());
            
            // 모든 요청 완료 대기
            yield return imageCoroutine;
            yield return gazeCoroutine;
            yield return handCoroutine;
            yield return slamCoroutine;
            yield return imuCoroutine;
            
            // 대기
            yield return new WaitForSeconds(config.refreshRateMs / 1000f);
        }
    }
    
    private IEnumerator FetchLatestImage()
    {
        string url = $"{config.baseUrl}/vrs-streams/?image_data__isnull=false&limit=1&ordering=-id";
        yield return StartCoroutine(MakeRequest<ApiResponse<VRSImageData>>(url, OnImageResponseReceived));
    }
    
    private IEnumerator FetchLatestEyeGaze()
    {
        string url = $"{config.baseUrl}/eye-gaze/?limit=1&ordering=-id";
        yield return StartCoroutine(MakeRequest<ApiResponse<EyeGazeData>>(url, OnEyeGazeResponseReceived));
    }
    
    private IEnumerator FetchLatestHandTracking()
    {
        string url = $"{config.baseUrl}/hand-tracking/?limit=1&ordering=-id";
        yield return StartCoroutine(MakeRequest<ApiResponse<HandTrackingData>>(url, OnHandTrackingResponseReceived));
    }
    
    private IEnumerator FetchLatestSLAM()
    {
        string url = $"{config.baseUrl}/slam-trajectory/?limit=1&ordering=-id";
        yield return StartCoroutine(MakeRequest<ApiResponse<SLAMTrajectoryData>>(url, OnSLAMResponseReceived));
    }
    
    private IEnumerator FetchLatestIMU()
    {
        string url = $"{config.baseUrl}/imu-data/?limit=1&ordering=-id";
        yield return StartCoroutine(MakeRequest<ApiResponse<IMUData>>(url, OnIMUResponseReceived));
    }
    
    private IEnumerator MakeRequest<T>(string url, System.Action<T> onSuccess)
    {
        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.timeout = config.timeoutSeconds;
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    T response = JsonConvert.DeserializeObject<T>(request.downloadHandler.text);
                    onSuccess?.Invoke(response);
                }
                catch (Exception e)
                {
                    LogError($"JSON Parse Error for {url}: {e.Message}");
                }
            }
            else
            {
                LogError($"Request Failed for {url}: {request.error}");
            }
        }
    }
    
    // Response handlers
    private void OnImageResponseReceived(ApiResponse<VRSImageData> response)
    {
        if (response?.results != null && response.results.Length > 0)
        {
            OnImageReceived?.Invoke(response.results[0]);
        }
    }
    
    private void OnEyeGazeResponseReceived(ApiResponse<EyeGazeData> response)
    {
        if (response?.results != null && response.results.Length > 0)
        {
            OnEyeGazeReceived?.Invoke(response.results[0]);
        }
    }
    
    private void OnHandTrackingResponseReceived(ApiResponse<HandTrackingData> response)
    {
        if (response?.results != null && response.results.Length > 0)
        {
            OnHandTrackingReceived?.Invoke(response.results[0]);
        }
    }
    
    private void OnSLAMResponseReceived(ApiResponse<SLAMTrajectoryData> response)
    {
        if (response?.results != null && response.results.Length > 0)
        {
            OnSLAMReceived?.Invoke(response.results[0]);
        }
    }
    
    private void OnIMUResponseReceived(ApiResponse<IMUData> response)
    {
        if (response?.results != null && response.results.Length > 0)
        {
            OnIMUReceived?.Invoke(response.results[0]);
        }
    }
    
    private void LogDebug(string message)
    {
        if (enableDebugLogs)
            Debug.Log($"[ARDApiClient] {message}");
    }
    
    private void LogError(string message)
    {
        Debug.LogError($"[ARDApiClient] {message}");
        OnError?.Invoke(message);
    }
}
```

### 2. 데이터 모델 (ARDDataModels.cs)

```csharp
using System;
using UnityEngine;

[System.Serializable]
public class ApiResponse<T>
{
    public int count;
    public string next;
    public string previous;
    public T[] results;
}

[System.Serializable]
public class VRSImageData
{
    public int id;
    public int session;
    public string stream_name;
    public string timestamp;
    public string image_data; // Base64 JPEG
    public int image_width;
    public int image_height;
    public int original_size_bytes;
    public int compressed_size_bytes;
    public int compression_quality;
    
    // Unity에서 사용할 Texture2D 변환
    public Texture2D ToTexture2D()
    {
        if (string.IsNullOrEmpty(image_data))
            return null;
            
        try
        {
            byte[] imageBytes = Convert.FromBase64String(image_data);
            Texture2D texture = new Texture2D(image_width, image_height);
            texture.LoadImage(imageBytes);
            return texture;
        }
        catch (Exception e)
        {
            Debug.LogError($"Failed to convert image data: {e.Message}");
            return null;
        }
    }
}

[System.Serializable]
public class EyeGazeData
{
    public int id;
    public int session;
    public string timestamp;
    public string gaze_type;
    public float yaw;
    public float pitch;
    public float depth_m;
    public float confidence;
    public GazeDirection gaze_direction;
    
    // Unity Vector3 변환
    public Vector3 ToUnityVector()
    {
        return new Vector3(gaze_direction.x, gaze_direction.y, gaze_direction.z);
    }
    
    // 화면 좌표로 변환 (1408x1408 기준)
    public Vector2 ToScreenCoordinate(int screenWidth = 1408, int screenHeight = 1408)
    {
        // Yaw/Pitch를 화면 좌표로 변환
        float normalizedX = (yaw + 45f) / 90f; // -45~45도를 0~1로 정규화
        float normalizedY = (pitch + 30f) / 60f; // -30~30도를 0~1로 정규화
        
        float screenX = Mathf.Clamp01(normalizedX) * screenWidth;
        float screenY = Mathf.Clamp01(1f - normalizedY) * screenHeight; // Y축 반전
        
        return new Vector2(screenX, screenY);
    }
}

[System.Serializable]
public class GazeDirection
{
    public float x;
    public float y;
    public float z;
}

[System.Serializable]
public class HandTrackingData
{
    public int id;
    public int session;
    public string timestamp;
    public float[][] left_hand_landmarks;
    public float[] left_hand_wrist_normal;
    public float[] left_hand_palm_normal;
    public float[][] right_hand_landmarks;
    public float[] right_hand_wrist_normal;
    public float[] right_hand_palm_normal;
    public bool has_left_hand;
    public bool has_right_hand;
    
    // Unity Vector3 배열로 변환
    public Vector3[] GetLeftHandLandmarks()
    {
        if (left_hand_landmarks == null) return null;
        
        Vector3[] landmarks = new Vector3[left_hand_landmarks.Length];
        for (int i = 0; i < left_hand_landmarks.Length; i++)
        {
            if (left_hand_landmarks[i] != null && left_hand_landmarks[i].Length >= 3)
            {
                landmarks[i] = new Vector3(
                    left_hand_landmarks[i][0],
                    left_hand_landmarks[i][1],
                    left_hand_landmarks[i][2]
                );
            }
        }
        return landmarks;
    }
    
    public Vector3[] GetRightHandLandmarks()
    {
        if (right_hand_landmarks == null) return null;
        
        Vector3[] landmarks = new Vector3[right_hand_landmarks.Length];
        for (int i = 0; i < right_hand_landmarks.Length; i++)
        {
            if (right_hand_landmarks[i] != null && right_hand_landmarks[i].Length >= 3)
            {
                landmarks[i] = new Vector3(
                    right_hand_landmarks[i][0],
                    right_hand_landmarks[i][1],
                    right_hand_landmarks[i][2]
                );
            }
        }
        return landmarks;
    }
}

[System.Serializable]
public class SLAMTrajectoryData
{
    public int id;
    public int session;
    public string timestamp;
    public float[][] transform_matrix;
    public Position position;
    
    // Unity Matrix4x4로 변환
    public Matrix4x4 ToUnityMatrix()
    {
        if (transform_matrix == null || transform_matrix.Length != 4)
            return Matrix4x4.identity;
            
        Matrix4x4 matrix = new Matrix4x4();
        for (int i = 0; i < 4; i++)
        {
            for (int j = 0; j < 4; j++)
            {
                if (transform_matrix[i] != null && transform_matrix[i].Length > j)
                {
                    matrix[i, j] = transform_matrix[i][j];
                }
            }
        }
        return matrix;
    }
    
    // Unity Vector3 위치
    public Vector3 ToUnityPosition()
    {
        return new Vector3(position.x, position.y, position.z);
    }
}

[System.Serializable]
public class Position
{
    public float x;
    public float y;
    public float z;
}

[System.Serializable]
public class IMUData
{
    public int id;
    public int session;
    public string timestamp;
    public string imu_type;
    public float accel_x;
    public float accel_y;
    public float accel_z;
    public float gyro_x;
    public float gyro_y;
    public float gyro_z;
    public float acceleration_magnitude;
    public float angular_velocity_magnitude;
    public float temperature_c;
    
    // Unity Vector3로 변환
    public Vector3 GetAcceleration()
    {
        return new Vector3(accel_x, accel_y, accel_z);
    }
    
    public Vector3 GetAngularVelocity()
    {
        return new Vector3(gyro_x, gyro_y, gyro_z);
    }
}
```

### 3. ARD 매니저 (ARDManager.cs)

```csharp
using UnityEngine;
using UnityEngine.UI;
using System.Collections.Generic;

public class ARDManager : MonoBehaviour
{
    [Header("Components")]
    public ARDApiClient apiClient;
    
    [Header("UI References")]
    public RawImage ariaImageDisplay;
    public Transform gazePointer;
    public Transform leftHandRoot;
    public Transform rightHandRoot;
    public Transform slamTracker;
    
    [Header("Prefabs")]
    public GameObject handLandmarkPrefab;
    public GameObject gazePointerPrefab;
    
    [Header("Settings")]
    public bool showImageStream = true;
    public bool showEyeGaze = true;
    public bool showHandTracking = true;
    public bool showSLAMTracking = true;
    public bool showIMUDebug = true;
    
    // 상태 관리
    private VRSImageData currentImage;
    private EyeGazeData currentGaze;
    private HandTrackingData currentHands;
    private SLAMTrajectoryData currentSLAM;
    private IMUData currentIMU;
    
    // UI 객체 풀
    private List<GameObject> leftHandLandmarks = new List<GameObject>();
    private List<GameObject> rightHandLandmarks = new List<GameObject>();
    
    void Start()
    {
        InitializeComponents();
        SetupEventListeners();
    }
    
    void InitializeComponents()
    {
        // API 클라이언트 초기화
        if (apiClient == null)
        {
            apiClient = GetComponent<ARDApiClient>();
        }
        
        // 시선 포인터 생성
        if (gazePointer == null && gazePointerPrefab != null)
        {
            GameObject gazeObj = Instantiate(gazePointerPrefab);
            gazePointer = gazeObj.transform;
        }
        
        // 손 랜드마크 풀 초기화
        InitializeHandLandmarkPools();
    }
    
    void SetupEventListeners()
    {
        if (apiClient != null)
        {
            apiClient.OnImageReceived += OnImageReceived;
            apiClient.OnEyeGazeReceived += OnEyeGazeReceived;
            apiClient.OnHandTrackingReceived += OnHandTrackingReceived;
            apiClient.OnSLAMReceived += OnSLAMReceived;
            apiClient.OnIMUReceived += OnIMUReceived;
            apiClient.OnError += OnErrorReceived;
        }
    }
    
    void OnDestroy()
    {
        // 이벤트 리스너 해제
        if (apiClient != null)
        {
            apiClient.OnImageReceived -= OnImageReceived;
            apiClient.OnEyeGazeReceived -= OnEyeGazeReceived;
            apiClient.OnHandTrackingReceived -= OnHandTrackingReceived;
            apiClient.OnSLAMReceived -= OnSLAMReceived;
            apiClient.OnIMUReceived -= OnIMUReceived;
            apiClient.OnError -= OnErrorReceived;
        }
    }
    
    // 데이터 수신 핸들러들
    private void OnImageReceived(VRSImageData imageData)
    {
        currentImage = imageData;
        
        if (showImageStream && ariaImageDisplay != null)
        {
            Texture2D texture = imageData.ToTexture2D();
            if (texture != null)
            {
                ariaImageDisplay.texture = texture;
                Debug.Log($"Updated Aria Image: {imageData.stream_name} ({imageData.image_width}x{imageData.image_height})");
            }
        }
    }
    
    private void OnEyeGazeReceived(EyeGazeData gazeData)
    {
        currentGaze = gazeData;
        
        if (showEyeGaze && gazePointer != null)
        {
            // 시선 방향을 3D 공간에 표시
            Vector3 gazeDirection = gazeData.ToUnityVector();
            gazePointer.position = gazeDirection * gazeData.depth_m;
            
            // 화면 좌표로 변환해서 UI에 표시
            Vector2 screenPos = gazeData.ToScreenCoordinate();
            Debug.Log($"Eye Gaze: Yaw={gazeData.yaw:F1}°, Pitch={gazeData.pitch:F1}°, Screen=({screenPos.x:F0},{screenPos.y:F0}), Confidence={gazeData.confidence:F2}");
        }
    }
    
    private void OnHandTrackingReceived(HandTrackingData handData)
    {
        currentHands = handData;
        
        if (showHandTracking)
        {
            // 왼손 표시
            if (handData.has_left_hand && leftHandRoot != null)
            {
                Vector3[] leftLandmarks = handData.GetLeftHandLandmarks();
                UpdateHandLandmarks(leftLandmarks, leftHandLandmarks, leftHandRoot);
            }
            
            // 오른손 표시
            if (handData.has_right_hand && rightHandRoot != null)
            {
                Vector3[] rightLandmarks = handData.GetRightHandLandmarks();
                UpdateHandLandmarks(rightLandmarks, rightHandLandmarks, rightHandRoot);
            }
            
            Debug.Log($"Hand Tracking: Left={handData.has_left_hand}, Right={handData.has_right_hand}");
        }
    }
    
    private void OnSLAMReceived(SLAMTrajectoryData slamData)
    {
        currentSLAM = slamData;
        
        if (showSLAMTracking && slamTracker != null)
        {
            // SLAM 위치로 트래커 이동
            Vector3 position = slamData.ToUnityPosition();
            Matrix4x4 transform = slamData.ToUnityMatrix();
            
            slamTracker.position = position;
            slamTracker.rotation = transform.rotation;
            
            Debug.Log($"SLAM Position: ({position.x:F2}, {position.y:F2}, {position.z:F2})");
        }
    }
    
    private void OnIMUReceived(IMUData imuData)
    {
        currentIMU = imuData;
        
        if (showIMUDebug)
        {
            Vector3 acceleration = imuData.GetAcceleration();
            Vector3 angularVelocity = imuData.GetAngularVelocity();
            
            Debug.Log($"IMU [{imuData.imu_type}]: Accel=({acceleration.x:F2},{acceleration.y:F2},{acceleration.z:F2}) " +
                     $"Gyro=({angularVelocity.x:F3},{angularVelocity.y:F3},{angularVelocity.z:F3})");
        }
    }
    
    private void OnErrorReceived(string error)
    {
        Debug.LogError($"ARD API Error: {error}");
    }
    
    // 유틸리티 메서드들
    private void InitializeHandLandmarkPools()
    {
        // 왼손 랜드마크 풀 (21개)
        for (int i = 0; i < 21; i++)
        {
            GameObject landmark = Instantiate(handLandmarkPrefab, leftHandRoot);
            landmark.SetActive(false);
            leftHandLandmarks.Add(landmark);
        }
        
        // 오른손 랜드마크 풀 (21개)
        for (int i = 0; i < 21; i++)
        {
            GameObject landmark = Instantiate(handLandmarkPrefab, rightHandRoot);
            landmark.SetActive(false);
            rightHandLandmarks.Add(landmark);
        }
    }
    
    private void UpdateHandLandmarks(Vector3[] landmarks, List<GameObject> landmarkObjects, Transform parent)
    {
        if (landmarks == null) return;
        
        for (int i = 0; i < landmarkObjects.Count; i++)
        {
            if (i < landmarks.Length)
            {
                landmarkObjects[i].SetActive(true);
                landmarkObjects[i].transform.localPosition = landmarks[i];
            }
            else
            {
                landmarkObjects[i].SetActive(false);
            }
        }
    }
    
    // 공개 메서드들 (다른 스크립트에서 호출 가능)
    public VRSImageData GetCurrentImage() => currentImage;
    public EyeGazeData GetCurrentGaze() => currentGaze;
    public HandTrackingData GetCurrentHands() => currentHands;
    public SLAMTrajectoryData GetCurrentSLAM() => currentSLAM;
    public IMUData GetCurrentIMU() => currentIMU;
    
    // 실시간 시선-화면 매핑
    public Vector2 GetGazeScreenPosition()
    {
        if (currentGaze != null)
        {
            return currentGaze.ToScreenCoordinate();
        }
        return Vector2.zero;
    }
    
    // 시선과 이미지 결합
    public (Texture2D image, Vector2 gazePos) GetImageWithGaze()
    {
        Texture2D image = currentImage?.ToTexture2D();
        Vector2 gazePos = GetGazeScreenPosition();
        return (image, gazePos);
    }
}
```

### 4. 시선-이미지 오버레이 컴포넌트 (GazeImageOverlay.cs)

```csharp
using UnityEngine;
using UnityEngine.UI;

public class GazeImageOverlay : MonoBehaviour
{
    [Header("References")]
    public ARDManager ardManager;
    public RawImage imageDisplay;
    public RectTransform gazeIndicator;
    
    [Header("Settings")]
    public Color gazeIndicatorColor = Color.red;
    public float gazeIndicatorSize = 20f;
    public bool showConfidenceAlpha = true;
    
    private Image gazeIndicatorImage;
    
    void Start()
    {
        InitializeGazeIndicator();
    }
    
    void Update()
    {
        UpdateGazeOverlay();
    }
    
    void InitializeGazeIndicator()
    {
        if (gazeIndicator != null)
        {
            gazeIndicatorImage = gazeIndicator.GetComponent<Image>();
            if (gazeIndicatorImage != null)
            {
                gazeIndicatorImage.color = gazeIndicatorColor;
            }
            
            gazeIndicator.sizeDelta = new Vector2(gazeIndicatorSize, gazeIndicatorSize);
        }
    }
    
    void UpdateGazeOverlay()
    {
        if (ardManager == null || imageDisplay == null || gazeIndicator == null)
            return;
            
        EyeGazeData currentGaze = ardManager.GetCurrentGaze();
        if (currentGaze == null) return;
        
        // 시선 위치를 이미지 좌표계로 변환
        Vector2 gazeScreenPos = currentGaze.ToScreenCoordinate();
        
        // RectTransform 좌표로 변환
        RectTransform imageRect = imageDisplay.rectTransform;
        Vector2 imageSize = imageRect.sizeDelta;
        
        // 정규화된 좌표를 UI 좌표로 변환
        float normalizedX = gazeScreenPos.x / 1408f; // 원본 이미지 크기로 정규화
        float normalizedY = gazeScreenPos.y / 1408f;
        
        Vector2 uiPosition = new Vector2(
            (normalizedX - 0.5f) * imageSize.x,
            (normalizedY - 0.5f) * imageSize.y
        );
        
        gazeIndicator.anchoredPosition = uiPosition;
        
        // 신뢰도에 따른 투명도 조절
        if (showConfidenceAlpha && gazeIndicatorImage != null)
        {
            Color color = gazeIndicatorColor;
            color.a = currentGaze.confidence;
            gazeIndicatorImage.color = color;
        }
        
        // 시선 데이터가 유효한 경우에만 표시
        gazeIndicator.gameObject.SetActive(currentGaze.confidence > 0.5f);
    }
}
```

## 🎮 사용 방법

### 1. Scene 설정

1. **빈 GameObject 생성** → "ARDSystem"으로 이름 변경
2. **ARDApiClient.cs** 스크립트 추가
3. **ARDManager.cs** 스크립트 추가
4. **Canvas 생성** → UI 요소들 배치
5. **RawImage 생성** → Aria 이미지 표시용

### 2. Inspector 설정

```
ARDSystem
├── ARDApiClient
│   ├── Base Url: http://127.0.0.1:8000/api/v1/aria
│   ├── Timeout Seconds: 10
│   └── Refresh Rate Ms: 100
└── ARDManager
    ├── Api Client: ARDSystem (자동 연결)
    ├── Aria Image Display: Canvas/AriaImage
    ├── Show Image Stream: ✓
    ├── Show Eye Gaze: ✓
    ├── Show Hand Tracking: ✓
    └── Show SLAM Tracking: ✓
```

### 3. 런타임 사용

```csharp
// 다른 스크립트에서 ARD 데이터 접근
ARDManager ardManager = FindObjectOfType<ARDManager>();

// 현재 시선 위치 가져오기
Vector2 gazePos = ardManager.GetGazeScreenPosition();

// 현재 이미지와 시선 동시 가져오기
var (image, gazePosition) = ardManager.GetImageWithGaze();

// 손 추적 데이터 확인
HandTrackingData hands = ardManager.GetCurrentHands();
if (hands != null && hands.has_left_hand)
{
    Vector3[] leftHandLandmarks = hands.GetLeftHandLandmarks();
}
```

## 🚀 고급 활용 예시

### 교수님 요구사항 구현: 시선-화면 매핑

```csharp
public class GazeScreenMapper : MonoBehaviour
{
    public ARDManager ardManager;
    public Camera mainCamera;
    
    void Update()
    {
        var currentGaze = ardManager.GetCurrentGaze();
        var currentImage = ardManager.GetCurrentImage();
        
        if (currentGaze != null && currentImage != null)
        {
            // 1. RGB 이미지 중심점 (704, 704)
            Vector2 screenCenter = new Vector2(704, 704);
            
            // 2. 시선이 향하는 화면 상 좌표
            Vector2 gazeScreenPos = currentGaze.ToScreenCoordinate();
            
            // 3. 중심점 기준 상대 좌표
            Vector2 relativeGaze = gazeScreenPos - screenCenter;
            
            Debug.Log($"Screen Center: {screenCenter}, Gaze Position: {gazeScreenPos}, Relative: {relativeGaze}");
            
            // 4. Unity 3D 공간으로 투영
            Vector3 worldGazePoint = ProjectGazeToWorld(relativeGaze, currentGaze.depth_m);
        }
    }
    
    Vector3 ProjectGazeToWorld(Vector2 screenOffset, float depth)
    {
        // 화면 좌표를 3D 월드 좌표로 변환
        Vector3 screenPoint = new Vector3(screenOffset.x, screenOffset.y, depth);
        return mainCamera.ScreenToWorldPoint(screenPoint);
    }
}
```

## 🔧 성능 최적화 팁

### 1. 메모리 관리
```csharp
// Texture2D 메모리 해제
private void OnImageReceived(VRSImageData imageData)
{
    if (ariaImageDisplay.texture != null)
    {
        DestroyImmediate(ariaImageDisplay.texture); // 이전 텍스처 해제
    }
    
    Texture2D newTexture = imageData.ToTexture2D();
    ariaImageDisplay.texture = newTexture;
}
```

### 2. 업데이트 주기 조절
```csharp
[Header("Performance")]
public float imageUpdateInterval = 0.1f; // 10 FPS
public float gazeUpdateInterval = 0.05f; // 20 FPS
public float handUpdateInterval = 0.1f; // 10 FPS
```

### 3. 조건부 업데이트
```csharp
// 화면에 보일 때만 업데이트
void Update()
{
    if (imageDisplay.isActiveAndEnabled && showImageStream)
    {
        UpdateImageStream();
    }
}
```

## 📊 디버그 정보 표시

```csharp
void OnGUI()
{
    if (showDebugInfo)
    {
        GUILayout.BeginArea(new Rect(10, 10, 300, 400));
        
        GUILayout.Label($"=== ARD Debug Info ===");
        
        if (currentImage != null)
            GUILayout.Label($"Image: {currentImage.stream_name} ({currentImage.image_width}x{currentImage.image_height})");
            
        if (currentGaze != null)
            GUILayout.Label($"Gaze: Yaw={currentGaze.yaw:F1}° Pitch={currentGaze.pitch:F1}° Conf={currentGaze.confidence:F2}");
            
        if (currentHands != null)
            GUILayout.Label($"Hands: L={currentHands.has_left_hand} R={currentHands.has_right_hand}");
            
        if (currentSLAM != null)
            GUILayout.Label($"SLAM: ({currentSLAM.position.x:F2}, {currentSLAM.position.y:F2}, {currentSLAM.position.z:F2})");
            
        GUILayout.EndArea();
    }
}
```

## 🎯 결론

이 Unity 통합 가이드를 통해:

✅ **실시간 ARD 데이터** 수신 및 처리  
✅ **멀티모달 센서 융합** (이미지 + 시선 + 손 + 위치)  
✅ **유지보수성** 높은 모듈화 구조  
✅ **성능 최적화** 및 메모리 관리  
✅ **교수님 요구사항** 구현 가능  

Project Aria의 강력한 멀티모달 센서 데이터를 Unity에서 완전히 활용할 수 있습니다! 🚀