"""Lightweight REST endpoints for direct messaging."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model

from .models import Message

User = get_user_model()


class DirectMessageListView(APIView):
    """List direct messages between the authenticated user and another user."""

    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            other = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        messages = Message.objects.filter(
            sender__in=[request.user, other],
            recipient__in=[request.user, other],
        ).order_by("created_at")[:200]

        data = [
            {
                "id": str(m.id),
                "sender_id": m.sender_id,
                "recipient_id": m.recipient_id,
                "body": m.body,
                "is_read": m.is_read,
                "read_at": m.read_at,
                "created_at": m.created_at,
            }
            for m in messages
        ]
        return Response({"messages": data})


class DirectMessageSendView(APIView):
    """Send a direct message."""

    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        body = str(request.data.get("body") or "").strip()
        if not body:
            return Response({"error": "body is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            recipient = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            body=body,
        )

        return Response(
            {
                "id": str(message.id),
                "sender_id": message.sender_id,
                "recipient_id": message.recipient_id,
                "body": message.body,
                "created_at": message.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

