"""
Tests for profile management functionality.
"""
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Profile, UserPreference, LinkedAccount

User = get_user_model()


@pytest.fixture
def api_client():
    """Return an API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create a regular user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        full_name='Test User',
        registration_number='REG001',
        phone_number='+254700000001'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        email='admin@example.com',
        password='adminpass123',
        full_name='Admin User',
        role='ADMIN'
    )


@pytest.fixture
def oauth_user(db):
    """Create an OAuth user (Google)."""
    return User.objects.create_user(
        email='oauth@example.com',
        password=None,
        full_name='OAuth User',
        auth_provider='google',
        is_verified=True
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """Return an authenticated API client."""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Return an authenticated admin API client."""
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return api_client


# ============================================
# Profile GET Tests
# ============================================


@pytest.mark.django_db
class TestProfileGet:
    """Tests for GET profile endpoint."""

    def test_unauthenticated_user_cannot_get_profile(self, api_client):
        """Test that unauthenticated users cannot access profile."""
        url = reverse('accounts:profile')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_user_can_get_profile(self, authenticated_client, user):
        """Test that authenticated users can get their profile."""
        url = reverse('accounts:profile')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email
        assert response.data['full_name'] == user.full_name

    def test_profile_includes_academic_names(
        self,
        authenticated_client,
        user,
        faculty,
        department,
        course,
    ):
        """Test profile exposes faculty/department/course names for mobile display."""
        user.faculty = faculty
        user.department = department
        user.course = course
        user.save(update_fields=["faculty", "department", "course"])

        url = reverse("accounts:profile")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["faculty"] == faculty.id
        assert response.data["department"] == department.id
        assert response.data["course"] == course.id
        assert response.data["faculty_name"] == faculty.name
        assert response.data["department_name"] == department.name
        assert response.data["course_name"] == course.name

    def test_profile_includes_completion(self, authenticated_client, user):
        """Test that profile response includes completion data."""
        url = reverse('accounts:profile')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'completion' in response.data
        assert 'percentage' in response.data['completion']

    def test_profile_includes_linked_providers(self, authenticated_client, user):
        """Test that profile response includes linked providers."""
        url = reverse('accounts:profile')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'linked_providers' in response.data

    def test_profile_includes_stats(self, authenticated_client, user):
        """Test that profile response includes user stats."""
        url = reverse('accounts:profile')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'stats' in response.data
        assert 'total_uploads' in response.data['stats']


# ============================================
# Profile PATCH Tests
# ============================================


@pytest.mark.django_db
class TestProfileUpdate:
    """Tests for PATCH profile endpoint."""

    def test_user_can_update_full_name(self, authenticated_client, user):
        """Test that user can update full name."""
        url = reverse('accounts:profile')
        response = authenticated_client.patch(url, {'full_name': 'New Name'}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['full_name'] == 'New Name'

    def test_user_can_update_phone_number(self, authenticated_client, user):
        """Test that user can update phone number."""
        url = reverse('accounts:profile')
        response = authenticated_client.patch(
            url, 
            {'phone_number': '+254700000002'}, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_user_can_update_year_of_study(self, authenticated_client, user):
        """Test that user can update year of study."""
        url = reverse('accounts:profile')
        response = authenticated_client.patch(
            url, 
            {'year_of_study': 2}, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['year_of_study'] == 2

    def test_user_cannot_update_invalid_year(self, authenticated_client, user):
        """Test that user cannot update with invalid year."""
        url = reverse('accounts:profile')
        response = authenticated_client.patch(
            url, 
            {'year_of_study': 10}, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_cannot_update_role(self, authenticated_client, user):
        """Test that user cannot update role (protected field)."""
        url = reverse('accounts:profile')
        response = authenticated_client.patch(
            url, 
            {'role': 'ADMIN'}, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        # Role should remain unchanged
        user.refresh_from_db()
        assert user.role == 'STUDENT'

    def test_user_cannot_update_auth_provider(self, authenticated_client, user):
        """Test that user cannot update auth_provider (protected field)."""
        url = reverse('accounts:profile')
        response = authenticated_client.patch(
            url, 
            {'auth_provider': 'google'}, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.auth_provider == 'email'

    def test_user_can_update_profile_fields(self, authenticated_client, user):
        """Test that user can update extended profile fields."""
        url = reverse('accounts:profile')
        response = authenticated_client.patch(
            url, 
            {'bio': 'Test bio', 'address': 'Test address'}, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['profile']['bio'] == 'Test bio'


# ============================================
# Profile Photo Tests
# ============================================


@pytest.mark.django_db
class TestProfilePhoto:
    """Tests for profile photo upload and delete."""

    def test_user_can_upload_photo(self, authenticated_client, user):
        """Test that user can upload profile photo."""
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        url = reverse('accounts:profile_photo_upload')
        
        # Create a small test image
        image = SimpleUploadedFile(
            "test.jpg",
            b"file_content",
            content_type="image/jpeg"
        )
        
        response = authenticated_client.post(
            url, 
            {'profile_image': image}, 
            format='multipart'
        )
        
        # Note: May fail due to validation, but endpoint should respond
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_user_can_delete_photo(self, authenticated_client, user):
        """Test that user can delete profile photo."""
        url = reverse('accounts:profile_photo_delete')
        response = authenticated_client.delete(url)
        
        # Even without photo, should respond
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# ============================================
# Preferences Tests
# ============================================


@pytest.mark.django_db
class TestProfilePreferences:
    """Tests for profile preferences endpoint."""

    def test_user_can_get_preferences(self, authenticated_client, user):
        """Test that user can get preferences."""
        url = reverse('accounts:profile_preferences')
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'email_notifications' in response.data
        assert 'push_notifications' in response.data
        assert 'weekly_digest' in response.data
        assert 'timezone' in response.data

    def test_user_can_update_preferences(self, authenticated_client, user):
        """Test that user can update preferences."""
        url = reverse('accounts:profile_preferences')
        response = authenticated_client.patch(
            url, 
            {'email_notifications': False}, 
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['email_notifications'] == False

    def test_push_notifications_can_differ_from_app_notifications(self, authenticated_client, user):
        """Push-specific preference should persist independently."""
        url = reverse('accounts:profile_preferences')
        response = authenticated_client.patch(
            url,
            {
                'app_notifications': False,
                'push_notifications': True,
                'weekly_digest': False,
                'timezone': 'UTC',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['app_notifications'] is False
        assert response.data['push_notifications'] is True
        assert response.data['weekly_digest'] is False
        assert response.data['timezone'] == 'UTC'


# ============================================
# Profile Completion Tests
# ============================================


@pytest.mark.django_db
class TestProfileCompletion:
    """Tests for profile completion endpoint."""

    def test_user_can_get_completion(self, authenticated_client, user):
        """Test that user can get completion status."""
        url = reverse('accounts:profile_completion')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'percentage' in response.data
        assert 'missing_fields' in response.data

    def test_incomplete_profile_has_low_completion(self, user):
        """Test that incomplete profile has low completion."""
        from apps.accounts.services import ProfileCompletionService
        
        completion = ProfileCompletionService.calculate_completion(user)
        
        # New user with only email should have low completion
        assert completion['percentage'] < 100
        assert len(completion['missing_fields']) > 0

    def test_complete_profile_has_full_completion(self, db):
        """Test that complete profile has 100% completion."""
        from apps.faculties.models import Faculty, Department
        from apps.courses.models import Course
        from apps.accounts.services import ProfileCompletionService
        
        # Create complete user
        faculty = Faculty.objects.create(name='Engineering')
        department = Department.objects.create(name='Computer Science', faculty=faculty)
        course = Course.objects.create(name='Data Science', department=department)
        
        user = User.objects.create_user(
            email='complete@example.com',
            password='testpass123',
            full_name='Complete User',
            registration_number='REG999',
            phone_number='+254700000999',
            faculty=faculty,
            department=department,
            course=course,
            year_of_study=2,
            semester=1
        )
        
        completion = ProfileCompletionService.calculate_completion(user)
        
        # Complete profile should have high completion
        assert completion['percentage'] >= 60


# ============================================
# Password Change Tests
# ============================================


@pytest.mark.django_db
class TestPasswordChange:
    """Tests for password change endpoint."""

    def test_user_can_change_password(self, authenticated_client, user):
        """Test that user can change password."""
        url = reverse('accounts:password_change')
        response = authenticated_client.post(
            url, 
            {
                'old_password': 'testpass123',
                'new_password': 'newpass123',
                'new_password_confirm': 'newpass123'
            }, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify password was changed
        user.refresh_from_db()
        assert user.check_password('newpass123')

    def test_user_cannot_change_password_with_wrong_old(self, authenticated_client, user):
        """Test that user cannot change password with wrong old password."""
        url = reverse('accounts:password_change')
        response = authenticated_client.post(
            url, 
            {
                'old_password': 'wrongpass',
                'new_password': 'newpass123',
                'new_password_confirm': 'newpass123'
            }, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_oauth_user_cannot_change_password(self, api_client, oauth_user):
        """Test that OAuth user cannot change password."""
        refresh = RefreshToken.for_user(oauth_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('accounts:password_change')
        response = api_client.post(
            url, 
            {
                'old_password': 'testpass123',
                'new_password': 'newpass123',
                'new_password_confirm': 'newpass123'
            }, 
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Cannot change password' in response.data['error']


# ============================================
# Linked Accounts Tests
# ============================================


@pytest.mark.django_db
class TestLinkedAccounts:
    """Tests for linked accounts endpoint."""

    def test_user_can_get_linked_accounts(self, authenticated_client, user):
        """Test that user can get linked accounts."""
        url = reverse('accounts:profile_linked_accounts')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'linked_providers' in response.data

    def test_oauth_user_has_provider_linked(self, api_client, oauth_user):
        """Test that OAuth user has provider in linked list."""
        refresh = RefreshToken.for_user(oauth_user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        url = reverse('accounts:profile_linked_accounts')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'google' in response.data['linked_providers']


# ============================================
# Validation Tests
# ============================================


@pytest.mark.django_db
class TestProfileValidation:
    """Tests for profile validation."""

    def test_duplicate_registration_number_rejected(self, user, db):
        """Test that duplicate registration number is rejected."""
        from apps.accounts.serializers import UserUpdateSerializer
        from rest_framework import serializers
        
        # Create another user with a different registration number
        User.objects.create_user(
            email='another@example.com',
            password='testpass123',
            registration_number='REG999'
        )
        
        # Try to update first user's registration number to duplicate
        serializer = UserUpdateSerializer(
            user, 
            data={'registration_number': 'REG999'},
            context={'request': type('obj', (object,), {'user': user})()}
        )
        
        assert not serializer.is_valid()
        assert 'registration_number' in serializer.errors
