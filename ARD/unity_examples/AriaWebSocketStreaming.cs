/*
Unity C# WebSocket Client for Real-time Aria Streaming
실시간 WebSocket을 통한 Aria 이미지 스트리밍

Installation:
1. Install "WebSocket Sharp" or "NativeWebSocket" Unity package
2. Add this script to GameObject in Unity scene
3. Configure server URL and start streaming

Features:
- Real-time frame reception via WebSocket
- Automatic texture update
- Performance monitoring
- Error handling and reconnection
*/

using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using WebSocketSharp; // or use NativeWebSocket
using Newtonsoft.Json;

public class AriaWebSocketStreaming : MonoBehaviour
{
    [Header("WebSocket Configuration")]
    public string serverHost = "localhost";
    public int serverPort = 8000;
    public string sessionId = "unity-live-session";
    
    [Header("Unity Components")]
    public RawImage targetImage;
    public Text statusText;
    public Text fpsText;
    
    [Header("Streaming Settings")]
    public bool autoStart = true;
    public StreamQuality quality = StreamQuality.Medium;
    
    public enum StreamQuality { Low, Medium, High, Auto }
    
    private WebSocket webSocket;
    private bool isConnected = false;
    private bool isStreaming = false;
    
    // Performance tracking
    private int frameCount = 0;
    private float lastFpsUpdate = 0f;
    private float currentFps = 0f;
    
    // Frame data classes
    [Serializable]
    public class WebSocketMessage
    {
        public string type;
        public object data;
    }
    
    [Serializable]
    public class FrameData
    {
        public string frame_id;
        public string timestamp;
        public string image_data; // Base64 encoded JPEG
        public int size_bytes;
        public string format;
        public string stream_type;
        public string source;
    }
    
    [Serializable]
    public class StreamConfig
    {
        public bool rgb = true;
        public bool slam = false;
        public string quality = "medium";
    }
    
    void Start()
    {
        InitializeWebSocket();
        if (autoStart)
        {
            ConnectToServer();
        }
    }
    
    void InitializeWebSocket()
    {
        string wsUrl = $"ws://{serverHost}:{serverPort}/ws/unity/stream/{sessionId}/";
        
        webSocket = new WebSocket(wsUrl);
        
        webSocket.OnOpen += OnWebSocketOpen;
        webSocket.OnMessage += OnWebSocketMessage;
        webSocket.OnError += OnWebSocketError;  
        webSocket.OnClose += OnWebSocketClose;
        
        UpdateStatus("WebSocket initialized");
        Debug.Log($"WebSocket URL: {wsUrl}");
    }
    
    public void ConnectToServer()
    {
        if (webSocket != null && !isConnected)
        {
            UpdateStatus("Connecting to server...");
            webSocket.Connect();
        }
    }
    
    public void DisconnectFromServer()
    {
        if (webSocket != null && isConnected)
        {
            StopStreaming();
            webSocket.Close();
        }
    }
    
    private void OnWebSocketOpen(object sender, EventArgs e)
    {
        isConnected = true;
        UpdateStatus("✅ Connected to Aria server");
        Debug.Log("WebSocket connected successfully");
    }
    
    private void OnWebSocketMessage(object sender, MessageEventArgs e)
    {
        try
        {
            var messageData = JsonConvert.DeserializeObject<dynamic>(e.Data);
            string messageType = messageData.type;
            
            switch (messageType)
            {
                case "connection_established":
                    HandleConnectionEstablished(messageData);
                    break;
                case "streaming_started":
                    HandleStreamingStarted(messageData);
                    break;
                case "real_time_frame":
                    HandleRealTimeFrame(messageData);
                    break;
                case "streaming_stopped":
                    HandleStreamingStopped(messageData);
                    break;
                case "error":
                    HandleError(messageData);
                    break;
                default:
                    Debug.Log($"Unknown message type: {messageType}");
                    break;
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error processing WebSocket message: {ex.Message}");
        }
    }
    
    private void HandleConnectionEstablished(dynamic data)
    {
        UpdateStatus("🎯 Connection established with Aria server");
        
        // Auto-start streaming
        if (autoStart)
        {
            StartStreaming();
        }
    }
    
    private void HandleStreamingStarted(dynamic data)
    {
        isStreaming = true;
        UpdateStatus("🚀 Real-time streaming active");
        Debug.Log("Streaming started successfully");
    }
    
    private void HandleRealTimeFrame(dynamic data)
    {
        try
        {
            string frameId = data.frame_id;
            string imageBase64 = data.image_data;
            int sizeBytes = data.size_bytes;
            
            // Convert Base64 to Texture2D
            byte[] imageBytes = Convert.FromBase64String(imageBase64);
            Texture2D texture = new Texture2D(2, 2);
            
            if (texture.LoadImage(imageBytes))
            {
                // Update UI on main thread
                if (targetImage != null)
                {
                    targetImage.texture = texture;
                }
                
                // Update performance metrics
                frameCount++;
                UpdateFPS();
                
                Debug.Log($"Frame received: {frameId} ({sizeBytes} bytes)");
            }
            else
            {
                Debug.LogError($"Failed to load image from frame: {frameId}");
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error processing frame: {ex.Message}");
        }
    }
    
    private void HandleStreamingStopped(dynamic data)
    {
        isStreaming = false;
        UpdateStatus("🛑 Streaming stopped");
        Debug.Log("Streaming stopped");
    }
    
    private void HandleError(dynamic data)
    {
        string errorMessage = data.message;
        UpdateStatus($"❌ Error: {errorMessage}");
        Debug.LogError($"WebSocket error: {errorMessage}");
    }
    
    public void StartStreaming()
    {
        if (isConnected && !isStreaming)
        {
            var startCommand = new
            {
                type = "start_streaming",
                config = new StreamConfig
                {
                    rgb = true,
                    slam = false,
                    quality = quality.ToString().ToLower()
                }
            };
            
            string json = JsonConvert.SerializeObject(startCommand);
            webSocket.Send(json);
            
            UpdateStatus("📤 Starting streaming...");
        }
    }
    
    public void StopStreaming()
    {
        if (isConnected && isStreaming)
        {
            var stopCommand = new { type = "stop_streaming" };
            string json = JsonConvert.SerializeObject(stopCommand);
            webSocket.Send(json);
            
            UpdateStatus("📤 Stopping streaming...");
        }
    }
    
    private void OnWebSocketError(object sender, WebSocketSharp.ErrorEventArgs e)
    {
        UpdateStatus($"❌ WebSocket Error: {e.Message}");
        Debug.LogError($"WebSocket error: {e.Message}");
    }
    
    private void OnWebSocketClose(object sender, CloseEventArgs e)
    {
        isConnected = false;
        isStreaming = false;
        UpdateStatus("🔌 Disconnected from server");
        Debug.Log($"WebSocket closed: {e.Reason}");
    }
    
    private void UpdateStatus(string message)
    {
        if (statusText != null)
        {
            statusText.text = message;
        }
        Debug.Log($"Status: {message}");
    }
    
    private void UpdateFPS()
    {
        if (Time.time - lastFpsUpdate >= 1.0f)
        {
            currentFps = frameCount / (Time.time - lastFpsUpdate);
            frameCount = 0;
            lastFpsUpdate = Time.time;
            
            if (fpsText != null)
            {
                fpsText.text = $"FPS: {currentFps:F1}";
            }
        }
    }
    
    void OnDestroy()
    {
        if (webSocket != null)
        {
            webSocket.Close();
        }
    }
    
    // UI Button handlers
    public void OnConnectButtonClick()
    {
        ConnectToServer();
    }
    
    public void OnDisconnectButtonClick()
    {
        DisconnectFromServer();
    }
    
    public void OnStartStreamingButtonClick()
    {
        StartStreaming();
    }
    
    public void OnStopStreamingButtonClick()
    {
        StopStreaming();
    }
}