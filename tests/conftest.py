"""
Pytest configuration and fixtures.
"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.faculties.models import Faculty, Department
from apps.courses.models import Course, Unit

User = get_user_model()


@pytest.fixture
def api_client():
    """Return an API client for testing."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a regular user."""
    return User.objects.create_user(
        email='student@test.com',
        password='testpass123',
        full_name='Test Student',
        registration_number='STU001',
        role='student'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        email='admin@test.com',
        password='adminpass123',
        full_name='Test Admin',
        role='admin'
    )


@pytest.fixture
def moderator_user(db):
    """Create a moderator user."""
    return User.objects.create_user(
        email='moderator@test.com',
        password='modpass123',
        full_name='Test Moderator',
        registration_number='MOD001',
        role='moderator'
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """Return an authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Return an admin-authenticated API client."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def moderator_client(api_client, moderator_user):
    """Return a moderator-authenticated API client."""
    api_client.force_authenticate(user=moderator_user)
    return api_client


@pytest.fixture
def faculty(db):
    """Create a default faculty for tests that need academic hierarchy."""
    return Faculty.objects.create(name='Science', code='SCI')


@pytest.fixture
def department(db, faculty):
    """Create a default department under the faculty."""
    return Department.objects.create(
        faculty=faculty,
        name='Computer Science',
        code='CS'
    )


@pytest.fixture
def course(db, department):
    """Create a default course under the department."""
    return Course.objects.create(
        department=department,
        name='Bachelor of Science',
        code='BSC',
        duration_years=4
    )


@pytest.fixture
def unit(db, course):
    """Create a default unit under the course."""
    return Unit.objects.create(
        course=course,
        name='Data Structures',
        code='CS201',
        semester='1',
        year_of_study=2
    )
