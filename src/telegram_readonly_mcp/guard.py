from __future__ import annotations

from typing import Any

from telethon import TelegramClient, functions

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


class ReadOnlyViolation(PermissionError):
    pass


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
    def __init__(self, *args: Any, authentication: bool = False, **kwargs: Any):
        kwargs.update(
            receive_updates=False,
            catch_up=False,
            flood_sleep_threshold=0,
            request_retries=1,
            connection_retries=2,
            raise_last_call_error=True,
        )
        super().__init__(*args, **kwargs)
        self._authentication_mode = authentication
        original_send = self._sender.send

        def guarded_send(request: Any, ordered: bool = False) -> Any:
            assert_read_request(request, authentication=self._authentication_mode)
            return original_send(request, ordered=ordered)

        # connect() sends directly through _sender, bypassing _call(). Guard both boundaries.
        self._sender.send = guarded_send

    async def _call(
        self,
        sender: Any,
        request: Any,
        ordered: bool = False,
        flood_sleep_threshold: int | None = None,
    ) -> Any:
        assert_read_request(request, authentication=self._authentication_mode)
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
