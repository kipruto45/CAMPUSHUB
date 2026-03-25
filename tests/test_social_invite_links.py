import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_invite_validate_unknown_token_returns_message(client):
    url = reverse("social:invite-link-validate", args=["bogus-token"])
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data


@pytest.mark.django_db
def test_invite_landing_unknown_token_redirects_or_json(client, settings):
    # Ensure frontend base is set so redirect is predictable
    settings.FRONTEND_URL = "https://example.com"
    url = reverse("social:invite-landing", args=["bogus-token"])
    resp = client.get(url, HTTP_ACCEPT="text/html")
    # Should render a friendly fallback instead of blank/500
    assert resp.status_code == 404
    assert "Invite not available" in resp.content.decode()
