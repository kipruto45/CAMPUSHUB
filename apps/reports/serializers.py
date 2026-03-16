"""
Serializers for reports app.
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for Report model."""

    reporter_details = UserSerializer(source="reporter", read_only=True)
    reviewed_by_details = UserSerializer(source="reviewed_by", read_only=True)
    target_type = serializers.SerializerMethodField()
    target_title = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "reporter",
            "reporter_details",
            "resource",
            "comment",
            "target_type",
            "target_title",
            "reason_type",
            "message",
            "status",
            "reviewed_by",
            "reviewed_by_details",
            "resolution_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reporter",
            "status",
            "reviewed_by",
            "resolution_note",
            "created_at",
            "updated_at",
        ]

    def get_target_type(self, obj) -> str:
        return obj.get_target_type()

    def get_target_title(self, obj) -> str:
        return obj.get_target_title()


class ReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reports."""

    class Meta:
        model = Report
        fields = ["resource", "comment", "reason_type", "message"]

    def validate(self, data):
        """Ensure either resource or comment is provided."""
        if not data.get("resource") and not data.get("comment"):
            raise serializers.ValidationError(
                "Either resource or comment must be provided."
            )
        if data.get("resource") and data.get("comment"):
            raise serializers.ValidationError(
                "Cannot report both resource and comment at once."
            )
        request = self.context.get("request")
        reporter = request.user if request else None
        if reporter:
            query = Report.objects.filter(
                reporter=reporter, status__in=["open", "in_review"]
            )
            if data.get("resource"):
                resource = data["resource"]
                if not (resource.status == "approved" and resource.is_public) and not (
                    resource.uploaded_by == reporter
                    or reporter.is_admin
                    or reporter.is_moderator
                ):
                    raise serializers.ValidationError(
                        "You cannot report this resource."
                    )
                query = query.filter(resource=resource)
            if data.get("comment"):
                comment = data["comment"]
                comment_resource = comment.resource
                if not (
                    comment_resource.status == "approved" and comment_resource.is_public
                ) and not (
                    comment_resource.uploaded_by == reporter
                    or reporter.is_admin
                    or reporter.is_moderator
                ):
                    raise serializers.ValidationError("You cannot report this comment.")
                query = query.filter(comment=comment)
            if query.exists():
                raise serializers.ValidationError(
                    "You already have an active report for this content."
                )
        return data


class ReportUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating reports (admin/moderator)."""

    class Meta:
        model = Report
        fields = ["status", "resolution_note"]

    def validate_status(self, value):
        """Validate status transitions."""
        valid_transitions = {
            "open": ["in_review", "dismissed"],
            "in_review": ["resolved", "dismissed"],
            "resolved": [],
            "dismissed": [],
        }
        current_status = self.instance.status if self.instance else "open"
        if value not in valid_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f"Cannot change status from {current_status} to {value}."
            )
        return value


class ReportListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for report list views."""

    reporter_name = serializers.CharField(source="reporter.full_name", read_only=True)
    target_type = serializers.SerializerMethodField()
    target_title = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "id",
            "reporter_name",
            "target_type",
            "target_title",
            "reason_type",
            "status",
            "created_at",
        ]

    def get_target_type(self, obj) -> str:
        return obj.get_target_type()

    def get_target_title(self, obj) -> str:
        return obj.get_target_title()
