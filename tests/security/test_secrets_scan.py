import re
from pathlib import Path
import pytest


EXCLUDE_DIRS = {
    ".git",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "logs",
}

EXCLUDE_FILES = {
    ".env",
    "facebook_auth.json",
    "README.md",
}

PATTERNS = [
    re.compile(r"GROQ_API_KEY\s*=\s*\S+"),
    re.compile(r"CODA_API_TOKEN\s*=\s*\S+"),
    re.compile(r"TELEGRAM_BOT_TOKEN\s*=\s*\S+"),
    re.compile(r"FACEBOOK_APP_SECRET\s*=\s*\S+"),
    re.compile(r"FACEBOOK_ACCESS_TOKEN\s*=\s*\S+"),
]


@pytest.mark.security
def test_no_obvious_secrets_in_repo():
    root = Path.cwd()
    hits = []

    for path in root.rglob("*"):
        if path.is_dir():
            if path.name in EXCLUDE_DIRS:
                continue

        # Skip excluded dirs by checking any parent segment
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue

        if path.is_file():
            if path.name in EXCLUDE_FILES:
                continue
            if path.stat().st_size > 512 * 1024:
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for pattern in PATTERNS:
                if pattern.search(content):
                    hits.append(str(path))
                    break

    assert not hits, f"Potential secrets found in files: {', '.join(hits)}"
