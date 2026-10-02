"""Real Telethon iterators over synthetic MTProto responses; no network/sessions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from telethon import functions, types
from telethon.network.mtprotosender import MTProtoSender
from telethon.sessions import StringSession

from telegram_readonly_mcp.backend import TelegramBackend
from telegram_readonly_mcp.config import Settings
from telegram_readonly_mcp.guard import GuardedTelegramClient, assert_read_request


async def test_real_telethon_iterators_and_rpc_guard(monkeypatch, tmp_path):
    date = datetime(2026, 10, 2, 9, tzinfo=UTC)
    user = types.User(id=101, access_hash=11, first_name="Synthetic person")
    group = types.Chat(
        id=202,
        title="Synthetic group",
        photo=types.ChatPhotoEmpty(),
        participants_count=2,
        date=date,
        version=1,
    )
    channel = types.Channel(
        id=303,
        access_hash=33,
        title="Synthetic channel",
        photo=types.ChatPhotoEmpty(),
        date=date,
        broadcast=True,
    )
    peers = [types.PeerUser(101), types.PeerChat(202), types.PeerChannel(303)]
    messages = {101: [], -202: [], -1000000000303: []}
    for chat_id, peer in zip(messages, peers, strict=True):
        messages[chat_id] = [
            types.Message(
                id=i,
                peer_id=peer,
                from_id=types.PeerUser(101),
                date=date,
                message=f"synthetic item {i}",
            )
            for i in (4, 3, 2, 1)
        ]
    dialogs = [
        types.Dialog(
            peer=peer,
            top_message=4,
            read_inbox_max_id=2,
            read_outbox_max_id=0,
            unread_count=2,
            unread_mentions_count=0,
            unread_reactions_count=0,
            unread_poll_votes_count=0,
            notify_settings=types.PeerNotifySettings(),
            folder_id=1 if isinstance(peer, types.PeerChat) else None,
        )
        for peer in peers
    ]
    requests = []

    def fake_send(sender, rpc_request, ordered=False):
        assert_read_request(rpc_request)
        while isinstance(rpc_request, functions.InvokeWithoutUpdatesRequest):
            rpc_request = rpc_request.query
        requests.append(type(rpc_request))
        if isinstance(rpc_request, functions.messages.GetDialogsRequest):
            result = types.messages.Dialogs(
                dialogs=dialogs,
                messages=[m[0] for m in messages.values()],
                chats=[group, channel],
                users=[user],
            )
        else:
            if isinstance(rpc_request, functions.channels.GetMessagesRequest):
                chat_id = -1000000000303
            elif isinstance(rpc_request, functions.messages.GetMessagesRequest):
                chat_id = 101  # Exercise private message lookup separately from channel lookup.
            else:
                peer = rpc_request.peer
                chat_id = (
                    peer.user_id
                    if isinstance(peer, types.InputPeerUser)
                    else -peer.chat_id
                    if isinstance(peer, types.InputPeerChat)
                    else -(1000000000000 + peer.channel_id)
                )
            records = messages[chat_id]
            if hasattr(rpc_request, "id"):
                ids = [item.id for item in rpc_request.id]
                records = [m for m in records if m.id in ids]
            else:
                offset_id = getattr(rpc_request, "offset_id", 0)
                min_id = getattr(rpc_request, "min_id", 0)
                records = [
                    m for m in records if (not offset_id or m.id < offset_id) and m.id > min_id
                ]
                if isinstance(rpc_request, functions.messages.SearchRequest):
                    records = [m for m in records if rpc_request.q in m.message]
                records = records[: rpc_request.limit]
            result = types.messages.Messages(
                messages=records, topics=[], chats=[group, channel], users=[user]
            )
        future = asyncio.get_running_loop().create_future()
        future.set_result(result)
        return future

    monkeypatch.setattr(MTProtoSender, "send", fake_send)
    backend = TelegramBackend(Settings(session_dir=tmp_path))
    backend.client = GuardedTelegramClient(StringSession(), 1, "a" * 32)
    all_dialogs = await backend.dialogs()
    assert [(d.id, d.kind) for d in all_dialogs] == [
        (101, "private"),
        (-202, "group"),
        (-1000000000303, "channel"),
    ]
    assert all_dialogs[1].archived
    history = await backend.messages(-202, limit=2)
    assert [m.id for m in history] == [4, 3]
    older = await backend.messages(-202, limit=2, before_id=3)
    assert [m.id for m in older] == [2, 1]
    found = await backend.messages(-1000000000303, limit=3, query="item 3")
    assert [m.id for m in found] == [3]
    assert (await backend.message(101, 3)).text == "synthetic item 3"
    assert (await backend.message(-1000000000303, 3)).chat_id == -1000000000303
    assert await backend.message(101, 999) is None
    assert set(requests) == {
        functions.messages.GetDialogsRequest,
        functions.messages.GetHistoryRequest,
        functions.messages.SearchRequest,
        functions.messages.GetMessagesRequest,
        functions.channels.GetMessagesRequest,
    }
