"""
Backup and export API views for CampusHub admin tools.
"""

import csv
import json
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.authentication import JWTAuthentication
from apps.admin_management.permissions import IsAdmin

logger = logging.getLogger(__name__)
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _is_truthy(value) -> bool:
    return str(value or "").strip().lower() in TRUTHY_VALUES


def _timestamp_slug(value: datetime | None = None) -> str:
    moment = value or timezone.now()
    return moment.strftime("%Y%m%d_%H%M%S")


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=_json_default, ensure_ascii=False)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _format_label(value: str) -> str:
    return str(value).replace("_", " ").strip().title()


def _calculate_total_storage_bytes() -> int:
    total_size = 0
    try:
        media_root = settings.MEDIA_ROOT
        if os.path.exists(media_root):
            for dirpath, _dirnames, filenames in os.walk(media_root):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
    except Exception:
        logger.exception("Failed to calculate total storage usage.")
    return total_size


def _build_download_url(request, path: str, params: dict[str, str]) -> str:
    base_url = request.build_absolute_uri(path)
    query_string = urlencode(params)
    return f"{base_url}?{query_string}" if query_string else base_url


def _collect_export_payload(user) -> dict:
    from django.contrib.auth import get_user_model
    from apps.announcements.models import Announcement
    from apps.courses.models import Course, Unit
    from apps.faculties.models import Department, Faculty
    from apps.resources.models import Resource
    from apps.social.models import StudyGroup

    User = get_user_model()
    exported_at = timezone.now()

    faculties = list(
        Faculty.objects.order_by("name").values("id", "name", "code", "is_active")
    )
    departments = list(
        Department.objects.select_related("faculty")
        .order_by("name")
        .values("id", "name", "code", "faculty_id", "faculty__name", "is_active")
    )
    courses = list(
        Course.objects.select_related("department")
        .order_by("name")
        .values("id", "name", "code", "department_id", "department__name", "is_active")
    )
    units = list(
        Unit.objects.select_related("course")
        .order_by("code", "name")
        .values(
            "id",
            "name",
            "code",
            "course_id",
            "course__name",
            "semester",
            "year_of_study",
            "is_active",
        )
    )

    users = [
        {
            "id": account.id,
            "email": account.email,
            "first_name": account.first_name,
            "last_name": account.last_name,
            "registration_number": account.registration_number,
            "role": account.role,
            "is_active": account.is_active,
            "is_verified": account.is_verified,
            "date_joined": account.date_joined,
            "last_login": account.last_login,
        }
        for account in User.objects.order_by("date_joined")
    ]

    resources = [
        {
            "id": str(resource.id),
            "title": resource.title,
            "status": resource.status,
            "resource_type": resource.resource_type,
            "file_type": resource.file_type,
            "file_size": resource.file_size,
            "download_count": resource.download_count,
            "view_count": resource.view_count,
            "uploaded_by": resource.uploaded_by.email if resource.uploaded_by else "",
            "course_name": resource.course.name if resource.course else "",
            "unit_name": resource.unit.name if resource.unit else "",
            "created_at": resource.created_at,
        }
        for resource in Resource.objects.select_related("uploaded_by", "course", "unit").order_by("-created_at")
    ]

    study_groups = [
        {
            "id": str(group.id),
            "name": group.name,
            "status": group.status,
            "privacy": group.privacy,
            "is_public": group.is_public,
            "year_of_study": group.year_of_study,
            "allow_member_invites": group.allow_member_invites,
            "max_members": group.max_members,
            "member_count": group.memberships.filter(status="active").count(),
            "creator_email": group.creator.email,
            "course_name": group.course.name if group.course else "",
            "created_at": group.created_at,
        }
        for group in StudyGroup.objects.select_related("creator", "course").order_by("-created_at")
    ]

    announcements = list(
        Announcement.objects.select_related("created_by")
        .order_by("-created_at")
        .values(
            "id",
            "title",
            "announcement_type",
            "status",
            "is_pinned",
            "published_at",
            "created_at",
            "created_by__email",
        )
    )

    return {
        "export_date": exported_at.isoformat(),
        "exported_by": user.email,
        "summary": {
            "faculties_count": len(faculties),
            "departments_count": len(departments),
            "courses_count": len(courses),
            "units_count": len(units),
            "users_count": len(users),
            "resources_count": len(resources),
            "study_groups_count": len(study_groups),
            "announcements_count": len(announcements),
        },
        "faculties": faculties,
        "departments": departments,
        "courses": courses,
        "units": units,
        "users": users,
        "resources": resources,
        "study_groups": study_groups,
        "announcements": announcements,
    }


def _build_backup_metadata(request) -> dict:
    from django.contrib.auth import get_user_model
    from apps.announcements.models import Announcement
    from apps.resources.models import Resource
    from apps.social.models import StudyGroup

    User = get_user_model()
    created_at = timezone.now()
    total_storage_bytes = _calculate_total_storage_bytes()

    return {
        "backup_id": _timestamp_slug(created_at),
        "timestamp": created_at.isoformat(),
        "created_by": request.user.email,
        "resources_count": Resource.objects.count(),
        "users_count": User.objects.count(),
        "study_groups_count": StudyGroup.objects.count(),
        "announcements_count": Announcement.objects.count(),
        "total_storage_bytes": total_storage_bytes,
        "total_storage_mb": round(total_storage_bytes / (1024 * 1024), 2),
        "database_name": str(settings.DATABASES["default"]["NAME"]),
        "includes": [
            "faculties",
            "departments",
            "courses",
            "units",
            "users",
            "resources",
            "study_groups",
            "announcements",
        ],
        "download_url": _build_download_url(
            request,
            request.path,
            {"download": "1"},
        ),
    }


def _csv_response(payload: dict) -> HttpResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["CampusHub Data Export"])
    writer.writerow(["Generated At", payload.get("export_date", "")])
    writer.writerow(["Generated By", payload.get("exported_by", "")])
    writer.writerow([])
    writer.writerow(["Summary"])
    writer.writerow(["Metric", "Value"])
    for key, value in payload.get("summary", {}).items():
        writer.writerow([_format_label(key), value])

    for section_name in [
        "faculties",
        "departments",
        "courses",
        "units",
        "users",
        "resources",
        "study_groups",
        "announcements",
    ]:
        writer.writerow([])
        writer.writerow([_format_label(section_name)])
        records = payload.get(section_name, [])
        if not records:
            writer.writerow(["No records"])
            continue

        headers = list(records[0].keys())
        writer.writerow(headers)
        for record in records:
            writer.writerow([_stringify(record.get(header)) for header in headers])

    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="campushub_export_{_timestamp_slug()}.csv"'
    )
    return response


def _excel_response(payload: dict) -> HttpResponse:
    def xml_cell(value) -> str:
        return f'<Cell><Data ss:Type="String">{escape(_stringify(value))}</Data></Cell>'

    worksheets = []

    summary_rows = [
        ("Generated At", payload.get("export_date", "")),
        ("Generated By", payload.get("exported_by", "")),
    ]
    summary_rows.extend(payload.get("summary", {}).items())
    worksheets.append(
        "<Worksheet ss:Name=\"Summary\"><Table>"
        + "".join(
            f"<Row>{xml_cell(_format_label(key))}{xml_cell(value)}</Row>"
            for key, value in summary_rows
        )
        + "</Table></Worksheet>"
    )

    for section_name in [
        "faculties",
        "departments",
        "courses",
        "units",
        "users",
        "resources",
        "study_groups",
        "announcements",
    ]:
        records = payload.get(section_name, [])
        worksheet_name = _format_label(section_name)[:31]
        table_rows = []
        if records:
            headers = list(records[0].keys())
            table_rows.append(
                "<Row>" + "".join(xml_cell(header) for header in headers) + "</Row>"
            )
            for record in records:
                table_rows.append(
                    "<Row>"
                    + "".join(xml_cell(record.get(header)) for header in headers)
                    + "</Row>"
                )
        else:
            table_rows.append(f"<Row>{xml_cell('No records')}</Row>")

        worksheets.append(
            f"<Worksheet ss:Name=\"{escape(worksheet_name)}\"><Table>"
            + "".join(table_rows)
            + "</Table></Worksheet>"
        )

    workbook = (
        '<?xml version="1.0"?>'
        '<?mso-application progid="Excel.Sheet"?>'
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:x="urn:schemas-microsoft-com:office:excel" '
        'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        + "".join(worksheets)
        + "</Workbook>"
    )

    response = HttpResponse(
        workbook,
        content_type="application/vnd.ms-excel",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="campushub_export_{_timestamp_slug()}.xls"'
    )
    return response


def _pdf_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _build_pdf_bytes(lines: list[str]) -> bytes:
    page_width = 612
    page_height = 792
    margin_left = 48
    margin_top = 742
    line_height = 14
    lines_per_page = 48
    chunks = [
        lines[index:index + lines_per_page]
        for index in range(0, len(lines), lines_per_page)
    ] or [["CampusHub Export"]]

    objects: dict[int, bytes] = {}
    next_object_id = 4
    page_ids: list[int] = []

    for chunk in chunks:
        content_object_id = next_object_id
        page_object_id = next_object_id + 1
        next_object_id += 2

        content_lines = [f"BT /F1 10 Tf {margin_left} {margin_top} Td {line_height} TL"]
        for index, raw_line in enumerate(chunk):
            encoded_line = _pdf_escape(raw_line)
            if index == 0:
                content_lines.append(f"({encoded_line}) Tj")
            else:
                content_lines.append(f"T* ({encoded_line}) Tj")
        content_lines.append("ET")
        content_stream = "\n".join(content_lines).encode("latin-1", "replace")

        objects[content_object_id] = (
            f"<< /Length {len(content_stream)} >>\nstream\n".encode("ascii")
            + content_stream
            + b"\nendstream"
        )
        objects[page_object_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_object_id} 0 R >>"
        ).encode("ascii")
        page_ids.append(page_object_id)

    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        f"<< /Type /Pages /Count {len(page_ids)} /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] >>"
    ).encode("ascii")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * next_object_id

    for object_id in range(1, next_object_id):
        offsets[object_id] = pdf.tell()
        pdf.write(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.write(objects[object_id])
        pdf.write(b"\nendobj\n")

    xref_offset = pdf.tell()
    pdf.write(f"xref\n0 {next_object_id}\n".encode("ascii"))
    pdf.write(b"0000000000 65535 f \n")
    for object_id in range(1, next_object_id):
        pdf.write(f"{offsets[object_id]:010d} 00000 n \n".encode("ascii"))

    pdf.write(
        (
            f"trailer\n<< /Size {next_object_id} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("ascii")
    )
    return pdf.getvalue()


def _pdf_response(payload: dict) -> HttpResponse:
    lines = [
        "CampusHub Data Export",
        f"Generated At: {payload.get('export_date', '')}",
        f"Generated By: {payload.get('exported_by', '')}",
        "",
        "Summary",
    ]
    lines.extend(
        f"{_format_label(key)}: {_stringify(value)}"
        for key, value in payload.get("summary", {}).items()
    )

    for section_name in [
        "faculties",
        "departments",
        "courses",
        "units",
        "users",
        "resources",
        "study_groups",
        "announcements",
    ]:
        lines.append("")
        lines.append(_format_label(section_name))
        records = payload.get(section_name, [])
        if not records:
            lines.append("No records")
            continue

        headers = list(records[0].keys())
        lines.append(" | ".join(headers))
        for record in records:
            lines.append(" | ".join(_stringify(record.get(header)) for header in headers))

    response = HttpResponse(_build_pdf_bytes(lines), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="campushub_export_{_timestamp_slug()}.pdf"'
    )
    return response


def _export_download_response(payload: dict, export_format: str) -> HttpResponse:
    normalized_format = str(export_format or "csv").strip().lower()
    if normalized_format == "csv":
        return _csv_response(payload)
    if normalized_format in {"excel", "xls", "xlsx"}:
        return _excel_response(payload)
    if normalized_format == "pdf":
        return _pdf_response(payload)

    return Response(
        {
            "success": False,
            "message": "Unsupported export format. Use csv, pdf, or excel.",
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated, IsAdmin])
def create_backup(request):
    """
    Create backup metadata or download a JSON backup snapshot.
    """
    backup_data = _build_backup_metadata(request)

    if _is_truthy(request.query_params.get("download")):
        payload = {
            "backup": backup_data,
            "data": _collect_export_payload(request.user),
        }
        response = HttpResponse(
            json.dumps(payload, default=_json_default, indent=2),
            content_type="application/json",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="campushub_backup_{backup_data["backup_id"]}.json"'
        )
        return response

    return Response(
        {
            "success": True,
            "backup": backup_data,
            "message": "Backup metadata generated successfully",
        }
    )


@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated, IsAdmin])
def system_stats(request):
    """
    Get detailed system statistics.
    """
    from django.contrib.auth import get_user_model
    from apps.accounts.models import UserActivity
    from apps.announcements.models import Announcement
    from apps.courses.models import Course
    from apps.faculties.models import Department, Faculty
    from apps.reports.models import Report
    from apps.resources.models import Resource
    from apps.social.models import StudyGroup

    User = get_user_model()

    try:
        total_users = User.objects.all().count()
    except Exception as exc:
        logger.error("Error getting total_users: %s", exc)
        total_users = 0

    try:
        active_users = User.objects.filter(is_active=True).count()
    except Exception as exc:
        logger.error("Error getting active_users: %s", exc)
        active_users = 0

    try:
        verified_users = User.objects.filter(is_verified=True).count()
    except Exception as exc:
        logger.error("Error getting verified_users: %s", exc)
        verified_users = 0

    try:
        total_students = User.objects.filter(
            Q(role__iexact="STUDENT") | Q(role__isnull=True) | Q(role="")
        ).count()
    except Exception as exc:
        logger.error("Error getting total_students: %s", exc)
        total_students = 0

    try:
        total_admins = User.objects.filter(
            Q(role__iexact="ADMIN") | Q(is_superuser=True)
        ).count()
    except Exception as exc:
        logger.error("Error getting total_admins: %s", exc)
        total_admins = 0

    try:
        suspended_users = User.objects.filter(is_active=False).count()
    except Exception as exc:
        logger.error("Error getting suspended_users: %s", exc)
        suspended_users = 0

    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    active_users_today = User.objects.filter(last_login__date=today).count()
    new_users_today = User.objects.filter(date_joined__date=today).count()
    active_users_week = User.objects.filter(last_login__date__gte=week_ago).count()

    total_resources = Resource.objects.count()
    approved_resources = Resource.objects.filter(status="approved").count()
    pending_resources = Resource.objects.filter(status__in=["pending", "flagged"]).count()
    rejected_resources = Resource.objects.filter(status="rejected").count()

    total_downloads = sum(Resource.objects.values_list("download_count", flat=True)) or 0
    total_shares = sum(Resource.objects.values_list("share_count", flat=True)) or 0
    reported_resources = Report.objects.filter(status__in=["open", "in_review"]).count()

    total_study_groups = StudyGroup.objects.count()
    total_announcements = Announcement.objects.count()
    total_news = 0

    total_faculties = Faculty.objects.count()
    total_departments = Department.objects.count()
    total_courses = Course.objects.count()

    total_size = _calculate_total_storage_bytes()
    activities_today = UserActivity.objects.filter(created_at__date=today).count()

    return Response(
        {
            "summary": {
                "total_users": total_users,
                "total_students": total_students,
                "total_admins": total_admins,
                "total_resources": total_resources,
                "pending_resources": pending_resources,
                "approved_resources": approved_resources,
                "rejected_resources": rejected_resources,
                "reported_resources": reported_resources,
                "total_downloads": total_downloads,
                "total_shares": total_shares,
                "total_study_groups": total_study_groups,
                "total_announcements": total_announcements,
                "total_news": total_news,
                "active_users_today": active_users_today,
                "new_users_today": new_users_today,
                "active_users_week": active_users_week,
                "suspended_users": suspended_users,
            },
            "users": {
                "total": total_users,
                "students": total_students,
                "admins": total_admins,
                "active": active_users,
                "verified": verified_users,
                "active_today": active_users_today,
                "new_today": new_users_today,
                "active_week": active_users_week,
                "suspended": suspended_users,
            },
            "resources": {
                "total": total_resources,
                "approved": approved_resources,
                "pending": pending_resources,
                "rejected": rejected_resources,
                "reported": reported_resources,
                "downloads": total_downloads,
                "shares": total_shares,
            },
            "study_groups": {
                "total": total_study_groups,
            },
            "announcements": {
                "total": total_announcements,
            },
            "news": {
                "total": total_news,
            },
            "academic": {
                "faculties": total_faculties,
                "departments": total_departments,
                "courses": total_courses,
            },
            "storage": {
                "total_bytes": total_size,
                "total_mb": round(total_size / (1024 * 1024), 2),
                "total_gb": round(total_size / (1024 * 1024 * 1024), 2),
            },
            "activity": {
                "activities_today": activities_today,
                "active_users_today": active_users_today,
                "new_users_today": new_users_today,
                "active_users_week": active_users_week,
            },
        }
    )


@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated, IsAdmin])
def export_data(request):
    """
    Export platform data as metadata or downloadable CSV/PDF/Excel files.
    """
    export_format = str(request.query_params.get("format") or "csv").strip().lower()

    if _is_truthy(request.query_params.get("download")):
        payload = _collect_export_payload(request.user)
        return _export_download_response(payload, export_format)

    exported_at = timezone.now()
    payload = _collect_export_payload(request.user)
    metadata = {
        "export_date": payload["export_date"],
        "exported_by": payload["exported_by"],
        **payload["summary"],
        "available_formats": ["csv", "pdf", "excel"],
        "download_urls": {
            "csv": _build_download_url(
                request,
                request.path,
                {"download": "1", "format": "csv"},
            ),
            "pdf": _build_download_url(
                request,
                request.path,
                {"download": "1", "format": "pdf"},
            ),
            "excel": _build_download_url(
                request,
                request.path,
                {"download": "1", "format": "excel"},
            ),
        },
        "generated_at": exported_at.isoformat(),
    }

    return Response(
        {
            "success": True,
            "data": metadata,
            "message": "Data export prepared successfully",
        }
    )
