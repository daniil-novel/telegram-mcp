from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError
from telethon import functions, types
from telethon.sessions import StringSession

from telegram_readonly_mcp.config import load_settings
from telegram_readonly_mcp.guard import (
    GuardedTelegramClient,
    ReadOnlyViolation,
    assert_read_request,
)
from telegram_readonly_mcp.models import BetweenInput, HistoryInput
from telegram_readonly_mcp.security import SessionStore


@pytest.mark.parametrize(
    "rpc_request",
    [
        functions.messages.SendMessageRequest(types.InputPeerSelf(), "never sent"),
        functions.messages.DeleteMessagesRequest([1]),
        functions.messages.EditMessageRequest(types.InputPeerSelf(), 1, message="never edited"),
        functions.messages.ReadHistoryRequest(types.InputPeerSelf(), 1),
        functions.channels.ReadHistoryRequest(types.InputChannel(1, 2), 1),
        functions.channels.JoinChannelRequest(types.InputChannel(1, 2)),
        functions.channels.LeaveChannelRequest(types.InputChannel(1, 2)),
        functions.account.UpdateStatusRequest(offline=False),
        functions.auth.ExportAuthorizationRequest(2),
        functions.auth.LogOutRequest(),
        functions.updates.GetDifferenceRequest(pts=0, date=None, qts=0),
    ],
)
def test_mutations_blocked_even_wrapped_and_in_auth(rpc_request):
    for authentication in (False, True):
        for wrapped in (
            rpc_request,
            functions.InvokeWithoutUpdatesRequest(rpc_request),
            [functions.help.GetConfigRequest(), rpc_request],
        ):
            with pytest.raises(ReadOnlyViolation):
                assert_read_request(wrapped, authentication=authentication)


def test_auth_only_separate_cli():
    request = functions.auth.SendCodeRequest("+10000000000", 1, "a" * 32, types.CodeSettings())
    with pytest.raises(ReadOnlyViolation):
        assert_read_request(request)
    assert_read_request(request, authentication=True)


def test_read_wrappers_and_unknown_class():
    assert_read_request(functions.InvokeWithoutUpdatesRequest(functions.help.GetConfigRequest()))
    with pytest.raises(ReadOnlyViolation):
        assert_read_request(object())


async def test_guard_both_client_and_direct_sender():
    client = GuardedTelegramClient(StringSession(), 1, "a" * 32)
    request = functions.messages.SendMessageRequest(types.InputPeerSelf(), "never sent")
    with pytest.raises(ReadOnlyViolation):
        await client(request)
    with pytest.raises(ReadOnlyViolation):
        client._sender.send(request)
    me = types.User(id=1, access_hash=2, first_name="Synthetic", bot=False)
    await client._on_login(me)
    assert client._authorized is True
    assert client._no_updates


def test_protected_session_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "private")
    store.save("synthetic-session-not-credentials")
    assert store.load() == "synthetic-session-not-credentials"
    assert store.is_private()
    if os.name == "nt":
        assert b"synthetic-session-not-credentials" not in store.path.read_bytes()
    else:
        assert (store.directory.stat().st_mode & 0o777) == 0o700


def test_session_cannot_live_in_project():
    import telegram_readonly_mcp.security as module

    project = Path(module.__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="outside"):
        SessionStore(project / "should-not-be-created")


def test_empty_acl_denies_everything(tmp_path, monkeypatch):
    for name in ("TELEGRAM_ALLOWED_CHAT_IDS", "TELEGRAM_API_ID", "TELEGRAM_API_HASH"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / "empty.env"
    env.write_text("TELEGRAM_ALLOWED_CHAT_IDS=\n", encoding="utf-8")
    assert load_settings(env).allow_ids == frozenset()


def test_validation_and_secret_redaction(tmp_path):
    settings = load_settings(tmp_path / "missing.env")
    assert "api_hash=SecretStr('')" in repr(settings)
    with pytest.raises(ValueError, match="Fill"):
        settings.require_credentials()
    with pytest.raises(ValidationError):
        HistoryInput(chat_id=1, limit=201)
    with pytest.raises(ValidationError):
        HistoryInput(chat_id=1, send=True)
    with pytest.raises(ValidationError):
        BetweenInput(chat_id=1, start="2026-10-02T00:00:00", end="2026-10-03T00:00:00Z")
