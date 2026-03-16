"""
URL configuration for gamification app.
"""

from django.urls import path
from apps.gamification import views

app_name = "gamification"

urlpatterns = [
    path('stats/', views.user_gamification_stats, name='gamification-stats'),
    path('leaderboard/', views.leaderboard, name='gamification-leaderboard'),
    path('check-badges/', views.check_badges, name='gamification-check-badges'),
]
