from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from telethon import errors

from .backend import Backend
from .config import Settings
from .guard import ReadOnlyViolation, require_write_chat
from .models import (
    AcrossInput,
    BetweenInput,
    DeleteMessagesInput,
    DeleteMessagesResult,
    Dialog,
    DialogsInput,
    EditMessageInput,
    HistoryInput,
    MessageInput,
    MessageResult,
    Page,
    SearchInput,
    SendMessageInput,
    WriteMessageResult,
)

READ_TOOLS = frozenset(
    {
        "list_dialogs",
        "get_chat_history",
        "get_message",
        "search_messages",
        "get_unread_messages",
        "get_latest_messages",
        "messages_between",
    }
)
WRITE_INPUTS = {
    "send_message": SendMessageInput,
    "edit_message": EditMessageInput,
    "delete_messages": DeleteMessagesInput,
}
WRITE_TOOLS = frozenset(WRITE_INPUTS)


class ReadService:
    def __init__(self, backend: Backend, settings: Settings):
        self.backend = backend
        self.settings = settings
        self.lock = asyncio.Lock()
        self.cursor_key = secrets.token_bytes(32)
        self.opened = False

    def allowed(self, chat_id: int) -> bool:
        return chat_id not in self.settings.deny_ids and (
            self.settings.allow_ids is None or chat_id in self.settings.allow_ids
        )

    def require_chat(self, chat_id: int) -> None:
        if not self.allowed(chat_id):
            raise ReadOnlyViolation("Chat is denied by the local read ACL.")

    async def dialogs(self) -> list[Dialog]:
        return sorted(
            (d for d in await self.backend.dialogs() if self.allowed(d.id)), key=lambda d: d.id
        )

    async def require_dialog(self, chat_id: int) -> Dialog:
        self.require_chat(chat_id)  # Reject before fetching anything from Telegram.
        return next((d for d in await self.dialogs() if d.id == chat_id), None) or self._missing()

    @staticmethod
    def _missing() -> Any:
        raise ValueError("Chat is not in the current dialog list; use list_dialogs first.")

    def _binding(self, operation: str, params: Any) -> str:
        config = params.model_dump(mode="json", exclude={"cursor", "limit"})
        config["operation"] = operation
        config["allow"] = (
            sorted(self.settings.allow_ids) if self.settings.allow_ids is not None else "*"
        )
        config["deny"] = sorted(self.settings.deny_ids)
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()

    def _encode(self, binding: str, state: dict[str, int]) -> str:
        body = json.dumps({"binding": binding, "state": state}, separators=(",", ":")).encode()
        signature = hmac.digest(self.cursor_key, body, "sha256")
        return base64.urlsafe_b64encode(signature + body).decode()

    def _decode(self, token: str | None, binding: str) -> dict[str, int]:
        if not token:
            return {}
        try:
            raw = base64.b64decode(token, altchars=b"-_", validate=True)
            signature, body = raw[:32], raw[32:]
            if not hmac.compare_digest(signature, hmac.digest(self.cursor_key, body, "sha256")):
                raise ValueError
            data = json.loads(body)
            if data["binding"] != binding:
                raise ValueError
            state = data["state"]
            if not isinstance(state, dict) or not all(type(v) is int for v in state.values()):
                raise ValueError
            return state
        except (ValueError, KeyError, TypeError):
            raise ValueError(
                "Invalid/expired cursor or changed query/ACL. Restart without cursor."
            ) from None

    def _page(self, items: list[Any], *, order: str, **kwargs: Any) -> Page:
        return Page(
            items=items,
            fetched_at=datetime.now(UTC),
            source=self.backend.source,
            order=order,
            **kwargs,
        )

    async def execute(self, operation: str, params: Any) -> Any:
        writing = operation in WRITE_TOOLS
        if writing:
            if not self.settings.write_enabled:
                raise ReadOnlyViolation("Write tools are disabled by local configuration.")
            expected = WRITE_INPUTS[operation]
            if type(params) is not expected:
                raise ValueError("Use the exact input model for the requested write tool.")
            # Revalidate even a constructed/copied Python model before side effects.
            params = expected.model_validate(params.model_dump(warnings=False))
            require_write_chat(self.settings, params.chat_id)
        elif operation not in READ_TOOLS:
            raise ReadOnlyViolation("Only the seven fixed read tools are allowed.")
        try:
            async with asyncio.timeout(self.settings.timeout_seconds), self.lock:
                chat_id = getattr(params, "chat_id", None)
                if chat_id is not None:
                    self.require_chat(chat_id)
                if not self.opened:
                    await self.backend.open()
                    self.opened = True
                return await getattr(self, operation)(params)
        except errors.FloodWaitError as exc:
            raise ValueError(f"Telegram rate limit. Retry after {exc.seconds} seconds.") from None
        except (errors.UnauthorizedError, errors.AuthKeyError):
            raise ValueError(
                "Telegram session expired/revoked. Run 'auth' in your terminal."
            ) from None
        except (errors.ServerError, errors.TimedOutError):
            raise ValueError(
                "Write outcome is unknown after a Telegram server error; it may have completed. "
                "Read the targeted chat before retrying."
                if writing
                else "Telegram could not complete the read request. Retry this page later."
            ) from None
        except errors.RPCError:
            raise ValueError(
                "Telegram rejected the write request. Check message ownership and chat permissions."
                if writing
                else "Telegram rejected the read request. Check access and retry later."
            ) from None
        except (ReadOnlyViolation, ValueError):
            raise
        except (OSError, TimeoutError):
            raise ValueError(
                "Write outcome is unknown; it may have completed. "
                "Read the targeted chat before retrying."
                if writing
                else "Read timed out or connection failed. Retry this page later."
            ) from None
        except Exception:
            raise ValueError(
                "Write outcome could not be confirmed. Inspect the targeted chat before retrying."
                if writing
                else "Read failed safely; no Telegram write operation was performed."
            ) from None

    async def _write_dialog(self, chat_id: int) -> Dialog:
        require_write_chat(self.settings, chat_id)
        return await self.require_dialog(chat_id)

    async def _write_message(self, chat_id: int, message_id: int, *, own: bool) -> Any:
        message = await self.backend.message(chat_id, message_id)
        if message is None or message.chat_id != chat_id or message.id != message_id:
            raise ValueError("Message does not exist in the specified chat.")
        if own and (not message.outgoing or message.service_action):
            raise ReadOnlyViolation("Only your own outgoing non-service messages can be changed.")
        return message

    async def send_message(self, params: SendMessageInput) -> WriteMessageResult:
        params = SendMessageInput.model_validate(params.model_dump(warnings=False))
        await self._write_dialog(params.chat_id)
        if params.reply_to_message_id is not None:
            await self._write_message(params.chat_id, params.reply_to_message_id, own=False)
        return await self.backend.send_message(params)

    async def edit_message(self, params: EditMessageInput) -> WriteMessageResult:
        params = EditMessageInput.model_validate(params.model_dump(warnings=False))
        await self._write_dialog(params.chat_id)
        previous = await self._write_message(params.chat_id, params.message_id, own=True)
        if previous.media_type:
            raise ValueError("Only plain-text messages can be edited through this tool.")
        return await self.backend.edit_message(params)

    async def delete_messages(self, params: DeleteMessagesInput) -> DeleteMessagesResult:
        params = DeleteMessagesInput.model_validate(params.model_dump(warnings=False))
        await self._write_dialog(params.chat_id)
        if params.chat_id <= -1000000000000 and not params.revoke:
            raise ValueError("Channels/megagroups always delete for everyone; use revoke=true.")
        for message_id in params.message_ids:
            await self._write_message(params.chat_id, message_id, own=True)
        return await self.backend.delete_messages(params)

    async def list_dialogs(self, params: DialogsInput) -> Page:
        binding = self._binding("list_dialogs", params)
        state = self._decode(params.cursor, binding)
        records = [
            d
            for d in await self.dialogs()
            if (not params.query or params.query.casefold() in d.title.casefold())
            and ("last_id" not in state or d.id > state["last_id"])
        ]
        items = records[: params.limit]
        more = len(records) > params.limit
        return self._page(
            items,
            order="chat_id ascending",
            has_more=more,
            next_cursor=self._encode(binding, {"last_id": items[-1].id}) if more else None,
        )

    async def get_chat_history(self, params: HistoryInput) -> Page:
        await self.require_dialog(params.chat_id)
        records = await self.backend.messages(
            params.chat_id, limit=params.limit + 1, before_id=params.before_id
        )
        items = records[: params.limit]
        more = len(records) > params.limit
        return self._page(
            items,
            order="newest first in chat",
            has_more=more,
            next_before_id=items[-1].id if more else None,
        )

    async def get_message(self, params: MessageInput) -> MessageResult:
        await self.require_dialog(params.chat_id)
        message = await self.backend.message(params.chat_id, params.message_id)
        return MessageResult(message=message, source=self.backend.source)

    async def messages_between(self, params: BetweenInput) -> Page:
        if params.start >= params.end:
            raise ValueError("start must precede end; interval is [start, end).")
        await self.require_dialog(params.chat_id)
        records = await self.backend.messages(
            params.chat_id,
            limit=params.limit + 1,
            before_id=params.before_id,
            start=params.start,
            end=params.end,
        )
        items = records[: params.limit]
        more = len(records) > params.limit
        return self._page(
            items,
            order="newest first in chat; start inclusive, end exclusive",
            has_more=more,
            next_before_id=items[-1].id if more else None,
        )

    async def search_messages(self, params: SearchInput) -> Page:
        return await self._walk("search_messages", params)

    async def get_latest_messages(self, params: AcrossInput) -> Page:
        return await self._walk("get_latest_messages", params)

    async def get_unread_messages(self, params: AcrossInput) -> Page:
        return await self._walk("get_unread_messages", params)

    async def _walk(self, operation: str, params: SearchInput | AcrossInput) -> Page:
        binding = self._binding(operation, params)
        state = self._decode(params.cursor, binding)
        if params.chat_id is not None:
            chats = [await self.require_dialog(params.chat_id)]
        else:
            chats = await self.dialogs()
        if operation == "get_unread_messages":
            chats = [d for d in chats if d.unread_count > 0]
        if "chat_id" in state:
            chats = [d for d in chats if d.id >= state["chat_id"]]
        items = []
        continuation = None
        scanned = 0
        for index, dialog in enumerate(chats):
            if scanned >= self.settings.scan_chats or len(items) >= params.limit:
                continuation = {"chat_id": dialog.id, "before_id": 0, "taken": 0}
                break
            scanned += 1
            same_chat = state.get("chat_id") == dialog.id
            before = state.get("before_id", 0) if same_chat else 0
            taken = state.get("taken", 0) if same_chat else 0
            latest = operation == "get_latest_messages"
            budget = params.limit - len(items)
            if latest:
                budget = min(budget, params.per_chat_limit - taken)
            unread = operation == "get_unread_messages"
            records = await self.backend.messages(
                dialog.id,
                limit=budget + 1,
                before_id=before,
                min_id=dialog.read_inbox_max_id if unread else 0,
                query=params.query if isinstance(params, SearchInput) else None,
            )
            consumed = records[:budget]
            items.extend(m for m in consumed if not unread or not m.outgoing)
            more_in_chat = len(records) > budget and (
                not latest or taken + len(consumed) < params.per_chat_limit
            )
            if more_in_chat:
                continuation = {
                    "chat_id": dialog.id,
                    "before_id": consumed[-1].id,
                    "taken": taken + len(consumed),
                }
                break
            if len(items) >= params.limit and index + 1 < len(chats):
                continuation = {"chat_id": chats[index + 1].id, "before_id": 0, "taken": 0}
                break
        more = continuation is not None
        return self._page(
            items,
            order="chat_id ascending; newest first within each chat",
            has_more=more,
            next_cursor=self._encode(binding, continuation) if more else None,
            scan_limited=scanned >= self.settings.scan_chats and more,
            scope="incoming above read_inbox_max_id"
            if operation == "get_unread_messages"
            else "allowed dialogs",
        )
