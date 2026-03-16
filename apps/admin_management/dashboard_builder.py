"""
Custom Dashboard Builder
Allows admins to customize their dashboard with configurable widgets
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.db import models


class DashboardWidgetType:
    """Available widget types for the dashboard."""
    STATS_CARD = "stats_card"
    CHART_LINE = "chart_line"
    CHART_BAR = "chart_bar"
    CHART_PIE = "chart_pie"
    TABLE = "table"
    LIST = "list"
    ACTIVITY_FEED = "activity_feed"
    QUICK_ACTIONS = "quick_actions"
    NOTIFICATIONS = "notifications"
    RESOURCE_QUEUE = "resource_queue"
    USER_TABLE = "user_table"
    KPI_CARD = "kpi_card"
    PROGRESS_BAR = "progress_bar"

    CHOICES = [
        (STATS_CARD, "Stats Card"),
        (CHART_LINE, "Line Chart"),
        (CHART_BAR, "Bar Chart"),
        (CHART_PIE, "Pie Chart"),
        (TABLE, "Table"),
        (LIST, "List"),
        (ACTIVITY_FEED, "Activity Feed"),
        (QUICK_ACTIONS, "Quick Actions"),
        (NOTIFICATIONS, "Notifications"),
        (RESOURCE_QUEUE, "Resource Queue"),
        (USER_TABLE, "User Table"),
        (KPI_CARD, "KPI Card"),
        (PROGRESS_BAR, "Progress Bar"),
    ]


@dataclass
class DashboardWidget:
    """Widget configuration for dashboard."""
    id: str
    type: str
    title: str
    position: Dict[str, int]  # x, y, width, height
    config: Dict[str, Any] = field(default_factory=dict)
    data_source: str = ""
    is_visible: bool = True
    refresh_interval: int = 300  # seconds


@dataclass
class DashboardLayout:
    """Dashboard layout configuration."""
    id: str
    name: str
    widgets: List[DashboardWidget] = field(default_factory=list)
    columns: int = 12
    rows: int = 12
    is_default: bool = False


# Default dashboard layouts
DEFAULT_LAYOUTS = {
    "overview": DashboardLayout(
        id="overview",
        name="Overview Dashboard",
        is_default=True,
        widgets=[
            DashboardWidget(
                id="stats_users",
                type=DashboardWidgetType.STATS_CARD,
                title="Total Users",
                position={"x": 0, "y": 0, "w": 3, "h": 2},
                data_source="/api/admin/stats/users/",
            ),
            DashboardWidget(
                id="stats_resources",
                type=DashboardWidgetType.STATS_CARD,
                title="Total Resources",
                position={"x": 3, "y": 0, "w": 3, "h": 2},
                data_source="/api/admin/stats/resources/",
            ),
            DashboardWidget(
                id="stats_downloads",
                type=DashboardWidgetType.STATS_CARD,
                title="Total Downloads",
                position={"x": 6, "y": 0, "w": 3, "h": 2},
                data_source="/api/admin/stats/downloads/",
            ),
            DashboardWidget(
                id="stats_reports",
                type=DashboardWidgetType.STATS_CARD,
                title="Pending Reports",
                position={"x": 9, "y": 0, "w": 3, "h": 2},
                data_source="/api/admin/stats/reports/",
            ),
            DashboardWidget(
                id="activity_chart",
                type=DashboardWidgetType.CHART_LINE,
                title="Activity Over Time",
                position={"x": 0, "y": 2, "w": 8, "h": 4},
                data_source="/api/admin/stats/activity/",
            ),
            DashboardWidget(
                id="notifications",
                type=DashboardWidgetType.NOTIFICATIONS,
                title="Recent Notifications",
                position={"x": 8, "y": 2, "w": 4, "h": 4},
                data_source="/api/notifications/admin/notifications/",
            ),
            DashboardWidget(
                id="resource_queue",
                type=DashboardWidgetType.RESOURCE_QUEUE,
                title="Pending Moderation",
                position={"x": 0, "y": 6, "w": 6, "h": 4},
                data_source="/api/admin/resources/?status=pending",
            ),
            DashboardWidget(
                id="quick_actions",
                type=DashboardWidgetType.QUICK_ACTIONS,
                title="Quick Actions",
                position={"x": 6, "y": 6, "w": 6, "h": 4},
            ),
        ],
    ),
    "analytics": DashboardLayout(
        id="analytics",
        name="Analytics Dashboard",
        widgets=[
            DashboardWidget(
                id="kpi_users",
                type=DashboardWidgetType.KPI_CARD,
                title="User Growth",
                position={"x": 0, "y": 0, "w": 4, "h": 2},
                data_source="/api/admin/stats/user-growth/",
            ),
            DashboardWidget(
                id="kpi_engagement",
                type=DashboardWidgetType.KPI_CARD,
                title="Engagement Rate",
                position={"x": 4, "y": 0, "w": 4, "h": 2},
                data_source="/api/admin/stats/engagement/",
            ),
            DashboardWidget(
                id="kpi_content",
                type=DashboardWidgetType.KPI_CARD,
                title="Content Growth",
                position={"x": 8, "y": 0, "w": 4, "h": 2},
                data_source="/api/admin/stats/content-growth/",
            ),
            DashboardWidget(
                id="user_chart",
                type=DashboardWidgetType.CHART_BAR,
                title="User Registrations",
                position={"x": 0, "y": 2, "w": 6, "h": 4},
                data_source="/api/admin/stats/registrations/",
            ),
            DashboardWidget(
                id="download_chart",
                type=DashboardWidgetType.CHART_LINE,
                title="Download Trends",
                position={"x": 6, "y": 2, "w": 6, "h": 4},
                data_source="/api/admin/stats/downloads/",
            ),
        ],
    ),
    "moderation": DashboardLayout(
        id="moderation",
        name="Moderation Dashboard",
        widgets=[
            DashboardWidget(
                id="pending_resources",
                type=DashboardWidgetType.STATS_CARD,
                title="Pending Resources",
                position={"x": 0, "y": 0, "w": 4, "h": 2},
                data_source="/api/admin/stats/pending-resources/",
            ),
            DashboardWidget(
                id="flagged_content",
                type=DashboardWidgetType.STATS_CARD,
                title="Flagged Content",
                position={"x": 4, "y": 0, "w": 4, "h": 2},
                data_source="/api/admin/stats/flagged-content/",
            ),
            DashboardWidget(
                id="reports",
                type=DashboardWidgetType.STATS_CARD,
                title="Open Reports",
                position={"x": 8, "y": 0, "w": 4, "h": 2},
                data_source="/api/admin/stats/open-reports/",
            ),
            DashboardWidget(
                id="resource_queue_table",
                type=DashboardWidgetType.RESOURCE_QUEUE,
                title="Resource Moderation Queue",
                position={"x": 0, "y": 2, "w": 12, "h": 6},
                data_source="/api/admin/resources/?status=pending",
            ),
        ],
    ),
}


class DashboardBuilderService:
    """
    Service for managing custom dashboard configurations.
    """

    @staticmethod
    def get_available_widgets() -> List[Dict[str, Any]]:
        """Get list of available widget types with their configurations."""
        return [
            {
                "type": DashboardWidgetType.STATS_CARD,
                "name": "Stats Card",
                "description": "Display a single metric with icon",
                "default_size": {"w": 3, "h": 2},
                "config_fields": ["title", "icon", "data_source", "color"],
            },
            {
                "type": DashboardWidgetType.KPI_CARD,
                "name": "KPI Card",
                "description": "Key Performance Indicator with trend",
                "default_size": {"w": 4, "h": 2},
                "config_fields": ["title", "data_source", "trend", "color"],
            },
            {
                "type": DashboardWidgetType.CHART_LINE,
                "name": "Line Chart",
                "description": "Display data trends over time",
                "default_size": {"w": 6, "h": 4},
                "config_fields": ["title", "data_source", "time_range", "colors"],
            },
            {
                "type": DashboardWidgetType.CHART_BAR,
                "name": "Bar Chart",
                "description": "Compare values across categories",
                "default_size": {"w": 6, "h": 4},
                "config_fields": ["title", "data_source", "orientation", "colors"],
            },
            {
                "type": DashboardWidgetType.CHART_PIE,
                "name": "Pie Chart",
                "description": "Show distribution of values",
                "default_size": {"w": 4, "h": 4},
                "config_fields": ["title", "data_source", "colors"],
            },
            {
                "type": DashboardWidgetType.TABLE,
                "name": "Table",
                "description": "Display data in tabular format",
                "default_size": {"w": 6, "h": 4},
                "config_fields": ["title", "data_source", "columns"],
            },
            {
                "type": DashboardWidgetType.LIST,
                "name": "List",
                "description": "Display items in a list",
                "default_size": {"w": 4, "h": 4},
                "config_fields": ["title", "data_source", "item_template"],
            },
            {
                "type": DashboardWidgetType.ACTIVITY_FEED,
                "name": "Activity Feed",
                "description": "Show recent system activities",
                "default_size": {"w": 4, "h": 4},
                "config_fields": ["title", "activity_types", "limit"],
            },
            {
                "type": DashboardWidgetType.NOTIFICATIONS,
                "name": "Notifications",
                "description": "Show recent admin notifications",
                "default_size": {"w": 4, "h": 4},
                "config_fields": ["title", "types", "limit"],
            },
            {
                "type": DashboardWidgetType.QUICK_ACTIONS,
                "name": "Quick Actions",
                "description": "Buttons for common admin actions",
                "default_size": {"w": 6, "h": 2},
                "config_fields": ["title", "actions"],
            },
            {
                "type": DashboardWidgetType.RESOURCE_QUEUE,
                "name": "Resource Queue",
                "description": "Show resources pending moderation",
                "default_size": {"w": 6, "h": 4},
                "config_fields": ["title", "status_filter", "limit"],
            },
            {
                "type": DashboardWidgetType.USER_TABLE,
                "name": "User Table",
                "description": "Display users with management options",
                "default_size": {"w": 6, "h": 4},
                "config_fields": ["title", "filters", "columns"],
            },
        ]

    @staticmethod
    def get_default_layouts() -> Dict[str, Any]:
        """Get predefined dashboard layouts."""
        result = {}
        for key, layout in DEFAULT_LAYOUTS.items():
            result[key] = {
                "id": layout.id,
                "name": layout.name,
                "is_default": layout.is_default,
                "columns": layout.columns,
                "rows": layout.rows,
                "widgets": [
                    {
                        "id": w.id,
                        "type": w.type,
                        "title": w.title,
                        "position": w.position,
                        "config": w.config,
                        "data_source": w.data_source,
                        "is_visible": w.is_visible,
                        "refresh_interval": w.refresh_interval,
                    }
                    for w in layout.widgets
                ],
            }
        return result

    @staticmethod
    def get_layout_json(layout_id: str) -> Optional[str]:
        """Get JSON string for a specific layout."""
        if layout_id in DEFAULT_LAYOUTS:
            layout = DEFAULT_LAYOUTS[layout_id]
            return json.dumps(
                {
                    "id": layout.id,
                    "name": layout.name,
                    "columns": layout.columns,
                    "rows": layout.rows,
                    "widgets": [
                        {
                            "id": w.id,
                            "type": w.type,
                            "title": w.title,
                            "position": w.position,
                            "config": w.config,
                            "data_source": w.data_source,
                            "is_visible": w.is_visible,
                            "refresh_interval": w.refresh_interval,
                        }
                        for w in layout.widgets
                    ],
                }
            )
        return None

    @staticmethod
    def create_custom_layout(
        name: str,
        widgets: List[Dict[str, Any]],
        columns: int = 12,
        rows: int = 12,
    ) -> str:
        """Create a custom layout configuration."""
        layout_id = f"custom_{name.lower().replace(' ', '_')}"
        return json.dumps(
            {
                "id": layout_id,
                "name": name,
                "columns": columns,
                "rows": rows,
                "widgets": widgets,
                "is_custom": True,
            }
        )

    @staticmethod
    def validate_layout(layout_json: str) -> Dict[str, Any]:
        """Validate a dashboard layout configuration."""
        try:
            layout = json.loads(layout_json)
            errors = []

            # Check required fields
            if "id" not in layout:
                errors.append("Missing required field: id")
            if "name" not in layout:
                errors.append("Missing required field: name")
            if "widgets" not in layout:
                errors.append("Missing required field: widgets")

            # Validate widgets
            widget_ids = set()
            for widget in layout.get("widgets", []):
                if "id" in widget:
                    if widget["id"] in widget_ids:
                        errors.append(f"Duplicate widget id: {widget['id']}")
                    widget_ids.add(widget["id"])
                else:
                    errors.append("Widget missing id field")

                # Validate position
                position = widget.get("position", {})
                if position.get("w", 0) > layout.get("columns", 12):
                    errors.append(f"Widget {widget.get('id')} exceeds grid width")

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "layout": layout,
            }
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "errors": [f"Invalid JSON: {str(e)}"],
                "layout": None,
            }
