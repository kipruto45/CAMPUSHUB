"""
URL configuration for Library & Storage Management Module.
"""

from django.urls import path

from apps.library import views

app_name = "library"

urlpatterns = [
    # Library Overview
    path("", views.LibraryOverviewView.as_view(), name="library-overview"),
    
    # Storage
    path(
        "storage-summary/", views.StorageSummaryView.as_view(), name="storage-summary"
    ),
    
    # Folders
    path("folders/", views.FolderListView.as_view(), name="folder-list"),
    path(
        "folders/all/", views.AllFoldersView.as_view(), name="folder-all"
    ),
    path(
        "folders/<uuid:folder_id>/",
        views.FolderDetailView.as_view(),
        name="folder-detail",
    ),
    path(
        "folders/<uuid:folder_id>/move/",
        views.MoveFolderView.as_view(),
        name="folder-move",
    ),
    path(
        "folders/<uuid:folder_id>/favorite/",
        views.FavoriteFolderView.as_view(),
        name="folder-favorite",
    ),
    
    # Files
    path("files/", views.FileListView.as_view(), name="file-list"),
    path(
        "files/<uuid:file_id>/",
        views.FileDetailView.as_view(),
        name="file-detail",
    ),
    path(
        "files/<uuid:file_id>/move/",
        views.MoveFileView.as_view(),
        name="file-move",
    ),
    path(
        "files/<uuid:file_id>/duplicate/",
        views.DuplicateFileView.as_view(),
        name="file-duplicate",
    ),
    path(
        "files/<uuid:file_id>/favorite/",
        views.FavoriteFileView.as_view(),
        name="file-favorite",
    ),
    
    # Share, Download & Preview
    path(
        "files/<uuid:file_id>/share/",
        views.ShareFileView.as_view(),
        name="file-share",
    ),
    path(
        "files/<uuid:file_id>/download/",
        views.FileDownloadView.as_view(),
        name="file-download",
    ),
    path(
        "files/<uuid:file_id>/preview/",
        views.FilePreviewView.as_view(),
        name="file-preview",
    ),
    
    # Recent & Favorites
    path("recent/", views.RecentFilesView.as_view(), name="recent-files"),
    path("favorites/files/", views.FavoriteFilesView.as_view(), name="favorite-files"),
    path("favorites/folders/", views.FavoriteFoldersView.as_view(), name="favorite-folders"),
    
    # Trash / Recovery
    path("trash/", views.TrashListView.as_view(), name="trash-list"),
    path(
        "trash/move-to-trash/",
        views.MoveFileToTrashView.as_view(),
        name="move-to-trash",
    ),
    path("trash/restore/", views.RestoreFileView.as_view(), name="restore-file"),
    path(
        "trash/permanent-delete/",
        views.PermanentDeleteView.as_view(),
        name="permanent-delete",
    ),
    # Alternative endpoints for trash operations by ID
    path(
        "files/<uuid:file_id>/restore/",
        views.restore_file_by_id,
        name="file-restore",
    ),
    path(
        "files/<uuid:file_id>/permanent-delete/",
        views.permanent_delete_by_id,
        name="file-permanent-delete",
    ),
]
