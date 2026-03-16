"""Gamification API Views for CampusHub."""

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.authentication import JWTAuthentication
from apps.gamification.services import GamificationService


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def user_gamification_stats(request):
    """
    Get current user's gamification statistics.
    """
    return Response(GamificationService.get_user_stats_payload(request.user))


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def leaderboard(request):
    """
    Get leaderboard rankings.
    Query params: period (daily, weekly, monthly, all_time)
    """
    period = request.query_params.get('period', 'all_time')
    return Response(
        GamificationService.get_leaderboard_payload(
            user=request.user,
            period=period,
        )
    )


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def check_badges(request):
    """
    Check and award any new badges based on user's current stats.
    Accepts POST for mobile parity and GET for backward compatibility.
    """
    return Response(GamificationService.award_available_badges(request.user))
