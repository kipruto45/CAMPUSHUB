"""
Views for Library & Storage Management Module.
"""

from django.db.models import Q
from django.http import HttpResponseRedirect
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from apps.core.pagination import StandardResultsSetPagination
from apps.library.permissions import IsOwnerOrReadOnly
from apps.library.serializers import (
    CreateFolderSerializer,
    FileShareSerializer,
    FilePreviewSerializer,
    LibraryOverviewSerializer,
    MoveFileSerializer,
    MoveFolderSerializer,
    MoveToTrashSerializer,
    PermanentDeleteSerializer,
    PersonalFolderDetailSerializer,
    PersonalFolderSerializer,
    PersonalResourceDetailSerializer,
    PersonalResourceSerializer,
    RenameFileSerializer,
    RenameFolderSerializer,
    RestoreFileSerializer,
    StorageSummarySerializer,
    TrashItemSerializer,
    UploadFileSerializer,
)
from apps.library.services import (
    can_user_upload_file,
    create_folder,
    delete_folder,
    duplicate_file,
    favorite_file,
    favorite_folder,
    generate_share_link,
    get_shareable_file,
    get_all_user_folders,
    get_favorite_files,
    get_favorite_folders,
    get_file_by_id,
    get_file_download_url,
    get_file_preview_info,
    get_files_in_folder,
    get_folder_by_id,
    get_library_overview,
    get_recent_files,
    get_storage_summary,
    get_user_folders,
    get_user_trash_items,
    is_allowed_file_type,
    move_file,
    move_folder,
    move_file_to_trash,
    permanently_delete_file,
    record_share_activity,
    rename_file,
    rename_folder,
    restore_trashed_file,
    upload_file,
)
from apps.resources.models import PersonalFolder, PersonalResource
from apps.core.storage import get_storage_service


# =============================================================================
# LIBRARY OVERVIEW
# =============================================================================


class LibraryOverviewView(APIView):
    """
    Get library overview for the authenticated user.
    Returns top folders, recent files, favorites, and storage summary.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        overview = get_library_overview(request.user)
        serializer = LibraryOverviewSerializer(overview)
        return Response(serializer.data)


# =============================================================================
# STORAGE
# =============================================================================


class StorageSummaryView(APIView):
    """
    Get storage summary for the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        summary = get_storage_summary(request.user)
        serializer = StorageSummarySerializer(summary)
        return Response(serializer.data)


# =============================================================================
# FOLDERS
# =============================================================================


class FolderListView(generics.ListCreateAPIView):
    """
    List and create personal folders.
    """

    serializer_class = PersonalFolderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PersonalFolder.objects.none()
        
        parent_id = self.request.query_params.get("parent")
        user = self.request.user
        
        if parent_id:
            return PersonalFolder.objects.filter(
                user=user, parent_id=parent_id
            ).prefetch_related("subfolders", "personal_resources")
        else:
            return PersonalFolder.objects.filter(
                user=user, parent__isnull=True
            ).prefetch_related("subfolders", "personal_resources")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateFolderSerializer
        return PersonalFolderSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        parent_id = data.get("parent")
        parent = None
        if parent_id:
            parent = PersonalFolder.objects.filter(
                id=parent_id, user=self.request.user
            ).first()
        
        folder = create_folder(self.request.user, {
            "name": data.get("name"),
            "parent": parent,
            "color": data.get("color", "#3b82f6"),
        })
        return folder

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        folder = self.perform_create(serializer)
        response_serializer = PersonalFolderSerializer(folder, context={"request": request})
        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class FolderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a personal folder.
    """

    serializer_class = PersonalFolderDetailSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    lookup_url_kwarg = "folder_id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PersonalFolder.objects.none()
        return PersonalFolder.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return RenameFolderSerializer
        return PersonalFolderDetailSerializer

    def perform_update(self, serializer):
        if isinstance(serializer.validated_data, dict):
            folder = serializer.save()
            return folder
        # Handle simple update
        folder = self.get_object()
        folder = rename_folder(self.request.user, folder, serializer.validated_data)
        return folder

    def perform_destroy(self, instance):
        delete_folder(self.request.user, instance)


class MoveFolderView(APIView):
    """
    Move a folder to a different parent.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, folder_id, *args, **kwargs):
        serializer = MoveFolderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        folder = get_folder_by_id(request.user, folder_id)
        if not folder:
            return Response(
                {"error": "Folder not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        target_parent_id = serializer.validated_data.get("target_parent_id")
        target_parent = None
        if target_parent_id:
            target_parent = get_folder_by_id(request.user, target_parent_id)
            if not target_parent:
                return Response(
                    {"error": "Target folder not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            folder = move_folder(request.user, folder, target_parent)
            return Response(PersonalFolderSerializer(folder).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FavoriteFolderView(APIView):
    """
    Toggle favorite status of a folder.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, folder_id, *args, **kwargs):
        folder = get_folder_by_id(request.user, folder_id)
        if not folder:
            return Response(
                {"error": "Folder not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        folder = favorite_folder(request.user, folder)
        return Response(PersonalFolderSerializer(folder).data)


class AllFoldersView(APIView):
    """
    Get all folders for a user (for move operations).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        folders = get_all_user_folders(request.user)
        serializer = PersonalFolderSerializer(folders, many=True)
        return Response(serializer.data)


# =============================================================================
# FILES
# =============================================================================


class FileListView(generics.ListCreateAPIView):
    """
    List and create personal files.
    """

    serializer_class = PersonalResourceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PersonalResource.objects.none()
        
        folder_id = self.request.query_params.get("folder")
        user = self.request.user
        
        if folder_id:
            return PersonalResource.objects.filter(
                user=user, folder_id=folder_id
            ).select_related("folder")
        else:
            return PersonalResource.objects.filter(
                user=user, folder__isnull=True
            ).select_related("folder")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UploadFileSerializer
        return PersonalResourceSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        folder_id = data.get("folder")
        folder = None
        if folder_id:
            folder = PersonalFolder.objects.filter(
                id=folder_id, user=self.request.user
            ).first()
        
        file_obj = upload_file(self.request.user, data.get("file"), {
            "title": data.get("title"),
            "folder": folder,
            "description": data.get("description", ""),
        })
        return file_obj


class FileDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a personal file.
    """

    serializer_class = PersonalResourceDetailSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    lookup_url_kwarg = "file_id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PersonalResource.objects.none()
        # Use all_objects to include soft-deleted items for delete operations
        return PersonalResource.all_objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return RenameFileSerializer
        return PersonalResourceDetailSerializer

    def perform_update(self, serializer):
        file_obj = serializer.save()
        return file_obj

    def perform_destroy(self, instance):
        move_file_to_trash(self.request.user, instance)


class MoveFileView(APIView):
    """
    Move a file to a different folder.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, file_id, *args, **kwargs):
        serializer = MoveFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = get_file_by_id(request.user, file_id)
        if not file_obj:
            return Response(
                {"error": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        folder_id = serializer.validated_data.get("folder_id")
        target_folder = None
        if folder_id:
            target_folder = get_folder_by_id(request.user, folder_id)
            if not target_folder:
                return Response(
                    {"error": "Target folder not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            file_obj = move_file(request.user, file_obj, target_folder)
            return Response(PersonalResourceSerializer(file_obj).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DuplicateFileView(APIView):
    """
    Duplicate a file.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, file_id, *args, **kwargs):
        file_obj = get_file_by_id(request.user, file_id)
        if not file_obj:
            return Response(
                {"error": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            duplicate = duplicate_file(request.user, file_obj)
            return Response(PersonalResourceSerializer(duplicate).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FavoriteFileView(APIView):
    """
    Toggle favorite status of a file.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, file_id, *args, **kwargs):
        file_obj = get_file_by_id(request.user, file_id)
        if not file_obj:
            return Response(
                {"error": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_obj = favorite_file(request.user, file_obj)
        return Response(PersonalResourceSerializer(file_obj).data)


# =============================================================================
# SHARE
# =============================================================================


class SharedLibraryFileView(APIView):
    """
    Public share link resolver for personal library files.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, file_id, token, *args, **kwargs):
        file_obj = get_shareable_file(file_id, token)
        if not file_obj or file_obj.is_deleted:
            return Response(
                {"error": "Invalid or expired share link."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not file_obj.file:
            return Response(
                {"error": "File has no downloadable content."},
                status=status.HTTP_404_NOT_FOUND,
            )

        storage = get_storage_service()
        download_url = storage.get_url(
            file_obj.file.name,
            signed=True,
            expires=60 * 60,
            download=True,
        )
        if download_url.startswith("/"):
            download_url = request.build_absolute_uri(download_url)
        return HttpResponseRedirect(download_url)


class ShareFileView(APIView):
    """
    Generate a shareable link for a personal file.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, file_id, *args, **kwargs):
        file_obj = get_file_by_id(request.user, file_id)
        if not file_obj:
            return Response(
                {"error": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Generate share link
        share_data = generate_share_link(request.user, file_obj)
        
        # Build the full share URL
        base_url = request.build_absolute_uri("/")
        share_data["share_url"] = f"{base_url}share/library/{share_data['file_id']}/{share_data['token']}/"
        share_data["can_share"] = True
        
        serializer = FileShareSerializer(share_data, context={"request": request})
        return Response(serializer.data)

    def post(self, request, file_id, *args, **kwargs):
        """Record a share action."""
        file_obj = get_file_by_id(request.user, file_id)
        if not file_obj:
            return Response(
                {"error": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        method = request.data.get("method", "unknown")
        record_share_activity(request.user, file_obj, method)
        
        return Response({"success": True, "message": "Share recorded."})


class FileDownloadView(APIView):
    """
    Get download URL for a personal file.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, file_id, *args, **kwargs):
        file_obj = get_file_by_id(request.user, file_id)
        if not file_obj:
            return Response(
                {"error": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        download_url = get_file_download_url(request.user, file_obj, request)
        if not download_url:
            return Response(
                {"error": "File has no downloadable content."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "download_url": download_url,
            "file_name": file_obj.title,
            "file_type": file_obj.file_type,
            "file_size": file_obj.file_size,
        })


class FilePreviewView(APIView):
    """
    Get preview information for a personal file.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, file_id, *args, **kwargs):
        file_obj = get_file_by_id(request.user, file_id)
        if not file_obj:
            return Response(
                {"error": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        preview_info = get_file_preview_info(request.user, file_obj)
        preview_info["file_url"] = get_file_download_url(request.user, file_obj, request)
        preview_info["thumbnail_url"] = preview_info.get("file_url")  # Could add thumbnail generation
        
        serializer = FilePreviewSerializer(preview_info)
        return Response(serializer.data)


# =============================================================================
# RECENT & FAVORITES
# =============================================================================


class RecentFilesView(APIView):
    """
    Get recently accessed files.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        limit = int(request.query_params.get("limit", 10))
        files = get_recent_files(request.user, limit=limit)
        serializer = PersonalResourceSerializer(files, many=True)
        return Response(serializer.data)


class FavoriteFilesView(APIView):
    """
    Get favorite files.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        files = get_favorite_files(request.user)
        serializer = PersonalResourceSerializer(files, many=True)
        return Response(serializer.data)


class FavoriteFoldersView(APIView):
    """
    Get favorite folders.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        folders = get_favorite_folders(request.user)
        serializer = PersonalFolderSerializer(folders, many=True)
        return Response(serializer.data)


# =============================================================================
# TRASH
# =============================================================================


class TrashListView(APIView):
    """
    Get list of trashed items for the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        trash_items = get_user_trash_items(request.user)
        serializer = TrashItemSerializer(
            trash_items, many=True, context={"request": request}
        )
        return Response(serializer.data)


class MoveFileToTrashView(APIView):
    """
    Move a file to trash.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = MoveToTrashSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_id = serializer.validated_data["file_id"]

        try:
            file_obj = PersonalResource.all_objects.get(
                id=file_id, user=request.user, is_deleted=False
            )
        except PersonalResource.DoesNotExist:
            return Response(
                {"error": "File not found or already in trash."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            move_file_to_trash(request.user, file_obj)
            return Response(
                {"message": "File moved to trash successfully."},
                status=status.HTTP_200_OK,
            )
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RestoreFileView(APIView):
    """
    Restore a trashed file.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = RestoreFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_id = serializer.validated_data["file_id"]

        try:
            file_obj = PersonalResource.all_objects.get(
                id=file_id, user=request.user, is_deleted=True
            )
        except PersonalResource.DoesNotExist:
            return Response(
                {"error": "Trashed file not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            restore_trashed_file(request.user, file_obj)
            return Response(
                {"message": "File restored successfully."}, status=status.HTTP_200_OK
            )
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PermanentDeleteView(APIView):
    """
    Permanently delete a trashed file.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = PermanentDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_id = serializer.validated_data["file_id"]

        try:
            file_obj = PersonalResource.all_objects.get(
                id=file_id, user=request.user, is_deleted=True
            )
        except PersonalResource.DoesNotExist:
            return Response(
                {"error": "Trashed file not found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            permanently_delete_file(request.user, file_obj)
            return Response(
                {"message": "File permanently deleted."}, status=status.HTTP_200_OK
            )
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# FILE OPERATIONS BY ID
# =============================================================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def restore_file_by_id(request, file_id, *args, **kwargs):
    """Restore a trashed file by ID."""
    try:
        file_obj = PersonalResource.all_objects.get(
            id=file_id, user=request.user, is_deleted=True
        )
    except PersonalResource.DoesNotExist:
        return Response(
            {"error": "Trashed file not found."}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        restore_trashed_file(request.user, file_obj)
        return Response(
            {"message": "File restored successfully."}, status=status.HTTP_200_OK
        )
    except PermissionError as e:
        return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def permanent_delete_by_id(request, file_id, *args, **kwargs):
    """Permanently delete a trashed file by ID."""
    try:
        file_obj = PersonalResource.all_objects.get(
            id=file_id, user=request.user, is_deleted=True
        )
    except PersonalResource.DoesNotExist:
        return Response(
            {"error": "Trashed file not found."}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        permanently_delete_file(request.user, file_obj)
        return Response(
            {"message": "File permanently deleted."}, status=status.HTTP_200_OK
        )
    except PermissionError as e:
        return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
