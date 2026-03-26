"""
Serializers for certificates API.
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.certificates.models import Certificate, CertificateTemplate, CertificateType


class CertificateTypeSerializer(serializers.ModelSerializer):
    """Serializer for CertificateType model."""

    class Meta:
        model = CertificateType
        fields = [
            "id",
            "name",
            "slug",
            "type",
            "description",
            "is_active",
            "requires_verification",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CertificateTemplateSerializer(serializers.ModelSerializer):
    """Serializer for CertificateTemplate model."""

    certificate_type_name = serializers.CharField(
        source="certificate_type.name", read_only=True
    )

    class Meta:
        model = CertificateTemplate
        fields = [
            "id",
            "name",
            "slug",
            "certificate_type",
            "certificate_type_name",
            "title",
            "description",
            "header_image",
            "footer_text",
            "background_color",
            "border_color",
            "text_color",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CertificateListSerializer(serializers.ModelSerializer):
    """Serializer for listing certificates."""

    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    certificate_type_name = serializers.CharField(
        source="certificate_type.name", read_only=True
    )

    class Meta:
        model = Certificate
        fields = [
            "id",
            "unique_id",
            "user_name",
            "certificate_type",
            "certificate_type_name",
            "title",
            "recipient_name",
            "issue_date",
            "expiry_date",
            "status",
            "verification_url",
            "created_at",
        ]
        read_only_fields = fields


class CertificateDetailSerializer(serializers.ModelSerializer):
    """Serializer for certificate details."""

    user = UserSerializer(read_only=True)
    certificate_type = CertificateTypeSerializer(read_only=True)
    template = CertificateTemplateSerializer(read_only=True)
    issued_by_user = serializers.CharField(
        source="issued_by.get_full_name", read_only=True
    )
    course_name = serializers.CharField(source="course.name", read_only=True)
    achievement_name = serializers.CharField(
        source="achievement.name", read_only=True
    )

    class Meta:
        model = Certificate
        fields = [
            "id",
            "unique_id",
            "user",
            "certificate_type",
            "template",
            "title",
            "recipient_name",
            "description",
            "course",
            "course_name",
            "achievement",
            "achievement_name",
            "issuing_authority",
            "issued_by",
            "issued_by_user",
            "issue_date",
            "expiry_date",
            "status",
            "verification_url",
            "qr_code",
            "pdf_file",
            "metadata",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CertificateGenerateSerializer(serializers.Serializer):
    """Serializer for generating certificates."""

    certificate_type = serializers.ChoiceField(choices=CertificateType.TYPE_CHOICES)
    user_id = serializers.IntegerField()
    course_id = serializers.UUIDField(required=False)
    achievement_id = serializers.IntegerField(required=False)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    issuing_authority = serializers.CharField(
        max_length=255, default="CampusHub"
    )
    expiry_date = serializers.DateTimeField(required=False)

    def validate(self, data):
        """Validate the input data."""
        certificate_type = data.get("certificate_type")

        if certificate_type == "course_completion" and not data.get("course_id"):
            raise serializers.ValidationError(
                "course_id is required for course completion certificates"
            )

        if certificate_type == "achievement" and not data.get("achievement_id"):
            raise serializers.ValidationError(
                "achievement_id is required for achievement certificates"
            )

        return data


class CertificateVerifySerializer(serializers.Serializer):
    """Serializer for certificate verification response."""

    valid = serializers.BooleanField()
    unique_id = serializers.CharField()
    title = serializers.CharField()
    recipient_name = serializers.CharField()
    issue_date = serializers.DateTimeField()
    status = serializers.CharField()
    verification_url = serializers.URLField()
    message = serializers.CharField()
