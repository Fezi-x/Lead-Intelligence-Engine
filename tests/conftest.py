import sys
import types
from pathlib import Path

# Ensure project root is on sys.path for local module imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _ensure_dummy_groq_module():
    try:
        import groq  # noqa: F401
        return
    except Exception:
        pass

    class _PlaceholderGroq:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "Groq SDK is not installed. Tests should monkeypatch evaluator.Groq with a stub."
            )

    dummy = types.SimpleNamespace(Groq=_PlaceholderGroq)
    sys.modules.setdefault("groq", dummy)


_ensure_dummy_groq_module()
