"""
API views for certificates.
"""

import logging

from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.exceptions import log_exception_response
from apps.courses.models import Course
from apps.payments.freemium import Feature, can_access_feature

from .models import Certificate, CertificateTemplate, CertificateType
from .serializers import (
    CertificateDetailSerializer,
    CertificateGenerateSerializer,
    CertificateListSerializer,
    CertificateTemplateSerializer,
    CertificateTypeSerializer,
    CertificateVerifySerializer,
)
from .services import CertificateService

logger = logging.getLogger(__name__)


def _certificate_feature_denied(user):
    has_access, reason = can_access_feature(user, Feature.CERTIFICATES)
    if has_access:
        return None
    return {
        "error": "Feature not available",
        "reason": reason,
        "feature": Feature.CERTIFICATES.value,
        "upgrade_url": "/settings/billing/upgrade/",
    }


class CertificateFeatureAccessMixin:
    """Require a certificate-enabled plan for protected certificate actions."""

    def dispatch(self, request, *args, **kwargs):
        handler_kwargs = {key: value for key, value in kwargs.items() if key != "version"}
        self.args = args
        self.kwargs = handler_kwargs
        request = self.initialize_request(request, *args, **kwargs)
        self.request = request
        self.headers = self.default_response_headers

        try:
            self.initial(request, *args, **kwargs)
            denied_payload = _certificate_feature_denied(request.user)
            if denied_payload:
                response = Response(
                    denied_payload,
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                handler = getattr(
                    self,
                    request.method.lower(),
                    self.http_method_not_allowed,
                )
                response = handler(request, *args, **handler_kwargs)
        except Exception as exc:
            response = self.handle_exception(exc)

        self.response = self.finalize_response(request, response, *args, **handler_kwargs)
        return self.response


class CertificateTypeListView(CertificateFeatureAccessMixin, generics.ListAPIView):
    """List all certificate types."""

    queryset = CertificateType.objects.filter(is_active=True)
    serializer_class = CertificateTypeSerializer
    permission_classes = [IsAuthenticated]


class CertificateTemplateListView(CertificateFeatureAccessMixin, generics.ListAPIView):
    """List all certificate templates."""

    queryset = CertificateTemplate.objects.filter(is_active=True)
    serializer_class = CertificateTemplateSerializer
    permission_classes = [IsAuthenticated]


class CertificateListCreateView(CertificateFeatureAccessMixin, generics.ListCreateAPIView):
    """List all certificates for the authenticated user or create a new one."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CertificateGenerateSerializer
        return CertificateListSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Certificate.objects.none()
        return Certificate.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        serializer = CertificateGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            certificate = _generate_certificate_from_data(
                data=serializer.validated_data,
                issued_by=request.user,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        detail_serializer = CertificateDetailSerializer(certificate)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)


class CertificateDetailView(CertificateFeatureAccessMixin, generics.RetrieveAPIView):
    """Retrieve a specific certificate."""

    queryset = Certificate.objects.all()
    serializer_class = CertificateDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "unique_id"


class CertificateDownloadView(CertificateFeatureAccessMixin, APIView):
    """Download certificate as PDF."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Download Certificate",
        description="Download certificate PDF file"
    )
    def get(self, request, unique_id):
        try:
            certificate = Certificate.objects.get(unique_id=unique_id)

            # Check if user owns the certificate or is admin
            if certificate.user != request.user and not request.user.is_staff:
                return Response(
                    {"error": "You don't have permission to download this certificate"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if not certificate.pdf_file:
                return Response(
                    {"error": "PDF file not available"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response = FileResponse(
                certificate.pdf_file.open(),
                content_type="application/pdf",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="certificate_{certificate.unique_id}.pdf"'
            )
            return response

        except Certificate.DoesNotExist:
            return Response(
                {"error": "Certificate not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class CertificateVerifyView(APIView):
    """Verify a certificate by its unique ID."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Verify Certificate",
        description="Verify a certificate using its unique ID",
        responses=CertificateVerifySerializer,
    )
    def get(self, request, unique_id):
        service = CertificateService()
        result = service.verify_certificate(unique_id)

        if result["certificate"]:
            certificate = result["certificate"]
            return Response(
                {
                    "valid": result["valid"],
                    "unique_id": certificate.unique_id,
                    "title": certificate.title,
                    "recipient_name": certificate.recipient_name,
                    "issue_date": certificate.issue_date,
                    "status": certificate.status,
                    "verification_url": certificate.verification_url,
                    "message": result["message"],
                }
            )
        else:
            return Response(
                {
                    "valid": False,
                    "unique_id": unique_id,
                    "title": None,
                    "recipient_name": None,
                    "issue_date": None,
                    "status": None,
                    "verification_url": None,
                    "message": result["message"],
                },
                status=status.HTTP_404_NOT_FOUND,
            )


class CertificateGenerateView(CertificateFeatureAccessMixin, APIView):
    """Generate a new certificate."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Generate Certificate",
        description="Generate a new certificate for a user",
        request=CertificateGenerateSerializer,
    )
    def post(self, request, *args, **kwargs):
        serializer = CertificateGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            certificate = _generate_certificate_from_data(
                data=serializer.validated_data,
                issued_by=request.user,
            )
            serializer = CertificateDetailSerializer(certificate)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        except Exception:
            return log_exception_response(
                logger_obj=logger,
                log_message="Error generating certificate",
                user_message=(
                    "We couldn't generate that certificate right now. Please try again."
                ),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                field="error",
            )


class UserCertificateListView(CertificateFeatureAccessMixin, generics.ListAPIView):
    """List all certificates for a specific user."""

    serializer_class = CertificateListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Certificate.objects.none()
        user_id = self.kwargs.get("user_id")
        return Certificate.objects.filter(user_id=user_id)


def _generate_certificate_from_data(data, issued_by):
    """Create a certificate from validated request data."""
    service = CertificateService()

    try:
        user = User.objects.get(id=data["user_id"])
    except User.DoesNotExist as exc:
        raise ValueError("User not found") from exc

    certificate_type = data["certificate_type"]

    if certificate_type == "course_completion":
        try:
            course = Course.objects.get(id=data["course_id"])
        except Course.DoesNotExist as exc:
            raise ValueError("Course not found") from exc

        return service.create_course_completion_certificate(
            user=user,
            course=course,
            issued_by=issued_by,
        )

    if certificate_type == "achievement":
        from apps.gamification.models import Achievement

        try:
            achievement = Achievement.objects.get(id=data["achievement_id"])
        except Achievement.DoesNotExist as exc:
            raise ValueError("Achievement not found") from exc

        return service.create_achievement_certificate(
            user=user,
            achievement=achievement,
            issued_by=issued_by,
        )

    return service.create_custom_certificate(
        user=user,
        title=data["title"],
        description=data.get("description", ""),
        issuing_authority=data.get("issuing_authority", "CampusHub"),
        issued_by=issued_by,
        expiry_date=data.get("expiry_date"),
    )
