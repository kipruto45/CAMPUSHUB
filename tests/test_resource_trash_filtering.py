import pytest
from django.contrib.auth import get_user_model
from apps.resources.models import Resource
from apps.resources.views import ResourceViewSet
from rest_framework.test import APIRequestFactory, force_authenticate


@pytest.mark.django_db
def test_resource_queryset_excludes_trashed():
    user = get_user_model().objects.create_user(username="u", email="u@e.com", password="pass")
    live = Resource.objects.create(title="Live", uploaded_by=user, status="approved", is_public=True)
    trashed = Resource.objects.create(title="Trash", uploaded_by=user, status="approved", is_public=True, is_deleted=True)

    factory = APIRequestFactory()
    request = factory.get("/api/v1/resources/")
    force_authenticate(request, user=user)

    view = ResourceViewSet()
    view.request = request
    qs = view.get_queryset()

    assert live in qs
    assert trashed not in qs


@pytest.mark.django_db
def test_restore_self_allows_owner_to_restore():
    user = get_user_model().objects.create_user(username="owner", email="o@e.com", password="pass")
    trashed = Resource.all_objects.create(
        title="Needs Restore",
        uploaded_by=user,
        status="approved",
        is_public=True,
        is_deleted=True,
    )

    factory = APIRequestFactory()
    request = factory.post(f"/api/v1/resources/{trashed.slug}/restore-self/")
    force_authenticate(request, user=user)

    view = ResourceViewSet.as_view({"post": "restore_self"})
    response = view(request, slug=trashed.slug)

    trashed.refresh_from_db()
    assert response.status_code == 200
    assert trashed.is_deleted is False
    assert trashed.status == "pending"
