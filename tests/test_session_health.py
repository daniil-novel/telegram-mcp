from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import SecretStr
from telethon import errors, functions
from telethon.crypto import AuthKey
from telethon.sessions import StringSession

from telegram_readonly_mcp import session_health
from telegram_readonly_mcp.config import Settings
from telegram_readonly_mcp.security import SessionStore
from telegram_readonly_mcp.session_health import SessionStatus


@pytest.fixture
def stored_session(tmp_path):
    settings = Settings(api_id=1, api_hash=SecretStr("a" * 32), session_dir=tmp_path / "private")
    store = SessionStore(settings.session_dir)
    session = StringSession()
    session.set_dc(2, "149.154.167.50", 443)
    session.auth_key = AuthKey(b"\x02" * 256)
    store.save(session.save())
    return settings, store


def test_another_process_cannot_open_the_same_session_while_locked(stored_session):
    _, store = stored_session
    script = """
import sys
from pathlib import Path
from telegram_readonly_mcp.security import SessionBusy, SessionStore
try:
    with SessionStore(Path(sys.argv[1])).lock_connection():
        pass
except SessionBusy:
    sys.exit(3)
"""
    args = [sys.executable, "-c", script, str(store.directory)]
    with store.lock_connection():
        assert subprocess.run(args, timeout=10, check=False).returncode == 3
    assert subprocess.run(args, timeout=10, check=False).returncode == 0


async def test_busy_check_and_missing_session_do_not_connect(monkeypatch, stored_session, tmp_path):
    settings, store = stored_session

    def unexpected(*args, **kwargs):
        pytest.fail("Session check started a Telegram client with no available session")

    monkeypatch.setattr(session_health, "GuardedTelegramClient", unexpected)
    with store.lock_connection():
        assert await session_health.check_session(settings) == SessionStatus.BUSY
    missing = settings.model_copy(update={"session_dir": tmp_path / "missing"})
    assert await session_health.check_session(missing) == SessionStatus.LOGIN_REQUIRED


@pytest.mark.parametrize("outcome", ["ok", "revoked", "offline"])
async def test_check_uses_only_state_and_never_replaces_the_session(
    monkeypatch, stored_session, outcome
):
    settings, store = stored_session
    before = store.path.read_bytes()
    calls = []

    class Client:
        def __init__(self, *_args, **kwargs):
            assert not kwargs.get("authentication") and not kwargs.get("write_settings")

        async def connect(self):
            calls.append("connect")

        async def __call__(self, request):
            assert type(request) is functions.updates.GetStateRequest
            calls.append("probe")
            if outcome == "revoked":
                raise errors.SessionRevokedError(request=request)
            if outcome == "offline":
                raise OSError("synthetic network failure")

        async def disconnect(self):
            with pytest.raises(session_health.SessionBusy):
                store.lock_connection()
            calls.append("disconnect")

    monkeypatch.setattr(session_health, "GuardedTelegramClient", Client)
    assert (
        await session_health.check_session(settings)
        == {
            "ok": SessionStatus.AUTHORIZED,
            "revoked": SessionStatus.LOGIN_REQUIRED,
            "offline": SessionStatus.TEMPORARILY_UNAVAILABLE,
        }[outcome]
    )
    assert calls == ["connect", "probe", "disconnect"]
    assert store.path.read_bytes() == before
    with store.lock_connection():
        pass
