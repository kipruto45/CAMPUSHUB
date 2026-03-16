"""Unit tests for resources permission classes."""

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.resources import permissions as resource_permissions


def _request(factory, method="get", user=None):
    request = getattr(factory, method)("/resources/permissions/")
    request.user = user if user is not None else AnonymousUser()
    return request


def test_resource_owner_or_read_only_permission(
    user,
    admin_user,
    moderator_user,
):
    permission = resource_permissions.IsResourceOwnerOrReadOnly()
    factory = APIRequestFactory()
    approved = SimpleNamespace(status="approved", uploaded_by=admin_user)
    pending_owned = SimpleNamespace(status="pending", uploaded_by=user)
    pending_other = SimpleNamespace(status="pending", uploaded_by=admin_user)

    assert permission.has_object_permission(
        _request(factory, method="get"),
        None,
        approved,
    )
    assert not permission.has_object_permission(
        _request(factory, method="get"),
        None,
        pending_other,
    )

    assert permission.has_object_permission(
        _request(factory, method="patch", user=admin_user),
        None,
        pending_owned,
    )
    assert permission.has_object_permission(
        _request(factory, method="delete", user=moderator_user),
        None,
        pending_owned,
    )

    assert permission.has_object_permission(
        _request(factory, method="get", user=user),
        None,
        pending_owned,
    )
    assert not permission.has_object_permission(
        _request(factory, method="get", user=user),
        None,
        pending_other,
    )
    assert permission.has_object_permission(
        _request(factory, method="patch", user=user),
        None,
        pending_owned,
    )
    assert not permission.has_object_permission(
        _request(factory, method="patch", user=user),
        None,
        approved,
    )


def test_can_upload_resource_permission(user):
    permission = resource_permissions.CanUploadResource()
    factory = APIRequestFactory()

    assert permission.has_permission(_request(factory, user=user), None)
    assert not permission.has_permission(_request(factory), None)


def test_can_approve_resource_permission(user, admin_user, moderator_user):
    permission = resource_permissions.CanApproveResource()
    factory = APIRequestFactory()

    assert permission.has_permission(_request(factory, user=admin_user), None)
    assert permission.has_permission(
        _request(factory, user=moderator_user),
        None,
    )
    assert not permission.has_permission(_request(factory, user=user), None)
    assert not permission.has_permission(_request(factory), None)


def test_can_view_pending_resource_permission(
    user,
    admin_user,
    moderator_user,
):
    permission = resource_permissions.CanViewPendingResource()
    factory = APIRequestFactory()
    approved = SimpleNamespace(status="approved", uploaded_by=admin_user)
    pending_owned = SimpleNamespace(status="pending", uploaded_by=user)
    pending_other = SimpleNamespace(status="pending", uploaded_by=admin_user)

    assert permission.has_object_permission(
        _request(factory, method="get"),
        None,
        approved,
    )
    assert permission.has_object_permission(
        _request(factory, method="get", user=user),
        None,
        pending_owned,
    )
    assert permission.has_object_permission(
        _request(factory, method="get", user=admin_user),
        None,
        pending_other,
    )
    assert permission.has_object_permission(
        _request(factory, method="get", user=moderator_user),
        None,
        pending_other,
    )
    assert not permission.has_object_permission(
        _request(factory, method="get"),
        None,
        pending_other,
    )
