"""
URL configuration for cloud storage integration.
"""

from django.urls import path

from . import views

app_name = "cloud_storage"

urlpatterns = [
    # Connection + status
    path("<str:provider>/status/", views.CloudStorageStatusView.as_view(), name="status"),
    path("<str:provider>/account/", views.CloudStorageAccountView.as_view(), name="account"),
    path("<str:provider>/connect/", views.CloudStorageConnectView.as_view(), name="connect"),
    path("<str:provider>/oauth/callback/", views.CloudStorageOAuthCallbackView.as_view(), name="callback"),
    path("<str:provider>/disconnect/", views.CloudStorageDisconnectView.as_view(), name="disconnect"),
    # Browsing & storage info
    path("<str:provider>/files/", views.CloudStorageFilesView.as_view(), name="files"),
    path("<str:provider>/folders/", views.CloudStorageFoldersView.as_view(), name="folders"),
    path("<str:provider>/download/<str:file_id>/", views.CloudStorageDownloadView.as_view(), name="download"),
    path("<str:provider>/storage/", views.CloudStorageStorageView.as_view(), name="storage"),
    path("<str:provider>/sync/", views.CloudStorageSyncView.as_view(), name="sync"),
    # Import/export operations
    path("<str:provider>/import/", views.cloud_storage_import, name="import"),
    path("<str:provider>/export/", views.cloud_storage_export, name="export"),
    # List all connected accounts
    path("accounts/", views.CloudAccountsListView.as_view(), name="accounts"),
]
