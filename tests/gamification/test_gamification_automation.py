"""Tests for gamification automations wired to live app events."""

import pytest
from django.urls import reverse

from apps.accounts.verification import generate_signed_verification_token
from apps.bookmarks.models import Bookmark
from apps.comments.models import Comment
from apps.downloads.models import Download
from apps.gamification.models import Badge, Leaderboard, UserBadge, UserPoints, UserStats
from apps.ratings.models import Rating
from apps.resources.models import Resource


@pytest.fixture
def upload_automation_badge(db):
    return Badge.objects.create(
        name="Automation Uploader",
        slug="automation-uploader",
        description="Upload one resource",
        icon="fa-upload",
        category="uploads",
        points_required=7,
        requirement_type="total_uploads",
        requirement_value=1,
    )


@pytest.fixture
def verified_automation_badge(db):
    return Badge.objects.create(
        name="Automation Verified",
        slug="automation-verified",
        description="Verify email once",
        icon="fa-check-circle",
        category="special",
        points_required=4,
        requirement_type="email_verified",
        requirement_value=1,
    )


@pytest.mark.django_db
def test_resource_creation_records_upload_points_and_leaderboard(
    user,
    course,
    upload_automation_badge,
):
    resource = Resource.objects.create(
        title="Signal Driven Notes",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="pending",
        is_public=True,
    )

    stats = UserStats.objects.get(user=user)

    assert stats.total_uploads == 1
    assert UserPoints.objects.filter(user=user, action="upload_resource").count() == 1
    assert UserBadge.objects.filter(user=user, badge=upload_automation_badge).exists()
    assert Leaderboard.objects.get(period="all_time", user=user).points == stats.total_points
    assert resource.uploaded_by_id == user.id


@pytest.mark.django_db
def test_share_endpoint_increments_once_and_updates_gamification(
    authenticated_client,
    user,
    course,
):
    resource = Resource.objects.create(
        title="Share Automation Resource",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
        is_public=True,
        share_count=0,
    )

    response = authenticated_client.post(
        reverse("resources:resource-share", kwargs={"slug": resource.slug}),
        {"share_method": "copy_link"},
        format="json",
    )

    resource.refresh_from_db()
    stats = UserStats.objects.get(user=user)

    assert response.status_code == 200
    assert resource.share_count == 1
    assert response.data["share_count"] == 1
    assert stats.total_shares == 1
    assert stats.resources_shared == 1
    assert UserPoints.objects.filter(user=user, action="share_resource").count() == 1


@pytest.mark.django_db
def test_download_comment_rating_and_bookmark_events_update_stats(user, admin_user, course):
    resource = Resource.objects.create(
        title="Automation Resource",
        resource_type="notes",
        course=course,
        uploaded_by=admin_user,
        status="approved",
        is_public=True,
    )

    Download.objects.create(user=user, resource=resource)
    Comment.objects.create(user=user, resource=resource, content="Helpful notes")
    rating = Rating.objects.create(user=user, resource=resource, value=5)
    Bookmark.objects.create(user=user, resource=resource)

    stats = UserStats.objects.get(user=user)
    assert stats.total_downloads == 1
    assert stats.total_comments == 1
    assert stats.total_ratings == 1
    assert stats.resources_saved == 1
    assert UserPoints.objects.filter(user=user, action="download_resource").count() == 1
    assert UserPoints.objects.filter(user=user, action="comment_resource").count() == 1
    assert UserPoints.objects.filter(user=user, action="rate_resource").count() == 1

    rating.value = 4
    rating.save(update_fields=["value"])
    Bookmark.objects.filter(user=user, resource=resource).delete()

    stats.refresh_from_db()
    assert stats.total_ratings == 1
    assert stats.resources_saved == 0
    assert UserPoints.objects.filter(user=user, action="rate_resource").count() == 1


@pytest.mark.django_db
def test_email_verification_and_login_automations(
    api_client,
    user,
    verified_automation_badge,
):
    token = generate_signed_verification_token(user)

    verify_response = api_client.get(
        reverse("accounts:verify_email", kwargs={"token": token})
    )
    login_response = api_client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": "testpass123"},
        format="json",
    )
    second_login_response = api_client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": "testpass123"},
        format="json",
    )

    user.refresh_from_db()
    stats = UserStats.objects.get(user=user)

    assert verify_response.status_code == 200
    assert login_response.status_code == 200
    assert second_login_response.status_code == 200
    assert user.is_verified is True
    assert stats.consecutive_login_days == 1
    assert UserPoints.objects.filter(user=user, action="verify_email").count() == 1
    assert UserPoints.objects.filter(user=user, action="daily_login").count() == 1
    assert UserBadge.objects.filter(user=user, badge=verified_automation_badge).exists()
