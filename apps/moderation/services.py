"""Services for moderation workflows and automations."""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.comments.models import Comment
from apps.notifications.services import NotificationService
from apps.reports.models import Report
from apps.resources.models import Resource

from .models import AdminActivityLog, ModerationLog


class ModerationService:
    """Central moderation workflow service."""

    SEVERE_REPORT_REASONS = {"copyright", "abusive", "spam"}
    AUTO_FLAG_REPORT_THRESHOLD = 3

    @staticmethod
    def get_moderation_team():
        """Return admins and moderators with robust role matching."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.filter(
            Q(role__iexact="admin") | Q(role__iexact="moderator") | Q(is_superuser=True)
        ).distinct()

    @staticmethod
    def notify_moderation_team(*, title: str, message: str, link: str = ""):
        """Notify all moderators/admins."""
        for moderator in ModerationService.get_moderation_team():
            NotificationService.create_notification(
                recipient=moderator,
                title=title,
                message=message,
                notification_type="system",
                link=link,
            )
        from apps.notifications.websocket import WebSocketNotificationService

        WebSocketNotificationService.send_global_notification(
            title=title,
            message=message,
            priority="high",
        )

    @staticmethod
    def create_moderation_log(
        *,
        reviewer,
        action: str,
        reason: str = "",
        resource: Resource | None = None,
        comment: Comment | None = None,
    ):
        """Create moderation audit entries for resources and comments."""
        if not resource and comment:
            resource = comment.resource
        return ModerationLog.objects.create(
            resource=resource,
            comment=comment,
            reviewed_by=reviewer,
            action=action,
            reason=reason,
        )

    @staticmethod
    @transaction.atomic
    def approve_resource(*, resource: Resource, reviewer, reason: str = "") -> Resource:
        """Approve resource and execute all side effects."""
        resource.status = "approved"
        resource.rejection_reason = ""
        resource.approved_by = reviewer
        resource.approved_at = timezone.now()
        resource.is_public = True
        resource.save(
            update_fields=[
                "status",
                "rejection_reason",
                "approved_by",
                "approved_at",
                "is_public",
                "updated_at",
            ]
        )

        ModerationService.create_moderation_log(
            resource=resource,
            reviewer=reviewer,
            action="approved",
            reason=reason,
        )
        ModerationService.log_admin_activity(
            admin=reviewer,
            action="resource_approved",
            target_type="resource",
            target_id=str(resource.id),
            target_title=resource.title,
            metadata={"reason": reason} if reason else {},
        )
        NotificationService.notify_resource_approved(resource)
        
        # Notify interested users about the new resource
        try:
            NotificationService.notify_new_resource_available(resource)
        except Exception:
            pass  # Don't fail if notification fails
        
        return resource

    @staticmethod
    @transaction.atomic
    def reject_resource(*, resource: Resource, reviewer, reason: str) -> Resource:
        """Reject resource and execute all side effects."""
        resource.status = "rejected"
        resource.rejection_reason = reason
        resource.approved_by = None
        resource.approved_at = None
        resource.save(
            update_fields=[
                "status",
                "rejection_reason",
                "approved_by",
                "approved_at",
                "updated_at",
            ]
        )

        ModerationService.create_moderation_log(
            resource=resource,
            reviewer=reviewer,
            action="rejected",
            reason=reason,
        )
        ModerationService.log_admin_activity(
            admin=reviewer,
            action="resource_rejected",
            target_type="resource",
            target_id=str(resource.id),
            target_title=resource.title,
            metadata={"reason": reason},
        )
        NotificationService.notify_resource_rejected(
            resource, resource.rejection_reason
        )
        return resource

    @staticmethod
    def calculate_resource_priority(resource: Resource) -> float:
        """Calculate moderation priority score for queue ordering."""
        report_qs = Report.objects.filter(resource=resource)
        report_count = report_qs.count()
        severe_count = report_qs.filter(
            reason_type__in=ModerationService.SEVERE_REPORT_REASONS
        ).count()
        return round(
            (report_count * 10)
            + (severe_count * 20)
            + (resource.download_count * 0.5)
            + (resource.view_count / 100),
            2,
        )

    @staticmethod
    @transaction.atomic
    def flag_resource(*, resource: Resource, reviewer, reason: str = "") -> Resource:
        """Flag a resource for review without rejecting it."""
        resource.status = "flagged"
        resource.save(update_fields=["status", "updated_at"])

        ModerationService.create_moderation_log(
            resource=resource,
            reviewer=reviewer,
            action="flagged",
            reason=reason,
        )

        ModerationService.log_admin_activity(
            admin=reviewer,
            action="resource_flagged",
            target_type="resource",
            target_id=str(resource.id),
            target_title=resource.title,
            metadata={"reason": reason} if reason else {},
        )

        ModerationService.notify_moderation_team(
            title="Resource Flagged",
            message=f'"{resource.title}" was flagged for review.',
            link=f"/resources/{resource.slug}/",
        )
        return resource

    @staticmethod
    @transaction.atomic
    def archive_resource(*, resource: Resource, reviewer, reason: str = "") -> Resource:
        """Archive a resource (soft delete)."""
        resource.status = "archived"
        resource.is_public = False
        resource.save(update_fields=["status", "is_public", "updated_at"])

        ModerationService.create_moderation_log(
            resource=resource,
            reviewer=reviewer,
            action="archived",
            reason=reason,
        )

        ModerationService.log_admin_activity(
            admin=reviewer,
            action="resource_archived",
            target_type="resource",
            target_id=str(resource.id),
            target_title=resource.title,
            metadata={"reason": reason} if reason else {},
        )
        return resource

    @staticmethod
    @transaction.atomic
    def restore_resource(*, resource: Resource, reviewer) -> Resource:
        """Restore an archived, flagged, or rejected resource to public visibility."""
        resource.status = "approved"
        resource.is_public = True
        resource.rejection_reason = ""
        resource.approved_by = reviewer
        resource.approved_at = timezone.now()
        resource.save(
            update_fields=[
                "status",
                "is_public",
                "rejection_reason",
                "approved_by",
                "approved_at",
                "updated_at",
            ]
        )

        ModerationService.create_moderation_log(
            resource=resource,
            reviewer=reviewer,
            action="restored",
            reason="Resource restored to approved",
        )

        ModerationService.log_admin_activity(
            admin=reviewer,
            action="resource_restored",
            target_type="resource",
            target_id=str(resource.id),
            target_title=resource.title,
            metadata={},
        )
        return resource

    @staticmethod
    def log_admin_activity(
        *,
        admin,
        action: str,
        target_type: str,
        target_id: str,
        target_title: str = "",
        metadata: dict = None,
        ip_address: str = None,
        user_agent: str = "",
    ):
        """Log admin activity for audit trail."""
        if not admin or not getattr(admin, "is_authenticated", False):
            return None

        return AdminActivityLog.objects.create(
            admin=admin,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            target_title=target_title,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def get_admin_activity_logs(
        admin=None,
        action=None,
        target_type=None,
        days=30,
        limit=100,
    ):
        """Get filtered admin activity logs."""
        from django.utils import timezone
        from datetime import timedelta

        queryset = AdminActivityLog.objects.all()

        if admin:
            queryset = queryset.filter(admin=admin)
        if action:
            queryset = queryset.filter(action=action)
        if target_type:
            queryset = queryset.filter(target_type=target_type)

        since = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(created_at__gte=since)

        return queryset[:limit]

    @staticmethod
    @transaction.atomic
    def queue_resource_for_review(*, resource: Resource, reason: str, reviewer=None):
        """Auto-hide risky resources instead of sending them to a manual queue."""
        state_changed = False
        if resource.status == "approved" or resource.is_public:
            # Move flagged resources back into manual moderation queue.
            resource.status = "pending"
            resource.is_public = False
            resource.save(update_fields=["status", "is_public", "updated_at"])
            state_changed = True

        if state_changed and reviewer:
            ModerationService.create_moderation_log(
                resource=resource,
                reviewer=reviewer,
                action="flagged",
                reason=reason,
            )

        if state_changed:
            NotificationService.create_notification(
                recipient=resource.uploaded_by,
                title="Resource Hidden Automatically",
                message=(
                    f'Your resource "{resource.title}" was hidden automatically after reports. '
                    f"Reason: {reason}"
                ),
                notification_type="system",
                link=f"/resources/{resource.slug}/",
                target_resource=resource,
            )

    @staticmethod
    @transaction.atomic
    def lock_comment(
        *, comment: Comment, reviewer, reason: str = "", hide_content: bool = False
    ):
        """Lock a comment and optionally hide its content."""
        updated_fields = []
        hidden_applied = False
        if not comment.is_locked:
            comment.is_locked = True
            updated_fields.append("is_locked")
        if hide_content:
            if not comment.moderation_hidden:
                comment.moderation_hidden_content = comment.content
                comment.moderation_hidden = True
                updated_fields.extend(
                    ["moderation_hidden_content", "moderation_hidden"]
                )
                hidden_applied = True
            if comment.content != "[hidden by moderation]":
                comment.content = "[hidden by moderation]"
                updated_fields.append("content")
                hidden_applied = True
            if not comment.is_deleted:
                comment.is_deleted = True
                updated_fields.append("is_deleted")
                hidden_applied = True

        if updated_fields:
            comment.save(update_fields=updated_fields + ["updated_at"])
            if "is_locked" in updated_fields:
                ModerationService.create_moderation_log(
                    comment=comment,
                    reviewer=reviewer,
                    action="locked",
                    reason=reason,
                )
            if hidden_applied:
                ModerationService.create_moderation_log(
                    comment=comment,
                    reviewer=reviewer,
                    action="hidden",
                    reason=reason,
                )
            title = "Comment Under Review" if hidden_applied else "Comment Locked"
            message = (
                "Your comment was temporarily hidden while it is being reviewed by moderators."
                if hidden_applied
                else "Your comment was locked by a moderator and cannot be edited for now."
            )
            NotificationService.create_notification(
                recipient=comment.user,
                title=title,
                message=message,
                notification_type="system",
                link=f"/resources/{comment.resource.slug}/",
                target_resource=comment.resource,
                target_comment=comment,
            )
        return comment

    @staticmethod
    @transaction.atomic
    def unlock_comment(
        *, comment: Comment, reviewer, reason: str = "", restore_content: bool = False
    ):
        """Unlock comment and optionally restore auto-hidden content."""
        updated_fields = []
        restored = False
        if comment.is_locked:
            comment.is_locked = False
            updated_fields.append("is_locked")
        if restore_content and comment.moderation_hidden:
            if comment.moderation_hidden_content:
                comment.content = comment.moderation_hidden_content
                updated_fields.append("content")
            comment.is_deleted = False
            comment.moderation_hidden = False
            comment.moderation_hidden_content = ""
            updated_fields.extend(
                ["is_deleted", "moderation_hidden", "moderation_hidden_content"]
            )
            restored = True

        if updated_fields:
            comment.save(update_fields=updated_fields + ["updated_at"])
            if "is_locked" in updated_fields:
                ModerationService.create_moderation_log(
                    comment=comment,
                    reviewer=reviewer,
                    action="unlocked",
                    reason=reason,
                )
            if restored:
                ModerationService.create_moderation_log(
                    comment=comment,
                    reviewer=reviewer,
                    action="restored",
                    reason=reason,
                )
            NotificationService.create_notification(
                recipient=comment.user,
                title="Comment Restored" if restored else "Comment Unlocked",
                message=(
                    "Your comment is visible again after moderation review was completed."
                    if restored
                    else "Your comment was unlocked by moderation and can be edited again."
                ),
                notification_type="system",
                link=f"/resources/{comment.resource.slug}/",
                target_resource=comment.resource,
                target_comment=comment,
            )
        return comment

    @staticmethod
    @transaction.atomic
    def queue_comment_for_review(*, comment: Comment, reason: str, reviewer=None):
        """Auto-hide and lock comments that require urgent moderation."""
        actor = reviewer or comment.user
        ModerationService.lock_comment(
            comment=comment,
            reviewer=actor,
            reason=reason,
            hide_content=True,
        )
        ModerationService.notify_moderation_team(
            title="Comment Flagged For Review",
            message=f"Comment #{comment.id} was auto-hidden. Reason: {reason}",
            link=f"/resources/{comment.resource.slug}/",
        )

    @staticmethod
    @transaction.atomic
    def maybe_release_comment_after_report_decision(report: Report):
        """Auto-release moderated comments once all active reports are closed."""
        if not report.comment:
            return

        comment = report.comment
        if not comment.moderation_hidden:
            return

        active_reports_exist = Report.objects.filter(
            comment=comment,
            status__in=["open", "in_review"],
        ).exists()
        if active_reports_exist:
            return

        reviewer = report.reviewed_by or report.reporter
        ModerationService.unlock_comment(
            comment=comment,
            reviewer=reviewer,
            reason=f"All active reports closed after report #{report.id} decision.",
            restore_content=True,
        )

    @staticmethod
    def handle_new_report(report: Report):
        """Automate moderation workload after a new report is submitted."""
        target = (
            report.resource.title if report.resource else f"Comment {report.comment_id}"
        )
        ModerationService.notify_moderation_team(
            title="New Content Report",
            message=f"New {report.reason_type} report submitted for {target}.",
            link=f"/reports/{report.id}/",
        )

        if report.resource:
            open_reports = Report.objects.filter(
                resource=report.resource, status__in=["open", "in_review"]
            )

            if report.reason_type in ModerationService.SEVERE_REPORT_REASONS:
                if report.status == "open":
                    report.status = "in_review"
                    report.save(update_fields=["status", "updated_at"])
                ModerationService.queue_resource_for_review(
                    resource=report.resource,
                    reason=f"Severe report reason: {report.reason_type}",
                    reviewer=report.reporter,
                )
                return

            if open_reports.count() >= ModerationService.AUTO_FLAG_REPORT_THRESHOLD:
                if report.status == "open":
                    report.status = "in_review"
                    report.save(update_fields=["status", "updated_at"])
                ModerationService.queue_resource_for_review(
                    resource=report.resource,
                    reason=f"{open_reports.count()} open reports reached threshold",
                    reviewer=report.reporter,
                )
            return

        if report.comment:
            open_reports = Report.objects.filter(
                comment=report.comment, status__in=["open", "in_review"]
            )
            if report.reason_type in ModerationService.SEVERE_REPORT_REASONS:
                if report.status == "open":
                    report.status = "in_review"
                    report.save(update_fields=["status", "updated_at"])
                ModerationService.queue_comment_for_review(
                    comment=report.comment,
                    reason=f"Severe report reason: {report.reason_type}",
                    reviewer=report.reporter,
                )
                return

            if open_reports.count() >= ModerationService.AUTO_FLAG_REPORT_THRESHOLD:
                if report.status == "open":
                    report.status = "in_review"
                    report.save(update_fields=["status", "updated_at"])
                ModerationService.queue_comment_for_review(
                    comment=report.comment,
                    reason=f"{open_reports.count()} open reports reached threshold",
                    reviewer=report.reporter,
                )

    @staticmethod
    def build_pending_queryset():
        """Get review-needed resources with calculated priority."""
        pending = Resource.objects.filter(status__in=["pending", "flagged"]).annotate(
            report_items_count=Count("reports"),
            severe_reports_count=Count(
                "reports",
                filter=Q(
                    reports__reason_type__in=ModerationService.SEVERE_REPORT_REASONS
                ),
            ),
        )
        return pending.order_by(
            "-severe_reports_count", "-report_items_count", "-created_at"
        )
