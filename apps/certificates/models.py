"""
Models for certificates app.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class CertificateType(TimeStampedModel):
    """
    Model for defining different types of certificates.
    """

    TYPE_CHOICES = [
        ("course_completion", "Course Completion"),
        ("achievement", "Achievement"),
        ("milestone", "Milestone"),
        ("custom", "Custom"),
    ]

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="custom")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    requires_verification = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Certificate Type"
        verbose_name_plural = "Certificate Types"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class CertificateTemplate(TimeStampedModel):
    """
    Model for customizable certificate templates.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    certificate_type = models.ForeignKey(
        CertificateType,
        on_delete=models.CASCADE,
        related_name="templates",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    header_image = models.ImageField(upload_to="certificates/templates/", blank=True)
    footer_text = models.CharField(max_length=500, blank=True)
    background_color = models.CharField(max_length=20, default="#FFFFFF")
    border_color = models.CharField(max_length=20, default="#000000")
    text_color = models.CharField(max_length=20, default="#000000")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Certificate Template"
        verbose_name_plural = "Certificate Templates"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.certificate_type.name})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Certificate(TimeStampedModel):
    """
    Model for certificates issued to users.
    """

    STATUS_CHOICES = [
        ("issued", "Issued"),
        ("revoked", "Revoked"),
        ("expired", "Expired"),
    ]

    # Unique identifier for the certificate
    unique_id = models.CharField(max_length=50, unique=True, editable=False)

    # User who received the certificate
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates",
    )

    # Certificate type and template
    certificate_type = models.ForeignKey(
        CertificateType,
        on_delete=models.PROTECT,
        related_name="certificates",
    )
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )

    # Certificate details
    title = models.CharField(max_length=255)
    recipient_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Related entity (course, achievement, etc.)
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    achievement = models.ForeignKey(
        "gamification.Achievement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )

    # Issuing authority
    issuing_authority = models.CharField(max_length=255, default="CampusHub")
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_certificates",
    )

    # Dates
    issue_date = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="issued"
    )

    # Verification
    verification_url = models.URLField(max_length=500, blank=True)
    qr_code = models.ImageField(upload_to="certificates/qr/", blank=True)
    pdf_file = models.FileField(upload_to="certificates/pdfs/", blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Certificate"
        verbose_name_plural = "Certificates"
        ordering = ["-issue_date"]
        indexes = [
            models.Index(fields=["user", "-issue_date"]),
            models.Index(fields=["status", "-issue_date"]),
            models.Index(fields=["unique_id"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient_name}"

    def save(self, *args, **kwargs):
        if not self.unique_id:
            self.unique_id = self._generate_unique_id()
        if not self.verification_url:
            self.verification_url = self._generate_verification_url()
        super().save(*args, **kwargs)

    def _generate_unique_id(self):
        """Generate a unique certificate ID."""
        timestamp = timezone.now().strftime("%Y%m%d")
        random_part = uuid.uuid4().hex[:8].upper()
        return f"CERT-{timestamp}-{random_part}"

    def _generate_verification_url(self):
        """Generate the verification URL for the certificate."""
        base_url = getattr(settings, "BASE_URL", "https://campushub.example.com")
        return f"{base_url}/api/certificates/verify/{self.unique_id}/"

    def is_valid(self):
        """Check if the certificate is valid."""
        if self.status != "issued":
            return False
        if self.expiry_date and self.expiry_date < timezone.now():
            self.status = "expired"
            self.save()
            return False
        return True

    def revoke(self):
        """Revoke the certificate."""
        self.status = "revoked"
        self.save()

    def get_verification_data(self):
        """Get data for QR code generation."""
        return {
            "unique_id": self.unique_id,
            "title": self.title,
            "recipient_name": self.recipient_name,
            "issue_date": self.issue_date.isoformat(),
            "verification_url": self.verification_url,
        }
