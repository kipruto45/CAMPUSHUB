"""
Health check endpoint for monitoring.
"""

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
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


def _check_cloudinary():
    """Check Cloudinary connectivity."""
    cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', None)
    api_key = getattr(settings, 'CLOUDINARY_API_KEY', None)
    enabled = getattr(settings, 'CLOUDINARY_ENABLED', False)
    
    if not enabled:
        return "disabled", True
    
    if not cloud_name or not api_key:
        return "unhealthy: Cloudinary credentials not configured", False
    
    try:
        from cloudinary.api import ping
        result = ping()
        if result.get('status') == 'ok':
            return f"healthy: cloud_name={cloud_name}", True
        return f"unhealthy: unexpected response: {result}", False
    except Exception as e:
        return f"unhealthy: {str(e)}", False


def _build_status(include_channel_layer=False, include_cloudinary=False):
    payload = {"status": "healthy"}

    payload["database"], database_ok = _check_database()
    payload["cache"], cache_ok = _check_cache()

    checks = [database_ok, cache_ok]
    if include_channel_layer:
        payload["channel_layer"], channel_ok = _check_channel_layer()
        checks.append(channel_ok)
    if include_cloudinary:
        payload["cloudinary"], cloudinary_ok = _check_cloudinary()
        checks.append(cloudinary_ok)

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


@api_view(["POST"])
def test_email(request):
    """
    Test email sending endpoint.
    
    POST body (optional):
        - email: recipient email address (defaults to EMAIL_HOST_USER)
    
    Returns:
        200 OK: Email sent successfully
        400 Bad Request: Invalid request
        500 Error: Email sending failed
    """
    from django.conf import settings
    from django.core.mail import get_connection
    from django.core.mail.message import EmailMessage
    
    # Get recipient
    recipient = request.data.get("email") or getattr(settings, "EMAIL_HOST_USER", None)
    if not recipient:
        return Response({
            "status": "error",
            "message": "No recipient email specified and EMAIL_HOST_USER not configured"
        }, status=400)
    
    try:
        # Test SMTP connection
        connection = get_connection(fail_silently=False)
        connection.open()
        
        # Send test email
        email = EmailMessage(
            subject="Test Email from CampusHub",
            body="This is a test email from CampusHub. If you received this, email delivery is working correctly!",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@campushub.com"),
            to=[recipient],
        )
        email.send(fail_silently=False)
        
        connection.close()
        
        return Response({
            "status": "success",
            "message": f"Test email sent successfully to {recipient}"
        }, status=200)
        
    except Exception as e:
        return Response({
            "status": "error",
            "message": f"Failed to send email: {str(e)}"
        }, status=500)


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


@api_view(["POST"])
@permission_classes([AllowAny])
def test_cloudinary(request):
    """
    Test Cloudinary upload endpoint.
    
    Tests that Cloudinary is properly configured and can accept uploads.
    
    Returns:
        200 OK: Cloudinary is working
        400 Bad Request: Cloudinary is disabled
        500 Error: Cloudinary test failed
    """
    from django.conf import settings
    
    enabled = getattr(settings, 'CLOUDINARY_ENABLED', False)
    if not enabled:
        return Response({
            "status": "disabled",
            "message": "Cloudinary is not enabled"
        }, status=400)
    
    cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', None)
    api_key = getattr(settings, 'CLOUDINARY_API_KEY', None)
    
    if not cloud_name or not api_key:
        return Response({
            "status": "error",
            "message": "Cloudinary credentials not configured"
        }, status=500)
    
    try:
        from cloudinary.api import ping
        
        # Test connection to Cloudinary
        result = ping()
        
        return Response({
            "status": "success",
            "message": f"Cloudinary is working. Cloud: {cloud_name}",
            "result": result
        })
        
    except Exception as e:
        return Response({
            "status": "error",
            "message": f"Cloudinary test failed: {str(e)}"
        }, status=500)
