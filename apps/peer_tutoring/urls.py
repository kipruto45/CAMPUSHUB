"""
URL routing for Peer Tutoring
"""

from django.urls import path
from . import views

app_name = 'peer_tutoring'

urlpatterns = [
    # Tutors
    path('tutors/', views.TutorListView.as_view(), name='tutor-list'),
    path('profile/', views.MyProfileView.as_view(), name='my-profile'),
    
    # Sessions
    path('sessions/', views.SessionListCreateView.as_view(), name='session-list'),
    path('sessions/<uuid:pk>/', views.SessionDetailView.as_view(), name='session-detail'),
    path('sessions/<uuid:pk>/confirm/', views.confirm_session, name='session-confirm'),
    path('sessions/<uuid:pk>/start/', views.start_session, name='session-start'),
    path('sessions/<uuid:pk>/complete/', views.complete_session, name='session-complete'),
    path('sessions/<uuid:pk>/review/', views.submit_review, name='session-review'),
    
    # Requests
    path('requests/', views.RequestListCreateView.as_view(), name='request-list'),
    
    # Subjects
    path('subjects/', views.SubjectListView.as_view(), name='subject-list'),
]
