"""
AI URL Configuration
"""

from django.urls import path

from apps.ai.views import (
    AISearchView,
    AIRecommendationsView,
    LearningPathView,
    AIChatbotView,
    AISummarizationView,
    public_chatbot,
    StudyGoalGenerateView,
    StudyGoalListView,
    StudyGoalDetailView,
    StudyGoalCompleteView,
    StudyGoalProgressView,
)

app_name = 'ai'

urlpatterns = [
    # Search
    path('search/', AISearchView.as_view(), name='search'),
    
    # Recommendations
    path('recommendations/', AIRecommendationsView.as_view(), name='recommendations'),
    path('learning-path/', LearningPathView.as_view(), name='learning-path'),
    
    # Chatbot
    path('chat/', AIChatbotView.as_view(), name='chat'),
    path('chat/public/', public_chatbot, name='public-chat'),
    
    # Summarization
    path('summarize/', AISummarizationView.as_view(), name='summarize'),
    
    # Study Goals
    path('study-goals/generate/', StudyGoalGenerateView.as_view(), name='study-goals-generate'),
    path('study-goals/', StudyGoalListView.as_view(), name='study-goals-list'),
    path('study-goals/<uuid:goal_id>/', StudyGoalDetailView.as_view(), name='study-goals-detail'),
    path('study-goals/<uuid:goal_id>/complete/', StudyGoalCompleteView.as_view(), name='study-goals-complete'),
    path('study-goals/<uuid:goal_id>/progress/', StudyGoalProgressView.as_view(), name='study-goals-progress'),
]
