"""
Views for Live Study Rooms
"""

import uuid
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StudyRoom, RoomParticipant, RoomMessage, RoomRecording
from .serializers import (
    StudyRoomSerializer,
    StudyRoomCreateSerializer,
    RoomParticipantSerializer,
    RoomMessageSerializer,
    RoomRecordingSerializer,
)


class RoomListCreateView(generics.ListCreateAPIView):
    """List all study rooms or create a new room"""
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StudyRoomCreateSerializer
        return StudyRoomSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StudyRoom.objects.none()

        queryset = StudyRoom.objects.exclude(status=StudyRoom.RoomStatus.ENDED)
        
        # Filter by room type
        room_type = self.request.query_params.get('type')
        if room_type:
            queryset = queryset.filter(room_type=room_type)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.select_related('host', 'study_group').order_by('-created_at')


class RoomDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a study room"""
    queryset = StudyRoom.objects.all()
    serializer_class = StudyRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudyRoom.objects.all()


class JoinRoomView(APIView):
    """Join a study room"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            room = StudyRoom.objects.exclude(status=StudyRoom.RoomStatus.ENDED).get(pk=pk)
        except StudyRoom.DoesNotExist:
            return Response(
                {'error': 'Room not found or not active'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if room is at capacity
        active_participants = room.participants.filter(
            left_at__isnull=True,
            status=RoomParticipant.Status.CONNECTED,
        ).count()
        if room.max_participants and active_participants >= room.max_participants:
            return Response(
                {'error': 'Room is at capacity'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user is already in the room
        participant, created = RoomParticipant.objects.get_or_create(
            room=room,
            user=request.user,
            defaults={
                'status': RoomParticipant.Status.CONNECTED,
            }
        )

        if not created:
            # Reactivate if already joined but was inactive
            participant.status = RoomParticipant.Status.CONNECTED
            participant.left_at = None
            participant.save(update_fields=['status', 'left_at'])

        serializer = RoomParticipantSerializer(participant)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LeaveRoomView(APIView):
    """Leave a study room"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            participant = RoomParticipant.objects.get(
                room__pk=pk,
                user=request.user,
                left_at__isnull=True,
            )
        except RoomParticipant.DoesNotExist:
            return Response(
                {'error': 'You are not a participant in this room'},
                status=status.HTTP_404_NOT_FOUND
            )

        participant.status = RoomParticipant.Status.DISCONNECTED
        participant.left_at = timezone.now()
        participant.save(update_fields=['status', 'left_at'])

        return Response({'message': 'Left room successfully'}, status=status.HTTP_200_OK)


class RoomParticipantsView(generics.ListAPIView):
    """List all participants in a room"""
    serializer_class = RoomParticipantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RoomParticipant.objects.none()
        room_id = self.kwargs.get('pk')
        if not room_id:
            return RoomParticipant.objects.none()
        return RoomParticipant.objects.filter(
            room__pk=room_id,
            left_at__isnull=True,
        ).select_related('user')


class RoomMessagesView(generics.ListCreateAPIView):
    """List messages or send a message in a room"""
    serializer_class = RoomMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RoomMessage.objects.none()
        room_id = self.kwargs.get('pk')
        if not room_id:
            return RoomMessage.objects.none()
        return RoomMessage.objects.filter(
            room__pk=room_id
        ).select_related('user').order_by('-created_at')[:100]

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            room_id=self.kwargs['pk']
        )


class StartRecordingView(APIView):
    """Start recording a room"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            room = StudyRoom.objects.get(pk=pk)
        except StudyRoom.DoesNotExist:
            return Response(
                {'error': 'Room not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is host
        if room.host != request.user:
            return Response(
                {'error': 'Only the host can start recording'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if room supports recording
        if not room.is_recording_enabled:
            return Response(
                {'error': 'Recording is not enabled for this room'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if RoomRecording.objects.filter(
            room=room,
            status=RoomRecording.Status.RECORDING,
        ).exists():
            return Response(
                {'error': 'Room is already being recorded'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create recording record
        recording = RoomRecording.objects.create(
            room=room,
            recorded_by=request.user,
            file_url=f'/recordings/{room.id}/{uuid.uuid4()}.webm',
            status=RoomRecording.Status.RECORDING,
        )

        return Response(
            RoomRecordingSerializer(recording).data,
            status=status.HTTP_201_CREATED
        )


class StopRecordingView(APIView):
    """Stop recording a room"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            room = StudyRoom.objects.get(pk=pk)
        except StudyRoom.DoesNotExist:
            return Response(
                {'error': 'Room not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is host
        if room.host != request.user:
            return Response(
                {'error': 'Only the host can stop recording'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Update recording record
        recording = RoomRecording.objects.filter(
            room=room,
            status=RoomRecording.Status.RECORDING,
        ).first()

        if not recording:
            return Response(
                {'error': 'Room is not being recorded'},
                status=status.HTTP_400_BAD_REQUEST
            )

        recording.status = RoomRecording.Status.COMPLETED
        recording.save(update_fields=['status'])

        return Response({'message': 'Recording stopped'}, status=status.HTTP_200_OK)


class ActiveRoomsView(generics.ListAPIView):
    """List all currently active rooms"""
    serializer_class = StudyRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StudyRoom.objects.none()
        return StudyRoom.objects.filter(
            status=StudyRoom.RoomStatus.ACTIVE,
        ).select_related('host').order_by('-created_at')[:50]


class MyRoomsView(generics.ListAPIView):
    """List rooms the current user is participating in"""
    serializer_class = StudyRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return StudyRoom.objects.none()
        # Get rooms where user is host or active participant
        participant_room_ids = RoomParticipant.objects.filter(
            user=self.request.user,
            left_at__isnull=True,
            status=RoomParticipant.Status.CONNECTED,
        ).values_list('room_id', flat=True)

        return StudyRoom.objects.filter(
            Q(host=self.request.user) | Q(id__in=participant_room_ids)
        ).exclude(
            status=StudyRoom.RoomStatus.ENDED
        ).select_related('host').order_by('-created_at')
