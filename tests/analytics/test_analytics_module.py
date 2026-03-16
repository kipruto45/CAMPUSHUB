"""Tests for analytics services and endpoints."""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.activity.models import ActivityType, RecentActivity
from apps.analytics.models import DailyAnalytics
from apps.analytics.services import AnalyticsService, DashboardChartService
from apps.bookmarks.models import Bookmark
from apps.comments.models import Comment
from apps.downloads.models import Download
from apps.favorites.models import Favorite, FavoriteType
from apps.ratings.models import Rating
from apps.resources.models import Resource


@pytest.fixture
def analytics_seed_data(user, admin_user, course):
    resource_1 = Resource.objects.create(
        title="Resource One",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
    )
    resource_2 = Resource.objects.create(
        title="Resource Two",
        resource_type="slides",
        course=course,
        uploaded_by=user,
        status="approved",
    )
    resource_3 = Resource.objects.create(
        title="Resource Three",
        resource_type="notes",
        course=course,
        uploaded_by=admin_user,
        status="pending",
    )

    Download.objects.create(user=user, resource=resource_1)
    Download.objects.create(user=admin_user, resource=resource_1)
    Download.objects.create(user=user, resource=resource_1)
    Download.objects.create(user=user, resource=resource_2)

    return {
        "r1": resource_1,
        "r2": resource_2,
        "r3": resource_3,
    }


@pytest.mark.django_db
def test_dashboard_stats_service_returns_summary(analytics_seed_data):
    stats = AnalyticsService.get_dashboard_stats()

    assert stats["users"]["total"] >= 2
    assert stats["resources"]["total"] >= 3
    assert stats["resources"]["approved"] >= 2
    assert stats["downloads"]["total"] >= 4


@pytest.mark.django_db
def test_most_downloaded_resources_service_orders_results(analytics_seed_data):
    resources = list(AnalyticsService.get_most_downloaded_resources(limit=2))

    assert len(resources) == 2
    assert resources[0].id == analytics_seed_data["r1"].id


@pytest.mark.django_db
def test_most_active_uploaders_service_orders_results(analytics_seed_data):
    users = list(AnalyticsService.get_most_active_uploaders(limit=2))

    assert len(users) >= 1
    assert users[0].uploads.count() >= users[-1].uploads.count()


@pytest.mark.django_db
def test_resources_by_course_and_trends_services(analytics_seed_data):
    by_course = list(AnalyticsService.get_resources_by_course())
    upload_trends = list(AnalyticsService.get_daily_upload_trends(days=7))
    download_trends = list(AnalyticsService.get_daily_download_trends(days=7))

    assert by_course
    assert "count" in by_course[0]
    assert upload_trends
    assert "count" in upload_trends[0]
    assert download_trends
    assert "count" in download_trends[0]


@pytest.mark.django_db
def test_dashboard_endpoint_requires_admin(authenticated_client):
    response = authenticated_client.get("/api/analytics/dashboard/")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_dashboard_and_analytics_endpoints_for_admin(
    admin_client,
    analytics_seed_data,
):
    dashboard = admin_client.get("/api/analytics/dashboard/")
    most_downloaded = admin_client.get("/api/analytics/resources/?limit=5")
    uploaders = admin_client.get("/api/analytics/uploaders/?limit=5")
    by_course = admin_client.get("/api/analytics/resources-by-course/")
    upload_trends = admin_client.get("/api/analytics/upload-trends/?days=7")
    download_trends = admin_client.get(
        "/api/analytics/download-trends/?days=7"
    )

    assert dashboard.status_code == status.HTTP_200_OK
    assert "users" in dashboard.data

    assert most_downloaded.status_code == status.HTTP_200_OK
    assert isinstance(most_downloaded.data, list)

    assert uploaders.status_code == status.HTTP_200_OK
    assert isinstance(uploaders.data, list)

    assert by_course.status_code == status.HTTP_200_OK
    assert isinstance(by_course.data, list)

    assert upload_trends.status_code == status.HTTP_200_OK
    assert isinstance(upload_trends.data, list)

    assert download_trends.status_code == status.HTTP_200_OK
    assert isinstance(download_trends.data, list)


@pytest.mark.django_db
def test_activity_summary_and_engagement_score_services(user, admin_user, course):
    baseline = AnalyticsService.get_user_activity_summary(user)

    uploaded_resource = Resource.objects.create(
        title="User Upload",
        resource_type="notes",
        course=course,
        uploaded_by=user,
        status="approved",
    )
    target_resource = Resource.objects.create(
        title="Target Resource",
        resource_type="book",
        course=course,
        uploaded_by=admin_user,
        status="approved",
    )
    Download.objects.create(user=user, resource=target_resource)
    Bookmark.objects.create(user=user, resource=target_resource)
    Favorite.objects.create(
        user=user,
        favorite_type=FavoriteType.RESOURCE,
        resource=target_resource,
    )
    Comment.objects.create(
        user=user,
        resource=target_resource,
        content="Great resource",
    )
    Rating.objects.create(user=user, resource=target_resource, value=5)
    RecentActivity.objects.create(
        user=user,
        activity_type=ActivityType.VIEWED_RESOURCE,
        resource=target_resource,
    )

    summary = AnalyticsService.get_user_activity_summary(user)
    score = AnalyticsService.get_user_engagement_score(user)

    assert summary["uploads"] >= baseline["uploads"] + 1
    assert summary["downloads"] >= baseline["downloads"] + 1
    assert summary["bookmarks"] >= baseline["bookmarks"] + 1
    assert summary["favorites"] >= baseline["favorites"] + 1
    assert summary["comments"] >= baseline["comments"] + 1
    assert summary["ratings"] >= baseline["ratings"] + 1
    assert summary["recent_activities"] >= baseline["recent_activities"] + 1
    assert uploaded_resource.id
    assert 0 < score <= 100


@pytest.mark.django_db
def test_demographics_trends_and_platform_health_services(
    user,
    admin_user,
    faculty,
    course,
    analytics_seed_data,
):
    user.faculty = faculty
    user.course = course
    user.year_of_study = 2
    user.save(update_fields=["faculty", "course", "year_of_study"])

    admin_user.faculty = faculty
    admin_user.course = course
    admin_user.year_of_study = 4
    admin_user.save(update_fields=["faculty", "course", "year_of_study"])

    demographics = AnalyticsService.get_user_demographics()
    trends = AnalyticsService.get_popular_content_trends(days=14)
    health = AnalyticsService.get_platform_health()

    assert "by_faculty" in demographics
    assert "by_course" in demographics
    assert "by_year" in demographics
    assert isinstance(trends["downloads"], list)
    assert isinstance(trends["new_resources"], list)
    assert health["users"]["total"] >= 2
    assert "resources" in health
    assert "activity" in health


@pytest.mark.django_db
def test_resource_analytics_and_dashboard_chart_services(user, admin_user, course):
    resource = Resource.objects.create(
        title="Analytics Target",
        resource_type="notes",
        course=course,
        uploaded_by=admin_user,
        status="approved",
        file_type="pdf",
    )
    Download.objects.create(user=user, resource=resource)
    Download.objects.create(user=admin_user, resource=resource)
    Comment.objects.create(user=user, resource=resource, content="Useful")
    Rating.objects.create(user=user, resource=resource, value=4)
    RecentActivity.objects.create(
        user=user,
        activity_type=ActivityType.VIEWED_RESOURCE,
        resource=resource,
    )

    analytics = AnalyticsService.get_resource_analytics(resource.id)
    invalid = AnalyticsService.get_resource_analytics("not-a-uuid")
    downloads_chart = DashboardChartService.get_downloads_chart_data(days=30)
    type_chart = DashboardChartService.get_resource_types_chart_data()
    heatmap = DashboardChartService.get_user_activity_heatmap(user, days=30)

    assert analytics["downloads"]["total"] == 2
    assert analytics["ratings"]["average"] == 4
    assert analytics["comments"]["count"] == 1
    assert invalid is None
    assert len(downloads_chart["labels"]) == len(downloads_chart["values"])
    assert len(type_chart["labels"]) == len(type_chart["values"])
    assert len(heatmap["labels"]) == len(heatmap["values"])


@pytest.mark.django_db
def test_daily_snapshot_and_weekly_report_services(analytics_seed_data):
    assert DailyAnalytics.objects.count() == 0

    AnalyticsService.create_daily_snapshot()
    AnalyticsService.create_daily_snapshot()
    report = AnalyticsService.generate_weekly_report()

    assert DailyAnalytics.objects.count() == 1
    snapshot = DailyAnalytics.objects.first()
    assert snapshot.total_users >= 1
    assert snapshot.total_resources >= 1
    assert "period" in report
    assert "new_users" in report
    assert "new_resources" in report
    assert "total_downloads" in report


@pytest.mark.django_db
def test_extended_analytics_endpoints_permissions_and_validation(
    user,
    admin_user,
    analytics_seed_data,
):
    unauth_client = APIClient()
    student_client = APIClient()
    student_client.force_authenticate(user=user)
    admin_client = APIClient()
    admin_client.force_authenticate(user=admin_user)

    unauth_summary = unauth_client.get("/api/analytics/user/activity-summary/")
    user_summary = student_client.get(
        "/api/analytics/user/activity-summary/?days=abc"
    )
    user_heatmap = student_client.get(
        "/api/analytics/user/activity-heatmap/?days=bad"
    )
    user_score = student_client.get("/api/analytics/user/engagement-score/")
    forbidden_health = student_client.get("/api/analytics/health/")
    admin_health = admin_client.get("/api/analytics/health/")
    admin_invalid_limit = admin_client.get("/api/analytics/resources/?limit=invalid")
    admin_invalid_days = admin_client.get("/api/analytics/upload-trends/?days=bad")
    missing_resource_id = admin_client.get("/api/analytics/resource-analytics/")
    not_found_resource = admin_client.get(
        "/api/analytics/resource-analytics/?resource_id=not-a-uuid"
    )

    assert unauth_summary.status_code == status.HTTP_401_UNAUTHORIZED
    assert user_summary.status_code == status.HTTP_200_OK
    assert user_heatmap.status_code == status.HTTP_200_OK
    assert user_score.status_code == status.HTTP_200_OK
    assert "engagement_score" in user_score.data
    assert forbidden_health.status_code == status.HTTP_403_FORBIDDEN
    assert admin_health.status_code == status.HTTP_200_OK
    assert admin_invalid_limit.status_code == status.HTTP_200_OK
    assert isinstance(admin_invalid_limit.data, list)
    assert admin_invalid_days.status_code == status.HTTP_200_OK
    assert isinstance(admin_invalid_days.data, list)
    assert missing_resource_id.status_code == status.HTTP_400_BAD_REQUEST
    assert not_found_resource.status_code == status.HTTP_404_NOT_FOUND
