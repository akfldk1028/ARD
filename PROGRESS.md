자 시댕아 이제 Kafka 폴더를 만들고 consumer 하고 producer 를 만들어  지금 스트리밍을하기에는 너무많은 데이터가 들어가서 터져서그래  리눅스로 kafka 설치하고  순차적으로생각해




https://facebookresearch.github.io/projectaria_tools/docs/ARK/sdk/samples/device_stream#code-walkthrough
https://facebookresearch.github.io/projectaria_tools/docs/ARK/sdk/samples/streaming_subscribe

https://facebookresearch.github.io/projectaria_tools/docs/ARK/sdk/samples/device_recording

https://facebookresearch.github.io/projectaria_tools/docs/ARK/sdk/samples/device_stream



https://facebookresearch.github.io/projectaria_tools/docs/ARK/sdk/samples/undistort_rgb_image


https://facebookresearch.github.io/projectaria_tools/docs/ARK/sdk/samples/ticsync_sample

myenv로 리눅스 가상환경키고 ipynb 랑 공식문서 제대로봐서 하나의 데이터로 동시스트리밍가능하게 해봐 이 경로에 D:\Data\05_CGXR\ARD\ARD_Backend\ARD\aria_sessions

그리고 유지보수편하게 rest api 로 하고 urls 하고 views 를 깔끔하게 짜야해 순차적으로 하나하나

ipynb 데이터 받아서 동시스트리밍가능하게


myenv로 리눅스 가상환경키고 테스트도 가능한거아니까 테스트도하고 


--------------
sh(cd ARD && source ../myenv/bin/activate && daphne -p 8000 ARD.asgi:application)

와ㅣ 시발 까먹을뻔 명령어 이거다
동현아 정신차려
------------------------------------

\aria_sessions\templates\aria_sessions\streaming_test.html with 1 addition and 1 removal
       159                    streams: ['camera-rgb', 'camera-slam-left', 'camera-slam-right'], 




● Bash(cd "D:\Data\05_CGXR\ARD\ARD_Backend" && source myenv/bin/activate && python
      ARD/aria_sessions/vrs_diagnostic.py)
  ⎿  Error: [ProgressLogger][INFO]: 2025-08-05 22:19:51: Opening                             
     D:\Data\05_CGXR\ARD\ARD_Backend\ARD\aria_sessions\data\sample.vrs...                    
     [MultiRecordFileReader][DEBUG]: Opened file                                             
     'D:\Data\05_CGXR\ARD\ARD_Backend\ARD\aria_sessions\data\sample.vrs' and assigned to     
     reader #0                                                                               
     [VrsDataProvider][INFO]: streamId 211-1/camera-et activated                             
     [VrsDataProvider][INFO]: streamId 214-1/camera-rgb activated                            
     [VrsDataProvider][INFO]: streamId 231-1/mic activated                                   
     [VrsDataProvider][INFO]: streamId 247-1/baro0 activated                                 
     [VrsDataProvider][INFO]: streamId 281-1/gps activated                                   
     [VrsDataProvider][INFO]: streamId 282-1/wps activated                                   
     [VrsDataProvider][INFO]: streamId 283-1/bluetooth activated                             
     [VrsDataProvider][WARNING]: Unsupported TimeSync mode: APP, ignoring.                   
     … +24 lines (ctrl+r to see all)                                                         

● I can see the output before the Unicode error! The VRS file DOES contain many sensor       
  types:

  - camera-et (eye tracking)
  - camera-rgb
  - mic (microphone/audio)
  - baro0 (barometer)
  - gps
  - wps, bluetooth
  - camera-slam-left, camera-slam-right
  - imu-right, imu-left (IMU sensors!)
  - mag0 (magnetometer!)

  The user was absolutely right! The VRS file contains ALL the sensor types. Let me fix      
  the Unicode issue and run the diagnostic again:

● Update(ARD\aria_sessions\vrs_diagnostic.py)
  ⎿  Updated ARD\aria_sessions\vrs_diagnostic.py with 1 addition and 1 removal
       20            print("❌ 유효하지 않은 VRS 데이터 프로바이더")                          
       21            return                                                                  
       22                                                                                    
       23 -      print("✅ 데이터 프로바이더 생성 성공")
       23 +      print("OK 데이터 프로바이더 생성 성공")
       24                                                                                    
       25        # 2. 모든 스트림 조회 (ipynb 패턴)                                          
       26        print("\n2. 모든 스트림 조회...")                                           

● Let me replace all Unicode symbols to fix the encoding issue:

● Update(ARD\aria_sessions\vrs_diagnostic.py)
  ⎿  Updated ARD\aria_sessions\vrs_diagnostic.py with 1 addition and 1 removal
       17        print("\n1. 데이터 프로바이더 생성 중...")                                  
       18        provider = data_provider.create_vrs_data_provider(vrs_file_path)            
       19        if not provider:                                                            
       20 -          print("❌ 유효하지 않은 VRS 데이터 프로바이더")
       20 +          print("ERROR: 유효하지 않은 VRS 데이터 프로바이더")
       21            return                                                                  
       22                                                                                    
       23        print("OK 데이터 프로바이더 생성 성공")                                     

● Update(ARD\aria_sessions\vrs_diagnostic.py)
  ⎿  Updated ARD\aria_sessions\vrs_diagnostic.py with 1 addition and 1 removal
       26        print("\n2. 모든 스트림 조회...")                                           
       27        try:                                                                        
       28            all_streams = provider.get_all_streams()                                
       29 -          print(f"✅ 총 {len(all_streams)}개 스트림 발견")
       29 +          print(f"OK 총 {len(all_streams)}개 스트림 발견")
       30                                                                                    
       31            stream_summary = {}                                                     
       32            for stream_id in all_streams:                                           

● Let me create a simpler version without Unicode symbols:

● Write(ARD\aria_sessions\simple_diagnostic.py)
  ⎿  Wrote 1 lines to ARD\aria_sessions\simple_diagnostic.py
     #!/usr/bin/env python3                                                                  
     """                                                                                     
     Simple VRS diagnostic without Unicode symbols                                           
     """                                                                                     
     import os
     import sys
     from projectaria_tools.core import data_provider
     from projectaria_tools.core.sensor_data import TimeDomain
     from projectaria_tools.core.stream_id import RecordableTypeId, StreamId

● Bash(cd "D:\Data\05_CGXR\ARD\ARD_Backend" && source myenv/bin/activate && python
      ARD/aria_sessions/simple_diagnostic.py)
  ⎿ === VRS File Diagnostic: D:\Data\05_CGXR\ARD\ARD_Backend\ARD\aria_sessions\data\samp     
    le.vrs ===
    … +55 lines (ctrl+r to expand)


● Perfect! I can see the critical information before the error. The VRS file contains        
  ALL the sensor types the user mentioned:

  Available streams (12 total):
  - camera-et (211-1): 123 data points - Eye tracking camera ✅
  - camera-rgb (214-1): 123 data points - RGB camera ✅
  - mic (231-1): 286 data points - Microphone/Audio ✅
  - baro0 (247-1): 616 data points - Barometer ✅
  - gps (281-1): 13 data points - GPS ✅
  - wps (282-1): 50 data points
  - bluetooth (283-1): 24 data points
  - camera-slam-left (1201-1): 123 data points - SLAM camera ✅
  - camera-slam-right (1201-2): 123 data points - SLAM camera ✅
  - imu-right (1202-1): 12,319 data points - IMU sensor ✅
  - imu-left (1202-2): 9,763 data points - IMU sensor ✅
  - mag0 (1203-1): 121 data points - Magnetometer ✅




