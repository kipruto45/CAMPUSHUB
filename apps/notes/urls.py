"""
Notes URL configuration for CampusHub
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import NoteViewSet, NoteListView, NoteDetailView

app_name = 'notes'

router = DefaultRouter()
router.register(r'', NoteViewSet, basename='note')

urlpatterns = [
    path('', include(router.urls)),
]