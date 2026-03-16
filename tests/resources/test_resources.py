"""
Tests for resources endpoints.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.faculties.models import Faculty, Department
from apps.courses.models import Course, Unit
from apps.resources.models import Resource
from apps.notifications.models import Notification
from apps.accounts.models import UserActivity
from apps.resources.models import UserStorage


@pytest.fixture
def faculty(db):
    """Create a faculty."""
    return Faculty.objects.create(name='Science', code='SCI')


@pytest.fixture
def department(db, faculty):
    """Create a department."""
    return Department.objects.create(
        faculty=faculty,
        name='Computer Science',
        code='CS'
    )


@pytest.fixture
def course(db, department):
    """Create a course."""
    return Course.objects.create(
        department=department,
        name='Bachelor of Science',
        code='BSC',
        duration_years=4
    )


@pytest.fixture
def unit(db, course):
    """Create a unit."""
    return Unit.objects.create(
        course=course,
        name='Data Structures',
        code='CS201',
        semester='1',
        year_of_study=2
    )


@pytest.fixture
def upload_file():
    """Create a valid upload file."""
    return SimpleUploadedFile(
        'lecture_notes.pdf',
        b'%PDF-1.4 sample',
        content_type='application/pdf'
    )


@pytest.mark.django_db
class TestResourceList:
    """Test resource list endpoints."""

    def test_list_resources_unauthenticated(self, api_client, course, user):
        """Test listing resources as unauthenticated user."""
        Resource.objects.create(
            title='Test Notes',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = reverse('resources:resource-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_list_approved_only(self, api_client, course, user):
        """Test that only approved resources are visible to students."""
        Resource.objects.create(
            title='Approved Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        Resource.objects.create(
            title='Pending Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='pending'
        )
        url = reverse('resources:resource-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1


@pytest.mark.django_db
class TestResourceCreate:
    """Test resource creation."""

    def test_create_resource(self, authenticated_client, faculty, department, course, unit, upload_file):
        """Test creating a resource."""
        url = reverse('resources:resource-list')
        data = {
            'title': 'New Lecture Notes',
            'description': 'Chapter 1-5 notes',
            'resource_type': 'notes',
            'file': upload_file,
            'faculty': str(faculty.id),
            'department': str(department.id),
            'course': str(course.id),
            'unit': str(unit.id),
            'semester': '1',
            'year_of_study': 2,
            'tags': 'important,exam'
        }
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'New Lecture Notes'
        assert response.data['status'] == 'pending'  # Default status

    def test_create_resource_unauthenticated(self, api_client, course):
        """Test creating resource without authentication."""
        url = reverse('resources:resource-list')
        data = {
            'title': 'New Lecture Notes',
            'resource_type': 'notes',
            'course': str(course.id)
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestResourceFiltering:
    """Test resource filtering."""

    def test_filter_by_course(self, authenticated_client, course, user):
        """Test filtering resources by course."""
        Resource.objects.create(
            title='CS Notes',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"{reverse('resources:resource-list')}?course={course.id}"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_filter_by_resource_type(self, authenticated_client, course, user):
        """Test filtering by resource type."""
        Resource.objects.create(
            title='Notes',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        Resource.objects.create(
            title='Past Paper',
            resource_type='past_paper',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"{reverse('resources:resource-list')}?resource_type=notes"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1


@pytest.mark.django_db
class TestBookmarks:
    """Test bookmark functionality."""

    def test_create_bookmark(self, authenticated_client, course, user):
        """Test creating a bookmark."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = reverse('bookmarks:bookmark-list')
        data = {'resource': str(resource.id)}
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_duplicate_bookmark(self, authenticated_client, course, user):
        """Test that duplicate bookmarks are not allowed."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = reverse('bookmarks:bookmark-list')
        data = {'resource': str(resource.id)}
        authenticated_client.post(url, data, format='json')
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestResourceDetail:
    """Test resource detail endpoints."""

    def test_resource_detail_unauthenticated(self, api_client, course, user):
        """Test getting resource detail as unauthenticated user."""
        resource = Resource.objects.create(
            title='Test Resource',
            description='Test Description',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"/api/resources/{resource.slug}/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Test Resource'
        assert 'can_download' in response.data

    def test_resource_detail_includes_related(self, api_client, course, user):
        """Test that related resources are included."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"/api/resources/{resource.slug}/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'related_resources' in response.data

    def test_resource_detail_view_count_increments(self, api_client, course, user):
        """Test that view count increments on detail access."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved',
            view_count=0
        )
        url = f"/api/resources/{resource.slug}/"
        api_client.get(url)
        resource.refresh_from_db()
        assert resource.view_count == 1

    def test_pending_resource_hidden_from_student(self, api_client, course, user):
        """Test that pending resources are hidden from regular students."""
        resource = Resource.objects.create(
            title='Pending Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='pending'
        )
        url = f"/api/resources/{resource.slug}/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_pending_resource_visible_to_owner(self, authenticated_client, course, user):
        """Test that pending resources are visible to the owner."""
        resource = Resource.objects.create(
            title='My Pending Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='pending'
        )
        url = f"/api/resources/{resource.slug}/"
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestResourceDownload:
    """Test resource download endpoint."""

    def test_download_approved_resource(self, api_client, course, user):
        """Test downloading an approved resource."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"/api/resources/{resource.slug}/download/"
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'file_url' in response.data

    def test_download_pending_resource_blocked(self, api_client, course, user):
        """Test that pending resources cannot be downloaded."""
        resource = Resource.objects.create(
            title='Pending Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='pending'
        )
        url = f"/api/resources/{resource.slug}/download/"
        response = api_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestResourceShare:
    """Test resource sharing endpoints."""

    def test_share_link_for_approved_public_resource(self, authenticated_client, course, user):
        resource = Resource.objects.create(
            title="Data Structures Notes",
            resource_type="notes",
            course=course,
            uploaded_by=user,
            status="approved",
            is_public=True,
        )
        url = reverse("resources:resource-share-link", kwargs={"slug": resource.slug})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["can_share"] is True
        assert resource.slug in response.data["share_url"]
        assert "Check out this resource on CampusHub" in response.data["share_message"]

    def test_share_link_allows_uuid_lookup(self, authenticated_client, course, user):
        resource = Resource.objects.create(
            title="UUID Share Lookup",
            resource_type="notes",
            course=course,
            uploaded_by=user,
            status="approved",
            is_public=True,
        )
        url = reverse("resources:resource-share-link", kwargs={"slug": str(resource.id)})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["slug"] == resource.slug

    def test_share_link_rejects_private_resource(self, authenticated_client, course, user):
        resource = Resource.objects.create(
            title="Private Notes",
            resource_type="notes",
            course=course,
            uploaded_by=user,
            status="approved",
            is_public=False,
        )
        url = reverse("resources:resource-share-link", kwargs={"slug": resource.slug})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_share_link_rejects_pending_resource(self, authenticated_client, course, user):
        resource = Resource.objects.create(
            title="Pending Notes",
            resource_type="notes",
            course=course,
            uploaded_by=user,
            status="pending",
            is_public=True,
        )
        url = reverse("resources:resource-share-link", kwargs={"slug": resource.slug})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_share_action_increments_share_count(self, authenticated_client, course, user):
        resource = Resource.objects.create(
            title="Share Me",
            resource_type="notes",
            course=course,
            uploaded_by=user,
            status="approved",
            is_public=True,
            share_count=0,
        )
        url = reverse("resources:resource-share", kwargs={"slug": resource.slug})
        response = authenticated_client.post(url, {"share_method": "copy_link"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        resource.refresh_from_db()
        assert resource.share_count == 1
        assert response.data["share_count"] == 1

    def test_share_action_requires_authentication(self, api_client, course, user):
        resource = Resource.objects.create(
            title="Auth Required Share",
            resource_type="notes",
            course=course,
            uploaded_by=user,
            status="approved",
            is_public=True,
        )
        url = reverse("resources:resource-share", kwargs={"slug": resource.slug})
        response = api_client.post(url, {"share_method": "copy_link"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_share_link_invalid_resource(self, authenticated_client):
        url = reverse(
            "resources:resource-share-link",
            kwargs={"slug": "non-existent-resource"},
        )
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestResourceBookmark:
    """Test resource bookmark toggle endpoint."""

    def test_toggle_bookmark(self, authenticated_client, course, user):
        """Test toggling bookmark on a resource."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"/api/resources/{resource.slug}/bookmark/"
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_bookmarked'] is True

    def test_bookmark_requires_auth(self, api_client, course, user):
        """Test that bookmarking requires authentication."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"/api/resources/{resource.slug}/bookmark/"
        response = api_client.post(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestResourceRating:
    """Test resource rating endpoint."""

    def test_rate_resource(self, authenticated_client, course, admin_user):
        """Test rating a resource."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=admin_user,
            status='approved'
        )
        url = f"/api/resources/{resource.slug}/rate/"
        response = authenticated_client.post(url, {'value': 5})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['user_rating'] == 5

    def test_invalid_rating_rejected(self, authenticated_client, course, user):
        """Test that invalid ratings are rejected."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"/api/resources/{resource.slug}/rate/"
        response = authenticated_client.post(url, {'value': 6})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rating_requires_auth(self, api_client, course, user):
        """Test that rating requires authentication."""
        resource = Resource.objects.create(
            title='Test Resource',
            resource_type='notes',
            course=course,
            uploaded_by=user,
            status='approved'
        )
        url = f"/api/resources/{resource.slug}/rate/"
        response = api_client.post(url, {'value': 5})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUploadModule:
    """Test Module 6 upload workflow requirements."""

    def _payload(self, faculty, department, course, unit, **extra):
        data = {
            'title': 'Algorithms Notes',
            'description': 'Week 1 notes',
            'resource_type': 'notes',
            'faculty': str(faculty.id),
            'department': str(department.id),
            'course': str(course.id),
            'unit': str(unit.id),
            'semester': '1',
            'year_of_study': 2,
            'tags': 'algorithms, notes',
        }
        data.update(extra)
        return data

    def test_upload_sets_pending_by_default(self, authenticated_client, faculty, department, course, unit, upload_file):
        url = reverse('resources:resource-list')
        data = self._payload(faculty, department, course, unit, file=upload_file)
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] == 'pending'

    def test_unsupported_file_type_rejected(self, authenticated_client, faculty, department, course, unit):
        file_obj = SimpleUploadedFile('malware.exe', b'bad', content_type='application/octet-stream')
        url = reverse('resources:resource-list')
        data = self._payload(faculty, department, course, unit, file=file_obj)
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'file' in str(response.data).lower()

    def test_missing_required_metadata_rejected(self, authenticated_client, upload_file):
        url = reverse('resources:resource-list')
        response = authenticated_client.post(
            url,
            {'title': 'No metadata', 'resource_type': 'notes', 'file': upload_file},
            format='multipart'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'faculty' in response.data

    def test_invalid_unit_course_relation_rejected(self, authenticated_client, faculty, department, course, unit, upload_file):
        other_course = Course.objects.create(
            department=department,
            name='Bachelor of IT',
            code='BIT',
            duration_years=4
        )
        url = reverse('resources:resource-list')
        data = self._payload(faculty, department, other_course, unit, file=upload_file)
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'unit' in response.data

    def test_duplicate_upload_rejected(self, authenticated_client, faculty, department, course, unit):
        url = reverse('resources:resource-list')
        first = self._payload(
            faculty, department, course, unit,
            file=SimpleUploadedFile('dup.pdf', b'%PDF-1.4 first', content_type='application/pdf')
        )
        second = self._payload(
            faculty, department, course, unit,
            file=SimpleUploadedFile('dup.pdf', b'%PDF-1.4 first', content_type='application/pdf')
        )
        assert authenticated_client.post(url, first, format='multipart').status_code == status.HTTP_201_CREATED
        response = authenticated_client.post(url, second, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_my_uploads_lists_only_owner(self, authenticated_client, user, admin_user, faculty, department, course, unit):
        Resource.objects.create(
            title='Mine',
            resource_type='notes',
            uploaded_by=user,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            semester='1',
            year_of_study=2,
            status='pending'
        )
        Resource.objects.create(
            title='Not Mine',
            resource_type='notes',
            uploaded_by=admin_user,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            semester='1',
            year_of_study=2,
            status='pending'
        )
        response = authenticated_client.get(reverse('resources:my-uploads'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_owner_can_edit_pending_upload(self, authenticated_client, user, faculty, department, course, unit):
        resource = Resource.objects.create(
            title='Edit Me',
            resource_type='notes',
            uploaded_by=user,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            semester='1',
            year_of_study=2,
            status='pending'
        )
        response = authenticated_client.patch(
            reverse('resources:resource-update', kwargs={'pk': resource.id}),
            {'title': 'Edited Title'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        resource.refresh_from_db()
        assert resource.title == 'Edited Title'

    def test_owner_cannot_edit_approved_upload(self, authenticated_client, user, faculty, department, course, unit):
        resource = Resource.objects.create(
            title='Locked',
            resource_type='notes',
            uploaded_by=user,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            semester='1',
            year_of_study=2,
            status='approved'
        )
        response = authenticated_client.patch(
            reverse('resources:resource-update', kwargs={'pk': resource.id}),
            {'title': 'Should Not Work'},
            format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_can_delete_pending_upload(self, authenticated_client, user, faculty, department, course, unit):
        resource = Resource.objects.create(
            title='Delete Me',
            resource_type='notes',
            uploaded_by=user,
            faculty=faculty,
            department=department,
            course=course,
            unit=unit,
            semester='1',
            year_of_study=2,
            status='pending'
        )
        response = authenticated_client.delete(
            reverse('resources:resource-update', kwargs={'pk': resource.id})
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Resource.objects.filter(id=resource.id).exists()

    def test_auto_fill_title_from_filename(self, authenticated_client, faculty, department, course, unit):
        url = reverse('resources:resource-list')
        data = self._payload(
            faculty,
            department,
            course,
            unit,
            title='',
            file=SimpleUploadedFile('machine_learning_intro.pdf', b'%PDF-1.4 data', content_type='application/pdf')
        )
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Machine Learning Intro'

    def test_auto_suggest_tags_when_missing(self, authenticated_client, faculty, department, course, unit, upload_file):
        url = reverse('resources:resource-list')
        data = self._payload(faculty, department, course, unit, file=upload_file, tags='')
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['tags'] != ''

    def test_auto_notify_moderators_and_log_activity(
        self, authenticated_client, user, moderator_user, admin_user, faculty, department, course, unit, upload_file
    ):
        url = reverse('resources:resource-list')
        data = self._payload(faculty, department, course, unit, file=upload_file)
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

        assert Notification.objects.filter(
            recipient=moderator_user,
            title='New Resource Pending Review',
        ).exists()
        assert Notification.objects.filter(
            recipient=admin_user,
            title='New Resource Pending Review',
        ).exists()
        assert UserActivity.objects.filter(user=user, action='upload').exists()

    def test_auto_recalculate_upload_count_and_storage(self, authenticated_client, user, faculty, department, course, unit):
        upload = SimpleUploadedFile('count_check.pdf', b'%PDF-1.4 counting', content_type='application/pdf')
        url = reverse('resources:resource-list')
        data = self._payload(faculty, department, course, unit, file=upload)
        response = authenticated_client.post(url, data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED

        user.refresh_from_db()
        user.profile.refresh_from_db()
        storage = UserStorage.objects.get(user=user)
        assert user.profile.total_uploads == 1
        assert storage.used_storage > 0

        resource_id = response.data['id']
        delete_response = authenticated_client.delete(reverse('resources:resource-update', kwargs={'pk': resource_id}))
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        user.profile.refresh_from_db()
        storage.refresh_from_db()
        assert user.profile.total_uploads == 0
        assert storage.used_storage == 0
