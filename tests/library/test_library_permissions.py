"""Unit tests for library permission classes."""

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.library import permissions as library_permissions


def _request(factory, method="get", user=None):
    request = getattr(factory, method)("/library/permissions/")
    request.user = user if user is not None else AnonymousUser()
    return request


def test_owner_or_read_only_permission(user, admin_user):
    factory = APIRequestFactory()
    permission = library_permissions.IsOwnerOrReadOnly()
    obj = SimpleNamespace(user=user)

    assert permission.has_object_permission(
        _request(factory, method="get", user=admin_user), None, obj
    )
    assert permission.has_object_permission(
        _request(factory, method="patch", user=user), None, obj
    )
    assert not permission.has_object_permission(
        _request(factory, method="patch", user=admin_user), None, obj
    )


def test_can_access_library_permission(user):
    factory = APIRequestFactory()
    permission = library_permissions.CanAccessLibrary()

    assert permission.has_permission(_request(factory, user=user), None)
    assert not permission.has_permission(_request(factory), None)


def test_can_manage_storage_permission(user):
    factory = APIRequestFactory()
    permission = library_permissions.CanManageStorage()

    assert permission.has_permission(_request(factory, user=user), None)
    assert not permission.has_permission(_request(factory), None)
