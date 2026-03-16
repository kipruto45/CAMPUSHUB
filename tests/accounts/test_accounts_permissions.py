"""Unit tests for account permission classes."""

from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.accounts import permissions as account_permissions


def _request(factory, method="get", user=None):
    request = getattr(factory, method)("/accounts/permissions/")
    request.user = user if user is not None else AnonymousUser()
    return request


def test_is_student_permission(user, admin_user):
    factory = APIRequestFactory()
    permission = account_permissions.IsStudent()

    assert permission.has_permission(_request(factory, user=user), None)
    assert not permission.has_permission(
        _request(factory, user=admin_user),
        None,
    )
    assert not permission.has_permission(_request(factory), None)


def test_is_admin_user_permission(user, admin_user):
    factory = APIRequestFactory()
    permission = account_permissions.IsAdminUser()

    assert permission.has_permission(_request(factory, user=admin_user), None)
    assert not permission.has_permission(_request(factory, user=user), None)


def test_is_moderator_user_permission(moderator_user, admin_user, user):
    factory = APIRequestFactory()
    permission = account_permissions.IsModeratorUser()

    assert permission.has_permission(
        _request(factory, user=moderator_user),
        None,
    )
    assert permission.has_permission(_request(factory, user=admin_user), None)
    assert not permission.has_permission(_request(factory, user=user), None)


def test_owner_or_read_only_permission(user, admin_user):
    factory = APIRequestFactory()
    permission = account_permissions.IsOwnerOrReadOnly()

    assert permission.has_object_permission(
        _request(factory, method="get", user=admin_user), None, user
    )
    assert permission.has_object_permission(
        _request(factory, method="patch", user=user), None, user
    )
    assert permission.has_object_permission(
        _request(factory, method="put", user=admin_user), None, user
    )
    assert not permission.has_object_permission(
        _request(factory, method="delete"), None, user
    )


def test_can_manage_user_permission(user, moderator_user, admin_user):
    factory = APIRequestFactory()
    permission = account_permissions.CanManageUser()

    assert permission.has_permission(_request(factory, user=admin_user), None)
    assert permission.has_permission(
        _request(factory, user=moderator_user),
        None,
    )
    assert not permission.has_permission(_request(factory, user=user), None)
    assert not permission.has_permission(_request(factory), None)
