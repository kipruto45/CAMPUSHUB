"""
Freemium model with tiered access for CampusHub.

This module defines feature access for each tier:
- Free tier: Basic features (calendar, announcements, basic library)
- Premium tier ($9.99/mo): +AI features, advanced analytics, more storage
- Pro tier ($19.99/mo): +All integrations, priority support, certificates
- Enterprise tier (custom): +White-label, API access, dedicated support
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from django.utils import timezone
from datetime import timedelta


class Tier(str, Enum):
    """Subscription tier levels."""
    FREE = "free"
    PREMIUM = "premium"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Feature(str, Enum):
    """Available features in the platform."""
    # Core features (Free)
    CALENDAR = "calendar"
    ANNOUNCEMENTS = "announcements"
    BASIC_LIBRARY = "basic_library"
    PROFILE = "profile"
    MESSAGING = "messaging"
    NOTIFICATIONS = "notifications"
    
    # Premium features
    AI_FEATURES = "ai_features"
    AI_SUMMARIZATION = "ai_summarization"
    AI_CHAT = "ai_chat"
    ADVANCED_ANALYTICS = "advanced_analytics"
    EXTRA_STORAGE = "extra_storage"
    NO_ADS = "no_ads"
    
    # Pro features
    ALL_INTEGRATIONS = "all_integrations"
    PRIORITY_SUPPORT = "priority_support"
    CERTIFICATES = "certificates"
    CUSTOM_TIMETABLES = "custom_timetables"
    EXPORT_DATA = "export_data"
    ADVANCED_SEARCH = "advanced_search"
    
    # Enterprise features
    WHITE_LABEL = "white_label"
    API_ACCESS = "api_access"
    DEDICATED_SUPPORT = "dedicated_support"
    SSO = "sso"
    AUDIT_LOGS = "audit_logs"
    CUSTOM_BRANDING = "custom_branding"
    BULK_OPERATIONS = "bulk_operations"
    ADVANCED_SECURITY = "advanced_security"


# Feature definitions with metadata
FEATURE_METADATA: Dict[Feature, dict] = {
    # Core features
    Feature.CALENDAR: {
        "name": "Calendar",
        "description": "Access to personal and academic calendar",
        "category": "core",
    },
    Feature.ANNOUNCEMENTS: {
        "name": "Announcements",
        "description": "View campus announcements and notifications",
        "category": "core",
    },
    Feature.BASIC_LIBRARY: {
        "name": "Basic Library",
        "description": "Access to basic library resources",
        "category": "core",
    },
    Feature.PROFILE: {
        "name": "Profile",
        "description": "User profile management",
        "category": "core",
    },
    Feature.MESSAGING: {
        "name": "Messaging",
        "description": "Send and receive messages",
        "category": "core",
    },
    Feature.NOTIFICATIONS: {
        "name": "Notifications",
        "description": "Push and email notifications",
        "category": "core",
    },
    
    # Premium features
    Feature.AI_FEATURES: {
        "name": "AI Features",
        "description": "Access to AI-powered features",
        "category": "premium",
    },
    Feature.AI_SUMMARIZATION: {
        "name": "AI Summarization",
        "description": "AI-powered content summarization",
        "category": "premium",
    },
    Feature.AI_CHAT: {
        "name": "AI Chat",
        "description": "AI assistant for Q&A",
        "category": "premium",
    },
    Feature.ADVANCED_ANALYTICS: {
        "name": "Advanced Analytics",
        "description": "Detailed analytics and insights",
        "category": "premium",
    },
    Feature.EXTRA_STORAGE: {
        "name": "Extra Storage",
        "description": "Additional cloud storage",
        "category": "premium",
    },
    Feature.NO_ADS: {
        "name": "No Ads",
        "description": "Ad-free experience",
        "category": "premium",
    },
    
    # Pro features
    Feature.ALL_INTEGRATIONS: {
        "name": "All Integrations",
        "description": "Access to all third-party integrations",
        "category": "pro",
    },
    Feature.PRIORITY_SUPPORT: {
        "name": "Priority Support",
        "description": "Get help faster with priority support",
        "category": "pro",
    },
    Feature.CERTIFICATES: {
        "name": "Certificates",
        "description": "Generate and download certificates",
        "category": "pro",
    },
    Feature.CUSTOM_TIMETABLES: {
        "name": "Custom Timetables",
        "description": "Create custom timetables and schedules",
        "category": "pro",
    },
    Feature.EXPORT_DATA: {
        "name": "Export Data",
        "description": "Export your data in various formats",
        "category": "pro",
    },
    Feature.ADVANCED_SEARCH: {
        "name": "Advanced Search",
        "description": "Advanced search with filters",
        "category": "pro",
    },
    
    # Enterprise features
    Feature.WHITE_LABEL: {
        "name": "White Label",
        "description": "Custom branded experience",
        "category": "enterprise",
    },
    Feature.API_ACCESS: {
        "name": "API Access",
        "description": "Programmatic access to platform",
        "category": "enterprise",
    },
    Feature.DEDICATED_SUPPORT: {
        "name": "Dedicated Support",
        "description": "24/7 dedicated support",
        "category": "enterprise",
    },
    Feature.SSO: {
        "name": "Single Sign-On",
        "description": "SSO integration with identity providers",
        "category": "enterprise",
    },
    Feature.AUDIT_LOGS: {
        "name": "Audit Logs",
        "description": "Comprehensive audit trail",
        "category": "enterprise",
    },
    Feature.CUSTOM_BRANDING: {
        "name": "Custom Branding",
        "description": "Full custom branding options",
        "category": "enterprise",
    },
    Feature.BULK_OPERATIONS: {
        "name": "Bulk Operations",
        "description": "Perform bulk user operations",
        "category": "enterprise",
    },
    Feature.ADVANCED_SECURITY: {
        "name": "Advanced Security",
        "description": "Enhanced security features",
        "category": "enterprise",
    },
}


# Tier feature mappings
TIER_FEATURES: Dict[Tier, Set[Feature]] = {
    Tier.FREE: {
        Feature.CALENDAR,
        Feature.ANNOUNCEMENTS,
        Feature.BASIC_LIBRARY,
        Feature.PROFILE,
        Feature.MESSAGING,
        Feature.NOTIFICATIONS,
    },
    Tier.PREMIUM: {
        Feature.CALENDAR,
        Feature.ANNOUNCEMENTS,
        Feature.BASIC_LIBRARY,
        Feature.PROFILE,
        Feature.MESSAGING,
        Feature.NOTIFICATIONS,
        Feature.AI_FEATURES,
        Feature.AI_SUMMARIZATION,
        Feature.AI_CHAT,
        Feature.ADVANCED_ANALYTICS,
        Feature.EXTRA_STORAGE,
        Feature.NO_ADS,
    },
    Tier.PRO: {
        Feature.CALENDAR,
        Feature.ANNOUNCEMENTS,
        Feature.BASIC_LIBRARY,
        Feature.PROFILE,
        Feature.MESSAGING,
        Feature.NOTIFICATIONS,
        Feature.AI_FEATURES,
        Feature.AI_SUMMARIZATION,
        Feature.AI_CHAT,
        Feature.ADVANCED_ANALYTICS,
        Feature.EXTRA_STORAGE,
        Feature.NO_ADS,
        Feature.ALL_INTEGRATIONS,
        Feature.PRIORITY_SUPPORT,
        Feature.CERTIFICATES,
        Feature.CUSTOM_TIMETABLES,
        Feature.EXPORT_DATA,
        Feature.ADVANCED_SEARCH,
    },
    Tier.ENTERPRISE: {
        Feature.CALENDAR,
        Feature.ANNOUNCEMENTS,
        Feature.BASIC_LIBRARY,
        Feature.PROFILE,
        Feature.MESSAGING,
        Feature.NOTIFICATIONS,
        Feature.AI_FEATURES,
        Feature.AI_SUMMARIZATION,
        Feature.AI_CHAT,
        Feature.ADVANCED_ANALYTICS,
        Feature.EXTRA_STORAGE,
        Feature.NO_ADS,
        Feature.ALL_INTEGRATIONS,
        Feature.PRIORITY_SUPPORT,
        Feature.CERTIFICATES,
        Feature.CUSTOM_TIMETABLES,
        Feature.EXPORT_DATA,
        Feature.ADVANCED_SEARCH,
        Feature.WHITE_LABEL,
        Feature.API_ACCESS,
        Feature.DEDICATED_SUPPORT,
        Feature.SSO,
        Feature.AUDIT_LOGS,
        Feature.CUSTOM_BRANDING,
        Feature.BULK_OPERATIONS,
        Feature.ADVANCED_SECURITY,
    },
}


# Tier pricing
TIER_PRICING: Dict[Tier, dict] = {
    Tier.FREE: {
        "monthly": 0,
        "yearly": 0,
        "price_id": None,
    },
    Tier.PREMIUM: {
        "monthly": 9.99,
        "yearly": 99.99,
        "price_id": "price_premium_monthly",  # Stripe price ID
    },
    Tier.PRO: {
        "monthly": 19.99,
        "yearly": 199.99,
        "price_id": "price_pro_monthly",  # Stripe price ID
    },
    Tier.ENTERPRISE: {
        "monthly": "custom",
        "yearly": "custom",
        "price_id": None,
    },
}


# Storage limits per tier (in GB)
TIER_STORAGE_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 1,
    Tier.PREMIUM: 10,
    Tier.PRO: 50,
    Tier.ENTERPRISE: 500,
}


# Download limits per tier (monthly)
TIER_DOWNLOAD_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 50,
    Tier.PREMIUM: 500,
    Tier.PRO: -1,  # Unlimited
    Tier.ENTERPRISE: -1,  # Unlimited
}


# Trial configuration
TRIAL_CONFIG: dict = {
    "duration_days": 7,
    "tier": Tier.PREMIUM,
    "max_trials_per_user": 1,
}


@dataclass
class TierInfo:
    """Information about a subscription tier."""
    tier: Tier
    name: str
    description: str
    price_monthly: float
    price_yearly: float
    features: List[Feature]
    storage_limit_gb: int
    download_limit_monthly: int
    is_popular: bool = False
    
    def to_dict(self) -> dict:
        return {
            "tier": self.tier.value,
            "name": self.name,
            "description": self.description,
            "price_monthly": self.price_monthly,
            "price_yearly": self.price_yearly,
            "features": [f.value for f in self.features],
            "feature_details": [
                {
                    "key": f.value,
                    "name": FEATURE_METADATA[f]["name"],
                    "description": FEATURE_METADATA[f]["description"],
                    "category": FEATURE_METADATA[f]["category"],
                }
                for f in self.features
            ],
            "storage_limit_gb": self.storage_limit_gb,
            "download_limit_monthly": self.download_limit_monthly,
            "is_popular": self.is_popular,
        }


# Predefined tier information
TIER_INFO: Dict[Tier, TierInfo] = {
    Tier.FREE: TierInfo(
        tier=Tier.FREE,
        name="Free",
        description="Basic features for everyday use",
        price_monthly=0,
        price_yearly=0,
        features=list(TIER_FEATURES[Tier.FREE]),
        storage_limit_gb=TIER_STORAGE_LIMITS[Tier.FREE],
        download_limit_monthly=TIER_DOWNLOAD_LIMITS[Tier.FREE],
    ),
    Tier.PREMIUM: TierInfo(
        tier=Tier.PREMIUM,
        name="Premium",
        description="Unlock AI features and advanced analytics",
        price_monthly=9.99,
        price_yearly=99.99,
        features=list(TIER_FEATURES[Tier.PREMIUM]),
        storage_limit_gb=TIER_STORAGE_LIMITS[Tier.PREMIUM],
        download_limit_monthly=TIER_DOWNLOAD_LIMITS[Tier.PREMIUM],
        is_popular=True,
    ),
    Tier.PRO: TierInfo(
        tier=Tier.PRO,
        name="Pro",
        description="All integrations and priority support",
        price_monthly=19.99,
        price_yearly=199.99,
        features=list(TIER_FEATURES[Tier.PRO]),
        storage_limit_gb=TIER_STORAGE_LIMITS[Tier.PRO],
        download_limit_monthly=TIER_DOWNLOAD_LIMITS[Tier.PRO],
    ),
    Tier.ENTERPRISE: TierInfo(
        tier=Tier.ENTERPRISE,
        name="Enterprise",
        description="Custom solutions for organizations",
        price_monthly=0,  # Custom pricing
        price_yearly=0,
        features=list(TIER_FEATURES[Tier.ENTERPRISE]),
        storage_limit_gb=TIER_STORAGE_LIMITS[Tier.ENTERPRISE],
        download_limit_monthly=TIER_DOWNLOAD_LIMITS[Tier.ENTERPRISE],
    ),
}


def get_tier_from_string(tier_str: str) -> Tier:
    """Convert string to Tier enum."""
    tier_str = tier_str.lower()
    for tier in Tier:
        if tier.value == tier_str:
            return tier
    return Tier.FREE


def get_user_tier(user) -> Tier:
    """
    Get the current tier for a user.
    
    Checks user's subscription status and returns appropriate tier.
    """
    from .models import Subscription, Plan
    
    if not user or not user.is_authenticated:
        return Tier.FREE
    
    try:
        # Get active subscription
        subscription = Subscription.objects.filter(
            user=user,
            status__in=["active", "trialing"]
        ).select_related("plan").first()
        
        if subscription and subscription.plan:
            return get_tier_from_string(subscription.plan.tier)
    except Exception:
        pass
    
    return Tier.FREE


def has_feature(user, feature: Feature) -> bool:
    """
    Check if a user has access to a specific feature.
    
    Args:
        user: The user to check
        feature: The feature to check access for
        
    Returns:
        True if user has access to the feature
    """
    if not user or not user.is_authenticated:
        # Unauthenticated users only get free features
        return feature in TIER_FEATURES[Tier.FREE]
    
    user_tier = get_user_tier(user)
    return feature in TIER_FEATURES[user_tier]


def get_user_features(user) -> Set[Feature]:
    """Get all features available to a user based on their tier."""
    user_tier = get_user_tier(user)
    return TIER_FEATURES[user_tier].copy()


def get_user_tier_info(user) -> Optional[TierInfo]:
    """Get detailed tier information for a user."""
    user_tier = get_user_tier(user)
    return TIER_INFO.get(user_tier)


def can_access_feature(user, feature: Feature) -> tuple[bool, Optional[str]]:
    """
    Check if user can access a feature, return (has_access, reason).
    
    Returns:
        tuple: (has_access, reason_if_denied)
    """
    if has_feature(user, feature):
        return True, None
    
    # Determine why access was denied
    user_tier = get_user_tier(user)
    
    # Find the lowest tier that has this feature
    for tier in [Tier.ENTERPRISE, Tier.PRO, Tier.PREMIUM]:
        if feature in TIER_FEATURES[tier]:
            return False, f"Upgrade to {tier.value.capitalize()} to access this feature"
    
    return False, "This feature is not available"


def get_trial_eligibility(user) -> dict:
    """
    Check if user is eligible for a trial.
    
    Returns:
        dict with eligibility status and details
    """
    from .models import Subscription
    
    if not user or not user.is_authenticated:
        return {
            "eligible": False,
            "reason": "Must be logged in to start a trial",
        }
    
    # Check if user already had a trial
    trial_count = Subscription.objects.filter(
        user=user,
        status="trialing"
    ).count()
    
    if trial_count >= TRIAL_CONFIG["max_trials_per_user"]:
        return {
            "eligible": False,
            "reason": "You have already used your trial",
        }
    
    # Check if user has active subscription
    active_sub = Subscription.objects.filter(
        user=user,
        status="active"
    ).exists()
    
    if active_sub:
        return {
            "eligible": False,
            "reason": "You already have an active subscription",
        }
    
    return {
        "eligible": True,
        "tier": TRIAL_CONFIG["tier"].value,
        "duration_days": TRIAL_CONFIG["duration_days"],
    }


def get_feature_access_summary(user) -> dict:
    """
    Get a summary of feature access for a user.
    
    Returns:
        dict with tier info and feature access details
    """
    user_tier = get_user_tier(user)
    user_features = get_user_features(user)
    
    # Categorize features
    categories = {
        "core": [],
        "premium": [],
        "pro": [],
        "enterprise": [],
    }
    
    for feature in Feature:
        has_access = feature in user_features
        categories[FEATURE_METADATA[feature]["category"]].append({
            "key": feature.value,
            "name": FEATURE_METADATA[feature]["name"],
            "description": FEATURE_METADATA[feature]["description"],
            "available": has_access,
        })
    
    return {
        "tier": user_tier.value,
        "tier_name": TIER_INFO[user_tier].name,
        "storage_limit_gb": TIER_STORAGE_LIMITS[user_tier],
        "download_limit_monthly": TIER_DOWNLOAD_LIMITS[user_tier],
        "features": user_features,
        "categories": categories,
    }
