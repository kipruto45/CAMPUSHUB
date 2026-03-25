"""
Tests for notes app.
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notes.models import Note, NoteShare, NoteVersion, NotePresence, NoteLock

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestNoteModel:
    """Tests for Note model."""

    def test_note_creation(self, user):
        """Test note creation."""
        note = Note.objects.create(
            title="Test Note",
            content="Test content",
            owner=user,
        )
        assert note.id is not None
        assert note.title == "Test Note"
        assert note.status == Note.NoteStatus.DRAFT

    def test_note_str(self, user):
        """Test note string representation."""
        note = Note.objects.create(
            title="Test Note",
            owner=user,
        )
        assert "Test Note" in str(note)


@pytest.mark.django_db
class TestNoteShareModel:
    """Tests for NoteShare model."""

    def test_note_share_creation(self, user):
        """Test note share creation."""
        note = Note.objects.create(
            title="Test Note",
            owner=user,
        )
        user2 = User.objects.create_user(
            email="test2@example.com",
            password="testpass123",
        )
        share = NoteShare.objects.create(
            note=note,
            user=user2,
            permission=NoteShare.Permission.VIEW,
        )
        assert share.id is not None
        assert share.permission == NoteShare.Permission.VIEW


@pytest.mark.django_db
class TestNoteVersionModel:
    """Tests for NoteVersion model."""

    def test_note_version_creation(self, user):
        """Test note version creation."""
        note = Note.objects.create(
            title="Test Note",
            content="Test content",
            owner=user,
        )
        version = NoteVersion.objects.create(
            note=note,
            title="Test Note",
            content="Test content",
            version_number=1,
            created_by=user,
        )
        assert version.id is not None
        assert version.version_number == 1


@pytest.mark.django_db
class TestNotePresenceModel:
    """Tests for NotePresence model."""

    def test_note_presence_creation(self, user):
        """Test note presence creation."""
        note = Note.objects.create(
            title="Test Note",
            owner=user,
        )
        presence = NotePresence.objects.create(
            note=note,
            user=user,
            activity=NotePresence.ActivityType.EDITING,
        )
        assert presence.id is not None
        assert presence.activity == NotePresence.ActivityType.EDITING


@pytest.mark.django_db
class TestNoteLockModel:
    """Tests for NoteLock model."""

    def test_note_lock_creation(self, user):
        """Test note lock creation."""
        from datetime import timedelta
        
        note = Note.objects.create(
            title="Test Note",
            owner=user,
        )
        lock = NoteLock.objects.create(
            note=note,
            user=user,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        assert lock.id is not None
        assert lock.is_expired is False