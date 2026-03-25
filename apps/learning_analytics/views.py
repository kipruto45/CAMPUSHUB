"""
Views for Learning Analytics API
"""

from datetime import timedelta
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import LearningSession, LearningProgress, StudyStreak, LearningInsight, PerformanceMetrics
from .services import LearningAnalyticsService
from .serializers import (
    LearningSessionSerializer,
    LearningProgressSerializer,
    StudyStreakSerializer,
    LearningInsightSerializer,
    PerformanceMetricsSerializer,
)


class DashboardView(generics.RetrieveAPIView):
    """Get user's learning dashboard"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = int(request.query_params.get('period', 30))
        data = LearningAnalyticsService.get_user_dashboard(request.user, period)
        return Response(data)


class SubjectBreakdownView(generics.ListAPIView):
    """Get study time breakdown by subject"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = int(request.query_params.get('period', 30))
        data = LearningAnalyticsService.get_subject_breakdown(request.user, period)
        return Response(data)


class WeeklyProgressView(generics.ListAPIView):
    """Get weekly study progress"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = LearningAnalyticsService.get_weekly_progress(request.user)
        return Response(data)


class PerformanceTrendsView(generics.ListAPIView):
    """Get performance trends over time"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = int(request.query_params.get('period', 90))
        data = LearningAnalyticsService.get_performance_trends(request.user, period)
        return Response(data)


class StartSessionView(generics.CreateAPIView):
    """Start a new learning session"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_type = request.data.get('session_type', 'study')
        subject = request.data.get('subject', '')
        resource_id = request.data.get('resource_id')
        
        resource = None
        if resource_id:
            from apps.resources.models import Resource
            resource = Resource.objects.filter(id=resource_id).first()
        
        session = LearningAnalyticsService.start_session(
            user=request.user,
            session_type=session_type,
            subject=subject,
            resource=resource
        )
        
        return Response(
            LearningSessionSerializer(session).data,
            status=status.HTTP_201_CREATED
        )


class EndSessionView(generics.UpdateAPIView):
    """End a learning session"""
    permission_classes = [IsAuthenticated]
    queryset = LearningSession.objects.all()
    serializer_class = LearningSessionSerializer

    def post(self, request, pk):
        session = LearningAnalyticsService.end_session(pk)
        if session:
            return Response(LearningSessionSerializer(session).data)
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND
        )


class UpdateProgressView(generics.UpdateAPIView):
    """Update learning progress"""
    permission_classes = [IsAuthenticated]
    queryset = LearningProgress.objects.all()
    serializer_class = LearningProgressSerializer

    def post(self, request):
        course_id = request.data.get('course_id')
        resource_id = request.data.get('resource_id')
        progress = float(request.data.get('progress', 0))
        time_spent = int(request.data.get('time_spent', 0))
        
        course = None
        resource = None
        
        if course_id:
            from apps.courses.models import Course
            course = Course.objects.filter(id=course_id).first()
        
        if resource_id:
            from apps.resources.models import Resource
            resource = Resource.objects.filter(id=resource_id).first()
        
        progress_obj = LearningAnalyticsService.update_progress(
            user=request.user,
            course=course,
            resource=resource,
            progress=progress,
            time_spent=time_spent
        )
        
        if progress_obj:
            return Response(LearningProgressSerializer(progress_obj).data)
        return Response(
            {'error': 'Invalid request'},
            status=status.HTTP_400_BAD_REQUEST
        )


class InsightsListView(generics.ListAPIView):
    """List learning insights"""
    permission_classes = [IsAuthenticated]
    serializer_class = LearningInsightSerializer

    def get_queryset(self):
        queryset = LearningInsight.objects.filter(user=self.request.user)
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        # Filter by type
        insight_type = self.request.query_params.get('type')
        if insight_type:
            queryset = queryset.filter(insight_type=insight_type)
        
        return queryset[:20]


class MarkInsightReadView(generics.UpdateAPIView):
    """Mark an insight as read"""
    permission_classes = [IsAuthenticated]
    queryset = LearningInsight.objects.all()
    serializer_class = LearningInsightSerializer

    def post(self, request, pk):
        try:
            insight = LearningInsight.objects.get(pk=pk, user=request.user)
            insight.is_read = True
            insight.save()
            return Response(LearningInsightSerializer(insight).data)
        except LearningInsight.DoesNotExist:
            return Response(
                {'error': 'Insight not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class GenerateInsightsView(generics.CreateAPIView):
    """Generate new learning insights"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        insights = LearningAnalyticsService.generate_insights(request.user)
        return Response(
            LearningInsightSerializer(insights, many=True).data,
            status=status.HTTP_201_CREATED
        )


class MetricsListView(generics.ListAPIView):
    """List performance metrics"""
    permission_classes = [IsAuthenticated]
    serializer_class = PerformanceMetricsSerializer

    def get_queryset(self):
        return PerformanceMetrics.objects.filter(
            user=self.request.user
        ).order_by('-period_start')[:12]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_interaction(request):
    """Record a learning interaction (page view, etc.)"""
    session_id = request.data.get('session_id')
    interaction_type = request.data.get('type', 'view')
    
    if not session_id:
        return Response(
            {'error': 'session_id required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        session = LearningSession.objects.get(id=session_id, user=request.user)
        session.interactions += 1
        
        if interaction_type == 'page':
            session.pages_viewed += 1
        
        session.save()
        
        return Response({'success': True, 'interactions': session.interactions})
    except LearningSession.DoesNotExist:
        return Response(
            {'error': 'Session not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_streak(request):
    """Get user's study streak"""
    streak, created = StudyStreak.objects.get_or_create(user=request.user)
    return Response(StudyStreakSerializer(streak).data)
