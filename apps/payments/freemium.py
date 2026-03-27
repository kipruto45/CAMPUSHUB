"""
Freemium and entitlement helpers for CampusHub.

This module keeps subscription tiers, feature access, and role-based trial
policies in one place so the backend and mobile apps can make the same
decisions.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from django.db import models
from django.utils import timezone


class Tier(str, Enum):
    """Subscription tier levels used across the product."""

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class Feature(str, Enum):
    """Available features in the platform."""

    # Core features (Free - limited)
    CALENDAR = "calendar"
    ANNOUNCEMENTS = "announcements"
    BASIC_LIBRARY = "basic_library"
    PROFILE = "profile"
    MESSAGING = "messaging"
    NOTIFICATIONS = "notifications"

    # Basic plan features
    AI_FEATURES = "ai_features"
    AI_SUMMARIZATION = "ai_summarization"
    AI_CHAT = "ai_chat"
    ADVANCED_ANALYTICS = "advanced_analytics"
    EXTRA_STORAGE = "extra_storage"
    NO_ADS = "no_ads"
    UNLIMITED_DOWNLOADS = "unlimited_downloads"
    UNLIMITED_UPLOADS = "unlimited_uploads"
    UNLIMITED_MESSAGES = "unlimited_messages"
    UNLIMITED_GROUPS = "unlimited_groups"
    ADVANCED_SEARCH_FILTERS = "advanced_search_filters"
    INSTANT_NOTIFICATIONS = "instant_notifications"
    PRIORITY_ACCESS = "priority_access"
    NO_WATERMARKS = "no_watermarks"
    CUSTOM_FOLDERS = "custom_folders"
    RECURRING_EVENTS = "recurring_events"
    CALENDAR_SHARING = "calendar_sharing"
    RICH_TEXT_EDITING = "rich_text_editing"
    COLLABORATIVE_EDITING = "collaborative_editing"
    VERSION_HISTORY = "version_history"
    LEADERBOARD_PRIZES = "leaderboard_prizes"
    ACHIEVEMENT_SHARING = "achievement_sharing"
    DAILY_STREAK_REWARDS = "daily_streak_rewards"
    EMAIL_DIGEST = "email_digest"
    PUSH_NOTIFICATIONS_FEATURE = "push_notifications_feature"
    PROFILE_VERIFICATION = "profile_verification"
    CUSTOM_USERNAME = "custom_username"
    THEME_CUSTOMIZATION = "theme_customization"
    PRIVACY_CONTROLS = "privacy_controls"
    STUDY_SCHEDULES = "study_schedules"
    BULK_UPLOADS = "bulk_uploads"
    PRIVATE_UPLOADS = "private_uploads"
    UPLOAD_APPROVAL = "upload_approval"
    RESOURCE_REQUESTS = "resource_requests"
    DOWNLOAD_TRACKING = "download_tracking"
    RATING_BREAKDOWN = "rating_breakdown"
    USAGE_STATISTICS = "usage_statistics"
    COMPARISON_STATS = "comparison_stats"
    EXPORT_REPORTS = "export_reports"
    LIVE_CHAT = "live_chat"
    PHONE_SUPPORT = "phone_support"
    PRIORITY_RESPONSE = "priority_response"

    # Premium plan features
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


FEATURE_METADATA: Dict[Feature, dict] = {
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
    Feature.AI_FEATURES: {
        "name": "AI Features",
        "description": "Access to AI-powered features",
        "category": "basic",
    },
    Feature.AI_SUMMARIZATION: {
        "name": "AI Summarization",
        "description": "AI-powered content summarization",
        "category": "basic",
    },
    Feature.AI_CHAT: {
        "name": "AI Chat",
        "description": "AI assistant for Q&A",
        "category": "basic",
    },
    Feature.ADVANCED_ANALYTICS: {
        "name": "Advanced Analytics",
        "description": "Detailed analytics and insights",
        "category": "basic",
    },
    Feature.EXTRA_STORAGE: {
        "name": "Extra Storage",
        "description": "Additional cloud storage",
        "category": "basic",
    },
    Feature.NO_ADS: {
        "name": "No Ads",
        "description": "Ad-free experience",
        "category": "basic",
    },
    Feature.UNLIMITED_DOWNLOADS: {
        "name": "Unlimited Downloads",
        "description": "Download unlimited resources per month",
        "category": "basic",
    },
    Feature.UNLIMITED_UPLOADS: {
        "name": "Unlimited Uploads",
        "description": "Upload unlimited resources per month",
        "category": "basic",
    },
    Feature.UNLIMITED_MESSAGES: {
        "name": "Unlimited Messages",
        "description": "Send unlimited messages per day",
        "category": "basic",
    },
    Feature.UNLIMITED_GROUPS: {
        "name": "Unlimited Groups",
        "description": "Join unlimited study groups",
        "category": "basic",
    },
    Feature.ADVANCED_SEARCH_FILTERS: {
        "name": "Advanced Search Filters",
        "description": "Filter by date, rating, file type, and more",
        "category": "basic",
    },
    Feature.INSTANT_NOTIFICATIONS: {
        "name": "Instant Notifications",
        "description": "Receive notifications instantly",
        "category": "basic",
    },
    Feature.PRIORITY_ACCESS: {
        "name": "Priority Access",
        "description": "Instant access to new resources",
        "category": "basic",
    },
    Feature.NO_WATERMARKS: {
        "name": "No Watermarks",
        "description": "Download clean files without watermarks",
        "category": "basic",
    },
    Feature.CUSTOM_FOLDERS: {
        "name": "Custom Folders",
        "description": "Organize resources into folders",
        "category": "basic",
    },
    Feature.RECURRING_EVENTS: {
        "name": "Recurring Events",
        "description": "Create repeating calendar events",
        "category": "basic",
    },
    Feature.CALENDAR_SHARING: {
        "name": "Calendar Sharing",
        "description": "Share calendar with classmates",
        "category": "basic",
    },
    Feature.RICH_TEXT_EDITING: {
        "name": "Rich Text Editing",
        "description": "Format documents with rich text",
        "category": "basic",
    },
    Feature.COLLABORATIVE_EDITING: {
        "name": "Collaborative Editing",
        "description": "Co-edit documents with others",
        "category": "basic",
    },
    Feature.VERSION_HISTORY: {
        "name": "Version History",
        "description": "Track previous versions of uploads",
        "category": "basic",
    },
    Feature.LEADERBOARD_PRIZES: {
        "name": "Leaderboard Prizes",
        "description": "Win rewards for top leaderboard positions",
        "category": "basic",
    },
    Feature.ACHIEVEMENT_SHARING: {
        "name": "Achievement Sharing",
        "description": "Share achievements on social media",
        "category": "basic",
    },
    Feature.DAILY_STREAK_REWARDS: {
        "name": "Daily Streak Rewards",
        "description": "Get rewards for daily login streaks",
        "category": "basic",
    },
    Feature.EMAIL_DIGEST: {
        "name": "Email Digest",
        "description": "Get daily/weekly email summaries",
        "category": "basic",
    },
    Feature.PUSH_NOTIFICATIONS_FEATURE: {
        "name": "Push Notifications",
        "description": "Receive push notifications for new resources",
        "category": "basic",
    },
    Feature.PROFILE_VERIFICATION: {
        "name": "Profile Verification",
        "description": "Get verified status badge",
        "category": "basic",
    },
    Feature.CUSTOM_USERNAME: {
        "name": "Custom Username",
        "description": "Set a custom username",
        "category": "basic",
    },
    Feature.THEME_CUSTOMIZATION: {
        "name": "Theme Customization",
        "description": "Customize app theme and colors",
        "category": "basic",
    },
    Feature.PRIVACY_CONTROLS: {
        "name": "Privacy Controls",
        "description": "Hide online status and activity",
        "category": "basic",
    },
    Feature.STUDY_SCHEDULES: {
        "name": "Study Schedules",
        "description": "Create custom study schedules",
        "category": "basic",
    },
    Feature.BULK_UPLOADS: {
        "name": "Bulk Uploads",
        "description": "Upload multiple files at once",
        "category": "basic",
    },
    Feature.PRIVATE_UPLOADS: {
        "name": "Private Uploads",
        "description": "Upload resources privately",
        "category": "basic",
    },
    Feature.UPLOAD_APPROVAL: {
        "name": "Upload Approval",
        "description": "Skip admin approval for uploads",
        "category": "basic",
    },
    Feature.RESOURCE_REQUESTS: {
        "name": "Resource Requests",
        "description": "Request specific resources from others",
        "category": "basic",
    },
    Feature.DOWNLOAD_TRACKING: {
        "name": "Download Tracking",
        "description": "See who downloaded your uploads",
        "category": "basic",
    },
    Feature.RATING_BREAKDOWN: {
        "name": "Rating Breakdown",
        "description": "See detailed rating distribution",
        "category": "basic",
    },
    Feature.USAGE_STATISTICS: {
        "name": "Usage Statistics",
        "description": "View how often your resources are viewed",
        "category": "basic",
    },
    Feature.COMPARISON_STATS: {
        "name": "Comparison Stats",
        "description": "Compare your stats to campus averages",
        "category": "basic",
    },
    Feature.EXPORT_REPORTS: {
        "name": "Export Reports",
        "description": "Download your activity reports",
        "category": "basic",
    },
    Feature.LIVE_CHAT: {
        "name": "Live Chat",
        "description": "Use in-app support chat",
        "category": "basic",
    },
    Feature.PHONE_SUPPORT: {
        "name": "Phone Support",
        "description": "Call support line",
        "category": "basic",
    },
    Feature.PRIORITY_RESPONSE: {
        "name": "Priority Response",
        "description": "Get faster support response times",
        "category": "basic",
    },
    Feature.AI_SUMMARIZATION: {
        "name": "AI Summarization",
        "description": "AI-powered content summarization",
        "category": "basic",
    },
    Feature.AI_CHAT: {
        "name": "AI Chat",
        "description": "AI assistant for Q&A",
        "category": "basic",
    },
    Feature.ADVANCED_ANALYTICS: {
        "name": "Advanced Analytics",
        "description": "Detailed analytics and insights",
        "category": "basic",
    },
    Feature.EXTRA_STORAGE: {
        "name": "Extra Storage",
        "description": "Additional cloud storage",
        "category": "basic",
    },
    Feature.NO_ADS: {
        "name": "No Ads",
        "description": "Ad-free experience",
        "category": "basic",
    },
    Feature.ALL_INTEGRATIONS: {
        "name": "All Integrations",
        "description": "Access to all third-party integrations",
        "category": "premium",
    },
    Feature.PRIORITY_SUPPORT: {
        "name": "Priority Support",
        "description": "Get help faster with priority support",
        "category": "premium",
    },
    Feature.CERTIFICATES: {
        "name": "Certificates",
        "description": "Generate and download certificates",
        "category": "premium",
    },
    Feature.CUSTOM_TIMETABLES: {
        "name": "Custom Timetables",
        "description": "Create custom timetables and schedules",
        "category": "premium",
    },
    Feature.EXPORT_DATA: {
        "name": "Export Data",
        "description": "Export your data in various formats",
        "category": "premium",
    },
    Feature.ADVANCED_SEARCH: {
        "name": "Advanced Search",
        "description": "Advanced search with filters",
        "category": "premium",
    },
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


TIER_FEATURES: Dict[Tier, Set[Feature]] = {
    Tier.FREE: {
        Feature.CALENDAR,
        Feature.ANNOUNCEMENTS,
        Feature.BASIC_LIBRARY,
        Feature.PROFILE,
        Feature.MESSAGING,
        Feature.NOTIFICATIONS,
    },
    Tier.BASIC: {
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
        Feature.ADVANCED_SEARCH_FILTERS,
        Feature.INSTANT_NOTIFICATIONS,
        Feature.PRIORITY_ACCESS,
        Feature.NO_WATERMARKS,
        Feature.CUSTOM_FOLDERS,
        Feature.RECURRING_EVENTS,
        Feature.CALENDAR_SHARING,
        Feature.RICH_TEXT_EDITING,
        Feature.COLLABORATIVE_EDITING,
        Feature.VERSION_HISTORY,
        Feature.LEADERBOARD_PRIZES,
        Feature.ACHIEVEMENT_SHARING,
        Feature.DAILY_STREAK_REWARDS,
        Feature.EMAIL_DIGEST,
        Feature.PUSH_NOTIFICATIONS_FEATURE,
        Feature.PROFILE_VERIFICATION,
        Feature.CUSTOM_USERNAME,
        Feature.THEME_CUSTOMIZATION,
        Feature.PRIVACY_CONTROLS,
        Feature.STUDY_SCHEDULES,
        Feature.BULK_UPLOADS,
        Feature.PRIVATE_UPLOADS,
        Feature.UPLOAD_APPROVAL,
        Feature.RESOURCE_REQUESTS,
        Feature.DOWNLOAD_TRACKING,
        Feature.RATING_BREAKDOWN,
        Feature.USAGE_STATISTICS,
        Feature.COMPARISON_STATS,
        Feature.EXPORT_REPORTS,
        Feature.LIVE_CHAT,
        Feature.PHONE_SUPPORT,
        Feature.PRIORITY_RESPONSE,
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
        Feature.ADVANCED_SEARCH_FILTERS,
        Feature.INSTANT_NOTIFICATIONS,
        Feature.PRIORITY_ACCESS,
        Feature.NO_WATERMARKS,
        Feature.CUSTOM_FOLDERS,
        Feature.RECURRING_EVENTS,
        Feature.CALENDAR_SHARING,
        Feature.RICH_TEXT_EDITING,
        Feature.COLLABORATIVE_EDITING,
        Feature.VERSION_HISTORY,
        Feature.LEADERBOARD_PRIZES,
        Feature.ACHIEVEMENT_SHARING,
        Feature.DAILY_STREAK_REWARDS,
        Feature.EMAIL_DIGEST,
        Feature.PUSH_NOTIFICATIONS_FEATURE,
        Feature.PROFILE_VERIFICATION,
        Feature.CUSTOM_USERNAME,
        Feature.THEME_CUSTOMIZATION,
        Feature.PRIVACY_CONTROLS,
        Feature.STUDY_SCHEDULES,
        Feature.BULK_UPLOADS,
        Feature.PRIVATE_UPLOADS,
        Feature.UPLOAD_APPROVAL,
        Feature.RESOURCE_REQUESTS,
        Feature.DOWNLOAD_TRACKING,
        Feature.RATING_BREAKDOWN,
        Feature.USAGE_STATISTICS,
        Feature.COMPARISON_STATS,
        Feature.EXPORT_REPORTS,
        Feature.LIVE_CHAT,
        Feature.PHONE_SUPPORT,
        Feature.PRIORITY_RESPONSE,
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
        Feature.UNLIMITED_DOWNLOADS,
        Feature.UNLIMITED_UPLOADS,
        Feature.UNLIMITED_MESSAGES,
        Feature.UNLIMITED_GROUPS,
        Feature.ADVANCED_SEARCH_FILTERS,
        Feature.INSTANT_NOTIFICATIONS,
        Feature.PRIORITY_ACCESS,
        Feature.NO_WATERMARKS,
        Feature.CUSTOM_FOLDERS,
        Feature.RECURRING_EVENTS,
        Feature.CALENDAR_SHARING,
        Feature.RICH_TEXT_EDITING,
        Feature.COLLABORATIVE_EDITING,
        Feature.VERSION_HISTORY,
        Feature.LEADERBOARD_PRIZES,
        Feature.ACHIEVEMENT_SHARING,
        Feature.DAILY_STREAK_REWARDS,
        Feature.EMAIL_DIGEST,
        Feature.PUSH_NOTIFICATIONS_FEATURE,
        Feature.PROFILE_VERIFICATION,
        Feature.CUSTOM_USERNAME,
        Feature.THEME_CUSTOMIZATION,
        Feature.PRIVACY_CONTROLS,
        Feature.STUDY_SCHEDULES,
        Feature.BULK_UPLOADS,
        Feature.PRIVATE_UPLOADS,
        Feature.UPLOAD_APPROVAL,
        Feature.RESOURCE_REQUESTS,
        Feature.DOWNLOAD_TRACKING,
        Feature.RATING_BREAKDOWN,
        Feature.USAGE_STATISTICS,
        Feature.COMPARISON_STATS,
        Feature.EXPORT_REPORTS,
        Feature.LIVE_CHAT,
        Feature.PHONE_SUPPORT,
        Feature.PRIORITY_RESPONSE,
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


TIER_PRICING: Dict[Tier, dict] = {
    Tier.FREE: {"monthly": 0, "yearly": 0, "price_id": None},
    Tier.BASIC: {"monthly": 5.99, "yearly": 59.99, "price_id": "price_basic_monthly"},
    Tier.PREMIUM: {
        "monthly": 12.00,
        "yearly": 120.00,
        "price_id": "price_premium_monthly",
    },
    Tier.ENTERPRISE: {
        "monthly": 49.00,
        "yearly": 490.00,
        "price_id": None,
    },
}


TIER_MAX_UPLOAD_SIZE_MB: Dict[Tier, int] = {
    Tier.FREE: 8,
    Tier.BASIC: 40,
    Tier.PREMIUM: 150,
    Tier.ENTERPRISE: 512,
}


TIER_STORAGE_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 1,
    Tier.BASIC: 8,
    Tier.PREMIUM: 40,
    Tier.ENTERPRISE: 500,
}


TIER_DOWNLOAD_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 25,
    Tier.BASIC: 250,
    Tier.PREMIUM: 1500,
    Tier.ENTERPRISE: -1,
}


TIER_UPLOAD_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 4,
    Tier.BASIC: 40,
    Tier.PREMIUM: 180,
    Tier.ENTERPRISE: -1,
}


TIER_MESSAGE_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 8,
    Tier.BASIC: 120,
    Tier.PREMIUM: 500,
    Tier.ENTERPRISE: -1,
}


TIER_GROUP_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 2,
    Tier.BASIC: 8,
    Tier.PREMIUM: 30,
    Tier.ENTERPRISE: -1,
}


TIER_BOOKMARK_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 15,
    Tier.BASIC: 120,
    Tier.PREMIUM: 500,
    Tier.ENTERPRISE: -1,
}


TIER_EVENT_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 6,
    Tier.BASIC: 40,
    Tier.PREMIUM: 200,
    Tier.ENTERPRISE: -1,
}


TIER_POINTS_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 250,
    Tier.BASIC: 5000,
    Tier.PREMIUM: 25000,
    Tier.ENTERPRISE: -1,
}


TIER_BADGE_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 3,
    Tier.BASIC: 20,
    Tier.PREMIUM: -1,
    Tier.ENTERPRISE: -1,
}


TIER_SEARCH_RESULTS_LIMITS: Dict[Tier, int] = {
    Tier.FREE: 6,
    Tier.BASIC: 30,
    Tier.PREMIUM: 100,
    Tier.ENTERPRISE: -1,
}


TIER_NOTIFICATION_DELAY_HOURS: Dict[Tier, int] = {
    Tier.FREE: 6,
    Tier.BASIC: 1,
    Tier.PREMIUM: 0,
    Tier.ENTERPRISE: 0,
}


TIER_SUPPORT_RESPONSE_HOURS: Dict[Tier, int] = {
    Tier.FREE: 72,
    Tier.BASIC: 24,
    Tier.PREMIUM: 8,
    Tier.ENTERPRISE: 1,
}


TRIAL_LIMIT_OVERRIDES: Dict[Tier, dict] = {
    Tier.BASIC: {
        "storage_gb": 2,
        "max_upload_mb": 20,
        "downloads_monthly": 80,
        "unlimited_downloads": False,
        "upload_limit_monthly": 12,
        "message_limit_daily": 40,
        "group_limit": 3,
        "bookmark_limit": 40,
        "event_limit_monthly": 12,
        "points_limit_monthly": 1200,
        "badge_limit": 6,
        "search_results_limit": 12,
        "notification_delay_hours": 2,
        "support_response_hours": 48,
        "priority_support": False,
        "early_access": False,
    },
    Tier.PREMIUM: {
        "storage_gb": 12,
        "max_upload_mb": 80,
        "downloads_monthly": 320,
        "unlimited_downloads": False,
        "upload_limit_monthly": 30,
        "message_limit_daily": 120,
        "group_limit": 8,
        "bookmark_limit": 120,
        "event_limit_monthly": 40,
        "points_limit_monthly": 6000,
        "badge_limit": 18,
        "search_results_limit": 35,
        "notification_delay_hours": 1,
        "support_response_hours": 24,
        "priority_support": False,
        "early_access": False,
    },
}


TRIAL_FEATURE_EXCLUSIONS: Dict[Tier, Set[Feature]] = {
    Tier.BASIC: {
        Feature.EXPORT_REPORTS,
        Feature.LIVE_CHAT,
        Feature.PHONE_SUPPORT,
        Feature.PRIORITY_RESPONSE,
    },
    Tier.PREMIUM: {
        Feature.ALL_INTEGRATIONS,
        Feature.PRIORITY_SUPPORT,
        Feature.CERTIFICATES,
        Feature.EXPORT_DATA,
        Feature.LIVE_CHAT,
        Feature.PHONE_SUPPORT,
        Feature.PRIORITY_RESPONSE,
    },
}


PLAN_PROFILE_BY_TIER: Dict[Tier, dict] = {
    Tier.FREE: {
        "plan_type": "Starter",
        "ideal_for": "Light browsing, core calendar access, and occasional downloads.",
        "highlights": [
            "Core study tools",
            "Basic library access",
            "Announcements and calendar",
        ],
    },
    Tier.BASIC: {
        "plan_type": "Focus",
        "ideal_for": "Active students who need AI help and stronger daily limits.",
        "highlights": [
            "AI chat and summaries",
            "Analytics and folders",
            "Moderate creator limits",
        ],
    },
    Tier.PREMIUM: {
        "plan_type": "Power",
        "ideal_for": "Heavy contributors, study leaders, and serious daily use.",
        "highlights": [
            "Large upload and download caps",
            "Advanced search and certificates",
            "Priority perks and early access",
        ],
    },
    Tier.ENTERPRISE: {
        "plan_type": "Campus",
        "ideal_for": "Departments, teams, and institution-scale collaboration.",
        "highlights": [
            "Enterprise controls",
            "Unlimited collaboration workflows",
            "Dedicated operational support",
        ],
    },
}


TRIAL_CONFIG: dict = {
    "default_duration_days": 7,
    "max_trials_per_user": 1,
    "tier_by_role": {
        "student": Tier.BASIC,
        "admin": Tier.PREMIUM,
    },
}


ADMIN_ROLE_CODES = {
    "ADMIN",
    "MODERATOR",
    "SUPPORT_STAFF",
    "DEPARTMENT_HEAD",
    "INSTRUCTOR",
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
    upload_limit_monthly: int
    message_limit_daily: int
    group_limit: int
    bookmark_limit: int
    event_limit_monthly: int
    points_limit_monthly: int
    badge_limit: int
    search_results_limit: int
    notification_delay_hours: int
    support_response_hours: int
    is_popular: bool = False

    def to_dict(self) -> dict:
        profile = get_plan_profile(self.tier)
        return {
            "tier": self.tier.value,
            "name": self.name,
            "description": self.description,
            "plan_type": profile["plan_type"],
            "ideal_for": profile["ideal_for"],
            "highlights": profile["highlights"],
            "price_monthly": self.price_monthly,
            "price_yearly": self.price_yearly,
            "features": [feature.value for feature in self.features],
            "feature_details": [
                {
                    "key": feature.value,
                    "name": FEATURE_METADATA[feature]["name"],
                    "description": FEATURE_METADATA[feature]["description"],
                    "category": FEATURE_METADATA[feature]["category"],
                }
                for feature in self.features
            ],
            "storage_limit_gb": self.storage_limit_gb,
            "download_limit_monthly": self.download_limit_monthly,
            "upload_limit_monthly": self.upload_limit_monthly,
            "message_limit_daily": self.message_limit_daily,
            "group_limit": self.group_limit,
            "bookmark_limit": self.bookmark_limit,
            "event_limit_monthly": self.event_limit_monthly,
            "points_limit_monthly": self.points_limit_monthly,
            "badge_limit": self.badge_limit,
            "search_results_limit": self.search_results_limit,
            "notification_delay_hours": self.notification_delay_hours,
            "support_response_hours": self.support_response_hours,
            "is_popular": self.is_popular,
        }


TIER_INFO: Dict[Tier, TierInfo] = {
    Tier.FREE: TierInfo(
        tier=Tier.FREE,
        name="Free",
        description="Starter access with tighter limits for light use.",
        price_monthly=0,
        price_yearly=0,
        features=list(TIER_FEATURES[Tier.FREE]),
        storage_limit_gb=TIER_STORAGE_LIMITS[Tier.FREE],
        download_limit_monthly=TIER_DOWNLOAD_LIMITS[Tier.FREE],
        upload_limit_monthly=TIER_UPLOAD_LIMITS[Tier.FREE],
        message_limit_daily=TIER_MESSAGE_LIMITS[Tier.FREE],
        group_limit=TIER_GROUP_LIMITS[Tier.FREE],
        bookmark_limit=TIER_BOOKMARK_LIMITS[Tier.FREE],
        event_limit_monthly=TIER_EVENT_LIMITS[Tier.FREE],
        points_limit_monthly=TIER_POINTS_LIMITS[Tier.FREE],
        badge_limit=TIER_BADGE_LIMITS[Tier.FREE],
        search_results_limit=TIER_SEARCH_RESULTS_LIMITS[Tier.FREE],
        notification_delay_hours=TIER_NOTIFICATION_DELAY_HOURS[Tier.FREE],
        support_response_hours=TIER_SUPPORT_RESPONSE_HOURS[Tier.FREE],
    ),
    Tier.BASIC: TierInfo(
        tier=Tier.BASIC,
        name="Basic",
        description="Focused student plan with AI tools and stronger daily caps.",
        price_monthly=5.99,
        price_yearly=59.99,
        features=list(TIER_FEATURES[Tier.BASIC]),
        storage_limit_gb=TIER_STORAGE_LIMITS[Tier.BASIC],
        download_limit_monthly=TIER_DOWNLOAD_LIMITS[Tier.BASIC],
        upload_limit_monthly=TIER_UPLOAD_LIMITS[Tier.BASIC],
        message_limit_daily=TIER_MESSAGE_LIMITS[Tier.BASIC],
        group_limit=TIER_GROUP_LIMITS[Tier.BASIC],
        bookmark_limit=TIER_BOOKMARK_LIMITS[Tier.BASIC],
        event_limit_monthly=TIER_EVENT_LIMITS[Tier.BASIC],
        points_limit_monthly=TIER_POINTS_LIMITS[Tier.BASIC],
        badge_limit=TIER_BADGE_LIMITS[Tier.BASIC],
        search_results_limit=TIER_SEARCH_RESULTS_LIMITS[Tier.BASIC],
        notification_delay_hours=TIER_NOTIFICATION_DELAY_HOURS[Tier.BASIC],
        support_response_hours=TIER_SUPPORT_RESPONSE_HOURS[Tier.BASIC],
        is_popular=True,
    ),
    Tier.PREMIUM: TierInfo(
        tier=Tier.PREMIUM,
        name="Premium",
        description="Power-user plan with larger limits, certificates, and premium perks.",
        price_monthly=12.00,
        price_yearly=120.00,
        features=list(TIER_FEATURES[Tier.PREMIUM]),
        storage_limit_gb=TIER_STORAGE_LIMITS[Tier.PREMIUM],
        download_limit_monthly=TIER_DOWNLOAD_LIMITS[Tier.PREMIUM],
        upload_limit_monthly=TIER_UPLOAD_LIMITS[Tier.PREMIUM],
        message_limit_daily=TIER_MESSAGE_LIMITS[Tier.PREMIUM],
        group_limit=TIER_GROUP_LIMITS[Tier.PREMIUM],
        bookmark_limit=TIER_BOOKMARK_LIMITS[Tier.PREMIUM],
        event_limit_monthly=TIER_EVENT_LIMITS[Tier.PREMIUM],
        points_limit_monthly=TIER_POINTS_LIMITS[Tier.PREMIUM],
        badge_limit=TIER_BADGE_LIMITS[Tier.PREMIUM],
        search_results_limit=TIER_SEARCH_RESULTS_LIMITS[Tier.PREMIUM],
        notification_delay_hours=TIER_NOTIFICATION_DELAY_HOURS[Tier.PREMIUM],
        support_response_hours=TIER_SUPPORT_RESPONSE_HOURS[Tier.PREMIUM],
    ),
    Tier.ENTERPRISE: TierInfo(
        tier=Tier.ENTERPRISE,
        name="Enterprise",
        description="Institution-grade access for departments and high-scale collaboration.",
        price_monthly=49.00,
        price_yearly=490.00,
        features=list(TIER_FEATURES[Tier.ENTERPRISE]),
        storage_limit_gb=TIER_STORAGE_LIMITS[Tier.ENTERPRISE],
        download_limit_monthly=TIER_DOWNLOAD_LIMITS[Tier.ENTERPRISE],
        upload_limit_monthly=TIER_UPLOAD_LIMITS[Tier.ENTERPRISE],
        message_limit_daily=TIER_MESSAGE_LIMITS[Tier.ENTERPRISE],
        group_limit=TIER_GROUP_LIMITS[Tier.ENTERPRISE],
        bookmark_limit=TIER_BOOKMARK_LIMITS[Tier.ENTERPRISE],
        event_limit_monthly=TIER_EVENT_LIMITS[Tier.ENTERPRISE],
        points_limit_monthly=TIER_POINTS_LIMITS[Tier.ENTERPRISE],
        badge_limit=TIER_BADGE_LIMITS[Tier.ENTERPRISE],
        search_results_limit=TIER_SEARCH_RESULTS_LIMITS[Tier.ENTERPRISE],
        notification_delay_hours=TIER_NOTIFICATION_DELAY_HOURS[Tier.ENTERPRISE],
        support_response_hours=TIER_SUPPORT_RESPONSE_HOURS[Tier.ENTERPRISE],
    ),
}


def get_tier_from_string(tier_str: str) -> Tier:
    """Convert a raw tier string to the supported enum."""

    normalized = str(tier_str or "").strip().lower()
    for tier in Tier:
        if tier.value == normalized:
            return tier
    if normalized == "pro":
        return Tier.PREMIUM
    return Tier.FREE


def get_plan_profile(tier: Tier) -> dict:
    """Return presentation metadata for a plan tier."""

    profile = PLAN_PROFILE_BY_TIER.get(tier, PLAN_PROFILE_BY_TIER[Tier.FREE])
    return {
        "plan_type": profile["plan_type"],
        "ideal_for": profile["ideal_for"],
        "highlights": list(profile["highlights"]),
    }


def _get_role_code(user) -> str:
    return str(getattr(user, "role", "") or "").strip().upper()


def is_admin_role_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    role_codes = set(getattr(user, "assigned_role_codes", []) or [])
    role_codes.add(_get_role_code(user))
    return bool(role_codes & ADMIN_ROLE_CODES)


def get_trial_policy(user) -> dict:
    """Return the trial configuration for a user."""

    role_bucket = "admin" if is_admin_role_user(user) else "student"
    duration_days = TRIAL_CONFIG["default_duration_days"]
    tier = TRIAL_CONFIG["tier_by_role"].get(role_bucket, Tier.BASIC)
    tier_info = TIER_INFO[tier]
    return {
        "role_bucket": role_bucket,
        "duration_days": duration_days,
        "tier": tier,
        "tier_name": tier_info.name,
        "max_trials_per_user": TRIAL_CONFIG["max_trials_per_user"],
    }


def _calculate_trial_duration_days(subscription) -> int:
    trial_start = getattr(subscription, "trial_start", None)
    trial_end = getattr(subscription, "trial_end", None)
    if trial_start and trial_end:
        return max(1, (trial_end.date() - trial_start.date()).days)
    return int(TRIAL_CONFIG["default_duration_days"])


def _save_subscription_metadata(subscription, metadata: Dict[str, Any]) -> None:
    subscription.metadata = metadata
    subscription.save(update_fields=["metadata", "updated_at"])


def _send_trial_expiration_notifications(subscription, *, now=None) -> None:
    from apps.payments.notifications import PaymentNotificationService

    now = now or timezone.now()
    metadata = dict(subscription.metadata or {})
    reminders = dict(metadata.get("reminders") or {})
    user = subscription.user
    plan_name = getattr(getattr(subscription, "plan", None), "name", None) or "CampusHub"
    changed = False

    if getattr(user, "email", None) and not reminders.get("trial_expired_email_sent_at"):
        if PaymentNotificationService.send_trial_expired_email(
            user=user,
            plan_name=plan_name,
        ):
            reminders["trial_expired_email_sent_at"] = now.isoformat()
            changed = True

    if getattr(user, "phone_number", None) and not reminders.get("trial_expired_sms_sent_at"):
        if PaymentNotificationService.send_trial_expired_sms(
            user=user,
            plan_name=plan_name,
        ):
            reminders["trial_expired_sms_sent_at"] = now.isoformat()
            changed = True

    if changed:
        metadata["reminders"] = reminders
        _save_subscription_metadata(subscription, metadata)


def _expire_trial_subscription(subscription, *, now=None):
    now = now or timezone.now()
    metadata = dict(subscription.metadata or {})
    metadata.setdefault("trial", True)
    metadata["trial_expired"] = True
    metadata["trial_expired_at"] = metadata.get("trial_expired_at") or now.isoformat()
    metadata.setdefault("trial_duration_days", _calculate_trial_duration_days(subscription))

    update_fields = ["metadata", "updated_at"]
    subscription.metadata = metadata

    if subscription.status != "canceled":
        subscription.status = "canceled"
        subscription.canceled_at = subscription.canceled_at or now
        subscription.cancel_at_period_end = False
        if getattr(subscription, "trial_end", None) and not getattr(
            subscription, "current_period_end", None
        ):
            subscription.current_period_end = subscription.trial_end
            update_fields.append("current_period_end")
        update_fields.extend(["status", "canceled_at", "cancel_at_period_end"])

    subscription.save(update_fields=list(dict.fromkeys(update_fields)))
    _send_trial_expiration_notifications(subscription, now=now)
    return subscription


def process_expired_trials(*, user=None, now=None) -> int:
    """Expire due trial subscriptions and send one-time upgrade notices."""

    from .models import Subscription

    now = now or timezone.now()
    queryset = Subscription.objects.filter(
        status="trialing",
        trial_end__isnull=False,
        trial_end__lte=now,
    ).select_related("user", "plan")

    if user is not None:
        queryset = queryset.filter(user=user)

    expired = 0
    for subscription in queryset.iterator():
        _expire_trial_subscription(subscription, now=now)
        expired += 1

    return expired


def get_active_subscription(user, include_pending: bool = False):
    """Return the most relevant subscription for a user."""

    from .models import Subscription

    if not user or not getattr(user, "is_authenticated", False):
        return None

    process_expired_trials(user=user)

    statuses = ["active", "trialing", "past_due"]
    if include_pending:
        statuses.append("unpaid")

    return (
        Subscription.objects.filter(user=user, status__in=statuses)
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )


def get_user_tier(user) -> Tier:
    """Get the current tier for a user."""

    if not user or not getattr(user, "is_authenticated", False):
        return Tier.FREE

    try:
        subscription = get_active_subscription(user)
        if subscription and subscription.plan:
            return get_tier_from_string(subscription.plan.tier)
    except Exception:
        pass

    return Tier.FREE


def get_trial_feature_exclusions(user, subscription=None) -> Set[Feature]:
    """Return the features intentionally locked during a free trial."""

    if not user or not getattr(user, "is_authenticated", False):
        return set()

    trial_subscription = subscription or get_active_subscription(user)
    if (
        not trial_subscription
        or getattr(trial_subscription, "status", None) != "trialing"
        or not getattr(trial_subscription, "plan", None)
    ):
        return set()

    trial_tier = get_tier_from_string(trial_subscription.plan.tier)
    return TRIAL_FEATURE_EXCLUSIONS.get(trial_tier, set()).copy()


def has_feature(user, feature: Feature) -> bool:
    """Check if a user has access to a specific feature."""

    if not user or not getattr(user, "is_authenticated", False):
        return feature in TIER_FEATURES[Tier.FREE]

    return feature in get_user_features(user)


def get_user_features(user) -> Set[Feature]:
    """Get all features available to a user based on their tier."""

    if not user or not getattr(user, "is_authenticated", False):
        return TIER_FEATURES[Tier.FREE].copy()

    subscription = get_active_subscription(user)
    tier = (
        get_tier_from_string(subscription.plan.tier)
        if subscription and getattr(subscription, "plan", None)
        else get_user_tier(user)
    )
    features = TIER_FEATURES[tier].copy()
    features -= get_trial_feature_exclusions(user, subscription=subscription)
    return features


def get_user_tier_info(user) -> Optional[TierInfo]:
    """Get detailed tier information for a user."""

    return TIER_INFO.get(get_user_tier(user))


def can_access_feature(user, feature: Feature) -> tuple[bool, Optional[str]]:
    """Return whether a user can access a feature and the denial reason."""

    if has_feature(user, feature):
        return True, None

    subscription = get_active_subscription(user)
    if feature in get_trial_feature_exclusions(user, subscription=subscription):
        trial_tier = get_tier_from_string(getattr(getattr(subscription, "plan", None), "tier", ""))
        return (
            False,
            f"{FEATURE_METADATA[feature]['name']} unlocks after upgrading your {TIER_INFO[trial_tier].name} trial to the full paid plan",
        )

    required_tiers = [Tier.BASIC, Tier.PREMIUM, Tier.ENTERPRISE]
    for tier in required_tiers:
        if feature in TIER_FEATURES[tier]:
            return False, f"Upgrade to {TIER_INFO[tier].name} to access this feature"

    return False, "This feature is not available"


def get_trial_eligibility(user) -> dict:
    """Check if the user can start a trial."""

    from .models import Subscription

    if not user or not getattr(user, "is_authenticated", False):
        return {
            "eligible": False,
            "reason": "Must be logged in to start a trial",
        }

    process_expired_trials(user=user)
    policy = get_trial_policy(user)
    trial_count = (
        Subscription.objects.filter(user=user)
        .filter(
            models.Q(status="trialing")
            | models.Q(trial_start__isnull=False)
            | models.Q(trial_end__isnull=False)
            | models.Q(metadata__trial=True)
        )
        .count()
    )

    if trial_count >= policy["max_trials_per_user"]:
        return {
            "eligible": False,
            "reason": "You have already used your trial",
            "role_bucket": policy["role_bucket"],
            "tier": policy["tier"].value,
            "duration_days": policy["duration_days"],
        }

    active_sub = Subscription.objects.filter(
        user=user,
        status__in=["active", "trialing", "past_due", "unpaid"],
    ).exists()
    if active_sub:
        return {
            "eligible": False,
            "reason": "You already have an active subscription",
            "role_bucket": policy["role_bucket"],
            "tier": policy["tier"].value,
            "duration_days": policy["duration_days"],
        }

    return {
        "eligible": True,
        "role_bucket": policy["role_bucket"],
        "tier": policy["tier"].value,
        "tier_name": policy["tier_name"],
        "duration_days": policy["duration_days"],
    }


def start_free_trial(user, *, auto_started: bool = False, source: str = "manual"):
    """Create a free trial subscription for the user."""

    from .models import Plan, Subscription

    eligibility = get_trial_eligibility(user)
    if not eligibility.get("eligible"):
        return None, eligibility

    tier = get_tier_from_string(eligibility["tier"])
    plan = (
        Plan.objects.filter(tier=tier.value, is_active=True)
        .order_by("display_order", "created_at", "id")
        .first()
    )
    if not plan:
        tier_info = TIER_INFO[tier]
        profile = get_plan_profile(tier)
        plan = Plan.objects.create(
            name=tier_info.name,
            tier=tier.value,
            description=tier_info.description,
            price_monthly=TIER_PRICING[tier]["monthly"],
            price_yearly=TIER_PRICING[tier]["yearly"],
            billing_period="monthly",
            storage_limit_gb=TIER_STORAGE_LIMITS[tier],
            max_upload_size_mb=TIER_MAX_UPLOAD_SIZE_MB[tier],
            download_limit_monthly=0 if TIER_DOWNLOAD_LIMITS[tier] < 0 else TIER_DOWNLOAD_LIMITS[tier],
            upload_limit_monthly=TIER_UPLOAD_LIMITS[tier],
            message_limit_daily=TIER_MESSAGE_LIMITS[tier],
            group_limit=TIER_GROUP_LIMITS[tier],
            bookmark_limit=TIER_BOOKMARK_LIMITS[tier],
            event_limit_monthly=TIER_EVENT_LIMITS[tier],
            points_limit_monthly=TIER_POINTS_LIMITS[tier],
            badge_limit=TIER_BADGE_LIMITS[tier],
            search_results_limit=TIER_SEARCH_RESULTS_LIMITS[tier],
            notification_delay_hours=TIER_NOTIFICATION_DELAY_HOURS[tier],
            support_response_hours=TIER_SUPPORT_RESPONSE_HOURS[tier],
            can_download_unlimited=TIER_DOWNLOAD_LIMITS[tier] < 0,
            has_ads=tier == Tier.FREE,
            has_priority_support=tier in {Tier.PREMIUM, Tier.ENTERPRISE},
            has_analytics=tier in {Tier.BASIC, Tier.PREMIUM, Tier.ENTERPRISE},
            has_early_access=tier in {Tier.PREMIUM, Tier.ENTERPRISE},
            is_featured=tier == Tier.BASIC,
            display_order=list(Tier).index(tier),
            is_active=True,
            metadata=profile,
        )

    now = timezone.now()
    trial_end = now + timedelta(days=eligibility["duration_days"])
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        status="trialing",
        billing_period=plan.billing_period or "monthly",
        trial_start=now,
        current_period_start=now,
        current_period_end=trial_end,
        trial_end=trial_end,
        metadata={
            "trial": True,
            "auto_started": auto_started,
            "role_bucket": eligibility["role_bucket"],
            "trial_tier": tier.value,
            "trial_duration_days": eligibility["duration_days"],
            "source": source,
            "started_at": now.isoformat(),
        },
    )
    return subscription, {
        "success": True,
        "subscription_id": str(subscription.id),
        "tier": tier.value,
        "tier_name": TIER_INFO[tier].name,
        "duration_days": eligibility["duration_days"],
        "role_bucket": eligibility["role_bucket"],
        "trial_end": trial_end.isoformat(),
        "auto_started": auto_started,
    }


def ensure_default_trial(user, *, source: str = "login"):
    """Best-effort helper to auto-provision a first trial when eligible."""

    subscription, _payload = start_free_trial(user, auto_started=True, source=source)
    return subscription


def get_admin_access_status(user) -> dict:
    """Return whether an admin-role user may access admin operations."""

    if not user or not getattr(user, "is_authenticated", False):
        return {
            "required": False,
            "has_access": False,
            "reason": "Authentication required",
            "trial_eligible": False,
        }

    if not is_admin_role_user(user):
        return {
            "required": False,
            "has_access": True,
            "reason": None,
            "trial_eligible": False,
        }

    if getattr(user, "is_superuser", False):
        return {
            "required": False,
            "has_access": True,
            "reason": None,
            "trial_eligible": False,
            "bypass": "superuser",
        }

    eligibility = get_trial_eligibility(user)
    subscription = get_active_subscription(user, include_pending=True)
    plan = getattr(subscription, "plan", None)
    has_access = bool(
        subscription
        and plan
        and subscription.status in {"active", "trialing", "past_due"}
        and str(plan.tier).lower() != Tier.FREE.value
    )

    if has_access:
        return {
            "required": True,
            "has_access": True,
            "reason": None,
            "trial_eligible": False,
            "subscription_status": subscription.status,
            "plan_tier": plan.tier,
            "plan_name": plan.name,
        }

    return {
        "required": True,
        "has_access": False,
        "reason": (
            "Admin access requires an active paid plan. Start your 7-day free "
            "trial or upgrade to continue."
        ),
        "trial_eligible": bool(eligibility.get("eligible")),
        "trial_duration_days": eligibility.get("duration_days"),
        "trial_tier": eligibility.get("tier"),
        "subscription_status": getattr(subscription, "status", None),
        "plan_tier": getattr(plan, "tier", None),
        "plan_name": getattr(plan, "name", None),
    }


def get_feature_access_summary(user) -> dict:
    """Get a subscription, trial, and feature access summary for the user."""

    from .models import Subscription
    from apps.payments.signals import get_user_plan_limits

    user_tier = get_user_tier(user)
    user_features = get_user_features(user)
    tier_info = TIER_INFO[user_tier]
    plan_profile = get_plan_profile(user_tier)
    subscription = get_active_subscription(user, include_pending=True)
    plan = getattr(subscription, "plan", None)
    trial_eligibility = get_trial_eligibility(user)
    admin_access = get_admin_access_status(user)
    limits = get_user_plan_limits(user)
    trial_locked_features = sorted(
        feature.value
        for feature in get_trial_feature_exclusions(user, subscription=subscription)
    )

    categories = {
        "core": [],
        "basic": [],
        "premium": [],
        "enterprise": [],
    }
    for feature in Feature:
        categories[FEATURE_METADATA[feature]["category"]].append(
            {
                "key": feature.value,
                "name": FEATURE_METADATA[feature]["name"],
                "description": FEATURE_METADATA[feature]["description"],
                "available": feature in user_features,
            }
        )

    is_trial = bool(subscription and subscription.status == "trialing")
    plan_tier = str(getattr(plan, "tier", "") or user_tier.value).lower() or Tier.FREE.value
    role_bucket = get_trial_policy(user)["role_bucket"] if getattr(user, "is_authenticated", False) else "guest"
    latest_trial = None
    trial_expired = False
    trial_expired_at = None
    upgrade_prompt = None

    trial_end = getattr(subscription, "trial_end", None)
    trial_days_total = None
    if is_trial and getattr(subscription, "trial_start", None) and trial_end:
        trial_days_total = max(
            1,
            (trial_end.date() - subscription.trial_start.date()).days,
        )
    elif trial_eligibility.get("eligible"):
        trial_days_total = trial_eligibility.get("duration_days")

    if getattr(user, "is_authenticated", False):
        latest_trial = (
            Subscription.objects.filter(user=user)
            .filter(
                models.Q(metadata__trial=True)
                | models.Q(trial_start__isnull=False)
                | models.Q(trial_end__isnull=False)
            )
            .select_related("plan")
            .order_by("-trial_end", "-created_at")
            .first()
        )

    if latest_trial is not None:
        latest_metadata = dict(latest_trial.metadata or {})
        latest_trial_end = getattr(latest_trial, "trial_end", None)
        trial_expired = bool(
            latest_metadata.get("trial_expired")
            or (
                latest_metadata.get("trial")
                and latest_trial.status == "canceled"
                and latest_trial_end
                and latest_trial_end <= timezone.now()
            )
        )
        if trial_expired:
            if latest_metadata.get("trial_expired_at"):
                trial_expired_at = latest_metadata["trial_expired_at"]
            elif hasattr(latest_trial_end, "isoformat"):
                trial_expired_at = latest_trial_end.isoformat()

    trial_banner = None
    if is_trial:
        end_label = (
            trial_end.strftime("%B %d, %Y")
            if hasattr(trial_end, "strftime")
            else str(trial_end)
        )
        trial_banner = {
            "title": "Your 7-day free trial is active",
            "message": f"Your {tier_info.name} trial ends on {end_label}. Trial access uses reduced caps, and some premium perks stay locked until you upgrade.",
            "cta_label": "Upgrade",
        }
    elif getattr(user, "is_authenticated", False) and user_tier == Tier.FREE:
        if trial_expired:
            upgrade_prompt = {
                "title": "Your free trial has ended",
                "message": "Your 7-day free trial has elapsed. Upgrade now to restore AI tools, analytics, certificates, and premium access.",
                "cta_label": "Upgrade",
            }
        else:
            upgrade_prompt = {
                "title": "You are on the Free plan",
                "message": "Free access includes only the core study tools. Upgrade to unlock AI features, analytics, certificates, integrations, and higher limits.",
                "cta_label": "Upgrade",
            }

    return {
        "tier": user_tier.value,
        "tier_name": tier_info.name,
        "plan_type": plan_profile["plan_type"],
        "ideal_for": plan_profile["ideal_for"],
        "highlights": plan_profile["highlights"],
        "plan_name": getattr(plan, "name", tier_info.name if user_tier != Tier.FREE else "Free"),
        "plan_tier": plan_tier,
        "subscription_status": getattr(subscription, "status", None),
        "subscription_id": str(subscription.id) if subscription else None,
        "billing_period": getattr(subscription, "billing_period", None),
        "current_period_end": subscription.current_period_end.isoformat()
        if getattr(subscription, "current_period_end", None)
        else None,
        "cancel_at_period_end": bool(getattr(subscription, "cancel_at_period_end", False)),
        "is_trial": is_trial,
        "trial_start": subscription.trial_start.isoformat()
        if getattr(subscription, "trial_start", None)
        else None,
        "trial_end": trial_end.isoformat() if hasattr(trial_end, "isoformat") else None,
        "trial_days_total": trial_days_total,
        "trial_eligible": bool(trial_eligibility.get("eligible")),
        "trial_duration_days": trial_eligibility.get("duration_days"),
        "trial_tier": trial_eligibility.get("tier"),
        "role_bucket": role_bucket,
        "show_trial_banner": bool(trial_banner),
        "show_upgrade_prompt": bool(upgrade_prompt),
        "trial_banner": trial_banner,
        "upgrade_prompt": upgrade_prompt,
        "trial_expired": trial_expired,
        "trial_expired_at": trial_expired_at,
        "is_free_plan": user_tier == Tier.FREE,
        "requires_plan_upgrade": not admin_access.get("has_access", True) if admin_access.get("required") else False,
        "admin_access_required": bool(admin_access.get("required")),
        "admin_access_granted": bool(admin_access.get("has_access")),
        "admin_access_reason": admin_access.get("reason"),
        "storage_limit_gb": limits.get("storage_gb", TIER_STORAGE_LIMITS[user_tier]),
        "max_upload_size_mb": limits.get("max_upload_mb", 10),
        "download_limit_monthly": limits.get("downloads_monthly", TIER_DOWNLOAD_LIMITS[user_tier]),
        "upload_limit_monthly": limits.get("upload_limit_monthly", TIER_UPLOAD_LIMITS[user_tier]),
        "message_limit_daily": limits.get("message_limit_daily", TIER_MESSAGE_LIMITS[user_tier]),
        "group_limit": limits.get("group_limit", TIER_GROUP_LIMITS[user_tier]),
        "bookmark_limit": limits.get("bookmark_limit", TIER_BOOKMARK_LIMITS[user_tier]),
        "event_limit_monthly": limits.get("event_limit_monthly", TIER_EVENT_LIMITS[user_tier]),
        "points_limit_monthly": limits.get("points_limit_monthly", TIER_POINTS_LIMITS[user_tier]),
        "badge_limit": limits.get("badge_limit", TIER_BADGE_LIMITS[user_tier]),
        "search_results_limit": limits.get("search_results_limit", TIER_SEARCH_RESULTS_LIMITS[user_tier]),
        "notification_delay_hours": limits.get(
            "notification_delay_hours",
            TIER_NOTIFICATION_DELAY_HOURS[user_tier],
        ),
        "support_response_hours": limits.get(
            "support_response_hours",
            TIER_SUPPORT_RESPONSE_HOURS[user_tier],
        ),
        "can_download_unlimited": limits.get("unlimited_downloads", False),
        "has_ads": limits.get("has_ads", True),
        "has_priority_support": limits.get("priority_support", False),
        "has_analytics": limits.get("analytics", False),
        "has_early_access": limits.get("early_access", False),
        "is_trial_limited": bool(limits.get("is_trial_limited")),
        "trial_locked_features": trial_locked_features,
        "limits": {
            "storage_gb": limits.get("storage_gb", TIER_STORAGE_LIMITS[user_tier]),
            "max_upload_mb": limits.get("max_upload_mb", TIER_MAX_UPLOAD_SIZE_MB[user_tier]),
            "downloads_monthly": limits.get("downloads_monthly", TIER_DOWNLOAD_LIMITS[user_tier]),
            "unlimited_downloads": limits.get("unlimited_downloads", False),
            "upload_limit_monthly": limits.get("upload_limit_monthly", TIER_UPLOAD_LIMITS[user_tier]),
            "message_limit_daily": limits.get("message_limit_daily", TIER_MESSAGE_LIMITS[user_tier]),
            "group_limit": limits.get("group_limit", TIER_GROUP_LIMITS[user_tier]),
            "bookmark_limit": limits.get("bookmark_limit", TIER_BOOKMARK_LIMITS[user_tier]),
            "event_limit_monthly": limits.get("event_limit_monthly", TIER_EVENT_LIMITS[user_tier]),
            "points_limit_monthly": limits.get("points_limit_monthly", TIER_POINTS_LIMITS[user_tier]),
            "badge_limit": limits.get("badge_limit", TIER_BADGE_LIMITS[user_tier]),
            "search_results_limit": limits.get(
                "search_results_limit",
                TIER_SEARCH_RESULTS_LIMITS[user_tier],
            ),
            "notification_delay_hours": limits.get(
                "notification_delay_hours",
                TIER_NOTIFICATION_DELAY_HOURS[user_tier],
            ),
            "support_response_hours": limits.get(
                "support_response_hours",
                TIER_SUPPORT_RESPONSE_HOURS[user_tier],
            ),
            "has_ads": limits.get("has_ads", True),
            "priority_support": limits.get("priority_support", False),
            "analytics": limits.get("analytics", False),
            "early_access": limits.get("early_access", False),
            "is_trial_limited": bool(limits.get("is_trial_limited")),
        },
        "features": sorted(feature.value for feature in user_features),
        "feature_flags": {
            feature.value: feature in user_features
            for feature in Feature
        },
        "locked_features": sorted(
            feature.value for feature in Feature if feature not in user_features
        ),
        "categories": categories,
    }
