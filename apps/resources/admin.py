"""
Admin configuration for resources app.
"""

from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.utils.safestring import mark_safe
from django.core.files.base import ContentFile
from django.contrib import messages
import zipfile
from io import BytesIO

from .models import (Folder, FolderItem, Resource, ResourceFile,
                     ResourceShareEvent, UserStorage)


class ResourceFileInline(admin.TabularInline):
    model = ResourceFile
    extra = 0
    readonly_fields = ["filename", "file_size", "file_type", "created_at"]


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """Admin configuration for Resource model."""

    list_display = [
        "title",
        "resource_type",
        "uploaded_by",
        "status",
        "is_pinned",
        "is_deleted",
        "view_count",
        "download_count",
        "share_count",
        "average_rating",
        "created_at",
    ]
    list_filter = [
        "status",
        "resource_type",
        "is_public",
        "is_pinned",
        "is_deleted",
        "created_at",
        "faculty",
        "department",
        "course",
    ]
    search_fields = ["title", "description", "tags", "uploaded_by__email"]
    readonly_fields = [
        "view_count",
        "download_count",
        "share_count",
        "average_rating",
        "created_at",
        "updated_at",
        "slug",
    ]
    ordering = ["-is_pinned", "-created_at"]
    date_hierarchy = "created_at"
    inlines = [ResourceFileInline]

    fieldsets = (
        ("Basic Info", {"fields": ("title", "slug", "description", "resource_type")}),
        ("File", {"fields": ("file", "thumbnail", "file_size", "file_type")}),
        (
            "Classification",
            {
                "fields": (
                    "faculty",
                    "department",
                    "course",
                    "unit",
                    "semester",
                    "year_of_study",
                    "tags",
                )
            },
        ),
        ("Uploader", {"fields": ("uploaded_by",)}),
        (
            "Status",
            {"fields": ("status", "is_public", "is_pinned", "rejection_reason")},
        ),
        (
            "Statistics",
            {"fields": ("view_count", "download_count", "share_count", "average_rating")},
        ),
        ("AI/OCR", {"fields": ("ocr_text", "ai_summary"), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    actions = [
        "approve_resources",
        "reject_resources",
        "make_public",
        "make_private",
        "pin_resources",
        "unpin_resources",
        "move_to_trash",
        "restore_from_trash",
        "permanent_delete_from_trash",
    ]

    def approve_resources(self, request, queryset):
        queryset.update(status="approved")

    def reject_resources(self, request, queryset):
        queryset.update(status="rejected")

    def make_public(self, request, queryset):
        queryset.update(is_public=True)

    def make_private(self, request, queryset):
        queryset.update(is_public=False)

    def pin_resources(self, request, queryset):
        queryset.update(is_pinned=True)

    def unpin_resources(self, request, queryset):
        queryset.update(is_pinned=False)

    def move_to_trash(self, request, queryset):
        moved = 0
        for res in queryset:
            res.soft_delete()
            moved += 1
        self.message_user(request, f"{moved} resources moved to trash.")

    def restore_from_trash(self, request, queryset):
        """Restore trashed resources from trash."""
        updated = queryset.update(is_deleted=False, deleted_at=None, status="approved")
        self.message_user(request, f"{updated} resources restored from trash.")

    def permanent_delete_from_trash(self, request, queryset):
        """Permanently delete resources from trash."""
        updated = queryset.delete()[0]
        self.message_user(request, f"{updated} resources permanently deleted.")

    def get_queryset(self, request):
        return self.model.all_objects.all()

    # -------- Bulk upload --------
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "bulk-upload/",
                self.admin_site.admin_view(self.bulk_upload_view),
                name="resources_resource_bulk_upload",
            )
        ]
        return custom + urls

    def bulk_upload_view(self, request):
        """
        Simple bulk upload: accept a ZIP, create a Resource per file.
        """
        context = dict(
            self.admin_site.each_context(request),
            opts=self.model._meta,
            title="Bulk upload resources",
        )
        if request.method == "POST" and request.FILES.get("zip_file"):
            zip_file = request.FILES["zip_file"]
            created = 0
            skipped = 0
            invalid = 0
            max_size = 25 * 1024 * 1024  # 25MB per file limit
            allowed_ext = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "png", "jpg", "jpeg"}

            # Optional flags
            status = request.POST.get("status", "approved")
            is_public = request.POST.get("is_public", "on") == "on"

            try:
                with zipfile.ZipFile(zip_file) as zf:
                    for name in zf.namelist():
                        if name.endswith("/") or name.startswith("__MACOSX"):
                            continue
                        info = zf.getinfo(name)
                        if info.file_size > max_size:
                            skipped += 1
                            continue
                        data = zf.read(name)
                        filename = name.split("/")[-1]
                        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                        if ext not in allowed_ext:
                            invalid += 1
                            continue
                        resource = Resource(
                            title=filename.rsplit(".", 1)[0],
                            uploaded_by=request.user,
                            status=status,
                            is_public=is_public,
                        )
                        resource.file.save(
                            f"resources/{filename}",
                            ContentFile(data),
                            save=True,
                        )
                        created += 1
                if created:
                    messages.success(request, f"Uploaded {created} resources.")
                if skipped:
                    messages.warning(request, f"Skipped {skipped} files (too large or invalid).")
                if invalid:
                    messages.warning(request, f"Skipped {invalid} files (unsupported type).")
            except zipfile.BadZipFile:
                messages.error(request, "Invalid ZIP file.")
            return redirect("..")

        return render(
            request,
            "admin/resources/resource/bulk_upload.html",
            context,
        )


@admin.register(ResourceFile)
class ResourceFileAdmin(admin.ModelAdmin):
    list_display = ["filename", "resource", "file_size", "file_type", "created_at"]
    list_filter = ["file_type", "created_at"]
    search_fields = ["filename", "resource__title"]


@admin.register(ResourceShareEvent)
class ResourceShareEventAdmin(admin.ModelAdmin):
    list_display = ["resource", "user", "share_method", "shared_at"]
    list_filter = ["share_method", "shared_at"]
    search_fields = ["resource__title", "user__email", "device_info", "ip_address"]
    readonly_fields = [
        "resource",
        "user",
        "share_method",
        "ip_address",
        "device_info",
        "shared_at",
    ]


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "color", "is_pinned", "created_at"]
    list_filter = ["is_pinned", "color", "created_at"]
    search_fields = ["name", "user__email"]


@admin.register(FolderItem)
class FolderItemAdmin(admin.ModelAdmin):
    list_display = ["folder", "resource", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["folder__name", "resource__title"]


@admin.register(UserStorage)
class UserStorageAdmin(admin.ModelAdmin):
    list_display = ["user", "used_storage", "storage_limit", "created_at"]
    search_fields = ["user__email"]
    readonly_fields = ["used_storage", "storage_limit", "created_at", "updated_at"]
