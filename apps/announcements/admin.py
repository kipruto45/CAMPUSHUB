"""
Admin configuration for announcements app.
"""

from django.contrib import admin

from .models import Announcement, AnnouncementAttachment


class AnnouncementAttachmentInline(admin.TabularInline):
    model = AnnouncementAttachment
    extra = 1
    readonly_fields = ["filename", "file_size", "file_type", "created_at", "updated_at"]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "announcement_type",
        "status",
        "is_pinned",
        "published_at",
        "created_by",
    ]
    list_filter = [
        "status",
        "announcement_type",
        "is_pinned",
        "target_faculty",
        "target_department",
    ]
    search_fields = ["title", "content"]
    readonly_fields = ["slug", "created_at", "updated_at"]
    date_hierarchy = "published_at"
    inlines = [AnnouncementAttachmentInline]

    fieldsets = (
        ("Basic Info", {"fields": ("title", "slug", "content")}),
        ("Classification", {"fields": ("announcement_type", "status", "is_pinned")}),
        (
            "Targeting",
            {
                "fields": (
                    "target_faculty",
                    "target_department",
                    "target_course",
                    "target_year_of_study",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "published_at", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
