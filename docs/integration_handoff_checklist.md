# CampusHub Integration Handoff Checklist

This is the single checklist of values and decisions still needed to finish the
remaining integrations cleanly.

Current state as of 2026-03-27:

- OpenAI is wired.
- Stripe is wired.
- PayPal is wired.
- Calendar sync is wired for Google and Outlook.
- Apple and Google in-app purchase validation is wired.
- Deployment wiring for workers/beat and Cloudinary is in place.

## 1. Core Deployment Values

Fill these first for any real deployment:

```env
SECRET_KEY=
JWT_SECRET_KEY=
ENVIRONMENT=production
DEBUG=False
ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=
DATABASE_URL=
FRONTEND_URL=
BASE_URL=
RESOURCE_SHARE_BASE_URL=
MOBILE_DEEPLINK_HOST=
```

Needed decisions:

- Final backend API domain
- Final frontend/web domain
- Final mobile deep-link host
- PostgreSQL vs another production database

## 2. Async Infrastructure

Needed for Celery jobs, sync jobs, and production-grade background work:

```env
REDIS_URL=
CACHE_BACKEND=redis
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=
CHANNEL_LAYER_BACKEND=redis
```

Needed decision:

- Do you want Redis-backed workers in production

## 3. Email Integration

Needed for verification, password reset, account notices, and payment emails:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=
EMAIL_PORT=
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=
```

## 4. Storage Integration

Choose one primary media storage path.

AWS S3 option:

```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=
```

Cloudinary option:

```env
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CLOUDINARY_ENABLED=True
```

Needed decision:

- S3 or Cloudinary for uploaded media

## 5. Push Notifications

Android via Firebase Cloud Messaging:

```env
FCM_ENABLED=True
FCM_SERVER_KEY=
FCM_PROJECT_ID=
FCM_SERVICE_ACCOUNT_PATH=
```

iOS via Apple Push Notification service:

```env
APNS_ENABLED=True
APNS_KEY_ID=
APNS_TEAM_ID=
APNS_BUNDLE_ID=
APNS_AUTH_KEY_PATH=
APNS_AUTH_KEY=
APNS_ENVIRONMENT=production
IOS_TEAM_ID=
IOS_BUNDLE_ID=
```

Needed decision:

- Whether to keep iOS push disabled for now or fully enable APNS

## 6. Google OAuth

Needed for login and Google-backed integrations:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=
EXPO_PUBLIC_GOOGLE_IOS_URL_SCHEME=
```

## 7. Microsoft OAuth

Needed for login, Outlook calendar, OneDrive, and Teams:

```env
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_REDIRECT_URI=
MICROSOFT_TENANT_ID=common
EXPO_PUBLIC_MICROSOFT_CLIENT_ID=
EXPO_PUBLIC_MICROSOFT_TENANT_ID=common
EXPO_PUBLIC_MICROSOFT_REDIRECT_URI=
EXPO_PUBLIC_MICROSOFT_ANDROID_SIGNATURE_HASH=
```

## 8. Google Classroom and Microsoft Teams

Needed if you want those integrations turned on:

```env
GOOGLE_CLASSROOM_REDIRECT_URI=
MICROSOFT_OAUTH_CLIENT_ID=
MICROSOFT_OAUTH_CLIENT_SECRET=
MICROSOFT_TEAMS_REDIRECT_URI=
```

Note:

- Teams can reuse the main Microsoft app credentials if you prefer

## 9. OpenAI

Already supplied, but listed here for completeness:

```env
OPENAI_API_KEY=
AI_CHAT_MODEL=gpt-4o-mini
AI_CHAT_TEMPERATURE=0.4
AI_CHAT_MAX_TOKENS=500
AI_CHAT_TIMEOUT_SECONDS=25
SUMMARIZATION_MODEL=gpt-4o-mini
```

## 10. Stripe

Already supplied:

```env
STRIPE_PUBLISHABLE_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
```

Still needed for real recurring plan checkout:

```env
STRIPE_BASIC_MONTHLY_PRICE_ID=
STRIPE_BASIC_YEARLY_PRICE_ID=
STRIPE_BASIC_PRODUCT_ID=
STRIPE_PREMIUM_MONTHLY_PRICE_ID=
STRIPE_PREMIUM_YEARLY_PRICE_ID=
STRIPE_PREMIUM_PRODUCT_ID=
STRIPE_ENTERPRISE_MONTHLY_PRICE_ID=
STRIPE_ENTERPRISE_YEARLY_PRICE_ID=
STRIPE_ENTERPRISE_PRODUCT_ID=
```

## 11. PayPal

Already supplied:

```env
PAYPAL_MODE=sandbox
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=
PAYPAL_TIMEOUT_SECONDS=30
```

Still needed operationally:

- PayPal webhook configured in the PayPal dashboard
- Set `PAYPAL_WEBHOOK_ID` from the PayPal webhook configuration
- Final production callback/base URLs

## 12. App Store & Google Play

Apple App Store verification:

```env
APPLE_IAP_SHARED_SECRET=
APPLE_IAP_USE_SANDBOX=False
APPLE_IAP_TIMEOUT_SECONDS=30
```

Google Play verification:

```env
GOOGLE_PLAY_PACKAGE_NAME=
# Provide one of the following:
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64=
GOOGLE_PLAY_SERVICE_ACCOUNT_PATH=
GOOGLE_PLAY_TIMEOUT_SECONDS=30
GOOGLE_PLAY_STRICT_VALIDATION=False
```

## 13. Mobile Money

Needed only if you want M-Pesa or other mobile money support:

```env
MOBILE_MONEY_PROVIDER=
MOBILE_MONEY_SHORT_CODE=
MOBILE_MONEY_CONSUMER_KEY=
MOBILE_MONEY_CONSUMER_SECRET=
MOBILE_MONEY_PASSKEY=
MOBILE_MONEY_ENV=sandbox
MOBILE_MONEY_TRANSACTION_TYPE=CustomerPayBillOnline
MOBILE_MONEY_CALLBACK_URL=
MOBILE_MONEY_API_BASE_URL=
MOBILE_MONEY_TIMEOUT_SECONDS=30
```

## 14. SMS

Needed if payment alerts and trial-expiry SMS should be live:

Africa's Talking option:

```env
SMS_PROVIDER=africastalking
AFRICAS_TALKING_USERNAME=
AFRICAS_TALKING_API_KEY=
AFRICAS_TALKING_SHORT_CODE=
```

Generic SMS option:

```env
SMS_API_URL=
SMS_API_KEY=
SMS_SENDER_ID=CampusHub
```

## 15. Observability and Security

Sentry:

```env
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_SESSIONS_SAMPLE_RATE=0.1
SENTRY_ERROR_SAMPLE_RATE=1.0
SENTRY_SEND_DEFAULT_PII=False
```

Encryption:

```env
ENCRYPTION_ENABLED=True
ENCRYPTION_MASTER_KEY=
ENCRYPTION_KEY_SALT=
ENCRYPTION_ALLOW_FALLBACK=False
ENCRYPTION_KEY_VERSION=1
ENCRYPTION_PREVIOUS_KEYS=
```

## 16. Mobile Release Metadata

Needed for production mobile auth and app links:

```env
EXPO_PUBLIC_API_URL=
ANDROID_APP_PACKAGE=
ANDROID_SHA256_CERT_FINGERPRINTS=
IOS_TEAM_ID=
IOS_BUNDLE_ID=
```

## 17. Still Missing In Code

These are not just missing values. They still need implementation work:

- Mobile store setup and Expo/EAS config for `react-native-iap` (native IAP wiring is in the app, but store-side setup is still required).

## 18. Fastest Way To Send Me What Is Missing

You can reply with only the sections you want to finish next.

Example:

```env
# Core
ALLOWED_HOSTS=api.example.com
CSRF_TRUSTED_ORIGINS=https://api.example.com,https://example.com
DATABASE_URL=postgresql://...

# Email
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...

# SMS
AFRICAS_TALKING_USERNAME=...
AFRICAS_TALKING_API_KEY=...
```

Then I can wire the remaining config and implementation in one pass.
