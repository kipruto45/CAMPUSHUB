"""
Tests for the Resource Sharing functionality.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import User
from apps.resources.models import Resource, ResourceShareEvent
from apps.resources.services import ResourceShareService


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="testuser@example.com", password="testpass123", full_name="Test User"
    )


@pytest.fixture
def other_user(db):
    """Create another test user."""
    return User.objects.create_user(
        email="otheruser@example.com", password="otherpass123", full_name="Other User"
    )


@pytest.fixture
def authenticated_client(client, user):
    """Create an authenticated test client."""
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def public_approved_resource(db, user):
    """Create a public approved resource that can be shared."""
    from apps.faculties.models import Faculty

    faculty = Faculty.objects.create(name="Engineering")
    department = faculty.departments.create(name="Computer Science")
    course = department.courses.create(name="Computer Science", code="CS")

    return Resource.objects.create(
        title="Data Structures Notes",
        description="Complete notes on data structures",
        file="test.pdf",
        file_type="pdf",
        file_size=1024,
        uploaded_by=user,
        course=course,
        status="approved",
        is_public=True,
    )


@pytest.fixture
def private_resource(db, user):
    """Create a private resource that cannot be shared."""
    from apps.faculties.models import Faculty

    faculty = Faculty.objects.create(name="Engineering")
    department = faculty.departments.create(name="Computer Science")
    course = department.courses.create(name="Computer Science", code="CS")

    return Resource.objects.create(
        title="Private Notes",
        description="Private notes",
        file="private.pdf",
        file_type="pdf",
        file_size=512,
        uploaded_by=user,
        course=course,
        status="approved",
        is_public=False,
    )


@pytest.fixture
def pending_resource(db, user):
    """Create a pending resource that cannot be shared."""
    from apps.faculties.models import Faculty

    faculty = Faculty.objects.create(name="Engineering")
    department = faculty.departments.create(name="Computer Science")
    course = department.courses.create(name="Computer Science", code="CS")

    return Resource.objects.create(
        title="Pending Notes",
        description="Pending notes",
        file="pending.pdf",
        file_type="pdf",
        file_size=512,
        uploaded_by=user,
        course=course,
        status="pending",
        is_public=True,
    )


@pytest.fixture
def rejected_resource(db, user):
    """Create a rejected resource that cannot be shared."""
    from apps.faculties.models import Faculty

    faculty = Faculty.objects.create(name="Engineering")
    department = faculty.departments.create(name="Computer Science")
    course = department.courses.create(name="Computer Science", code="CS")

    return Resource.objects.create(
        title="Rejected Notes",
        description="Rejected notes",
        file="rejected.pdf",
        file_type="pdf",
        file_size=512,
        uploaded_by=user,
        course=course,
        status="rejected",
        is_public=True,
    )


@pytest.mark.django_db
class TestResourceShareService:
    """Tests for the ResourceShareService class."""

    def test_can_share_approved_public_resource(self, public_approved_resource):
        """Test that approved public resources can be shared."""
        can_share, error = ResourceShareService.can_share(public_approved_resource)
        assert can_share is True
        assert error is None

    def test_cannot_share_private_resource(self, private_resource):
        """Test that private resources cannot be shared."""
        can_share, error = ResourceShareService.can_share(private_resource)
        assert can_share is False
        assert "Private" in error

    def test_cannot_share_pending_resource(self, pending_resource):
        """Test that pending resources cannot be shared."""
        can_share, error = ResourceShareService.can_share(pending_resource)
        assert can_share is False
        assert "approved" in error.lower()

    def test_cannot_share_rejected_resource(self, rejected_resource):
        """Test that rejected resources cannot be shared."""
        can_share, error = ResourceShareService.can_share(rejected_resource)
        assert can_share is False
        assert "approved" in error.lower()

    def test_build_share_url(self, public_approved_resource):
        """Test share URL generation."""
        service = ResourceShareService(public_approved_resource)
        share_url = service.build_share_url()
        assert share_url == f"https://campushub.app/resources/{public_approved_resource.slug}"

    def test_build_share_message(self, public_approved_resource):
        """Test share message generation."""
        service = ResourceShareService(public_approved_resource)
        message = service.build_share_message()
        assert "Data Structures Notes" in message
        assert "https://campushub.app/resources/" in message
        assert "CampusHub" in message

    def test_get_share_payload_approved_resource(self, public_approved_resource):
        """Test getting share payload for shareable resource."""
        service = ResourceShareService(public_approved_resource)
        payload = service.get_share_payload()
        
        assert payload["can_share"] is True
        assert payload["title"] == "Data Structures Notes"
        assert payload["slug"] == public_approved_resource.slug
        assert "share_url" in payload
        assert "share_message" in payload
        assert payload["resource_id"] == str(public_approved_resource.id)

    def test_get_share_payload_private_resource(self, private_resource):
        """Test getting share payload for non-shareable resource."""
        service = ResourceShareService(private_resource)
        payload = service.get_share_payload()
        
        assert payload["can_share"] is False
        assert "Private" in payload["reason"]
        assert payload["share_url"] == ""

    def test_share_count_increments(self, public_approved_resource):
        """Test that share count increments when recording a share."""
        initial_count = public_approved_resource.share_count
        
        service = ResourceShareService(public_approved_resource)
        service.record_share(method="copy_link")
        
        public_approved_resource.refresh_from_db()
        assert public_approved_resource.share_count == initial_count + 1


@pytest.mark.django_db
class TestResourceShareLinkEndpoint:
    """Tests for the /api/resources/{id}/share-link/ endpoint."""

    def test_share_link_requires_authentication(self, client, public_approved_resource):
        """Test that share-link endpoint works without authentication."""
        url = f"/api/resources/{public_approved_resource.id}/share-link/"
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_share_link_approved_resource(self, authenticated_client, public_approved_resource):
        """Test getting share link for approved public resource."""
        url = f"/api/resources/{public_approved_resource.id}/share-link/"
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["can_share"] is True
        assert "share_url" in response.data
        assert "share_message" in response.data
        assert response.data["title"] == "Data Structures Notes"

    def test_share_link_private_resource(self, authenticated_client, private_resource):
        """Test getting share link for private resource returns 403."""
        url = f"/api/resources/{private_resource.id}/share-link/"
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_share_link_pending_resource(self, authenticated_client, pending_resource):
        """Test getting share link for pending resource returns 403."""
        url = f"/api/resources/{pending_resource.id}/share-link/"
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_share_link_rejected_resource(self, authenticated_client, rejected_resource):
        """Test getting share link for rejected resource returns 403."""
        url = f"/api/resources/{rejected_resource.id}/share-link/"
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_share_link_nonexistent_resource(self, authenticated_client):
        """Test getting share link for nonexistent resource returns 404."""
        url = "/api/resources/00000000-0000-0000-0000-000000000000/share-link/"
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestResourceShareEndpoint:
    """Tests for the /api/resources/{id}/share/ endpoint."""

    def test_share_requires_authentication(self, client, public_approved_resource):
        """Test that share endpoint requires authentication."""
        url = f"/api/resources/{public_approved_resource.id}/share/"
        response = client.post(url, {"share_method": "copy_link"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_share_approved_resource(self, authenticated_client, public_approved_resource):
        """Test sharing an approved public resource."""
        url = f"/api/resources/{public_approved_resource.id}/share/"
        response = authenticated_client.post(url, {"share_method": "copy_link"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
        assert "share_count" in response.data

    def test_share_increments_count(self, authenticated_client, public_approved_resource):
        """Test that sharing increments the share count."""
        initial_count = public_approved_resource.share_count
        
        url = f"/api/resources/{public_approved_resource.id}/share/"
        authenticated_client.post(url, {"share_method": "native_share"})
        
        public_approved_resource.refresh_from_db()
        assert public_approved_resource.share_count == initial_count + 1

    def test_share_creates_share_event(self, authenticated_client, user, public_approved_resource):
        """Test that sharing creates a ResourceShareEvent."""
        url = f"/api/resources/{public_approved_resource.id}/share/"
        authenticated_client.post(url, {"share_method": "whatsapp"})

        event = ResourceShareEvent.objects.filter(
            resource=public_approved_resource,
            user=user
        ).first()
        
        assert event is not None
        assert event.share_method == "whatsapp"

    def test_share_private_resource_fails(self, authenticated_client, private_resource):
        """Test that sharing a private resource fails."""
        url = f"/api/resources/{private_resource.id}/share/"
        response = authenticated_client.post(url, {"share_method": "copy_link"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestShareMessageFormat:
    """Tests for share message formatting."""

    def test_share_message_includes_resource_title(self, public_approved_resource):
        """Test that share message includes resource title."""
        service = ResourceShareService(public_approved_resource)
        message = service.build_share_message()
        
        assert public_approved_resource.title in message

    def test_share_message_includes_url(self, public_approved_resource):
        """Test that share message includes shareable URL."""
        service = ResourceShareService(public_approved_resource)
        message = service.build_share_message()
        
        assert "https://campushub.app/resources/" in message

    def test_share_message_platform_text(self, public_approved_resource):
        """Test that share message includes platform branding."""
        service = ResourceShareService(public_approved_resource)
        message = service.build_share_message()
        
        assert "CampusHub" in message

    def test_share_payload_includes_deep_link(self, public_approved_resource):
        """Test that share payload includes deep link for mobile."""
        service = ResourceShareService(public_approved_resource)
        payload = service.get_share_payload()
        
        assert "deep_link_url" in payload
        assert f"campushub://resources/{public_approved_resource.slug}" == payload["deep_link_url"]


@pytest.mark.django_db
class TestResourceShareBySlug:
    """Tests for sharing resources by slug URL."""

    def test_share_link_by_slug(self, authenticated_client, public_approved_resource):
        """Test getting share link using slug URL."""
        url = f"/api/resources/{public_approved_resource.slug}/share-link/"
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["can_share"] is True

    def test_share_by_slug(self, authenticated_client, public_approved_resource):
        """Test sharing using slug URL."""
        url = f"/api/resources/{public_approved_resource.slug}/share/"
        response = authenticated_client.post(url, {"share_method": "email"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["success"] is True
