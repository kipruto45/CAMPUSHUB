"""
Services for Learning Analytics
Business logic for tracking and analyzing learning patterns
"""

from datetime import timedelta
from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import LearningSession, LearningProgress, StudyStreak, LearningInsight, PerformanceMetrics

User = get_user_model()


class LearningAnalyticsService:
    """Service for learning analytics operations"""
    
    @staticmethod
    def start_session(user, session_type='study', subject='', resource=None):
        """Start a new learning session"""
        session = LearningSession.objects.create(
            user=user,
            session_type=session_type,
            subject=subject,
            resource=resource,
            started_at=timezone.now()
        )
        
        # Update study streak
        streak, _ = StudyStreak.objects.get_or_create(user=user)
        streak.update_streak()
        
        return session
    
    @staticmethod
    def end_session(session_id):
        """End a learning session"""
        try:
            session = LearningSession.objects.get(id=session_id)
            session.end_session()
            return session
        except LearningSession.DoesNotExist:
            return None
    
    @staticmethod
    def update_progress(user, course=None, resource=None, progress=0, time_spent=0):
        """Update learning progress for a course or resource"""
        if not course and not resource:
            return None
        
        progress_obj, created = LearningProgress.objects.get_or_create(
            user=user,
            course=course,
            resource=resource,
            defaults={'progress_percentage': progress}
        )
        
        progress_obj.progress_percentage = max(progress_obj.progress_percentage, progress)
        progress_obj.time_spent_minutes += time_spent
        
        if progress >= 100 and not progress_obj.completed_at:
            progress_obj.completed_at = timezone.now()
        
        progress_obj.save()
        return progress_obj
    
    @staticmethod
    def get_user_dashboard(user, period_days=30):
        """Get comprehensive learning dashboard data"""
        start_date = timezone.now() - timedelta(days=period_days)
        
        # Session stats
        sessions = LearningSession.objects.filter(
            user=user,
            started_at__gte=start_date
        )
        
        total_study_time = sessions.aggregate(
            total=Sum('duration_minutes')
        )['total'] or 0
        
        sessions_count = sessions.count()
        average_session = sessions.aggregate(
            avg=Avg('duration_minutes')
        )['avg'] or 0
        
        # Progress stats
        progress = LearningProgress.objects.filter(
            user=user,
            last_accessed__gte=start_date
        )
        
        resources_completed = progress.filter(
            resource__isnull=False,
            completed_at__isnull=False
        ).count()
        
        courses_completed = progress.filter(
            course__isnull=False,
            completed_at__isnull=False
        ).count()
        
        # Streak info
        streak = StudyStreak.objects.filter(user=user).first()
        
        # Recent insights
        insights = LearningInsight.objects.filter(
            user=user,
            is_read=False
        ).order_by('-created_at')[:5]
        
        return {
            'period_days': period_days,
            'study_time': {
                'total_minutes': total_study_time,
                'total_hours': round(total_study_time / 60, 1),
                'sessions_count': sessions_count,
                'average_session_minutes': round(average_session, 1),
            },
            'progress': {
                'resources_completed': resources_completed,
                'courses_completed': courses_completed,
            },
            'streak': {
                'current': streak.current_streak if streak else 0,
                'longest': streak.longest_streak if streak else 0,
                'total_days': streak.total_study_days if streak else 0,
            },
            'recent_insights': list(insights.values(
                'id', 'insight_type', 'title', 'description', 'priority', 'created_at'
            )),
        }
    
    @staticmethod
    def get_subject_breakdown(user, period_days=30):
        """Get study time breakdown by subject"""
        start_date = timezone.now() - timedelta(days=period_days)
        
        breakdown = LearningSession.objects.filter(
            user=user,
            started_at__gte=start_date,
            subject__isnull=False
        ).values('subject').annotate(
            total_time=Sum('duration_minutes'),
            sessions=Count('id'),
            avg_focus=Avg('focus_score')
        ).order_by('-total_time')
        
        return list(breakdown)
    
    @staticmethod
    def get_weekly_progress(user):
        """Get daily study progress for the past 7 days"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=6)
        
        daily_data = []
        
        for i in range(7):
            day = week_ago + timedelta(days=i)
            day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
            day_end = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.max.time()))
            
            sessions = LearningSession.objects.filter(
                user=user,
                started_at__gte=day_start,
                started_at__lte=day_end
            )
            
            total_time = sessions.aggregate(sum=Sum('duration_minutes'))['sum'] or 0
            session_count = sessions.count()
            
            daily_data.append({
                'date': day.isoformat(),
                'day_name': day.strftime('%a'),
                'study_minutes': total_time,
                'sessions': session_count,
            })
        
        return daily_data
    
    @staticmethod
    def get_performance_trends(user, period_days=90):
        """Get performance trends over time"""
        start_date = timezone.now() - timedelta(days=period_days)
        
        # Weekly aggregates
        weekly_data = []
        
        for week in range(period_days // 7):
            week_start = start_date + timedelta(days=week * 7)
            week_end = week_start + timedelta(days=7)
            
            sessions = LearningSession.objects.filter(
                user=user,
                started_at__gte=week_start,
                started_at__lt=week_end
            )
            
            total_time = sessions.aggregate(sum=Sum('duration_minutes'))['sum'] or 0
            avg_focus = sessions.aggregate(avg=Avg('focus_score'))['avg'] or 0
            
            progress = LearningProgress.objects.filter(
                user=user,
                last_accessed__gte=week_start,
                last_accessed__lt=week_end,
                completed_at__isnull=False
            ).count()
            
            weekly_data.append({
                'week_start': week_start.date().isoformat(),
                'study_time': total_time,
                'avg_focus': round(avg_focus, 1),
                'completed_items': progress,
            })
        
        return weekly_data
    
    @staticmethod
    def generate_insights(user):
        """Generate AI-powered learning insights"""
        insights_created = []
        
        # Get recent data
        week_ago = timezone.now() - timedelta(days=7)
        
        # Check study consistency
        streak = StudyStreak.objects.filter(user=user).first()
        if streak and streak.current_streak >= 7:
            insight, created = LearningInsight.objects.get_or_create(
                user=user,
                insight_type='achievement',
                title='Week-long Study Streak!',
                description=f"You've studied for {streak.current_streak} consecutive days. Keep up the great work!",
                defaults={'priority': 'high'}
            )
            if created:
                insights_created.append(insight)
        
        # Check for subjects needing attention
        subject_breakdown = LearningSession.objects.filter(
            user=user,
            started_at__gte=week_ago
        ).values('subject').annotate(
            total_time=Sum('duration_minutes')
        ).order_by('total_time')
        
        subjects = list(subject_breakdown)
        if subjects:
            least_studied = subjects[0]
            if least_studied['subject'] and least_studied['total_time'] < 30:
                insight, created = LearningInsight.objects.get_or_create(
                    user=user,
                    insight_type='recommendation',
                    title=f'Explore {least_studied["subject"]}',
                    description=f"You haven't spent much time on {least_studied['subject']} this week. Consider dedicating more time to it.",
                    defaults={
                        'subject': least_studied['subject'],
                        'priority': 'medium'
                    }
                )
                if created:
                    insights_created.append(insight)
        
        # Check quiz performance
        recent_progress = LearningProgress.objects.filter(
            user=user,
            quiz_score__isnull=False,
            updated_at__gte=week_ago
        ).order_by('-updated_at')[:5]
        
        quiz_scores = [p.quiz_score for p in recent_progress if p.quiz_score]
        if quiz_scores:
            avg_score = sum(quiz_scores) / len(quiz_scores)
            if avg_score >= 80:
                insight, created = LearningInsight.objects.get_or_create(
                    user=user,
                    insight_type='strength',
                    title='Excellent Quiz Performance!',
                    description=f"Your average quiz score is {avg_score:.0f}%. You're doing great!",
                    defaults={'priority': 'low'}
                )
                if created:
                    insights_created.append(insight)
            elif avg_score < 60:
                insight, created = LearningInsight.objects.get_or_create(
                    user=user,
                    insight_type='suggestion',
                    title='Quiz Score Improvement',
                    description=f"Your average quiz score is {avg_score:.0f}%. Consider reviewing the material again.",
                    defaults={'priority': 'medium'}
                )
                if created:
                    insights_created.append(insight)
        
        return insights_created
    
    @staticmethod
    def aggregate_metrics(user, period_start, period_end):
        """Aggregate performance metrics for a time period"""
        start_datetime = timezone.make_aware(timezone.datetime.combine(period_start, timezone.datetime.min.time()))
        end_datetime = timezone.make_aware(timezone.datetime.combine(period_end, timezone.datetime.max.time()))
        
        # Session metrics
        sessions = LearningSession.objects.filter(
            user=user,
            started_at__gte=start_datetime,
            started_at__lte=end_datetime
        )
        
        total_time = sessions.aggregate(sum=Sum('duration_minutes'))['sum'] or 0
        sessions_count = sessions.count()
        avg_duration = sessions.aggregate(avg=Avg('duration_minutes'))['avg'] or 0
        
        # Progress metrics
        progress = LearningProgress.objects.filter(
            user=user,
            last_accessed__gte=start_datetime,
            last_accessed__lte=end_datetime
        )
        
        resources_completed = progress.filter(
            resource__isnull=False,
            completed_at__isnull=False
        ).count()
        
        courses_completed = progress.filter(
            course__isnull=False,
            completed_at__isnull=False
        ).count()
        
        # Quiz scores
        quiz_scores = progress.filter(quiz_score__isnull=False).values_list('quiz_score', flat=True)
        avg_quiz = sum(quiz_scores) / len(quiz_scores) if quiz_scores else None
        
        # Create or update metrics
        metrics, _ = PerformanceMetrics.objects.update_or_create(
            user=user,
            period_start=period_start,
            period_end=period_end,
            defaults={
                'total_study_time_minutes': total_time,
                'sessions_count': sessions_count,
                'average_session_duration': avg_duration,
                'resources_completed': resources_completed,
                'courses_completed': courses_completed,
                'average_quiz_score': avg_quiz,
            }
        )
        
        return metrics
