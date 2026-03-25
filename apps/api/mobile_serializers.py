"""
Mobile API serializers for CampusHub.
Provides optimized serializers for mobile clients.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class MobileUserSerializer(serializers.ModelSerializer):
    """Optimized user serializer for mobile."""

    full_name = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "is_staff",
            "is_superuser",
            "registration_number",
            "profile_image",
            "course_name",
            "year_of_study",
            "is_verified",
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_course_name(self, obj):
        return obj.course.name if obj.course else None


class MobileResourceSerializer(serializers.Serializer):
    """Optimized resource serializer for mobile."""

    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField(required=False)
    file_type = serializers.CharField()
    file_size = serializers.IntegerField()
    thumbnail = serializers.URLField(required=False)
    uploaded_by = serializers.CharField()
    course_name = serializers.CharField()
    unit_name = serializers.CharField()
    download_count = serializers.IntegerField()
    view_count = serializers.IntegerField()
    average_rating = serializers.FloatField()
    created_at = serializers.DateTimeField()


class MobileDashboardSerializer(serializers.Serializer):
    """Dashboard data optimized for mobile."""

    total_uploads = serializers.IntegerField()
    total_downloads = serializers.IntegerField()
    total_bookmarks = serializers.IntegerField()
    storage_used = serializers.IntegerField()
    storage_limit = serializers.IntegerField()
    recent_resources = serializers.ListField()
    announcements = serializers.ListField()


class MobileNotificationSerializer(serializers.Serializer):
    """Optimized notification serializer for mobile."""

    id = serializers.UUIDField()
    title = serializers.CharField()
    message = serializers.CharField()
    notification_type = serializers.CharField()
    is_read = serializers.BooleanField()
    link = serializers.CharField(required=False)
    created_at = serializers.DateTimeField()


class MobileSearchResultSerializer(serializers.Serializer):
    """Search results optimized for mobile."""

    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
    file_type = serializers.CharField()
    thumbnail = serializers.URLField()
    uploaded_by = serializers.CharField()
    course_name = serializers.CharField()
    download_count = serializers.IntegerField()
    average_rating = serializers.FloatField()
    relevance_score = serializers.FloatField(required=False)


class MobileDownloadSerializer(serializers.Serializer):
    """Download data optimized for mobile."""

    resource_id = serializers.UUIDField()
    title = serializers.CharField()
    file_url = serializers.URLField()
    file_size = serializers.IntegerField()
    download_token = serializers.CharField()


class MobileUploadResponseSerializer(serializers.Serializer):
    """Upload response optimized for mobile."""

    success = serializers.BooleanField()
    resource_id = serializers.UUIDField(required=False)
    message = serializers.CharField()
    upload_url = serializers.URLField(required=False)


class MobileErrorSerializer(serializers.Serializer):
    """Standard error response for mobile."""

    error = serializers.CharField()
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.DictField(required=False)


class MobilePaginatedResponseSerializer(serializers.Serializer):
    """Paginated response wrapper for mobile."""

    success = serializers.BooleanField(default=True)
    data = serializers.ListField()
    pagination = serializers.DictField()


class MobileAuthSerializer(serializers.Serializer):
    """Authentication response for mobile."""

    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    expires_in = serializers.IntegerField()
    user = MobileUserSerializer()


class MobileProfileUpdateSerializer(serializers.Serializer):
    """Profile update data for mobile."""

    first_name = serializers.CharField(required=False, max_length=30)
    last_name = serializers.CharField(required=False, max_length=30)
    bio = serializers.CharField(required=False, max_length=500)
    profile_image = serializers.ImageField(required=False)
    phone = serializers.CharField(required=False, max_length=20)
    course_id = serializers.UUIDField(required=False)
    year_of_study = serializers.IntegerField(required=False, min_value=1, max_value=7)


class MobileRegistrationSerializer(serializers.Serializer):
    """Registration data for mobile."""

    email = serializers.EmailField()
    password = serializers.CharField(min_length=8)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    course_id = serializers.UUIDField(required=False)
    year_of_study = serializers.IntegerField(required=False, min_value=1, max_value=7)


class MobileLoginSerializer(serializers.Serializer):
    """Login data for mobile."""

    email = serializers.EmailField()
    password = serializers.CharField()
    device_token = serializers.CharField(required=False)


class MobileRefreshTokenSerializer(serializers.Serializer):
    """Refresh token data for mobile."""

    refresh_token = serializers.CharField()


class MobileDeviceSerializer(serializers.Serializer):
    """Device registration for mobile push notifications."""

    device_token = serializers.CharField(required=True)
    device_type = serializers.ChoiceField(choices=["android", "ios", "web"])
    device_name = serializers.CharField(required=False)
    device_model = serializers.CharField(required=False)
    app_version = serializers.CharField(required=False)


class MobileSettingsSerializer(serializers.Serializer):
    """User settings for mobile."""

    email_notifications = serializers.BooleanField()
    push_notifications = serializers.BooleanField()
    weekly_digest = serializers.BooleanField()
    language = serializers.CharField(max_length=10)
    theme = serializers.ChoiceField(choices=["light", "dark", "system"])


class MobileStatsSerializer(serializers.Serializer):
    """User statistics for mobile."""

    total_uploads = serializers.IntegerField()
    total_downloads = serializers.IntegerField()
    total_bookmarks = serializers.IntegerField()
    total_favorites = serializers.IntegerField()
    total_comments = serializers.IntegerField()
    total_ratings = serializers.IntegerField()
    storage_used = serializers.IntegerField()
    storage_limit = serializers.IntegerField()
    points = serializers.IntegerField()
    badges_count = serializers.IntegerField()


class GestureConfigurationSerializer(serializers.Serializer):
    """Serializer for gesture configuration."""

    id = serializers.UUIDField(read_only=True)
    gestures_enabled = serializers.BooleanField()
    swipe_sensitivity = serializers.IntegerField()
    double_tap_sensitivity = serializers.IntegerField()
    long_press_duration = serializers.IntegerField()
    haptic_feedback = serializers.BooleanField()
    gesture_animations = serializers.BooleanField()
    edge_gestures_enabled = serializers.BooleanField()
    edge_zone_width = serializers.IntegerField()
    custom_gestures_enabled = serializers.BooleanField()
    max_custom_gestures = serializers.IntegerField()
    gesture_timeout = serializers.IntegerField()
    require_auth_for_favorites = serializers.BooleanField()
    require_auth_for_bookmarks = serializers.BooleanField()
    require_auth_for_share = serializers.BooleanField()


class SwipeActionSerializer(serializers.Serializer):
    """Serializer for swipe actions."""

    id = serializers.UUIDField(read_only=True)
    action_type = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False)
    icon = serializers.CharField(required=False)
    is_system = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField()
    requires_auth = serializers.BooleanField()
    action_params = serializers.DictField(required=False)
    available_on = serializers.ListField(required=False)
    priority = serializers.IntegerField()


class UserSwipeMappingSerializer(serializers.Serializer):
    """Serializer for user swipe mappings."""

    id = serializers.UUIDField(read_only=True)
    gesture_type = serializers.CharField()
    direction = serializers.ChoiceField(
        choices=["left", "right", "up", "down", "any"]
    )
    action_id = serializers.UUIDField()
    is_enabled = serializers.BooleanField()
    screen = serializers.CharField(required=False, allow_blank=True)
    min_swipe_distance = serializers.IntegerField()
    max_swipe_time = serializers.IntegerField()


class CustomGestureSerializer(serializers.Serializer):
    """Serializer for custom gestures."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    gesture_pattern = serializers.ListField()
    min_match_score = serializers.IntegerField(min_value=0, max_value=100)
    action_id = serializers.UUIDField(required=False, allow_null=True)
    custom_action_name = serializers.CharField(required=False, allow_blank=True)
    custom_action_params = serializers.DictField(required=False)
    is_active = serializers.BooleanField()
    usage_count = serializers.IntegerField(read_only=True)
    last_used = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class GestureAnalyticsSerializer(serializers.Serializer):
    """Serializer for gesture analytics."""

    id = serializers.UUIDField(read_only=True)
    gesture_type = serializers.CharField()
    action_triggered_id = serializers.UUIDField(required=False, allow_null=True)
    recognized = serializers.BooleanField()
    gesture_duration = serializers.IntegerField(required=False, allow_null=True)
    gesture_distance = serializers.IntegerField(required=False, allow_null=True)
    screen = serializers.CharField()
    action_completed = serializers.BooleanField()
    error_message = serializers.CharField(required=False, allow_blank=True)
    session_id = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


# =============================================================================
# Haptic Feedback Serializers
# =============================================================================

class HapticFeedbackConfigurationSerializer(serializers.Serializer):
    """Serializer for haptic feedback configuration."""

    id = serializers.UUIDField(read_only=True)
    haptics_enabled = serializers.BooleanField()
    default_intensity = serializers.CharField()
    haptic_for_gestures = serializers.BooleanField()
    haptic_for_notifications = serializers.BooleanField()
    haptic_for_button_presses = serializers.BooleanField()
    haptic_for_selection = serializers.BooleanField()
    haptic_for_success = serializers.BooleanField()
    haptic_for_error = serializers.BooleanField()
    haptic_for_warning = serializers.BooleanField()
    master_volume = serializers.IntegerField(min_value=0, max_value=100)
    swipe_intensity = serializers.CharField()
    tap_intensity = serializers.CharField()
    long_press_intensity = serializers.CharField()


class HapticPatternSerializer(serializers.Serializer):
    """Serializer for haptic patterns."""

    id = serializers.UUIDField(read_only=True)
    pattern_type = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    pattern_data = serializers.ListField()
    recommended_intensity = serializers.CharField()
    is_system = serializers.BooleanField(read_only=True)
    is_active = serializers.BooleanField()
    category = serializers.CharField()


class CustomHapticPatternSerializer(serializers.Serializer):
    """Serializer for custom haptic patterns."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    pattern_data = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField()
        )
    )
    intensity = serializers.CharField()
    is_active = serializers.BooleanField()
    usage_count = serializers.IntegerField(read_only=True)
    last_used = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class HapticActionMappingSerializer(serializers.Serializer):
    """Serializer for haptic action mappings."""

    id = serializers.UUIDField(read_only=True)
    action = serializers.CharField(max_length=100)
    pattern_id = serializers.UUIDField(required=False, allow_null=True)
    custom_pattern_id = serializers.UUIDField(required=False, allow_null=True)
    intensity_override = serializers.CharField(required=False, allow_blank=True)
    is_enabled = serializers.BooleanField()


class HapticPatternListSerializer(serializers.Serializer):
    """Serializer for listing available haptic patterns."""

    patterns = HapticPatternSerializer(many=True)
    categories = serializers.ListField()
