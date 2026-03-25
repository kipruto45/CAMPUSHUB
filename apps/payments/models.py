"""
Payment models for premium subscriptions.
"""

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Plan(TimeStampedModel):
    """Subscription plans available on the platform."""

    TIER_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("premium", "Premium"),
        ("enterprise", "Enterprise"),
    ]

    BILLING_PERIOD_CHOICES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    name = models.CharField(max_length=100)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default="free")
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billing_period = models.CharField(max_length=20, choices=BILLING_PERIOD_CHOICES, default="monthly")

    # Features
    storage_limit_gb = models.PositiveIntegerField(default=1)
    max_upload_size_mb = models.PositiveIntegerField(default=10)
    download_limit_monthly = models.PositiveIntegerField(default=50)
    can_download_unlimited = models.BooleanField(default=False)
    has_ads = models.BooleanField(default=True)
    has_priority_support = models.BooleanField(default=False)
    has_analytics = models.BooleanField(default=False)
    has_early_access = models.BooleanField(default=False)

    # Stripe
    stripe_monthly_price_id = models.CharField(max_length=100, blank=True)
    stripe_yearly_price_id = models.CharField(max_length=100, blank=True)
    stripe_product_id = models.CharField(max_length=100, blank=True)

    # Display
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "payments"
        ordering = ["display_order", "name"]
        verbose_name = "Plan"
        verbose_name_plural = "Plans"

    def __str__(self):
        return f"{self.name} ({self.tier})"

    @property
    def current_price(self):
        return self.price_monthly if self.billing_period == "monthly" else self.price_yearly


class Subscription(TimeStampedModel):
    """User subscription tracking."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("trialing", "Trialing"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("unpaid", "Unpaid"),
        ("paused", "Paused"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions"
    )

    # Stripe subscription info
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trialing")

    # Billing
    billing_period = models.CharField(max_length=20, default="monthly")
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)

    # Trial
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "payments"
        ordering = ["-created_at"]
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["stripe_subscription_id"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"

    @property
    def is_active(self):
        return self.status in ["active", "trialing"]

    @property
    def is_canceled(self):
        return self.status == "canceled"


class Payment(TimeStampedModel):
    """Payment history for subscriptions."""

    TYPE_CHOICES = [
        ("subscription", "Subscription"),
        ("one_time", "One-time"),
        ("refund", "Refund"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("succeeded", "Succeeded"),
        ("partial", "Partial"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )

    # Payment info
    payment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="subscription")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Stripe
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)
    stripe_charge_id = models.CharField(max_length=100, blank=True)
    stripe_invoice_id = models.CharField(max_length=100, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Details
    description = models.TextField(blank=True)
    receipt_url = models.URLField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Refund info
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "payments"
        ordering = ["-created_at"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["stripe_payment_intent_id"]),
        ]

    def __str__(self):
        return f"{self.user.username} - ${self.amount} ({self.status})"


class StorageUpgrade(TimeStampedModel):
    """Storage upgrade purchases."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("canceled", "Canceled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="storage_upgrades"
    )

    # Upgrade details
    storage_gb = models.PositiveIntegerField()
    duration_days = models.PositiveIntegerField(default=30)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # Stripe
    stripe_product_id = models.CharField(max_length=100, blank=True)
    stripe_price_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Period
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    # Payment
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storage_upgrades"
    )

    class Meta:
        app_label = "payments"
        ordering = ["-created_at"]
        verbose_name = "Storage Upgrade"
        verbose_name_plural = "Storage Upgrades"

    def __str__(self):
        return f"{self.user.username} - {self.storage_gb}GB"


class Invoice(TimeStampedModel):
    """Generated invoices for user billing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invoices"
    )

    # Invoice details
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Stripe
    stripe_invoice_id = models.CharField(max_length=100, blank=True)
    stripe_invoice_pdf = models.URLField(blank=True)

    # Status
    status = models.CharField(max_length=20, default="draft")
    paid_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    # Items
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "payments"
        ordering = ["-created_at"]
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"

    def __str__(self):
        return f"Invoice {self.invoice_number}"


class PromoCode(TimeStampedModel):
    """Promotional codes for discounts."""

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.TextField(blank=True)

    # Discount
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Limits
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    current_uses = models.PositiveIntegerField(default=0)
    max_uses_per_user = models.PositiveIntegerField(default=1)

    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)

    # Plans this applies to
    applicable_plans = models.ManyToManyField(Plan, blank=True, related_name="promo_codes")

    # Restrictions
    first_time_only = models.BooleanField(default=False)
    min_subscription_months = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "payments"
        ordering = ["-created_at"]
        verbose_name = "Promo Code"
        verbose_name_plural = "Promo Codes"

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        if not self.is_active:
            return False

        now = timezone.now()
        if now < self.valid_from:
            return False

        if self.valid_until and now > self.valid_until:
            return False

        if self.max_uses and self.current_uses >= self.max_uses:
            return False

        return True


class UserCoupon(TimeStampedModel):
    """Coupons applied to user accounts."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coupons"
    )
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.CASCADE,
        related_name="user_coupons"
    )

    # Applied to
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupons"
    )

    # Discount applied
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = "payments"
        unique_together = ["user", "promo_code", "subscription"]
        verbose_name = "User Coupon"
        verbose_name_plural = "User Coupons"

    def __str__(self):
        return f"{self.user.username} - {self.promo_code.code}"


# ============== In-App Purchase Models ==============

class InAppProduct(TimeStampedModel):
    """In-app purchase products for mobile platforms."""

    PLATFORM_CHOICES = [
        ("apple", "Apple App Store"),
        ("google", "Google Play Store"),
        ("web", "Web (Stripe)"),
    ]

    PRODUCT_TYPE_CHOICES = [
        ("subscription", "Subscription"),
        ("one_time", "One-time Purchase"),
        ("feature_unlock", "Feature Unlock"),
    ]

    SUBSCRIPTION_TYPE_CHOICES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Platform
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES)
    
    # Subscription type (if applicable)
    subscription_type = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_TYPE_CHOICES,
        blank=True,
        null=True
    )
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    
    # Platform-specific product IDs
    apple_product_id = models.CharField(max_length=100, blank=True)
    google_product_id = models.CharField(max_length=100, blank=True)
    stripe_price_id = models.CharField(max_length=100, blank=True)
    
    # Tier mapping
    tier = models.CharField(max_length=20, choices=Plan.TIER_CHOICES, blank=True)
    
    # Features (for feature unlocks)
    feature_key = models.CharField(max_length=50, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    
    # Display
    display_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "payments"
        ordering = ["display_order", "name"]
        verbose_name = "In-App Product"
        verbose_name_plural = "In-App Products"
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "apple_product_id"],
                name="unique_apple_product",
                condition=models.Q(apple_product_id__gt="")
            ),
            models.UniqueConstraint(
                fields=["platform", "google_product_id"],
                name="unique_google_product",
                condition=models.Q(google_product_id__gt="")
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.platform})"


class InAppPurchase(TimeStampedModel):
    """Record of in-app purchases."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("canceled", "Canceled"),
        ("refunded", "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="in_app_purchases"
    )
    product = models.ForeignKey(
        InAppProduct,
        on_delete=models.PROTECT,
        related_name="purchases"
    )
    
    # Platform
    platform = models.CharField(max_length=20, choices=InAppProduct.PLATFORM_CHOICES)
    
    # Platform-specific transaction IDs
    apple_transaction_id = models.CharField(max_length=100, blank=True)
    google_purchase_token = models.CharField(max_length=200, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    # Subscription period
    is_subscription = models.BooleanField(default=False)
    subscription_type = models.CharField(max_length=20, blank=True)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    expires_date = models.DateTimeField(null=True, blank=True)
    auto_renew_enabled = models.BooleanField(default=False)
    
    # Original transaction (for subscriptions)
    original_transaction_id = models.CharField(max_length=100, blank=True)
    
    # Payment
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    
    # Linked subscription
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="in_app_purchases"
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "payments"
        ordering = ["-created_at"]
        verbose_name = "In-App Purchase"
        verbose_name_plural = "In-App Purchases"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["platform", "apple_transaction_id"]),
            models.Index(fields=["platform", "google_purchase_token"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

    @property
    def is_active(self):
        if self.status != "active":
            return False
        # Check expires_date first (used by Apple/Google)
        if self.expires_date and self.expires_date < timezone.now():
            return False
        # Also check period_end for subscription tracking
        if self.period_end and self.period_end < timezone.now():
            return False
        return True


class FeatureUnlock(TimeStampedModel):
    """Unlocked features for users."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="unlocked_features"
    )
    
    # Feature identifier
    feature_key = models.CharField(max_length=50)
    feature_name = models.CharField(max_length=200)
    
    # Source
    purchase = models.ForeignKey(
        InAppPurchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unlocked_features"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Expiration (for time-limited unlocks)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "payments"
        verbose_name = "Feature Unlock"
        verbose_name_plural = "Feature Unlocks"
        unique_together = ["user", "feature_key"]

    def __str__(self):
        return f"{self.user.username} - {self.feature_name}"

    @property
    def is_currently_active(self):
        """Check if the feature unlock is currently active (considering expiration)."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
