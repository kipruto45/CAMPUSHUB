# Mobile Backend Integration Checklist

Use this checklist before connecting Android/iOS clients to production.

## 1. API Contract
- Freeze and export contract: `make mobile-contract PYTHON=venv/bin/python`.
- Mobile app env is set:
  - `EXPO_PUBLIC_API_URL=http://<backend-host>:8000/api`
- Confirm mobile endpoints in Swagger/ReDoc:
  - `/api/mobile/register/`
  - `/api/mobile/login/`
  - `/api/mobile/refresh/`
  - `/api/mobile/resources/`
  - `/api/mobile/resources/{id}/`
  - `/api/mobile/resources/upload/`
  - `/api/mobile/resources/{id}/bookmark/`
  - `/api/mobile/resources/{id}/favorite/`
  - `/api/mobile/resources/{id}/download/`
  - `/api/mobile/resources/{id}/save-to-library/`
  - `/api/mobile/bookmarks/`
  - `/api/mobile/favorites/`
  - `/api/mobile/library/summary/`
  - `/api/mobile/library/files/`
  - `/api/mobile/library/folders/`
  - `/api/mobile/dashboard/`
  - `/api/mobile/notifications/`
  - `/api/mobile/device/register/`
  - `/api/mobile/sync/`
- Validate response shape:
  - `success`
  - `data` (on success)
  - `error` (on failure)
  - `meta.api_version`

## 2. Auth + Session
- JWT login works with email and registration number.
- Refresh rotates tokens and invalidates old refresh token.
- Logout deactivates supplied device token.
- Mobile clients send `Authorization: Bearer <access_token>`.

## 3. Reliability (Retries)
- For retry-prone write endpoints, send `X-Idempotency-Key`.
- Backend supports replay-safe behavior for:
  - `POST /api/mobile/resources/{id}/bookmark/`
  - `POST /api/mobile/resources/{id}/favorite/`
  - `POST /api/mobile/resources/{id}/download/`
  - `POST /api/mobile/resources/{id}/save-to-library/`
  - `POST /api/mobile/device/register/`
  - `POST /api/mobile/notifications/{id}/read/`
  - `POST /api/mobile/topic/subscribe/`
  - `POST /api/mobile/topic/unsubscribe/`
- On replay, backend returns `X-Idempotent-Replay: true`.

## 4. Pagination, Filtering, Sorting
- Resource list query params:
  - `page`, `limit`
  - `type`, `course`, `unit`, `search`
  - `sort`: `newest|oldest|popular|downloads|rating|title`
- Verify pagination metadata:
  - `page`, `limit`, `total`, `pages`

## 5. Push Notifications
- Register device token after login.
- Confirm push providers are intentionally configured:
  - Keep `FCM_ENABLED=False` / `APNS_ENABLED=False` until credentials are ready.
  - Enable a provider only when keys are set and validated.
- Test topic subscribe/unsubscribe from mobile.
- Validate unread count and mark-read flow.

## 6. Observability
- Every response includes `X-Request-ID`.
- Mobile API responses include `X-API-Version`.
- Run infra checks: `make mobile-infra-check PYTHON=venv/bin/python`.
- Health endpoints:
  - `/health/`
  - `/health/ready/`
- Sentry DSN and release configured for production.

## 7. Security and Production
- `ENVIRONMENT=production`
- `DEBUG=False`
- `SECRET_KEY` is strong (50+ chars, high entropy)
- `ALLOWED_HOSTS` configured
- `CSRF_TRUSTED_ORIGINS` configured
- HTTPS enabled and proxied correctly
- PostgreSQL + Redis reachable from app runtime
- `CHANNEL_LAYER_BACKEND=redis` in production

## 8. CI/CD and Validation
- Run `make mobile-verify PYTHON=venv/bin/python`.
- Run `make prod-readiness PYTHON=venv/bin/python` with production env values.
- Run full tests: `venv/bin/pytest -q`.
- Run deploy checks: `venv/bin/python manage.py check --deploy` with production env vars.

## 9. Staging Smoke Test
- Deploy latest backend to staging.
- Run migrations.
- Login from Android and iOS test builds.
- Verify key flows:
  - auth
  - dashboard
  - resource list/detail
  - notifications
  - offline sync
