"""Tests for admin management permission classes."""

from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.admin_management import permissions as admin_permissions


def _request(factory, method="get", user=None):
    request = getattr(factory, method)("/admin-management/permissions/")
    request.user = user if user is not None else AnonymousUser()
    return request


def test_is_admin_permission(admin_user, moderator_user):
    factory = APIRequestFactory()
    permission = admin_permissions.IsAdmin()

    assert permission.has_permission(_request(factory, user=admin_user), None)
    assert not permission.has_permission(
        _request(factory, user=moderator_user),
        None,
    )
    assert not permission.has_permission(_request(factory), None)


def test_is_super_admin_permission(admin_user, moderator_user):
    factory = APIRequestFactory()
    permission = admin_permissions.IsSuperAdmin()

    assert permission.has_permission(_request(factory, user=admin_user), None)
    assert not permission.has_permission(
        _request(factory, user=moderator_user),
        None,
    )
    assert not permission.has_permission(_request(factory), None)


def test_is_admin_or_read_only_permission(admin_user, moderator_user, user):
    factory = APIRequestFactory()
    permission = admin_permissions.IsAdminOrReadOnly()

    assert permission.has_permission(
        _request(factory, method="get", user=admin_user),
        None,
    )
    assert permission.has_permission(
        _request(factory, method="get", user=moderator_user), None
    )
    assert not permission.has_permission(
        _request(factory, method="get", user=user),
        None,
    )

    assert permission.has_permission(
        _request(factory, method="post", user=admin_user),
        None,
    )
    assert not permission.has_permission(
        _request(factory, method="post", user=moderator_user), None
    )
    assert not permission.has_permission(
        _request(factory, method="delete"),
        None,
    )
