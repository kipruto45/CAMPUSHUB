"""
Export and Report Builder
Provides comprehensive report generation and data export capabilities
"""

import csv
import json
from io import StringIO
from datetime import datetime
from typing import Dict, List, Optional, Any
from django.db.models import QuerySet, Count, Sum, Avg
from django.http import HttpResponse


class ReportFormat:
    """Available export formats."""
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"


class ReportType:
    """Predefined report types."""
    USER_ACTIVITY = "user_activity"
    RESOURCE_USAGE = "resource_usage"
    SYSTEM_ANALYTICS = "system_analytics"
    MODERATION_REPORT = "moderation_report"
    ENGAGEMENT_REPORT = "engagement_report"
    CUSTOM = "custom"


class ReportBuilderService:
    """
    Service for building and exporting reports.
    """

    @staticmethod
    def get_available_reports() -> List[Dict[str, Any]]:
        """Get list of available report types."""
        return [
            {
                'id': ReportType.USER_ACTIVITY,
                'name': 'User Activity Report',
                'description': 'Detailed user activity and engagement metrics',
                'filters': ['date_range', 'user_role', 'department'],
                'fields': ['user', 'activity_type', 'timestamp', 'details'],
            },
            {
                'id': ReportType.RESOURCE_USAGE,
                'name': 'Resource Usage Report',
                'description': 'Resource downloads, views, and ratings',
                'filters': ['date_range', 'faculty', 'department', 'file_type'],
                'fields': ['title', 'downloads', 'views', 'rating', 'upload_date'],
            },
            {
                'id': ReportType.SYSTEM_ANALYTICS,
                'name': 'System Analytics Report',
                'description': 'API usage, performance metrics, and system health',
                'filters': ['date_range', 'endpoint'],
                'fields': ['endpoint', 'request_count', 'avg_response_time', 'error_rate'],
            },
            {
                'id': ReportType.MODERATION_REPORT,
                'name': 'Moderation Report',
                'description': 'Content moderation actions and trends',
                'filters': ['date_range', 'status', 'moderator'],
                'fields': ['resource', 'status', 'moderator', 'action_date', 'notes'],
            },
            {
                'id': ReportType.ENGAGEMENT_REPORT,
                'name': 'Engagement Report',
                'description': 'User engagement and retention metrics',
                'filters': ['date_range', 'engagement_level'],
                'fields': ['user', 'login_count', 'resource_count', 'last_active'],
            },
        ]

    @staticmethod
    def build_user_activity_report(filters: Dict = None) -> QuerySet:
        """Build user activity report."""
        from apps.activity.models import RecentActivity
        
        queryset = RecentActivity.objects.all().select_related('user')
        
        if filters:
            if 'date_range' in filters:
                queryset = queryset.filter(created_at__range=filters['date_range'])
            if 'user_role' in filters:
                queryset = queryset.filter(user__role=filters['user_role'])
        
        return queryset.order_by('-created_at')

    @staticmethod
    def build_resource_usage_report(filters: Dict = None) -> QuerySet:
        """Build resource usage report."""
        from apps.resources.models import Resource
        
        queryset = Resource.objects.all().select_related('uploaded_by', 'faculty', 'department')
        
        if filters:
            if 'date_range' in filters:
                queryset = queryset.filter(created_at__range=filters['date_range'])
            if 'faculty' in filters:
                queryset = queryset.filter(faculty_id=filters['faculty'])
            if 'file_type' in filters:
                queryset = queryset.filter(file_type=filters['file_type'])
        
        return queryset.order_by('-download_count', '-view_count')

    @staticmethod
    def build_system_analytics_report(filters: Dict = None) -> QuerySet:
        """Build system analytics report."""
        from apps.core.middleware import APIRequestLog
        
        queryset = APIRequestLog.objects.all()
        
        if filters:
            if 'date_range' in filters:
                queryset = queryset.filter(created_at__range=filters['date_range'])
            if 'endpoint' in filters:
                queryset = queryset.filter(endpoint__icontains=filters['endpoint'])
        
        return queryset.order_by('-created_at')

    @staticmethod
    def export_to_json(data: List[Dict]) -> str:
        """Export data to JSON format."""
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def export_to_csv(data: List[Dict]) -> str:
        """Export data to CSV format."""
        if not data:
            return ""
        
        output = StringIO()
        fieldnames = list(data[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in data:
            # Convert non-serializable values to strings
            cleaned_row = {}
            for key, value in row.items():
                if isinstance(value, (datetime,)):
                    cleaned_row[key] = value.isoformat()
                else:
                    cleaned_row[key] = str(value) if value is not None else ''
            writer.writerow(cleaned_row)
        
        return output.getvalue()

    @staticmethod
    def generate_report(
        report_type: str,
        filters: Dict = None,
        fields: List[str] = None,
        format: str = ReportFormat.JSON,
    ) -> Dict[str, Any]:
        """
        Generate a report with given parameters.
        
        Args:
            report_type: Type of report to generate
            filters: Filter criteria
            fields: Fields to include in report
            format: Output format (json, csv)
            
        Returns:
            Dictionary with report data and metadata
        """
        filters = filters or {}
        
        # Get the appropriate queryset
        if report_type == ReportType.USER_ACTIVITY:
            queryset = ReportBuilderService.build_user_activity_report(filters)
        elif report_type == ReportType.RESOURCE_USAGE:
            queryset = ReportBuilderService.build_resource_usage_report(filters)
        elif report_type == ReportType.SYSTEM_ANALYTICS:
            queryset = ReportBuilderService.build_system_analytics_report(filters)
        else:
            queryset = []

        # Convert to list of dicts
        data = []
        for item in queryset[:1000]:  # Limit to 1000 records
            item_dict = {}
            if fields:
                for field in fields:
                    if hasattr(item, field):
                        item_dict[field] = getattr(item, field)
            else:
                # Include all fields
                if hasattr(item, '__dict__'):
                    item_dict = {k: v for k, v in item.__dict__.items() 
                               if not k.startswith('_')}
            
            # Clean up the data
            cleaned_item = {}
            for key, value in item_dict.items():
                if isinstance(value, (datetime,)):
                    cleaned_item[key] = value.isoformat()
                elif hasattr(value, '__dict__'):
                    # Skip related objects
                    continue
                else:
                    cleaned_item[key] = value
            
            data.append(cleaned_item)

        # Format output
        if format == ReportFormat.CSV:
            formatted_data = ReportBuilderService.export_to_csv(data)
        else:
            formatted_data = ReportBuilderService.export_to_json(data)

        return {
            'report_type': report_type,
            'generated_at': datetime.now().isoformat(),
            'record_count': len(data),
            'filters': filters,
            'format': format,
            'data': formatted_data if format == ReportFormat.JSON else None,
            'csv_data': formatted_data if format == ReportFormat.CSV else None,
        }

    @staticmethod
    def get_report_summary(report_type: str, filters: Dict = None) -> Dict[str, Any]:
        """Get summary statistics for a report."""
        filters = filters or {}
        
        if report_type == ReportType.USER_ACTIVITY:
            from apps.activity.models import RecentActivity
            queryset = RecentActivity.objects.all()
            total = queryset.count()
            
            return {
                'total_activities': total,
                'unique_users': queryset.values('user').distinct().count(),
            }
        
        elif report_type == ReportType.RESOURCE_USAGE:
            from apps.resources.models import Resource
            queryset = Resource.objects.all()
            
            return {
                'total_resources': queryset.count(),
                'total_downloads': queryset.aggregate(Sum('download_count'))['download_count__sum'] or 0,
                'total_views': queryset.aggregate(Sum('view_count'))['view_count__sum'] or 0,
                'avg_rating': queryset.aggregate(Avg('average_rating'))['average_rating__avg'] or 0,
            }
        
        elif report_type == ReportType.SYSTEM_ANALYTICS:
            from apps.core.middleware import APIRequestLog
            queryset = APIRequestLog.objects.all()
            
            return {
                'total_requests': queryset.count(),
                'unique_endpoints': queryset.values('endpoint').distinct().count(),
            }
        
        return {}


class BulkOperationsService:
    """
    Service for bulk admin operations.
    """

    @staticmethod
    def bulk_update_resources(resource_ids: List[str], updates: Dict) -> Dict[str, Any]:
        """Bulk update resources."""
        from apps.resources.models import Resource
        
        updated_count = Resource.objects.filter(id__in=resource_ids).update(**updates)
        
        return {
            'success': True,
            'updated_count': updated_count,
            'total_requested': len(resource_ids),
        }

    @staticmethod
    def bulk_delete_resources(resource_ids: List[str], soft: bool = True) -> Dict[str, Any]:
        """Bulk delete resources."""
        from apps.resources.models import Resource
        
        if soft:
            deleted_count = Resource.objects.filter(id__in=resource_ids).update(is_deleted=True)
        else:
            deleted_count = Resource.objects.filter(id__in=resource_ids).delete()[0]
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'total_requested': len(resource_ids),
            'soft_delete': soft,
        }

    @staticmethod
    def bulk_update_users(user_ids: List[int], updates: Dict) -> Dict[str, Any]:
        """Bulk update users."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        updated_count = User.objects.filter(id__in=user_ids).update(**updates)
        
        return {
            'success': True,
            'updated_count': updated_count,
            'total_requested': len(user_ids),
        }

    @staticmethod
    def bulk_moderate_resources(
        resource_ids: List[str],
        action: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Bulk moderate resources."""
        from apps.resources.models import Resource
        
        updates = {
            'moderation_status': action,
            'moderation_notes': reason,
        }
        
        updated_count = Resource.objects.filter(id__in=resource_ids).update(**updates)
        
        return {
            'success': True,
            'action': action,
            'updated_count': updated_count,
            'total_requested': len(resource_ids),
        }
