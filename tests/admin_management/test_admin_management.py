"""Tests for admin management module."""
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.courses.models import Course
from apps.faculties.models import Department, Faculty
from apps.moderation.models import AdminActivityLog, ModerationLog
from apps.notifications.models import Notification
from apps.reports.models import Report
from apps.resources.models import Resource
from apps.comments.models import Comment
from apps.accounts.models import Profile, UserActivity

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email='student_admin_module@test.com',
        password='pass12345',
        first_name='Student',
        last_name='User',
        role='STUDENT',
        registration_number='STU-ADMIN-001',
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email='admin_admin_module@test.com',
        password='pass12345',
        first_name='Admin',
        last_name='User',
        role='ADMIN',
    )


@pytest.fixture
def moderator_user(db):
    return User.objects.create_user(
        email='moderator_admin_module@test.com',
        password='pass12345',
        first_name='Moderator',
        last_name='User',
        role='MODERATOR',
        registration_number='MOD-ADMIN-001',
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def moderator_client(api_client, moderator_user):
    api_client.force_authenticate(user=moderator_user)
    return api_client


@pytest.fixture
def admin_management_course(db):
    faculty = Faculty.objects.create(name='Engineering Admin', code='ENGA')
    department = Department.objects.create(
        faculty=faculty,
        name='Software Engineering Admin',
        code='SEA',
    )
    return Course.objects.create(
        department=department,
        name='BSc Software Engineering Admin',
        code='BSC-SEA',
        duration_years=4,
    )


@pytest.mark.django_db
class TestAdminManagement:
    """Core admin management workflows."""

    def test_student_cannot_access_admin_dashboard(self, authenticated_client):
        response = authenticated_client.get(reverse('admin_management:dashboard'))
        assert response.status_code == 403

    def test_admin_can_access_dashboard(self, admin_client):
        response = admin_client.get(reverse('admin_management:dashboard'))
        assert response.status_code == 200
        assert 'users' in response.data
        assert 'resources' in response.data
        assert 'reports' in response.data
        assert 'engagement' in response.data
        assert 'moderation' in response.data

    def test_admin_can_update_user_status(self, admin_client, user):
        response = admin_client.patch(
            reverse('admin_management:user-status', kwargs={'user_id': user.id}),
            {'is_active': False},
            format='json',
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.is_active is False

    def test_admin_can_update_user_role(self, admin_client, user):
        response = admin_client.patch(
            reverse('admin_management:user-role', kwargs={'user_id': user.id}),
            {'role': 'MODERATOR'},
            format='json',
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.role == 'MODERATOR'

    def test_admin_can_approve_pending_resource(
        self, admin_client, admin_user, user, admin_management_course
    ):
        resource = Resource.objects.create(
            title='Pending Resource',
            resource_type='notes',
            uploaded_by=user,
            course=admin_management_course,
            status='pending',
            is_public=True,
        )

        response = admin_client.post(
            reverse('admin_management:resource-approve', kwargs={'resource_id': resource.id}),
            {'reason': 'Quality checks passed'},
            format='json',
        )
        assert response.status_code == 200

        resource.refresh_from_db()
        assert resource.status == 'approved'
        assert resource.approved_by_id == admin_user.id
        assert resource.approved_at is not None
        assert ModerationLog.objects.filter(resource=resource, action='approved').exists()

    def test_admin_resource_approval_writes_admin_activity_log(
        self, admin_client, user, admin_user, admin_management_course
    ):
        resource = Resource.objects.create(
            title='Pending Approval Audit',
            resource_type='notes',
            uploaded_by=user,
            course=admin_management_course,
            status='pending',
            is_public=True,
        )

        response = admin_client.post(
            reverse('admin_management:resource-approve', kwargs={'resource_id': resource.id}),
            {'reason': 'Approved for release'},
            format='json',
        )
        assert response.status_code == 200
        assert AdminActivityLog.objects.filter(
            admin=admin_user,
            action='resource_approved',
            target_type='resource',
            target_id=str(resource.id),
        ).exists()

    def test_admin_resource_detail_exposes_mobile_expected_metrics(
        self, admin_client, user, admin_user, admin_management_course
    ):
        resource = Resource.objects.create(
            title='Resource Detail Contract',
            resource_type='notes',
            uploaded_by=admin_user,
            course=admin_management_course,
            status='approved',
            is_public=True,
            average_rating=4.5,
        )
        Comment.objects.create(
            user=user,
            resource=resource,
            content='Looks useful',
        )

        response = admin_client.get(
            reverse('admin_management:resource-detail', kwargs={'resource_id': resource.id})
        )
        assert response.status_code == 200
        assert response.data['average_rating'] == '4.50'
        assert response.data['comments_count'] == 1
        assert response.data['reports_count'] == 0

    def test_admin_user_detail_exposes_profile_and_stats_contract(
        self, admin_client, user, admin_management_course
    ):
        user.course = admin_management_course
        user.department = admin_management_course.department
        user.faculty = admin_management_course.department.faculty
        user.year_of_study = 2
        user.save()
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.total_uploads = 3
        profile.total_downloads = 7
        profile.total_bookmarks = 5
        profile.save()

        response = admin_client.get(
            reverse('admin_management:user-detail', kwargs={'user_id': user.id})
        )

        assert response.status_code == 200
        assert response.data['faculty_name'] == admin_management_course.department.faculty.name
        assert response.data['department_name'] == admin_management_course.department.name
        assert response.data['course_name'] == admin_management_course.name
        assert response.data['stats']['total_uploads'] == 3
        assert response.data['stats']['total_downloads'] == 7
        assert response.data['stats']['total_bookmarks'] == 5

    def test_admin_can_view_user_activities(self, admin_client, user):
        UserActivity.objects.create(
            user=user,
            action='login',
            description='Signed in from mobile app',
        )

        response = admin_client.get(
            reverse('admin_management:user-activities', kwargs={'user_id': user.id})
        )

        assert response.status_code == 200
        assert response.data['count'] == 1
        assert response.data['results'][0]['action'] == 'login'
        assert response.data['results'][0]['description'] == 'Signed in from mobile app'

    def test_admin_can_resolve_report(self, admin_client, user, admin_user, admin_management_course):
        resource = Resource.objects.create(
            title='Report Target Resource',
            resource_type='notes',
            uploaded_by=admin_user,
            course=admin_management_course,
            status='approved',
            is_public=True,
        )
        report = Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type='inappropriate',
            message='Needs review',
            status='open',
        )

        response = admin_client.post(
            reverse('admin_management:report-resolve', kwargs={'report_id': report.id}),
            {'resolution_note': 'Issue resolved'},
            format='json',
        )
        assert response.status_code == 200

        report.refresh_from_db()
        assert report.status == 'resolved'
        assert report.reviewed_by == admin_user
        assert Notification.objects.filter(
            recipient=user,
            notification_type='report_update',
        ).exists()

    def test_moderator_cannot_access_admin_management(self, moderator_client):
        response = moderator_client.get(reverse('admin_management:user-list'))
        assert response.status_code == 403

    def test_admin_faculty_create_and_update_write_activity_logs(self, admin_client):
        create_response = admin_client.post(
            reverse('admin_management:faculty-list'),
            {
                'name': 'Health Sciences',
                'code': 'HSC',
                'description': 'Health programs',
                'is_active': True,
            },
            format='json',
        )
        assert create_response.status_code == 201
        faculty_id = create_response.data['id']

        assert AdminActivityLog.objects.filter(
            action='faculty_created',
            target_type='faculty',
            target_id=str(faculty_id),
        ).exists()

        update_response = admin_client.patch(
            reverse('admin_management:faculty-detail', kwargs={'faculty_id': faculty_id}),
            {'description': 'Updated health programs'},
            format='json',
        )
        assert update_response.status_code == 200
        assert AdminActivityLog.objects.filter(
            action='faculty_updated',
            target_type='faculty',
            target_id=str(faculty_id),
        ).exists()
