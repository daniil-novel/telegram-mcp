from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from telethon import functions, types, utils
from telethon.sessions import StringSession

from .config import Settings
from .guard import GuardedTelegramClient, ReadOnlyViolation, require_write_chat
from .models import (
    DeleteMessagesInput,
    DeleteMessagesResult,
    Dialog,
    EditMessageInput,
    Message,
    SendMessageInput,
    WriteMessageResult,
)
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
    async def send_message(self, params: SendMessageInput) -> WriteMessageResult: ...
    async def edit_message(self, params: EditMessageInput) -> WriteMessageResult: ...
    async def delete_messages(self, params: DeleteMessagesInput) -> DeleteMessagesResult: ...


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
        self.self_peer: types.InputPeerUser | None = None

    async def open(self) -> None:
        self.settings.require_credentials()
        session = StringSession(SessionStore(self.settings.session_dir).load())
        self.client = GuardedTelegramClient(
            session,
            self.settings.api_id,
            self.settings.api_hash.get_secret_value(),
            write_settings=self.settings,
            device_model="Unofficial Telegram MCP",
            app_version="0.2.0",
        )
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                raise ValueError("Telegram session expired. Run 'auth' locally again.")
            me = await self.client.get_me()
            if me is None or me.bot:
                raise ValueError("A personal Telegram account session is required, not a bot.")
            self.self_peer = utils.get_input_peer(me, allow_self=False)
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
        peer = self.peers[chat_id]
        if type(peer) is types.InputPeerSelf:
            if self.self_peer is None or self.self_peer.user_id != chat_id:
                raise ValueError("Saved Messages identity is not available; reconnect locally.")
            return self.self_peer
        return peer

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
        # Nonchannel getMessages ignores the peer argument. Never let IDs address another chat.
        if (
            not item
            or type(item) not in {types.Message, types.MessageService}
            or item.id != message_id
            or utils.get_peer_id(item.peer_id) != chat_id
        ):
            return None
        return serialize_message(item, chat_id)

    async def _existing_message(self, chat_id: int, message_id: int, *, own: bool) -> Message:
        message = await self.message(chat_id, message_id)
        if message is None:
            raise ValueError("Message does not exist in the specified chat.")
        if own and (not message.outgoing or message.service_action):
            raise ReadOnlyViolation("Only your own outgoing non-service messages can be changed.")
        return message

    def _response_message(self, request: object, response: object, chat_id: int) -> Message | None:
        if type(response) is types.UpdateShortSentMessage:
            return Message(
                id=response.id,
                chat_id=chat_id,
                date=response.date,
                text=request.message,
                outgoing=True,
                reply_to_id=getattr(getattr(request, "reply_to", None), "reply_to_msg_id", None),
            )
        updates = (
            response.updates
            if type(response) in {types.Updates, types.UpdatesCombined}
            else [response.update]
            if type(response) is types.UpdateShort
            else []
        )
        target_id = getattr(request, "id", None)
        if type(request) is functions.messages.SendMessageRequest:
            target_id = next(
                (
                    u.id
                    for u in updates
                    if type(u) is types.UpdateMessageID and u.random_id == request.random_id
                ),
                None,
            )
        for update in updates:
            if type(update) in {
                types.UpdateNewMessage,
                types.UpdateNewChannelMessage,
                types.UpdateEditMessage,
                types.UpdateEditChannelMessage,
            }:
                item = update.message
                if item.id == target_id and utils.get_peer_id(item.peer_id) == chat_id:
                    return serialize_message(item, chat_id)
        return None

    async def send_message(self, params: SendMessageInput) -> WriteMessageResult:
        params = SendMessageInput.model_validate(params.model_dump(warnings=False))
        require_write_chat(self.settings, params.chat_id)
        assert self.client is not None
        peer = self._peer(params.chat_id)
        if params.reply_to_message_id is not None:
            await self._existing_message(params.chat_id, params.reply_to_message_id, own=False)
        request = functions.messages.SendMessageRequest(
            peer=peer,
            message=params.text,
            no_webpage=True,
            silent=params.silent,
            reply_to=types.InputReplyToMessage(params.reply_to_message_id)
            if params.reply_to_message_id is not None
            else None,
            entities=[],
        )
        with self.client.authorize_write(request, params.chat_id):
            response = await self.client(request)
        return WriteMessageResult(
            operation="send_message",
            chat_id=params.chat_id,
            message=self._response_message(request, response, params.chat_id),
            source=self.source,
        )

    async def edit_message(self, params: EditMessageInput) -> WriteMessageResult:
        params = EditMessageInput.model_validate(params.model_dump(warnings=False))
        require_write_chat(self.settings, params.chat_id)
        assert self.client is not None
        peer = self._peer(params.chat_id)
        previous = await self._existing_message(params.chat_id, params.message_id, own=True)
        if previous.media_type:
            raise ValueError("Only plain-text messages can be edited through this tool.")
        request = functions.messages.EditMessageRequest(
            peer=peer,
            id=params.message_id,
            message=params.text,
            no_webpage=True,
            entities=[],
        )
        with self.client.authorize_write(request, params.chat_id):
            response = await self.client(request)
        return WriteMessageResult(
            operation="edit_message",
            chat_id=params.chat_id,
            message=self._response_message(request, response, params.chat_id),
            source=self.source,
        )

    async def delete_messages(self, params: DeleteMessagesInput) -> DeleteMessagesResult:
        params = DeleteMessagesInput.model_validate(params.model_dump(warnings=False))
        require_write_chat(self.settings, params.chat_id)
        assert self.client is not None
        peer = self._peer(params.chat_id)
        if type(peer) is types.InputPeerChannel and not params.revoke:
            raise ValueError("Channels/megagroups always delete for everyone; use revoke=true.")
        # Validate every requested ID before constructing a mutation; no partial batch deletion.
        for message_id in params.message_ids:
            await self._existing_message(params.chat_id, message_id, own=True)
        request = (
            functions.channels.DeleteMessagesRequest(
                channel=utils.get_input_channel(peer),
                id=list(params.message_ids),
            )
            if type(peer) is types.InputPeerChannel
            else functions.messages.DeleteMessagesRequest(
                id=list(params.message_ids), revoke=params.revoke
            )
        )
        with self.client.authorize_write(request, params.chat_id):
            await self.client(request)
        return DeleteMessagesResult(
            chat_id=params.chat_id,
            requested_message_ids=params.message_ids,
            revoke=params.revoke,
            source=self.source,
        )


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

    async def send_message(self, params: SendMessageInput) -> WriteMessageResult:
        item = Message(
            id=max((m.id for m in self.data if m.chat_id == params.chat_id), default=0) + 1,
            chat_id=params.chat_id,
            date=datetime.now(UTC),
            text=params.text,
            outgoing=True,
            reply_to_id=params.reply_to_message_id,
        )
        self.data.append(item)
        return WriteMessageResult(
            operation="send_message",
            chat_id=params.chat_id,
            message=item,
            source=self.source,
        )

    async def edit_message(self, params: EditMessageInput) -> WriteMessageResult:
        previous = await self.message(params.chat_id, params.message_id)
        if (
            previous is None
            or not previous.outgoing
            or previous.service_action
            or previous.media_type
        ):
            raise ValueError("Only your own outgoing plain-text messages can be edited.")
        item = previous.model_copy(update={"text": params.text, "edited_at": datetime.now(UTC)})
        self.data[self.data.index(previous)] = item
        return WriteMessageResult(
            operation="edit_message",
            chat_id=params.chat_id,
            message=item,
            source=self.source,
        )

    async def delete_messages(self, params: DeleteMessagesInput) -> DeleteMessagesResult:
        previous = [
            await self.message(params.chat_id, message_id) for message_id in params.message_ids
        ]
        if any(m is None or not m.outgoing or m.service_action for m in previous):
            raise ValueError("Only your own outgoing non-service messages can be deleted.")
        self.data = [
            m for m in self.data if not (m.chat_id == params.chat_id and m.id in params.message_ids)
        ]
        return DeleteMessagesResult(
            chat_id=params.chat_id,
            requested_message_ids=params.message_ids,
            revoke=params.revoke,
            source=self.source,
        )
