"""
Services for Library & Storage Management Module.
Handles storage calculations, trash operations, file management, folder operations.
"""

from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.text import slugify

from apps.core.storage.utils import build_storage_download_path
from apps.resources.models import PersonalFolder, PersonalResource


# Default storage limits (in bytes)
DEFAULT_STORAGE_LIMIT = 500 * 1024 * 1024  # 500 MB
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file

# Warning thresholds
STORAGE_WARNING_THRESHOLD = 0.7  # 70%
STORAGE_CRITICAL_THRESHOLD = 0.9  # 90%

# Allowed file extensions
ALLOWED_FILE_EXTENSIONS = [
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "txt",
    "rtf",
    "odt",
    "ods",
    "odp",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "svg",
    "zip",
    "rar",
    "7z",
    "tar",
    "gz",
    "mp3",
    "mp4",
    "wav",
    "avi",
    "mov",
    "mkv",
]

RESOURCE_TYPE_LIBRARY_FOLDERS = {
    "notes": {"name": "Notes", "color": "#3b82f6"},
    "past_paper": {"name": "Past Papers", "color": "#f59e0b"},
    "assignment": {"name": "Assignments", "color": "#ef4444"},
    "book": {"name": "Books", "color": "#10b981"},
    "slides": {"name": "Slides", "color": "#06b6d4"},
    "tutorial": {"name": "Tutorials", "color": "#8b5cf6"},
    "other": {"name": "Other", "color": "#6b7280"},
}


# =============================================================================
# STORAGE SERVICE
# =============================================================================


def calculate_user_storage(user):
    """
    Calculate total storage used by a user.
    Excludes trashed files from the count.
    """
    total_size = (
        PersonalResource.objects.filter(user=user).aggregate(total=Sum("file_size"))[
            "total"
        ]
        or 0
    )
    return total_size


def get_storage_limit(user):
    """
    Get storage limit for a user.
    Can be extended based on user tiers in the future.
    """
    return DEFAULT_STORAGE_LIMIT


def get_storage_summary(user):
    """
    Get complete storage summary for a user.
    """
    storage_used = calculate_user_storage(user)
    storage_limit = get_storage_limit(user)
    storage_remaining = max(0, storage_limit - storage_used)
    usage_percent = (storage_used / storage_limit * 100) if storage_limit > 0 else 0

    # Get user-scoped file count (excluding trashed - uses custom manager)
    file_count = PersonalResource.objects.filter(user=user).count()

    # Determine warning level
    warning_level = "normal"
    if usage_percent >= STORAGE_CRITICAL_THRESHOLD * 100:
        warning_level = "critical"
    elif usage_percent >= STORAGE_WARNING_THRESHOLD * 100:
        warning_level = "warning"

    return {
        "storage_limit_bytes": storage_limit,
        "storage_used_bytes": storage_used,
        "storage_remaining_bytes": storage_remaining,
        "usage_percent": round(usage_percent, 2),
        "total_files": file_count,
        "warning_level": warning_level,
    }


def can_user_upload_file(user, file_size):
    """
    Check if user can upload a file based on size and remaining storage.
    """
    # Check per-file size limit
    if file_size > MAX_FILE_SIZE:
        return (
            False,
            f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / 1024 / 1024}MB",
        )

    # Check total storage limit
    current_usage = calculate_user_storage(user)
    storage_limit = get_storage_limit(user)

    if current_usage + file_size > storage_limit:
        remaining = storage_limit - current_usage
        return (
            False,
            f"Not enough storage. You have {remaining / 1024 / 1024:.2f}MB remaining.",
        )

    return True, None


def is_allowed_file_type(filename):
    """
    Check if file type is allowed.
    """
    extension = filename.split(".")[-1].lower() if "." in filename else ""
    return extension in ALLOWED_FILE_EXTENSIONS


def get_folder_storage(user, folder):
    """
    Calculate storage used by a specific folder.
    """
    total_size = (
        PersonalResource.objects.filter(user=user, folder=folder).aggregate(
            total=Sum("file_size")
        )["total"]
        or 0
    )
    return total_size


def get_default_resource_type_folder_name(resource_type: str | None) -> str:
    """
    Resolve the default personal-library folder name for a resource type.
    """
    return RESOURCE_TYPE_LIBRARY_FOLDERS.get(
        resource_type or "other",
        RESOURCE_TYPE_LIBRARY_FOLDERS["other"],
    )["name"]


def get_or_create_resource_type_folder(user, resource):
    """
    Get or create a top-level personal folder for the resource type.
    """
    config = RESOURCE_TYPE_LIBRARY_FOLDERS.get(
        getattr(resource, "resource_type", None) or "other",
        RESOURCE_TYPE_LIBRARY_FOLDERS["other"],
    )
    folder = PersonalFolder.objects.filter(
        user=user,
        parent__isnull=True,
        name__iexact=config["name"],
    ).first()
    if folder:
        return folder, False

    folder = PersonalFolder.objects.create(
        user=user,
        name=config["name"],
        color=config["color"],
    )
    return folder, True


def save_public_resource_to_library(user, resource, folder=None, title=None):
    """
    Save an approved public resource into the user's personal library.

    When no destination folder is provided, the resource is routed into a
    top-level folder derived from its resource type.
    """
    if resource.status != "approved" or not resource.is_public:
        raise ValueError("Only approved public resources can be added to your library.")

    if not resource.file:
        raise ValueError("Resource file is not available.")

    auto_assign_folder = folder is None
    if auto_assign_folder:
        folder, _ = get_or_create_resource_type_folder(user, resource)
    elif folder.user_id != user.id:
        raise ValueError("Folder not found.")

    existing = (
        PersonalResource.objects.select_related("folder")
        .filter(user=user, linked_public_resource=resource)
        .first()
    )
    if existing:
        if auto_assign_folder and existing.folder_id is None and folder is not None:
            existing.folder = folder
            existing.save(update_fields=["folder"])
        return existing, False, existing.folder or folder

    personal_resource = PersonalResource.objects.create(
        user=user,
        folder=folder,
        title=title or resource.title,
        file=resource.file,
        file_type=resource.file_type,
        file_size=resource.file_size,
        description=resource.description,
        tags=resource.tags,
        visibility="private",
        source_type="saved",
        linked_public_resource=resource,
    )
    return personal_resource, True, folder


# =============================================================================
# FOLDER SERVICE
# =============================================================================


def create_folder(user, data):
    """
    Create a new folder for a user.
    """
    name = data.get("name")
    parent = data.get("parent")
    color = data.get("color", "#3b82f6")

    # Validate parent belongs to user if provided
    if parent:
        if not PersonalFolder.objects.filter(id=parent.id, user=user).exists():
            raise ValueError("Parent folder not found or does not belong to you.")

    # Check for duplicate name in same parent
    query = Q(user=user, name__iexact=name, parent=parent)
    if parent is None:
        query = Q(user=user, name__iexact=name, parent__isnull=True)
    
    if PersonalFolder.objects.filter(query).exists():
        raise ValueError("A folder with this name already exists in this location.")

    folder = PersonalFolder.objects.create(
        user=user,
        name=name,
        parent=parent,
        color=color,
        slug=slugify(f"{name}-{user.id}-{timezone.now().timestamp()}"),
    )
    return folder


def rename_folder(user, folder, data):
    """
    Rename a folder.
    """
    new_name = data.get("name")

    if not new_name:
        raise ValueError("Folder name is required.")

    # Check for duplicate name in same parent
    query = Q(user=user, name__iexact=new_name, parent=folder.parent)
    if folder.parent is None:
        query = Q(user=user, name__iexact=new_name, parent__isnull=True)
    
    # Exclude current folder
    existing = PersonalFolder.objects.filter(query).exclude(id=folder.id).exists()
    if existing:
        raise ValueError("A folder with this name already exists in this location.")

    folder.name = new_name
    folder.save()
    return folder


def move_folder(user, folder, target_parent):
    """
    Move a folder to a new parent.
    """
    # Validate target parent belongs to user
    if target_parent:
        if not PersonalFolder.objects.filter(id=target_parent.id, user=user).exists():
            raise ValueError("Target folder not found or does not belong to you.")
        
        # Check for circular nesting - folder cannot be moved into itself or its descendants
        if target_parent.id == folder.id:
            raise ValueError("Folder cannot be moved into itself.")
        
        # Check if target is a descendant of the folder
        current = target_parent
        while current:
            if current.id == folder.id:
                raise ValueError("Folder cannot be moved into one of its own subfolders.")
            current = current.parent

    # Check for duplicate name in target location
    query = Q(user=user, name__iexact=folder.name, parent=target_parent)
    if target_parent is None:
        query = Q(user=user, name__iexact=folder.name, parent__isnull=True)
    
    existing = PersonalFolder.objects.filter(query).exclude(id=folder.id).exists()
    if existing:
        raise ValueError("A folder with this name already exists in the target location.")

    folder.parent = target_parent
    folder.save()
    return folder


def favorite_folder(user, folder):
    """
    Toggle favorite status of a folder.
    """
    folder.is_favorite = not folder.is_favorite
    folder.save()
    return folder


def delete_folder(user, folder):
    """
    Delete a folder and optionally its contents.
    """
    # Move all files in folder to root (not trashed)
    PersonalResource.objects.filter(folder=folder).update(folder=None)
    
    # Move all subfolders to root
    PersonalFolder.objects.filter(parent=folder).update(parent=folder.parent)
    
    folder.delete()
    return True


def get_folder_by_id(user, folder_id):
    """
    Get a folder by ID for a specific user.
    """
    try:
        return PersonalFolder.objects.get(id=folder_id, user=user)
    except PersonalFolder.DoesNotExist:
        return None


def get_user_folders(user, parent=None):
    """
    Get all folders for a user, optionally filtered by parent.
    """
    query = Q(user=user)
    if parent is not None:
        query &= Q(parent=parent)
    else:
        query &= Q(parent__isnull=True)
    
    return PersonalFolder.objects.filter(query).prefetch_related("subfolders")


def get_all_user_folders(user):
    """
    Get all folders for a user (for move operations).
    """
    return PersonalFolder.objects.filter(user=user).order_by("parent__name", "name")


# =============================================================================
# FILE SERVICE
# =============================================================================


def upload_file(user, file_obj, data):
    """
    Upload a new file for a user.
    """
    title = data.get("title", file_obj.name)
    folder = data.get("folder")
    description = data.get("description", "")

    # Validate folder belongs to user if provided
    if folder:
        if not PersonalFolder.objects.filter(id=folder.id, user=user).exists():
            raise ValueError("Folder not found or does not belong to you.")

    # Check storage limits
    file_size = file_obj.size if hasattr(file_obj, "size") else 0
    can_upload, error_msg = can_user_upload_file(user, file_size)
    if not can_upload:
        raise ValueError(error_msg)

    # Check file type
    filename = file_obj.name if hasattr(file_obj, "name") else ""
    if not is_allowed_file_type(filename):
        raise ValueError("File type not allowed.")

    # Create the file
    personal_file = PersonalResource.objects.create(
        user=user,
        folder=folder,
        title=title,
        file=file_obj,
        description=description,
        source_type="uploaded",
    )
    return personal_file


def rename_file(user, file_obj, data):
    """
    Rename a file.
    """
    new_title = data.get("title")

    if not new_title:
        raise ValueError("File title is required.")

    file_obj.title = new_title
    file_obj.save()
    return file_obj


def move_file(user, file_obj, target_folder):
    """
    Move a file to a different folder.
    """
    # Validate target folder belongs to user if provided
    if target_folder:
        if not PersonalFolder.objects.filter(id=target_folder.id, user=user).exists():
            raise ValueError("Target folder not found or does not belong to you.")

    file_obj.folder = target_folder
    file_obj.save()
    return file_obj


def duplicate_file(user, file_obj):
    """
    Duplicate a file.
    """
    if not file_obj.file:
        raise ValueError("Cannot duplicate file without file content.")

    # Create duplicate with modified title
    duplicate_title = f"{file_obj.title} (Copy)"
    
    # Handle duplicate title if it exists
    base_title = duplicate_title
    counter = 1
    while PersonalResource.objects.filter(
        user=user, 
        folder=file_obj.folder, 
        title=duplicate_title
    ).exists():
        counter += 1
        duplicate_title = f"{base_title} ({counter})"

    # Copy the file
    from django.core.files.base import ContentFile
    file_content = file_obj.file.read()
    file_copy = ContentFile(file_content)
    file_copy.name = file_obj.file.name

    duplicate = PersonalResource.objects.create(
        user=user,
        folder=file_obj.folder,
        title=duplicate_title,
        file=file_copy,
        file_type=file_obj.file_type,
        description=file_obj.description,
        source_type="imported",
    )
    return duplicate


def favorite_file(user, file_obj):
    """
    Toggle favorite status of a file.
    """
    file_obj.is_favorite = not file_obj.is_favorite
    file_obj.save()
    return file_obj


def track_file_access(user, file_obj):
    """
    Track file access time.
    """
    file_obj.mark_accessed()
    return file_obj


def get_file_by_id(user, file_id):
    """
    Get a file by ID for a specific user.
    """
    try:
        return PersonalResource.objects.get(id=file_id, user=user)
    except PersonalResource.DoesNotExist:
        return None


def get_files_in_folder(user, folder=None):
    """
    Get all files in a specific folder or root.
    """
    query = Q(user=user)
    if folder is not None:
        query &= Q(folder=folder)
    else:
        query &= Q(folder__isnull=True)
    
    return PersonalResource.objects.filter(query).order_by("-created_at")


def get_user_files(user):
    """
    Get all files for a user.
    """
    return PersonalResource.objects.filter(user=user).order_by("-created_at")


# =============================================================================
# RECENT & FAVORITES SERVICE
# =============================================================================


def get_recent_files(user, limit=10):
    """
    Get recently accessed files for a user.
    """
    return (
        PersonalResource.objects.filter(user=user)
        .exclude(last_accessed_at__isnull=True)
        .order_by("-last_accessed_at")[:limit]
    )


def get_favorite_files(user):
    """
    Get favorite files for a user.
    """
    return PersonalResource.objects.filter(user=user, is_favorite=True).order_by(
        "-updated_at"
    )


def get_favorite_folders(user):
    """
    Get favorite folders for a user.
    """
    return PersonalFolder.objects.filter(user=user, is_favorite=True).order_by(
        "-updated_at"
    )


# =============================================================================
# SHARE SERVICE
# =============================================================================


def generate_share_link(user, file_obj):
    """
    Generate a shareable link for a personal file.
    Personal files are private, so this creates a temporary token-based URL.
    """
    import uuid
    from django.core.signing import TimestampSigner
    
    # Generate a unique share token
    share_token = str(uuid.uuid4())
    
    # Store the token temporarily (in a real app, you'd store this in a model)
    # For now, we'll return a signed URL that includes the file ID
    signer = TimestampSigner()
    signed_token = signer.sign(f"{file_obj.id}:{share_token}")
    
    return {
        "token": signed_token,
        "file_id": str(file_obj.id),
        "file_title": file_obj.title,
        "file_type": file_obj.file_type,
        "expires_in": 7 * 24 * 60 * 60,  # 7 days in seconds
    }


def get_shareable_file(file_id, token):
    """
    Get a file by share token.
    Used to validate share links.
    """
    from django.core.signing import BadSignature, TimestampSigner
    
    try:
        signer = TimestampSigner()
        unsigned = signer.unsign(token, max_age=7 * 24 * 60 * 60)  # 7 days
        file_id_from_token, _ = unsigned.split(":")
        
        if str(file_id) != file_id_from_token:
            return None
            
        return PersonalResource.objects.get(id=file_id)
    except (BadSignature, ValueError, PersonalResource.DoesNotExist):
        return None


def record_share_activity(user, file_obj, method):
    """
    Record when a file is shared.
    """
    # This could be extended to store share history
    file_obj.save()  # Updates the updated_at timestamp
    return True


def get_file_download_url(user, file_obj, request):
    """
    Get a direct download URL for a file.
    """
    if file_obj.file:
        return request.build_absolute_uri(
            build_storage_download_path(file_obj.file.name, public=False)
        )
    return None


def get_file_preview_info(user, file_obj):
    """
    Get preview information for a file.
    Returns metadata needed for preview generation.
    """
    file_type = file_obj.file_type.lower() if file_obj.file_type else ""
    
    # Determine if file is previewable
    previewable_types = [
        "pdf",
        "doc", "docx",
        "xls", "xlsx",
        "ppt", "pptx",
        "txt", "rtf",
        "jpg", "jpeg", "png", "gif", "bmp", "svg",
    ]
    
    is_previewable = any(file_type.endswith(ext) for ext in previewable_types)
    is_image = file_type.startswith("image") or file_type in ["jpg", "jpeg", "png", "gif", "bmp", "svg"]
    is_pdf = file_type == "pdf"
    
    return {
        "is_previewable": is_previewable,
        "is_image": is_image,
        "is_pdf": is_pdf,
        "preview_type": "image" if is_image else ("pdf" if is_pdf else "document"),
        "file_type": file_type,
    }


# =============================================================================
# LIBRARY OVERVIEW SERVICE
# =============================================================================


def get_library_overview(user):
    """
    Get comprehensive library overview including:
    - Top folders (root level)
    - Recent files
    - Favorites preview
    - Storage summary
    """
    # Get root folders
    root_folders = (
        PersonalFolder.objects.filter(user=user, parent__isnull=True)
        .prefetch_related("subfolders")
        .order_by("-is_favorite", "name")[:10]
    )

    # Get recent files
    recent_files = get_recent_files(user, limit=5)

    # Get favorite folders
    favorite_folders = get_favorite_folders(user)[:5]

    # Get favorite files
    favorite_files = get_favorite_files(user)[:5]

    # Get storage summary
    storage = get_storage_summary(user)

    return {
        "root_folders": root_folders,
        "recent_files": recent_files,
        "favorite_folders": favorite_folders,
        "favorite_files": favorite_files,
        "storage_summary": storage,
    }


# =============================================================================
# TRASH SERVICE
# =============================================================================


def move_file_to_trash(user, file_obj):
    """
    Move a file to trash (soft delete).
    """
    if file_obj.user != user:
        raise PermissionError("You don't have permission to delete this file.")

    if file_obj.is_deleted:
        raise ValueError("File is already in trash.")

    # Store original folder
    file_obj.original_folder = file_obj.folder
    file_obj.folder = None  # Remove from current folder
    file_obj.is_deleted = True
    file_obj.deleted_at = timezone.now()
    file_obj.save()

    return file_obj


def restore_trashed_file(user, file_obj):
    """
    Restore a trashed file to its original location.
    """
    if file_obj.user != user:
        raise PermissionError("You don't have permission to restore this file.")

    if not file_obj.is_deleted:
        raise ValueError("File is not in trash.")

    # Restore to original folder if it exists and belongs to user
    if file_obj.original_folder and file_obj.original_folder.user == user:
        file_obj.folder = file_obj.original_folder
    else:
        file_obj.folder = None  # Restore to root

    file_obj.is_deleted = False
    file_obj.deleted_at = None
    file_obj.save()

    return file_obj


def permanently_delete_file(user, file_obj):
    """
    Permanently delete a trashed file.
    """
    if file_obj.user != user:
        raise PermissionError("You don't have permission to delete this file.")

    if not file_obj.is_deleted:
        raise ValueError("File must be in trash before permanent deletion.")

    # Delete the actual file from storage
    if file_obj.file:
        file_obj.file.delete(save=False)

    file_obj.delete()
    return True


def get_user_trash_items(user):
    """
    Get all trashed items for a user.
    """
    return (
        PersonalResource.all_objects.filter(user=user, is_deleted=True)
        .select_related("original_folder")
        .order_by("-deleted_at")
    )
