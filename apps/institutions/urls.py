"""
URL routing for Institutions
"""

from django.urls import path
from . import views

app_name = 'institutions'

urlpatterns = [
    # Institutions
    path('', views.InstitutionListView.as_view(), name='institution-list'),
    path('<uuid:pk>/', views.InstitutionDetailView.as_view(), name='institution-detail'),
    path('my/', views.MyInstitutionView.as_view(), name='my-institution'),
    path('<uuid:institution_id>/stats/', views.InstitutionStatsView.as_view(), name='institution-stats'),
    
    # Admins
    path('<uuid:institution_id>/admins/', views.InstitutionAdminsView.as_view(), name='institution-admins'),
    
    # Departments
    path('<uuid:institution_id>/departments/', views.DepartmentListView.as_view(), name='department-list'),
    
    # Invitations
    path('<uuid:institution_id>/invitations/', views.InvitationListView.as_view(), name='invitation-list'),
    
    # Public endpoints
    path('detect/', views.detect_institution, name='detect-institution'),
    path('invitation/accept/', views.accept_invitation, name='accept-invitation'),
]
