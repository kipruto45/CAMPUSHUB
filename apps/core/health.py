"""
Health check endpoint for monitoring.
"""

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return "healthy", True
    except Exception as e:
        return f"unhealthy: {str(e)}", False


def _check_cache():
    try:
        cache.set("health_check", "ok", 10)
        if cache.get("health_check") == "ok":
            cache.delete("health_check")
            return "healthy", True
        return "unhealthy: cache not working", False
    except Exception as e:
        return f"unhealthy: {str(e)}", False


def _check_channel_layer():
    layers = getattr(settings, "CHANNEL_LAYERS", {}) or {}
    backend = str(layers.get("default", {}).get("BACKEND", "")).strip()
    if backend:
        return f"healthy: {backend}", True
    return "unhealthy: channel layer backend missing", False


def _build_status(include_channel_layer=False):
    payload = {"status": "healthy"}

    payload["database"], database_ok = _check_database()
    payload["cache"], cache_ok = _check_cache()

    checks = [database_ok, cache_ok]
    if include_channel_layer:
        payload["channel_layer"], channel_ok = _check_channel_layer()
        checks.append(channel_ok)

    overall_status = 200 if all(checks) else 503
    if overall_status == 503:
        payload["status"] = "unhealthy" if not include_channel_layer else "not_ready"

    return payload, overall_status


@api_view(["GET"])
def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.

    Returns:
        200 OK: All systems operational
        503 Service Unavailable: One or more systems down
    """
    health_status, overall_status = _build_status(include_channel_layer=False)

    return Response(health_status, status=overall_status)


@api_view(["GET"])
def readiness_check(request):
    """
    Readiness check for Kubernetes/Container orchestration.
    """
    readiness_status, overall_status = _build_status(include_channel_layer=True)
    if overall_status == 200:
        readiness_status["status"] = "ready"
    return Response(readiness_status, status=overall_status)


@api_view(["GET"])
def maintenance_check(request):
    """
    Maintenance mode check endpoint for mobile app.
    
    Returns:
        200 OK: App is operational (maintenance_mode: false)
        200 OK: App is in maintenance mode (maintenance_mode: true)
    """
    maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)
    
    # Check if request IP is allowed during maintenance
    allowed_ips = getattr(settings, 'MAINTENANCE_ALLOWED_IPS', '')
    if allowed_ips:
        allowed_ip_list = [ip.strip() for ip in allowed_ips.split(',') if ip.strip()]
        client_ip = get_client_ip(request)
        if client_ip in allowed_ip_list:
            maintenance_mode = False
    
    response_data = {
        "maintenance_mode": maintenance_mode,
        "message": getattr(settings, 'MAINTENANCE_MESSAGE', '') if maintenance_mode else None,
    }
    
    return Response(response_data, status=200)


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip
