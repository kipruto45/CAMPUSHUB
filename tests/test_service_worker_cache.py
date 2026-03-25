import re
from pathlib import Path


def test_sw_defines_cache_names():
    sw_path = Path("static/pwa/sw.js")
    content = sw_path.read_text()
    # Ensure new versioned caches are declared
    for token in ["campushub-shell", "campushub-static", "campushub-api", "campushub-images"]:
        assert token in content


def test_sw_offline_url_present():
    content = Path("static/pwa/sw.js").read_text()
    assert "OFFLINE_URL" in content
    assert "/offline/" in content
