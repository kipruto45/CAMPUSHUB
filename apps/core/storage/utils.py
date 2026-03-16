"""
Helpers for building storage-access URLs.
"""

from urllib.parse import quote


def build_storage_download_path(path: str, public: bool) -> str:
    """
    Build a storage API download path for a stored file.
    Returns a relative URL (no scheme/host).
    """
    safe_path = quote(str(path or "").lstrip("/"), safe="/")
    if not safe_path:
        return ""
    prefix = "/api/storage/public/" if public else "/api/storage/private/"
    return f"{prefix}{safe_path}/?download=1"
