"""Opt-in writes tested with synthetic models, ASGI, and Telethon RPC responses only."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError
from telethon import errors, functions, types
from telethon.network.mtprotosender import MTProtoSender
from telethon.sessions import StringSession

from telegram_readonly_mcp.backend import DemoBackend, TelegramBackend
from telegram_readonly_mcp.config import Settings, load_settings
from telegram_readonly_mcp.guard import GuardedTelegramClient, ReadOnlyViolation
from telegram_readonly_mcp.models import (
    DeleteMessagesInput,
    Dialog,
    EditMessageInput,
    MessageInput,
    SendMessageInput,
)
from telegram_readonly_mcp.server import create_http_app, create_server
from telegram_readonly_mcp.service import READ_TOOLS, WRITE_TOOLS, ReadService


def settings(tmp_path, **overrides):
    return Settings(
        session_dir=tmp_path / "synthetic-no-session",
        **{
            "write_enabled": True,
            "write_allow_ids": frozenset({101, -202, -1000000000303}),
            **overrides,
        },
    )


def test_configuration_defaults_and_exact_explicit_opt_in(tmp_path, monkeypatch):
    for key in ("TELEGRAM_WRITE_ENABLED", "TELEGRAM_WRITE_ALLOWED_CHAT_IDS"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / "synthetic.env"
    env.write_text("", encoding="utf-8")
    config = load_settings(env)
    assert config.write_enabled is False and config.write_allow_ids == frozenset()
    env.write_text(
        "TELEGRAM_WRITE_ENABLED=true\nTELEGRAM_WRITE_ALLOWED_CHAT_IDS=101,-202\n", encoding="utf-8"
    )
    config = load_settings(env)
    assert config.write_enabled is True and config.write_allow_ids == frozenset({101, -202})
    monkeypatch.setenv("TELEGRAM_WRITE_ENABLED", "false")
    assert load_settings(env).write_enabled is False
    monkeypatch.delenv("TELEGRAM_WRITE_ENABLED")
    for value in ("*", "0", "01", "+101", "1_01", "1.5", "True", "9223372036854775808"):
        monkeypatch.setenv("TELEGRAM_WRITE_ALLOWED_CHAT_IDS", value)
        with pytest.raises(ValueError):
            load_settings(env)
    monkeypatch.delenv("TELEGRAM_WRITE_ALLOWED_CHAT_IDS")
    monkeypatch.setenv("TELEGRAM_WRITE_ENABLED", "yes")
    with pytest.raises(ValueError, match="true or false"):
        load_settings(env)


@pytest.mark.parametrize("bad_id", [True, "101", 101.0, 0, 2**63])
def test_strict_numeric_chat_ids_and_config(tmp_path, bad_id):
    with pytest.raises(ValidationError):
        SendMessageInput(chat_id=bad_id, text="synthetic")
    with pytest.raises(ValidationError):
        settings(tmp_path, write_allow_ids=[bad_id])


@pytest.mark.parametrize(
    "bad_params",
    [
        {"text": " "},
        {"text": "a" * 4097},
        {"text": "😀" * 2049},
        {"text": "ok", "silent": "false"},
        {"text": "ok", "silent": 0},
        {"text": "ok", "reply_to_message_id": True},
        {"text": "ok", "reply_to_message_id": 2**31},
        {"text": "ok", "parse_mode": "html"},
    ],
)
def test_bounded_literal_send_input(bad_params):
    with pytest.raises(ValidationError):
        SendMessageInput(chat_id=101, **bad_params)
    params = SendMessageInput(chat_id=101, text="  **literal**\nhttps://example.invalid  ")
    assert params.text.startswith("  ") and params.text.endswith("  ") and params.silent is True


@pytest.mark.parametrize("ids", [[], [1, 1], [0], [True], ["1"], list(range(1, 102))])
def test_bounded_unique_deletion_ids(ids):
    with pytest.raises(ValidationError):
        DeleteMessagesInput(chat_id=101, message_ids=ids)


@pytest.mark.parametrize(
    "overrides",
    [
        {"write_enabled": False},
        {"write_allow_ids": frozenset()},
        {"deny_ids": frozenset({101})},
        {"allow_ids": frozenset({-202})},
    ],
)
async def test_denial_before_backend_open_or_any_network(tmp_path, overrides):
    class Untouched(DemoBackend):
        async def open(self):
            raise AssertionError("A denied write must not open a backend")

        async def dialogs(self):
            raise AssertionError("A denied write must not fetch dialogs")

    service = ReadService(Untouched(), settings(tmp_path, **overrides))
    with pytest.raises(ReadOnlyViolation):
        await service.execute("send_message", SendMessageInput(chat_id=101, text="never sent"))
    assert service.opened is False


async def test_demo_send_edit_delete_preserves_read_watermarks_and_ownership(tmp_path):
    backend = DemoBackend()
    service = ReadService(backend, settings(tmp_path))
    watermark = backend.chats[0].read_inbox_max_id
    sent = await service.execute(
        "send_message", SendMessageInput(chat_id=101, text=" **literal** ", reply_to_message_id=1)
    )
    assert sent.source == "demo" and sent.message.outgoing and sent.message.reply_to_id == 1
    assert sent.message.text == " **literal** "
    edited = await service.execute(
        "edit_message", EditMessageInput(chat_id=101, message_id=sent.message.id, text="changed")
    )
    assert edited.message.text == "changed" and edited.message.edited_at is not None
    before = list(backend.data)
    with pytest.raises(ReadOnlyViolation, match="own outgoing"):
        await service.execute(
            "edit_message", EditMessageInput(chat_id=101, message_id=1, text="bad")
        )
    with pytest.raises(ReadOnlyViolation, match="own outgoing"):
        await service.execute(
            "delete_messages", DeleteMessagesInput(chat_id=101, message_ids=[sent.message.id, 1])
        )
    assert backend.data == before  # A mixed valid/invalid delete batch has no partial effect.
    deleted = await service.execute(
        "delete_messages", DeleteMessagesInput(chat_id=101, message_ids=[sent.message.id])
    )
    assert deleted.accepted and deleted.requested_message_ids == [sent.message.id]
    assert await backend.message(101, sent.message.id) is None
    assert backend.chats[0].read_inbox_max_id == watermark


async def test_revalidation_defeats_constructed_or_copied_invalid_models(tmp_path):
    service = ReadService(DemoBackend(), settings(tmp_path))
    for params in (
        SendMessageInput.model_construct(chat_id=True, text="bad", silent=True),
        SendMessageInput(chat_id=101, text="good").model_copy(update={"silent": "false"}),
    ):
        with pytest.raises(ValidationError):
            await service.execute("send_message", params)
    assert service.opened is False


async def test_missing_replies_and_channel_local_only_deletion_refused(tmp_path):
    service = ReadService(DemoBackend(), settings(tmp_path))
    with pytest.raises(ValueError, match="does not exist"):
        await service.execute(
            "send_message", SendMessageInput(chat_id=101, text="bad", reply_to_message_id=999)
        )
    with pytest.raises(ValueError, match="always delete for everyone"):
        await service.execute(
            "delete_messages",
            DeleteMessagesInput(chat_id=-1000000000303, message_ids=[2], revoke=False),
        )


async def test_write_timeout_does_not_claim_no_effect_or_retry(tmp_path):
    class Uncertain(DemoBackend):
        attempts = 0

        async def send_message(self, params):
            self.attempts += 1
            await super().send_message(params)
            raise TimeoutError()

    backend = Uncertain()
    service = ReadService(backend, settings(tmp_path))
    with pytest.raises(ValueError, match="outcome is unknown"):
        await service.execute("send_message", SendMessageInput(chat_id=101, text="synthetic"))
    assert backend.attempts == 1
    assert any(m.text == "synthetic" for m in backend.data)


@pytest.mark.parametrize(
    "error_class",
    [
        errors.ServerError,
        errors.TimedOutError,
        errors.RandomIdDuplicateError,
        errors.RpcCallFailError,
    ],
)
async def test_rpc_server_error_is_an_uncertain_write_outcome(tmp_path, error_class):
    class Uncertain(DemoBackend):
        attempts = 0

        async def send_message(self, params):
            self.attempts += 1
            await super().send_message(params)
            if error_class in {errors.ServerError, errors.TimedOutError}:
                raise error_class(None, "SYNTHETIC_PRIVATE_DETAIL", 500)
            raise error_class(None)

    backend = Uncertain()
    service = ReadService(backend, settings(tmp_path))
    with pytest.raises(ValueError, match="outcome is unknown") as caught:
        await service.execute("send_message", SendMessageInput(chat_id=101, text="synthetic"))
    assert backend.attempts == 1 and "SYNTHETIC_PRIVATE_DETAIL" not in str(caught.value)


@pytest.fixture
def rpc_backend(tmp_path, monkeypatch):
    date = datetime(2026, 10, 6, tzinfo=UTC)
    messages = {
        1: types.Message(id=1, peer_id=types.PeerUser(101), date=date, message="own", out=True),
        2: types.Message(
            id=2, peer_id=types.PeerUser(101), date=date, message="incoming", out=False
        ),
        3: types.Message(
            id=3, peer_id=types.PeerUser(202), date=date, message="other chat", out=True
        ),
        4: types.Message(
            id=4, peer_id=types.PeerChannel(303), date=date, message="own channel", out=True
        ),
        5: types.Message(
            id=5,
            peer_id=types.PeerUser(101),
            date=date,
            message="caption",
            out=True,
            media=types.MessageMediaPhoto(),
        ),
        6: types.MessageService(
            id=6,
            peer_id=types.PeerUser(101),
            date=date,
            action=types.MessageActionPinMessage(),
            out=True,
        ),
    }
    requests = []

    def fake_send(sender, request, ordered=False):
        while type(request) in {
            functions.InvokeWithoutUpdatesRequest,
            functions.InvokeWithLayerRequest,
            functions.InitConnectionRequest,
        }:
            request = request.query
        requests.append(request)
        if type(request) in {
            functions.messages.GetMessagesRequest,
            functions.channels.GetMessagesRequest,
        }:
            result = types.messages.Messages(
                messages=[messages[item.id] for item in request.id if item.id in messages],
                topics=[],
                chats=[],
                users=[],
            )
        elif type(request) is functions.messages.SendMessageRequest:
            result = types.UpdateShortSentMessage(id=100, pts=1, pts_count=1, date=date, out=True)
        elif type(request) is functions.messages.EditMessageRequest:
            message = messages[request.id]
            message.message = request.message
            result = types.Updates(
                updates=[types.UpdateEditMessage(message=message, pts=2, pts_count=1)],
                users=[],
                chats=[],
                date=date,
                seq=1,
            )
        elif type(request) in {
            functions.messages.DeleteMessagesRequest,
            functions.channels.DeleteMessagesRequest,
        }:
            result = types.messages.AffectedMessages(pts=3, pts_count=1)
        else:
            raise AssertionError(f"Unexpected synthetic RPC: {type(request).__name__}")
        future = asyncio.get_running_loop().create_future()
        future.set_result(result)
        return future

    monkeypatch.setattr(MTProtoSender, "send", fake_send)
    config = settings(tmp_path)
    backend = TelegramBackend(config)
    backend.client = GuardedTelegramClient(StringSession(), 1, "a" * 32, write_settings=config)
    backend.peers = {
        101: types.InputPeerUser(101, 11),
        -202: types.InputPeerChat(202),
        -1000000000303: types.InputPeerChannel(303, 33),
    }
    return backend, requests


async def test_real_rpc_send_plain_text_silent_and_edit_owned_message(rpc_backend):
    backend, requests = rpc_backend
    sent = await backend.send_message(
        SendMessageInput(
            chat_id=101, text=" **literal** https://example.invalid ", reply_to_message_id=2
        )
    )
    request = requests[-1]
    assert type(request) is functions.messages.SendMessageRequest
    assert request.no_webpage is True and request.entities == [] and request.silent is True
    assert request.message == sent.message.text and sent.message.id == 100
    assert request.reply_to.reply_to_msg_id == 2
    await backend.send_message(SendMessageInput(chat_id=101, text="audible", silent=False))
    assert requests[-1].silent is False
    edited = await backend.edit_message(EditMessageInput(chat_id=101, message_id=1, text="new"))
    assert edited.message.id == 1 and edited.message.text == "new"
    assert requests[-1].no_webpage is True and requests[-1].entities == []
    assert backend.client._request_retries == 0 and backend.client._no_updates is True


async def test_nonchannel_ids_cannot_address_other_chats_and_no_partial_delete(rpc_backend):
    backend, requests = rpc_backend
    assert await backend.message(101, 3) is None
    for ids in ([3], [1, 3], [1, 2], [1, 6]):
        with pytest.raises((ValueError, ReadOnlyViolation)):
            await backend.delete_messages(DeleteMessagesInput(chat_id=101, message_ids=ids))
    assert not any(
        type(r)
        in {functions.messages.DeleteMessagesRequest, functions.channels.DeleteMessagesRequest}
        for r in requests
    )
    with pytest.raises(ReadOnlyViolation, match="own outgoing"):
        await backend.edit_message(EditMessageInput(chat_id=101, message_id=2, text="bad"))
    with pytest.raises(ValueError, match="plain-text"):
        await backend.edit_message(EditMessageInput(chat_id=101, message_id=5, text="bad"))
    assert not any(type(r) is functions.messages.EditMessageRequest for r in requests)
    with pytest.raises(ValueError, match="does not exist"):
        await backend.send_message(SendMessageInput(chat_id=101, text="bad", reply_to_message_id=3))
    assert not any(type(r) is functions.messages.SendMessageRequest for r in requests)


async def test_service_messages_remain_readable_but_not_mutable(rpc_backend, monkeypatch):
    backend, requests = rpc_backend

    async def dialogs():
        return [Dialog(id=101, title="Synthetic", kind="private")]

    monkeypatch.setattr(backend, "dialogs", dialogs)
    service = ReadService(backend, backend.settings)
    service.opened = True  # Synthetic RPC backend is ready; never load a session/connect.
    result = await service.execute("get_message", MessageInput(chat_id=101, message_id=6))
    assert result.message.service_action == "MessageActionPinMessage"
    with pytest.raises(ReadOnlyViolation, match="non-service"):
        await backend.edit_message(EditMessageInput(chat_id=101, message_id=6, text="bad"))
    assert not any(type(r) is functions.messages.EditMessageRequest for r in requests)


async def test_channel_aware_delete_rpc_and_nonchannel_revoke(rpc_backend):
    backend, requests = rpc_backend
    await backend.delete_messages(DeleteMessagesInput(chat_id=101, message_ids=[1], revoke=False))
    assert type(requests[-1]) is functions.messages.DeleteMessagesRequest
    assert requests[-1].id == [1] and requests[-1].revoke is False
    await backend.delete_messages(DeleteMessagesInput(chat_id=-1000000000303, message_ids=[4]))
    assert type(requests[-1]) is functions.channels.DeleteMessagesRequest
    assert requests[-1].channel.channel_id == 303 and requests[-1].id == [4]
    with pytest.raises(ValueError, match="always delete for everyone"):
        await backend.delete_messages(
            DeleteMessagesInput(chat_id=-1000000000303, message_ids=[4], revoke=False)
        )


async def test_guards_both_rpc_boundaries_and_scoped_request_identity(rpc_backend):
    backend, requests = rpc_backend
    client = backend.client
    request = functions.messages.SendMessageRequest(
        peer=backend.peers[101],
        message="synthetic",
        no_webpage=True,
        silent=True,
        entities=[],
    )
    for wrapper in (request, functions.InvokeWithoutUpdatesRequest(request), [request]):
        with pytest.raises(ReadOnlyViolation):
            await client(wrapper)
        with pytest.raises(ReadOnlyViolation):
            client._sender.send(wrapper)
    assert requests == []
    with client.authorize_write(request, 101):
        await client(request)
        copied = functions.messages.SendMessageRequest(
            peer=backend.peers[101],
            message="synthetic",
            no_webpage=True,
            silent=True,
            entities=[],
        )
        with pytest.raises(ReadOnlyViolation):
            client._sender.send(copied)
        request.message = "changed after approval"
        with pytest.raises(ReadOnlyViolation):
            await client(request)
        with pytest.raises(ReadOnlyViolation):
            client._sender.send(request)
        request.message = "synthetic"

        async def child_task():
            with pytest.raises(ReadOnlyViolation):
                await client(request)

        await asyncio.create_task(child_task())
        with pytest.raises(ReadOnlyViolation):
            await client._call(object(), request)
    with pytest.raises(ReadOnlyViolation):
        client._sender.send(request)


@pytest.mark.parametrize(
    "rpc_request",
    [
        functions.messages.SendMessageRequest(types.InputPeerUser(101, 11), "no preview flag"),
        functions.messages.SendMessageRequest(
            types.InputPeerUser(999, 11), "wrong peer", no_webpage=True, silent=True, entities=[]
        ),
        functions.messages.EditMessageRequest(
            types.InputPeerUser(101, 11),
            1,
            message="bad",
            no_webpage=True,
            media=types.InputMediaEmpty(),
        ),
        functions.messages.SendMessageRequest(
            types.InputPeerUser(101, 11),
            "paid",
            no_webpage=True,
            silent=True,
            entities=[],
            allow_paid_stars=1,
        ),
        functions.messages.SendMessageRequest(
            types.InputPeerUser(101, 11),
            "scheduled",
            no_webpage=True,
            silent=True,
            entities=[],
            schedule_date=datetime(2026, 10, 7, tzinfo=UTC),
        ),
        functions.messages.SendMessageRequest(
            types.InputPeerUser(101, 11),
            "markup",
            no_webpage=True,
            silent=True,
            entities=[types.MessageEntityBold(offset=0, length=2)],
        ),
        functions.messages.SendMessageRequest(
            types.InputPeerUser(101, 11),
            "impersonation",
            no_webpage=True,
            silent=True,
            entities=[],
            send_as=types.InputPeerUser(202, 22),
        ),
        functions.messages.SendMessageRequest(
            types.InputPeerUser(101, 11),
            "external reply",
            no_webpage=True,
            silent=True,
            entities=[],
            reply_to=types.InputReplyToMessage(
                reply_to_msg_id=1,
                reply_to_peer_id=types.InputPeerUser(202, 22),
            ),
        ),
        functions.channels.DeleteMessagesRequest(types.InputChannel(999, 11), [1]),
        functions.messages.DeleteMessagesRequest([0], revoke=True),
        functions.account.UpdateStatusRequest(offline=False),
        functions.auth.LogOutRequest(),
        object(),
    ],
)
async def test_write_approval_rejects_bad_shape_and_unknown_rpc(rpc_backend, rpc_request):
    backend, requests = rpc_backend
    with pytest.raises((ReadOnlyViolation, ValidationError)):
        with backend.client.authorize_write(rpc_request, 101):
            await backend.client(rpc_request)
    assert requests == []


@pytest.mark.parametrize(
    "rpc_request",
    [
        functions.messages.ReadHistoryRequest(types.InputPeerSelf(), 1),
        functions.account.UpdateStatusRequest(offline=False),
        functions.channels.JoinChannelRequest(types.InputChannel(1, 2)),
        functions.auth.LogOutRequest(),
        functions.auth.ExportAuthorizationRequest(2),
        functions.updates.GetDifferenceRequest(pts=0, date=None, qts=0),
    ],
)
async def test_background_and_account_mutations_stay_blocked_when_write_enabled(
    rpc_backend, rpc_request
):
    backend, requests = rpc_backend
    with pytest.raises(ReadOnlyViolation):
        await backend.client(functions.InvokeWithoutUpdatesRequest(rpc_request))
    with pytest.raises(ReadOnlyViolation):
        backend.client._sender.send(rpc_request)
    assert requests == []


async def test_authentication_client_cannot_write_even_with_enabled_settings(tmp_path):
    client = GuardedTelegramClient(
        StringSession(),
        1,
        "a" * 32,
        authentication=True,
        write_settings=settings(tmp_path),
    )
    request = functions.messages.SendMessageRequest(
        types.InputPeerUser(101, 11),
        "synthetic",
        no_webpage=True,
        silent=True,
        entities=[],
    )
    with pytest.raises(ReadOnlyViolation):
        with client.authorize_write(request, 101):
            await client(request)


async def test_client_does_not_retry_5xx_writes(tmp_path, monkeypatch):
    attempts = 0

    def failed_send(sender, request, ordered=False):
        nonlocal attempts
        attempts += 1
        future = asyncio.get_running_loop().create_future()
        future.set_exception(errors.ServerError(request, "SYNTHETIC_5XX", 500))
        return future

    monkeypatch.setattr(MTProtoSender, "send", failed_send)
    client = GuardedTelegramClient(StringSession(), 1, "a" * 32, write_settings=settings(tmp_path))
    request = functions.messages.SendMessageRequest(
        types.InputPeerUser(101, 11),
        "synthetic",
        no_webpage=True,
        silent=True,
        entities=[],
    )
    with client.authorize_write(request, 101), pytest.raises(errors.ServerError):
        await client(request)
    assert attempts == 1


async def test_enabled_rpc_acl_denies_before_sender_send(rpc_backend):
    backend, requests = rpc_backend
    request = functions.messages.SendMessageRequest(
        types.InputPeerUser(999, 11),
        "synthetic",
        no_webpage=True,
        silent=True,
        entities=[],
    )
    with pytest.raises(ReadOnlyViolation, match="ACL"):
        with backend.client.authorize_write(request, 999):
            await backend.client(request)
    assert requests == []


async def test_tools_absent_by_default_and_correct_annotations_when_enabled(tmp_path):
    readonly, _ = create_server(Settings(session_dir=tmp_path), demo=True)
    assert {t.name for t in await readonly.list_tools()} == READ_TOOLS
    enabled, _ = create_server(settings(tmp_path), demo=True)
    tools = {t.name: t for t in await enabled.list_tools()}
    assert tools.keys() == READ_TOOLS | WRITE_TOOLS
    assert tools["send_message"].annotations.readOnlyHint is False
    assert tools["send_message"].annotations.idempotentHint is False
    assert tools["edit_message"].annotations.destructiveHint is True
    assert tools["delete_messages"].annotations.destructiveHint is True


async def test_authenticated_http_write_and_denied_chat(tmp_path):
    mcp, _ = create_server(settings(tmp_path, write_allow_ids=frozenset({101})), demo=True)
    token = "synthetic-http-write-test-token-0123456789"
    app = create_http_app(mcp, token)
    async with (
        app.app.router.lifespan_context(app.app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8765",
        ) as client,
    ):
        headers = {
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "send_message",
                "arguments": {"params": {"chat_id": 101, "text": "demo"}},
            },
        }
        assert (await client.post("/mcp", json=payload)).status_code == 401
        response = await client.post("/mcp", headers=headers, json=payload)
        assert not response.json()["result"].get("isError")
        assert response.json()["result"]["structuredContent"]["source"] == "demo"
        payload["params"]["arguments"]["params"]["chat_id"] = -202
        response = await client.post("/mcp", headers=headers, json=payload)
        assert response.json()["result"]["isError"] is True
        payload["params"]["arguments"]["params"]["chat_id"] = "101"
        response = await client.post("/mcp", headers=headers, json=payload)
        assert response.json()["result"]["isError"] is True


async def test_enabled_stdio_protocol_with_synthetic_writes_only(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WRITE_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_WRITE_ALLOWED_CHAT_IDS", "101")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "*")
    monkeypatch.setenv("TELEGRAM_DENIED_CHAT_IDS", "")
    monkeypatch.setenv("TELEGRAM_API_ID", "0")
    monkeypatch.setenv("TELEGRAM_SESSION_DIR", str(tmp_path / "never-created"))
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "telegram_readonly_mcp",
            "--env-file",
            str(tmp_path / "absent.env"),
            "serve",
            "--demo",
        ],
        env={
            "TELEGRAM_WRITE_ENABLED": "true",
            "TELEGRAM_WRITE_ALLOWED_CHAT_IDS": "101",
            "TELEGRAM_ALLOWED_CHAT_IDS": "*",
            "TELEGRAM_DENIED_CHAT_IDS": "",
            "TELEGRAM_API_ID": "0",
            "TELEGRAM_API_HASH": "",
            "TELEGRAM_SESSION_DIR": str(tmp_path / "never-created"),
        },
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        assert (
            "untrusted" in initialized.instructions
            and "explicit user authorization" in initialized.instructions
        )
        assert {
            tool.name for tool in (await session.list_tools()).tools
        } == READ_TOOLS | WRITE_TOOLS
        sent = await session.call_tool(
            "send_message", {"params": {"chat_id": 101, "text": "synthetic"}}
        )
        assert not sent.isError and sent.structuredContent["source"] == "demo"
        message_id = sent.structuredContent["message"]["id"]
        edited = await session.call_tool(
            "edit_message",
            {"params": {"chat_id": 101, "message_id": message_id, "text": "changed"}},
        )
        assert not edited.isError and edited.structuredContent["message"]["text"] == "changed"
        deleted = await session.call_tool(
            "delete_messages",
            {"params": {"chat_id": 101, "message_ids": [message_id]}},
        )
        assert not deleted.isError and deleted.structuredContent["accepted"] is True
    assert not (tmp_path / "never-created").exists()
