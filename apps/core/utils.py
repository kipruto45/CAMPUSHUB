"""
Utility functions for CampusHub.
"""

import hashlib
import os
import uuid

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone


def generate_unique_id():
    """Generate a unique ID."""
    return uuid.uuid4().hex


def generate_random_string(length=32):
    """Generate a random string."""
    import secrets

    return secrets.token_urlsafe(length)


def hash_file(file):
    """Generate MD5 hash of a file."""
    md5_hash = hashlib.md5()
    for chunk in file.chunks():
        md5_hash.update(chunk)
    return md5_hash.hexdigest()


def get_file_extension(filename):
    """Get file extension."""
    return os.path.splitext(filename)[1].lower().strip(".")


def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_user_agent(request):
    """Get user agent from request."""
    return request.META.get("HTTP_USER_AGENT", "")


def calculate_average_rating(ratings):
    """Calculate average rating from a list of ratings."""
    if not ratings:
        return 0
    return sum(ratings) / len(ratings)


def send_email(subject, template_name, context, to_email):
    """Send email using template."""
    from apps.core.emails import EmailService

    html_message = render_to_string(template_name, context)
    EmailService.send_email(
        subject=subject,
        message=html_message,
        recipient_list=[to_email],
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        fail_silently=False,
    )


def get_time_ago(dt):
    """Get human-readable time ago string."""
    now = timezone.now()
    diff = now - dt

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"


def is_valid_uuid(value):
    """Check if value is a valid UUID."""
    import uuid

    try:
        uuid.UUID(value)
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def clean_html(text):
    """Remove HTML tags from text."""
    from django.utils.html import strip_tags

    return strip_tags(text)


def truncate_text(text, length=100, suffix="..."):
    """Truncate text to specified length."""
    if len(text) <= length:
        return text
    return text[:length].rstrip(" ") + suffix


def get_resource_types():
    """Get available resource types."""
    return [
        {"value": "notes", "label": "Notes"},
        {"value": "past_paper", "label": "Past Paper"},
        {"value": "assignment", "label": "Assignment"},
        {"value": "book", "label": "Book"},
        {"value": "slides", "label": "Slides"},
        {"value": "tutorial", "label": "Tutorial"},
        {"value": "other", "label": "Other"},
    ]


def get_resource_statuses():
    """Get available resource statuses."""
    return [
        {"value": "pending", "label": "Pending"},
        {"value": "approved", "label": "Approved"},
        {"value": "rejected", "label": "Rejected"},
    ]


def get_notification_types():
    """Get available notification types."""
    return [
        {"value": "resource_approved", "label": "Resource Approved"},
        {"value": "resource_rejected", "label": "Resource Rejected"},
        {"value": "new_comment", "label": "New Comment"},
        {"value": "new_rating", "label": "New Rating"},
        {"value": "new_download", "label": "New Download"},
        {"value": "trending", "label": "Trending Resource"},
        {"value": "system", "label": "System Notification"},
    ]


def get_user_roles():
    """Get available user roles."""
    return [
        {"value": "STUDENT", "label": "Student"},
        {"value": "MODERATOR", "label": "Moderator"},
        {"value": "ADMIN", "label": "Admin"},
    ]


def generate_slug(title, model_class, pk=None):
    """Generate a unique slug from title."""
    from django.utils.text import slugify

    slug = slugify(title)
    original_slug = slug
    counter = 1

    while True:
        queryset = model_class.objects.filter(slug=slug)
        if pk:
            queryset = queryset.exclude(pk=pk)
        if not queryset.exists():
            return slug
        slug = f"{original_slug}-{counter}"
        counter += 1
