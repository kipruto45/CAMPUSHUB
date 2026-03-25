import pytest
from rest_framework_simplejwt.tokens import AccessToken


@pytest.mark.django_db
def test_admin_can_impersonate_user(admin_client, admin_user, user):
    url = f"/api/admin-management/users/{user.id}/impersonate/"
    resp = admin_client.post(url)

    assert resp.status_code == 201
    assert "access" in resp.data

    token = AccessToken(resp.data["access"])
    assert token["user_id"] == user.id
    assert token["impersonated_by"] == admin_user.id
    # short-lived: less than or equal to 30 minutes
    assert token.lifetime.total_seconds() <= 30 * 60
