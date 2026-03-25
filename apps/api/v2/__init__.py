"""
Lightweight API v2 façade.

These endpoints provide functional data today by delegating to existing v1
services and serializers, so clients can start integrating while the dedicated
v2 stack evolves.
"""

from django.urls import path

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.resources.models import Resource
from apps.resources.serializers import ResourceListSerializer
from apps.accounts.models import User
from apps.courses.models import Course
from apps.search.services import SearchService
from apps.notifications.serializers import NotificationListSerializer
from apps.notifications.models import Notification
from apps.analytics.models import AnalyticsEvent
from apps.payments.models import Payment

@extend_schema(
    summary="API v2 Root",
    description="Feature-complete facade that maps to stable v1 capabilities while v2 evolves.",
    responses={
        200: {
            "description": "Version handshake",
            "content": {
                "application/json": {
                    "example": {
                        "version": "v2",
                        "status": "online",
                        "backed_by": "v1 core",
                        "resources": "/api/v2/resources/",
                        "users": "/api/v2/users/",
                        "search": "/api/v2/search/?q=notes",
                    }
                }
            }
        }
    }
)
@api_view(["GET"])
@permission_classes([AllowAny])
def api_v2_root(request):
    """
    API v2 root endpoint - returns live capability map.
    """
    return Response({
        "version": "v2",
        "status": "online",
        "backed_by": "v1 core",
        "resources": "/api/v2/resources/",
        "users": "/api/v2/users/",
        "search": "/api/v2/search/",
        "notifications": "/api/v2/notifications/",
        "payments": "/api/v2/payments/",
    })


@extend_schema(
    summary="Resources - v2 live",
    description="Lists resources using the v1 backend, paginated.",
    responses={
        200: {
            "description": "Paginated resources",
            "content": {
                "application/json": {
                    "example": {
                        "count": 2,
                        "results": [
                            {"id": "uuid", "title": "Lecture 1", "resource_type": "notes"}
                        ]
                    }
                }
            }
        }
    }
)
@api_view(["GET"])
@permission_classes([AllowAny])
def v2_resources(request):
    """List resources (public or owned)."""
    qs = Resource.objects.filter(status="approved", is_public=True)
    if request.user.is_authenticated:
        qs = qs | Resource.objects.filter(uploaded_by=request.user)
    qs = qs.select_related("course", "unit", "uploaded_by").order_by("-created_at")[:50]
    serializer = ResourceListSerializer(qs, many=True, context={"request": request})
    return Response({"count": len(serializer.data), "results": serializer.data})


@extend_schema(
    summary="Users - v2 live",
    description="Returns basic user directory (first/last name, role).",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def v2_users(request):
    users = User.objects.filter(is_active=True).order_by("-date_joined")[:50]
    data = [
        {
            "id": u.id,
            "name": u.full_name,
            "email": u.email,
            "role": u.role,
            "faculty": getattr(u.faculty, "name", ""),
        }
        for u in users
    ]
    return Response({"count": len(data), "results": data})


@extend_schema(
    summary="Analytics - v2 live",
    description="Returns headline metrics using analytics service.",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def v2_analytics(request):
    total_events = AnalyticsEvent.objects.count()
    recent_events = AnalyticsEvent.objects.order_by("-timestamp")[:20].values(
        "event_type", "event_name", "timestamp", "user_id"
    )
    return Response(
        {
            "total_events": total_events,
            "recent": list(recent_events),
        }
    )


@extend_schema(
    summary="Courses - v2 live",
    description="List courses with id/name/code.",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def v2_courses(request):
    courses = Course.objects.all().order_by("name")[:100]
    data = [
        {"id": c.id, "name": c.name, "code": c.code, "department": getattr(c.department, "name", "")}
        for c in courses
    ]
    return Response({"count": len(data), "results": data})


@extend_schema(
    summary="Search - v2 live",
    description="Performs search using existing search service.",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def v2_search(request):
    query = request.query_params.get("q", "")
    qs = SearchService.apply_filters(
        Resource.objects.filter(status="approved", is_public=True), request.query_params
    )
    results = SearchService.rank_search_results(qs, query, user=request.user)[:20]
    serializer = ResourceListSerializer(results, many=True, context={"request": request})
    return Response({"count": len(serializer.data), "results": serializer.data})


@extend_schema(
    summary="Notifications - v2 live",
    description="Return current user's notifications (first 50).",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def v2_notifications(request):
    qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:50]
    serializer = NotificationListSerializer(qs, many=True, context={"request": request})
    return Response({"count": len(serializer.data), "results": serializer.data})


@extend_schema(
    summary="Payments - v2 live",
    description="Return subscription/payment capabilities and last receipt if available.",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def v2_payments(request):
    last_payment = (
        Payment.objects.filter(user=request.user)
        .order_by("-created_at")
        .values("id", "amount", "currency", "status", "receipt_url", "created_at")
        .first()
    )
    return Response(
        {
            "payment_providers": ["stripe", "paypal", "mobile_money"],
            "last_payment": last_payment,
        }
    )


# URL patterns for v2 stubs
urlpatterns = [
    # Root
    path("", api_v2_root, name="api-v2-root"),
    
    # Resources
    path("resources/", v2_resources, name="v2-resources"),
    
    # Users
    path("users/", v2_users, name="v2-users"),
    
    # Analytics
    path("analytics/", v2_analytics, name="v2-analytics"),
    
    # Courses
    path("courses/", v2_courses, name="v2-courses"),
    
    # Search
    path("search/", v2_search, name="v2-search"),
    
    # Notifications
    path("notifications/", v2_notifications, name="v2-notifications"),
    
    # Payments
    path("payments/", v2_payments, name="v2-payments"),
]
