# Generated initial migration for notifications app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("resources", "__first__"),
        ("comments", "__first__"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=200)),
                ("message", models.TextField()),
                (
                    "notification_type",
                    models.CharField(
                        choices=[
                            ("resource_approved", "Resource Approved"),
                            ("resource_rejected", "Resource Rejected"),
                            ("new_comment", "New Comment"),
                            ("comment_reply", "Comment Reply"),
                            ("new_rating", "New Rating"),
                            ("new_download", "New Download"),
                            ("trending", "Trending Resource"),
                            ("announcement", "Announcement"),
                            ("report_update", "Report Update"),
                            ("system", "System Notification"),
                        ],
                        default="system",
                        max_length=50,
                    ),
                ),
                ("is_read", models.BooleanField(default=False)),
                ("link", models.CharField(blank=True, max_length=500)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "target_comment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notifications",
                        to="comments.comment",
                    ),
                ),
                (
                    "target_resource",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notifications",
                        to="resources.resource",
                    ),
                ),
            ],
            options={
                "verbose_name": "Notification",
                "verbose_name_plural": "Notifications",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="DeviceToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("device_token", models.CharField(max_length=500, unique=True)),
                (
                    "device_type",
                    models.CharField(
                        choices=[
                            ("android", "Android"),
                            ("ios", "iOS"),
                            ("web", "Web"),
                        ],
                        default="android",
                        max_length=20,
                    ),
                ),
                ("device_name", models.CharField(blank=True, max_length=100)),
                ("device_model", models.CharField(blank=True, max_length=100)),
                ("app_version", models.CharField(blank=True, max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("last_used", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="device_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Device Token",
                "verbose_name_plural": "Device Tokens",
                "ordering": ["-last_used"],
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["-created_at"], name="notificatio_created_4b4c8e_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "is_read", "-created_at"],
                name="notificatio_recipie_5d7e9f_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="devicetoken",
            index=models.Index(
                fields=["user", "is_active"], name="notificatio_user_id_7c8e5d_fk"
            ),
        ),
        migrations.AddIndex(
            model_name="devicetoken",
            index=models.Index(
                fields=["device_token"], name="notificatio_device_4f0c8e_idx"
            ),
        ),
    ]
