"""Schema preprocessing hooks for drf-spectacular."""

from __future__ import annotations


def _normalize_api_path(path: str) -> str:
    if path.startswith("/api/v1/"):
        return path[len("/api/v1") :]
    if path.startswith("/api/"):
        return path[len("/api") :]
    return path


def preprocess_canonical_api_endpoints(endpoints):
    """
    Prefer `/api/v1/...` endpoints in the schema when an unversioned `/api/...`
    compatibility alias exposes the same normalized path and method.
    """

    versioned_signatures = {
        (_normalize_api_path(path), method)
        for path, _path_regex, method, _callback in endpoints
        if path.startswith("/api/v1/")
    }

    filtered = []
    for endpoint in endpoints:
        path, _path_regex, method, _callback = endpoint
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            signature = (_normalize_api_path(path), method)
            if signature in versioned_signatures:
                continue
        filtered.append(endpoint)

    return filtered
