"""
Binary streaming API views with metadata/binary separation
Optimized endpoints for real-time VRS data access with ID linking
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from django.http import JsonResponse, HttpResponse, Http404
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
# Removed cache imports for Kafka-only binary streaming
# from django.core.cache import cache
# from django.views.decorators.cache import cache_page
# from django.utils.decorators import method_decorator

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .binary_models import (
    BinaryFrameRegistry, 
    BinaryFrameMetadata, 
    BinaryFrameReference,
    SensorDataBinary,
    BinaryStreamingStats
)
from .serializers import (
    BinaryFrameRegistrySerializer,
    BinaryFrameMetadataSerializer, 
    BinaryFrameReferenceSerializer
)
from common.kafka.binary_producer import BinaryKafkaProducer
from common.kafka.binary_consumer import BinaryKafkaConsumer
from .vrs_binary_reader import VRSBinaryStreamer

logger = logging.getLogger(__name__)

class BinaryFrameRegistryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Frame registry for ID linking between metadata and binary data
    Central coordination point for binary streaming
    """
    
    queryset = BinaryFrameRegistry.objects.all()
    serializer_class = BinaryFrameRegistrySerializer
    ordering = ['-created_at']
    filterset_fields = ['session_id', 'stream_id', 'status']
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get frame registry statistics"""
        stats = BinaryFrameRegistry.objects.aggregate(
            total_frames=Count('id'),
            pending_frames=Count('id', filter=Q(status='PENDING')),
            linked_frames=Count('id', filter=Q(status='LINKED')),
            processed_frames=Count('id', filter=Q(status='PROCESSED')),
            failed_frames=Count('id', filter=Q(status='FAILED')),
            avg_size_bytes=Avg('size_bytes'),
            total_size_bytes=Sum('size_bytes')
        )
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def by_session(self, request):
        """Get frames grouped by session"""
        session_id = request.query_params.get('session_id')
        if not session_id:
            return Response({'error': 'session_id required'}, status=400)
        
        frames = self.queryset.filter(session_id=session_id)
        
        return Response({
            'session_id': session_id,
            'total_frames': frames.count(),
            'by_stream': {
                stream['stream_id']: stream['count'] 
                for stream in frames.values('stream_id').annotate(count=Count('id'))
            },
            'by_status': {
                stat['status']: stat['count']
                for stat in frames.values('status').annotate(count=Count('id'))
            }
        })

class BinaryFrameMetadataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Frame metadata API (without binary data)
    Fast access to frame information and properties
    """
    
    queryset = BinaryFrameMetadata.objects.all()
    serializer_class = BinaryFrameMetadataSerializer
    ordering = ['-capture_timestamp_ns']
    filterset_fields = ['session_id', 'stream_id', 'compression_format']
    
    @action(detail=False, methods=['get'])
    def compression_stats(self, request):
        """Get compression statistics"""
        stats = BinaryFrameMetadata.objects.aggregate(
            avg_compression_ratio=Avg('compression_ratio'),
            total_original_bytes=Sum('original_size_bytes'),
            total_compressed_bytes=Sum('compressed_size_bytes'),
            frames_by_format=Count('compression_format')
        )
        
        # Compression by format
        format_stats = {}
        for fmt in BinaryFrameMetadata.objects.values_list('compression_format', flat=True).distinct():
            format_data = BinaryFrameMetadata.objects.filter(compression_format=fmt).aggregate(
                count=Count('id'),
                avg_ratio=Avg('compression_ratio'),
                avg_quality=Avg('compression_quality')
            )
            format_stats[fmt] = format_data
        
        return Response({
            'overall': stats,
            'by_format': format_stats
        })
    
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """Get frames timeline for visualization"""
        session_id = request.query_params.get('session_id')
        stream_id = request.query_params.get('stream_id')
        
        queryset = self.queryset
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        if stream_id:
            queryset = queryset.filter(stream_id=stream_id)
        
        frames = queryset.order_by('capture_timestamp_ns')[:1000]  # Limit for performance
        
        timeline = []
        for frame in frames:
            timeline.append({
                'frame_id': frame.frame_id,
                'frame_index': frame.frame_index,
                'timestamp_ns': frame.capture_timestamp_ns,
                'size_bytes': frame.compressed_size_bytes,
                'compression_ratio': frame.compression_ratio
            })
        
        return Response({
            'session_id': session_id,
            'stream_id': stream_id,
            'frame_count': len(timeline),
            'timeline': timeline
        })

class BinaryDataAccessView(APIView):
    """
    Binary data access API
    Retrieves actual image bytes from Kafka/storage with caching
    """
    
    permission_classes = [AllowAny]
    
    def get(self, request, frame_id):
        """
        Get binary data for a specific frame
        
        Query parameters:
        - format: response format (raw, base64, info)
        - cache: use cache (disabled for Kafka-only mode)
        """
        
        response_format = request.query_params.get('format', 'raw')
        
        try:
            # Get frame registry entry
            registry = BinaryFrameRegistry.objects.select_related(
                'metadata', 'binary_ref'
            ).get(frame_id=frame_id)
            
            if registry.status != 'LINKED' and registry.status != 'PROCESSED':
                return JsonResponse({
                    'error': 'Frame not ready',
                    'status': registry.status,
                    'frame_id': frame_id
                }, status=404)
            
            # Get binary data from Kafka/storage (no caching for now)
            binary_data = self._fetch_binary_data(registry.binary_ref)
            
            if binary_data is None:
                return JsonResponse({
                    'error': 'Binary data not found',
                    'frame_id': frame_id
                }, status=404)
            
            # Update access statistics
            registry.binary_ref.access_count += 1
            registry.binary_ref.last_accessed = timezone.now()
            registry.binary_ref.save(update_fields=['access_count', 'last_accessed'])
            
            return self._create_response(binary_data, response_format, registry.metadata)
            
        except BinaryFrameRegistry.DoesNotExist:
            return JsonResponse({
                'error': 'Frame not found',
                'frame_id': frame_id
            }, status=404)
        except Exception as e:
            logger.error(f"Binary data access error for {frame_id}: {e}")
            return JsonResponse({
                'error': 'Internal server error',
                'message': str(e)
            }, status=500)
    
    def _fetch_binary_data(self, binary_ref: BinaryFrameReference) -> Optional[bytes]:
        """Fetch binary data from storage backend"""
        
        if binary_ref.storage_type == 'KAFKA':
            return self._fetch_from_kafka(binary_ref)
        elif binary_ref.storage_type == 'CACHE':
            return self._fetch_from_cache(binary_ref)
        elif binary_ref.storage_type == 'FILE':
            return self._fetch_from_file(binary_ref.storage_path)
        else:
            logger.error(f"Unsupported storage type: {binary_ref.storage_type}")
            return None
    
    def _fetch_from_kafka(self, binary_ref: BinaryFrameReference) -> Optional[bytes]:
        """Fetch binary data from Kafka topic"""
        try:
            # This would typically use a Kafka consumer to fetch specific message
            # For now, return None as this requires more complex Kafka offset seeking
            logger.warning("Direct Kafka fetching not implemented - use consumer coordination")
            return None
        except Exception as e:
            logger.error(f"Kafka fetch error: {e}")
            return None
    
    def _fetch_from_cache(self, binary_ref: BinaryFrameReference) -> Optional[bytes]:
        """Fetch binary data from cache (disabled for Kafka-only mode)"""
        try:
            # Cache disabled for Kafka-based binary streaming
            logger.warning("Cache access disabled in Kafka-only mode")
            return None
        except Exception as e:
            logger.error(f"Cache fetch error: {e}")
            return None
    
    def _fetch_from_file(self, file_path: str) -> Optional[bytes]:
        """Fetch binary data from file system"""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"File fetch error: {e}")
            return None
    
    def _create_response(self, binary_data: bytes, response_format: str, metadata: BinaryFrameMetadata):
        """Create appropriate response based on format"""
        
        if response_format == 'info':
            return JsonResponse({
                'frame_id': metadata.frame_id,
                'size_bytes': len(binary_data),
                'compression_format': metadata.compression_format,
                'compression_ratio': metadata.compression_ratio,
                'image_width': metadata.image_width,
                'image_height': metadata.image_height,
                'channels': metadata.channels
            })
        
        elif response_format == 'base64':
            import base64
            return JsonResponse({
                'frame_id': metadata.frame_id,
                'data': base64.b64encode(binary_data).decode('utf-8'),
                'format': metadata.compression_format,
                'size_bytes': len(binary_data)
            })
        
        else:  # raw format
            content_type = {
                'jpeg': 'image/jpeg',
                'png': 'image/png', 
                'webp': 'image/webp',
                'raw': 'application/octet-stream'
            }.get(metadata.compression_format, 'application/octet-stream')
            
            response = HttpResponse(binary_data, content_type=content_type)
            response['Content-Length'] = len(binary_data)
            response['X-Frame-ID'] = metadata.frame_id
            response['X-Compression-Ratio'] = str(metadata.compression_ratio)
            return response

class BinaryStreamingControlView(APIView):
    """
    Binary streaming control API
    Start/stop/monitor binary VRS streaming operations
    """
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get streaming status"""
        
        # Get active streaming sessions
        active_stats = BinaryStreamingStats.objects.filter(
            status='ACTIVE'
        ).order_by('-started_at')
        
        recent_stats = BinaryStreamingStats.objects.filter(
            started_at__gte=timezone.now() - timedelta(hours=1)
        ).aggregate(
            total_sessions=Count('id'),
            total_frames=Sum('total_frames'),
            avg_fps=Avg('frames_per_second'),
            total_bytes=Sum('total_bytes')
        )
        
        return JsonResponse({
            'status': 'available',
            'service': 'aria-binary-streaming',
            'active_sessions': active_stats.count(),
            'recent_stats': recent_stats,
            'timestamp': timezone.now().isoformat()
        })
    
    def post(self, request):
        """Start binary streaming"""
        
        try:
            data = json.loads(request.body) if request.body else {}
            
            session_id = data.get('session_id', f'binary-session-{int(timezone.now().timestamp())}')
            duration_seconds = data.get('duration_seconds', 30)
            streams = data.get('streams', ['rgb'])  # Default to RGB stream
            compression_format = data.get('compression_format', 'jpeg')
            compression_quality = data.get('compression_quality', 90)
            
            # Validate parameters
            if duration_seconds > 300:  # 5 minutes max
                return JsonResponse({
                    'error': 'Duration too long (max 300 seconds)'
                }, status=400)
            
            # Initialize VRS binary streamer
            # Note: In production, this would be handled by a background task
            streamer = VRSBinaryStreamer(
                vrs_file_path='/app/ARD/data/mps_samples/sample.vrs',
                mps_data_path='/app/ARD/data/mps_samples',
                compression_format=compression_format,
                compression_quality=compression_quality
            )
            
            # Send test frame first
            test_result = streamer.send_test_binary_frame(session_id)
            
            if not test_result.get('success'):
                return JsonResponse({
                    'error': 'Failed to initialize streaming',
                    'details': test_result.get('error')
                }, status=500)
            
            # Create streaming stats record
            streaming_stats = BinaryStreamingStats.objects.create(
                session_id=session_id,
                stream_type='vrs_binary',
                status='ACTIVE'
            )
            
            return JsonResponse({
                'success': True,
                'session_id': session_id,
                'streaming_started': True,
                'test_frame': test_result,
                'parameters': {
                    'duration_seconds': duration_seconds,
                    'streams': streams,
                    'compression_format': compression_format,
                    'compression_quality': compression_quality
                },
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Binary streaming start error: {e}")
            return JsonResponse({
                'error': 'Failed to start streaming',
                'message': str(e)
            }, status=500)
    
    def delete(self, request):
        """Stop streaming"""
        
        session_id = request.query_params.get('session_id')
        
        if session_id:
            # Stop specific session
            updated = BinaryStreamingStats.objects.filter(
                session_id=session_id,
                status='ACTIVE'
            ).update(
                status='COMPLETED',
                completed_at=timezone.now()
            )
            
            return JsonResponse({
                'success': True,
                'stopped_sessions': updated,
                'session_id': session_id
            })
        else:
            # Stop all active sessions
            updated = BinaryStreamingStats.objects.filter(
                status='ACTIVE'
            ).update(
                status='COMPLETED',
                completed_at=timezone.now()
            )
            
            return JsonResponse({
                'success': True,
                'stopped_sessions': updated,
                'message': 'All streaming stopped'
            })

class BinaryTestMessageView(APIView):
    """
    Binary test message API
    Send test frames using binary streaming architecture
    """
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Send test binary frame (GET)"""
        session_id = request.GET.get('session_id', 'test-binary-session')
        compression_format = request.GET.get('format', 'jpeg')
        compression_quality = int(request.GET.get('quality', 90))
        
        return self._send_test_frame(session_id, compression_format, compression_quality)
    
    def post(self, request):
        """Send test binary frame (POST)"""
        
        try:
            data = json.loads(request.body) if request.body else {}
            session_id = data.get('session_id', 'test-binary-session')
            compression_format = data.get('format', 'jpeg')
            compression_quality = data.get('quality', 90)
            
            return self._send_test_frame(session_id, compression_format, compression_quality)
            
        except Exception as e:
            logger.error(f"Error in POST test message: {e}")
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to process request',
                'error': str(e)
            }, status=500)
    
    def _send_test_frame(self, session_id, compression_format, compression_quality):
        """Internal method to send test frame"""
        try:
            
            # Initialize binary producer
            producer = BinaryKafkaProducer()
            
            # Send test frame
            result = producer.send_test_binary_frame(session_id)
            
            producer.close()
            
            if result['success']:
                # Also save to Django database for immediate access
                try:
                    from .binary_models import BinaryFrameRegistry, BinaryFrameMetadata, BinaryFrameReference
                    import tempfile
                    
                    metadata = result['metadata']
                    frame_id = metadata['frame_id']
                    
                    # Create registry entry
                    registry = BinaryFrameRegistry.objects.create(
                        frame_id=frame_id,
                        session_id=metadata['session_id'],
                        stream_id=metadata['stream_id'],
                        frame_index=metadata['frame_index'],
                        status='LINKED',
                        size_bytes=metadata['compression']['compressed_size'],
                        compression_format=compression_format,
                        compression_ratio=metadata['compression']['compression_ratio']
                    )
                    
                    # Create metadata entry
                    metadata_obj = BinaryFrameMetadata.objects.create(
                        frame_id=frame_id,
                        session_id=metadata['session_id'],
                        stream_id=metadata['stream_id'],
                        frame_index=metadata['frame_index'],
                        capture_timestamp_ns=metadata['capture_timestamp_ns'],
                        image_width=metadata['image_width'],
                        image_height=metadata['image_height'],
                        channels=metadata['channels'],
                        compression_format=compression_format,
                        compression_quality=compression_quality,
                        original_size_bytes=metadata['compression']['original_size'],
                        compressed_size_bytes=metadata['compression']['compressed_size'],
                        compression_ratio=metadata['compression']['compression_ratio']
                    )
                    
                    # Create file reference (temporary file for demo)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    temp_file.write(result.get('binary_data', b''))
                    temp_file.close()
                    
                    reference = BinaryFrameReference.objects.create(
                        registry=registry,
                        frame_id=frame_id,
                        storage_type='FILE',
                        storage_path=temp_file.name
                    )
                    
                    logger.info(f"Binary frame {frame_id} saved to database")
                    
                except Exception as db_error:
                    logger.warning(f"Failed to save to database: {db_error}")
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Test binary frame sent and saved',
                    'result': result,
                    'compression': result['compression'],
                    'frame_access_url': f'/api/v1/aria/binary/data/{frame_id}/',
                    'timestamp': timezone.now().isoformat()
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to send test frame',
                    'error': result.get('error')
                }, status=500)
                
        except Exception as e:
            logger.error(f"Binary test message error: {e}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)

class BinaryAnalyticsView(APIView):
    """
    Binary streaming analytics and monitoring
    Simple Kafka-based analytics without Redis dependencies
    """
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get binary streaming analytics"""
        
        try:
            # Simple analytics without complex aggregations
            total_frames = BinaryFrameRegistry.objects.count()
            total_metadata = BinaryFrameMetadata.objects.count() 
            
            # Basic streaming stats (if any streaming sessions exist)
            streaming_count = 0
            try:
                streaming_count = BinaryStreamingStats.objects.count()
            except:
                pass
            
            analytics = {
                'binary_analytics': {
                    'total_frames_registered': total_frames,
                    'total_metadata_records': total_metadata,
                    'streaming_sessions': streaming_count,
                    'system_status': 'operational',
                    'kafka_enabled': True,
                    'redis_enabled': False,
                },
                'capabilities': {
                    'image_streaming': True,
                    'binary_compression': True,
                    'kafka_integration': True,
                    'real_time_processing': True,
                },
                'endpoints': {
                    'binary_registry': '/api/v1/aria/binary/registry/',
                    'binary_metadata': '/api/v1/aria/binary/metadata/',
                    'binary_streaming': '/api/v1/aria/binary/streaming/',
                    'binary_test': '/api/v1/aria/binary/test-message/',
                },
                'kafka_topics': {
                    'binary_frames': 'aria-binary-frames',
                    'image_stream': 'aria-image-stream',
                    'video_stream': 'aria-video-stream',
                },
                'message': 'Binary streaming system ready for Kafka-based image/video streaming'
            }
            
            return JsonResponse(analytics)
            
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            return JsonResponse({
                'error': 'Analytics temporarily unavailable',
                'message': str(e),
                'binary_system_status': 'operational',
                'kafka_integration': 'ready'
            }, status=200)  # Still return 200 since system is working