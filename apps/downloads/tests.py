"""
Tests for downloads app.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.resources.models import Resource

User = get_user_model()


class DownloadHistoryTests(APITestCase):
    """Tests for download history endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_get_download_history_empty(self):
        """Test getting empty download history."""
        url = reverse("downloads:download-history-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_get_download_history_unauthenticated(self):
        """Test unauthenticated request is rejected."""
        self.client.force_authenticate(user=None)
        url = reverse("downloads:download-history-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DownloadResourceTests(APITestCase):
    """Tests for resource download endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    @patch("apps.resources.models.Resource.objects.get")
    def test_download_nonexistent_resource(self, mock_get):
        """Test downloading non-existent resource fails."""
        mock_get.side_effect = Resource.DoesNotExist

        url = reverse(
            "downloads:download-resource",
            kwargs={"resource_id": "00000000-0000-0000-0000-000000000001"},
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_resource_unauthenticated(self):
        """Test unauthenticated download is rejected."""
        self.client.force_authenticate(user=None)

        url = reverse(
            "downloads:download-resource",
            kwargs={"resource_id": "00000000-0000-0000-0000-000000000001"},
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DownloadStatsTests(APITestCase):
    """Tests for download statistics endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_get_download_stats(self):
        """Test getting download statistics."""
        url = reverse("downloads:download-stats")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_downloads", response.data)
        self.assertIn("unique_resources", response.data)
        self.assertIn("recent_downloads", response.data)

    def test_get_stats_unauthenticated(self):
        """Test unauthenticated request is rejected."""
        self.client.force_authenticate(user=None)

        url = reverse("downloads:download-stats")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RecentDownloadsTests(APITestCase):
    """Tests for recent downloads endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

    def test_get_recent_downloads(self):
        """Test getting recent downloads."""
        url = reverse("downloads:recent-downloads")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_get_recent_unauthenticated(self):
        """Test unauthenticated request is rejected."""
        self.client.force_authenticate(user=None)

        url = reverse("downloads:recent-downloads")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
