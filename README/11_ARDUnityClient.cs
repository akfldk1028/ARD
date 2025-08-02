using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json;

/// <summary>
/// ARD API Unity 클라이언트
/// Django ARD API와 연동하여 실시간 AR 데이터를 받아오는 Unity 클라이언트
/// </summary>
public class ARDUnityClient : MonoBehaviour
{
    [Header("ARD API 설정")]
    [SerializeField] private string apiBaseUrl = "http://localhost:8000";
    [SerializeField] private float dataFetchInterval = 0.1f; // 100ms마다 데이터 가져오기
    [SerializeField] private int maxDataPerRequest = 10;
    
    [Header("스트리밍 설정")]
    [SerializeField] private bool autoStartStreaming = true;
    [SerializeField] private int streamingDuration = 300; // 5분
    [SerializeField] private string streamType = "all"; // "all", "vrs", "mps"
    
    // API 엔드포인트
    private string ApiBase => $"{apiBaseUrl}/api/streams/api";
    private string StreamingEndpoint => $"{ApiBase}/streaming/";
    private string EyeGazeEndpoint => $"{ApiBase}/eye-gaze/";
    private string HandTrackingEndpoint => $"{ApiBase}/hand-tracking/";
    private string SlamTrajectoryEndpoint => $"{ApiBase}/slam-trajectory/";
    
    // 상태 관리
    private bool isStreaming = false;
    private bool isConnected = false;
    private Coroutine dataFetchCoroutine;
    
    // 이벤트 시스템
    public static event Action<EyeGazeData[]> OnEyeGazeDataReceived;
    public static event Action<HandTrackingData[]> OnHandTrackingDataReceived;
    public static event Action<SlamTrajectoryData[]> OnSlamTrajectoryDataReceived;
    public static event Action<bool> OnConnectionStatusChanged;
    public static event Action<bool> OnStreamingStatusChanged;
    
    private void Start()
    {
        StartCoroutine(Initialize());
    }
    
    private IEnumerator Initialize()
    {
        Debug.Log("[ARD] Unity 클라이언트 초기화 중...");
        
        // API 연결 테스트
        yield return StartCoroutine(TestConnection());
        
        if (isConnected && autoStartStreaming)
        {
            // 자동 스트리밍 시작
            yield return StartCoroutine(StartStreaming());
        }
    }
    
    /// <summary>
    /// API 연결 테스트
    /// </summary>
    public IEnumerator TestConnection()
    {
        Debug.Log("[ARD] API 연결 테스트 중...");
        
        using (UnityWebRequest request = UnityWebRequest.Get($"{ApiBase}/sessions/"))
        {
            request.timeout = 5;
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                isConnected = true;
                Debug.Log("[ARD] ✅ API 연결 성공!");
                OnConnectionStatusChanged?.Invoke(true);
            }
            else
            {
                isConnected = false;
                Debug.LogError($"[ARD] ❌ API 연결 실패: {request.error}");
                OnConnectionStatusChanged?.Invoke(false);
            }
        }
    }
    
    /// <summary>
    /// VRS/MPS 스트리밍 시작
    /// </summary>
    public IEnumerator StartStreaming()
    {
        if (isStreaming)
        {
            Debug.LogWarning("[ARD] 이미 스트리밍이 진행 중입니다.");
            yield break;
        }
        
        Debug.Log($"[ARD] 스트리밍 시작: {streamType} ({streamingDuration}초)");
        
        var streamingRequest = new StreamingRequest
        {
            duration = streamingDuration,
            stream_type = streamType
        };
        
        string jsonData = JsonConvert.SerializeObject(streamingRequest);
        
        using (UnityWebRequest request = new UnityWebRequest(StreamingEndpoint, "POST"))
        {
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonData);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                var response = JsonConvert.DeserializeObject<StreamingResponse>(request.downloadHandler.text);
                if (response.status == "success")
                {
                    isStreaming = true;
                    Debug.Log($"[ARD] ✅ 스트리밍 시작 성공: {response.message}");
                    OnStreamingStatusChanged?.Invoke(true);
                    
                    // 데이터 수신 시작
                    dataFetchCoroutine = StartCoroutine(FetchDataLoop());
                }
                else
                {
                    Debug.LogError($"[ARD] 스트리밍 시작 실패: {response.message}");
                }
            }
            else
            {
                Debug.LogError($"[ARD] 스트리밍 요청 실패: {request.error}");
            }
        }
    }
    
    /// <summary>
    /// 스트리밍 중지
    /// </summary>
    public IEnumerator StopStreaming()
    {
        if (!isStreaming)
        {
            Debug.LogWarning("[ARD] 진행 중인 스트리밍이 없습니다.");
            yield break;
        }
        
        Debug.Log("[ARD] 스트리밍 중지 중...");
        
        using (UnityWebRequest request = UnityWebRequest.Delete(StreamingEndpoint))
        {
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                isStreaming = false;
                Debug.Log("[ARD] ✅ 스트리밍 중지 완료");
                OnStreamingStatusChanged?.Invoke(false);
                
                // 데이터 수신 중지
                if (dataFetchCoroutine != null)
                {
                    StopCoroutine(dataFetchCoroutine);
                    dataFetchCoroutine = null;
                }
            }
            else
            {
                Debug.LogError($"[ARD] 스트리밍 중지 실패: {request.error}");
            }
        }
    }
    
    /// <summary>
    /// 실시간 데이터 수신 루프
    /// </summary>
    private IEnumerator FetchDataLoop()
    {
        while (isStreaming && isConnected)
        {
            // Eye Gaze 데이터 가져오기
            yield return StartCoroutine(FetchEyeGazeData());
            
            // Hand Tracking 데이터 가져오기
            yield return StartCoroutine(FetchHandTrackingData());
            
            // SLAM Trajectory 데이터 가져오기
            yield return StartCoroutine(FetchSlamTrajectoryData());
            
            yield return new WaitForSeconds(dataFetchInterval);
        }
    }
    
    /// <summary>
    /// Eye Gaze 데이터 가져오기
    /// </summary>
    private IEnumerator FetchEyeGazeData()
    {
        string url = $"{EyeGazeEndpoint}?ordering=-timestamp&page_size={maxDataPerRequest}";
        
        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.timeout = 2;
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    var response = JsonConvert.DeserializeObject<PaginatedResponse<EyeGazeData>>(request.downloadHandler.text);
                    if (response.results != null && response.results.Length > 0)
                    {
                        OnEyeGazeDataReceived?.Invoke(response.results);
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[ARD] Eye Gaze 데이터 파싱 오류: {e.Message}");
                }
            }
        }
    }
    
    /// <summary>
    /// Hand Tracking 데이터 가져오기
    /// </summary>
    private IEnumerator FetchHandTrackingData()
    {
        string url = $"{HandTrackingEndpoint}?ordering=-timestamp&page_size={maxDataPerRequest}";
        
        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.timeout = 2;
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    var response = JsonConvert.DeserializeObject<PaginatedResponse<HandTrackingData>>(request.downloadHandler.text);
                    if (response.results != null && response.results.Length > 0)
                    {
                        OnHandTrackingDataReceived?.Invoke(response.results);
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[ARD] Hand Tracking 데이터 파싱 오류: {e.Message}");
                }
            }
        }
    }
    
    /// <summary>
    /// SLAM Trajectory 데이터 가져오기
    /// </summary>
    private IEnumerator FetchSlamTrajectoryData()
    {
        string url = $"{SlamTrajectoryEndpoint}?ordering=-timestamp&page_size={maxDataPerRequest}";
        
        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            request.timeout = 2;
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    var response = JsonConvert.DeserializeObject<PaginatedResponse<SlamTrajectoryData>>(request.downloadHandler.text);
                    if (response.results != null && response.results.Length > 0)
                    {
                        OnSlamTrajectoryDataReceived?.Invoke(response.results);
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[ARD] SLAM Trajectory 데이터 파싱 오류: {e.Message}");
                }
            }
        }
    }
    
    private void OnDestroy()
    {
        if (isStreaming)
        {
            StartCoroutine(StopStreaming());
        }
    }
    
    // Public 메서드들 (Unity Inspector나 다른 스크립트에서 호출)
    public void StartStreamingManual() => StartCoroutine(StartStreaming());
    public void StopStreamingManual() => StartCoroutine(StopStreaming());
    public void TestConnectionManual() => StartCoroutine(TestConnection());
}

// 데이터 구조체들 (JSON 직렬화용)
[Serializable]
public class StreamingRequest
{
    public int duration;
    public string stream_type;
}

[Serializable]
public class StreamingResponse
{
    public string status;
    public string message;
    public int duration;
    public string stream_type;
    public string timestamp;
}

[Serializable]
public class PaginatedResponse<T>
{
    public int count;
    public string next;
    public string previous;
    public T[] results;
}

[Serializable]
public class EyeGazeData
{
    public int id;
    public string timestamp;
    public string gaze_type;
    public float yaw;
    public float pitch;
    public float depth_m;
    public float confidence;
    public GazeDirection gaze_direction;
}

[Serializable]
public class GazeDirection
{
    public float x;
    public float y;
    public float z;
}

[Serializable]
public class HandTrackingData
{
    public int id;
    public string timestamp;
    public object left_hand_landmarks;
    public object right_hand_landmarks;
    public bool has_left_hand;
    public bool has_right_hand;
}

[Serializable]
public class SlamTrajectoryData
{
    public int id;
    public string timestamp;
    public Position position;
    public float[][] transform_matrix;
}

[Serializable]
public class Position
{
    public float x;
    public float y;
    public float z;
}