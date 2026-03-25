"""Forms for admin-managed invitation workflows."""

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from apps.admin_management.models import AdminInvitationRole, AdminRoleInvitation


class AdminRoleInvitationAdminForm(forms.ModelForm):
    """Admin form with searchable multi-role selection."""

    roles = forms.ModelMultipleChoiceField(
        queryset=AdminInvitationRole.objects.filter(
            is_active=True,
            is_assignable=True,
        ).order_by("sort_order", "name"),
        widget=FilteredSelectMultiple("Roles", is_stacked=False),
        required=True,
        help_text="Select one or more roles to include in this invitation.",
    )

    class Meta:
        model = AdminRoleInvitation
        fields = [
            "email",
            "roles",
            "note",
            "expires_at",
            "email_subject",
            "email_body",
            "metadata",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            role_codes = self.instance.get_role_codes()
            self.fields["roles"].initial = AdminInvitationRole.objects.filter(
                code__in=role_codes
            )
