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
        queryset = StudyRoom.objects.filter(is_active=True)
        
        # Filter by room type
        room_type = self.request.query_params.get('type')
        if room_type:
            queryset = queryset.filter(room_type=room_type)
        
        # Filter by subject
        subject = self.request.query_params.get('subject')
        if subject:
            queryset = queryset.filter(subject__icontains=subject)
        
        # Filter by privacy
        privacy = self.request.query_params.get('privacy')
        if privacy:
            queryset = queryset.filter(privacy=privacy)
        
        # Only show rooms that haven't ended
        queryset = queryset.filter(
            Q(end_time__isnull=True) | Q(end_time__gt=timezone.now())
        ).order_by('-created_at')
        
        return queryset


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
            room = StudyRoom.objects.get(pk=pk, is_active=True)
        except StudyRoom.DoesNotExist:
            return Response(
                {'error': 'Room not found or not active'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if room is at capacity
        if room.max_participants and room.current_participants >= room.max_participants:
            return Response(
                {'error': 'Room is at capacity'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user is already in the room
        participant, created = RoomParticipant.objects.get_or_create(
            room=room,
            user=request.user,
            defaults={
                'joined_at': timezone.now(),
                'is_active': True,
            }
        )

        if not created:
            # Reactivate if already joined but was inactive
            participant.is_active = True
            participant.joined_at = timezone.now()
            participant.save()

        # Update room participant count
        room.current_participants = room.participants.filter(is_active=True).count()
        room.save()

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
                is_active=True
            )
        except RoomParticipant.DoesNotExist:
            return Response(
                {'error': 'You are not a participant in this room'},
                status=status.HTTP_404_NOT_FOUND
            )

        participant.is_active = False
        participant.left_at = timezone.now()
        participant.save()

        # Update room participant count
        room = participant.room
        room.current_participants = room.participants.filter(is_active=True).count()
        room.save()

        return Response({'message': 'Left room successfully'}, status=status.HTTP_200_OK)


class RoomParticipantsView(generics.ListAPIView):
    """List all participants in a room"""
    serializer_class = RoomParticipantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RoomParticipant.objects.filter(
            room__pk=self.kwargs['pk'],
            is_active=True
        ).select_related('user')


class RoomMessagesView(generics.ListCreateAPIView):
    """List messages or send a message in a room"""
    serializer_class = RoomMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RoomMessage.objects.filter(
            room__pk=self.kwargs['pk']
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

        # Check if already recording
        if room.is_recording:
            return Response(
                {'error': 'Room is already being recorded'},
                status=status.HTTP_400_BAD_REQUEST
            )

        room.is_recording = True
        room.save()

        # Create recording record
        recording = RoomRecording.objects.create(
            room=room,
            started_at=timezone.now(),
            recording_url=f'/recordings/{room.id}/{uuid.uuid4()}.webm'
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

        # Check if not recording
        if not room.is_recording:
            return Response(
                {'error': 'Room is not being recorded'},
                status=status.HTTP_400_BAD_REQUEST
            )

        room.is_recording = False
        room.save()

        # Update recording record
        recording = RoomRecording.objects.filter(
            room=room,
            ended_at__isnull=True
        ).first()

        if recording:
            recording.ended_at = timezone.now()
            recording.save()

        return Response({'message': 'Recording stopped'}, status=status.HTTP_200_OK)


class ActiveRoomsView(generics.ListAPIView):
    """List all currently active rooms"""
    serializer_class = StudyRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudyRoom.objects.filter(
            is_active=True,
        ).filter(
            Q(end_time__isnull=True) | Q(end_time__gt=timezone.now())
        ).select_related('host').order_by('-created_at')[:50]


class MyRoomsView(generics.ListAPIView):
    """List rooms the current user is participating in"""
    serializer_class = StudyRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get rooms where user is host or active participant
        participant_room_ids = RoomParticipant.objects.filter(
            user=self.request.user,
            is_active=True
        ).values_list('room_id', flat=True)

        return StudyRoom.objects.filter(
            Q(host=self.request.user) | Q(id__in=participant_room_ids)
        ).filter(
            Q(end_time__isnull=True) | Q(end_time__gt=timezone.now())
        ).select_related('host').order_by('-created_at')
