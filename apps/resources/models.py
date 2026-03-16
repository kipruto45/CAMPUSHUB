"""
Models for resources app.
"""

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class PersonalResourceManager(models.Manager):
    """Manager for PersonalResource that excludes trashed files by default."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def all_with_trash(self):
        """Return all resources including trashed ones."""
        return super().get_queryset()

    def trash_only(self):
        """Return only trashed resources."""
        return super().get_queryset().filter(is_deleted=True)


class Resource(TimeStampedModel):
    """Model for learning resources."""

    RESOURCE_TYPE_CHOICES = [
        ("notes", "Notes"),
        ("past_paper", "Past Paper"),
        ("assignment", "Assignment"),
        ("book", "Book"),
        ("slides", "Slides"),
        ("tutorial", "Tutorial"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("flagged", "Flagged"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    resource_type = models.CharField(
        max_length=20, choices=RESOURCE_TYPE_CHOICES, default="notes"
    )
    file = models.FileField(upload_to="resources/%Y/%m/", null=True, blank=True)
    thumbnail = models.ImageField(upload_to="thumbnails/", null=True, blank=True)
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=50, blank=True)
    normalized_filename = models.CharField(max_length=255, blank=True)

    faculty = models.ForeignKey(
        "faculties.Faculty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )
    department = models.ForeignKey(
        "faculties.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )
    unit = models.ForeignKey(
        "courses.Unit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )
    semester = models.CharField(max_length=1, blank=True)
    year_of_study = models.PositiveSmallIntegerField(null=True, blank=True)

    tags = models.CharField(
        max_length=500, blank=True, help_text="Comma-separated tags"
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="uploads"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_public = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False)

    # Approval tracking
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_resources",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Reports tracking
    reports_count = models.PositiveIntegerField(default=0)

    view_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    # OCR and AI fields for future use
    ocr_text = models.TextField(blank=True, help_text="Extracted text from OCR")
    ai_summary = models.TextField(blank=True, help_text="AI-generated summary")

    rejection_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["resource_type", "status"]),
            models.Index(fields=["uploaded_by", "status"]),
            models.Index(fields=["is_pinned", "-created_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = (
                slugify(f"{self.title[:50]}-{self.uploaded_by.id}") or "resource"
            )
            self.slug = base_slug
            if Resource.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{uuid4().hex[:8]}"

        if self.file and not self.file_size:
            self.file_size = self.file.size

        if self.file:
            self.file_type = self.file.name.split(".")[-1].lower()
            from .validators import sanitize_filename

            self.normalized_filename = sanitize_filename(self.file.name)

        super().save(*args, **kwargs)

    def increment_view_count(self):
        """Increment view count."""
        self.view_count += 1
        self.save(update_fields=["view_count"])

    def increment_download_count(self):
        """Increment download count."""
        self.download_count += 1
        self.save(update_fields=["download_count"])

    def increment_share_count(self):
        """Increment share count."""
        self.share_count += 1
        self.save(update_fields=["share_count"])

    def get_tags_list(self):
        """Get tags as a list."""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(",")]
        return []

    def get_file_icon(self):
        """Get file type icon class."""
        icon_map = {
            "pdf": "fas fa-file-pdf",
            "doc": "fas fa-file-word",
            "docx": "fas fa-file-word",
            "ppt": "fas fa-file-powerpoint",
            "pptx": "fas fa-file-powerpoint",
            "xls": "fas fa-file-excel",
            "xlsx": "fas fa-file-excel",
            "jpg": "fas fa-file-image",
            "jpeg": "fas fa-file-image",
            "png": "fas fa-file-image",
            "gif": "fas fa-file-image",
            "zip": "fas fa-file-archive",
            "rar": "fas fa-file-archive",
        }
        return icon_map.get(self.file_type, "fas fa-file")

    def get_absolute_url(self):
        """Get absolute URL for the resource."""
        return f"/resources/{self.slug}/"


class ResourceShareEvent(TimeStampedModel):
    """Track resource sharing events for analytics and recommendations."""

    class ShareMethod(models.TextChoices):
        COPY_LINK = "copy_link", "Copy Link"
        NATIVE_SHARE = "native_share", "Native Share"
        WHATSAPP = "whatsapp", "WhatsApp"
        TELEGRAM = "telegram", "Telegram"
        EMAIL = "email", "Email"
        SEND_TO_STUDENT = "send_to_student", "Send to Student"
        SHARE_TO_GROUP = "share_to_group", "Share to Study Group"
        OTHER = "other", "Other"

    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="share_events"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resource_share_events",
    )
    share_method = models.CharField(
        max_length=20,
        choices=ShareMethod.choices,
        default=ShareMethod.OTHER,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=500, blank=True)
    shared_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Resource Share Event"
        verbose_name_plural = "Resource Share Events"
        ordering = ["-shared_at"]
        indexes = [
            models.Index(fields=["resource", "-shared_at"]),
            models.Index(fields=["share_method", "-shared_at"]),
        ]

    def __str__(self):
        return f"{self.resource.title} - {self.share_method}"


class ResourceFile(TimeStampedModel):
    """Model for multiple file uploads per resource."""

    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="additional_files"
    )
    file = models.FileField(upload_to="resources/%Y/%m/additional/")
    filename = models.CharField(max_length=500)
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Resource File"
        verbose_name_plural = "Resource Files"
        ordering = ["filename"]

    def save(self, *args, **kwargs):
        self.filename = self.file.name
        self.file_size = self.file.size
        self.file_type = self.file.name.split(".")[-1].lower()
        super().save(*args, **kwargs)


class Folder(TimeStampedModel):
    """Model for organizing resources into folders."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="folders"
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, default="#3b82f6")  # Default blue color
    is_pinned = models.BooleanField(default=False)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subfolders",
    )

    class Meta:
        verbose_name = "Folder"
        verbose_name_plural = "Folders"
        ordering = ["-is_pinned", "name"]
        unique_together = ["user", "name", "parent"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.user.id}")
        super().save(*args, **kwargs)


class FolderItem(TimeStampedModel):
    """Model for items in folders."""

    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name="items")
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="folder_items"
    )

    class Meta:
        verbose_name = "Folder Item"
        verbose_name_plural = "Folder Items"
        unique_together = ["folder", "resource"]

    def __str__(self):
        return f"{self.folder.name} - {self.resource.title}"


class UserStorage(TimeStampedModel):
    """Track user storage usage."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="storage"
    )
    used_storage = models.BigIntegerField(default=0)
    storage_limit = models.BigIntegerField(
        default=5 * 1024 * 1024 * 1024
    )  # 5GB default

    class Meta:
        verbose_name = "User Storage"
        verbose_name_plural = "User Storages"

    def __str__(self):
        return (
            f"{self.user.email} - {self.used_storage / (1024 * 1024):.2f}MB / "
            f"{self.storage_limit / (1024 * 1024):.2f}MB"
        )

    def get_usage_percentage(self):
        return (self.used_storage / self.storage_limit) * 100

    def can_upload(self, file_size):
        return (self.used_storage + file_size) <= self.storage_limit


class StorageUpgradeRequest(TimeStampedModel):
    """Request for storage upgrade from a student."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("paid", "Paid"),
    ]

    PLAN_CHOICES = [
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("plus", "Plus"),
    ]

    BILLING_CHOICES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="storage_upgrade_requests",
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)
    billing_cycle = models.CharField(
        max_length=10, choices=BILLING_CHOICES, default="monthly"
    )
    payment_method = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Storage Upgrade Request"
        verbose_name_plural = "Storage Upgrade Requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.plan} ({self.status})"


class PersonalFolder(TimeStampedModel):
    """Model for personal library folders."""

    FOLDER_COLORS = [
        ("#3b82f6", "Blue"),
        ("#10b981", "Green"),
        ("#f59e0b", "Amber"),
        ("#ef4444", "Red"),
        ("#8b5cf6", "Purple"),
        ("#ec4899", "Pink"),
        ("#06b6d4", "Cyan"),
        ("#6b7280", "Gray"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_folders",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, blank=True)
    color = models.CharField(max_length=20, choices=FOLDER_COLORS, default="#3b82f6")
    is_favorite = models.BooleanField(default=False)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subfolders",
    )

    class Meta:
        verbose_name = "Personal Folder"
        verbose_name_plural = "Personal Folders"
        ordering = ["-is_favorite", "name"]
        unique_together = ["user", "name", "parent"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(
                f"{self.name}-{self.user.id}-{timezone.now().timestamp()}"
            )
        super().save(*args, **kwargs)

    def get_breadcrumbs(self):
        """Get folder breadcrumbs path."""
        breadcrumbs = []
        current = self
        while current:
            breadcrumbs.insert(
                0, {"id": str(current.id), "name": current.name, "slug": current.slug}
            )
            current = current.parent
        return breadcrumbs

    def get_file_count(self):
        """Get total number of files in this folder and subfolders."""
        count = self.personal_resources.count()
        for subfolder in self.subfolders.all():
            count += subfolder.get_file_count()
        return count

    def get_total_size(self):
        """Get total size of all files in this folder."""
        total = sum(f.file_size for f in self.personal_resources.all())
        for subfolder in self.subfolders.all():
            total += subfolder.get_total_size()
        return total


class PersonalResource(TimeStampedModel):
    """Model for personal library files."""

    # Use custom manager that excludes trashed files by default
    objects = PersonalResourceManager()
    all_objects = models.Manager()  # Include all objects including trashed

    VISIBILITY_CHOICES = [
        ("private", "Private"),
        ("shared_link", "Shared via Link"),
        ("submitted", "Submitted for Publication"),
    ]

    SOURCE_TYPE_CHOICES = [
        ("uploaded", "Uploaded"),
        ("saved", "Saved from Public"),
        ("imported", "Imported"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_resources",
    )
    folder = models.ForeignKey(
        PersonalFolder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_resources",
    )
    title = models.CharField(max_length=500)
    file = models.FileField(upload_to="personal/%Y/%m/")
    file_type = models.CharField(max_length=50, blank=True)
    file_size = models.BigIntegerField(default=0)
    description = models.TextField(blank=True)
    tags = models.CharField(max_length=500, blank=True)
    visibility = models.CharField(
        max_length=20, choices=VISIBILITY_CHOICES, default="private"
    )
    source_type = models.CharField(
        max_length=20, choices=SOURCE_TYPE_CHOICES, default="uploaded"
    )
    is_favorite = models.BooleanField(default=False)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    # Link to public resource if saved from public
    linked_public_resource = models.ForeignKey(
        Resource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_copies",
    )

    # Soft delete fields for Trash/Recovery Module
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    original_folder = models.ForeignKey(
        PersonalFolder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trashed_resources",
    )

    class Meta:
        verbose_name = "Personal Resource"
        verbose_name_plural = "Personal Resources"
        ordering = ["-last_accessed_at", "-created_at"]

    @property
    def is_in_trash(self):
        """Check if the resource is in trash."""
        return self.is_deleted

    @property
    def can_restore(self):
        """Check if the resource can be restored."""
        return self.is_deleted and self.deleted_at is not None

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.file:
            if not self.file_size:
                self.file_size = self.file.size
            if not self.file_type:
                self.file_type = (
                    self.file.name.split(".")[-1].lower()
                    if "." in self.file.name
                    else ""
                )
        super().save(*args, **kwargs)

    def get_file_icon(self):
        """Get file type icon class."""
        icon_map = {
            "pdf": "fas fa-file-pdf",
            "doc": "fas fa-file-word",
            "docx": "fas fa-file-word",
            "ppt": "fas fa-file-powerpoint",
            "pptx": "fas fa-file-powerpoint",
            "xls": "fas fa-file-excel",
            "xlsx": "fas fa-file-excel",
            "jpg": "fas fa-file-image",
            "jpeg": "fas fa-file-image",
            "png": "fas fa-file-image",
            "gif": "fas fa-file-image",
            "zip": "fas fa-file-archive",
            "rar": "fas fa-file-archive",
            "txt": "fas fa-file-alt",
            "md": "fas fa-file-alt",
        }
        return icon_map.get(self.file_type, "fas fa-file")

    def mark_accessed(self):
        """Update last accessed timestamp."""
        from django.utils import timezone

        self.last_accessed_at = timezone.now()
        self.save(update_fields=["last_accessed_at"])

    def get_tags_list(self):
        """Get tags as a list."""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(",")]
        return []


class ResourceRequest(TimeStampedModel):
    """
    Model for resource requests from students.
    Students can request specific resources they need but cannot find.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resource_requests",
    )
    faculty = models.ForeignKey(
        "faculties.Faculty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resource_requests",
    )
    department = models.ForeignKey(
        "faculties.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resource_requests",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resource_requests",
    )
    year_of_study = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fulfilled_requests",
    )
    fulfilled_resource = models.ForeignKey(
        "Resource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_fulfills",
    )
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    upvotes = models.PositiveIntegerField(default=0)
    requested_by_upvoted = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="upvoted_requests",
        blank=True,
    )

    class Meta:
        app_label = "resources"
        verbose_name = "Resource Request"
        verbose_name_plural = "Resource Requests"
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["requested_by", "-created_at"]),
        ]

    def __str__(self):
        return f"Request: {self.title} by {self.requested_by.email}"

    def upvote(self, user):
        """Upvote this request."""
        if user not in self.requested_by_upvoted.all():
            self.requested_by_upvoted.add(user)
            self.upvotes += 1
            self.save(update_fields=["upvotes"])
            return True
        return False

    def cancel_upvote(self, user):
        """Cancel upvote."""
        if user in self.requested_by_upvoted.all():
            self.requested_by_upvoted.remove(user)
            self.upvotes = max(0, self.upvotes - 1)
            self.save(update_fields=["upvotes"])
            return True
        return False


class ResourceVersion(TimeStampedModel):
    """
    Model for tracking resource version history.
    Stores snapshots of resource changes for audit trail.
    """

    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("archived", "Archived"),
        ("restored", "Restored"),
    ]

    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="resource_changes",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="resource_versions/", null=True, blank=True)
    change_summary = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        app_label = "resources"
        verbose_name = "Resource Version"
        verbose_name_plural = "Resource Versions"
        ordering = ["-version_number"]
        unique_together = ["resource", "version_number"]
        indexes = [
            models.Index(fields=["resource", "-created_at"]),
            models.Index(fields=["changed_by", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.resource.title} v{self.version_number}" 

    @classmethod
    def create_version(cls, resource, action, changed_by=None, change_summary="", request=None):
        """Create a new version snapshot of the resource."""
        from django.utils import timezone
        
        # Get the next version number
        last_version = cls.objects.filter(resource=resource).first()
        next_version = (last_version.version_number + 1) if last_version else 1
        
        # Get client IP if request provided
        ip_address = None
        if request:
            from apps.core.utils import get_client_ip
            ip_address = get_client_ip(request)
        
        return cls.objects.create(
            resource=resource,
            version_number=next_version,
            action=action,
            changed_by=changed_by,
            title=resource.title,
            description=resource.description,
            file=resource.file,
            change_summary=change_summary,
            ip_address=ip_address,
        )


class CourseProgress(TimeStampedModel):
    """
    Track student progress through course resources.
    """
    
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_progress",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="student_progress",
    )
    resource = models.ForeignKey(
        "Resource",
        on_delete=models.CASCADE,
        related_name="student_progress",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="not_started")
    completion_percentage = models.PositiveIntegerField(default=0)
    time_spent_minutes = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        app_label = "resources"
        verbose_name = "Course Progress"
        verbose_name_plural = "Course Progress"
        unique_together = ["user", "course", "resource"]
        indexes = [
            models.Index(fields=["user", "course"]),
            models.Index(fields=["user", "status"]),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.course.name} - {self.resource.title}"
    
    def mark_in_progress(self):
        """Mark resource as in progress."""
        self.status = "in_progress"
        if self.completion_percentage < 50:
            self.completion_percentage = 50
        self.last_accessed = timezone.now()
        self.save(update_fields=["status", "completion_percentage", "last_accessed"])
    
    def mark_completed(self):
        """Mark resource as completed."""
        self.status = "completed"
        self.completion_percentage = 100
        self.completed_at = timezone.now()
        self.last_accessed = timezone.now()
        self.save(update_fields=["status", "completion_percentage", "completed_at", "last_accessed"])
    
    def update_time_spent(self, minutes: int):
        """Update time spent on this resource."""
        self.time_spent_minutes += minutes
        self.last_accessed = timezone.now()
        self.save(update_fields=["time_spent_minutes", "last_accessed"])
