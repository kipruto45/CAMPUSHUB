"""
Mobile Gesture API Models for CampusHub.
Provides gesture configuration and swipe action management for mobile app.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class GestureType(models.TextChoices):
    """Predefined gesture types available in the app."""
    SWIPE_LEFT = "swipe_left", "Swipe Left"
    SWIPE_RIGHT = "swipe_right", "Swipe Right"
    SWIPE_UP = "swipe_up", "Swipe Up"
    SWIPE_DOWN = "swipe_down", "Swipe Down"
    DOUBLE_TAP = "double_tap", "Double Tap"
    LONG_PRESS = "long_press", "Long Press"
    PINCH = "pinch", "Pinch"
    ROTATE = "rotate", "Rotate"
    TWO_FINGER_SWIPE = "two_finger_swipe", "Two Finger Swipe"
    EDGE_SWIPE = "edge_swipe", "Edge Swipe"
    CUSTOM = "custom", "Custom Gesture"


class SwipeActionType(models.TextChoices):
    """Predefined swipe actions."""
    NAVIGATE_BACK = "navigate_back", "Navigate Back"
    OPEN_MENU = "open_menu", "Open Menu"
    OPEN_DRAWER = "open_drawer", "Open Drawer"
    CLOSE_DRAWER = "close_drawer", "Close Drawer"
    FAVORITE = "favorite", "Add to Favorites"
    UNFAVORITE = "unfavorite", "Remove from Favorites"
    SHARE = "share", "Share Content"
    BOOKMARK = "bookmark", "Add Bookmark"
    UNBOOKMARK = "unbookmark", "Remove Bookmark"
    REFRESH = "refresh", "Refresh Content"
    SCROLL_TO_TOP = "scroll_to_top", "Scroll to Top"
    SCROLL_TO_BOTTOM = "scroll_to_bottom", "Scroll to Bottom"
    OPEN_SEARCH = "open_search", "Open Search"
    CLOSE_SEARCH = "close_search", "Close Search"
    TOGGLE_THEME = "toggle_theme", "Toggle Theme"
    OPEN_NOTIFICATIONS = "open_notifications", "Open Notifications"
    OPEN_PROFILE = "open_profile", "Open Profile"
    RATE_CONTENT = "rate_content", "Rate Content"
    DOWNLOAD = "download", "Download Content"
    CUSTOM_ACTION = "custom_action", "Custom Action"


class GestureConfiguration(TimeStampedModel):
    """
    Stores user gesture preferences and settings.
    Each user can have their own gesture configuration.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gesture_config"
    )
    
    # Global gesture settings
    gestures_enabled = models.BooleanField(default=True)
    
    # Sensitivity levels (1-10, where 10 is most sensitive)
    swipe_sensitivity = models.IntegerField(default=5, choices=[
        (1, "Very Low"),
        (2, "Low"),
        (3, "Below Average"),
        (4, "Average"),
        (5, "Above Average"),
        (6, "High"),
        (7, "Very High"),
        (8, "Extreme"),
        (9, "Maximum"),
        (10, "Ultra"),
    ])
    
    # Double tap sensitivity
    double_tap_sensitivity = models.IntegerField(default=5, choices=[
        (1, "Very Low"),
        (2, "Low"),
        (3, "Below Average"),
        (4, "Average"),
        (5, "Above Average"),
        (6, "High"),
        (7, "Very High"),
        (8, "Extreme"),
        (9, "Maximum"),
        (10, "Ultra"),
    ])
    
    # Long press duration in milliseconds
    long_press_duration = models.IntegerField(default=500)
    
    # Enable haptic feedback
    haptic_feedback = models.BooleanField(default=True)
    
    # Enable gesture animations
    gesture_animations = models.BooleanField(default=True)
    
    # Enable edge gestures
    edge_gestures_enabled = models.BooleanField(default=True)
    
    # Edge gesture zone width in pixels
    edge_zone_width = models.IntegerField(default=20)
    
    # Enable custom gestures
    custom_gestures_enabled = models.BooleanField(default=True)
    
    # Maximum number of custom gestures allowed
    max_custom_gestures = models.IntegerField(default=10)
    
    # Gesture timeout in milliseconds (time to complete gesture)
    gesture_timeout = models.IntegerField(default=1000)
    
    # Require authentication for certain gestures
    require_auth_for_favorites = models.BooleanField(default=False)
    require_auth_for_bookmarks = models.BooleanField(default=False)
    require_auth_for_share = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Gesture Configuration"
        verbose_name_plural = "Gesture Configurations"

    def __str__(self):
        return f"Gesture Config - {self.user.email}"


class SwipeAction(TimeStampedModel):
    """
    Defines available swipe actions in the system.
    These are the predefined actions that can be mapped to gestures.
    """

    action_type = models.CharField(
        max_length=50,
        choices=SwipeActionType.choices,
        unique=True
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True)  # Icon name for mobile
    is_system = models.BooleanField(default=True)  # System-defined vs custom
    is_active = models.BooleanField(default=True)
    requires_auth = models.BooleanField(default=False)
    
    # Action parameters (JSON for flexible configuration)
    action_params = models.JSONField(default=dict, blank=True)
    
    # Screen/feature where this action is available
    available_on = models.JSONField(default=list, blank=True)  # List of screen names
    
    # Priority for action ordering (lower = higher priority)
    priority = models.IntegerField(default=100)

    class Meta:
        verbose_name = "Swipe Action"
        verbose_name_plural = "Swipe Actions"
        ordering = ["priority", "name"]

    def __str__(self):
        return self.name


class UserSwipeMapping(TimeStampedModel):
    """
    Maps user's gesture gestures to specific actions.
    Allows users to customize which gesture triggers which action.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="swipe_mappings"
    )
    
    gesture_type = models.CharField(
        max_length=50,
        choices=GestureType.choices
    )
    
    # Direction for swipe gestures (left, right, up, down)
    direction = models.CharField(
        max_length=20,
        choices=[
            ("left", "Left"),
            ("right", "Right"),
            ("up", "Up"),
            ("down", "Down"),
            ("any", "Any"),
        ],
        default="any",
        blank=True
    )
    
    action = models.ForeignKey(
        SwipeAction,
        on_delete=models.CASCADE,
        related_name="user_mappings"
    )
    
    # Enable/disable this specific mapping
    is_enabled = models.BooleanField(default=True)
    
    # Screen-specific mapping (empty = all screens)
    screen = models.CharField(max_length=100, blank=True)
    
    # Minimum swipe distance in pixels to trigger action
    min_swipe_distance = models.IntegerField(default=50)
    
    # Maximum swipe time in milliseconds
    max_swipe_time = models.IntegerField(default=500)

    class Meta:
        verbose_name = "User Swipe Mapping"
        verbose_name_plural = "User Swipe Mappings"
        unique_together = ["user", "gesture_type", "direction", "screen"]
        ordering = ["gesture_type", "direction"]

    def __str__(self):
        return f"{self.user.email} - {self.gesture_type} -> {self.action.name}"


class CustomGesture(TimeStampedModel):
    """
    Stores custom gestures created by users.
    Users can define their own gesture patterns.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custom_gestures"
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Gesture pattern (stored as list of points or encoded string)
    gesture_pattern = models.JSONField(
        help_text="Array of points defining the gesture path"
    )
    
    # Minimum match score (0-100) to recognize this gesture
    min_match_score = models.IntegerField(default=80)
    
    # Action to trigger when gesture is recognized
    action = models.ForeignKey(
        SwipeAction,
        on_delete=models.CASCADE,
        related_name="custom_gestures",
        null=True,
        blank=True
    )
    
    # Custom action name if not using predefined action
    custom_action_name = models.CharField(max_length=100, blank=True)
    
    # Custom action params
    custom_action_params = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    # Usage count
    usage_count = models.IntegerField(default=0)
    
    # Last used timestamp
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Custom Gesture"
        verbose_name_plural = "Custom Gestures"
        ordering = ["-usage_count", "-created_at"]

    def __str__(self):
        return f"{self.name} - {self.user.email}"


class GestureAnalytics(TimeStampedModel):
    """
    Stores analytics data for gesture usage.
    Helps understand how users interact with gestures.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gesture_analytics"
    )
    
    gesture_type = models.CharField(
        max_length=50,
        choices=GestureType.choices
    )
    
    action_triggered = models.ForeignKey(
        SwipeAction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="analytics"
    )
    
    # Whether the gesture was successfully recognized
    recognized = models.BooleanField(default=True)
    
    # Time taken to complete gesture in milliseconds
    gesture_duration = models.IntegerField(null=True, blank=True)
    
    # Distance traveled in pixels
    gesture_distance = models.IntegerField(null=True, blank=True)
    
    # Screen where gesture was performed
    screen = models.CharField(max_length=100)
    
    # Whether action was completed (e.g., user cancelled)
    action_completed = models.BooleanField(default=True)
    
    # Error message if gesture failed
    error_message = models.CharField(max_length=500, blank=True)
    
    # Session ID for grouping
    session_id = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Gesture Analytics"
        verbose_name_plural = "Gesture Analytics"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["gesture_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.gesture_type} - {self.created_at}"


def create_default_swipe_actions():
    """Create default swipe actions if they don't exist."""
    default_actions = [
        (SwipeActionType.NAVIGATE_BACK, "Navigate Back", "arrow-back", 1),
        (SwipeActionType.OPEN_MENU, "Open Menu", "menu", 2),
        (SwipeActionType.OPEN_DRAWER, "Open Drawer", "menu-open", 3),
        (SwipeActionType.CLOSE_DRAWER, "Close Drawer", "menu-close", 4),
        (SwipeActionType.FAVORITE, "Add to Favorites", "heart", 5),
        (SwipeActionType.UNFAVORITE, "Remove from Favorites", "heart-outline", 6),
        (SwipeActionType.SHARE, "Share Content", "share", 7),
        (SwipeActionType.BOOKMARK, "Add Bookmark", "bookmark", 8),
        (SwipeActionType.UNBOOKMARK, "Remove Bookmark", "bookmark-outline", 9),
        (SwipeActionType.REFRESH, "Refresh Content", "refresh", 10),
        (SwipeActionType.SCROLL_TO_TOP, "Scroll to Top", "arrow-up", 11),
        (SwipeActionType.SCROLL_TO_BOTTOM, "Scroll to Bottom", "arrow-down", 12),
        (SwipeActionType.OPEN_SEARCH, "Open Search", "search", 13),
        (SwipeActionType.CLOSE_SEARCH, "Close Search", "close", 14),
        (SwipeActionType.TOGGLE_THEME, "Toggle Theme", "theme", 15),
        (SwipeActionType.OPEN_NOTIFICATIONS, "Open Notifications", "notifications", 16),
        (SwipeActionType.OPEN_PROFILE, "Open Profile", "person", 17),
        (SwipeActionType.RATE_CONTENT, "Rate Content", "star", 18),
        (SwipeActionType.DOWNLOAD, "Download Content", "download", 19),
    ]
    
    for action_type, name, icon, priority in default_actions:
        SwipeAction.objects.get_or_create(
            action_type=action_type,
            defaults={
                "name": name,
                "icon": icon,
                "is_system": True,
                "is_active": True,
                "priority": priority,
            }
        )


# =============================================================================
# Haptic Feedback Models
# =============================================================================

class HapticIntensity(models.TextChoices):
    """Haptic feedback intensity levels."""
    LIGHT = "light", "Light"
    MEDIUM = "medium", "Medium"
    HEAVY = "heavy", "Heavy"
    SOFT = "soft", "Soft"
    RIGID = "rigid", "Rigid"


class HapticPatternType(models.TextChoices):
    """Predefined haptic pattern types."""
    SELECTION = "selection", "Selection (light tap)"
    SUCCESS = "success", "Success (double tap)"
    WARNING = "warning", "Warning (triple short pulses)"
    ERROR = "error", "Error (long-short-long)"
    IMPACT = "impact", "Impact (heavy tap)"
    NOTIFICATION = "notification", "Notification"
    FEEDBACK = "feedback", "Feedback"
    HEAVY = "heavy", "Heavy Impact"
    MEDIUM = "medium", "Medium Impact"
    LIGHT = "light", "Light Impact"
    RIGID = "rigid", "Rigid Impact"
    SOFT = "soft", "Soft Impact"
    SCROLL = "scroll", "Scroll"
    CELL_SELECTION = "cell_selection", "Cell Selection"


class HapticFeedbackConfiguration(TimeStampedModel):
    """
    Stores user haptic feedback preferences and settings.
    Each user can have their own haptic configuration.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="haptic_config"
    )
    
    # Global haptic settings
    haptics_enabled = models.BooleanField(default=True)
    
    # Default intensity for all haptic feedback
    default_intensity = models.CharField(
        max_length=20,
        choices=HapticIntensity.choices,
        default=HapticIntensity.MEDIUM
    )
    
    # Enable haptic for gestures
    haptic_for_gestures = models.BooleanField(default=True)
    
    # Enable haptic for notifications
    haptic_for_notifications = models.BooleanField(default=True)
    
    # Enable haptic for button presses
    haptic_for_button_presses = models.BooleanField(default=True)
    
    # Enable haptic for selection changes
    haptic_for_selection = models.BooleanField(default=True)
    
    # Enable haptic for success actions
    haptic_for_success = models.BooleanField(default=True)
    
    # Enable haptic for error actions
    haptic_for_error = models.BooleanField(default=True)
    
    # Enable haptic for warnings
    haptic_for_warning = models.BooleanField(default=True)
    
    # Master volume (0-100)
    master_volume = models.IntegerField(default=80)
    
    # Gesture-specific intensity overrides
    swipe_intensity = models.CharField(
        max_length=20,
        choices=HapticIntensity.choices,
        default=HapticIntensity.MEDIUM
    )
    
    tap_intensity = models.CharField(
        max_length=20,
        choices=HapticIntensity.choices,
        default=HapticIntensity.LIGHT
    )
    
    long_press_intensity = models.CharField(
        max_length=20,
        choices=HapticIntensity.choices,
        default=HapticIntensity.HEAVY
    )

    class Meta:
        verbose_name = "Haptic Feedback Configuration"
        verbose_name_plural = "Haptic Feedback Configurations"

    def __str__(self):
        return f"Haptic Config - {self.user.email}"


class HapticPattern(TimeStampedModel):
    """
    Stores predefined and custom haptic patterns.
    Predefined patterns are system-defined, custom patterns are user-created.
    """

    pattern_type = models.CharField(
        max_length=50,
        choices=HapticPatternType.choices,
        unique=True
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Pattern definition: list of (duration_ms, pause_ms) tuples
    # Example: [(50, 0), (50, 50), (50, 0)] for double tap
    pattern_data = models.JSONField(
        help_text="List of vibration segments: [{'duration': ms, 'pause': ms}, ...]"
    )
    
    # Intensity recommendation for this pattern
    recommended_intensity = models.CharField(
        max_length=20,
        choices=HapticIntensity.choices,
        default=HapticIntensity.MEDIUM
    )
    
    # Whether this is a system-defined pattern
    is_system = models.BooleanField(default=True)
    
    # Whether this pattern is active
    is_active = models.BooleanField(default=True)
    
    # Category for grouping patterns
    category = models.CharField(
        max_length=50,
        choices=[
            ("selection", "Selection"),
            ("notification", "Notification"),
            ("impact", "Impact"),
            ("feedback", "Feedback"),
            ("custom", "Custom"),
        ],
        default="feedback"
    )

    class Meta:
        verbose_name = "Haptic Pattern"
        verbose_name_plural = "Haptic Patterns"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class CustomHapticPattern(TimeStampedModel):
    """
    Stores custom haptic patterns created by users.
    Users can define their own vibration patterns.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="custom_haptic_patterns"
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Custom pattern definition
    pattern_data = models.JSONField(
        help_text="List of vibration segments: [{'duration': ms, 'pause': ms}, ...]"
    )
    
    # Intensity for this pattern
    intensity = models.CharField(
        max_length=20,
        choices=HapticIntensity.choices,
        default=HapticIntensity.MEDIUM
    )
    
    # Whether this pattern is active
    is_active = models.BooleanField(default=True)
    
    # Usage count
    usage_count = models.IntegerField(default=0)
    
    # Last used timestamp
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Custom Haptic Pattern"
        verbose_name_plural = "Custom Haptic Patterns"
        ordering = ["-usage_count", "-created_at"]

    def __str__(self):
        return f"{self.name} - {self.user.email}"


class HapticActionMapping(TimeStampedModel):
    """
    Maps actions to specific haptic patterns.
    Allows customization of which haptic pattern plays for which action.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="haptic_mappings"
    )
    
    # Action identifier (e.g., 'swipe_left', 'button_press', 'notification')
    action = models.CharField(max_length=100)
    
    # Pattern to use for this action (predefined)
    pattern = models.ForeignKey(
        HapticPattern,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_mappings"
    )
    
    # Custom pattern to use (overrides predefined pattern)
    custom_pattern = models.ForeignKey(
        CustomHapticPattern,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_mappings"
    )
    
    # Override intensity for this action
    intensity_override = models.CharField(
        max_length=20,
        choices=HapticIntensity.choices,
        blank=True,
        help_text="Leave empty to use pattern's default intensity"
    )
    
    # Enable/disable haptic for this specific action
    is_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Haptic Action Mapping"
        verbose_name_plural = "Haptic Action Mappings"
        unique_together = ["user", "action"]

    def __str__(self):
        return f"{self.user.email} - {self.action}"


def create_default_haptic_patterns():
    """Create default haptic patterns if they don't exist."""
    default_patterns = [
        # Selection patterns
        (
            HapticPatternType.SELECTION,
            "Selection",
            "Light tap for selection changes",
            [{"duration": 10, "pause": 0}],
            HapticIntensity.LIGHT,
            "selection"
        ),
        (
            HapticPatternType.CELL_SELECTION,
            "Cell Selection",
            "Light tap for table cell selection",
            [{"duration": 10, "pause": 0}],
            HapticIntensity.LIGHT,
            "selection"
        ),
        (
            HapticPatternType.SCROLL,
            "Scroll",
            "Subtle feedback when scrolling through lists",
            [{"duration": 5, "pause": 0}],
            HapticIntensity.LIGHT,
            "selection"
        ),
        
        # Success patterns
        (
            HapticPatternType.SUCCESS,
            "Success",
            "Double tap pattern for successful actions",
            [{"duration": 30, "pause": 50}, {"duration": 30, "pause": 0}],
            HapticIntensity.MEDIUM,
            "notification"
        ),
        (
            HapticPatternType.NOTIFICATION,
            "Notification",
            "Triple short pulses for notifications",
            [{"duration": 20, "pause": 30}, {"duration": 20, "pause": 30}, {"duration": 20, "pause": 0}],
            HapticIntensity.MEDIUM,
            "notification"
        ),
        
        # Warning patterns
        (
            HapticPatternType.WARNING,
            "Warning",
            "Triple short pulses for warnings",
            [{"duration": 25, "pause": 40}, {"duration": 25, "pause": 40}, {"duration": 25, "pause": 0}],
            HapticIntensity.MEDIUM,
            "notification"
        ),
        
        # Error patterns
        (
            HapticPatternType.ERROR,
            "Error",
            "Long-short-long pattern for errors",
            [{"duration": 80, "pause": 50}, {"duration": 40, "pause": 50}, {"duration": 80, "pause": 0}],
            HapticIntensity.HEAVY,
            "notification"
        ),
        
        # Impact patterns
        (
            HapticPatternType.IMPACT,
            "Impact",
            "Heavy tap for significant interactions",
            [{"duration": 50, "pause": 0}],
            HapticIntensity.HEAVY,
            "impact"
        ),
        (
            HapticPatternType.HEAVY,
            "Heavy Impact",
            "Strong haptic for heavy impacts",
            [{"duration": 60, "pause": 0}],
            HapticIntensity.HEAVY,
            "impact"
        ),
        (
            HapticPatternType.MEDIUM,
            "Medium Impact",
            "Medium haptic for moderate interactions",
            [{"duration": 40, "pause": 0}],
            HapticIntensity.MEDIUM,
            "impact"
        ),
        (
            HapticPatternType.LIGHT,
            "Light Impact",
            "Light haptic for subtle interactions",
            [{"duration": 20, "pause": 0}],
            HapticIntensity.LIGHT,
            "impact"
        ),
        (
            HapticPatternType.RIGID,
            "Rigid Impact",
            "Sharp, rigid haptic for firm surfaces",
            [{"duration": 45, "pause": 0}],
            HapticIntensity.RIGID,
            "impact"
        ),
        (
            HapticPatternType.SOFT,
            "Soft Impact",
            "Soft haptic for gentle interactions",
            [{"duration": 35, "pause": 0}],
            HapticIntensity.SOFT,
            "impact"
        ),
        
        # Feedback patterns
        (
            HapticPatternType.FEEDBACK,
            "Feedback",
            "General feedback haptic",
            [{"duration": 30, "pause": 0}],
            HapticIntensity.MEDIUM,
            "feedback"
        ),
    ]
    
    for pattern_type, name, description, pattern_data, intensity, category in default_patterns:
        HapticPattern.objects.get_or_create(
            pattern_type=pattern_type,
            defaults={
                "name": name,
                "description": description,
                "pattern_data": pattern_data,
                "recommended_intensity": intensity,
                "is_system": True,
                "is_active": True,
                "category": category,
            }
        )
