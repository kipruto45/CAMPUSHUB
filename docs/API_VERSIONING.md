# API Versioning

We now use **URLPathVersioning** for REST endpoints.

- Stable prefix: `/api/v1/…`
- Legacy alias: `/api/…` (marked deprecated; will be removed after migration window)
- Future placeholder: `/api/v2/…` returns `501 Not Yet Implemented`

Headers on every API response:

- `X-API-Version`: resolved version (`v1`, `legacy`, `v2`, etc.)
- `Deprecation`: `"false"` for the current stable version, `"true"` for legacy/unreleased paths.

Migration timeline:

1. Move clients from `/api/...` to `/api/v1/...` immediately.
2. `/api/` legacy will be sunset after v2 endpoints are live.
3. v2 namespace exists as a stub; responses return HTTP 501 until implemented.

Request/response changes:

- No payload changes for v1; only the URL prefix and version headers differ.
- Legacy endpoints still respond but carry `Deprecation: true` to signal migration need.

Testing tips:

- Add `version` to DRF test client kwargs when needed: `client.get("/api/v1/...", HTTP_X_API_VERSION="v1")`.
- Confirm headers: `response["X-API-Version"]`, `response["Deprecation"]`.
