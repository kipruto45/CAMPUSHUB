"""
URL configuration for Recommendation Module.
"""

from django.urls import path

from apps.recommendations import views

app_name = "recommendations"

urlpatterns = [
    # Personalized recommendations
    path("for-you/", views.ForYouRecommendationsView.as_view(), name="for-you"),
    # Popular recommendations (by views, downloads, favorites)
    path("popular/", views.PopularRecommendationsView.as_view(), name="popular"),
    # Trending resources
    path("trending/", views.TrendingRecommendationsView.as_view(), name="trending"),
    # Related resources
    path(
        "related/<uuid:resource_id>/",
        views.RelatedResourcesView.as_view(),
        name="related",
    ),
    # Course-based recommendations
    path(
        "course-based/",
        views.CourseBasedRecommendationsView.as_view(),
        name="course-based",
    ),
    # Saved-based recommendations
    path(
        "saved-based/",
        views.SavedBasedRecommendationsView.as_view(),
        name="saved-based",
    ),
    # Download-based recommendations
    path(
        "download-based/",
        views.DownloadBasedRecommendationsView.as_view(),
        name="download-based",
    ),
    # Content-based recommendations
    path(
        "content-based/",
        views.ContentBasedRecommendationsView.as_view(),
        name="content-based",
    ),
    # Collaborative filtering
    path(
        "collaborative/",
        views.CollaborativeFilteringView.as_view(),
        name="collaborative",
    ),
    # Hybrid recommendations (all signals combined)
    path("hybrid/", views.HybridRecommendationsView.as_view(), name="hybrid"),
    # Seasonal/Time-based recommendations
    path("seasonal/", views.SeasonalRecommendationsView.as_view(), name="seasonal"),
    # Dashboard recommendations (all types)
    path("dashboard/", views.dashboard_recommendations, name="dashboard"),
    # AI-powered study recommendations
    path("ai-study-plan/", views.AIStudyPlanView.as_view(), name="ai-study-plan"),
    path("difficulty-analysis/", views.DifficultyAnalysisView.as_view(), name="difficulty-analysis"),
    path("learning-path/", views.LearningPathView.as_view(), name="learning-path"),
]
