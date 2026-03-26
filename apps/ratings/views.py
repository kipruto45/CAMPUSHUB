"""
Views for ratings app.
"""

from django.db.models import Avg
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response

from .models import Rating
from .serializers import RatingCreateSerializer, RatingSerializer


def _recalculate_average_rating(resource):
    """Recalculate and persist average rating for a resource."""
    average = (
        Rating.objects.filter(resource=resource).aggregate(avg=Avg("value"))["avg"] or 0
    )
    resource.average_rating = round(average, 2)
    resource.save(update_fields=["average_rating"])


class RatingViewSet(viewsets.ModelViewSet):
    """ViewSet for Rating model."""

    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Rating.objects.none()
        return Rating.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = RatingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if rating already exists
        rating = Rating.objects.filter(
            user=request.user, resource=serializer.validated_data["resource"]
        ).first()

        if rating:
            # Update existing rating
            rating.value = serializer.validated_data["value"]
            rating.save()
            # Recalculate average
            _recalculate_average_rating(rating.resource)
            return Response(RatingSerializer(rating).data)

        # Create new rating
        rating = Rating.objects.create(
            user=request.user,
            resource=serializer.validated_data["resource"],
            value=serializer.validated_data["value"],
        )

        # Recalculate average
        _recalculate_average_rating(rating.resource)

        return Response(RatingSerializer(rating).data, status=status.HTTP_201_CREATED)


class ResourceRatingListView(generics.ListAPIView):
    """List ratings for a resource."""

    serializer_class = RatingSerializer

    def get_queryset(self):
        resource_id = self.kwargs.get("resource_id")
        return Rating.objects.filter(resource_id=resource_id)


class RateResourceView(generics.CreateAPIView):
    """Rate a resource."""

    serializer_class = RatingCreateSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="api_ratings_resources_rate_create")
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        resource_id = kwargs.get("resource_id")
        payload = request.data.copy()
        payload["resource"] = resource_id
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)

        # Check if rating already exists
        rating = Rating.objects.filter(
            user=request.user, resource_id=resource_id
        ).first()

        if rating:
            rating.value = serializer.validated_data["value"]
            rating.save()
        else:
            rating = Rating.objects.create(
                user=request.user,
                resource_id=resource_id,
                value=serializer.validated_data["value"],
            )

        # Recalculate average
        _recalculate_average_rating(rating.resource)

        return Response(RatingSerializer(rating).data, status=status.HTTP_201_CREATED)
