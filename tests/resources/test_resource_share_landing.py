import pytest
from django.urls import reverse

from apps.resources.models import Resource


@pytest.mark.django_db
def test_resource_share_landing_valid_json(client, settings, course, user):
    settings.FRONTEND_URL = "https://campus.test"
    resource = Resource.objects.create(
        title="Landing Resource",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        is_public=True,
    )

    url = reverse("resource-share-landing", kwargs={"slug": resource.slug})
    response = client.get(url, HTTP_ACCEPT="application/json")

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["resource"]["slug"] == resource.slug
    assert body["web_url"].endswith(f"/resource/{resource.slug}")
    assert body["deep_link"].endswith(f"/{resource.slug}")


@pytest.mark.django_db
def test_resource_share_landing_invalid_json(client):
    url = reverse("resource-share-landing", kwargs={"slug": "does-not-exist"})
    response = client.get(url, HTTP_ACCEPT="application/json")

    assert response.status_code == 404
    assert response.json()["valid"] is False


@pytest.mark.django_db
def test_resource_share_landing_html_redirects_or_fallback(client, settings, course, user):
    settings.FRONTEND_URL = "https://campus.test"
    resource = Resource.objects.create(
        title="Landing HTML Resource",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        is_public=True,
    )
    url = reverse("resource-share-landing", kwargs={"slug": resource.slug})

    response = client.get(url, HTTP_ACCEPT="text/html")
    assert response.status_code in (301, 302)
    assert response.url.endswith(f"/resource/{resource.slug}")

    # Invalid slug returns a human friendly fallback page instead of a blank screen
    bad_response = client.get(
        reverse("resource-share-landing", kwargs={"slug": "missing"}),
        HTTP_ACCEPT="text/html",
    )
    assert bad_response.status_code == 404
    assert "Link not available" in bad_response.content.decode()
