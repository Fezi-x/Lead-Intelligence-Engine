import pytest
from pathlib import Path


@pytest.mark.security
def test_gitignore_contains_sensitive_entries():
    content = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env" in content
    assert "venv/" in content
    assert "logs/" in content
    assert "facebook_auth.json" in content
