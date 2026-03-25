import pytest
from django.urls import reverse
from django.utils import timezone

from apps.analytics.models import AnalyticsEvent


@pytest.mark.django_db
def test_event_analytics_endpoint_auth(client, django_user_model):
    user = django_user_model.objects.create_user(username="u", password="p")
    client.login(username="u", password="p")

    AnalyticsEvent.objects.create(
        user=user,
        event_type="event_attended",
        event_name="Workshop",
        timestamp=timezone.now(),
    )

    url = reverse("analytics:event-analytics")
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert "attendance_trend" in data
    assert isinstance(data["attendance_trend"], list)
