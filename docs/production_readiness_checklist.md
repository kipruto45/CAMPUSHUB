# CampusHub Production Readiness Checklist

This checklist reflects the backend `production_readiness_check` command and the
current repo state as of 2026-03-27.

## 1. Environment

Set the backend to production mode:

```env
ENVIRONMENT=production
DEBUG=False
```

## 2. Secret Key

Set a high-entropy Django secret key:

```env
SECRET_KEY=<50+ character random secret>
```

Do not use `django-insecure-*` keys in production.

## 3. Hosts and CSRF

For the current planned domain, configure:

```env
ALLOWED_HOSTS=my-cham-a.app,api.my-cham-a.app
CSRF_TRUSTED_ORIGINS=https://my-cham-a.app,https://api.my-cham-a.app
```

## 4. HTTPS Security

Configure:

```env
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
```

Production settings already force:

- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")`

Make sure your reverse proxy actually sends `X-Forwarded-Proto: https`.

The bundled Docker production stack assumes TLS terminates upstream. Its
default Nginx config is HTTP-only and forwards the original
`X-Forwarded-Proto` header to Django. If you expose the stack directly without
an HTTPS terminator, you must either:

- provide your own cert-enabled Nginx config, or
- set `SECURE_SSL_REDIRECT=False` for that environment

The second option is acceptable for a private staging stack, not for the final
public production deployment.

## 5. Database

Use PostgreSQL in production:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
```

SQLite is acceptable for local development only.

## 6. Cache / Celery / Channels

Production requires Redis to be reachable:

```env
REDIS_URL=redis://<redis-host>:6379/0
CELERY_BROKER_URL=redis://<redis-host>:6379/0
CELERY_RESULT_BACKEND=redis://<redis-host>:6379/0
CHANNEL_LAYER_BACKEND=redis
```

## 7. Email

Use a real SMTP backend and valid sender:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-app-password>
DEFAULT_FROM_EMAIL=<verified-sender>
```

Verify:

- welcome emails
- password reset emails
- verification emails
- trial expired emails

Validate SMTP wiring:

```bash
python manage.py email_delivery_check --to you@example.com
```

## 8. SMS / Trial Expiry Alerts

Trial-expiry notifications now use the shared SMS pipeline. Configure Africa's
Talking or a generic SMS provider:

```env
SMS_PROVIDER=africastalking
AFRICAS_TALKING_USERNAME=<username>
AFRICAS_TALKING_API_KEY=<api-key>
AFRICAS_TALKING_SHORT_CODE=
```

Notes:

- `AFRICAS_TALKING_SHORT_CODE` is optional and can stay blank
- trial-expired SMS alerts only send when the user has a phone number
- expired trials are processed by Celery Beat via `process-expired-trials`

Validate SMS wiring without sending a live message:

```bash
python manage.py sms_delivery_check
```

Optionally send a real SMS test:

```bash
python manage.py sms_delivery_check --send --to +254700000001
```

## 9. OAuth

Update OAuth redirect URIs to the production API domain:

```env
GOOGLE_REDIRECT_URI=https://api.my-cham-a.app/api/auth/google/callback/
MICROSOFT_REDIRECT_URI=https://api.my-cham-a.app/api/auth/microsoft/callback/
```

Also update the same redirect URLs in:

- Google Cloud Console
- Microsoft Entra / Azure App Registration

## 10. Mobile App

For release builds, point the app to production:

```env
EXPO_PUBLIC_API_URL=https://api.my-cham-a.app/api
```

Also verify:

- app links / universal links
- OAuth callback flow
- push notification registration

## 11. Trial / Subscription Enforcement

Confirm the plan system is operating with the intended restrictions:

- free trial lasts 7 days
- expired trials downgrade the user back to free access
- students on free cannot access premium-only AI, analytics, certificates, or cloud integrations
- admins require an entitled plan or active admin trial to reach admin surfaces
- upgrade prompts disappear after a paid subscription becomes active

Operational checks:

```bash
python manage.py production_readiness_check
python manage.py sms_delivery_check
python manage.py email_delivery_check --to you@example.com
```

## 12. Secrets Hygiene

Do not keep live secrets in tracked files.

Current repo policy now ignores:

- `.env`
- `mobile/.env`
- `mobile/android/local.properties`
- `docs/login_credentials.txt`

If live secrets were previously shared or committed, rotate them before deployment.

## 13. Final Commands

Run before release:

```bash
python manage.py migrate
python manage.py check
python manage.py production_readiness_check
python manage.py sms_delivery_check
python manage.py email_delivery_check --to you@example.com
```

For a local dry run where SQLite is still in use:

```bash
python manage.py production_readiness_check --allow-sqlite
```
