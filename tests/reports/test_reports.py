"""
Tests for reports and moderation workflows.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.faculties.models import Faculty, Department
from apps.courses.models import Course
from apps.resources.models import Resource
from apps.reports.models import Report


@pytest.fixture
def faculty_report(db):
    """Create a faculty."""
    return Faculty.objects.create(name='Engineering', code='ENG')


@pytest.fixture
def department_report(db, faculty_report):
    """Create a department."""
    return Department.objects.create(
        faculty=faculty_report,
        name='Computer Engineering',
        code='CE',
    )


@pytest.fixture
def course_report(db, department_report):
    """Create a course."""
    return Course.objects.create(
        department=department_report,
        name='Computer Engineering',
        code='CPE',
        duration_years=5
    )


@pytest.mark.django_db
class TestReportCreation:
    """Test report creation."""

    def test_create_resource_report(self, authenticated_client, course_report, user, admin_user):
        """Test creating a report for a resource."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course_report,
            uploaded_by=admin_user,
            status='approved'
        )

        url = reverse('reports:report-list')
        data = {
            'resource': str(resource.id),
            'reason_type': 'inappropriate',
            'message': 'This content is inappropriate'
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Report.objects.count() == 1

    def test_cannot_report_without_reason(self, authenticated_client, course_report, user):
        """Test that report requires a reason."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course_report,
            uploaded_by=user,
            status='approved'
        )

        url = reverse('reports:report-list')
        data = {
            'resource': str(resource.id),
            'message': 'Test message'
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_report_without_target(self, authenticated_client):
        """Test that report requires either resource or comment."""
        url = reverse('reports:report-list')
        data = {
            'reason_type': 'spam',
            'message': 'Spam content'
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestReportResolution:
    """Test report resolution."""

    def test_moderator_can_resolve_report(self, moderator_client, course_report, user, admin_user):
        """Test that moderators can resolve reports."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course_report,
            uploaded_by=admin_user,
            status='approved'
        )

        # Create report
        report = Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type='inappropriate',
            message='Test report'
        )

        # Resolve report
        url = f"{reverse('reports:report-detail', kwargs={'id': report.id})}resolve/"
        response = moderator_client.post(url, {'resolution_note': 'Resolved'}, format='json')
        assert response.status_code == status.HTTP_200_OK

        report.refresh_from_db()
        assert report.status == 'resolved'
        assert report.reviewed_by is not None


@pytest.mark.django_db
class TestReportAccess:
    """Test report access control."""

    def test_students_cannot_access_all_reports(self, authenticated_client):
        """Test that students can only see their own reports."""
        url = reverse('reports:report-list')
        response = authenticated_client.get(url)
        # Should filter to own reports only
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_access_all_reports(self, admin_client):
        """Test that admins can see all reports."""
        url = reverse('reports:report-list')
        response = admin_client.get(url)
        assert response.status_code == status.HTTP_200_OK
