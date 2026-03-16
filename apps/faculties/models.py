"""
Models for faculties app.
"""

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Faculty(TimeStampedModel):
    """Model for Faculty."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Faculty"
        verbose_name_plural = "Faculties"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.code)
        super().save(*args, **kwargs)


class Department(TimeStampedModel):
    """Model for Department."""

    faculty = models.ForeignKey(
        Faculty, on_delete=models.CASCADE, related_name="departments"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["name"]
        unique_together = ["faculty", "code"]

    def __str__(self):
        return f"{self.name} ({self.faculty.code})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.faculty.code}-{self.code}")
        super().save(*args, **kwargs)
