"""
Admin configuration for certificates app.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Certificate, CertificateTemplate, CertificateType


@admin.register(CertificateType)
class CertificateTypeAdmin(admin.ModelAdmin):
    """Admin configuration for CertificateType."""

    list_display = ["name", "type", "is_active", "requires_verification", "created_at"]
    list_filter = ["type", "is_active", "requires_verification"]
    search_fields = ["name", "description"]
    ordering = ["name"]
    list_per_page = 25


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for CertificateTemplate."""

    list_display = ["name", "certificate_type", "is_default", "is_active", "created_at"]
    list_filter = ["certificate_type", "is_default", "is_active"]
    search_fields = ["name", "title"]
    ordering = ["name"]
    list_per_page = 25


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """Admin configuration for Certificate."""

    list_display = [
        "unique_id",
        "recipient_name",
        "certificate_type",
        "status",
        "issue_date",
        "view_pdf_link",
    ]
    list_filter = ["status", "certificate_type", "issue_date"]
    search_fields = [
        "unique_id",
        "recipient_name",
        "title",
        "user__email",
        "user__full_name",
    ]
    ordering = ["-issue_date"]
    list_per_page = 25
    readonly_fields = [
        "unique_id",
        "verification_url",
        "qr_code",
        "pdf_file",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "unique_id",
                    "user",
                    "certificate_type",
                    "template",
                )
            },
        ),
        (
            "Certificate Details",
            {
                "fields": (
                    "title",
                    "recipient_name",
                    "description",
                    "course",
                    "achievement",
                )
            },
        ),
        (
            "Issuing Information",
            {
                "fields": (
                    "issuing_authority",
                    "issued_by",
                    "issue_date",
                    "expiry_date",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "metadata",
                    "notes",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "verification_url",
                    "qr_code",
                    "pdf_file",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def view_pdf_link(self, obj):
        if obj.pdf_file:
            return format_html(
                '<a href="{}" target="_blank">View PDF</a>', obj.pdf_file.url
            )
        return "-"

    view_pdf_link.short_description = "PDF"
