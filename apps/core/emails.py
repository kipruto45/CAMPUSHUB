"""
Email service for CampusHub.
Provides email sending capabilities with templates.
"""

import logging
from typing import List, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def get_configured_frontend_base_url() -> str:
    """Return only explicitly configured frontend/app host values."""
    return (
        getattr(settings, "FRONTEND_BASE_URL", "")
        or getattr(settings, "FRONTEND_URL", "")
        or getattr(settings, "RESOURCE_SHARE_BASE_URL", "")
        or getattr(settings, "WEB_APP_URL", "")
    ).rstrip("/")


def get_frontend_base_url() -> str:
    """
    Get the frontend base URL from settings.
    Falls back to multiple settings for compatibility.
    """
    return (
        get_configured_frontend_base_url()
        or getattr(settings, "BASE_URL", "")
    ).rstrip("/")


def get_backend_base_url() -> str:
    """Get the backend/site base URL for absolute server-hosted links."""
    return str(getattr(settings, "BASE_URL", "") or "").strip().rstrip("/")


def get_site_name() -> str:
    """Return the configured site name with a safe default."""
    return str(getattr(settings, "SITE_NAME", "") or "CampusHub").strip()


def get_mobile_deeplink_scheme() -> str:
    """Return the configured mobile deeplink scheme."""
    return str(getattr(settings, "MOBILE_DEEPLINK_SCHEME", "") or "").strip()


def build_mailto_url(email: str = "") -> str:
    """Build a mailto URL when an email address is available."""
    normalized = str(email or "").strip()
    return f"mailto:{normalized}" if normalized else ""


def _encode_query(query: Optional[dict]) -> str:
    if not query:
        return ""
    return urlencode({key: value for key, value in query.items() if value is not None})


def build_frontend_url(path: str = "", query: Optional[dict] = None) -> str:
    """Build an absolute frontend/web URL."""
    base = get_configured_frontend_base_url()
    if not base:
        return ""
    normalized_path = str(path or "").strip()
    if normalized_path and not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    url = f"{base}{normalized_path}"
    encoded_query = _encode_query(query)
    return f"{url}?{encoded_query}" if encoded_query else url


def build_backend_url(path: str = "", query: Optional[dict] = None) -> str:
    """Build an absolute backend URL."""
    base = get_backend_base_url()
    if not base:
        return ""
    normalized_path = str(path or "").strip()
    if normalized_path and not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    url = f"{base}{normalized_path}"
    encoded_query = _encode_query(query)
    return f"{url}?{encoded_query}" if encoded_query else url


def build_mobile_deeplink(path: str = "", query: Optional[dict] = None) -> str:
    """Build a mobile deeplink to the Expo app."""
    scheme = get_mobile_deeplink_scheme()
    if not scheme:
        return ""
    normalized_path = str(path or "").strip().lstrip("/")
    base = f"{scheme}://{normalized_path}" if normalized_path else f"{scheme}://"
    encoded_query = _encode_query(query)
    return f"{base}?{encoded_query}" if encoded_query else base


def build_app_url(
    *,
    web_path: str = "",
    mobile_path: Optional[str] = None,
    query: Optional[dict] = None,
    fallback_path: str = "",
    mobile_query: Optional[dict] = None,
    fallback_query: Optional[dict] = None,
) -> str:
    """
    Build a user-facing URL for email links.
    Prefers frontend URLs, then mobile deeplinks, then backend URLs.
    """
    frontend_url = build_frontend_url(web_path, query=query)
    if frontend_url:
        return frontend_url

    deeplink = build_mobile_deeplink(
        mobile_path or web_path,
        query=mobile_query if mobile_query is not None else query,
    )
    if deeplink:
        return deeplink

    if fallback_path:
        return build_backend_url(
            fallback_path,
            query=fallback_query if fallback_query is not None else query,
        )
    return ""


def build_public_resource_url(resource) -> str:
    """Build a canonical resource URL for emails and sharing."""
    identifier = str(getattr(resource, "slug", "") or getattr(resource, "id", "") or "").strip()
    if not identifier:
        return ""
    base = (
        str(getattr(settings, "RESOURCE_SHARE_BASE_URL", "") or "").strip().rstrip("/")
        or get_frontend_base_url()
        or get_backend_base_url()
    )
    return f"{base}/resources/{identifier}" if base else f"/resources/{identifier}"


class EmailService:
    """
    Service for sending emails with templates.
    """

    # Email templates directory
    TEMPLATES_DIR = "emails/"

    @staticmethod
    def send_email(
        subject: str,
        message: str,
        recipient_list: List[str],
        html_message: Optional[str] = None,
        from_email: Optional[str] = None,
        fail_silently: bool = False,
    ) -> bool:
        """
        Send email to recipients.

        Args:
            subject: Email subject
            message: Plain text message
            recipient_list: List of recipient email addresses
            html_message: HTML message (optional)
            from_email: Sender email (optional)
            fail_silently: Whether to raise exceptions

        Returns:
            True if email was sent successfully
        """
        try:
            from_email = from_email or settings.DEFAULT_FROM_EMAIL

            if html_message:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=message,
                    from_email=from_email,
                    to=recipient_list,
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=fail_silently)
            else:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=from_email,
                    recipient_list=recipient_list,
                    fail_silently=fail_silently,
                )

            logger.info(f"Email sent to {recipient_list}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            if not fail_silently:
                raise
            return False

    @staticmethod
    def send_template_email(
        template_name: str,
        context: dict,
        subject: str,
        recipient_list: List[str],
        from_email: Optional[str] = None,
        *,
        raise_on_error: bool = False,
    ) -> bool:
        """
        Send email using a template.

        Args:
            template_name: Template name (without extension)
            context: Template context dictionary
            subject: Email subject
            recipient_list: List of recipient emails
            from_email: Sender email
            raise_on_error: Raise exception if template rendering/sending fails

        Returns:
            True if email was sent
        """
        try:
            # Render HTML and plain text versions
            html_content = render_to_string(
                f"{EmailService.TEMPLATES_DIR}{template_name}.html", context
            )
            plain_content = strip_tags(html_content)

            return EmailService.send_email(
                subject=subject,
                message=plain_content,
                html_message=html_content,
                recipient_list=recipient_list,
                from_email=from_email,
            )

        except Exception as e:
            logger.error(f"Failed to send template email: {e}")
            if raise_on_error:
                raise
            return False


class UserEmailService:
    """
    Email service for user-related notifications.
    """

    @staticmethod
    def _build_support_links() -> dict:
        """Build optional web/help/contact links for email templates."""
        support_email = str(getattr(settings, "SUPPORT_EMAIL", "") or "").strip()
        return {
            "website_url": get_frontend_base_url(),
            "help_center_url": build_app_url(
                web_path="/help",
                mobile_path="help",
                fallback_path="/api/docs/",
            ),
            "contact_url": (
                build_app_url(
                    web_path="/contact-support",
                    mobile_path="contact-support",
                )
                or build_mailto_url(support_email)
            ),
        }

    @staticmethod
    def send_welcome_email(
        user,
        verification_token=None,
        verification_url: Optional[str] = None,
        *,
        raise_on_error: bool = False,
    ) -> bool:
        """
        Send welcome email to new user.

        Args:
            user: User instance
            verification_token: Optional verification token
            verification_url: Optional pre-built verification URL
            raise_on_error: Raise exception if template rendering/sending fails

        Returns:
            True if email was sent
        """
        from apps.accounts.verification import generate_signed_verification_token

        site_name = get_site_name()
        if not verification_url:
            if not verification_token:
                verification_token = generate_signed_verification_token(user)
            verification_url = build_app_url(
                web_path=f"/verify-email/{verification_token}",
                mobile_path="verify-email",
                fallback_path=f"/api/auth/verify-email/{verification_token}/",
                mobile_query={"token": verification_token},
            )

        return EmailService.send_template_email(
            template_name="welcome",
            context={
                "user": user,
                "site_name": site_name,
                "verification_url": verification_url,
                **UserEmailService._build_support_links(),
            },
            subject=f"Welcome to {site_name}! Please verify your email",
            recipient_list=[user.email],
            raise_on_error=raise_on_error,
        )

    @staticmethod
    def send_password_reset_email(user, reset_token) -> bool:
        """
        Send password reset email.

        Args:
            user: User instance
            reset_token: Password reset token

        Returns:
            True if email was sent
        """
        reset_url = build_app_url(
            web_path=f"/password-reset/{reset_token}",
            mobile_path="reset-password",
            fallback_path=f"/api/auth/password/reset/confirm/{reset_token}/",
            mobile_query={"token": reset_token},
        )

        return EmailService.send_template_email(
            template_name="password_reset",
            context={
                "user": user,
                "reset_url": reset_url,
                "site_name": get_site_name(),
            },
            subject="Password Reset Request",
            recipient_list=[user.email],
        )

    @staticmethod
    def send_password_changed_confirmation(user) -> bool:
        """
        Send password change confirmation email.

        Args:
            user: User instance

        Returns:
            True if email was sent
        """
        return EmailService.send_template_email(
            template_name="password_changed",
            context={
                "user": user,
                "site_name": get_site_name(),
            },
            subject="Password Changed Successfully",
            recipient_list=[user.email],
        )

    @staticmethod
    def send_email_verification_email(
        user,
        verification_token=None,
        verification_url: Optional[str] = None,
        *,
        raise_on_error: bool = False,
    ) -> bool:
        """
        Send email verification email.

        Args:
            user: User instance
            verification_token: Email verification token
            verification_url: Optional pre-built verification URL
            raise_on_error: Raise exception if template rendering/sending fails

        Returns:
            True if email was sent
        """
        from apps.accounts.verification import generate_signed_verification_token

        site_name = get_site_name()
        if not verification_url:
            if not verification_token:
                verification_token = generate_signed_verification_token(user)
            verification_url = build_app_url(
                web_path=f"/verify-email/{verification_token}",
                mobile_path="verify-email",
                fallback_path=f"/api/auth/verify-email/{verification_token}/",
                mobile_query={"token": verification_token},
            )

        return EmailService.send_template_email(
            template_name="email_verification",
            context={
                "user": user,
                "verify_url": verification_url,
                "site_name": site_name,
            },
            subject="Verify Your Email Address",
            recipient_list=[user.email],
            raise_on_error=raise_on_error,
        )


class ResourceEmailService:
    """
    Email service for resource-related notifications.
    """

    @staticmethod
    def send_resource_approved_email(user, resource) -> bool:
        """
        Send email when resource is approved.

        Args:
            user: User instance
            resource: Resource instance

        Returns:
            True if email was sent
        """
        resource_url = build_public_resource_url(resource)

        return EmailService.send_template_email(
            template_name="resource_approved",
            context={
                "user": user,
                "resource": resource,
                "resource_url": resource_url,
                "site_name": get_site_name(),
            },
            subject="Your Resource Has Been Approved",
            recipient_list=[user.email],
        )

    @staticmethod
    def send_resource_rejected_email(user, resource, reason) -> bool:
        """
        Send email when resource is rejected.

        Args:
            user: User instance
            resource: Resource instance
            reason: Rejection reason

        Returns:
            True if email was sent
        """
        upload_url = build_app_url(
            web_path="/upload-resource",
            mobile_path="upload-resource",
            fallback_path="/api/docs/",
        )
        
        return EmailService.send_template_email(
            template_name="resource_rejected",
            context={
                "user": user,
                "resource": resource,
                "reason": reason,
                "upload_url": upload_url,
                "site_name": get_site_name(),
            },
            subject="Your Resource Has Been Rejected",
            recipient_list=[user.email],
        )

    @staticmethod
    def send_resource_uploaded_confirmation(user, resource) -> bool:
        """
        Send confirmation when resource is uploaded.

        Args:
            user: User instance
            resource: Resource instance

        Returns:
            True if email was sent
        """
        return EmailService.send_template_email(
            template_name="resource_uploaded",
            context={
                "user": user,
                "resource": resource,
                "site_name": get_site_name(),
            },
            subject="Resource Uploaded Successfully",
            recipient_list=[user.email],
        )


class AdminEmailService:
    """
    Email service for admin notifications.
    """

    @staticmethod
    def send_new_user_registration_email(admin_email, user) -> bool:
        """
        Notify admin of new user registration.

        Args:
            admin_email: Admin email address
            user: New user instance

        Returns:
            True if email was sent
        """
        profile_url = build_backend_url(f"/admin/accounts/user/{user.id}/change/")

        return EmailService.send_template_email(
            template_name="admin_new_user",
            context={
                "user": user,
                "profile_url": profile_url,
                "site_name": get_site_name(),
            },
            subject=f"New User Registration: {user.email}",
            recipient_list=[admin_email],
        )

    @staticmethod
    def send_new_report_email(admin_email, report) -> bool:
        """
        Notify admin of new report.

        Args:
            admin_email: Admin email address
            report: Report instance

        Returns:
            True if email was sent
        """
        report_url = build_backend_url(f"/admin/reports/report/{report.id}/change/")

        return EmailService.send_template_email(
            template_name="admin_new_report",
            context={
                "report": report,
                "report_url": report_url,
                "site_name": get_site_name(),
            },
            subject=f"New Report: {report.get_reason_type_display()}",
            recipient_list=[admin_email],
        )

    @staticmethod
    def send_pending_resources_email(admin_email, count) -> bool:
        """
        Notify admin of pending resources awaiting review.

        Args:
            admin_email: Admin email address
            count: Number of pending resources

        Returns:
            True if email was sent
        """
        if count == 0:
            return False

        moderation_url = build_backend_url("/admin/resources/resource/")

        return EmailService.send_template_email(
            template_name="admin_pending_resources",
            context={
                "count": count,
                "moderation_url": moderation_url,
                "site_name": get_site_name(),
            },
            subject=f"{count} Resources Pending Review",
            recipient_list=[admin_email],
        )

    @staticmethod
    def send_resource_approved_email(user, resource) -> bool:
        """
        Notify user that their resource was approved.

        Args:
            user: User who uploaded the resource
            resource: Approved resource instance

        Returns:
            True if email was sent
        """
        resource_url = build_public_resource_url(resource)

        return EmailService.send_template_email(
            template_name="resource_approved",
            context={
                "user": user,
                "resource": resource,
                "resource_url": resource_url,
                "site_name": get_site_name(),
            },
            subject=f"Your resource '{resource.title}' has been approved!",
            recipient_list=[user.email],
        )

    @staticmethod
    def send_resource_rejected_email(user, resource, reason) -> bool:
        """
        Notify user that their resource was rejected.

        Args:
            user: User who uploaded the resource
            resource: Rejected resource instance
            reason: Reason for rejection

        Returns:
            True if email was sent
        """
        upload_url = build_app_url(
            web_path="/upload-resource",
            mobile_path="upload-resource",
            fallback_path="/api/docs/",
        )

        return EmailService.send_template_email(
            template_name="resource_rejected",
            context={
                "user": user,
                "resource": resource,
                "reason": reason,
                "upload_url": upload_url,
                "site_name": get_site_name(),
            },
            subject=f"Your resource '{resource.title}' was not approved",
            recipient_list=[user.email],
        )

    @staticmethod
    def send_bulk_action_completed_email(admin_email, action, count, success_count, failed_count) -> bool:
        """
        Notify admin that bulk action completed.

        Args:
            admin_email: Admin email address
            action: Type of action performed
            count: Total resources affected
            success_count: Number of successful operations
            failed_count: Number of failed operations

        Returns:
            True if email was sent
        """
        moderation_url = build_backend_url("/admin/resources/resource/")

        return EmailService.send_template_email(
            template_name="admin_bulk_action",
            context={
                "action": action,
                "count": count,
                "success_count": success_count,
                "failed_count": failed_count,
                "moderation_url": moderation_url,
                "site_name": get_site_name(),
            },
            subject=f"Bulk {action.title()} Completed: {success_count}/{count} successful",
            recipient_list=[admin_email],
        )

    @staticmethod
    def send_storage_warning_email(admin_email, storage_percent, storage_used_gb) -> bool:
        """
        Notify admin of storage warning.

        Args:
            admin_email: Admin email address
            storage_percent: Percentage of storage used
            storage_used_gb: Storage used in GB

        Returns:
            True if email was sent
        """
        settings_url = build_backend_url("/admin/")

        return EmailService.send_template_email(
            template_name="admin_storage_warning",
            context={
                "storage_percent": storage_percent,
                "storage_used_gb": storage_used_gb,
                "settings_url": settings_url,
                "site_name": get_site_name(),
            },
            subject=f"Storage Warning: {storage_percent}% Used",
            recipient_list=[admin_email],
        )

    @staticmethod
    def send_campaign_emails(campaign_id) -> dict:
        """
        Send emails to all recipients of a campaign.

        Args:
            campaign_id: ID of the EmailCampaign to send

        Returns:
            Dict with sent_count, failed_count
        """
        from apps.core.models import EmailCampaign
        from django.db.models import Q
        from django.utils import timezone
        from apps.accounts.models import User

        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
        except EmailCampaign.DoesNotExist:
            return {'sent_count': 0, 'failed_count': 0, 'error': 'Campaign not found'}

        # Build user query based on target filters
        users_query = Q()
        target_filters = campaign.target_filters or {}

        if 'faculty_ids' in target_filters:
            users_query &= Q(faculty_id__in=target_filters['faculty_ids'])
        if 'department_ids' in target_filters:
            users_query &= Q(department_id__in=target_filters['department_ids'])
        if 'course_ids' in target_filters:
            users_query &= Q(course_id__in=target_filters['course_ids'])
        if 'year_of_study' in target_filters:
            users_query &= Q(year_of_study=target_filters['year_of_study'])
        if 'user_roles' in target_filters:
            users_query &= Q(role__in=target_filters['user_roles'])

        # Get recipients
        if target_filters:
            recipients = User.objects.filter(users_query, is_active=True).distinct()
        else:
            recipients = User.objects.filter(is_active=True).distinct()

        sent_count = 0
        failed_count = 0

        # Update campaign status
        campaign.status = 'sending'
        campaign.save()

        for user in recipients:
            try:
                # Send individual email
                EmailService.send_template_email(
                    template_name="campaign_email",
                    context={
                        "user": user,
                        "campaign": campaign,
                        "site_name": get_site_name(),
                    },
                    subject=campaign.subject,
                    recipient_list=[user.email],
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1

        # Update campaign with results
        campaign.status = 'sent'
        campaign.sent_at = timezone.now()
        campaign.sent_count = sent_count
        campaign.failed_count = failed_count
        campaign.save()

        return {
            'sent_count': sent_count,
            'failed_count': failed_count,
        }
