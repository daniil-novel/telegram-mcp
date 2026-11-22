from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from telethon import errors, functions, types
from telethon.network.mtprotosender import MTProtoSender
from telethon.sessions import StringSession

from telegram_readonly_mcp import cli, qr_login
from telegram_readonly_mcp.guard import (
    GuardedTelegramClient,
    ReadOnlyViolation,
    assert_read_request,
)


def test_qr_requests_are_allowed_only_in_interactive_auth():
    requests = (
        functions.auth.ExportLoginTokenRequest(1, "a" * 32, []),
        functions.auth.ImportLoginTokenRequest(b"synthetic"),
    )
    for request in requests:
        with pytest.raises(ReadOnlyViolation):
            assert_read_request(request)
        assert_read_request(request, authentication=True)
    with pytest.raises(ReadOnlyViolation):
        assert_read_request(
            functions.auth.AcceptLoginTokenRequest(b"synthetic"), authentication=True
        )


@pytest.mark.parametrize("needs_2fa", [False, True])
async def test_qr_scan_switches_off_updates_before_confirm_and_dc_import(monkeypatch, needs_2fa):
    rpc_types = []
    calls = []
    user = types.User(id=101, access_hash=11, first_name="Synthetic", bot=False)

    def fake_send(_sender, request, ordered=False):
        wrapped = isinstance(request, functions.InvokeWithoutUpdatesRequest)
        rpc = request.query if wrapped else request
        rpc_types.append((type(rpc), wrapped))
        reply = asyncio.get_running_loop().create_future()
        if len(rpc_types) == 1:
            reply.set_result(
                types.auth.LoginToken(datetime.now(UTC) + timedelta(seconds=20), b"qr")
            )
        elif len(rpc_types) == 2:
            reply.set_result(types.auth.LoginTokenMigrateTo(3, b"fake"))
        elif needs_2fa:
            reply.set_exception(errors.SessionPasswordNeededError(rpc))
        else:
            reply.set_result(types.auth.LoginTokenSuccess(types.auth.Authorization(user=user)))
        return reply

    monkeypatch.setattr(MTProtoSender, "send", fake_send)
    client = GuardedTelegramClient(StringSession(), 1, "a" * 32, authentication=True)

    async def switch_dc(dc_id):
        calls.append(dc_id)

    monkeypatch.setattr(client, "_switch_dc", switch_dc)

    class Window:
        def __init__(self, lang):
            pass

        def show(self, token):
            assert token == b"qr"

        async def wait_for_scan(self, event, expires):
            client._updates_queue.put_nowait(
                types.UpdateShort(types.UpdateConfig(), datetime.now(UTC))
            )
            await asyncio.sleep(0)
            assert not event.is_set()
            client._updates_queue.put_nowait(
                types.UpdateShort(types.UpdateLoginToken(), datetime.now(UTC))
            )
            await asyncio.wait_for(event.wait(), 1)
            return True

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(qr_login, "QrWindow", Window)
    updates = asyncio.create_task(client._update_loop())
    try:
        if needs_2fa:
            with pytest.raises(errors.SessionPasswordNeededError):
                await qr_login.authorize_qr(client, "ru")
        else:
            await qr_login.authorize_qr(client, "ru")
            assert await client.is_user_authorized()
    finally:
        updates.cancel()
        await asyncio.gather(updates, return_exceptions=True)
    assert calls == [3, "closed"]
    assert rpc_types == [
        (functions.auth.ExportLoginTokenRequest, False),
        (functions.auth.ExportLoginTokenRequest, True),
        (functions.auth.ImportLoginTokenRequest, True),
    ]
    assert client._no_updates and client._qr_scan is None


def test_code_delivery_message_distinguishes_telegram_sms_and_email():
    assert "служебный чат" in cli._code_delivery(types.auth.SentCodeTypeApp(5), "ru")
    assert "SMS" in cli._code_delivery(types.auth.SentCodeTypeSms(5), "ru")
    assert "почту" in cli._code_delivery(types.auth.SentCodeTypeEmailCode("masked", 5), "ru")
