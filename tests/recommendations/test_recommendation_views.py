"""Endpoint tests for recommendation views."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status

from apps.resources.models import Resource


@pytest.mark.django_db
def test_for_you_requires_authentication(api_client):
    url = reverse("recommendations:for-you")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_for_you_uses_default_limit_when_query_is_invalid(authenticated_client, user):
    resource = Resource.objects.create(
        title="For You Item",
        resource_type="notes",
        uploaded_by=user,
        status="approved",
        is_public=True,
    )
    url = reverse("recommendations:for-you")

    with patch(
        "apps.recommendations.views.get_for_you_recommendations",
        return_value=Resource.objects.filter(id=resource.id),
    ) as mocked:
        response = authenticated_client.get(f"{url}?limit=bad-value")

    assert response.status_code == status.HTTP_200_OK
    mocked.assert_called_once_with(user, 10)
    assert response.data["count"] >= 1


@pytest.mark.django_db
def test_trending_clamps_limit_to_maximum(api_client, user):
    resource = Resource.objects.create(
        title="Trending Item",
        resource_type="notes",
        uploaded_by=user,
        status="approved",
        is_public=True,
    )
    url = reverse("recommendations:trending")

    with patch(
        "apps.recommendations.views.get_trending_resources",
        return_value=Resource.objects.filter(id=resource.id),
    ) as mocked:
        response = api_client.get(f"{url}?limit=999")

    assert response.status_code == status.HTTP_200_OK
    mocked.assert_called_once_with(50)
    assert response.data["count"] >= 1


@pytest.mark.django_db
def test_related_returns_empty_for_non_approved_resource(api_client, user):
    pending_resource = Resource.objects.create(
        title="Pending Item",
        resource_type="notes",
        uploaded_by=user,
        status="pending",
    )
    url = reverse(
        "recommendations:related",
        kwargs={"resource_id": pending_resource.id},
    )
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0


@pytest.mark.django_db
def test_dashboard_recommendations_requires_authentication(api_client):
    url = reverse("recommendations:dashboard")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_dashboard_recommendations_returns_all_sections(authenticated_client, user):
    resource = Resource.objects.create(
        title="Dashboard Recommendation",
        resource_type="notes",
        uploaded_by=user,
        status="approved",
        is_public=True,
    )
    url = reverse("recommendations:dashboard")
    qs = Resource.objects.filter(id=resource.id)

    with patch(
        "apps.recommendations.views.get_for_you_recommendations",
        return_value=qs,
    ):
        with patch(
            "apps.recommendations.views.get_trending_resources",
            return_value=qs,
        ):
            with patch(
                "apps.recommendations.views.get_popular_recommendations",
                return_value=qs,
            ):
                with patch(
                    "apps.recommendations.views.get_download_based_recommendations",
                    return_value=qs,
                ):
                    response = authenticated_client.get(f"{url}?limit=3")

    assert response.status_code == status.HTTP_200_OK
    assert "for_you" in response.data
    assert "trending" in response.data
    assert "popular" in response.data
    assert "download_based" in response.data
