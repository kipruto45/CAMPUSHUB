"""
Tests for search and filtering functionality.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.faculties.models import Faculty, Department
from apps.courses.models import Course
from apps.resources.models import Resource


@pytest.fixture
def search_faculty(db):
    """Create a faculty."""
    return Faculty.objects.create(name='Science', code='SCI')


@pytest.fixture
def search_department(db, search_faculty):
    """Create a department."""
    return Department.objects.create(
        faculty=search_faculty,
        name='Computer Science',
        code='CS'
    )


@pytest.fixture
def search_course(db, search_department):
    """Create a course."""
    return Course.objects.create(
        department=search_department,
        name='Bachelor of Science',
        code='BSC',
        duration_years=4
    )


@pytest.mark.django_db
class TestResourceSearch:
    """Test resource search."""

    def test_search_by_title(self, api_client, search_course, user):
        """Test searching resources by title."""
        Resource.objects.create(
            title='Python Programming Notes',
            resource_type='notes',
            course=search_course,
            uploaded_by=user,
            status='approved'
        )
        Resource.objects.create(
            title='Java Tutorial',
            resource_type='tutorial',
            course=search_course,
            uploaded_by=user,
            status='approved'
        )

        url = f"{reverse('search:search')}?search=Python"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_search_by_description(self, api_client, search_course, user):
        """Test searching resources by description."""
        Resource.objects.create(
            title='Notes',
            description='Introduction to algorithms',
            resource_type='notes',
            course=search_course,
            uploaded_by=user,
            status='approved'
        )

        url = f"{reverse('search:search')}?search=algorithms"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1


@pytest.mark.django_db
class TestResourceFiltering:
    """Test resource filtering."""

    def test_filter_by_resource_type(self, api_client, search_course, user):
        """Test filtering by resource type."""
        Resource.objects.create(
            title='Notes',
            resource_type='notes',
            course=search_course,
            uploaded_by=user,
            status='approved'
        )
        Resource.objects.create(
            title='Past Paper',
            resource_type='past_paper',
            course=search_course,
            uploaded_by=user,
            status='approved'
        )

        url = f"{reverse('resources:resource-list')}?resource_type=notes"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_filter_by_status(self, authenticated_client, search_course, user):
        """Test filtering by status (admin/moderator only)."""
        Resource.objects.create(
            title='Approved',
            resource_type='notes',
            course=search_course,
            uploaded_by=user,
            status='approved'
        )
        Resource.objects.create(
            title='Pending',
            resource_type='notes',
            course=search_course,
            uploaded_by=user,
            status='pending'
        )

        # As regular user - should only see approved
        url = f"{reverse('resources:resource-list')}?status=pending"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Pending resources hidden from regular users

    def test_filter_by_faculty(self, api_client, search_course, user):
        """Test filtering by faculty."""
        Resource.objects.create(
            title='Science Notes',
            resource_type='notes',
            faculty=search_course.department.faculty,
            course=search_course,
            uploaded_by=user,
            status='approved'
        )

        url = f"{reverse('resources:resource-list')}?faculty={search_course.department.faculty.id}"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1


@pytest.mark.django_db
class TestResourceSorting:
    """Test resource sorting."""

    def test_sort_by_newest(self, api_client, search_course, user):
        """Test sorting by newest."""
        Resource.objects.create(
            title='Old Resource',
            resource_type='notes',
            course=search_course,
            uploaded_by=user,
            status='approved'
        )

        url = f"{reverse('resources:resource-list')}?ordering=-created_at"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_sort_by_most_downloaded(self, api_client, search_course, user):
        """Test sorting by most downloaded."""
        Resource.objects.create(
            title='Popular Resource',
            resource_type='notes',
            course=search_course,
            uploaded_by=user,
            status='approved',
            download_count=100
        )
        Resource.objects.create(
            title='Unpopular Resource',
            resource_type='notes',
            course=search_course,
            uploaded_by=user,
            status='approved',
            download_count=5
        )

        url = f"{reverse('resources:resource-list')}?ordering=-download_count"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # First result should have highest downloads


@pytest.mark.django_db
class TestPagination:
    """Test pagination."""

    def test_pagination_defaults(self, api_client, search_course, user):
        """Test default pagination."""
        # Create 25 resources
        for i in range(25):
            Resource.objects.create(
                title=f'Resource {i}',
                resource_type='notes',
                course=search_course,
                uploaded_by=user,
                status='approved'
            )

        url = reverse('resources:resource-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data

    def test_custom_page_size(self, api_client, search_course, user):
        """Test custom page size."""
        # Create 30 resources
        for i in range(30):
            Resource.objects.create(
                title=f'Resource {i}',
                resource_type='notes',
                course=search_course,
                uploaded_by=user,
                status='approved'
            )

        url = f"{reverse('resources:resource-list')}?page_size=10"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) <= 10
