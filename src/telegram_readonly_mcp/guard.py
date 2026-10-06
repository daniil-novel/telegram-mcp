from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from telethon import TelegramClient, functions, types, utils

from .config import Settings
from .models import DeleteMessagesInput, EditMessageInput, SendMessageInput

# Exact request classes: fail closed for unknown functions and subclasses.
READ_REQUESTS = frozenset(
    {
        functions.help.GetConfigRequest,
        functions.users.GetUsersRequest,
        functions.updates.GetStateRequest,
        functions.messages.GetDialogsRequest,
        functions.messages.GetHistoryRequest,
        functions.messages.GetMessagesRequest,
        functions.channels.GetMessagesRequest,
        functions.messages.SearchRequest,
    }
)
AUTH_REQUESTS = frozenset(
    {
        functions.auth.SendCodeRequest,
        functions.auth.ResendCodeRequest,
        functions.auth.SignInRequest,
        functions.auth.CheckPasswordRequest,
        functions.account.GetPasswordRequest,
    }
)
WRAPPERS = frozenset(
    {
        functions.InvokeWithLayerRequest,
        functions.InitConnectionRequest,
        functions.InvokeWithoutUpdatesRequest,
    }
)
WRITE_REQUESTS = frozenset(
    {
        functions.messages.SendMessageRequest,
        functions.messages.EditMessageRequest,
        functions.messages.DeleteMessagesRequest,
        functions.channels.DeleteMessagesRequest,
    }
)


class ReadOnlyViolation(PermissionError):
    pass


def require_write_chat(settings: Settings, chat_id: int) -> None:
    """Shared fail-closed policy, also applied before any backend/network work."""
    if type(chat_id) is not int or chat_id == 0 or not -(2**63) < chat_id < 2**63:
        raise ReadOnlyViolation("An exact nonzero numeric chat ID is required.")
    if not settings.write_enabled:
        raise ReadOnlyViolation("Writes are disabled; set TELEGRAM_WRITE_ENABLED=true locally.")
    if (
        chat_id not in settings.write_allow_ids
        or chat_id in settings.deny_ids
        or (settings.allow_ids is not None and chat_id not in settings.allow_ids)
    ):
        raise ReadOnlyViolation("Chat is denied by the local write/read ACL.")


@dataclass(frozen=True)
class _WriteAuthorization:
    request: Any
    snapshot: bytes
    chat_id: int
    task: asyncio.Task[Any] | None


def _validate_write_shape(request: Any, chat_id: int) -> None:
    """Allow only the exact plain-text requests constructed by our bounded backend."""
    if type(request) not in WRITE_REQUESTS:
        raise ReadOnlyViolation("MTProto operation is not on the fixed write allowlist.")
    if type(request) in {
        functions.messages.SendMessageRequest,
        functions.messages.EditMessageRequest,
    }:
        if (
            type(request.peer)
            not in {
                types.InputPeerUser,
                types.InputPeerChat,
                types.InputPeerChannel,
            }
            or utils.get_peer_id(request.peer) != chat_id
        ):
            raise ReadOnlyViolation("Write request peer does not match the approved chat ID.")
        if request.no_webpage is not True or request.entities not in (None, []):
            raise ReadOnlyViolation(
                "Writes require plain text without formatting or link previews."
            )
        # Reject media, markup, scheduling, impersonation, paid sends and future options.
        allowed = (
            {"peer", "message", "no_webpage", "silent", "reply_to", "random_id", "entities"}
            if type(request) is functions.messages.SendMessageRequest
            else {"peer", "id", "message", "no_webpage", "entities"}
        )
        if any(
            value is not None and value is not False
            for key, value in vars(request).items()
            if key not in allowed
        ):
            raise ReadOnlyViolation("Additional Telegram write options are disabled.")
        if type(request) is functions.messages.SendMessageRequest:
            reply = request.reply_to
            if reply is not None and (
                type(reply) is not types.InputReplyToMessage
                or any(
                    value is not None
                    for key, value in vars(reply).items()
                    if key != "reply_to_msg_id"
                )
            ):
                raise ReadOnlyViolation("Replies must target a message in the same approved chat.")
            SendMessageInput(
                chat_id=chat_id,
                text=request.message,
                silent=request.silent,
                reply_to_message_id=reply.reply_to_msg_id if reply else None,
            )
        else:
            EditMessageInput(chat_id=chat_id, message_id=request.id, text=request.message)
    else:
        if type(request) is functions.channels.DeleteMessagesRequest:
            if (
                type(request.channel) is not types.InputChannel
                or utils.get_peer_id(request.channel) != chat_id
            ):
                raise ReadOnlyViolation("Deletion channel does not match the approved chat ID.")
            revoke = True
        else:
            if chat_id <= -1000000000000:
                raise ReadOnlyViolation("Channel deletion requires the channel-specific request.")
            revoke = request.revoke
        DeleteMessagesInput(chat_id=chat_id, message_ids=request.id, revoke=revoke)


def assert_read_request(request: Any, *, authentication: bool = False, depth: int = 0) -> None:
    if depth > 8:
        raise ReadOnlyViolation("Too many MTProto request wrappers.")
    if isinstance(request, (list, tuple)):
        for item in request:
            assert_read_request(item, authentication=authentication, depth=depth + 1)
        return
    if type(request) in WRAPPERS:
        assert_read_request(request.query, authentication=authentication, depth=depth + 1)
        return
    if type(request) not in READ_REQUESTS and not (
        authentication and type(request) in AUTH_REQUESTS
    ):
        raise ReadOnlyViolation("MTProto operation is not on the read-only allowlist.")


class GuardedTelegramClient(TelegramClient):
    def __init__(
        self,
        *args: Any,
        authentication: bool = False,
        write_settings: Settings | None = None,
        **kwargs: Any,
    ):
        kwargs.update(
            receive_updates=False,
            catch_up=False,
            flood_sleep_threshold=0,
            request_retries=0 if write_settings and write_settings.write_enabled else 1,
            connection_retries=2,
            raise_last_call_error=True,
        )
        super().__init__(*args, **kwargs)
        self._authentication_mode = authentication
        self._write_settings = write_settings
        self._write_authorization: ContextVar[_WriteAuthorization | None] = ContextVar(
            "telegram_write_authorization", default=None
        )
        original_send = self._sender.send

        def guarded_send(request: Any, ordered: bool = False) -> Any:
            self._assert_request(request)
            return original_send(request, ordered=ordered)

        # connect() sends directly through _sender, bypassing _call(). Guard both boundaries.
        self._sender.send = guarded_send

    @contextmanager
    def authorize_write(self, request: Any, chat_id: int) -> Iterator[None]:
        """Approve one immutable request in the caller task, after backend ownership checks.

        This is an internal Python API, never an MCP tool or a raw-RPC endpoint.
        """
        if self._authentication_mode or self._write_settings is None:
            raise ReadOnlyViolation("This Telegram client does not permit writes.")
        require_write_chat(self._write_settings, chat_id)
        if self._write_authorization.get() is not None:
            raise ReadOnlyViolation("Nested write authorization is disabled.")
        _validate_write_shape(request, chat_id)
        approval = _WriteAuthorization(request, bytes(request), chat_id, asyncio.current_task())
        token = self._write_authorization.set(approval)
        try:
            yield
        finally:
            self._write_authorization.reset(token)

    def _assert_request(self, request: Any, *, depth: int = 0) -> None:
        if depth > 8:
            raise ReadOnlyViolation("Too many MTProto request wrappers.")
        if isinstance(request, (list, tuple)):
            for item in request:
                self._assert_request(item, depth=depth + 1)
            return
        if type(request) in WRAPPERS:
            self._assert_request(request.query, depth=depth + 1)
            return
        if type(request) not in WRITE_REQUESTS:
            assert_read_request(request, authentication=self._authentication_mode)
            return
        approval = self._write_authorization.get()
        if (
            approval is None
            or self._authentication_mode
            or self._write_settings is None
            or request is not approval.request
            or asyncio.current_task() is not approval.task
            or bytes(request) != approval.snapshot
        ):
            raise ReadOnlyViolation("Write RPC requires an exact backend-approved request.")
        require_write_chat(self._write_settings, approval.chat_id)
        _validate_write_shape(request, approval.chat_id)

    async def _call(
        self,
        sender: Any,
        request: Any,
        ordered: bool = False,
        flood_sleep_threshold: int | None = None,
    ) -> Any:
        self._assert_request(request)
        if sender is not self._sender:
            raise ReadOnlyViolation("Secondary/exported Telegram senders are disabled.")
        return await super()._call(sender, request, ordered, flood_sleep_threshold)

    async def _borrow_exported_sender(self, dc_id: int) -> Any:
        raise ReadOnlyViolation("Session export is disabled.")

    async def _on_login(self, user: Any) -> Any:
        # Telethon's default hook fetches update differences. Polling tools only
        # need self identity; do not start background account-history fetching.
        self._mb_entity_cache.set_self_user(user.id, user.bot, user.access_hash)
        self._authorized = True
        return user

    async def _update_loop(self) -> None:
        # The sender still handles MTProto acknowledgments and keepalives.
        # No update-difference requests or event handlers run in this client.
        await self.disconnected
