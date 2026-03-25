"""
Predictive Analytics Service
Provides predictive analytics for user behavior, resource popularity, and churn analysis
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, List, Optional, Any
from django.db.models import Count, Sum
from django.utils import timezone


@dataclass
class PredictionResult:
    """Result of a prediction analysis."""
    prediction_type: str
    score: float
    confidence: float
    factors: List[str]
    recommendation: str
    details: Dict[str, Any]


@dataclass
class RiskAssessmentResult:
    """Result of at-risk student assessment."""
    user_id: int
    email: str
    name: str
    risk_level: str  # low, medium, high, critical
    risk_score: float  # 0-100
    risk_category: str
    risk_factors: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    previous_risk_level: Optional[str] = None
    risk_change: str = "stable"  # increased, decreased, stable
    course_id: Optional[str] = None
    unit_id: Optional[str] = None


class RiskLevel:
    """Risk level constants."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    
    @staticmethod
    def from_score(score: float) -> str:
        """Convert risk score (0-100) to risk level."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


class PredictiveAnalyticsService:
    """
    Service for predictive analytics.
    
    Provides predictions for:
    - User engagement levels
    - Resource popularity
    - User churn risk
    - Content trends
    """

    @staticmethod
    def _count_resource_downloads(user) -> int:
        """Count download interactions using the real downloads/event models."""
        from apps.analytics.models import AnalyticsEvent
        from apps.downloads.models import Download

        download_count = Download.objects.filter(user=user, resource__isnull=False).count()
        event_count = AnalyticsEvent.objects.filter(
            user=user,
            event_type="resource_download",
        ).count()
        return max(download_count, event_count)

    @staticmethod
    def _count_resource_views(user) -> int:
        """Count view interactions using activity and analytics records."""
        from apps.activity.models import ActivityType, RecentActivity
        from apps.analytics.models import AnalyticsEvent

        activity_views = RecentActivity.objects.filter(
            user=user,
            activity_type=ActivityType.VIEWED_RESOURCE,
            resource__isnull=False,
        ).count()
        event_views = AnalyticsEvent.objects.filter(
            user=user,
            event_type="resource_view",
        ).count()
        return max(activity_views, event_views)

    @staticmethod
    def predict_user_engagement(user_id: int) -> PredictionResult:
        """
        Predict user engagement level based on historical activity.
        
        Args:
            user_id: User ID to analyze
            
        Returns:
            PredictionResult with engagement prediction
        """
        from apps.accounts.models import User
        from apps.activity.models import RecentActivity
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return PredictionResult(
                prediction_type='engagement',
                score=0.0,
                confidence=0.0,
                factors=[],
                recommendation='User not found',
                details={}
            )
        
        # Get recent activity count (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_activity = RecentActivity.objects.filter(
            user=user,
            created_at__gte=thirty_days_ago
        ).count()
        
        # Get resource interactions
        downloads = PredictiveAnalyticsService._count_resource_downloads(user)
        views = PredictiveAnalyticsService._count_resource_views(user)
        
        # Calculate engagement score (0-100)
        activity_score = min(recent_activity / 10, 1.0) * 30
        download_score = min(downloads / 5, 1.0) * 30
        view_score = min(views / 20, 1.0) * 40
        
        total_score = activity_score + download_score + view_score
        
        # Determine engagement level
        if total_score >= 70:
            level = 'high'
            recommendation = 'User is highly engaged. Consider premium features or mentorship programs.'
        elif total_score >= 40:
            level = 'medium'
            recommendation = 'User has moderate engagement. Encourage more participation.'
        else:
            level = 'low'
            recommendation = 'User has low engagement. Send re-engagement notifications.'
        
        return PredictionResult(
            prediction_type='engagement',
            score=total_score,
            confidence=0.85,
            factors=[
                f'{recent_activity} activities in last 30 days',
                f'{downloads} resources downloaded',
                f'{views} resources viewed',
            ],
            recommendation=recommendation,
            details={
                'engagement_level': level,
                'recent_activity': recent_activity,
                'downloads': downloads,
                'views': views,
            }
        )

    @staticmethod
    def predict_resource_popularity(resource_id: str) -> PredictionResult:
        """
        Predict future popularity of a resource.
        
        Args:
            resource_id: UUID of resource to analyze
            
        Returns:
            PredictionResult with popularity prediction
        """
        from apps.resources.models import Resource
        
        try:
            resource = Resource.objects.get(id=resource_id)
        except Resource.DoesNotExist:
            return PredictionResult(
                prediction_type='popularity',
                score=0.0,
                confidence=0.0,
                factors=[],
                recommendation='Resource not found',
                details={}
            )
        
        # Calculate popularity factors
        download_rate = resource.download_count / max((timezone.now() - resource.created_at).days, 1)
        view_rate = resource.view_count / max((timezone.now() - resource.created_at).days, 1)
        rating_score = resource.average_rating * 20  # Convert to 0-100
        
        # Engagement score
        engagement = (resource.download_count * 2 + resource.view_count) / max(
            (timezone.now() - resource.created_at).days * 10, 1
        )
        
        # Calculate predicted popularity score
        popularity_score = min((download_rate * 30 + view_rate * 20 + rating_score * 30 + engagement * 20), 100)
        
        # Determine trend
        if popularity_score >= 70:
            trend = 'trending'
            recommendation = 'Resource is trending. Consider featuring on homepage.'
        elif popularity_score >= 40:
            trend = 'stable'
            recommendation = 'Resource has stable popularity. Continue monitoring.'
        else:
            trend = 'declining'
            recommendation = 'Resource popularity is declining. Consider promoting or updating.'
        
        return PredictionResult(
            prediction_type='popularity',
            score=popularity_score,
            confidence=0.75,
            factors=[
                f'Download rate: {download_rate:.1f}/day',
                f'View rate: {view_rate:.1f}/day',
                f'Rating: {resource.average_rating:.1f}/5',
                f'Engagement: {engagement:.1f}',
            ],
            recommendation=recommendation,
            details={
                'trend': trend,
                'download_rate': download_rate,
                'view_rate': view_rate,
                'days_since_upload': (timezone.now() - resource.created_at).days,
            }
        )

    @staticmethod
    def predict_churn_risk() -> List[Dict[str, Any]]:
        """
        Identify users at risk of churning.
        
        Returns:
            List of users with churn risk scores
        """
        from apps.accounts.models import User
        from apps.activity.models import RecentActivity
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sixty_days_ago = timezone.now() - timedelta(days=60)
        
        # Get all active users
        all_users = User.objects.filter(is_active=True)
        
        churn_risks = []
        
        for user in all_users:
            # Check activity in last 30 days
            recent_count = RecentActivity.objects.filter(
                user=user,
                created_at__gte=thirty_days_ago
            ).count()
            
            # Check activity in last 60-30 days
            older_count = RecentActivity.objects.filter(
                user=user,
                created_at__gte=sixty_days_ago,
                created_at__lt=thirty_days_ago
            ).count()
            
            # Calculate churn risk score
            if older_count > 0:
                activity_change = (recent_count - older_count) / older_count
            else:
                activity_change = -1 if recent_count == 0 else 0
            
            # Risk factors
            risk_score = 0
            if recent_count == 0:
                risk_score = 100
            elif activity_change < -0.5:
                risk_score = 80
            elif activity_change < -0.25:
                risk_score = 60
            elif activity_change < 0:
                risk_score = 40
            else:
                risk_score = 20
            
            if risk_score >= 40:
                churn_risks.append({
                    'user_id': user.id,
                    'email': user.email,
                    'name': f"{user.first_name} {user.last_name}".strip() or user.email,
                    'risk_score': risk_score,
                    'recent_activity': recent_count,
                    'older_activity': older_count,
                    'activity_change': activity_change,
                    'risk_level': 'high' if risk_score >= 70 else 'medium' if risk_score >= 50 else 'low',
                })
        
        # Sort by risk score descending
        churn_risks.sort(key=lambda x: x['risk_score'], reverse=True)
        
        return churn_risks[:50]  # Top 50 at-risk users

    @staticmethod
    def get_content_trends() -> Dict[str, Any]:
        """
        Analyze content trends and predictions.
        
        Returns:
            Dictionary with trend analysis
        """
        from apps.resources.models import Resource
        
        # Get resources from last 90 days
        ninety_days_ago = timezone.now() - timedelta(days=90)
        
        resources = Resource.objects.filter(created_at__gte=ninety_days_ago)
        
        # Group by date
        by_date = {}
        for resource in resources:
            date_key = resource.created_at.date().isoformat()
            if date_key not in by_date:
                by_date[date_key] = {'count': 0, 'downloads': 0}
            by_date[date_key]['count'] += 1
            by_date[date_key]['downloads'] += resource.download_count
        
        # Get top categories
        top_categories = list(
            resources.values('file_type')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        
        # Calculate growth rate
        if len(by_date) >= 30:
            first_half = sum(d['count'] for d in list(by_date.values())[:15])
            second_half = sum(d['count'] for d in list(by_date.values())[15:])
            
            if first_half > 0:
                growth_rate = ((second_half - first_half) / first_half) * 100
            else:
                growth_rate = 0
        else:
            growth_rate = 0
        
        # Trend prediction
        if growth_rate > 20:
            trend = 'growing'
            prediction = 'Content is growing rapidly. Expect increased engagement.'
        elif growth_rate > 0:
            trend = 'stable'
            prediction = 'Content growth is stable. Maintain current strategies.'
        elif growth_rate > -20:
            trend = 'declining'
            prediction = 'Content growth is declining. Consider new content campaigns.'
        else:
            trend = 'shrinking'
            prediction = 'Content is shrinking significantly. Urgent review needed.'
        
        return {
            'trend': trend,
            'growth_rate': round(growth_rate, 2),
            'prediction': prediction,
            'total_resources': resources.count(),
            'by_date': by_date,
            'top_categories': top_categories,
            'total_downloads': resources.aggregate(Sum('download_count'))['download_count__sum'] or 0,
        }

    @staticmethod
    def get_user_predictions_summary() -> Dict[str, Any]:
        """
        Get summary of all user predictions.
        
        Returns:
            Dictionary with prediction summaries
        """
        from apps.accounts.models import User
        
        # Get active users
        active_users = User.objects.filter(is_active=True).count()
        
        # Get churn risks
        churn_risks = PredictiveAnalyticsService.predict_churn_risk()
        
        high_risk = sum(1 for u in churn_risks if u['risk_level'] == 'high')
        medium_risk = sum(1 for u in churn_risks if u['risk_level'] == 'medium')
        low_risk = sum(1 for u in churn_risks if u['risk_level'] == 'low')
        
        return {
            'total_active_users': active_users,
            'users_at_risk': len(churn_risks),
            'risk_distribution': {
                'high': high_risk,
                'medium': medium_risk,
                'low': low_risk,
            },
            'risk_percentage': round((len(churn_risks) / active_users * 100) if active_users > 0 else 0, 2),
        }

    @staticmethod
    def get_resource_predictions_summary() -> Dict[str, Any]:
        """
        Get summary of resource predictions.
        
        Returns:
            Dictionary with resource prediction summaries
        """
        from apps.resources.models import Resource
        
        # Get recent resources
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_resources = Resource.objects.filter(created_at__gte=thirty_days_ago)
        
        trending = []
        stable = []
        declining = []
        
        for resource in recent_resources[:20]:
            result = PredictiveAnalyticsService.predict_resource_popularity(str(resource.id))
            if result.details.get('trend') == 'trending':
                trending.append({
                    'id': str(resource.id),
                    'title': resource.title,
                    'score': result.score,
                })
            elif result.details.get('trend') == 'stable':
                stable.append({
                    'id': str(resource.id),
                    'title': resource.title,
                    'score': result.score,
                })
            else:
                declining.append({
                    'id': str(resource.id),
                    'title': resource.title,
                    'score': result.score,
                })
        
        return {
            'total_recent_resources': recent_resources.count(),
            'trending': trending,
            'stable': stable,
            'declining': declining,
        }

    # =========================================================================
    # At-Risk Student Detection Methods
    # =========================================================================

    @staticmethod
    def assess_student_risk(user_id: int, course_id: Optional[str] = None) -> Optional[RiskAssessmentResult]:
        """
        Assess risk level for a specific student.
        
        Args:
            user_id: User ID to assess
            course_id: Optional course ID to filter by
            
        Returns:
            RiskAssessmentResult with risk assessment details
        """
        from apps.accounts.models import User
        from apps.activity.models import RecentActivity
        from apps.analytics.models import StudentRiskAssessment
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
        
        # Skip non-student users
        if user.role.lower() != 'student':
            return None
        
        # Calculate risk components
        engagement_score = PredictiveAnalyticsService._calculate_engagement_risk(user)
        grade_pattern_score = PredictiveAnalyticsService._calculate_grade_pattern_risk(user, course_id)
        attendance_score = PredictiveAnalyticsService._calculate_attendance_risk(user, course_id)
        
        # Calculate overall risk score (weighted average)
        # Weights: engagement 30%, grades 40%, attendance 30%
        overall_score = (
            engagement_score * 0.30 +
            grade_pattern_score * 0.40 +
            attendance_score * 0.30
        )
        
        risk_level = RiskLevel.from_score(overall_score)
        
        # Get previous risk assessment
        previous_assessment = StudentRiskAssessment.objects.filter(
            user=user,
            is_active=True,
            risk_category='overall'
        ).order_by('-assessment_date').first()
        
        previous_risk_level = previous_assessment.risk_level if previous_assessment else None
        
        # Determine risk change
        if previous_risk_level:
            risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
            current_order = risk_order.get(risk_level, 0)
            previous_order = risk_order.get(previous_risk_level, 0)
            
            if current_order > previous_order:
                risk_change = 'increased'
            elif current_order < previous_order:
                risk_change = 'decreased'
            else:
                risk_change = 'stable'
        else:
            risk_change = 'stable'
        
        # Generate risk factors and recommendations
        risk_factors = {
            'engagement_score': round(engagement_score, 2),
            'grade_pattern_score': round(grade_pattern_score, 2),
            'attendance_score': round(attendance_score, 2),
            'overall_score': round(overall_score, 2),
        }
        
        recommendations = PredictiveAnalyticsService._generate_intervention_recommendations(
            risk_level, risk_factors
        )
        
        # Save risk assessment
        assessment = StudentRiskAssessment.objects.create(
            user=user,
            risk_level=risk_level,
            risk_category='overall',
            risk_score=overall_score,
            risk_factors=risk_factors,
            previous_risk_level=previous_risk_level,
            risk_change=risk_change,
            course_id=course_id,
            recommendations=recommendations,
            is_active=True,
        )
        
        # Trigger notifications if risk increased or is critical
        if risk_change == 'increased' or risk_level == RiskLevel.CRITICAL:
            from apps.core.predictive_analytics import AtRiskNotificationService
            AtRiskNotificationService.notify_student_at_risk(
                user=user,
                assessment=assessment,
                risk_change=risk_change
            )
        
        return RiskAssessmentResult(
            user_id=user.id,
            email=user.email,
            name=f"{user.first_name} {user.last_name}".strip() or user.email,
            risk_level=risk_level,
            risk_score=overall_score,
            risk_category='overall',
            risk_factors=risk_factors,
            recommendations=recommendations,
            previous_risk_level=previous_risk_level,
            risk_change=risk_change,
            course_id=course_id,
        )

    @staticmethod
    def _calculate_engagement_risk(user, course_id: Optional[str] = None) -> float:
        """
        Calculate engagement-based risk score (0-100).
        Higher score = higher risk.
        """
        from apps.activity.models import RecentActivity
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sixty_days_ago = timezone.now() - timedelta(days=60)
        
        # Recent activity count
        recent_activity = RecentActivity.objects.filter(
            user=user,
            created_at__gte=thirty_days_ago
        ).count()
        
        # Activity in previous 30 days
        older_activity = RecentActivity.objects.filter(
            user=user,
            created_at__gte=sixty_days_ago,
            created_at__lt=thirty_days_ago
        ).count()
        
        # Risk factors:
        # 1. No activity in last 30 days = high risk
        # 2. Significant drop in activity = medium-high risk
        # 3. Low overall activity = low-medium risk
        
        if recent_activity == 0:
            return 100.0  # Critical - completely inactive
        
        # Activity trend
        if older_activity > 0:
            activity_change = (recent_activity - older_activity) / older_activity
        else:
            activity_change = -1 if recent_activity < 5 else 0
        
        # Calculate risk score based on activity
        base_score = 0
        
        # Very low engagement (less than 5 activities in 30 days)
        if recent_activity < 5:
            base_score = 60
        elif recent_activity < 10:
            base_score = 40
        elif recent_activity < 20:
            base_score = 20
        else:
            base_score = 10
        
        # Add risk for declining activity
        if activity_change < -0.5:
            base_score += 30
        elif activity_change < -0.25:
            base_score += 20
        elif activity_change < 0:
            base_score += 10
        
        return min(base_score, 100)

    @staticmethod
    def _calculate_grade_pattern_risk(user, course_id: Optional[str] = None) -> float:
        """
        Calculate grade pattern-based risk score (0-100).
        Higher score = higher risk.
        
        Note: This uses activity-based grade estimation since we don't have
        actual grade data. In production, this would integrate with a grades system.
        """
        from apps.activity.models import ActivityType, RecentActivity
        
        # Get resources user has downloaded/viewed
        downloaded = PredictiveAnalyticsService._count_resource_downloads(user)
        viewed = PredictiveAnalyticsService._count_resource_views(user)
        
        # Use learning-material interaction activity as a proxy for academic momentum.
        study_activity = RecentActivity.objects.filter(
            user=user,
            activity_type__in=[
                ActivityType.VIEWED_RESOURCE,
                ActivityType.DOWNLOADED_RESOURCE,
            ],
        ).count()
        
        # Risk calculation based on learning engagement
        # Low interaction with materials indicates risk
        
        if downloaded == 0 and viewed == 0:
            return 80.0  # No engagement with materials
        
        # Calculate risk based on engagement level
        total_interactions = max(downloaded + viewed, study_activity)
        
        if total_interactions < 5:
            return 60
        elif total_interactions < 15:
            return 40
        elif total_interactions < 30:
            return 20
        else:
            return 10

    @staticmethod
    def _calculate_attendance_risk(user, course_id: Optional[str] = None) -> float:
        """
        Calculate attendance-based risk score (0-100).
        Higher score = higher risk.
        
        Note: This uses event attendance from analytics events.
        In production, this would integrate with an attendance system.
        """
        from apps.analytics.models import AnalyticsEvent
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Get attendance-related events
        attended_events = AnalyticsEvent.objects.filter(
            user=user,
            event_type__in=['event_attend', 'event_attended', 'attendance'],
            timestamp__gte=thirty_days_ago
        ).count()
        
        # Get total registered events
        registered_events = AnalyticsEvent.objects.filter(
            user=user,
            event_type__in=['event_register', 'registration'],
            timestamp__gte=thirty_days_ago
        ).count()
        
        # Calculate attendance rate
        if registered_events > 0:
            attendance_rate = attended_events / registered_events
        else:
            # If no registration data, use raw attendance as signal
            if attended_events == 0:
                return 50.0  # Unknown - no attendance data
            else:
                attendance_rate = 1.0
        
        # Risk based on attendance rate
        if attendance_rate < 0.5:
            return 90.0
        elif attendance_rate < 0.7:
            return 70.0
        elif attendance_rate < 0.85:
            return 40.0
        elif attendance_rate < 0.95:
            return 20.0
        else:
            return 5.0

    @staticmethod
    def _generate_intervention_recommendations(risk_level: str, risk_factors: Dict[str, Any]) -> List[str]:
        """
        Generate intervention recommendations based on risk level and factors.
        """
        recommendations = []
        
        if risk_level == RiskLevel.CRITICAL:
            recommendations.extend([
                "Immediate intervention required - schedule meeting with student",
                "Contact advisor for personalized support plan",
                "Consider peer tutoring assignment",
                "Review for potential withdrawal options",
            ])
        elif risk_level == RiskLevel.HIGH:
            recommendations.extend([
                "Schedule one-on-one meeting with student",
                "Recommend study group participation",
                "Send personalized encouragement message",
                "Review assignment submission patterns",
            ])
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.extend([
                "Send engagement reminder notification",
                "Recommend relevant study materials",
                "Invite to upcoming study sessions",
            ])
        else:  # LOW
            recommendations.extend([
                "Continue positive engagement",
                "Encourage peer mentoring",
            ])
        
        # Add specific recommendations based on risk factors
        if risk_factors.get('engagement_score', 0) > 60:
            recommendations.append("Focus on re-engagement: send personalized content recommendations")
        
        if risk_factors.get('attendance_score', 0) > 60:
            recommendations.append("Address attendance: send reminders for upcoming sessions")
        
        if risk_factors.get('grade_pattern_score', 0) > 60:
            recommendations.append("Support academic performance: recommend tutoring or office hours")
        
        return recommendations

    @staticmethod
    def get_at_risk_students(
        risk_level: Optional[str] = None,
        course_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get list of at-risk students.
        
        Args:
            risk_level: Filter by risk level (low, medium, high, critical)
            course_id: Filter by course ID
            limit: Maximum number of results
            
        Returns:
            List of at-risk students with assessment details
        """
        from apps.analytics.models import StudentRiskAssessment
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Get latest active assessments
        assessments = StudentRiskAssessment.objects.filter(
            is_active=True,
            risk_category='overall'
        ).order_by('-assessment_date')
        
        # Filter by risk level
        if risk_level:
            assessments = assessments.filter(risk_level=risk_level)
        
        # Filter by course
        if course_id:
            assessments = assessments.filter(course_id=course_id)
        
        # Get unique users (latest assessment per user)
        user_ids = assessments.values_list('user_id', flat=True).distinct()
        
        at_risk_students = []
        
        for user_id in user_ids[:limit]:
            latest = StudentRiskAssessment.objects.filter(
                user_id=user_id,
                is_active=True,
                risk_category='overall'
            ).order_by('-assessment_date').first()
            
            if latest and latest.risk_level != RiskLevel.LOW:
                try:
                    user = User.objects.get(id=user_id)
                    at_risk_students.append({
                        'user_id': user_id,
                        'email': user.email,
                        'name': f"{user.first_name} {user.last_name}".strip() or user.email,
                        'risk_level': latest.risk_level,
                        'risk_score': latest.risk_score,
                        'risk_factors': latest.risk_factors,
                        'recommendations': latest.recommendations,
                        'assessment_date': latest.assessment_date.isoformat() if latest.assessment_date else None,
                        'previous_risk_level': latest.previous_risk_level,
                        'risk_change': latest.risk_change,
                    })
                except User.DoesNotExist:
                    continue
        
        # Sort by risk score descending
        at_risk_students.sort(key=lambda x: x['risk_score'], reverse=True)
        
        return at_risk_students

    @staticmethod
    def get_student_risk_history(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Get risk assessment history for a student.
        
        Args:
            user_id: User ID to get history for
            limit: Maximum number of historical records
            
        Returns:
            List of historical risk assessments
        """
        from apps.analytics.models import StudentRiskAssessment
        
        assessments = StudentRiskAssessment.objects.filter(
            user_id=user_id,
            risk_category='overall'
        ).order_by('-assessment_date')[:limit]
        
        return [{
            'risk_level': a.risk_level,
            'risk_score': a.risk_score,
            'risk_factors': a.risk_factors,
            'assessment_date': a.assessment_date.isoformat() if a.assessment_date else None,
            'previous_risk_level': a.previous_risk_level,
            'risk_change': a.risk_change,
            'recommendations': a.recommendations,
        } for a in assessments]

    @staticmethod
    def trigger_manual_assessment(user_id: int, course_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Manually trigger a risk assessment for a student.
        
        Args:
            user_id: User ID to assess
            course_id: Optional course ID
            
        Returns:
            Assessment result dictionary
        """
        result = PredictiveAnalyticsService.assess_student_risk(user_id, course_id)
        
        if result is None:
            return {
                'success': False,
                'message': 'User not found or not a student'
            }
        
        return {
            'success': True,
            'message': f'Risk assessment completed for {result.name}',
            'assessment': {
                'user_id': result.user_id,
                'email': result.email,
                'name': result.name,
                'risk_level': result.risk_level,
                'risk_score': result.risk_score,
                'risk_factors': result.risk_factors,
                'recommendations': result.recommendations,
                'previous_risk_level': result.previous_risk_level,
                'risk_change': result.risk_change,
            }
        }

    @staticmethod
    def get_at_risk_summary() -> Dict[str, Any]:
        """
        Get summary of at-risk students across the platform.
        
        Returns:
            Dictionary with at-risk summary statistics
        """
        from apps.analytics.models import StudentRiskAssessment
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Get students
        total_students = User.objects.filter(role__iexact='student', is_active=True).count()
        
        # Get at-risk counts by level
        critical_count = StudentRiskAssessment.objects.filter(
            is_active=True,
            risk_category='overall',
            risk_level=RiskLevel.CRITICAL
        ).values('user_id').distinct().count()
        
        high_count = StudentRiskAssessment.objects.filter(
            is_active=True,
            risk_category='overall',
            risk_level=RiskLevel.HIGH
        ).values('user_id').distinct().count()
        
        medium_count = StudentRiskAssessment.objects.filter(
            is_active=True,
            risk_category='overall',
            risk_level=RiskLevel.MEDIUM
        ).values('user_id').distinct().count()
        
        low_count = StudentRiskAssessment.objects.filter(
            is_active=True,
            risk_category='overall',
            risk_level=RiskLevel.LOW
        ).values('user_id').distinct().count()
        
        total_assessed = StudentRiskAssessment.objects.filter(
            is_active=True,
            risk_category='overall'
        ).values('user_id').distinct().count()
        
        return {
            'total_students': total_students,
            'total_assessed': total_assessed,
            'risk_distribution': {
                'critical': critical_count,
                'high': high_count,
                'medium': medium_count,
                'low': low_count,
            },
            'at_risk_count': critical_count + high_count,
            'at_risk_percentage': round(
                ((critical_count + high_count) / total_students * 100) if total_students > 0 else 0,
                2
            ),
        }


class AtRiskNotificationService:
    """
    Service for sending notifications when students become at-risk.
    """
    
    @staticmethod
    def notify_student_at_risk(user, assessment, risk_change: str):
        """
        Send notifications when a student's risk level increases.
        
        Args:
            user: The at-risk student
            assessment: The risk assessment
            risk_change: How risk changed (increased, decreased, stable)
        """
        from apps.notifications.models import NotificationType
        from apps.notifications.services import NotificationService, AdminNotificationService
        
        # Determine notification type based on risk level
        if assessment.risk_level == RiskLevel.CRITICAL:
            notification_type = NotificationType.STUDENT_RISK_CRITICAL
            priority = 'urgent'
            title = "Critical: Student At Risk"
        elif risk_change == 'increased':
            notification_type = NotificationType.STUDENT_RISK_INCREASED
            priority = 'high'
            title = "Student Risk Increased"
        else:
            notification_type = NotificationType.STUDENT_AT_RISK
            priority = 'medium'
            title = "Student At Risk"
        
        # Build message
        student_name = f"{user.first_name} {user.last_name}".strip() or user.email
        risk_level_display = assessment.get_risk_level_display()
        
        message = (
            f"{student_name} has been identified as at-risk ({risk_level_display}). "
            f"Risk score: {assessment.risk_score:.0f}/100. "
            f"Recommendation: {assessment.recommendations[0] if assessment.recommendations else 'Review student'}"
        )
        
        # Update assessment with alert sent timestamp
        from django.utils import timezone
        assessment.alert_sent = True
        assessment.alert_sent_at = timezone.now()
        assessment.save(update_fields=['alert_sent', 'alert_sent_at'])
        
        # Notify admins
        AdminNotificationService.notify_admins(
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            link=f"/admin/students/{user.id}/risk/"
        )
        
        return True

    @staticmethod
    def notify_advisor_of_at_risk_student(advisor, student, assessment):
        """
        Notify an advisor about an at-risk student in their care.
        
        Args:
            advisor: The advisor to notify
            student: The at-risk student
            assessment: The risk assessment
        """
        from apps.notifications.models import NotificationType
        from apps.notifications.services import NotificationService
        
        student_name = f"{student.first_name} {student.last_name}".strip() or student.email
        risk_level_display = assessment.get_risk_level_display()
        
        NotificationService.create_notification(
            recipient=advisor,
            title="Student At Risk - Action Required",
            message=(
                f"{student_name} has been identified as at-risk ({risk_level_display}). "
                f"Please review their case and implement interventions."
            ),
            notification_type=NotificationType.ADVISOR_STUDENT_AT_RISK,
            link=f"/advisor/students/{student.id}/risk/"
        )
        
    @staticmethod
    def notify_instructor_of_at_risk_student(instructor, student, course, assessment):
        """
        Notify an instructor about an at-risk student in their course.
        
        Args:
            instructor: The instructor to notify
            student: The at-risk student
            course: The course
            assessment: The risk assessment
        """
        from apps.notifications.models import NotificationType
        from apps.notifications.services import NotificationService
        
        student_name = f"{student.first_name} {student.last_name}".strip() or student.email
        course_name = getattr(course, 'name', 'the course')
        risk_level_display = assessment.get_risk_level_display()
        
        NotificationService.create_notification(
            recipient=instructor,
            title="Student At Risk in Your Course",
            message=(
                f"{student_name} in {course_name} is at risk ({risk_level_display}). "
                f"Please consider reaching out to provide support."
            ),
            notification_type=NotificationType.INSTRUCTOR_STUDENT_AT_RISK,
            link=f"/courses/{course.id}/students/{student.id}/"
        )
