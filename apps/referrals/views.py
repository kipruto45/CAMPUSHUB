"""
API views for referral system.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .serializers import (
    ReferralCodeSerializer,
    ReferralListSerializer,
    ReferralStatsSerializer,
    RewardHistorySerializer,
    UseReferralCodeSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_referral_code(request):
    """
    Get the current user's referral code.
    GET /api/referrals/code/
    """
    referral_code = services.ReferralService.get_or_create_referral_code(request.user)
    serializer = ReferralCodeSerializer(referral_code)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_referral_stats(request):
    """
    Get referral statistics for the current user.
    GET /api/referrals/stats/
    """
    # Initialize default tiers if needed
    services.RewardService.initialize_default_tiers()

    stats = services.ReferralService.get_user_referral_stats(request.user)
    serializer = ReferralStatsSerializer(stats)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_referrals_list(request):
    """
    Get list of referrals made by the current user.
    GET /api/referrals/list/
    """
    referrals = services.ReferralService.get_user_referrals(request.user)
    serializer = ReferralListSerializer(referrals, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def use_referral_code(request):
    """
    Use a referral code.
    POST /api/referrals/use/
    """
    serializer = UseReferralCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    code = serializer.validated_data["code"]
    success, message, referral = services.ReferralService.use_referral_code(
        code, request.user
    )

    if success:
        return Response(
            {
                "success": True,
                "message": message,
                "referral": {
                    "id": str(referral.id),
                    "referrer": referral.referrer.email,
                },
            },
            status=status.HTTP_201_CREATED,
        )
    else:
        return Response(
            {"success": False, "message": message},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_reward_history(request):
    """
    Get reward history for the current user.
    GET /api/referrals/rewards/
    """
    rewards = services.RewardService.get_user_reward_history(request.user)
    serializer = RewardHistorySerializer(rewards, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def claim_referral_rewards(request):
    """
    Manually trigger reward claim for a referral (for testing/admin purposes).
    POST /api/referrals/claim/
    """
    referral_id = request.data.get("referral_id")
    if not referral_id:
        return Response(
            {"success": False, "message": "referral_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from .models import Referral

    try:
        referral = Referral.objects.get(
            id=referral_id,
            referrer=request.user,
            status="subscribed",
            rewards_claimed=False,
        )
    except Referral.DoesNotExist:
        return Response(
            {"success": False, "message": "Referral not found or already claimed"},
            status=status.HTTP_404_NOT_FOUND,
        )

    rewards = services.RewardService.award_referral_rewards(referral)

    return Response(
        {
            "success": True,
            "message": f"Awarded {len(rewards)} rewards",
            "rewards": RewardHistorySerializer(rewards, many=True).data,
        }
    )
