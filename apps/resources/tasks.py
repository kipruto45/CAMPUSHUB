"""
Celery tasks for resources app.
"""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def update_trending_resources():
    """Update trending resources."""
    from .automations import get_trending_resources

    trending = get_trending_resources(limit=50)
    return f"Updated trending resources: {len(trending)}"


@shared_task
def cleanup_old_resources():
    """Clean up old or orphaned resources."""
    from .models import Resource

    now = timezone.now()
    pending_cutoff = now - timedelta(days=30)
    rejected_cutoff = now - timedelta(days=180)

    orphaned_pending = Resource.objects.filter(
        status="pending",
        file__in=["", None],
        created_at__lt=pending_cutoff,
    )
    rejected_old = Resource.objects.filter(
        status="rejected",
        updated_at__lt=rejected_cutoff,
    )

    orphaned_count = orphaned_pending.count()
    rejected_count = rejected_old.count()
    orphaned_pending.delete()
    rejected_old.delete()
    return (
        f"Cleaned resources: orphaned_pending={orphaned_count}, "
        f"old_rejected={rejected_count}"
    )


@shared_task
def process_ocr(resource_id):
    """Process resource file for OCR."""
    from .models import Resource
    from .services import OCRService

    try:
        resource = Resource.objects.get(id=resource_id)
        if resource.file:
            text = OCRService.extract_text_from_pdf(resource.file)
            resource.ocr_text = text
            resource.save(update_fields=["ocr_text"])
        return f"OCR processed for resource: {resource_id}"
    except Resource.DoesNotExist:
        return f"Resource not found: {resource_id}"


@shared_task
def generate_ai_summary(resource_id):
    """Generate AI summary for resource."""
    from .models import Resource
    from .services import AIService

    try:
        resource = Resource.objects.get(id=resource_id)
        if resource.description or resource.ocr_text:
            text = resource.description or resource.ocr_text
            summary = AIService.generate_summary(text)
            resource.ai_summary = summary
            resource.save(update_fields=["ai_summary"])
        return f"AI summary generated for resource: {resource_id}"
    except Resource.DoesNotExist:
        return f"Resource not found: {resource_id}"


@shared_task
def suggest_tags(resource_id):
    """Generate smart tag suggestions for resource."""
    from .automations import suggest_tags as automation_suggest_tags
    from .models import Resource

    try:
        resource = Resource.objects.get(id=resource_id)
        suggestions = automation_suggest_tags(
            resource.title, resource.description, resource.resource_type
        )
        if not resource.tags and suggestions:
            resource.tags = ", ".join(suggestions)
            resource.save(update_fields=["tags"])
        return {"resource_id": resource_id, "suggestions": suggestions}
    except Resource.DoesNotExist:
        return f"Resource not found: {resource_id}"


@shared_task
def check_duplicates(resource_id):
    """Check for duplicate resources."""
    from .automations import detect_duplicate_file
    from .models import Resource

    try:
        resource = Resource.objects.get(id=resource_id)
        duplicate = detect_duplicate_file(
            user=resource.uploaded_by,
            file_name=resource.normalized_filename or resource.file.name,
            title=resource.title,
        )
        duplicates = [duplicate] if duplicate and duplicate.id != resource.id else []
        return {
            "resource_id": resource_id,
            "duplicates_count": len(duplicates),
            "duplicates": [d.id for d in duplicates],
        }
    except Resource.DoesNotExist:
        return f"Resource not found: {resource_id}"


@shared_task
def process_new_resource(resource_id):
    """Process new resource with OCR and AI."""
    # Process OCR
    process_ocr(resource_id)
    # Generate AI summary
    generate_ai_summary(resource_id)
    # Suggest tags
    suggest_tags(resource_id)

    return f"New resource processed: {resource_id}"
