"""Load the installed pytest-asyncio plugin with pytest compatibility patches."""

from __future__ import annotations

import importlib.util
import sysconfig
from pathlib import Path

import pytest

if not hasattr(pytest, "FixtureDef"):
    from _pytest.fixtures import FixtureDef

    pytest.FixtureDef = FixtureDef

_VENDORED_PLUGIN_PATH = (
    Path(sysconfig.get_paths()["purelib"]) / "pytest_asyncio" / "plugin.py"
)

_spec = importlib.util.spec_from_file_location(
    "_campushub_vendored_pytest_asyncio_plugin",
    _VENDORED_PLUGIN_PATH,
)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load vendored pytest_asyncio plugin from {_VENDORED_PLUGIN_PATH}")

_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

for _name in dir(_module):
    if _name.startswith("__") and _name not in {"__all__", "__doc__"}:
        continue
    globals()[_name] = getattr(_module, _name)

__all__ = getattr(_module, "__all__", ())
