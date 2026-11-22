from __future__ import annotations

import asyncio
from enum import IntEnum

from telethon import errors, functions
from telethon.sessions import StringSession

from . import __version__
from .config import Settings
from .guard import SESSION_REJECTED, GuardedTelegramClient
from .security import SessionBusy, SessionStore


class SessionStatus(IntEnum):
    AUTHORIZED = 0
    LOGIN_REQUIRED = 2
    BUSY = 3
    TEMPORARILY_UNAVAILABLE = 4


async def check_session(settings: Settings) -> SessionStatus:
    """Make one bounded authorization check with the existing key and no chat queries."""
    settings.require_credentials()
    store = SessionStore(settings.session_dir)
    try:
        with store.lock_connection():
            if not store.path.is_file():
                return SessionStatus.LOGIN_REQUIRED
            session = StringSession(store.load())
            if not session.auth_key:
                return SessionStatus.LOGIN_REQUIRED
            client = GuardedTelegramClient(
                session,
                settings.api_id,
                settings.api_hash.get_secret_value(),
                device_model="Unofficial Telegram MCP",
                app_version=__version__,
            )
            try:
                async with asyncio.timeout(20):
                    await client.connect()
                    await client(functions.updates.GetStateRequest())
                return SessionStatus.AUTHORIZED
            except SESSION_REJECTED:
                return SessionStatus.LOGIN_REQUIRED
            except (OSError, TimeoutError, errors.RPCError):
                return SessionStatus.TEMPORARILY_UNAVAILABLE
            finally:
                await client.disconnect()
    except SessionBusy:
        return SessionStatus.BUSY
