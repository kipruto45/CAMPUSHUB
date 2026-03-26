"""
Payment notification service for CampusHub.
Handles email and SMS notifications for payment events.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import models
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.utils.html import strip_tags

from apps.core.emails import EmailService, build_app_url
from apps.payments.receipts import attach_receipt_to_email, get_receipt_url_for_sms

logger = logging.getLogger(__name__)


class PaymentNotificationService:
    """
    Service for sending payment-related notifications via email and SMS.
    """

    @staticmethod
    def send_payment_success_email(
        user,
        amount: Decimal,
        currency: str,
        payment_type: str,
        payment_id: str = None,
        payment=None
    ) -> bool:
        """
        Send email notification when payment is successfully received.

        Args:
            user: User instance
            amount: Payment amount
            currency: Currency code (USD, KES, etc.)
            payment_type: Type of payment (subscription, storage_upgrade, etc.)
            payment_id: Optional payment identifier
            payment: Payment model instance (for receipt attachment)

        Returns:
            True if email sent successfully
        """
        try:
            from django.core.mail import EmailMultiAlternatives
            
            # Generate receipt URL for SMS links
            receipt_url = None
            if payment:
                receipt_url = get_receipt_url_for_sms(payment)

            context = {
                "user": user,
                "amount": amount,
                "currency": currency,
                "payment_type": payment_type.replace("_", " ").title(),
                "payment_id": payment_id,
                "billing_url": build_app_url(
                    web_path="/billing",
                    mobile_path="billing",
                    fallback_path="/api/payments/payments/",
                ),
                "receipt_url": receipt_url,
                "date": timezone.now().strftime("%B %d, %Y"),
            }

            # Render email template
            subject = f"Payment Received - {currency} {amount}"
            html_content = render_to_string(
                "emails/payment_success.html", context
            )
            plain_message = strip_tags(html_content)

            # Create email message
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            msg.attach_alternative(html_content, "text/html")
            
            # Attach PDF receipt if payment provided
            if payment:
                attach_receipt_to_email(payment, msg)
            
            msg.send(fail_silently=False)
            return True

        except Exception as e:
            logger.error(f"Failed to send payment success email: {e}")
            return False

    @staticmethod
    def send_payment_success_sms(
        user,
        amount: str,
        currency: str,
        payment_type: str,
        receipt_url: str = None
    ) -> bool:
        """
        Send SMS notification when payment is successfully received.

        Args:
            user: User instance
            amount: Payment amount as string
            currency: Currency code
            payment_type: Type of payment
            receipt_url: URL to download receipt

        Returns:
            True if SMS sent successfully
        """
        if not getattr(user, "phone_number", None):
            logger.info(f"User {user.id} has no phone number, skipping SMS")
            return False

        try:
            from apps.core.sms import sms_service

            # Build message with receipt link
            message = f"CampusHub: Payment of {currency} {amount} received for {payment_type.replace('_', ' ')}. "
            if receipt_url:
                message += f"Download receipt: {receipt_url}"
            else:
                message += "Thank you!"

            result = sms_service.send(phone=user.phone_number, message=message)
            return result.get("success", False)

        except Exception as e:
            logger.error(f"Failed to send payment success SMS: {e}")
            return False

    @staticmethod
    def send_payment_failure_email(
        user,
        amount: Decimal,
        currency: str,
        payment_type: str,
        reason: str = None
    ) -> bool:
        """
        Send email notification when payment fails.

        Args:
            user: User instance
            amount: Payment amount
            currency: Currency code
            payment_type: Type of payment
            reason: Failure reason

        Returns:
            True if email sent successfully
        """
        try:
            context = {
                "user": user,
                "amount": amount,
                "currency": currency,
                "payment_type": payment_type.replace("_", " ").title(),
                "reason": reason or "Unknown error",
                "retry_url": build_app_url(
                    web_path="/billing/pay",
                    mobile_path="billing/pay",
                    fallback_path="/api/payments/plans/",
                ),
                "support_email": getattr(settings, "SUPPORT_EMAIL", "support@campushub.com"),
                "date": timezone.now().strftime("%B %d, %Y"),
            }

            subject = f"Payment Failed - {currency} {amount}"
            html_content = render_to_string(
                "emails/payment_failed.html", context
            )
            plain_message = strip_tags(html_content)

            return EmailService.send_email(
                subject=subject,
                message=plain_message,
                recipient_list=[user.email],
                html_message=html_content,
            )

        except Exception as e:
            logger.error(f"Failed to send payment failure email: {e}")
            return False

    @staticmethod
    def send_subscription_expiry_reminder_email(
        user,
        days_remaining: int,
        plan_name: str,
        renewal_url: str = None
    ) -> bool:
        """
        Send email reminder before subscription expires.

        Args:
            user: User instance
            days_remaining: Days until expiration
            plan_name: Name of the subscription plan
            renewal_url: URL to renew subscription

        Returns:
            True if email sent successfully
        """
        try:
            renewal_url = renewal_url or build_app_url(
                web_path="/billing/plans",
                mobile_path="billing/plans",
                fallback_path="/api/payments/plans/",
            )

            context = {
                "user": user,
                "days_remaining": days_remaining,
                "plan_name": plan_name,
                "renewal_url": renewal_url,
                "date": timezone.now().strftime("%B %d, %Y"),
            }

            subject = f"Your {plan_name} subscription expires in {days_remaining} days"
            html_content = render_to_string(
                "emails/subscription_expiry_reminder.html", context
            )
            plain_message = strip_tags(html_content)

            return EmailService.send_email(
                subject=subject,
                message=plain_message,
                recipient_list=[user.email],
                html_message=html_content,
            )

        except Exception as e:
            logger.error(f"Failed to send subscription expiry email: {e}")
            return False

    @staticmethod
    def send_subscription_expiry_reminder_sms(
        user,
        days_remaining: int,
        plan_name: str
    ) -> bool:
        """
        Send SMS reminder before subscription expires.

        Args:
            user: User instance
            days_remaining: Days until expiration
            plan_name: Name of the subscription plan

        Returns:
            True if SMS sent successfully
        """
        if not getattr(user, "phone_number", None):
            return False

        try:
            from apps.core.sms import sms_service

            return sms_service.send_subscription_expiry_reminder(
                phone=user.phone_number,
                days_remaining=days_remaining,
                plan_name=plan_name
            ).get("success", False)

        except Exception as e:
            logger.error(f"Failed to send subscription expiry SMS: {e}")
            return False

    @staticmethod
    def send_trial_expired_email(
        user,
        plan_name: str,
        upgrade_url: str = None,
    ) -> bool:
        """Send a one-time email when a free trial elapses."""
        if not getattr(user, "email", None):
            return False

        try:
            upgrade_url = upgrade_url or build_app_url(
                web_path="/billing/plans",
                mobile_path="billing/plans",
                fallback_path="/api/payments/plans/",
            )
            context = {
                "user": user,
                "plan_name": plan_name,
                "upgrade_url": upgrade_url,
                "date": timezone.now().strftime("%B %d, %Y"),
            }
            subject = "Your CampusHub free trial has ended"
            html_content = render_to_string("emails/trial_expired.html", context)
            plain_message = strip_tags(html_content)

            return EmailService.send_email(
                subject=subject,
                message=plain_message,
                recipient_list=[user.email],
                html_message=html_content,
            )
        except Exception as e:
            logger.error(f"Failed to send trial expired email: {e}")
            return False

    @staticmethod
    def send_trial_expired_sms(
        user,
        plan_name: str,
    ) -> bool:
        """Send a one-time SMS when a free trial elapses."""
        if not getattr(user, "phone_number", None):
            return False

        try:
            from apps.core.sms import sms_service

            return sms_service.send_trial_expired_notice(
                phone=user.phone_number,
                plan_name=plan_name,
            ).get("success", False)
        except Exception as e:
            logger.error(f"Failed to send trial expired SMS: {e}")
            return False

    @staticmethod
    def send_payment_due_reminder_email(
        user,
        amount: Decimal,
        currency: str,
        due_date: str,
        description: str = None
    ) -> bool:
        """
        Send email reminder for pending payment.

        Args:
            user: User instance
            amount: Amount due
            currency: Currency code
            due_date: Due date string
            description: Payment description

        Returns:
            True if email sent successfully
        """
        try:
            context = {
                "user": user,
                "amount": amount,
                "currency": currency,
                "due_date": due_date,
                "description": description or "Pending payment",
                "payment_url": build_app_url(
                    web_path="/billing/pay",
                    mobile_path="billing/pay",
                    fallback_path="/api/payments/plans/",
                ),
                "date": timezone.now().strftime("%B %d, %Y"),
            }

            subject = f"Payment Reminder - {currency} {amount} due {due_date}"
            html_content = render_to_string(
                "emails/payment_due_reminder.html", context
            )
            plain_message = strip_tags(html_content)

            return EmailService.send_email(
                subject=subject,
                message=plain_message,
                recipient_list=[user.email],
                html_message=html_content,
            )

        except Exception as e:
            logger.error(f"Failed to send payment due reminder email: {e}")
            return False

    @staticmethod
    def send_payment_due_reminder_sms(
        user,
        amount: str,
        due_date: str
    ) -> bool:
        """
        Send SMS reminder for pending payment.

        Args:
            user: User instance
            amount: Amount due as string
            due_date: Due date string

        Returns:
            True if SMS sent successfully
        """
        if not getattr(user, "phone_number", None):
            return False

        try:
            from apps.core.sms import sms_service

            return sms_service.send_payment_due_reminder(
                phone=user.phone_number,
                amount=amount,
                due_date=due_date
            ).get("success", False)

        except Exception as e:
            logger.error(f"Failed to send payment due reminder SMS: {e}")
            return False

    @staticmethod
    def send_refund_notification_email(
        user,
        amount: Decimal,
        currency: str,
        payment_id: str,
        reason: str = None,
        payment=None,
    ) -> bool:
        """
        Send email when a refund is processed.

        Args:
            user: User instance
            amount: Refund amount
            currency: Currency code
            payment_id: Original payment ID
            reason: Refund reason
            payment: Payment instance (for receipt attachment)

        Returns:
            True if email sent successfully
        """
        try:
            context = {
                "user": user,
                "amount": amount,
                "currency": currency,
                "payment_id": payment_id,
                "reason": reason or "No reason provided",
                "billing_url": build_app_url(
                    web_path="/billing/history",
                    mobile_path="billing/history",
                    fallback_path="/api/payments/payments/",
                ),
                "date": timezone.now().strftime("%B %d, %Y"),
            }

            subject = f"Refund Processed - {currency} {amount}"
            html_content = render_to_string(
                "emails/refund_processed.html", context
            )
            plain_message = strip_tags(html_content)

            from django.core.mail import EmailMultiAlternatives
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            msg.attach_alternative(html_content, "text/html")

            if payment:
                from apps.payments.receipts import attach_receipt_to_email, get_receipt_url_for_sms
                try:
                    attach_receipt_to_email(payment, msg)
                    context["receipt_url"] = get_receipt_url_for_sms(payment)
                except Exception:
                    pass

            msg.send(fail_silently=False)
            return True

        except Exception as e:
            logger.error(f"Failed to send refund notification email: {e}")
            return False

    @staticmethod
    def send_subscription_activated_email(
        user,
        plan_name: str,
        billing_period: str,
        amount: Decimal,
        currency: str
    ) -> bool:
        """
        Send email when subscription is activated.

        Args:
            user: User instance
            plan_name: Name of subscription plan
            billing_period: monthly or yearly
            amount: Subscription amount
            currency: Currency code

        Returns:
            True if email sent successfully
        """
        try:
            context = {
                "user": user,
                "plan_name": plan_name,
                "billing_period": billing_period,
                "amount": amount,
                "currency": currency,
                "billing_url": build_app_url(
                    web_path="/billing",
                    mobile_path="billing",
                    fallback_path="/api/payments/subscription/",
                ),
                "date": timezone.now().strftime("%B %d, %Y"),
            }

            subject = f"Subscription Activated - {plan_name}"
            html_content = render_to_string(
                "emails/subscription_activated.html", context
            )
            plain_message = strip_tags(html_content)

            return EmailService.send_email(
                subject=subject,
                message=plain_message,
                recipient_list=[user.email],
                html_message=html_content,
            )

        except Exception as e:
            logger.error(f"Failed to send subscription activated email: {e}")
            return False

    @staticmethod
    def send_subscription_cancelled_email(
        user,
        plan_name: str,
        expiration_date: str
    ) -> bool:
        """
        Send email when subscription is cancelled.

        Args:
            user: User instance
            plan_name: Name of subscription plan
            expiration_date: When subscription expires

        Returns:
            True if email sent successfully
        """
        try:
            context = {
                "user": user,
                "plan_name": plan_name,
                "expiration_date": expiration_date,
                "reactivate_url": build_app_url(
                    web_path="/billing/plans",
                    mobile_path="billing/plans",
                    fallback_path="/api/payments/plans/",
                ),
                "date": timezone.now().strftime("%B %d, %Y"),
            }

            subject = f"Subscription Cancelled - {plan_name}"
            html_content = render_to_string(
                "emails/subscription_cancelled.html", context
            )
            plain_message = strip_tags(html_content)

            return EmailService.send_email(
                subject=subject,
                message=plain_message,
                recipient_list=[user.email],
                html_message=html_content,
            )

        except Exception as e:
            logger.error(f"Failed to send subscription cancelled email: {e}")
            return False

    @staticmethod
    def send_storage_upgrade_confirmation_email(
        user,
        storage_gb: int,
        duration_days: int,
        amount: Decimal,
        currency: str
    ) -> bool:
        """
        Send email when storage upgrade is purchased.

        Args:
            user: User instance
            storage_gb: Storage in GB
            duration_days: Duration in days
            amount: Amount paid
            currency: Currency code

        Returns:
            True if email sent successfully
        """
        try:
            context = {
                "user": user,
                "storage_gb": storage_gb,
                "duration_days": duration_days,
                "amount": amount,
                "currency": currency,
                "storage_url": build_app_url(
                    web_path="/storage",
                    mobile_path="storage",
                    fallback_path="/api/payments/storage/",
                ),
                "date": timezone.now().strftime("%B %d, %Y"),
            }

            subject = f"Storage Upgrade Complete - {storage_gb}GB"
            html_content = render_to_string(
                "emails/storage_upgrade_confirmed.html", context
            )
            plain_message = strip_tags(html_content)

            return EmailService.send_email(
                subject=subject,
                message=plain_message,
                recipient_list=[user.email],
                html_message=html_content,
            )

        except Exception as e:
            logger.error(f"Failed to send storage upgrade email: {e}")
            return False


# Singleton instance
payment_notification_service = PaymentNotificationService()


# ============== Celery Tasks for Scheduled Notifications ==============

def send_expiry_reminders():
    """
    Task to send subscription expiry reminders.
    Should be run daily via Celery beat.
    """
    from apps.payments.models import Subscription

    # Get subscriptions expiring in 7, 3, and 1 day(s)
    reminder_days = [7, 3, 1]

    for days in reminder_days:
        target_date = timezone.now() + timedelta(days=days)

        subscriptions = Subscription.objects.filter(
            status="active",
            current_period_end__date=target_date.date(),
        ).select_related("user", "plan")

        for sub in subscriptions:
            user = sub.user
            plan_name = sub.plan.name

            # Send email reminder
            payment_notification_service.send_subscription_expiry_reminder_email(
                user=user,
                days_remaining=days,
                plan_name=plan_name
            )

            # Send SMS reminder if phone available
            if getattr(user, "phone_number", None):
                payment_notification_service.send_subscription_expiry_reminder_sms(
                    user=user,
                    days_remaining=days,
                    plan_name=plan_name
                )

            logger.info(f"Sent expiry reminder for user {user.id}, subscription {sub.id}")


def send_payment_due_reminders():
    """
    Task to send payment due reminders.
    For pending payments or upcoming invoices.
    """
    from apps.payments.models import Invoice, Payment

    now = timezone.now()
    today = now.date()
    reminder_window_end = now + timedelta(days=3)
    sent_count = 0

    # Pending payments: remind if inferred/explicit due date is within reminder window.
    pending_payments = (
        Payment.objects.filter(
            status__in=["pending", "partial"],
            created_at__gte=now - timedelta(days=30),
        )
        .select_related("user")
        .order_by("created_at")
    )

    for payment in pending_payments:
        try:
            metadata = dict(payment.metadata or {})
            reminders = dict(metadata.get("reminders") or {})
            last_sent_raw = reminders.get("payment_due_last_sent_at")

            if isinstance(last_sent_raw, str):
                last_sent = parse_datetime(last_sent_raw)
                if last_sent and timezone.is_naive(last_sent):
                    last_sent = timezone.make_aware(last_sent)
                if last_sent and last_sent.date() == today:
                    continue

            due_at = None
            raw_due = metadata.get("due_date")
            if isinstance(raw_due, str):
                parsed_due = parse_datetime(raw_due)
                if parsed_due and timezone.is_naive(parsed_due):
                    parsed_due = timezone.make_aware(parsed_due)
                due_at = parsed_due

            # Fallback for legacy pending payments without explicit due date.
            if due_at is None:
                due_at = payment.created_at + timedelta(days=1)

            if due_at > reminder_window_end:
                continue

            due_date = timezone.localtime(due_at).strftime("%B %d, %Y")
            payment_notification_service.send_payment_due_reminder_email(
                user=payment.user,
                amount=payment.amount,
                currency=payment.currency,
                due_date=due_date,
                description=payment.description or "Pending payment",
            )

            if getattr(payment.user, "phone_number", None):
                payment_notification_service.send_payment_due_reminder_sms(
                    user=payment.user,
                    amount=f"{payment.currency} {payment.amount}",
                    due_date=due_date,
                )

            reminders["payment_due_last_sent_at"] = now.isoformat()
            metadata["reminders"] = reminders
            payment.metadata = metadata
            payment.save(update_fields=["metadata", "updated_at"])
            sent_count += 1
        except Exception as exc:
            logger.error(
                "Failed to send pending payment reminder for payment %s: %s",
                payment.id,
                exc,
            )

    # Unpaid/open invoices with explicit due date.
    invoice_statuses = ["draft", "open", "pending", "unpaid", "past_due"]
    due_invoices = (
        Invoice.objects.filter(
            status__in=invoice_statuses,
            paid_at__isnull=True,
            due_date__isnull=False,
            due_date__lte=reminder_window_end,
        )
        .filter(models.Q(voided_at__isnull=True))
        .select_related("user")
        .order_by("due_date")
    )

    for invoice in due_invoices:
        try:
            metadata = dict(invoice.metadata or {})
            reminders = dict(metadata.get("reminders") or {})
            last_sent_raw = reminders.get("invoice_due_last_sent_at")

            if isinstance(last_sent_raw, str):
                last_sent = parse_datetime(last_sent_raw)
                if last_sent and timezone.is_naive(last_sent):
                    last_sent = timezone.make_aware(last_sent)
                if last_sent and last_sent.date() == today:
                    continue

            due_date = timezone.localtime(invoice.due_date).strftime("%B %d, %Y")
            amount = invoice.total_amount or invoice.amount
            payment_notification_service.send_payment_due_reminder_email(
                user=invoice.user,
                amount=amount,
                currency=invoice.currency,
                due_date=due_date,
                description=invoice.description or f"Invoice {invoice.invoice_number}",
            )

            if getattr(invoice.user, "phone_number", None):
                payment_notification_service.send_payment_due_reminder_sms(
                    user=invoice.user,
                    amount=f"{invoice.currency} {amount}",
                    due_date=due_date,
                )

            reminders["invoice_due_last_sent_at"] = now.isoformat()
            metadata["reminders"] = reminders
            invoice.metadata = metadata
            invoice.save(update_fields=["metadata", "updated_at"])
            sent_count += 1
        except Exception as exc:
            logger.error(
                "Failed to send invoice reminder for invoice %s: %s",
                invoice.id,
                exc,
            )

    return sent_count
