"""
Models for announcements app.
"""

from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class AnnouncementStatus:
    """Announcement status constants."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

    CHOICES = [
        (DRAFT, "Draft"),
        (PUBLISHED, "Published"),
        (ARCHIVED, "Archived"),
    ]


class AnnouncementType:
    """Announcement type constants."""

    GENERAL = "general"
    ACADEMIC = "academic"
    MAINTENANCE = "maintenance"
    URGENT = "urgent"
    COURSE_UPDATE = "course_update"
    SYSTEM_NOTICE = "system_notice"

    CHOICES = [
        (GENERAL, "General"),
        (ACADEMIC, "Academic"),
        (MAINTENANCE, "Maintenance"),
        (URGENT, "Urgent"),
        (COURSE_UPDATE, "Course Update"),
        (SYSTEM_NOTICE, "System Notice"),
    ]


class Announcement(TimeStampedModel):
    """Model for announcements."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    content = models.TextField()
    announcement_type = models.CharField(
        max_length=50,
        choices=AnnouncementType.CHOICES,
        default=AnnouncementType.GENERAL,
    )
    status = models.CharField(
        max_length=20,
        choices=AnnouncementStatus.CHOICES,
        default=AnnouncementStatus.DRAFT,
    )

    # Targeting - optional filters
    target_faculty = models.ForeignKey(
        "faculties.Faculty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    target_department = models.ForeignKey(
        "faculties.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    target_course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )
    target_year_of_study = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Target specific year of study (1-5)"
    )

    is_pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_announcements",
    )

    class Meta:
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ["-is_pinned", "-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["-published_at"]),
            models.Index(fields=["status", "-published_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure unique slug
            original_slug = self.slug
            counter = 1
            while (
                Announcement.objects.filter(slug=self.slug).exclude(pk=self.pk).exists()
            ):
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def is_visible(self):
        """Check if announcement is visible to students."""
        return self.status == AnnouncementStatus.PUBLISHED

    @property
    def target_summary(self):
        """Get human-readable target summary."""
        targets = []
        if self.target_faculty:
            targets.append(self.target_faculty.name)
        if self.target_department:
            targets.append(self.target_department.name)
        if self.target_course:
            targets.append(self.target_course.name)
        if self.target_year_of_study:
            targets.append(f"Year {self.target_year_of_study}")

        return "All Students" if not targets else ", ".join(targets)


class AnnouncementAttachment(TimeStampedModel):
    """File attachment associated with an announcement."""

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="announcements/%Y/%m/")
    filename = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.filename or Path(self.file.name).name

    def save(self, *args, **kwargs):
        if self.file:
            self.filename = Path(self.file.name).name
            self.file_size = int(getattr(self.file, "size", 0) or 0)
            self.file_type = Path(self.file.name).suffix.lstrip(".").lower()
        super().save(*args, **kwargs)
