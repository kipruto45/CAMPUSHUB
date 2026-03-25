"""
Admin configuration for payments app.
"""

from django.contrib import admin

from .models import (
    FeatureUnlock,
    InAppProduct,
    InAppPurchase,
    Invoice,
    Payment,
    Plan,
    PromoCode,
    StorageUpgrade,
    Subscription,
    UserCoupon,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "tier",
        "price_monthly",
        "price_yearly",
        "billing_period",
        "is_active",
        "is_featured",
    ]
    list_filter = ["tier", "billing_period", "is_active", "is_featured"]
    search_fields = ["name", "description", "stripe_product_id"]
    ordering = ["display_order", "name"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "plan",
        "status",
        "billing_period",
        "current_period_end",
        "cancel_at_period_end",
    ]
    list_filter = ["status", "billing_period", "cancel_at_period_end", "plan"]
    search_fields = [
        "user__email",
        "user__full_name",
        "stripe_subscription_id",
        "stripe_customer_id",
    ]
    autocomplete_fields = ["user", "plan"]
    ordering = ["-created_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "amount",
        "currency",
        "payment_type",
        "status",
        "created_at",
    ]
    list_filter = ["status", "payment_type", "currency", "created_at"]
    search_fields = [
        "user__email",
        "user__full_name",
        "stripe_payment_intent_id",
        "stripe_charge_id",
        "stripe_invoice_id",
    ]
    autocomplete_fields = ["user", "subscription"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(StorageUpgrade)
class StorageUpgradeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "storage_gb",
        "duration_days",
        "price",
        "status",
        "starts_at",
        "ends_at",
    ]
    list_filter = ["status", "storage_gb", "duration_days"]
    search_fields = ["user__email", "user__full_name", "stripe_subscription_id"]
    autocomplete_fields = ["user", "payment"]
    ordering = ["-created_at"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number",
        "user",
        "total_amount",
        "currency",
        "status",
        "due_date",
        "paid_at",
    ]
    list_filter = ["status", "currency", "due_date", "paid_at"]
    search_fields = [
        "invoice_number",
        "user__email",
        "user__full_name",
        "stripe_invoice_id",
    ]
    autocomplete_fields = ["user"]
    ordering = ["-created_at"]


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "discount_type",
        "discount_value",
        "max_uses",
        "current_uses",
        "valid_from",
        "valid_until",
        "is_active",
    ]
    list_filter = ["discount_type", "is_active", "valid_from", "valid_until"]
    search_fields = ["code", "description"]
    filter_horizontal = ["applicable_plans"]
    ordering = ["-created_at"]


@admin.register(UserCoupon)
class UserCouponAdmin(admin.ModelAdmin):
    list_display = ["user", "promo_code", "subscription", "discount_amount", "created_at"]
    list_filter = ["promo_code", "created_at"]
    search_fields = ["user__email", "promo_code__code"]
    autocomplete_fields = ["user", "promo_code", "subscription"]
    ordering = ["-created_at"]


@admin.register(InAppProduct)
class InAppProductAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "platform",
        "product_type",
        "subscription_type",
        "price",
        "currency",
        "tier",
        "is_available",
        "is_active",
    ]
    list_filter = ["platform", "product_type", "subscription_type", "is_active", "is_available"]
    search_fields = [
        "name",
        "apple_product_id",
        "google_product_id",
        "stripe_price_id",
        "feature_key",
    ]
    ordering = ["display_order", "name"]


@admin.register(InAppPurchase)
class InAppPurchaseAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "product",
        "platform",
        "status",
        "amount",
        "currency",
        "expires_date",
        "auto_renew_enabled",
    ]
    list_filter = ["platform", "status", "is_subscription", "auto_renew_enabled"]
    search_fields = [
        "user__email",
        "apple_transaction_id",
        "google_purchase_token",
        "original_transaction_id",
    ]
    autocomplete_fields = ["user", "product", "subscription"]
    ordering = ["-created_at"]


@admin.register(FeatureUnlock)
class FeatureUnlockAdmin(admin.ModelAdmin):
    list_display = ["user", "feature_key", "feature_name", "is_active", "expires_at"]
    list_filter = ["is_active", "expires_at"]
    search_fields = ["user__email", "feature_key", "feature_name"]
    autocomplete_fields = ["user", "purchase"]
    ordering = ["-created_at"]
