"""
Serializers for referral API.
"""

from rest_framework import serializers

from .models import Referral, ReferralCode, RewardHistory, RewardTier


class ReferralCodeSerializer(serializers.ModelSerializer):
    """Serializer for referral code."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    usage_count = serializers.IntegerField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = ReferralCode
        fields = [
            "id",
            "code",
            "user_email",
            "is_active",
            "is_valid",
            "usage_count",
            "max_uses",
            "expires_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "user_email",
            "usage_count",
            "is_valid",
            "created_at",
        ]


class ReferralSerializer(serializers.ModelSerializer):
    """Serializer for referral."""

    referee_email = serializers.EmailField(source="referee.email", read_only=True)
    referrer_email = serializers.EmailField(source="referrer.email", read_only=True)

    class Meta:
        model = Referral
        fields = [
            "id",
            "referrer_email",
            "referee_email",
            "email",
            "status",
            "rewards_claimed",
            "subscribed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "referrer_email",
            "referee_email",
            "rewards_claimed",
            "subscribed_at",
            "created_at",
        ]


class ReferralListSerializer(serializers.ModelSerializer):
    """Serializer for listing referrals."""

    referee_email = serializers.SerializerMethodField()
    referee_name = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = [
            "id",
            "email",
            "referee_email",
            "referee_name",
            "status",
            "rewards_claimed",
            "subscribed_at",
            "created_at",
        ]

    def get_referee_email(self, obj):
        """Get referee's email if available."""
        return obj.referee.email if obj.referee else None

    def get_referee_name(self, obj):
        """Get referee's full name if available."""
        if obj.referee:
            full_name = obj.referee.full_name
            if full_name:
                return full_name
            first_name = obj.referee.first_name or ""
            last_name = obj.referee.last_name or ""
            return f"{first_name} {last_name}".strip() or None
        return None


class RewardHistorySerializer(serializers.ModelSerializer):
    """Serializer for reward history."""

    class Meta:
        model = RewardHistory
        fields = [
            "id",
            "reward_type",
            "reward_value",
            "description",
            "created_at",
        ]
        read_only_fields = fields


class RewardTierSerializer(serializers.ModelSerializer):
    """Serializer for reward tiers."""

    class Meta:
        model = RewardTier
        fields = [
            "id",
            "name",
            "min_referrals",
            "points",
            "premium_days",
            "badge",
            "is_active",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ReferralStatsSerializer(serializers.Serializer):
    """Serializer for referral statistics."""

    total_referrals = serializers.IntegerField()
    registered_count = serializers.IntegerField()
    subscribed_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    current_tier = serializers.DictField(required=False)
    next_tier = serializers.DictField(required=False)
    referrals_to_next_tier = serializers.IntegerField()


class UseReferralCodeSerializer(serializers.Serializer):
    """Serializer for using a referral code."""

    code = serializers.CharField(max_length=20, required=True)

    def validate_code(self, value):
        """Validate the referral code format."""
        value = value.upper().strip()
        if len(value) < 4:
            raise serializers.ValidationError("Invalid referral code format")
        return value
