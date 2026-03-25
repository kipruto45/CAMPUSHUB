"""
URL routing for Learning Analytics
"""

from django.urls import path
from . import views

app_name = 'learning_analytics'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('subjects/', views.SubjectBreakdownView.as_view(), name='subject-breakdown'),
    path('weekly/', views.WeeklyProgressView.as_view(), name='weekly-progress'),
    path('trends/', views.PerformanceTrendsView.as_view(), name='performance-trends'),
    
    # Sessions
    path('session/start/', views.StartSessionView.as_view(), name='start-session'),
    path('session/<uuid:pk>/end/', views.EndSessionView.as_view(), name='end-session'),
    path('interaction/', views.record_interaction, name='record-interaction'),
    
    # Progress
    path('progress/update/', views.UpdateProgressView.as_view(), name='update-progress'),
    
    # Streak
    path('streak/', views.get_streak, name='get-streak'),
    
    # Insights
    path('insights/', views.InsightsListView.as_view(), name='insights-list'),
    path('insights/<uuid:pk>/read/', views.MarkInsightReadView.as_view(), name='mark-insight-read'),
    path('insights/generate/', views.GenerateInsightsView.as_view(), name='generate-insights'),
    
    # Metrics
    path('metrics/', views.MetricsListView.as_view(), name='metrics-list'),
]
