"""
URL routing for Live Study Rooms
"""

from django.urls import path
from . import views

app_name = 'live_rooms'

urlpatterns = [
    # Room management
    path('', views.RoomListCreateView.as_view(), name='room-list-create'),
    path('<uuid:pk>/', views.RoomDetailView.as_view(), name='room-detail'),
    path('<uuid:pk>/join/', views.JoinRoomView.as_view(), name='room-join'),
    path('<uuid:pk>/leave/', views.LeaveRoomView.as_view(), name='room-leave'),
    path('<uuid:pk>/participants/', views.RoomParticipantsView.as_view(), name='room-participants'),
    path('<uuid:pk>/messages/', views.RoomMessagesView.as_view(), name='room-messages'),
    path('<uuid:pk>/recording/start/', views.StartRecordingView.as_view(), name='room-start-recording'),
    path('<uuid:pk>/recording/stop/', views.StopRecordingView.as_view(), name='room-stop-recording'),
    # Active rooms
    path('active/', views.ActiveRoomsView.as_view(), name='active-rooms'),
    # User's rooms
    path('my/', views.MyRoomsView.as_view(), name='my-rooms'),
]
