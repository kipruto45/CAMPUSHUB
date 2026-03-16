"""
Models for courses app.
"""

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Course(TimeStampedModel):
    """Model for Course."""

    department = models.ForeignKey(
        "faculties.Department", on_delete=models.CASCADE, related_name="courses"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    duration_years = models.PositiveSmallIntegerField(default=4)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Course"
        verbose_name_plural = "Courses"
        ordering = ["name"]
        unique_together = ["department", "code"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.department.faculty.code}-{self.code}")
        super().save(*args, **kwargs)


class Unit(TimeStampedModel):
    """Model for Unit/Subject."""

    SEMESTER_CHOICES = [
        ("1", "Semester 1"),
        ("2", "Semester 2"),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="units")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    semester = models.CharField(max_length=1, choices=SEMESTER_CHOICES, default="1")
    year_of_study = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Unit"
        verbose_name_plural = "Units"
        ordering = ["year_of_study", "semester", "code"]
        unique_together = ["course", "code", "semester"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.course.code}-{self.code}-s{self.semester}")
        super().save(*args, **kwargs)
