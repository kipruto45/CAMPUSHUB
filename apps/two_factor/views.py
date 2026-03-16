"""
API views for Two-Factor Authentication.
"""

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.authentication import JWTAuthentication
from apps.two_factor.services import TwoFactorService


@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def two_factor_status(request):
    status_payload = TwoFactorService.get_2fa_status(request.user)
    return Response(status_payload)


@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def two_factor_setup(request):
    method = str(request.data.get("method") or "totp").strip().lower()
    success, data = TwoFactorService.setup_2fa_for_user(request.user, method=method)
    if success:
        return Response(data)
    return Response(data, status=400)


@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def two_factor_enable(request):
    code = str(request.data.get("code") or "").strip()
    if not code:
        return Response({"detail": "Verification code is required."}, status=400)

    success, message = TwoFactorService.enable_2fa(request.user, verified_code=code)
    if not success:
        return Response({"detail": message}, status=400)

    from apps.two_factor.models import TwoFactorSetting

    settings = TwoFactorSetting.objects.filter(user=request.user).first()
    codes_list = [item.get("code") for item in (settings.backup_codes or [])] if settings else []

    return Response(
        {
            "message": message,
            "backup_codes": codes_list,
        }
    )


@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def two_factor_disable(request):
    password = str(request.data.get("password") or "")
    if not password:
        return Response({"detail": "Password is required."}, status=400)

    success, message = TwoFactorService.disable_2fa(request.user, password=password)
    if success:
        return Response({"message": message})
    return Response({"detail": message}, status=400)


@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def two_factor_recovery_codes(request):
    password = str(request.data.get("password") or "")
    if not password:
        return Response({"detail": "Password is required."}, status=400)

    if not request.user.check_password(password):
        return Response({"detail": "Invalid password."}, status=400)

    from apps.two_factor.models import TwoFactorSetting

    settings = TwoFactorSetting.objects.filter(user=request.user).first()
    if not settings or not settings.enabled:
        return Response({"detail": "Two-factor authentication is not enabled."}, status=400)

    settings.generate_backup_codes()
    settings.save(update_fields=["backup_codes", "updated_at"])
    codes_list = [item.get("code") for item in (settings.backup_codes or [])]

    return Response(
        {
            "message": "Recovery codes generated successfully.",
            "backup_codes": codes_list,
        }
    )
