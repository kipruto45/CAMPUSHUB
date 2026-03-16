"""
Predictive Analytics Service
Provides predictive analytics for user behavior, resource popularity, and churn analysis
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.db.models import Count, Avg, Sum, Q
from django.db.models.functions import ExtractMonth, ExtractYear
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
        from apps.resources.models import Resource
        
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
        downloads = Resource.objects.filter(downloads__user=user).count()
        views = Resource.objects.filter(views__user=user).count()
        
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
        
        # Get users with recent activity
        users_with_activity = User.objects.filter(
            recentactivity__created_at__gte=thirty_days_ago
        ).distinct()
        
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
        from django.db.models.functions import TruncDate
        
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
