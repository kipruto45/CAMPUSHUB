"""
Comprehensive tests for analytics module.
Tests for AnalyticsEvent, DailyMetric, Cohort, UserActivitySummary, LearningInsight, and StudentRiskAssessment.
"""

import pytest
from datetime import date, timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics.models import (
    AnalyticsEvent,
    DailyMetric,
    Cohort,
    UserActivitySummary,
    LearningInsight,
    StudentRiskAssessment,
    RiskLevel,
)

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        role='STUDENT'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        email='admin@example.com',
        password='adminpass123',
        role='ADMIN'
    )


# =========================
# AnalyticsEvent Tests
# =========================

@pytest.mark.django_db
class TestAnalyticsEvent:
    """Tests for AnalyticsEvent model."""

    def test_create_event(self, user):
        """Test creating an analytics event."""
        event = AnalyticsEvent.objects.create(
            user=user,
            event_type='page_view',
            event_name='Home Page',
            properties={'page': '/'},
        )
        
        assert event.id is not None
        assert event.event_type == 'page_view'
        assert event.event_name == 'Home Page'
        assert str(event) == 'page_view: Home Page'

    def test_event_types(self, user):
        """Test all event type choices."""
        event_types = [
            'page_view', 'resource_view', 'resource_download', 'resource_upload',
            'search', 'bookmark', 'favorite', 'comment', 'rating', 'share',
            'signup', 'login', 'logout', 'subscription', 'payment',
            'chat_message', 'study_group_join', 'notification_click',
        ]
        
        for event_type in event_types:
            event = AnalyticsEvent.objects.create(
                user=user,
                event_type=event_type,
                event_name=f'Test {event_type}',
            )
            assert event.event_type == event_type

    def test_anonymous_event(self):
        """Test creating an event without a user."""
        event = AnalyticsEvent.objects.create(
            event_type='page_view',
            event_name='Landing Page',
            session_id='session-123',
        )
        
        assert event.user is None
        assert event.session_id == 'session-123'

    def test_event_with_utm(self, user):
        """Test event with UTM parameters."""
        event = AnalyticsEvent.objects.create(
            user=user,
            event_type='page_view',
            event_name='Campaign Page',
            utm_source='google',
            utm_medium='cpc',
            utm_campaign='spring_sale',
            referrer='https://google.com',
        )
        
        assert event.utm_source == 'google'
        assert event.utm_medium == 'cpc'
        assert event.utm_campaign == 'spring_sale'

    def test_event_with_device_info(self, user):
        """Test event with device information."""
        event = AnalyticsEvent.objects.create(
            user=user,
            event_type='page_view',
            event_name='Mobile Page',
            device_type='mobile',
            browser='Chrome',
            os='Android',
            country='US',
            city='New York',
        )
        
        assert event.device_type == 'mobile'
        assert event.browser == 'Chrome'
        assert event.os == 'Android'
        assert event.country == 'US'

    def test_event_with_duration(self, user):
        """Test event with duration."""
        event = AnalyticsEvent.objects.create(
            user=user,
            event_type='resource_view',
            event_name='Reading Resource',
            duration_seconds=300,
        )
        
        assert event.duration_seconds == 300


# =========================
# DailyMetric Tests
# =========================

@pytest.mark.django_db
class TestDailyMetric:
    """Tests for DailyMetric model."""

    def test_create_daily_metric(self):
        """Test creating a daily metric."""
        metric = DailyMetric.objects.create(
            date=date.today(),
            total_users=1000,
            active_users=500,
            new_signups=25,
            active_dau=450,
            active_wau=800,
            active_mau=950,
        )
        
        assert metric.id is not None
        assert metric.date == date.today()
        assert metric.total_users == 1000
        assert metric.active_users == 500
        assert str(metric) == f"Metrics for {date.today()}"

    def test_content_metrics(self):
        """Test content metrics."""
        metric = DailyMetric.objects.create(
            date=date.today(),
            total_resources=500,
            new_resources=10,
            total_downloads=100,
            total_views=1000,
        )
        
        assert metric.total_resources == 500
        assert metric.new_resources == 10
        assert metric.total_downloads == 100
        assert metric.total_views == 1000

    def test_engagement_metrics(self):
        """Test engagement metrics."""
        metric = DailyMetric.objects.create(
            date=date.today(),
            total_bookmarks=50,
            total_favorites=30,
            total_comments=100,
            total_ratings=75,
            total_shares=20,
        )
        
        assert metric.total_bookmarks == 50
        assert metric.total_favorites == 30
        assert metric.total_comments == 100
        assert metric.total_ratings == 75
        assert metric.total_shares == 20


@pytest.mark.django_db
def test_user_activity_summary_blocks_free_plan_users(api_client, user):
    api_client.force_authenticate(user=user)

    response = api_client.get("/api/analytics/user/activity-summary/")

    assert response.status_code == 403
    assert response.data["feature"] == "advanced_analytics"

    def test_social_metrics(self):
        """Test social metrics."""
        metric = DailyMetric.objects.create(
            date=date.today(),
            new_friendships=15,
            study_groups_created=5,
            messages_sent=200,
        )
        
        assert metric.new_friendships == 15
        assert metric.study_groups_created == 5
        assert metric.messages_sent == 200

    def test_revenue_metrics(self):
        """Test revenue metrics."""
        metric = DailyMetric.objects.create(
            date=date.today(),
            new_subscriptions=10,
            total_revenue=500.00,
            total_storage_used_gb=100.50,
        )
        
        assert metric.new_subscriptions == 10
        assert metric.total_revenue == 500.00
        assert metric.total_storage_used_gb == 100.50


# =========================
# Cohort Tests
# =========================

@pytest.mark.django_db
class TestCohort:
    """Tests for Cohort model."""

    def test_create_cohort(self):
        """Test creating a cohort."""
        cohort = Cohort.objects.create(
            cohort_date=date.today(),
            cohort_type='signup',
            retention_data={'0': 100, '1': 80, '2': 60},
            initial_users=100,
            total_retained=60,
            retention_rate=60.00,
        )
        
        assert cohort.id is not None
        assert cohort.cohort_date == date.today()
        assert cohort.cohort_type == 'signup'
        assert str(cohort) == f"signup - {date.today()}"

    def test_cohort_types(self):
        """Test different cohort types."""
        cohort_types = ['signup', 'first_action', 'subscription']
        
        for cohort_type in cohort_types:
            cohort = Cohort.objects.create(
                cohort_date=date.today(),
                cohort_type=cohort_type,
                retention_data={},
            )
            assert cohort.cohort_type == cohort_type


# =========================
# UserActivitySummary Tests
# =========================

@pytest.mark.django_db
class TestUserActivitySummary:
    """Tests for UserActivitySummary model."""

    def test_create_activity_summary(self, user):
        """Test creating a user activity summary."""
        summary = UserActivitySummary.objects.create(
            user=user,
            period_start=date.today() - timedelta(days=7),
            period_end=date.today(),
            period_type='weekly',
            page_views=100,
            resource_views=50,
            downloads=10,
            uploads=5,
            searches=20,
            bookmarks=5,
            favorites=3,
            comments=15,
            ratings=8,
            messages_sent=30,
            total_active_seconds=3600,
            current_streak_days=5,
            longest_streak_days=10,
        )
        
        assert summary.id is not None
        assert summary.user == user
        assert summary.period_type == 'weekly'
        assert str(summary) == f"{user.username} - {date.today() - timedelta(days=7)}"

    def test_period_types(self, user):
        """Test different period types."""
        period_types = ['daily', 'weekly', 'monthly']
        
        for period_type in period_types:
            summary = UserActivitySummary.objects.create(
                user=user,
                period_start=date.today(),
                period_end=date.today(),
                period_type=period_type,
            )
            assert summary.period_type == period_type


# =========================
# LearningInsight Tests
# =========================

@pytest.mark.django_db
class TestLearningInsight:
    """Tests for LearningInsight model."""

    def test_create_insight(self, user):
        """Test creating a learning insight."""
        insight = LearningInsight.objects.create(
            user=user,
            insight_type='study_pattern',
            title='Improved Study Habits',
            description='You have been studying consistently for the past week.',
            priority='medium',
        )
        
        assert insight.id is not None
        assert insight.insight_type == 'study_pattern'
        assert insight.title == 'Improved Study Habits'
        assert insight.is_read is False
        assert str(insight) == 'study_pattern: Improved Study Habits'

    def test_insight_types(self, user):
        """Test all insight type choices."""
        insight_types = [
            'study_pattern', 'resource_gap', 'engagement_drop',
            'progress', 'recommendation', 'alert',
        ]
        
        for insight_type in insight_types:
            insight = LearningInsight.objects.create(
                user=user,
                insight_type=insight_type,
                title=f'Test {insight_type}',
                description='Test description',
            )
            assert insight.insight_type == insight_type

    def test_mark_as_read(self, user):
        """Test marking insight as read."""
        insight = LearningInsight.objects.create(
            user=user,
            insight_type='recommendation',
            title='Test',
            description='Test',
        )
        
        insight.is_read = True
        insight.read_at = timezone.now()
        insight.save()
        
        assert insight.is_read is True
        assert insight.read_at is not None


# =========================
# StudentRiskAssessment Tests
# =========================

@pytest.mark.django_db
class TestStudentRiskAssessment:
    """Tests for StudentRiskAssessment model."""

    def test_create_risk_assessment(self, user):
        """Test creating a student risk assessment."""
        assessment = StudentRiskAssessment.objects.create(
            user=user,
            risk_level=RiskLevel.LOW,
            risk_category='overall',
            risk_score=25.0,
            risk_factors={'low_activity': True, 'good_grades': True},
        )
        
        assert assessment.id is not None
        assert assessment.risk_level == RiskLevel.LOW
        assert assessment.risk_score == 25.0
        assert assessment.is_active is True
        assert str(user.email) in str(assessment)

    def test_risk_levels(self, user):
        """Test all risk level choices."""
        risk_levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        
        for risk_level in risk_levels:
            assessment = StudentRiskAssessment.objects.create(
                user=user,
                risk_level=risk_level,
                risk_category='overall',
                risk_score=50.0,
            )
            assert assessment.risk_level == risk_level

    def test_risk_categories(self, user):
        """Test all risk category choices."""
        categories = ['academic', 'engagement', 'attendance', 'behavioral', 'overall']
        
        for category in categories:
            assessment = StudentRiskAssessment.objects.create(
                user=user,
                risk_level=RiskLevel.MEDIUM,
                risk_category=category,
                risk_score=50.0,
            )
            assert assessment.risk_category == category

    def test_risk_change(self, user):
        """Test risk change tracking."""
        assessment = StudentRiskAssessment.objects.create(
            user=user,
            risk_level=RiskLevel.HIGH,
            risk_category='overall',
            risk_score=75.0,
            previous_risk_level=RiskLevel.MEDIUM,
            risk_change='increased',
        )
        
        assert assessment.previous_risk_level == RiskLevel.MEDIUM
        assert assessment.risk_change == 'increased'

    def test_alert_sent(self, user):
        """Test alert sent tracking."""
        assessment = StudentRiskAssessment.objects.create(
            user=user,
            risk_level=RiskLevel.CRITICAL,
            risk_category='overall',
            risk_score=90.0,
            alert_sent=True,
            alert_sent_at=timezone.now(),
        )
        
        assert assessment.alert_sent is True
        assert assessment.alert_sent_at is not None

    def test_recommendations(self, user):
        """Test recommendations field."""
        recommendations = [
            {'action': 'schedule_meeting', 'priority': 'high'},
            {'action': 'send_email', 'priority': 'medium'},
        ]
        
        assessment = StudentRiskAssessment.objects.create(
            user=user,
            risk_level=RiskLevel.HIGH,
            risk_category='engagement',
            risk_score=80.0,
            recommendations=recommendations,
        )
        
        assert len(assessment.recommendations) == 2
        assert assessment.recommendations[0]['action'] == 'schedule_meeting'
