# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an ARD (Aria Real-time Data) system that processes real-time AR data from Project Aria devices using Django backend and Kafka for stream processing. The system uses Meta's official Project Aria sample data and documentation for testing before connecting to actual Aria devices, with eventual Unity client integration.

## Architecture

**Core Components:**
- **Django Backend**: Main application server with REST APIs
- **Kafka Streaming**: Real-time data processing pipeline with Zookeeper
- **MPS Integration**: Project Aria's Machine Perception Services for AR data processing
- **VRS Reader**: Handles Project Aria VRS (Virtual Reality Service) file format

**Django Apps Structure:**
- `streams/`: Kafka producers/consumers for real-time data processing
- `mps/`: Machine Perception Services integration
- `aria_sessions/`: AR session management
- `analytics/`: Data analysis and processing
- `datasets/`: Dataset management
- `devices/`: Device registration and management
- `storage/`: File and data storage management
- `core/`: Core utilities (MPS loaders, VRS handlers)

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source myenv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install django-filter  # Required for DRF filtering

# Run Django migrations
python ARD/manage.py migrate

# Create superuser for admin access
python ARD/manage.py createsuperuser
```



### Data Streaming with Sample Data
```bash
# Start Kafka consumer for all topics
python ARD/manage.py start_kafka_consumer

# Stream sample VRS data to Kafka
python ARD/manage.py stream_vrs_data --vrs-file ARD/data/mps_samples/sample.vrs --mps-data-path ARD/data/mps_samples

# Stream only MPS data from samples
python ARD/manage.py stream_vrs_data --vrs-file ARD/data/mps_samples/sample.vrs --mps-data-path ARD/data/mps_samples --stream-type mps --duration 60
```

### Django Commands
```bash
# Run development server
python ARD/manage.py runserver

# Create superuser
python ARD/manage.py createsuperuser

# Make migrations
python ARD/manage.py makemigrations

# Apply migrations
python ARD/manage.py migrate

# Collect static files
python ARD/manage.py collectstatic

# Django shell
python ARD/manage.py shell

# Check Django setup
python ARD/manage.py check

# Show migrations status
python ARD/manage.py showmigrations

# Download/update sample MPS data
python ARD/manage.py download_sample_data
```

## Meta Official Documentation & Sample Data

**Documentation Notebooks (`ARD/data/ipynb/`):**
- `dataprovider_quickstart_tutorial.ipynb`: Data provider usage and VRS file handling
- `mps_quickstart_tutorial.ipynb`: MPS data processing tutorial
- `sophus_quickstart_tutorial.ipynb`: Sophus library for 3D transformations
- `ticsync_tutorial.ipynb`: Time synchronization tutorial

**Sample Data Structure (`ARD/data/mps_samples/`):**
- `sample.vrs`: Sample VRS recording file
- `eye_gaze/`: Eye tracking data samples
  - `general_eye_gaze.csv`: General eye gaze tracking results
  - `personalized_eye_gaze.csv`: Personalized eye gaze results
- `hand_tracking/`: Hand tracking samples
  - `hand_tracking_results.csv`: Hand landmarks and poses
  - `wrist_and_palm_poses.csv`: Wrist and palm orientation data
- `slam/`: SLAM processing results
  - `closed_loop_trajectory.csv`: Device trajectory with loop closure
  - `open_loop_trajectory.csv`: Raw trajectory without loop closure
  - `semidense_observations.csv.gz`: Semi-dense SLAM observations
  - `semidense_points.csv.gz`: Semi-dense point cloud data
  - `online_calibration.jsonl`: Real-time calibration data

## Kafka Topics Architecture

**VRS Data Streams:**
- `vrs-raw-stream`: Raw VRS frame data from RGB/SLAM cameras
- `mps-eye-gaze-general`: General eye gaze tracking data
- `mps-eye-gaze-personalized`: Personalized eye gaze data
- `mps-hand-tracking`: Hand tracking landmarks and poses
- `mps-slam-trajectory`: SLAM trajectory and pose data
- `mps-slam-points`: SLAM point cloud data
- `analytics-real-time`: Real-time analytics results

## Key Files and Their Purpose

**Streaming Infrastructure:**
- `streams/consumers.py`: AriaKafkaConsumer - handles all incoming Kafka messages and database persistence
- `streams/producers.py`: AriaKafkaProducer - sends structured data to Kafka topics  
- `streams/vrs_reader.py`: VRSKafkaStreamer - reads VRS files and streams to Kafka using Project Aria tools

**Django REST API (Class-Based Architecture):**
- `streams/models.py`: Database models for all AR data types with relationships and indexing
- `streams/serializers.py`: DRF serializers with computed fields and validation
- `streams/views.py`: Class-based ViewSets for professional API endpoints with filtering/pagination
- `streams/admin.py`: Comprehensive Django Admin interface with custom displays and actions
- `streams/urls.py`: Router-based URL configuration for ViewSets and API endpoints

**Data Processing Pipeline:**
- Uses Meta's `projectaria_tools` for VRS file parsing and MPS data processing
- Streams data from sample files to Kafka topics for real-time processing simulation
- Database models track kafka_offset for message processing consistency

**Project Aria Integration:**
- Stream IDs: RGB("214-1"), SLAM Left("1201-1"), SLAM Right("1201-2"), Eye Tracking("211-1")
- Transform matrix serialization for SLAM data using Sophus library
- MPS data provider integration for eye gaze, hand tracking, and SLAM processing

## Development Workflow

1. **Start with Sample Data**: Use files in `ARD/data/mps_samples/` for initial testing
2. **Reference Official Tutorials**: Check Jupyter notebooks in `ARD/data/ipynb/` for implementation patterns
3. **Stream Processing**: Test Kafka pipeline with sample data before connecting real devices
4. **Unity Integration**: Backend prepares data streams for real-time Unity visualization

## REST API Endpoints (Class-Based)

### Main Data API (ViewSets)
```bash
# Session Management
GET    /api/streams/api/sessions/                    # List sessions with pagination
POST   /api/streams/api/sessions/                    # Create new session
GET    /api/streams/api/sessions/{id}/               # Session detail
PUT    /api/streams/api/sessions/{id}/               # Update session
POST   /api/streams/api/sessions/{id}/end_session/   # End session action
GET    /api/streams/api/sessions/{id}/statistics/    # Session statistics

# VRS Stream Data
GET    /api/streams/api/vrs-streams/                 # VRS stream data with filtering
GET    /api/streams/api/vrs-streams/{id}/            # VRS stream detail
GET    /api/streams/api/vrs-streams/stream_summary/  # Stream summary statistics

# Eye Gaze Data
GET    /api/streams/api/eye-gaze/                    # Eye gaze data with confidence filtering
GET    /api/streams/api/eye-gaze/{id}/               # Eye gaze detail
GET    /api/streams/api/eye-gaze/gaze_heatmap/       # Gaze heatmap data

# Hand Tracking Data
GET    /api/streams/api/hand-tracking/               # Hand tracking with presence filtering
GET    /api/streams/api/hand-tracking/{id}/          # Hand tracking detail
GET    /api/streams/api/hand-tracking/hand_statistics/ # Hand detection statistics

# SLAM Trajectory Data
GET    /api/streams/api/slam-trajectory/             # SLAM trajectory with position filtering
GET    /api/streams/api/slam-trajectory/{id}/        # SLAM trajectory detail
GET    /api/streams/api/slam-trajectory/trajectory_path/ # Full trajectory path

# Kafka Consumer Status
GET    /api/streams/api/kafka-status/                # Consumer status monitoring
GET    /api/streams/api/kafka-status/health_check/   # Kafka health check
```

### Streaming Control API
```bash
# Streaming Management
GET    /api/streams/api/streaming/                   # Get streaming status
POST   /api/streams/api/streaming/                   # Start VRS/MPS streaming
DELETE /api/streams/api/streaming/                   # Stop streaming

# Test Messages
POST   /api/streams/api/test-message/                # Send test message to Kafka
```

### Query Parameters
```bash
# Pagination
?page=1&page_size=20

# Search and Filtering
?search=keyword                                      # Search across relevant fields
?session=1&gaze_type=general                        # Filter by session and type
?min_confidence=0.8                                 # Minimum confidence threshold
?has_left_hand=true&has_right_hand=false           # Hand presence filtering

# Time Range Filtering
?start_time=2023-01-01T00:00:00Z&end_time=2023-01-02T00:00:00Z

# Position Filtering (SLAM)
?x_min=-1.0&x_max=1.0&y_min=-1.0&y_max=1.0

# Ordering
?ordering=-timestamp                                 # Sort by timestamp descending
?ordering=confidence                                 # Sort by confidence ascending
```

### Django Admin Interface
```bash
# Admin Dashboard
/admin/                                             # Main admin interface

# Model Administration
/admin/streams/ariasession/                         # Session management
/admin/streams/vrsstream/                           # VRS stream data
/admin/streams/eyegazedata/                         # Eye gaze administration
/admin/streams/handtrackingdata/                    # Hand tracking management
/admin/streams/slamtrajectorydata/                  # SLAM trajectory admin
/admin/streams/kafkaconsumerstatus/                 # Kafka status monitoring
```

## Testing Notes

- All streaming operations are asynchronous using asyncio
- Sample data streaming includes frame/data sampling to prevent overwhelming
- Consumer status tracking maintains processing state in database
- Error handling includes Kafka offset tracking for reliability
- Class-based ViewSets provide professional filtering, pagination, and search
- Admin interface includes visual data displays and bulk operations

## API Testing Commands

```bash
# Test API endpoints
python ARD/manage.py test_class_based_api

# Start development server
python ARD/manage.py runserver

# Access DRF browsable API
http://127.0.0.1:8000/api/streams/api/

# Access Django Admin
http://127.0.0.1:8000/admin/
```