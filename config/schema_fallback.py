"""
Schema generation fallbacks for views without explicit serializers.
"""

from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView


class SchemaFallbackSerializer(serializers.Serializer):
    """Used only for schema introspection when a view has no serializer."""

    detail = serializers.CharField(required=False)


_ORIGINAL_GET_SERIALIZER_CLASS = GenericAPIView.get_serializer_class


def _get_serializer_class_with_fallback(self):
    serializer_class = getattr(self, "serializer_class", None)
    if serializer_class is not None:
        return serializer_class
    if getattr(self, "swagger_fake_view", False):
        return SchemaFallbackSerializer
    return _ORIGINAL_GET_SERIALIZER_CLASS(self)


def apply_schema_fallback() -> None:
    """
    Apply serializer fallbacks once, without affecting normal runtime logic.
    """

    if getattr(APIView, "_campushub_schema_fallback_applied", False):
        return

    APIView.serializer_class = SchemaFallbackSerializer
    GenericAPIView.get_serializer_class = _get_serializer_class_with_fallback
    APIView._campushub_schema_fallback_applied = True
