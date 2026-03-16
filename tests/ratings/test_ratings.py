"""Tests for ratings module."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.ratings.models import Rating
from apps.resources.models import Resource

User = get_user_model()


@pytest.fixture
def rateable_resource(db, admin_user):
    """Create an approved resource that users can rate."""
    return Resource.objects.create(
        title="Rateable Resource",
        resource_type="notes",
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
    )


@pytest.mark.django_db
class TestRatingsModule:
    """Ratings endpoints and score recalculation tests."""

    def test_user_can_create_rating(
        self, authenticated_client, user, rateable_resource
    ):
        response = authenticated_client.post(
            reverse("ratings:rating-list"),
            {"resource": str(rateable_resource.id), "value": 4},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Rating.objects.filter(
            user=user,
            resource=rateable_resource,
            value=4,
        ).exists()

    def test_duplicate_rating_request_updates_existing(
        self, authenticated_client, user, rateable_resource
    ):
        first = authenticated_client.post(
            reverse("ratings:rating-list"),
            {"resource": str(rateable_resource.id), "value": 2},
            format="json",
        )
        assert first.status_code == status.HTTP_201_CREATED

        second = authenticated_client.post(
            reverse("ratings:rating-list"),
            {"resource": str(rateable_resource.id), "value": 5},
            format="json",
        )
        assert second.status_code == status.HTTP_200_OK
        ratings_for_user = Rating.objects.filter(
            user=user, resource=rateable_resource
        )
        assert ratings_for_user.count() == 1
        assert ratings_for_user.first().value == 5

    def test_rate_resource_endpoint_requires_authentication(
        self, api_client, rateable_resource
    ):
        response = api_client.post(
            reverse(
                "ratings:rate-resource",
                kwargs={"resource_id": rateable_resource.id},
            ),
            {"value": 4},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_average_rating_is_recalculated_after_multiple_ratings(
        self, authenticated_client, api_client, user, rateable_resource
    ):
        other_user = User.objects.create_user(
            email="other-rating@test.com",
            password="testpass123",
            full_name="Other Rating User",
            registration_number="RAT001",
            role="student",
        )
        authenticated_client.post(
            reverse(
                "ratings:rate-resource",
                kwargs={"resource_id": rateable_resource.id},
            ),
            {"value": 5},
            format="json",
        )

        api_client.force_authenticate(user=other_user)
        api_client.post(
            reverse(
                "ratings:rate-resource",
                kwargs={"resource_id": rateable_resource.id},
            ),
            {"value": 3},
            format="json",
        )

        rateable_resource.refresh_from_db()
        assert float(rateable_resource.average_rating) == 4.0
        assert Rating.objects.filter(resource=rateable_resource).count() == 2

    def test_resource_rating_list_returns_ratings(
        self, authenticated_client, user, rateable_resource
    ):
        Rating.objects.create(user=user, resource=rateable_resource, value=4)
        response = authenticated_client.get(
            reverse(
                "ratings:resource-ratings",
                kwargs={"resource_id": rateable_resource.id},
            )
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
