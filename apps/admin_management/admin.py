"""Admin configuration for invitation management."""

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from apps.admin_management.forms import AdminRoleInvitationAdminForm
from apps.admin_management.models import (
    AdminInvitationBatch,
    AdminInvitationRole,
    AdminRoleInvitation,
    AdminRoleInvitationRole,
    AdminUserRoleAssignment,
)
from apps.admin_management.services import (
    _select_primary_role_definition,
    create_role_invitation,
    revoke_role_invitation,
    sync_role_definition_group,
)


class InvitationStatusFilter(admin.SimpleListFilter):
    """Filter invitations by computed status."""

    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return (
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "pending":
            return queryset.filter(
                accepted_at__isnull=True,
                revoked_at__isnull=True,
                expires_at__gt=now,
            )
        if self.value() == "accepted":
            return queryset.filter(accepted_at__isnull=False)
        if self.value() == "expired":
            return queryset.filter(
                accepted_at__isnull=True,
                revoked_at__isnull=True,
                expires_at__lte=now,
            )
        if self.value() == "revoked":
            return queryset.filter(revoked_at__isnull=False)
        return queryset


class AdminRoleInvitationRoleInline(admin.TabularInline):
    """Read-only role breakdown for an invitation."""

    model = AdminRoleInvitationRole
    extra = 0
    can_delete = False
    readonly_fields = ("role_definition", "is_primary", "permission_preset", "created_at")


@admin.register(AdminInvitationRole)
class AdminInvitationRoleAdmin(admin.ModelAdmin):
    """Admin tools for invitation role templates and presets."""

    list_display = (
        "code",
        "name",
        "is_active",
        "is_assignable",
        "requires_superuser",
        "sort_order",
    )
    list_filter = ("is_active", "is_assignable", "requires_superuser")
    search_fields = ("code", "name", "description")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Role",
            {
                "fields": (
                    "code",
                    "name",
                    "description",
                    "sort_order",
                    "is_active",
                    "is_assignable",
                    "requires_superuser",
                )
            },
        ),
        (
            "Invitation Controls",
            {
                "fields": (
                    "inviter_permissions",
                    "permission_preset",
                    "email_subject_template",
                    "email_body_template",
                    "metadata",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        sync_role_definition_group(obj)


@admin.register(AdminRoleInvitation)
class AdminRoleInvitationAdmin(admin.ModelAdmin):
    """Admin interface for single and bulk role invitations."""

    form = AdminRoleInvitationAdminForm
    inlines = (AdminRoleInvitationRoleInline,)
    list_display = (
        "email",
        "role_summary",
        "status_badge",
        "source",
        "invited_by",
        "accepted_by",
        "expires_at",
        "created_at",
    )
    list_filter = (InvitationStatusFilter, "source", "role", "created_at")
    search_fields = ("email", "token", "note")
    raw_id_fields = ("invited_by", "accepted_by", "revoked_by", "batch")
    readonly_fields = (
        "token",
        "status_badge",
        "last_sent_at",
        "accepted_at",
        "revoked_at",
        "created_at",
        "updated_at",
    )
    actions = ("revoke_pending_invitations",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("invited_by", "accepted_by", "revoked_by", "batch")
            .prefetch_related("invitation_roles__role_definition")
        )

    def role_summary(self, obj):
        return ", ".join(obj.get_role_names())

    role_summary.short_description = "Roles"

    def status_badge(self, obj):
        color_map = {
            "pending": "#1d4ed8",
            "accepted": "#15803d",
            "expired": "#b45309",
            "revoked": "#b91c1c",
        }
        status_value = obj.status
        color = color_map.get(status_value, "#475569")
        return format_html(
            "<strong style='color: {};'>{}</strong>",
            color,
            status_value.title(),
        )

    status_badge.short_description = "Status"

    @admin.action(description="Revoke selected pending invitations")
    def revoke_pending_invitations(self, request, queryset):
        revoked_count = 0
        for invitation in queryset:
            was_pending = invitation.status == "pending"
            result = revoke_role_invitation(actor=request.user, invitation=invitation)
            if result.get("success") and was_pending:
                revoked_count += 1
        self.message_user(
            request,
            f"Revoked {revoked_count} pending invitations.",
            level=messages.SUCCESS,
        )

    def save_model(self, request, obj, form, change):
        selected_roles = list(form.cleaned_data["roles"])
        primary_role = _select_primary_role_definition(selected_roles)

        if not change:
            created_invitation = create_role_invitation(
                actor=request.user,
                email=form.cleaned_data["email"],
                roles=[role_definition.code for role_definition in selected_roles],
                note=form.cleaned_data.get("note", ""),
                expires_at=form.cleaned_data["expires_at"],
                metadata=form.cleaned_data.get("metadata") or {},
                email_subject=form.cleaned_data.get("email_subject", ""),
                email_body=form.cleaned_data.get("email_body", ""),
                source=AdminRoleInvitation.InvitationSource.ADMIN,
                request=request,
            )
            obj.pk = created_invitation.pk
            obj.__dict__.update(created_invitation.__dict__)
            return

        obj.role = primary_role.code
        obj.source = obj.source or AdminRoleInvitation.InvitationSource.ADMIN
        super().save_model(request, obj, form, change)
        obj.invitation_roles.all().delete()
        AdminRoleInvitationRole.objects.bulk_create(
            [
                AdminRoleInvitationRole(
                    invitation=obj,
                    role_definition=role_definition,
                    is_primary=role_definition.code == primary_role.code,
                    permission_preset=list(role_definition.permission_preset or []),
                )
                for role_definition in selected_roles
            ]
        )


@admin.register(AdminInvitationBatch)
class AdminInvitationBatchAdmin(admin.ModelAdmin):
    """Read-only visibility into bulk invitation uploads."""

    list_display = (
        "name",
        "source_file_name",
        "invited_by",
        "total_rows",
        "successful_rows",
        "failed_rows",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("name", "source_file_name", "invited_by__email")
    readonly_fields = (
        "name",
        "source_file_name",
        "invited_by",
        "total_rows",
        "successful_rows",
        "failed_rows",
        "metadata",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(AdminUserRoleAssignment)
class AdminUserRoleAssignmentAdmin(admin.ModelAdmin):
    """Show applied user-role associations created by invitations."""

    list_display = (
        "user",
        "role_definition",
        "is_primary",
        "assigned_by",
        "assigned_at",
        "revoked_at",
    )
    list_filter = ("is_primary", "role_definition", "revoked_at")
    search_fields = ("user__email", "role_definition__code", "role_definition__name")
    raw_id_fields = ("user", "assigned_by", "invitation")
    readonly_fields = (
        "user",
        "role_definition",
        "invitation",
        "assigned_by",
        "is_primary",
        "permission_preset",
        "metadata",
        "assigned_at",
        "updated_at",
        "revoked_at",
    )

    def has_add_permission(self, request):
        return False
