"""Tests for shared core permission classes."""

from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.core import permissions as core_permissions


@pytest.fixture
def request_factory():
    return APIRequestFactory()


def _make_request(factory, method="get", user=None):
    request = getattr(factory, method)("/permissions/")
    request.user = user if user is not None else AnonymousUser()
    return request


def test_is_admin_permission(request_factory, admin_user, user):
    permission = core_permissions.IsAdmin()

    assert permission.has_permission(
        _make_request(request_factory, user=admin_user),
        None,
    )
    assert not permission.has_permission(
        _make_request(request_factory, user=user),
        None,
    )
    assert not permission.has_permission(_make_request(request_factory), None)


def test_is_moderator_permission(request_factory, moderator_user, admin_user):
    permission = core_permissions.IsModerator()

    assert permission.has_permission(
        _make_request(request_factory, user=moderator_user), None
    )
    assert not permission.has_permission(
        _make_request(request_factory, user=admin_user),
        None,
    )


def test_is_admin_or_moderator_permission(
    request_factory,
    moderator_user,
    admin_user,
    user,
):
    permission = core_permissions.IsAdminOrModerator()

    assert permission.has_permission(
        _make_request(request_factory, user=admin_user),
        None,
    )
    assert permission.has_permission(
        _make_request(request_factory, user=moderator_user), None
    )
    assert not permission.has_permission(
        _make_request(request_factory, user=user),
        None,
    )


def test_is_owner_uses_supported_owner_fields(
    request_factory,
    user,
    admin_user,
):
    permission = core_permissions.IsOwner()

    assert permission.has_object_permission(
        _make_request(request_factory, user=user),
        None,
        SimpleNamespace(user=user),
    )
    assert permission.has_object_permission(
        _make_request(request_factory, user=user),
        None,
        SimpleNamespace(uploaded_by=user),
    )
    assert permission.has_object_permission(
        _make_request(request_factory, user=user),
        None,
        SimpleNamespace(author=user),
    )
    assert not permission.has_object_permission(
        _make_request(request_factory, user=user),
        None,
        SimpleNamespace(uploaded_by=admin_user),
    )
    assert not permission.has_object_permission(
        _make_request(request_factory, user=user),
        None,
        SimpleNamespace(name="unknown"),
    )


def test_is_owner_or_read_only(request_factory, user, admin_user):
    permission = core_permissions.IsOwnerOrReadOnly()

    assert permission.has_object_permission(
        _make_request(request_factory, method="get", user=admin_user),
        None,
        SimpleNamespace(uploaded_by=user),
    )
    assert permission.has_object_permission(
        _make_request(request_factory, method="post", user=user),
        None,
        SimpleNamespace(uploaded_by=user),
    )
    assert not permission.has_object_permission(
        _make_request(request_factory, method="patch", user=admin_user),
        None,
        SimpleNamespace(uploaded_by=user),
    )


def test_verified_and_active_permissions(request_factory, user):
    verified_permission = core_permissions.IsVerifiedUser()
    active_permission = core_permissions.IsActiveUser()

    user.is_verified = True
    assert verified_permission.has_permission(
        _make_request(request_factory, user=user),
        None,
    )
    assert active_permission.has_permission(
        _make_request(request_factory, user=user),
        None,
    )

    user.is_verified = False
    user.is_active = False
    assert not verified_permission.has_permission(
        _make_request(request_factory, user=user), None
    )
    assert not active_permission.has_permission(
        _make_request(request_factory, user=user),
        None,
    )


def test_can_approve_and_moderate_permissions(
    request_factory,
    admin_user,
    moderator_user,
    user,
):
    approve_permission = core_permissions.CanApproveResource()
    moderate_permission = core_permissions.CanModerateContent()

    assert approve_permission.has_permission(
        _make_request(request_factory, user=admin_user),
        None,
    )
    assert approve_permission.has_permission(
        _make_request(request_factory, user=moderator_user), None
    )
    assert not approve_permission.has_permission(
        _make_request(request_factory, user=user),
        None,
    )

    assert moderate_permission.has_permission(
        _make_request(request_factory, user=admin_user), None
    )
    assert moderate_permission.has_permission(
        _make_request(request_factory, user=moderator_user), None
    )
    assert not moderate_permission.has_permission(
        _make_request(request_factory, user=user), None
    )


def test_can_upload_resource_permission(
    request_factory,
    user,
    moderator_user,
    admin_user,
):
    permission = core_permissions.CanUploadResource()

    assert permission.has_permission(
        _make_request(request_factory, user=user),
        None,
    )
    assert permission.has_permission(
        _make_request(request_factory, user=moderator_user), None
    )
    assert permission.has_permission(
        _make_request(request_factory, user=admin_user),
        None,
    )
    assert not permission.has_permission(_make_request(request_factory), None)


def test_public_resource_permission_always_true(request_factory):
    permission = core_permissions.IsPublicResource()
    assert permission.has_permission(_make_request(request_factory), None)


def test_approved_resource_permission_for_safe_requests(
    request_factory, user, admin_user, moderator_user
):
    permission = core_permissions.IsApprovedResource()
    approved = SimpleNamespace(status="approved", uploaded_by=user)
    pending = SimpleNamespace(status="pending", uploaded_by=user)
    other_pending = SimpleNamespace(status="pending", uploaded_by=admin_user)

    assert permission.has_object_permission(
        _make_request(request_factory, method="get"), None, approved
    )
    assert permission.has_object_permission(
        _make_request(request_factory, method="get", user=user), None, pending
    )
    assert permission.has_object_permission(
        _make_request(request_factory, method="get", user=admin_user),
        None,
        other_pending,
    )
    assert permission.has_object_permission(
        _make_request(request_factory, method="get", user=moderator_user),
        None,
        other_pending,
    )
    assert not permission.has_object_permission(
        _make_request(request_factory, method="get"), None, pending
    )


def test_approved_resource_permission_allows_non_safe_by_design(
    request_factory,
    user,
):
    permission = core_permissions.IsApprovedResource()
    pending = SimpleNamespace(status="pending", uploaded_by=user)

    assert permission.has_object_permission(
        _make_request(request_factory, method="post"), None, pending
    )
