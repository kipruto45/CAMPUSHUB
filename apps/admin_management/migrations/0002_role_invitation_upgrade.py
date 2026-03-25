# Generated manually for expanded role invitation support.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


ROLE_FIXTURES = [
    {
        "code": "STUDENT",
        "name": "Student",
        "description": "Default learner access for the CampusHub student experience.",
        "sort_order": 10,
        "requires_superuser": False,
        "inviter_permissions": [],
        "permission_preset": ["resources.view_resource"],
        "email_subject_template": "CampusHub invitation for {primary_role_name}",
        "email_body_template": (
            "Hello,\n\n"
            "You've been invited to join CampusHub with the following roles: {role_names_csv}.\n\n"
            "Invited by: {invited_by_name}\n"
            "Invitation email: {invitee_email}\n"
            "{note_block}"
            "Accept invitation: {accept_url}\n"
            "{app_url_block}"
            "This invitation expires on {expires_at}.\n"
        ),
        "metadata": {"audience": "student"},
    },
    {
        "code": "INSTRUCTOR",
        "name": "Instructor",
        "description": "Teaching staff who publish learning content and course updates.",
        "sort_order": 20,
        "requires_superuser": False,
        "inviter_permissions": [],
        "permission_preset": [
            "resources.add_resource",
            "resources.change_resource",
            "announcements.add_announcement",
            "announcements.change_announcement",
        ],
        "email_subject_template": "CampusHub invitation for {primary_role_name}",
        "email_body_template": (
            "Hello,\n\n"
            "CampusHub is ready for you as {primary_role_name}. Your invitation includes: {role_names_csv}.\n\n"
            "Invited by: {invited_by_name}\n"
            "{note_block}"
            "Accept invitation: {accept_url}\n"
            "{app_url_block}"
            "This invitation expires on {expires_at}.\n"
        ),
        "metadata": {"audience": "academic_staff"},
    },
    {
        "code": "DEPARTMENT_HEAD",
        "name": "Department Head",
        "description": "Department leadership with broader oversight for academic operations.",
        "sort_order": 30,
        "requires_superuser": False,
        "inviter_permissions": ["admin_management.can_invite_department_head_role"],
        "permission_preset": [
            "resources.add_resource",
            "resources.change_resource",
            "reports.view_report",
            "announcements.add_announcement",
            "announcements.change_announcement",
            "courses.view_course",
            "courses.change_course",
        ],
        "email_subject_template": "CampusHub invitation for {primary_role_name}",
        "email_body_template": (
            "Hello,\n\n"
            "You have been invited into CampusHub leadership access with the following roles: {role_names_csv}.\n\n"
            "Invited by: {invited_by_name}\n"
            "{note_block}"
            "Accept invitation: {accept_url}\n"
            "{app_url_block}"
            "This invitation expires on {expires_at}.\n"
        ),
        "metadata": {"audience": "academic_leadership"},
    },
    {
        "code": "SUPPORT_STAFF",
        "name": "Support Staff",
        "description": "Operational staff handling user support and admin assistance.",
        "sort_order": 40,
        "requires_superuser": False,
        "inviter_permissions": [],
        "permission_preset": [
            "accounts.view_user",
            "resources.view_resource",
            "reports.view_report",
        ],
        "email_subject_template": "CampusHub invitation for {primary_role_name}",
        "email_body_template": (
            "Hello,\n\n"
            "You've been invited to support CampusHub operations with these roles: {role_names_csv}.\n\n"
            "Invited by: {invited_by_name}\n"
            "{note_block}"
            "Accept invitation: {accept_url}\n"
            "{app_url_block}"
            "This invitation expires on {expires_at}.\n"
        ),
        "metadata": {"audience": "operations"},
    },
    {
        "code": "MODERATOR",
        "name": "Moderator",
        "description": "Moderation access for content review and community oversight.",
        "sort_order": 50,
        "requires_superuser": False,
        "inviter_permissions": [],
        "permission_preset": [
            "resources.change_resource",
            "resources.view_resource",
            "reports.change_report",
        ],
        "email_subject_template": "CampusHub invitation for {primary_role_name}",
        "email_body_template": (
            "Hello,\n\n"
            "You've been invited to moderate CampusHub with the following roles: {role_names_csv}.\n\n"
            "Invited by: {invited_by_name}\n"
            "{note_block}"
            "Accept invitation: {accept_url}\n"
            "{app_url_block}"
            "This invitation expires on {expires_at}.\n"
        ),
        "metadata": {"audience": "moderation"},
    },
    {
        "code": "ADMIN",
        "name": "Admin",
        "description": "Full platform administration for CampusHub operators.",
        "sort_order": 60,
        "requires_superuser": True,
        "inviter_permissions": ["admin_management.can_invite_admin_role"],
        "permission_preset": [
            "accounts.add_user",
            "accounts.change_user",
            "resources.change_resource",
            "reports.change_report",
            "announcements.change_announcement",
        ],
        "email_subject_template": "CampusHub invitation for {primary_role_name}",
        "email_body_template": (
            "Hello,\n\n"
            "You've been invited into CampusHub administration with the following roles: {role_names_csv}.\n\n"
            "Invited by: {invited_by_name}\n"
            "{note_block}"
            "Accept invitation: {accept_url}\n"
            "{app_url_block}"
            "This invitation expires on {expires_at}.\n"
        ),
        "metadata": {"audience": "administration"},
    },
]


def seed_role_invitation_catalog(apps, schema_editor):
    AdminInvitationRole = apps.get_model("admin_management", "AdminInvitationRole")
    AdminRoleInvitation = apps.get_model("admin_management", "AdminRoleInvitation")
    AdminRoleInvitationRole = apps.get_model("admin_management", "AdminRoleInvitationRole")
    AdminUserRoleAssignment = apps.get_model("admin_management", "AdminUserRoleAssignment")

    auth_app_label, auth_model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(auth_app_label, auth_model_name)

    role_map = {}
    for role_data in ROLE_FIXTURES:
        role, _ = AdminInvitationRole.objects.update_or_create(
            code=role_data["code"],
            defaults=role_data,
        )
        role_map[role.code] = role

    for invitation in AdminRoleInvitation.objects.all():
        role_definition = role_map.get(str(invitation.role or "").upper())
        if not role_definition:
            continue
        AdminRoleInvitationRole.objects.update_or_create(
            invitation=invitation,
            role_definition=role_definition,
            defaults={
                "is_primary": True,
                "permission_preset": list(role_definition.permission_preset or []),
                "metadata": {"backfilled": True},
            },
        )

    for user in User.objects.all():
        role_definition = role_map.get(str(getattr(user, "role", "") or "").upper())
        if not role_definition:
            continue
        AdminUserRoleAssignment.objects.update_or_create(
            user=user,
            role_definition=role_definition,
            defaults={
                "is_primary": True,
                "permission_preset": list(role_definition.permission_preset or []),
                "metadata": {"backfilled": True},
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("admin_management", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminInvitationBatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, max_length=255)),
                ("source_file_name", models.CharField(blank=True, max_length=255)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("successful_rows", models.PositiveIntegerField(default=0)),
                ("failed_rows", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admin_invitation_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "admin_invitation_batches",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AdminInvitationRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "code",
                    models.CharField(
                        choices=[
                            ("STUDENT", "Student"),
                            ("INSTRUCTOR", "Instructor"),
                            ("DEPARTMENT_HEAD", "Department Head"),
                            ("SUPPORT_STAFF", "Support Staff"),
                            ("MODERATOR", "Moderator"),
                            ("ADMIN", "Admin"),
                        ],
                        max_length=20,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_assignable", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=100)),
                ("requires_superuser", models.BooleanField(default=False)),
                ("inviter_permissions", models.JSONField(blank=True, default=list)),
                ("permission_preset", models.JSONField(blank=True, default=list)),
                ("email_subject_template", models.CharField(blank=True, max_length=255)),
                ("email_body_template", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "admin_invitation_roles",
                "ordering": ["sort_order", "name"],
                "permissions": (
                    ("can_invite_admin_role", "Can invite users with the Admin role"),
                    (
                        "can_invite_department_head_role",
                        "Can invite users with the Department Head role",
                    ),
                ),
            },
        ),
        migrations.AddField(
            model_name="adminroleinvitation",
            name="accepted_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="adminroleinvitation",
            name="batch",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invitations",
                to="admin_management.admininvitationbatch",
            ),
        ),
        migrations.AddField(
            model_name="adminroleinvitation",
            name="email_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="adminroleinvitation",
            name="email_subject",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="adminroleinvitation",
            name="last_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="adminroleinvitation",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="adminroleinvitation",
            name="revoked_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="admin_role_invitations_revoked",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="adminroleinvitation",
            name="source",
            field=models.CharField(
                choices=[("api", "API"), ("admin", "Admin"), ("csv", "CSV Upload")],
                default="api",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="AdminRoleInvitationRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_primary", models.BooleanField(default=False)),
                ("permission_preset", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "invitation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitation_roles",
                        to="admin_management.adminroleinvitation",
                    ),
                ),
                (
                    "role_definition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invitation_assignments",
                        to="admin_management.admininvitationrole",
                    ),
                ),
            ],
            options={
                "db_table": "admin_role_invitation_roles",
                "ordering": ["-is_primary", "role_definition__sort_order", "role_definition__name"],
            },
        ),
        migrations.CreateModel(
            name="AdminUserRoleAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_primary", models.BooleanField(default=False)),
                ("permission_preset", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="granted_role_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "invitation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="user_role_assignments",
                        to="admin_management.adminroleinvitation",
                    ),
                ),
                (
                    "role_definition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_assignments",
                        to="admin_management.admininvitationrole",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "admin_user_role_assignments",
                "ordering": ["-is_primary", "role_definition__sort_order", "role_definition__name"],
            },
        ),
        migrations.AddIndex(
            model_name="admininvitationbatch",
            index=models.Index(fields=["created_at"], name="admin_invit_created_7b4ce3_idx"),
        ),
        migrations.AddIndex(
            model_name="admininvitationrole",
            index=models.Index(fields=["code"], name="admin_invit_code_5ae11f_idx"),
        ),
        migrations.AddIndex(
            model_name="admininvitationrole",
            index=models.Index(fields=["is_active", "is_assignable"], name="admin_invit_is_act_4370c3_idx"),
        ),
        migrations.AddIndex(
            model_name="adminroleinvitation",
            index=models.Index(fields=["source", "created_at"], name="admin_role__source_36245f_idx"),
        ),
        migrations.AddConstraint(
            model_name="adminroleinvitationrole",
            constraint=models.UniqueConstraint(fields=("invitation", "role_definition"), name="admin_role_invitation_unique_role"),
        ),
        migrations.AddConstraint(
            model_name="adminuserroleassignment",
            constraint=models.UniqueConstraint(fields=("user", "role_definition"), name="admin_user_unique_role_assignment"),
        ),
        migrations.AddIndex(
            model_name="adminuserroleassignment",
            index=models.Index(fields=["user", "revoked_at"], name="admin_user__user_id_0bdb0f_idx"),
        ),
        migrations.RunPython(seed_role_invitation_catalog, migrations.RunPython.noop),
    ]
