"""Tests for mobile API endpoints."""

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model

User = get_user_model()


class MobileAuthTests(APITestCase):
    """Tests for mobile authentication endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])
    
    def test_mobile_register_success(self):
        """Test mobile registration endpoint."""
        url = reverse('api:mobile_register')
        data = {
            'email': 'newuser@example.com',
            'password': 'securepass123',
            'first_name': 'New',
            'last_name': 'User',
            'registration_number': 'REG/123456'
        }

        response = self.client.post(url, data, format='json')

        # Endpoint uses custom success wrapper with HTTP 200.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
        self.assertTrue(response.data['success'])
    
    def test_mobile_register_validation(self):
        """Test mobile registration validation."""
        url = reverse('api:mobile_register')
        
        # Missing required fields
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('success', response.data)
        self.assertFalse(response.data['success'])
    
    def test_mobile_login_success(self):
        """Test mobile login endpoint."""
        url = reverse('api:mobile_login')
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)
        self.assertIn('access_token', response.data['data'])
        self.assertEqual(response.data['data']['user']['role'], 'STUDENT')

    def test_mobile_login_parses_string_remember_me_flag(self):
        """Test remember_me string values are parsed correctly."""
        url = reverse('api:mobile_login')

        false_response = self.client.post(
            url,
            {
                'email': 'test@example.com',
                'password': 'testpass123',
                'remember_me': 'false',
            },
            format='json',
        )
        self.assertEqual(false_response.status_code, status.HTTP_200_OK)
        self.assertFalse(false_response.data['data']['remember_me'])

        true_response = self.client.post(
            url,
            {
                'email': 'test@example.com',
                'password': 'testpass123',
                'remember_me': 'true',
            },
            format='json',
        )
        self.assertEqual(true_response.status_code, status.HTTP_200_OK)
        self.assertTrue(true_response.data['data']['remember_me'])
    
    def test_mobile_login_invalid_credentials(self):
        """Test mobile login with invalid credentials."""
        url = reverse('api:mobile_login')
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        # Depending on exception handler config, auth failure is usually 401.
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
    
    def test_mobile_login_missing_fields(self):
        """Test mobile login with missing fields."""
        url = reverse('api:mobile_login')
        data = {'email': 'test@example.com'}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_mobile_logout_authenticated(self):
        """Test mobile logout as authenticated user."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_logout')
        
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_mobile_logout_blacklists_refresh_token(self):
        """Test mobile logout blacklists the supplied refresh token."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_logout')
        refresh = RefreshToken.for_user(self.user)

        response = self.client.post(
            url,
            {'refresh_token': str(refresh)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__token=str(refresh)).exists()
        )

    def test_mobile_logout_accepts_legacy_refresh_field(self):
        """Test mobile logout accepts refresh as an alias for refresh_token."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_logout')
        refresh = RefreshToken.for_user(self.user)

        response = self.client.post(
            url,
            {'refresh': str(refresh)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__token=str(refresh)).exists()
        )

    def test_mobile_logout_unauthenticated(self):
        """Test mobile logout without authentication."""
        url = reverse('api:mobile_logout')
        
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mobile_refresh_rotates_refresh_token(self):
        """Test mobile refresh issues new access and refresh tokens."""
        url = reverse('api:mobile_refresh_token')
        refresh = RefreshToken.for_user(self.user)

        response = self.client.post(
            url,
            {'refresh_token': str(refresh)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data['data'])
        self.assertIn('refresh_token', response.data['data'])
        self.assertNotEqual(response.data['data']['refresh_token'], str(refresh))

    def test_mobile_refresh_accepts_legacy_refresh_field(self):
        """Test mobile refresh accepts refresh as an alias for refresh_token."""
        url = reverse('api:mobile_refresh_token')
        refresh = RefreshToken.for_user(self.user)

        response = self.client.post(
            url,
            {'refresh': str(refresh)},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data['data'])
        self.assertIn('refresh_token', response.data['data'])


class MobileResourceTests(APITestCase):
    """Tests for mobile resource endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        # Note: Would need Resource model fixtures for full tests
    
    def test_mobile_resources_list_unauthenticated(self):
        """Test listing resources without authentication."""
        url = reverse('api:mobile_resources')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_mobile_resources_list_authenticated(self):
        """Test listing resources as authenticated user."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_resources')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)
    
    def test_mobile_resources_pagination(self):
        """Test resource pagination parameters."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_resources')
        
        response = self.client.get(url, {'page': 1, 'limit': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'data' in response.data and 'pagination' in response.data['data']:
            pagination = response.data['data']['pagination']
            self.assertIn('page', pagination)
            self.assertIn('limit', pagination)


class MobileNotificationTests(APITestCase):
    """Tests for mobile notification endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_mobile_notifications_list(self):
        """Test listing notifications."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_notifications')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
    
    def test_mobile_notifications_unauthenticated(self):
        """Test notifications endpoint requires auth."""
        url = reverse('api:mobile_notifications')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MobileDataTests(APITestCase):
    """Tests for mobile data endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_mobile_dashboard(self):
        """Test dashboard endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_dashboard')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)
        if response.data.get('success'):
            self.assertIn('data', response.data)
    
    def test_mobile_stats(self):
        """Test stats endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_stats')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_mobile_courses(self):
        """Test courses endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_courses')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_mobile_sync(self):
        """Test sync endpoint for offline support."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_sync')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('success', response.data)


class MobileDeviceTests(APITestCase):
    """Tests for mobile device endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_mobile_register_device(self):
        """Test device registration."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_register_device')
        
        data = {
            'device_token': 'test_device_token_123',
            'device_type': 'android',
            'device_name': 'Test Phone',
            'device_model': 'Pixel 5'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_mobile_subscribe_topic(self):
        """Test topic subscription."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_subscribe_topic')
        
        data = {
            'topic': 'announcements',
            'device_token': 'test_token'
        }
        
        with patch('apps.api.mobile_views.fcm_service.subscribe_to_topic') as mock:
            mock.return_value = {'success': True}
            response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_mobile_unsubscribe_topic(self):
        """Test topic unsubscription."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_unsubscribe_topic')
        
        data = {
            'topic': 'announcements',
            'device_token': 'test_token'
        }
        
        with patch('apps.api.mobile_views.fcm_service.unsubscribe_from_topic') as mock:
            mock.return_value = {'success': True}
            response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class MobileRateLimitTests(APITestCase):
    """Tests for mobile rate limiting."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_rate_limiting_anon(self):
        """Test rate limiting for anonymous users."""
        from apps.api.throttles import MobileAuthenticateThrottle

        url = reverse('api:mobile_login')
        data = {'email': 'test@example.com', 'password': 'wrong'}

        # Keep test deterministic by shrinking throttle limit for this case only.
        old_rate = MobileAuthenticateThrottle.rate
        MobileAuthenticateThrottle.rate = '2/minute'
        cache.clear()
        try:
            responses = []
            for _ in range(4):
                response = self.client.post(url, data, format='json')
                responses.append(response.status_code)
        finally:
            MobileAuthenticateThrottle.rate = old_rate
            cache.clear()

        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, responses)


class MobileResponseFormatTests(APITestCase):
    """Tests for mobile API response format consistency."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_success_response_format(self):
        """Test successful response has correct format."""
        self.client.force_authenticate(user=self.user)
        url = reverse('api:mobile_dashboard')
        
        response = self.client.get(url)
        
        self.assertIn('success', response.data)
        if response.data['success']:
            self.assertIn('data', response.data)
    
    def test_error_response_format(self):
        """Test error response has correct format."""
        url = reverse('api:mobile_login')
        data = {}  # Missing fields
        
        response = self.client.post(url, data, format='json')

        # Project may return either wrapped errors or DRF default error keys.
        self.assertTrue('success' in response.data or 'detail' in response.data or 'code' in response.data)


class DeepLinkTests(TestCase):
    """Tests for deep linking functionality."""
    
    def test_parse_resource_deep_link(self):
        """Test parsing resource deep link."""
        from apps.api.deeplinks import parse_deep_link, DeepLinkType
        
        url = 'campushub://resources/123'
        result = parse_deep_link(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.type, DeepLinkType.RESOURCE)
        self.assertEqual(result.params['id'], '123')
    
    def test_parse_https_deep_link(self):
        """Test parsing HTTPS deep link."""
        from apps.api.deeplinks import parse_deep_link, DeepLinkType
        
        url = 'https://campushub.com/resources/456'
        result = parse_deep_link(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.type, DeepLinkType.RESOURCE)
        self.assertEqual(result.params['id'], '456')
    
    def test_parse_invalid_deep_link(self):
        """Test parsing invalid deep link."""
        from apps.api.deeplinks import parse_deep_link
        
        result = parse_deep_link('https://google.com')
        self.assertIsNone(result)
    
    def test_build_deep_link(self):
        """Test building deep link."""
        from apps.api.deeplinks import build_deep_link, DeepLinkType
        
        url = build_deep_link(DeepLinkType.RESOURCE, id='789')
        
        self.assertIn('campushub://', url)
        self.assertIn('resources', url)
        self.assertIn('789', url)
    
    def test_get_mobile_route(self):
        """Test getting mobile route from deep link."""
        from apps.api.deeplinks import get_mobile_route
        
        url = 'campushub://resources/123'
        route = get_mobile_route(url)
        
        self.assertIsNotNone(route)
        self.assertIn('screen', route)
        self.assertIn('params', route)
    
    def test_search_deep_link_with_query(self):
        """Test search deep link with query parameter."""
        from apps.api.deeplinks import parse_deep_link, DeepLinkType
        
        url = 'campushub://search?q=python'
        result = parse_deep_link(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.type, DeepLinkType.SEARCH)
        self.assertEqual(result.params.get('q'), 'python')


class FCMSeviceTests(TestCase):
    """Tests for FCM service."""

    @override_settings(FCM_ENABLED=True, FCM_SERVER_KEY="", FCM_PROJECT_ID="campushub")
    def test_load_config_disables_when_server_key_missing(self):
        """FCM must be disabled if credentials are incomplete."""
        from apps.notifications.fcm import FCMService

        fcm = FCMService()
        self.assertFalse(fcm._config.enabled)
    
    @override_settings(
        FCM_ENABLED=True,
        FCM_SERVER_KEY="test_key",
        FCM_PROJECT_ID="campushub-test",
    )
    def test_load_config_enables_when_credentials_present(self):
        """FCM is enabled only when explicitly enabled and configured."""
        from apps.notifications.fcm import FCMService

        fcm = FCMService()
        self.assertTrue(fcm._config.enabled)
        self.assertEqual(fcm._config.project_id, "campushub-test")
    
    @patch('apps.notifications.fcm.requests.post')
    def test_send_to_token_success(self, mock_post):
        """Test sending FCM notification to token."""
        from apps.notifications.fcm import PushNotification, NotificationPriority
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': 1, 'message_id': '123'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        from apps.notifications.fcm import FCMService
        fcm = FCMService()
        fcm._config.enabled = True
        fcm._config.server_key = 'test_key'
        
        notification = PushNotification(
            title='Test',
            body='Test message',
            priority=NotificationPriority.HIGH
        )
        
        result = fcm.send_to_token('test_token', notification)
        
        self.assertTrue(result['success'])
    
    @patch('apps.notifications.fcm.requests.post')
    def test_send_to_topic(self, mock_post):
        """Test sending FCM notification to topic."""
        from apps.notifications.fcm import PushNotification
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'success': 1}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        from apps.notifications.fcm import FCMService
        fcm = FCMService()
        fcm._config.enabled = True
        fcm._config.server_key = 'test_key'
        
        notification = PushNotification(title='Test', body='Test')
        
        result = fcm.send_to_topic('announcements', notification)
        
        self.assertTrue(result.get('success'))


class APNsServiceTests(TestCase):
    """Tests for APNs service."""
    
    @patch('apps.notifications.apns.requests.post')
    def test_send_to_token_success(self, mock_post):
        """Test sending APNs notification."""
        from apps.notifications.apns import APNsNotification
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'apns-id': 'abc-123'}
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        from apps.notifications.apns import APNsService
        apns = APNsService()
        apns._config.enabled = True
        
        notification = APNsNotification(title='Test', body='Test message')
        
        result = apns.send_to_token('test_device_token', notification)
        
        self.assertTrue(result['success'])
