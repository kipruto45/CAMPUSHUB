"""
Admin configuration for resources app.
"""

from django.contrib import admin

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
