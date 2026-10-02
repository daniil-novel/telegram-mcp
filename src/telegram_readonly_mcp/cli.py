from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import sys
import warnings
from pathlib import Path

from telethon import errors
from telethon.sessions import StringSession

from .config import Settings, load_settings
from .guard import GuardedTelegramClient
from .security import SessionStore, protect_path
from .server import create_http_app, create_server


def hidden_input(prompt: str, *, strip: bool = True) -> str:
    # getpass can otherwise fall back to echoing secrets when no interactive TTY exists.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            value = getpass.getpass(prompt)
            return value.strip() if strip else value
        except getpass.GetPassWarning:
            raise ValueError(
                "Use an interactive terminal; secret input must not be echoed."
            ) from None


def required_hidden_input(prompt: str, *, strip: bool = True) -> str:
    for _ in range(3):
        value = hidden_input(prompt, strip=strip)
        if value:
            return value
        print(
            "Nothing entered. Input is hidden; type the value, then press Enter.", file=sys.stderr
        )
    raise ValueError("No value entered. Restart auth yourself in your terminal.")


async def authorize(settings: Settings) -> None:
    settings.require_credentials()
    if not sys.stdin.isatty():
        raise ValueError("Run auth yourself in an interactive terminal, not through an MCP tool.")
    store = SessionStore(settings.session_dir)
    session = StringSession(store.load()) if store.path.exists() else StringSession()
    client = GuardedTelegramClient(
        session,
        settings.api_id,
        settings.api_hash.get_secret_value(),
        authentication=True,
        device_model="Telegram Read-only MCP",
        app_version="0.1.0",
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            phone = required_hidden_input("Telegram phone (+country code, hidden): ")
            await client.send_code_request(phone)
            for attempt in range(3):
                code = required_hidden_input("Telegram login code (hidden): ")
                try:
                    await client.sign_in(phone=phone, code=code)
                    break
                except errors.PhoneCodeInvalidError:
                    if attempt == 2:
                        raise ValueError("Invalid login code. Restart auth yourself.") from None
                    print("Invalid code; try again.", file=sys.stderr)
                except errors.SessionPasswordNeededError:
                    for password_attempt in range(3):
                        password = required_hidden_input(
                            "Telegram 2FA password (hidden): ", strip=False
                        )
                        try:
                            await client.sign_in(password=password)
                            break
                        except errors.PasswordHashInvalidError:
                            if password_attempt == 2:
                                raise ValueError(
                                    "Invalid 2FA password. Restart auth yourself."
                                ) from None
                            print("Invalid 2FA password; try again.", file=sys.stderr)
                        finally:
                            password = None
                    break
        me = await client.get_me()
        if me is None or me.bot:
            raise ValueError("Authorization requires a personal account, not a bot.")
        store.save(client.session.save())
        print("Authorized. Session stored locally; no messages were read or changed.")
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded read-only Telegram MCP")
    parser.add_argument("--env-file", type=Path, help="Explicit local .env path")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("auth", help="Interactive user-only login; never an MCP tool")
    sub.add_parser("protect-env", help="Restrict .env file permissions to your account")
    serve = sub.add_parser("serve", help="Start the seven read-only MCP tools")
    serve.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    serve.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--demo", action="store_true", help="Synthetic data only; no Telegram connection"
    )
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, level=logging.CRITICAL)
    try:
        if args.action == "protect-env":
            path = args.env_file or Path.cwd() / ".env"
            if not path.is_file():
                raise ValueError("Create your local .env from .env.example first.")
            protect_path(path)
            print("Local .env permissions restricted.")
            return
        settings = load_settings(args.env_file)
        if args.action == "auth":
            asyncio.run(authorize(settings))
            return
        mcp, _ = create_server(settings, demo=args.demo)
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        else:
            import uvicorn

            app = create_http_app(mcp, settings.http_token.get_secret_value())
            uvicorn.run(app, host=args.host, port=args.port, access_log=False, log_level="critical")
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(130) from None
    except errors.FloodWaitError as exc:
        print(f"Authorization rate limit; retry after {exc.seconds} seconds.", file=sys.stderr)
        raise SystemExit(1) from None
    except errors.RPCError:
        print(
            "Telegram rejected authorization. Check your credentials/code/2FA locally.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (ValueError, PermissionError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print(
            "Startup failed. Check local configuration, permissions and connection.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
