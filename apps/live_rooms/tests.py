"""
Tests for live_rooms app.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.live_rooms.models import StudyRoom, RoomParticipant, RoomMessage, RoomRecording
from apps.live_rooms.serializers import StudyRoomCreateSerializer

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestStudyRoomModel:
    """Tests for StudyRoom model."""

    def test_study_room_creation(self, user):
        """Test study room creation."""
        room = StudyRoom.objects.create(
            name="Test Room",
            host=user,
        )
        assert room.id is not None
        assert room.name == "Test Room"
        assert room.status == StudyRoom.RoomStatus.WAITING

    def test_study_room_str(self, user):
        """Test study room string representation."""
        room = StudyRoom.objects.create(
            name="Test Room",
            host=user,
        )
        assert "Test Room" in str(room)

    def test_is_active_property(self, user):
        """Test is_active property."""
        room = StudyRoom.objects.create(
            name="Test Room",
            host=user,
            status=StudyRoom.RoomStatus.ACTIVE,
        )
        assert room.is_active is True

    def test_participant_count_property(self, user):
        """Test participant_count property."""
        room = StudyRoom.objects.create(
            name="Test Room",
            host=user,
        )
        assert room.participant_count == 1


@pytest.mark.django_db
class TestRoomParticipantModel:
    """Tests for RoomParticipant model."""

    def test_room_participant_creation(self, user):
        """Test room participant creation."""
        other_user = User.objects.create_user(
            email="another@example.com",
            password="testpass123",
        )
        room = StudyRoom.objects.create(
            name="Test Room",
            host=user,
        )
        participant = RoomParticipant.objects.create(
            room=room,
            user=other_user,
            role=RoomParticipant.Role.PARTICIPANT,
        )
        assert participant.id is not None
        assert participant.role == RoomParticipant.Role.PARTICIPANT

    def test_create_serializer_adds_host_as_connected_participant(self, user):
        request = APIRequestFactory().post("/api/live-rooms/rooms/", {})
        request.user = user

        serializer = StudyRoomCreateSerializer(
            data={
                "name": "Physics revision",
                "description": "Finals prep",
                "room_type": StudyRoom.RoomType.PUBLIC,
                "max_participants": 12,
                "is_recording_enabled": False,
                "is_screen_share_enabled": True,
            },
            context={"request": request},
        )

        assert serializer.is_valid(), serializer.errors
        room = serializer.save()
        participant = RoomParticipant.objects.get(room=room, user=user)

        assert participant.role == RoomParticipant.Role.HOST
        assert participant.status == RoomParticipant.Status.CONNECTED
        assert participant.left_at is None


@pytest.mark.django_db
class TestRoomMessageModel:
    """Tests for RoomMessage model."""

    def test_room_message_creation(self, user):
        """Test room message creation."""
        room = StudyRoom.objects.create(
            name="Test Room",
            host=user,
        )
        message = RoomMessage.objects.create(
            room=room,
            user=user,
            message="Hello world",
        )
        assert message.id is not None
        assert message.message == "Hello world"


@pytest.mark.django_db
class TestRoomRecordingModel:
    """Tests for RoomRecording model."""

    def test_room_recording_creation(self, user):
        """Test room recording creation."""
        room = StudyRoom.objects.create(
            name="Test Room",
            host=user,
        )
        recording = RoomRecording.objects.create(
            room=room,
            recorded_by=user,
            duration=300,
        )
        assert recording.id is not None
        assert recording.duration == 300
