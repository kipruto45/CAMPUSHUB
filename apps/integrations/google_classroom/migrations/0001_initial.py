import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleClassroomAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("google_user_id", models.CharField(max_length=255, unique=True)),
                ("email", models.EmailField(max_length=255)),
                ("access_token", models.TextField()),
                ("refresh_token", models.TextField()),
                ("token_expires_at", models.DateTimeField()),
                (
                    "sync_status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("syncing", "Syncing"),
                            ("error", "Error"),
                            ("disconnected", "Disconnected"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("last_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="google_classroom_account",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Google Classroom Account",
                "verbose_name_plural": "Google Classroom Accounts",
            },
        ),
        migrations.CreateModel(
            name="SyncState",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sync_type",
                    models.CharField(
                        choices=[
                            ("full", "Full Sync"),
                            ("incremental", "Incremental Sync"),
                            ("manual", "Manual Sync"),
                            ("scheduled", "Scheduled Sync"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "result",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("partial", "Partial"),
                        ],
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("courses_count", models.PositiveIntegerField(default=0)),
                ("assignments_count", models.PositiveIntegerField(default=0)),
                ("announcements_count", models.PositiveIntegerField(default=0)),
                ("submissions_count", models.PositiveIntegerField(default=0)),
                ("errors", models.TextField(blank=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="sync_history",
                        to="google_classroom.googleclassroomaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "Sync State",
                "verbose_name_plural": "Sync States",
                "ordering": ["-started_at"],
            },
        ),
        migrations.CreateModel(
            name="SyncedCourse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("google_course_id", models.CharField(max_length=255, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("section", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("room", models.CharField(blank=True, max_length=255)),
                ("owner_id", models.CharField(blank=True, max_length=255)),
                ("enrollment_code", models.CharField(blank=True, max_length=255)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="synced_courses",
                        to="google_classroom.googleclassroomaccount",
                    ),
                ),
                (
                    "linked_unit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="google_classroom_links",
                        to="courses.unit",
                    ),
                ),
            ],
            options={
                "verbose_name": "Synced Course",
                "verbose_name_plural": "Synced Courses",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="SyncedAnnouncement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("google_announcement_id", models.CharField(max_length=255, unique=True)),
                ("text", models.TextField()),
                ("state", models.CharField(default="published", max_length=20)),
                ("scheduled_date", models.DateTimeField(blank=True, null=True)),
                ("alternate_link", models.URLField(blank=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "synced_course",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="synced_announcements",
                        to="google_classroom.syncedcourse",
                    ),
                ),
            ],
            options={
                "verbose_name": "Synced Announcement",
                "verbose_name_plural": "Synced Announcements",
                "ordering": ["-scheduled_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SyncedAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("google_assignment_id", models.CharField(max_length=255, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("published", "Published"),
                            ("deleted", "Deleted"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("due_date", models.DateTimeField(blank=True, null=True)),
                ("max_points", models.FloatField(blank=True, null=True)),
                ("work_type", models.CharField(blank=True, max_length=50)),
                ("alternate_link", models.URLField(blank=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "synced_course",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="synced_assignments",
                        to="google_classroom.syncedcourse",
                    ),
                ),
            ],
            options={
                "verbose_name": "Synced Assignment",
                "verbose_name_plural": "Synced Assignments",
                "ordering": ["-due_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SyncedSubmission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("google_submission_id", models.CharField(max_length=255, unique=True)),
                ("student_email", models.EmailField(max_length=254)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("turned_in", "Turned In"),
                            ("returned", "Returned"),
                            ("reclaimed_by_student", "Reclaimed by Student"),
                            ("missing", "Missing"),
                        ],
                        default="created",
                        max_length=30,
                    ),
                ),
                ("assigned_grade", models.FloatField(blank=True, null=True)),
                ("draft_grade", models.FloatField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                (
                    "synced_assignment",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="synced_submissions",
                        to="google_classroom.syncedassignment",
                    ),
                ),
            ],
            options={
                "verbose_name": "Synced Submission",
                "verbose_name_plural": "Synced Submissions",
                "unique_together": {("synced_assignment", "student_email")},
            },
        ),
    ]
