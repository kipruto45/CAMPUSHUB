"""
URL configuration for social features.
"""

from django.urls import path

from .views import (
    MyStudyGroupsView,
    StudyGroupDetailView,
    StudyGroupUpdateView,
    StudyGroupDeleteView,
    StudyGroupInviteLinkJoinView,
    StudyGroupInviteLandingView,
    StudyGroupInviteLinkRevokeView,
    StudyGroupInviteLinkValidateView,
    StudyGroupInviteLinksView,
    StudyGroupJoinView,
    StudyGroupLeaveView,
    StudyGroupListCreateView,
    StudyGroupMembersView,
    StudyGroupPostsView,
    StudyGroupPostLikeView,
    StudyGroupPostCommentsView,
    StudyGroupResourcesView,
)
from .api import DirectMessageListView, DirectMessageSendView

app_name = "social"

urlpatterns = [
    path("study-groups/", StudyGroupListCreateView.as_view(), name="study-group-list"),
    path("study-groups/my-groups/", MyStudyGroupsView.as_view(), name="my-study-groups"),
    path("study-groups/<uuid:group_id>/", StudyGroupDetailView.as_view(), name="study-group-detail"),
    path("study-groups/<uuid:group_id>/update/", StudyGroupUpdateView.as_view(), name="study-group-update"),
    path("study-groups/<uuid:group_id>/delete/", StudyGroupDeleteView.as_view(), name="study-group-delete"),
    path("study-groups/<uuid:group_id>/join/", StudyGroupJoinView.as_view(), name="study-group-join"),
    path("study-groups/<uuid:group_id>/leave/", StudyGroupLeaveView.as_view(), name="study-group-leave"),
    path("study-groups/<uuid:group_id>/members/", StudyGroupMembersView.as_view(), name="study-group-members"),
    path("study-groups/<uuid:group_id>/posts/", StudyGroupPostsView.as_view(), name="study-group-posts"),
    path("study-groups/<uuid:group_id>/posts/<uuid:post_id>/like/", StudyGroupPostLikeView.as_view(), name="post-like"),
    path("study-groups/<uuid:group_id>/posts/<uuid:post_id>/comments/", StudyGroupPostCommentsView.as_view(), name="post-comments"),
    path("study-groups/<uuid:group_id>/resources/", StudyGroupResourcesView.as_view(), name="study-group-resources"),
    
    # Invite links
    path("study-groups/<uuid:group_id>/invite-links/", StudyGroupInviteLinksView.as_view(), name="invite-links"),
    path("study-groups/invite-links/<str:token>/revoke/", StudyGroupInviteLinkRevokeView.as_view(), name="invite-link-revoke"),
    path("study-groups/invite-links/<str:token>/validate/", StudyGroupInviteLinkValidateView.as_view(), name="invite-link-validate"),
    path("study-groups/invite-links/<str:token>/join/", StudyGroupInviteLinkJoinView.as_view(), name="invite-link-join"),
    path("invite/<str:token>/", StudyGroupInviteLandingView.as_view(), name="invite-landing"),

    # Direct messaging (REST fallback in addition to WebSocket)
    path("direct-messages/<int:user_id>/", DirectMessageListView.as_view(), name="direct-message-list"),
    path("direct-messages/<int:user_id>/send/", DirectMessageSendView.as_view(), name="direct-message-send"),
]
