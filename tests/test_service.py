from __future__ import annotations

from datetime import UTC, datetime

import pytest
from telethon import errors

from telegram_readonly_mcp.backend import DemoBackend
from telegram_readonly_mcp.config import Settings
from telegram_readonly_mcp.guard import ReadOnlyViolation
from telegram_readonly_mcp.models import (
    AcrossInput,
    BetweenInput,
    Dialog,
    DialogsInput,
    HistoryInput,
    Message,
    MessageInput,
    SearchInput,
)
from telegram_readonly_mcp.service import ReadService


@pytest.fixture
def service(tmp_path):
    return ReadService(DemoBackend(), Settings(session_dir=tmp_path))


async def collect(service, operation, params):
    result = []
    for _ in range(50):
        page = await service.execute(operation, params)
        assert len(page.items) <= params.limit
        result.extend(page.items)
        if not page.has_more:
            return result
        assert page.next_cursor
        params = params.model_copy(update={"cursor": page.next_cursor})
    raise AssertionError("Pagination did not terminate")


async def test_dialogs_archive_search_and_pagination(service):
    dialogs = await collect(service, "list_dialogs", DialogsInput(limit=1))
    assert len(dialogs) == 3
    assert any(d.archived for d in dialogs)
    page = await service.execute("list_dialogs", DialogsInput(query="ГРУППА"))
    assert [d.id for d in page.items] == [-202]


async def test_history_pages_same_message_ids_across_chats(service):
    first = await service.execute("get_chat_history", HistoryInput(chat_id=101, limit=2))
    assert [m.id for m in first.items] == [4, 3]
    second = await service.execute(
        "get_chat_history", HistoryInput(chat_id=101, limit=2, before_id=first.next_before_id)
    )
    assert [m.id for m in second.items] == [2, 1]
    assert not second.has_more
    one = await service.execute("get_message", MessageInput(chat_id=-202, message_id=3))
    assert one.message.chat_id == -202
    missing = await service.execute("get_message", MessageInput(chat_id=101, message_id=100))
    assert missing.message is None


@pytest.mark.parametrize(
    "operation,params,expected",
    [
        ("search_messages", SearchInput(query="задача", limit=2), 12),
        ("search_messages", SearchInput(query="задача", chat_id=101, limit=2), 4),
        ("get_latest_messages", AcrossInput(limit=1, per_chat_limit=2), 6),
        ("get_unread_messages", AcrossInput(limit=1), 6),
    ],
)
async def test_global_and_chat_pagination(service, operation, params, expected):
    messages = await collect(service, operation, params)
    assert len(messages) == expected
    assert len({(m.chat_id, m.id) for m in messages}) == expected


async def test_unread_excludes_outgoing_and_keeps_watermark(service):
    service.backend.data.append(
        Message(id=5, chat_id=101, date=datetime.now(UTC), text="outgoing", outgoing=True)
    )
    messages = await collect(service, "get_unread_messages", AcrossInput(chat_id=101, limit=1))
    assert [m.id for m in messages] == [4, 3]
    assert service.backend.chats[0].read_inbox_max_id == 2


async def test_date_boundaries_and_utc_conversion(service):
    params = BetweenInput(
        chat_id=101, start="2026-10-02T12:00:02+03:00", end="2026-10-02T12:00:04+03:00", limit=1
    )
    first = await service.execute("messages_between", params)
    assert [m.id for m in first.items] == [3]
    assert first.has_more
    second = await service.execute("messages_between", params.model_copy(update={"before_id": 3}))
    assert [m.id for m in second.items] == [2]
    assert not second.has_more
    with pytest.raises(ValueError, match="precede"):
        await service.execute("messages_between", params.model_copy(update={"end": params.start}))


async def test_acl_filters_all_and_denial_precedes_network(tmp_path):
    class Tracked(DemoBackend):
        calls = []

        async def messages(self, chat_id, **kwargs):
            self.calls.append(chat_id)
            return await super().messages(chat_id, **kwargs)

    backend = Tracked()
    service = ReadService(
        backend,
        Settings(
            session_dir=tmp_path, allow_ids=frozenset({101, -202}), deny_ids=frozenset({-202})
        ),
    )
    for operation, params in (
        ("get_chat_history", HistoryInput(chat_id=-202)),
        ("get_message", MessageInput(chat_id=-202, message_id=1)),
        ("get_latest_messages", AcrossInput(chat_id=-202)),
    ):
        with pytest.raises(ReadOnlyViolation):
            await service.execute(operation, params)
    assert not backend.calls
    dialogs = await collect(service, "list_dialogs", DialogsInput())
    assert [d.id for d in dialogs] == [101]
    messages = await collect(service, "search_messages", SearchInput(query="задача", limit=1))
    assert {m.chat_id for m in messages} == {101}
    assert set(backend.calls) == {101}


async def test_unknown_operation_blocked(service):
    with pytest.raises(ReadOnlyViolation):
        await service.execute("send_message", HistoryInput(chat_id=101))


async def test_invalid_tampered_cross_query_and_restart_cursors(service, tmp_path):
    page = await service.execute("search_messages", SearchInput(query="задача", limit=1))
    for token, query in (
        ("invalid!", "задача"),
        (page.next_cursor[:-2] + "AA", "задача"),
        (page.next_cursor, "other"),
    ):
        with pytest.raises(ValueError, match="cursor"):
            await service.execute("search_messages", SearchInput(query=query, cursor=token))
    restarted = ReadService(DemoBackend(), Settings(session_dir=tmp_path))
    with pytest.raises(ValueError, match="cursor"):
        await restarted.execute(
            "search_messages", SearchInput(query="задача", cursor=page.next_cursor)
        )


async def test_scan_cap_is_resumable_and_not_silent(tmp_path):
    chats = [Dialog(id=i, title=f"chat {i}", kind="private") for i in range(1, 42)]
    data = [Message(id=1, chat_id=41, date=datetime.now(UTC), text="find")]
    service = ReadService(DemoBackend(chats, data), Settings(session_dir=tmp_path, scan_chats=20))
    first = await service.execute("search_messages", SearchInput(query="find"))
    assert first.items == [] and first.has_more and first.scan_limited
    result = await collect(service, "search_messages", SearchInput(query="find"))
    assert len(result) == 1 and result[0].chat_id == 41


async def test_errors_do_not_expose_rpc_details(tmp_path):
    class Failing(DemoBackend):
        async def dialogs(self):
            raise errors.RPCError(None, "PRIVATE_SECRET", 500)

    service = ReadService(Failing(), Settings(session_dir=tmp_path))
    with pytest.raises(ValueError, match="Telegram rejected") as caught:
        await service.execute("list_dialogs", DialogsInput())
    assert "PRIVATE_SECRET" not in str(caught.value)


async def test_flood_wait_returns_retry_after(tmp_path):
    class Flooded(DemoBackend):
        async def dialogs(self):
            raise errors.FloodWaitError(None, 71)

    service = ReadService(Flooded(), Settings(session_dir=tmp_path))
    with pytest.raises(ValueError, match="71 seconds"):
        await service.execute("list_dialogs", DialogsInput())
