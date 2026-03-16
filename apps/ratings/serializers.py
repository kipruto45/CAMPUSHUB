"""
Serializers for ratings app.
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Rating


class RatingSerializer(serializers.ModelSerializer):
    """Serializer for Rating model."""

    user_details = UserSerializer(source="user", read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "user", "user_details", "resource", "value", "created_at"]
        read_only_fields = ["id", "created_at"]


class RatingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ratings."""

    class Meta:
        model = Rating
        fields = ["resource", "value"]
