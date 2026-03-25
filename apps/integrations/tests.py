"""
Comprehensive tests for integrations module.
Tests for Google Classroom and Microsoft Teams integrations.
"""

import pytest
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.integrations.google_classroom.models import (
    GoogleClassroomAccount,
    SyncedCourse,
    SyncedAssignment,
    SyncedSubmission,
    SyncedAnnouncement,
    SyncState as GoogleSyncState,
)

from apps.integrations.microsoft_teams.models import (
    MicrosoftTeamsAccount,
    SyncedTeam,
    SyncedChannel,
    SyncedAssignment as MSTeamsAssignment,
    SyncedSubmission as MSTeamsSubmission,
    SyncedAnnouncement as MSTeamsAnnouncement,
    SyncState as MSTeamsSyncState,
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        role='STUDENT'
    )


@pytest.fixture
def instructor(db):
    """Create an instructor user."""
    return User.objects.create_user(
        email='instructor@example.com',
        password='instructor123',
        role='INSTRUCTOR'
    )


# =========================
# Google Classroom Tests
# =========================

@pytest.mark.django_db
class TestGoogleClassroomAccount:
    """Tests for GoogleClassroomAccount model."""

    def test_create_account(self, user):
        """Test creating a Google Classroom account."""
        account = GoogleClassroomAccount.objects.create(
            user=user,
            google_user_id='google-123',
            email=user.email,
            access_token='access-token',
            refresh_token='refresh-token',
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        
        assert account.id is not None
        assert account.user == user
        assert account.google_user_id == 'google-123'
        assert account.sync_status == GoogleClassroomAccount.SyncStatus.ACTIVE
        assert str(account) == f"{user.email} - Google Classroom"

    def test_sync_statuses(self, user):
        """Test all sync status choices."""
        statuses = [
            GoogleClassroomAccount.SyncStatus.ACTIVE,
            GoogleClassroomAccount.SyncStatus.SYNCING,
            GoogleClassroomAccount.SyncStatus.ERROR,
            GoogleClassroomAccount.SyncStatus.DISCONNECTED,
        ]
        
        for status in statuses:
            account = GoogleClassroomAccount.objects.create(
                user=User.objects.create_user(email=f'{status}@example.com', password='test'),
                google_user_id=f'google-{status}',
                email=f'{status}@example.com',
                access_token='token',
                refresh_token='token',
                token_expires_at=timezone.now(),
                sync_status=status,
            )
            assert account.sync_status == status


@pytest.mark.django_db
class TestSyncedCourse:
    """Tests for SyncedCourse model."""

    def test_create_synced_course(self, user):
        """Test creating a synced course."""
        account = GoogleClassroomAccount.objects.create(
            user=user,
            google_user_id='google-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        course = SyncedCourse.objects.create(
            account=account,
            google_course_id='course-123',
            name='Introduction to Python',
            section='A',
            description='Learn Python basics',
            room='Room 101',
        )
        
        assert course.id is not None
        assert course.name == 'Introduction to Python'
        assert str(course) == 'Introduction to Python (course-123)'


@pytest.mark.django_db
class TestSyncedAssignment:
    """Tests for SyncedAssignment model."""

    def test_create_assignment(self, user):
        """Test creating a synced assignment."""
        account = GoogleClassroomAccount.objects.create(
            user=user,
            google_user_id='google-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        course = SyncedCourse.objects.create(
            account=account,
            google_course_id='course-123',
            name='Test Course',
        )
        
        assignment = SyncedAssignment.objects.create(
            synced_course=course,
            google_assignment_id='assignment-123',
            title='Homework 1',
            description='Complete exercises',
            state=SyncedAssignment.AssignmentState.PUBLISHED,
            due_date=timezone.now() + timedelta(days=7),
            max_points=100.0,
        )
        
        assert assignment.id is not None
        assert assignment.title == 'Homework 1'
        assert assignment.state == SyncedAssignment.AssignmentState.PUBLISHED
        assert str(assignment) == 'Homework 1 (assignment-123)'


@pytest.mark.django_db
class TestSyncedSubmission:
    """Tests for SyncedSubmission model."""

    def test_create_submission(self, user):
        """Test creating a synced submission."""
        account = GoogleClassroomAccount.objects.create(
            user=user,
            google_user_id='google-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        course = SyncedCourse.objects.create(
            account=account,
            google_course_id='course-123',
            name='Test Course',
        )
        
        assignment = SyncedAssignment.objects.create(
            synced_course=course,
            google_assignment_id='assignment-123',
            title='Homework 1',
        )
        
        submission = SyncedSubmission.objects.create(
            synced_assignment=assignment,
            google_submission_id='submission-123',
            student_email='student@example.com',
            state=SyncedSubmission.SubmissionState.TURNED_IN,
            assigned_grade=95.0,
            submitted_at=timezone.now(),
        )
        
        assert submission.id is not None
        assert submission.student_email == 'student@example.com'
        assert submission.state == SyncedSubmission.SubmissionState.TURNED_IN


@pytest.mark.django_db
class TestSyncedAnnouncement:
    """Tests for SyncedAnnouncement model."""

    def test_create_announcement(self, user):
        """Test creating a synced announcement."""
        account = GoogleClassroomAccount.objects.create(
            user=user,
            google_user_id='google-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        course = SyncedCourse.objects.create(
            account=account,
            google_course_id='course-123',
            name='Test Course',
        )
        
        announcement = SyncedAnnouncement.objects.create(
            synced_course=course,
            google_announcement_id='announcement-123',
            text='Important announcement about the course',
            state='published',
        )
        
        assert announcement.id is not None
        assert 'Important announcement' in announcement.text


@pytest.mark.django_db
class TestGoogleSyncState:
    """Tests for Google Classroom SyncState model."""

    def test_create_sync_state(self, user):
        """Test creating a sync state."""
        account = GoogleClassroomAccount.objects.create(
            user=user,
            google_user_id='google-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        sync_state = GoogleSyncState.objects.create(
            account=account,
            sync_type=GoogleSyncState.SyncType.FULL,
            result=GoogleSyncState.SyncResult.SUCCESS,
            started_at=timezone.now(),
            completed_at=timezone.now() + timedelta(minutes=5),
            courses_count=10,
            assignments_count=50,
            announcements_count=20,
            submissions_count=100,
        )
        
        assert sync_state.id is not None
        assert sync_state.sync_type == GoogleSyncState.SyncType.FULL
        assert sync_state.result == GoogleSyncState.SyncResult.SUCCESS


# =========================
# Microsoft Teams Tests
# =========================

@pytest.mark.django_db
class TestMicrosoftTeamsAccount:
    """Tests for MicrosoftTeamsAccount model."""

    def test_create_account(self, user):
        """Test creating a Microsoft Teams account."""
        account = MicrosoftTeamsAccount.objects.create(
            user=user,
            microsoft_user_id='ms-123',
            email=user.email,
            display_name='Test User',
            access_token='access-token',
            refresh_token='refresh-token',
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        
        assert account.id is not None
        assert account.user == user
        assert account.microsoft_user_id == 'ms-123'
        assert account.sync_status == MicrosoftTeamsAccount.SyncStatus.ACTIVE
        assert str(account) == f"{user.email} - Microsoft Teams"


@pytest.mark.django_db
class TestSyncedTeam:
    """Tests for SyncedTeam model."""

    def test_create_synced_team(self, user):
        """Test creating a synced team."""
        account = MicrosoftTeamsAccount.objects.create(
            user=user,
            microsoft_user_id='ms-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        team = SyncedTeam.objects.create(
            account=account,
            team_id='team-123',
            display_name='Python Class',
            description='Learn Python together',
            visibility='private',
        )
        
        assert team.id is not None
        assert team.display_name == 'Python Class'
        assert str(team) == 'Python Class (team-123)'


@pytest.mark.django_db
class TestSyncedChannel:
    """Tests for SyncedChannel model."""

    def test_create_channel(self, user):
        """Test creating a synced channel."""
        account = MicrosoftTeamsAccount.objects.create(
            user=user,
            microsoft_user_id='ms-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        team = SyncedTeam.objects.create(
            account=account,
            team_id='team-123',
            display_name='Test Team',
        )
        
        channel = SyncedChannel.objects.create(
            synced_team=team,
            channel_id='channel-123',
            display_name='General',
            description='General discussion',
            is_general=True,
        )
        
        assert channel.id is not None
        assert channel.display_name == 'General'
        assert channel.is_general is True


@pytest.mark.django_db
class TestMSTeamsAssignment:
    """Tests for Microsoft Teams SyncedAssignment model."""

    def test_create_assignment(self, user):
        """Test creating a Teams assignment."""
        account = MicrosoftTeamsAccount.objects.create(
            user=user,
            microsoft_user_id='ms-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        team = SyncedTeam.objects.create(
            account=account,
            team_id='team-123',
            display_name='Test Team',
        )
        
        assignment = MSTeamsAssignment.objects.create(
            synced_team=team,
            assignment_id='assignment-123',
            display_name='Week 1 Quiz',
            instructions='Complete all questions',
            status=MSTeamsAssignment.AssignmentStatus.PUBLISHED,
            due_date_time=timezone.now() + timedelta(days=7),
            max_points=50.0,
        )
        
        assert assignment.id is not None
        assert assignment.display_name == 'Week 1 Quiz'
        assert assignment.status == MSTeamsAssignment.AssignmentStatus.PUBLISHED


@pytest.mark.django_db
class TestMSTeamsSubmission:
    """Tests for Microsoft Teams SyncedSubmission model."""

    def test_create_submission(self, user):
        """Test creating a Teams submission."""
        account = MicrosoftTeamsAccount.objects.create(
            user=user,
            microsoft_user_id='ms-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        team = SyncedTeam.objects.create(
            account=account,
            team_id='team-123',
            display_name='Test Team',
        )
        
        assignment = MSTeamsAssignment.objects.create(
            synced_team=team,
            assignment_id='assignment-123',
            display_name='Quiz',
        )
        
        submission = MSTeamsSubmission.objects.create(
            synced_assignment=assignment,
            submission_id='submission-123',
            student_email='student@example.com',
            state=MSTeamsSubmission.SubmissionState.SUBMITTED,
            grade=45.0,
            feedback='Good work!',
            submitted_at=timezone.now(),
        )
        
        assert submission.id is not None
        assert submission.student_email == 'student@example.com'
        assert submission.state == MSTeamsSubmission.SubmissionState.SUBMITTED


@pytest.mark.django_db
class TestMSTeamsAnnouncement:
    """Tests for Microsoft Teams SyncedAnnouncement model."""

    def test_create_announcement(self, user):
        """Test creating a Teams announcement."""
        account = MicrosoftTeamsAccount.objects.create(
            user=user,
            microsoft_user_id='ms-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        team = SyncedTeam.objects.create(
            account=account,
            team_id='team-123',
            display_name='Test Team',
        )
        
        channel = SyncedChannel.objects.create(
            synced_team=team,
            channel_id='channel-123',
            display_name='General',
        )
        
        announcement = MSTeamsAnnouncement.objects.create(
            synced_channel=channel,
            announcement_id='announcement-123',
            topic='Welcome to the course',
            summary='Course introduction',
            body='Welcome everyone!',
            is_pinned=True,
        )
        
        assert announcement.id is not None
        assert announcement.topic == 'Welcome to the course'
        assert announcement.is_pinned is True


@pytest.mark.django_db
class TestMSTeamsSyncState:
    """Tests for Microsoft Teams SyncState model."""

    def test_create_sync_state(self, user):
        """Test creating a Teams sync state."""
        account = MicrosoftTeamsAccount.objects.create(
            user=user,
            microsoft_user_id='ms-123',
            email=user.email,
            access_token='token',
            refresh_token='token',
            token_expires_at=timezone.now(),
        )
        
        sync_state = MSTeamsSyncState.objects.create(
            account=account,
            sync_type=MSTeamsSyncState.SyncType.FULL,
            result=MSTeamsSyncState.SyncResult.SUCCESS,
            started_at=timezone.now(),
            completed_at=timezone.now() + timedelta(minutes=10),
            teams_count=5,
            channels_count=15,
            assignments_count=30,
            announcements_count=10,
            submissions_count=50,
        )
        
        assert sync_state.id is not None
        assert sync_state.sync_type == MSTeamsSyncState.SyncType.FULL
        assert sync_state.result == MSTeamsSyncState.SyncResult.SUCCESS
