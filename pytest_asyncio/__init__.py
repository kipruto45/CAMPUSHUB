"""Compatibility wrapper for the installed pytest-asyncio package."""

from importlib.metadata import PackageNotFoundError, version

from .plugin import fixture, is_async_test

try:
    __version__ = version("pytest-asyncio")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ("fixture", "is_async_test")
