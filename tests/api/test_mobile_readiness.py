"""Mobile backend readiness tests (Android + iOS integration)."""

import pytest
from django.core import mail
from django.test import override_settings

from apps.accounts.verification import (
    generate_signed_password_reset_token,
    generate_signed_verification_token,
)


@pytest.mark.django_db
class TestMobileAuthEndpoints:
    def test_mobile_login_invalid_credentials_returns_validation_error(self, api_client):
        response = api_client.post(
            '/api/mobile/login/',
            {'email': 'missing@example.com', 'password': 'wrong-pass'},
            format='json',
        )

        assert response.status_code == 401
        payload = response.data
        assert 'code' in payload or 'detail' in payload

    def test_mobile_login_accepts_registration_number(self, api_client, user):
        response = api_client.post(
            '/api/mobile/login/',
            {'registration_number': user.registration_number, 'password': 'testpass123'},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['access_token']
        assert response.data['data']['refresh_token']

    def test_mobile_register_supports_first_and_last_name(self, api_client):
        response = api_client.post(
            '/api/mobile/register/',
            {
                'email': 'mobile-user@test.com',
                'password': 'ValidPass123!',
                'first_name': 'Mobile',
                'last_name': 'User',
                'registration_number': 'MOB001',
            },
            format='json',
        )

        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['email'] == 'mobile-user@test.com'

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_mobile_register_sends_welcome_verification_email(self, api_client):
        response = api_client.post(
            '/api/mobile/register/',
            {
                'email': 'mobile-email@test.com',
                'password': 'ValidPass123!',
                'first_name': 'Email',
                'last_name': 'Tester',
                'registration_number': 'MOB002',
            },
            format='json',
        )

        assert response.status_code == 200
        assert response.data['success'] is True
        assert len(mail.outbox) == 1
        assert 'Welcome to' in mail.outbox[0].subject

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_mobile_password_reset_request_sends_email(self, api_client, user):
        response = api_client.post(
            '/api/mobile/password/reset/',
            {'email': user.email},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['message'] == 'Password reset email sent.'
        assert len(mail.outbox) == 1
        assert 'password reset' in mail.outbox[0].subject.lower()

    def test_mobile_password_reset_confirm_resets_password(self, api_client, user):
        token = generate_signed_password_reset_token(user)

        response = api_client.post(
            f'/api/mobile/password/reset/confirm/{token}/',
            {
                'new_password': 'NewValidPass123!',
                'new_password_confirm': 'NewValidPass123!',
            },
            format='json',
        )

        assert response.status_code == 200
        assert response.data['success'] is True

        user.refresh_from_db()
        assert user.check_password('NewValidPass123!') is True

    def test_mobile_verify_email_marks_user_verified(self, api_client, user):
        token = generate_signed_verification_token(user)

        response = api_client.get(f'/api/mobile/verify-email/{token}/')

        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['data']['is_verified'] is True

        user.refresh_from_db()
        assert user.is_verified is True

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_mobile_resend_verification_email_sends_email(self, api_client, user):
        user.is_verified = False
        user.save(update_fields=['is_verified'])

        response = api_client.post(
            '/api/mobile/verify-email/resend/',
            {'email': user.email},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['success'] is True
        assert len(mail.outbox) == 1
        assert 'verify' in mail.outbox[0].subject.lower()


@pytest.mark.django_db
class TestMobileApiAndDocs:
    def test_mobile_info_returns_available_websocket_routes(self, api_client):
        response = api_client.get('/api/mobile/info/')

        assert response.status_code == 200
        payload = response.json()
        websocket = payload['websocket']
        assert websocket['url'].endswith('/ws/notifications/')
        assert websocket['admin_notifications'].endswith('/ws/admin/notifications/')
        assert websocket['activity'].endswith('/ws/activity/')

    def test_mobile_info_exposes_mobile_feature_routes(self, api_client):
        response = api_client.get('/api/mobile/info/')

        assert response.status_code == 200
        payload = response.json()
        auth = payload['endpoints']['auth']
        assert auth['forgot_password'] == '/api/mobile/password/reset/'
        assert auth['reset_password_confirm'] == '/api/mobile/password/reset/confirm/<str:token>/'
        assert auth['verify_email'] == '/api/mobile/verify-email/<str:token>/'
        assert auth['resend_verification'] == '/api/mobile/verify-email/resend/'
        gamification = payload['endpoints']['gamification']
        assert gamification['stats'] == '/api/gamification/stats/'
        assert gamification['leaderboard'] == '/api/gamification/leaderboard/'
        assert gamification['check_badges'] == '/api/gamification/check-badges/'
        social = payload['endpoints']['social']
        assert social['study_groups'] == '/api/social/study-groups/'
        assert social['study_group_detail'] == '/api/social/study-groups/<uuid:group_id>/'
        resources = payload['endpoints']['resources']
        assert resources['upload'] == '/api/mobile/resources/upload/'
        assert resources['bookmark_toggle'] == '/api/mobile/resources/<uuid:id>/bookmark/'
        assert resources['favorite_toggle'] == '/api/mobile/resources/<uuid:id>/favorite/'
        assert resources['download'] == '/api/mobile/resources/<uuid:id>/download/'
        assert resources['save_to_library'] == '/api/mobile/resources/<uuid:id>/save-to-library/'

        assert payload['endpoints']['bookmarks']['list'] == '/api/mobile/bookmarks/'
        assert payload['endpoints']['favorites']['list'] == '/api/mobile/favorites/'
        assert payload['endpoints']['library']['summary'] == '/api/mobile/library/summary/'

        push_features = payload['features']['push_notifications']
        assert {'enabled', 'configured'} <= set(push_features['fcm'].keys())
        assert {'enabled', 'configured'} <= set(push_features['apns'].keys())

    def test_schema_endpoint_loads(self, api_client):
        response = api_client.get('/api/schema/')
        assert response.status_code == 200
        assert 'openapi' in response.content.decode('utf-8')


@pytest.mark.django_db
class TestDeepLinkAndAssociationEndpoints:
    def test_deeplink_build_and_parse_roundtrip(self, api_client):
        build_response = api_client.post(
            '/api/mobile/deeplink/build/',
            {'type': 'auth', 'action': 'login', 'params': {}},
            format='json',
        )

        assert build_response.status_code == 200
        deep_link_url = build_response.json()['data']['url']
        assert deep_link_url.endswith('auth/login')

        parse_response = api_client.post(
            '/api/mobile/deeplink/parse/',
            {'url': deep_link_url},
            format='json',
        )

        assert parse_response.status_code == 200
        parse_data = parse_response.json()['data']
        assert parse_data['type'] == 'auth'
        assert parse_data['action'] == 'login'
        assert parse_data['route']['screen'] == 'Login'

    @override_settings(
        ANDROID_APP_PACKAGE='com.campushub.mobile',
        ANDROID_SHA256_CERT_FINGERPRINTS=['AA:BB:CC'],
        IOS_TEAM_ID='TEAM123',
        IOS_BUNDLE_ID='com.campushub.mobile',
    )
    def test_android_and_ios_association_endpoints(self, api_client):
        android_response = api_client.get('/.well-known/assetlinks.json')
        assert android_response.status_code == 200
        android_payload = android_response.json()
        assert android_payload[0]['target']['package_name'] == 'com.campushub.mobile'
        assert android_payload[0]['target']['sha256_cert_fingerprints'] == ['AA:BB:CC']

        ios_response = api_client.get('/.well-known/apple-app-site-association')
        assert ios_response.status_code == 200
        ios_payload = ios_response.json()
        assert ios_payload['applinks']['details'][0]['appID'] == 'TEAM123.com.campushub.mobile'
