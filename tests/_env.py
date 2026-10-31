"""Offline test environment for blog_automation.

- Dummy env vars (always overridden: tests never see real secrets).
- Stubs for python-dotenv / openai when they are not installed, and for
  fcntl on non-POSIX dev machines (the agent itself targets Linux).
- Network guard: any real DNS lookup or socket connection raises.

Import it before blog_automation: ``from _env import ba``.
"""

import os
import socket
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TELEGRAM_TOKEN = "123456789:AAH-test_token-value"
OPENAI_KEY = "sk-test-0123456789abcdef"

os.environ.update(
    {
        "NOTION_TOKEN": "secret_testtesttesttesttesttest1234",
        "NOTION_ARTICULOS_DB_ID": "db-test",
        "OPENAI_API_KEY": OPENAI_KEY,
        "OPENAI_MODEL": "gpt-test",
        "SERPER_API_KEY": "serper-test-key-0123456789",
        "TELEGRAM_BOT_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": "42",
        "WP_CREDENTIALS_FILE": str(ROOT / "tests" / "missing-wp-credentials.json"),
        "DRY_RUN": "false",
        "AUTHOR_MAP_JSON": '{"client.example": "Client Author"}',
    }
)


def _stub(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module


try:
    import dotenv  # noqa: F401
except ImportError:
    _stub("dotenv", load_dotenv=lambda *a, **k: False)

try:
    import openai  # noqa: F401
except ImportError:

    class _OpenAI:
        def __init__(self, *args, **kwargs):
            def _blocked(*a, **k):
                raise RuntimeError("OpenAI is not reachable from tests")

            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=_blocked))

    _stub("openai", OpenAI=_OpenAI)

try:
    import fcntl  # noqa: F401

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

    def _flock(*args, **kwargs):
        raise OSError("fcntl.flock is not available on this platform")

    _stub("fcntl", LOCK_EX=2, LOCK_NB=4, LOCK_UN=8, flock=_flock)


def _no_network(*args, **kwargs):
    raise RuntimeError("network access attempted during tests")


socket.getaddrinfo = _no_network
socket.socket.connect = _no_network
socket.socket.connect_ex = _no_network

import blog_automation as ba  # noqa: E402

__all__ = ["ba", "HAS_FCNTL", "OPENAI_KEY", "TELEGRAM_TOKEN"]
