"""
Export service for CampusHub.
Provides export functionality for resources to CSV and PDF.
"""

import csv
import logging
from datetime import datetime
from typing import List

from django.http import HttpResponse

logger = logging.getLogger(__name__)


class ExportService:
    """
    Service for exporting data to various formats.
    """

    @staticmethod
    def export_resources_to_csv(resources, fields: List[str] = None) -> HttpResponse:
        """
        Export resources to CSV format.

        Args:
            resources: QuerySet of resources
            fields: List of field names to export (optional)

        Returns:
            HttpResponse with CSV data
        """
        # Default fields to export
        if fields is None:
            fields = [
                "id",
                "title",
                "description",
                "file_type",
                "course",
                "unit",
                "uploaded_by",
                "created_at",
                "download_count",
                "view_count",
                "status",
            ]

        # Create CSV response
        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="resources_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            },
        )

        # Create CSV writer
        writer = csv.writer(response)

        # Write header row
        writer.writerow([field.replace("_", " ").title() for field in fields])

        # Write data rows
        for resource in resources:
            row = []
            for field in fields:
                value = getattr(resource, field, None)

                # Handle related fields
                if value is None:
                    row.append("")
                elif hasattr(value, "__str__"):
                    # For foreign keys, get the string representation
                    if hasattr(value, "name"):
                        row.append(value.name)
                    elif hasattr(value, "username"):
                        row.append(value.username)
                    else:
                        row.append(str(value))
                elif isinstance(value, datetime):
                    row.append(value.strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    row.append(str(value))

            writer.writerow(row)

        return response

    @staticmethod
    def export_users_to_csv(users, fields: List[str] = None) -> HttpResponse:
        """
        Export users to CSV format.

        Args:
            users: QuerySet of users
            fields: List of field names to export

        Returns:
            HttpResponse with CSV data
        """
        if fields is None:
            fields = [
                "id",
                "email",
                "username",
                "first_name",
                "last_name",
                "course",
                "year_of_study",
                "is_active",
                "date_joined",
            ]

        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="users_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            },
        )

        writer = csv.writer(response)
        writer.writerow([field.replace("_", " ").title() for field in fields])

        for user in users:
            row = []
            for field in fields:
                value = getattr(user, field, None)

                if value is None:
                    row.append("")
                elif hasattr(value, "name"):
                    row.append(value.name)
                elif isinstance(value, datetime):
                    row.append(value.strftime("%Y-%m-%d %H:%M:%S"))
                else:
                    row.append(str(value))

            writer.writerow(row)

        return response

    @staticmethod
    def export_analytics_to_csv(
        analytics_data: dict, title: str = "Analytics"
    ) -> HttpResponse:
        """
        Export analytics data to CSV.

        Args:
            analytics_data: Dictionary of analytics data
            title: Title for the export

        Returns:
            HttpResponse with CSV data
        """
        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{title.lower().replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            },
        )

        writer = csv.writer(response)
        writer.writerow(["Metric", "Value"])

        def flatten_dict(d, parent_key=""):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}_{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key))
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        if isinstance(item, dict):
                            items.extend(flatten_dict(item, f"{new_key}_{i}"))
                        else:
                            items.append((f"{new_key}_{i}", item))
                else:
                    items.append((new_key, v))
            return items

        flattened = flatten_dict(analytics_data)
        for key, value in flattened:
            writer.writerow([key.replace("_", " ").title(), str(value)])

        return response

    @staticmethod
    def export_to_pdf_report(resources, title: str = "Resource Report") -> HttpResponse:
        """
        Export resources to PDF report.
        Note: Requires reportlab package.

        Args:
            resources: QuerySet of resources
            title: Report title

        Returns:
            HttpResponse with PDF data
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import (Paragraph, SimpleDocTemplate,
                                            Spacer, Table, TableStyle)

            # Create PDF response
            response = HttpResponse(
                content_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{title.lower().replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
                },
            )

            # Create PDF document
            doc = SimpleDocTemplate(
                response,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18,
            )

            # Get styles
            styles = getSampleStyleSheet()
            title_style = styles["Title"]
            heading_style = styles["Heading2"]
            normal_style = styles["Normal"]

            # Build content
            content = []

            # Add title
            content.append(Paragraph(title, title_style))
            content.append(Spacer(1, 0.2 * inch))

            # Add generation date
            content.append(
                Paragraph(
                    f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    normal_style,
                )
            )
            content.append(Spacer(1, 0.3 * inch))

            # Add summary
            content.append(
                Paragraph(f"Total Resources: {resources.count()}", heading_style)
            )
            content.append(Spacer(1, 0.2 * inch))

            # Create table data
            table_data = [["Title", "Course", "Type", "Downloads", "Views", "Status"]]

            for resource in resources[:50]:  # Limit to 50 rows
                table_data.append(
                    [
                        (
                            resource.title[:30] + "..."
                            if len(resource.title) > 30
                            else resource.title
                        ),
                        str(resource.course)[:15] if resource.course else "",
                        resource.file_type or "",
                        str(resource.download_count),
                        str(resource.view_count),
                        resource.status,
                    ]
                )

            # Create table
            table = Table(
                table_data,
                colWidths=[
                    2 * inch,
                    1 * inch,
                    0.8 * inch,
                    0.8 * inch,
                    0.8 * inch,
                    0.8 * inch,
                ],
            )

            # Style table
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ]
                )
            )

            content.append(table)

            # Build PDF
            doc.build(content)

            return response

        except ImportError:
            # Fallback to CSV if reportlab not installed
            logger.warning("reportlab not installed, falling back to CSV")
            return ExportService.export_resources_to_csv(
                resources, title="Resource Report"
            )

    @staticmethod
    def export_user_activity_to_csv(user, activities) -> HttpResponse:
        """
        Export user activity to CSV.

        Args:
            user: User instance
            activities: QuerySet of activities

        Returns:
            HttpResponse with CSV data
        """
        response = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="activity_{user.username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
            },
        )

        writer = csv.writer(response)
        writer.writerow(["Date", "Activity Type", "Description", "Resource"])

        for activity in activities:
            writer.writerow(
                [
                    (
                        activity.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if activity.created_at
                        else ""
                    ),
                    activity.activity_type,
                    activity.description or "",
                    str(activity.resource) if activity.resource else "",
                ]
            )

        return response


class ResourceExportSerializer:
    """
    Serializer for exporting resource data.
    """

    @staticmethod
    def to_dict(resource) -> dict:
        """
        Convert resource to dictionary for export.

        Args:
            resource: Resource instance

        Returns:
            Dictionary of resource data
        """
        return {
            "id": resource.id,
            "title": resource.title,
            "description": resource.description,
            "file_type": resource.file_type,
            "file_size": resource.file_size,
            "course": str(resource.course) if resource.course else None,
            "unit": str(resource.unit) if resource.unit else None,
            "faculty": str(resource.faculty) if resource.faculty else None,
            "uploaded_by": str(resource.uploaded_by) if resource.uploaded_by else None,
            "upload_date": (
                resource.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if resource.created_at
                else None
            ),
            "approved_date": (
                resource.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                if resource.status == "approved" and resource.updated_at
                else None
            ),
            "downloads": resource.download_count,
            "views": resource.view_count,
            "average_rating": resource.average_rating,
            "status": resource.status,
            "tags": resource.tags or "",
        }

    @staticmethod
    def to_csv_row(resource) -> list:
        """
        Convert resource to CSV row.

        Args:
            resource: Resource instance

        Returns:
            List of field values
        """
        data = ResourceExportSerializer.to_dict(resource)
        return [
            data.get("id", ""),
            data.get("title", ""),
            data.get("description", ""),
            data.get("file_type", ""),
            data.get("file_size", ""),
            data.get("course", ""),
            data.get("unit", ""),
            data.get("faculty", ""),
            data.get("uploaded_by", ""),
            data.get("upload_date", ""),
            data.get("downloads", ""),
            data.get("views", ""),
            data.get("average_rating", ""),
            data.get("status", ""),
            data.get("tags", ""),
        ]
