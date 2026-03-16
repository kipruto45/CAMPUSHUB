"""
Admin configuration for reports app.
"""

from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Admin configuration for Report model."""

    list_display = [
        "id",
        "get_target_type",
        "get_target_title",
        "reporter",
        "reason_type",
        "status",
        "created_at",
    ]
    list_filter = ["status", "reason_type", "created_at"]
    search_fields = [
        "reporter__email",
        "reporter__full_name",
        "resource__title",
        "message",
        "resolution_note",
    ]
    readonly_fields = [
        "reporter",
        "resource",
        "comment",
        "reason_type",
        "message",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Reporter & Content",
            {"fields": ("reporter", "resource", "comment", "reason_type", "message")},
        ),
        ("Resolution", {"fields": ("status", "reviewed_by", "resolution_note")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    actions = ["mark_as_resolved", "mark_as_dismissed"]

    def get_target_type(self, obj):
        return obj.get_target_type()

    get_target_type.short_description = "Type"

    def get_target_title(self, obj):
        if obj.resource:
            return obj.resource.title
        elif obj.comment:
            return f"Comment by {obj.comment.user.full_name}"
        return "N/A"

    get_target_title.short_description = "Target"

    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status="resolved", reviewed_by=request.user)
        self.message_user(request, f"{updated} report(s) marked as resolved.")

    mark_as_resolved.short_description = "Mark selected reports as resolved"

    def mark_as_dismissed(self, request, queryset):
        updated = queryset.update(status="dismissed", reviewed_by=request.user)
        self.message_user(request, f"{updated} report(s) dismissed.")

    mark_as_dismissed.short_description = "Dismiss selected reports"

    def has_add_permission(self, request):
        """Only allow viewing, not adding directly from admin."""
        return False
