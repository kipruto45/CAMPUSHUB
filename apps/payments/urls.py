"""
Payment URL configuration.
"""

from django.urls import path

from . import views
from . import webhooks
from .receipts import ReceiptDownloadView

app_name = "payments"

urlpatterns = [
    # Plans
    path("plans/", views.PlanListView.as_view(), name="plans"),
    
    # Subscription
    path("subscription/", views.SubscriptionView.as_view(), name="subscription"),
    path("subscription/cancel/", views.SubscriptionCancelView.as_view(), name="subscription-cancel"),
    path("subscription/reactivate/", views.SubscriptionReactivateView.as_view(), name="subscription-reactivate"),
    
    # Billing
    path("portal/", views.BillingPortalView.as_view(), name="billing-portal"),
    path("payments/", views.PaymentHistoryView.as_view(), name="payment-history"),
    path("payments/status/", views.PaymentStatusView.as_view(), name="payment-status"),
    path("checkout/", views.PaymentCreateView.as_view(), name="payment-create"),
    path("providers/", views.PaymentProviderStatusView.as_view(), name="payment-providers"),
    path("limits/", views.subscription_limits, name="subscription-limits"),
    
    # Storage
    path("storage/", views.StorageUpgradeView.as_view(), name="storage-upgrades"),
    
    # Promo codes
    path("promo/", views.ApplyPromoCodeView.as_view(), name="apply-promo"),

    # In-app purchases
    path("in-app/products/", views.InAppProductListView.as_view(), name="in-app-products"),
    path("in-app/subscription/", views.InAppPurchaseSubscriptionView.as_view(), name="in-app-subscription"),
    path("in-app/subscribe/", views.InAppPurchaseSubscribeView.as_view(), name="in-app-subscribe"),
    path("in-app/restore/", views.InAppPurchaseRestoreView.as_view(), name="in-app-restore"),
    path("in-app/cancel/", views.InAppPurchaseCancelView.as_view(), name="in-app-cancel"),
    path("in-app/features/", views.FeatureUnlockListView.as_view(), name="in-app-features"),
    
    # Webhooks - Stripe
    path("webhook/stripe/", webhooks.StripeWebhookView.as_view(), name="stripe-webhook"),
    # Legacy webhook (auto-detect)
    path("webhook/", webhooks.PaymentWebhookSelectView.as_view(), name="webhook-auto"),
    
    # Webhooks - PayPal
    path("webhook/paypal/", webhooks.PayPalWebhookView.as_view(), name="paypal-webhook"),
    
    # Webhooks - Mobile Money
    path("webhook/mobile-money/", webhooks.MobileMoneyWebhookView.as_view(), name="mobile-money-webhook"),
    
    # Webhooks - In-App Purchases (Apple/Google)
    path("webhook/apple/", webhooks.AppleWebhookView.as_view(), name="apple-webhook"),
    path("webhook/google/", webhooks.GoogleWebhookView.as_view(), name="google-webhook"),
    
    # Receipt download - secure, time-limited URL
    path("receipt/<uuid:payment_id>/download/", ReceiptDownloadView.get_receipt, name="receipt-download"),

    # Freemium Tier Endpoints
    path("tiers/", views.TierListView.as_view(), name="tiers"),
    path("tiers/user/", views.UserTierView.as_view(), name="user-tier"),
    path("feature-access/", views.FeatureAccessView.as_view(), name="feature-access"),
    path("trial/", views.TrialStartView.as_view(), name="trial-start"),
]
