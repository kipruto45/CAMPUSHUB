"""
Tests for the CampusHub AI assistant endpoints.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.resources.models import Resource


@pytest.fixture
def api_client():
    """Create an API client for AI endpoint tests."""
    return APIClient()


@pytest.fixture
def chat_user(db):
    """Create an authenticated student for AI assistant tests."""
    return User.objects.create_user(
        email="ai-student@example.com",
        password="SecurePass123!",
        full_name="AI Student",
        role="STUDENT",
    )


@pytest.fixture
def approved_resource(db, chat_user):
    """Create a searchable resource for chat retrieval flows."""
    return Resource.objects.create(
        title="Data Structures Notes",
        description="Clear notes on stacks, queues, linked lists, and trees.",
        ai_summary="A concise guide to core data structures and how to study them.",
        resource_type="notes",
        status="approved",
        uploaded_by=chat_user,
    )


@pytest.mark.django_db
class TestAIChatbot:
    """Regression tests for the mini-ChatGPT assistant API."""

    def test_chatbot_returns_platform_help(self, api_client, chat_user):
        api_client.force_authenticate(user=chat_user)

        response = api_client.post(
            "/api/v1/ai/chat/",
            {"message": "How do I upload a resource?"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "upload a resource" in response.data["message"].lower()
        assert response.data["metadata"]["intent"] == "platform_help"

    def test_chatbot_returns_resource_sources(self, api_client, chat_user, approved_resource):
        api_client.force_authenticate(user=chat_user)

        response = api_client.post(
            "/api/v1/ai/chat/",
            {"message": "Find notes for Data Structures"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["metadata"]["intent"] == "resource_search"
        assert response.data["metadata"]["matches_found"] >= 1
        assert any(
            source.get("id") == str(approved_resource.id)
            for source in response.data["sources"]
        )

    def test_chatbot_summary_queries_use_summary_intent(
        self,
        api_client,
        chat_user,
        approved_resource,
    ):
        api_client.force_authenticate(user=chat_user)

        response = api_client.post(
            "/api/v1/ai/chat/",
            {"message": "Summarize Data Structures Notes"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["metadata"]["intent"] == "summary"
        assert "summary" in response.data["message"].lower()
        assert any(
            source.get("id") == str(approved_resource.id)
            for source in response.data["sources"]
        )
