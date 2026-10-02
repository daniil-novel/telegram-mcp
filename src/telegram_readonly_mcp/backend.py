from __future__ import annotations

from datetime import datetime
from typing import Protocol

from telethon import types
from telethon.sessions import StringSession

from .config import Settings
from .guard import GuardedTelegramClient
from .models import Dialog, Message
from .security import SessionStore


class Backend(Protocol):
    source: str

    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def dialogs(self) -> list[Dialog]: ...
    async def messages(
        self,
        chat_id: int,
        *,
        limit: int,
        before_id: int = 0,
        min_id: int = 0,
        query: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Message]: ...
    async def message(self, chat_id: int, message_id: int) -> Message | None: ...


def serialize_message(item: object, chat_id: int) -> Message | None:
    if isinstance(item, types.MessageEmpty) or not getattr(item, "date", None):
        return None
    text = getattr(item, "message", "") or ""
    reply = getattr(item, "reply_to", None)
    media = getattr(item, "media", None)
    action = getattr(item, "action", None)
    return Message(
        id=item.id,
        chat_id=chat_id,
        date=item.date,
        text=text[:8000],
        text_truncated=len(text) > 8000,
        sender_id=getattr(item, "sender_id", None),
        outgoing=bool(getattr(item, "out", False)),
        reply_to_id=getattr(reply, "reply_to_msg_id", None),
        media_type=type(media).__name__ if media else None,
        service_action=type(action).__name__ if action else None,
        edited_at=getattr(item, "edit_date", None),
    )


class TelegramBackend:
    source = "telegram"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: GuardedTelegramClient | None = None
        self.peers: dict[int, object] = {}

    async def open(self) -> None:
        self.settings.require_credentials()
        session = StringSession(SessionStore(self.settings.session_dir).load())
        self.client = GuardedTelegramClient(
            session,
            self.settings.api_id,
            self.settings.api_hash.get_secret_value(),
            device_model="Telegram Read-only MCP",
            app_version="0.1.0",
        )
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                raise ValueError("Telegram session expired. Run 'auth' locally again.")
            me = await self.client.get_me()
            if me is None or me.bot:
                raise ValueError("A personal Telegram account session is required, not a bot.")
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        if self.client is not None:
            await self.client.disconnect()

    async def dialogs(self) -> list[Dialog]:
        assert self.client is not None
        records = []
        peers = {}
        # All folders including archived. This reads metadata; never acknowledges history.
        async for dialog in self.client.iter_dialogs(limit=None, ignore_migrated=False):
            peers[dialog.id] = dialog.input_entity
            records.append(
                Dialog(
                    id=dialog.id,
                    title=dialog.name or "",
                    kind=(
                        "private" if dialog.is_user else "group" if dialog.is_group else "channel"
                    ),
                    unread_count=dialog.unread_count,
                    read_inbox_max_id=dialog.dialog.read_inbox_max_id,
                    archived=bool(getattr(dialog.dialog, "folder_id", 0)),
                    latest=serialize_message(dialog.message, dialog.id) if dialog.message else None,
                )
            )
        self.peers = peers
        return records

    def _peer(self, chat_id: int) -> object:
        if chat_id not in self.peers:
            raise ValueError("Chat is not in the current account's dialog list.")
        return self.peers[chat_id]

    async def messages(
        self,
        chat_id: int,
        *,
        limit: int,
        before_id: int = 0,
        min_id: int = 0,
        query: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Message]:
        assert self.client is not None
        result = []
        async for item in self.client.iter_messages(
            self._peer(chat_id),
            limit=limit,
            offset_id=before_id,
            min_id=min_id,
            search=query,
            offset_date=end,
            wait_time=0,
        ):
            message = serialize_message(item, chat_id)
            if message is None:
                continue
            if start is not None and message.date < start:
                break
            if end is None or message.date < end:
                result.append(message)
        return result

    async def message(self, chat_id: int, message_id: int) -> Message | None:
        assert self.client is not None
        item = await self.client.get_messages(self._peer(chat_id), ids=message_id)
        return serialize_message(item, chat_id) if item else None


class DemoBackend:
    """Synthetic data only; never constructs a Telegram client or loads a session."""

    source = "demo"

    def __init__(self, dialogs: list[Dialog] | None = None, messages: list[Message] | None = None):
        self.data = (
            messages
            if messages is not None
            else [
                Message(
                    id=i,
                    chat_id=chat_id,
                    date=datetime.fromisoformat(f"2026-10-02T09:00:{i:02d}+00:00"),
                    text=f"Демо: задача {i}",
                    outgoing=(i == 2),
                )
                for chat_id in (101, -202, -1000000000303)
                for i in range(1, 5)
            ]
        )
        self.chats = (
            dialogs
            if dialogs is not None
            else [
                Dialog(
                    id=chat_id,
                    title=title,
                    kind=kind,
                    unread_count=2,
                    read_inbox_max_id=2,
                    latest=next(m for m in self.data if m.chat_id == chat_id and m.id == 4),
                    archived=chat_id == -202,
                )
                for chat_id, title, kind in (
                    (101, "Демо: личный чат", "private"),
                    (-202, "Демо: группа", "group"),
                    (-1000000000303, "Демо: канал", "channel"),
                )
            ]
        )

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def dialogs(self) -> list[Dialog]:
        return list(self.chats)

    async def messages(
        self,
        chat_id: int,
        *,
        limit: int,
        before_id: int = 0,
        min_id: int = 0,
        query: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Message]:
        return sorted(
            [
                m
                for m in self.data
                if m.chat_id == chat_id
                and m.id > min_id
                and (not before_id or m.id < before_id)
                and (not query or query.casefold() in m.text.casefold())
                and (start is None or m.date >= start)
                and (end is None or m.date < end)
            ],
            key=lambda m: m.id,
            reverse=True,
        )[:limit]

    async def message(self, chat_id: int, message_id: int) -> Message | None:
        return next((m for m in self.data if m.chat_id == chat_id and m.id == message_id), None)
