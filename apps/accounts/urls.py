"""
URL configuration for accounts app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView

from .oauth_views import (GoogleOAuthCallbackView, GoogleOAuthLinkView,
                          GoogleOAuthNativeView, GoogleOAuthUrlView,
                          GoogleOAuthView, MicrosoftOAuthCallbackView,
                          MicrosoftOAuthLinkView, MicrosoftOAuthNativeView,
                          MicrosoftOAuthUrlView, MicrosoftOAuthView)
from .views import (DeleteAccountView, EmailVerificationView, JWTTokenRefreshView,
                    LoginView, LogoutView, PasswordChangeView,
                    PasswordResetConfirmTokenOnlyView, PasswordResetConfirmView,
                    PasswordResetRequestView, ProfileCompletionView,
                    ProfileLinkedAccountUnlinkView, ProfileLinkedAccountsView,
                    ProfilePhotoDeleteView, ProfilePhotoUploadView,
                    ProfilePreferencesView, ProfileView, RegisterView,
                    ResendVerificationEmailView, UserActivityViewSet,
                    UserSearchView, UserSessionRevokeView, UserSessionsView,
                    UserViewSet, MagicLinkRequestView, MagicLinkConsumeView,
                    PasskeyRegistrationStartView, PasskeyRegistrationCompleteView,
                    PasskeyAuthenticationStartView, PasskeyAuthenticationCompleteView,
                    UserPasskeysView, PasskeyUpdateView)

app_name = "accounts"

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"activities", UserActivityViewSet, basename="user-activity")

urlpatterns = [
    # Authentication endpoints
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("magic-link/", MagicLinkRequestView.as_view(), name="magic-link-request"),
    path("magic-link/consume/", MagicLinkConsumeView.as_view(), name="magic-link-consume"),
    # Passkey (WebAuthn/FIDO2) endpoints
    path("passkeys/register/start/", PasskeyRegistrationStartView.as_view(), name="passkey-register-start"),
    path("passkeys/register/complete/", PasskeyRegistrationCompleteView.as_view(), name="passkey-register-complete"),
    path("passkeys/auth/start/", PasskeyAuthenticationStartView.as_view(), name="passkey-auth-start"),
    path("passkeys/auth/complete/", PasskeyAuthenticationCompleteView.as_view(), name="passkey-auth-complete"),
    path("passkeys/", UserPasskeysView.as_view(), name="user-passkeys"),
    path("passkeys/update/", PasskeyUpdateView.as_view(), name="passkey-update"),
    path("account/delete/", DeleteAccountView.as_view(), name="account-delete"),
    path("sessions/", UserSessionsView.as_view(), name="user-sessions"),
    path("sessions/revoke/", UserSessionRevokeView.as_view(), name="user-sessions-revoke"),
    path("2fa/", include("apps.two_factor.urls")),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", JWTTokenRefreshView.as_view(), name="token_refresh"),
    # OAuth2 endpoints
    path("google/", GoogleOAuthView.as_view(), name="google_oauth"),
    path("google/link/", GoogleOAuthLinkView.as_view(), name="google_oauth_link"),
    path("google/native/", GoogleOAuthNativeView.as_view(), name="google_oauth_native"),
    path("google/url/", GoogleOAuthUrlView.as_view(), name="google_oauth_url"),
    path("google/callback/", GoogleOAuthCallbackView.as_view(), name="google_oauth_callback"),
    path("microsoft/", MicrosoftOAuthView.as_view(), name="microsoft_oauth"),
    path("microsoft/link/", MicrosoftOAuthLinkView.as_view(), name="microsoft_oauth_link"),
    path(
        "microsoft/native/",
        MicrosoftOAuthNativeView.as_view(),
        name="microsoft_oauth_native",
    ),
    path("microsoft/url/", MicrosoftOAuthUrlView.as_view(), name="microsoft_oauth_url"),
    path(
        "microsoft/callback/",
        MicrosoftOAuthCallbackView.as_view(),
        name="microsoft_oauth_callback",
    ),
    # Password management endpoints
    path("password/change/", PasswordChangeView.as_view(), name="password_change"),
    path(
        "password/reset/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password/reset/",
        PasswordResetRequestView.as_view(),
        name="password_reset",
    ),
    path(
        "password/reset/confirm/<str:token>/",
        PasswordResetConfirmTokenOnlyView.as_view(),
        name="password_reset_confirm_token",
    ),
    path(
        "password/reset/confirm/<str:uidb64>/<str:token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "verify-email/resend/",
        ResendVerificationEmailView.as_view(),
        name="resend_verify_email",
    ),
    path(
        "verify-email/<str:token>/",
        EmailVerificationView.as_view(),
        name="verify_email",
    ),
    # Profile endpoints
    path("profile/", ProfileView.as_view(), name="profile"),
    path("me/", ProfileView.as_view(), name="current-user"),
    path(
        "profile/photo/", ProfilePhotoUploadView.as_view(), name="profile_photo_upload"
    ),
    path(
        "profile/photo/delete/",
        ProfilePhotoDeleteView.as_view(),
        name="profile_photo_delete",
    ),
    path(
        "profile/preferences/",
        ProfilePreferencesView.as_view(),
        name="profile_preferences",
    ),
    path(
        "profile/completion/",
        ProfileCompletionView.as_view(),
        name="profile_completion",
    ),
    path(
        "profile/linked-accounts/",
        ProfileLinkedAccountsView.as_view(),
        name="profile_linked_accounts",
    ),
    path(
        "profile/linked-accounts/unlink/",
        ProfileLinkedAccountUnlinkView.as_view(),
        name="profile_linked_accounts_unlink",
    ),
    # User search endpoint
    path(
        "users/search/",
        UserSearchView.as_view(),
        name="user_search",
    ),
    # Router URLs
    path("", include(router.urls)),
]
