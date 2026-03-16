"""Unit tests for downloads permission classes."""

from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from apps.downloads import permissions as download_permissions


def _request(factory, method="get", user=None):
    request = getattr(factory, method)("/downloads/permissions/")
    request.user = user if user is not None else AnonymousUser()
    return request


def test_can_download_resource_permission():
    permission = download_permissions.CanDownloadResource()

    assert permission.has_object_permission(
        _request(APIRequestFactory()), None, SimpleNamespace(status="approved")
    )
    assert not permission.has_object_permission(
        _request(APIRequestFactory()), None, SimpleNamespace(status="pending")
    )


def test_can_download_personal_file_permission(user, admin_user):
    permission = download_permissions.CanDownloadPersonalFile()
    file_obj = SimpleNamespace(user=user)

    assert permission.has_object_permission(
        _request(APIRequestFactory(), user=user), None, file_obj
    )
    assert not permission.has_object_permission(
        _request(APIRequestFactory(), user=admin_user), None, file_obj
    )


def test_can_view_download_history_permission(user, admin_user):
    permission = download_permissions.CanViewDownloadHistory()
    history_obj = SimpleNamespace(user=user)
    factory = APIRequestFactory()

    assert permission.has_permission(_request(factory, user=user), None)
    assert not permission.has_permission(_request(factory), None)

    assert permission.has_object_permission(
        _request(factory, user=user), None, history_obj
    )
    assert not permission.has_object_permission(
        _request(factory, user=admin_user), None, history_obj
    )
