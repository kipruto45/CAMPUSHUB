# Generated manually for admin_management initial schema.

import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminRoleInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("role", models.CharField(choices=[("STUDENT", "Student"), ("MODERATOR", "Moderator"), ("ADMIN", "Admin")], max_length=20)),
                ("note", models.TextField(blank=True)),
                ("token", models.CharField(blank=True, db_index=True, max_length=255, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "accepted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="admin_role_invitations_accepted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="admin_role_invitations_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "admin_role_invitations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CalendarCategory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("color", models.CharField(max_length=7)),
                ("icon", models.CharField(blank=True, max_length=50)),
                ("event_types", models.JSONField(default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "Calendar Categories",
                "db_table": "admin_calendar_categories",
            },
        ),
        migrations.CreateModel(
            name="CalendarTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("event_type", models.CharField(choices=[("announcement", "Announcement"), ("post", "Social Post"), ("email", "Email Campaign"), ("notification", "Push Notification"), ("promotion", "Promotion"), ("maintenance", "Maintenance"), ("event", "Event")], max_length=20)),
                ("default_duration_hours", models.IntegerField(default=1)),
                ("default_color", models.CharField(default="#3B82F6", max_length=7)),
                ("default_target", models.JSONField(default=dict)),
                ("title_template", models.CharField(max_length=255)),
                ("description_template", models.TextField(blank=True)),
                ("recurrence_pattern", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(null=True, on_delete=models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "db_table": "admin_calendar_templates",
            },
        ),
        migrations.CreateModel(
            name="ContentCalendarEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("event_type", models.CharField(choices=[("announcement", "Announcement"), ("post", "Social Post"), ("email", "Email Campaign"), ("notification", "Push Notification"), ("promotion", "Promotion"), ("maintenance", "Maintenance"), ("event", "Event")], max_length=20)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("scheduled", "Scheduled"), ("published", "Published"), ("cancelled", "Cancelled"), ("completed", "Completed")], default="draft", max_length=20)),
                ("start_datetime", models.DateTimeField()),
                ("end_datetime", models.DateTimeField(blank=True, null=True)),
                ("timezone", models.CharField(default="UTC", max_length=50)),
                ("is_all_day", models.BooleanField(default=False)),
                ("related_object_type", models.CharField(blank=True, max_length=50)),
                ("related_object_id", models.UUIDField(blank=True, null=True)),
                ("target_faculty_id", models.UUIDField(blank=True, null=True)),
                ("target_department_id", models.UUIDField(blank=True, null=True)),
                ("target_year_level", models.IntegerField(blank=True, null=True)),
                ("is_global", models.BooleanField(default=True)),
                ("recurrence_rule", models.CharField(blank=True, max_length=255)),
                ("color", models.CharField(default="#3B82F6", max_length=7)),
                ("icon", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="calendar_events_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "published_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="calendar_events_published",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "admin_content_calendar",
                "ordering": ["start_datetime"],
            },
        ),
        migrations.AddIndex(
            model_name="adminroleinvitation",
            index=models.Index(fields=["email", "created_at"], name="admin_role__email_50d905_idx"),
        ),
        migrations.AddIndex(
            model_name="adminroleinvitation",
            index=models.Index(fields=["role", "created_at"], name="admin_role__role_2a9013_idx"),
        ),
        migrations.AddIndex(
            model_name="adminroleinvitation",
            index=models.Index(fields=["expires_at"], name="admin_role__expire_ee40be_idx"),
        ),
        migrations.AddIndex(
            model_name="contentcalendarevent",
            index=models.Index(fields=["start_datetime"], name="admin_conte_start_d7f14f_idx"),
        ),
        migrations.AddIndex(
            model_name="contentcalendarevent",
            index=models.Index(fields=["event_type"], name="admin_conte_event_t_6f5afd_idx"),
        ),
        migrations.AddIndex(
            model_name="contentcalendarevent",
            index=models.Index(fields=["status"], name="admin_conte_status_0708f6_idx"),
        ),
    ]
