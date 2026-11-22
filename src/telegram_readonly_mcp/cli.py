from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import sys
import warnings
from pathlib import Path

from telethon import errors, functions, types, utils
from telethon.sessions import StringSession

from . import __version__
from .config import Settings, load_settings
from .exceptions import PublicError
from .guard import SESSION_REJECTED, GuardedTelegramClient, ReadOnlyViolation
from .qr_login import authorize_qr
from .security import SessionBusy, SessionStore, protect_path
from .server import create_http_app, create_server
from .session_health import SessionStatus, check_session


def _text(lang: str, en: str, ru: str) -> str:
    return ru if lang == "ru" else en


def hidden_input(prompt: str, *, strip: bool = True) -> str:
    # getpass can otherwise fall back to echoing secrets when no interactive TTY exists.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            value = getpass.getpass(prompt)
            return value.strip() if strip else value
        except getpass.GetPassWarning:
            raise PublicError(
                "Use an interactive terminal; secret input must not be echoed."
            ) from None


def required_hidden_input(prompt: str, *, strip: bool = True, lang: str = "en") -> str:
    for _ in range(3):
        value = hidden_input(prompt, strip=strip)
        if value:
            return value
        print(
            _text(
                lang,
                "Nothing entered. Input is hidden; type the value, then press Enter.",
                "Пустой ввод. Набери значение и нажми Enter. Символы скрыты.",
            ),
            file=sys.stderr,
        )
    raise PublicError(
        _text(
            lang,
            "No value entered. Restart auth in your terminal.",
            "Ничего не введено. Запусти вход снова.",
        )
    )


def _login_client(settings: Settings, session: StringSession) -> GuardedTelegramClient:
    return GuardedTelegramClient(
        session,
        settings.api_id,
        settings.api_hash.get_secret_value(),
        authentication=True,
        device_model="Unofficial Telegram MCP",
        app_version=__version__,
    )


def _select_method(lang: str) -> str:
    print(
        _text(
            lang,
            "1. Scan QR (recommended)\n2. Enter a login code\n0. Cancel",
            "1. Сканировать QR с телефона\n2. Войти по коду\n0. Отмена",
        )
    )
    while True:
        choice = input(_text(lang, "Choose [1]: ", "Выбери способ [1]: ")).strip()
        if choice in {"", "1"}:
            return "qr"
        if choice == "2":
            return "code"
        if choice == "0":
            raise KeyboardInterrupt
        print(_text(lang, "Enter 1, 2 or 0.", "Введи 1, 2 или 0."))


def _code_delivery(code_type: types.auth.TypeSentCodeType, lang: str) -> str:
    if isinstance(code_type, types.auth.SentCodeTypeApp):
        return _text(
            lang,
            "Telegram sent the code to the service chat named Telegram on a signed-in device.",
            "Код отправлен в служебный чат «Telegram» на устройстве, где ты уже вошёл.",
        )
    if isinstance(code_type, types.auth.SentCodeTypeEmailCode):
        return _text(
            lang,
            "Telegram sent the code to your login email.",
            "Код отправлен на электронную почту, привязанную для входа.",
        )
    if isinstance(
        code_type,
        (
            types.auth.SentCodeTypeSms,
            types.auth.SentCodeTypeSmsWord,
            types.auth.SentCodeTypeSmsPhrase,
        ),
    ):
        return _text(
            lang,
            "Telegram sent an SMS to the login number.",
            "Telegram отправил SMS на номер для входа.",
        )
    if isinstance(code_type, types.auth.SentCodeTypeCall):
        return _text(
            lang, "Telegram will call and read out the code.", "Telegram позвонит и продиктует код."
        )
    raise PublicError(
        _text(
            lang,
            "Telegram chose a delivery method this terminal cannot handle. Use QR.",
            "Telegram выбрал способ доставки, недоступный здесь. Войди по QR.",
        )
    )


async def _authorize_code(client: GuardedTelegramClient, phone: str, lang: str) -> None:
    if phone:
        print(_text(lang, "Using your saved login number.", "Использую сохранённый номер."))
    else:
        for _ in range(3):
            entered = required_hidden_input(
                _text(
                    lang,
                    "Phone with country code (hidden): ",
                    "Номер Telegram с кодом страны, начиная с + (ввод скрыт): ",
                ),
                lang=lang,
            )
            cleaned = utils.parse_phone(entered)
            if entered.startswith("+") and cleaned and 7 <= len(cleaned) <= 15:
                phone = "+" + cleaned
                break
            print(
                _text(
                    lang,
                    "Use the international format, starting with +.",
                    "Укажи номер в международном формате, начиная с +.",
                )
            )
        else:
            raise PublicError(_text(lang, "Invalid phone number.", "Некорректный номер телефона."))
    async with asyncio.timeout(20):
        sent = await client.send_code_request(phone)
    print(_code_delivery(sent.type, lang), flush=True)
    print(
        _text(
            lang,
            "The input is hidden. If no code arrives, press Ctrl+C and choose QR.",
            "При вводе символы не появятся. Если кода нет, нажми Ctrl+C и выбери вход по QR.",
        )
    )
    for attempt in range(3):
        code = required_hidden_input(
            _text(lang, "Telegram login code (hidden): ", "Код входа от Telegram (ввод скрыт): "),
            lang=lang,
        )
        try:
            async with asyncio.timeout(20):
                if isinstance(sent.type, types.auth.SentCodeTypeEmailCode):
                    result = await client(
                        functions.auth.SignInRequest(
                            phone,
                            sent.phone_code_hash,
                            email_verification=types.EmailVerificationCode(code),
                        )
                    )
                    if not isinstance(result, types.auth.Authorization):
                        raise PublicError(
                            _text(
                                lang,
                                "An existing Telegram account is required.",
                                "Для входа нужен существующий аккаунт Telegram.",
                            )
                        )
                    await client._on_login(result.user)
                else:
                    await client.sign_in(phone=phone, code=code)
            return
        except (errors.PhoneCodeInvalidError, errors.CodeInvalidError):
            if attempt == 2:
                raise PublicError(
                    _text(
                        lang,
                        "Invalid login code. Run auth again.",
                        "Неверный код. Запусти вход снова.",
                    )
                ) from None
            print(_text(lang, "Invalid code; try again.", "Неверный код. Попробуй ещё раз."))


async def _authorize_password(client: GuardedTelegramClient, settings: Settings, lang: str) -> None:
    configured = settings.twofa_password.get_secret_value()
    if not configured:
        print(
            _text(
                lang,
                "Telegram now requires your two-step verification password.",
                "Telegram просит пароль двухэтапной аутентификации, который ты настроил.",
            )
        )
    for attempt in range(3):
        password = configured or required_hidden_input(
            _text(lang, "Telegram 2FA password (hidden): ", "Пароль 2FA Telegram (ввод скрыт): "),
            strip=False,
            lang=lang,
        )
        try:
            async with asyncio.timeout(20):
                await client.sign_in(password=password)
            return
        except errors.PasswordHashInvalidError:
            if configured:
                raise PublicError(
                    _text(
                        lang,
                        "Configured TELEGRAM_2FA_PASSWORD was rejected. Correct or remove it.",
                        "Telegram отклонил пароль из TELEGRAM_2FA_PASSWORD. Исправь или убери его.",
                    )
                ) from None
            if attempt == 2:
                raise PublicError(
                    _text(
                        lang,
                        "Invalid 2FA password. Run auth again.",
                        "Неверный пароль 2FA. Запусти вход снова.",
                    )
                ) from None
            print(
                _text(
                    lang, "Invalid 2FA password; try again.", "Неверный пароль. Попробуй ещё раз."
                )
            )
        finally:
            del password


async def _save_login(
    client: GuardedTelegramClient,
    store: SessionStore,
    expected_phone: str | None,
    remember_phone: bool,
    lang: str,
    *,
    reused: bool = False,
) -> None:
    async with asyncio.timeout(20):
        me = await client.get_me()
    if me is None or me.bot:
        raise PublicError(
            _text(
                lang,
                "Authorization requires a personal account.",
                "Для входа нужен личный аккаунт Telegram.",
            )
        )
    account_phone = utils.parse_phone(getattr(me, "phone", None))
    if expected_phone and account_phone != expected_phone:
        raise PublicError(
            _text(
                lang,
                "The session does not match TELEGRAM_PHONE or the remembered number.",
                "Этот аккаунт не совпадает с сохранённым номером. Выбери нужный аккаунт.",
            )
        )
    if not reused:
        store.save(client.session.save())
    if remember_phone and account_phone and (not reused or not store.phone_path.exists()):
        store.save_phone("+" + account_phone)
    print(
        _text(
            lang,
            "Authorized. Session stored locally; no messages were read or changed.",
            "Сессия действует. Telegram MCP уже подключён."
            if reused
            else "Вход подтверждён. Сессия сохранена на этом компьютере.",
        )
    )


async def authorize(
    settings: Settings,
    *,
    remember_phone: bool = False,
    method: str = "code",
    lang: str = "en",
) -> None:
    settings.require_credentials()
    store = SessionStore(settings.session_dir)
    with store.lock_connection():
        phone = settings.phone.get_secret_value().strip()
        if not phone:
            phone = store.load_phone() or ""
        expected_phone = utils.parse_phone(phone) if phone else None
        if phone and expected_phone is None:
            raise PublicError(
                _text(
                    lang,
                    "TELEGRAM_PHONE must be a valid international number.",
                    "Проверь номер в TELEGRAM_PHONE. Нужен код страны.",
                )
            )
        if store.path.exists():
            client = _login_client(settings, StringSession(store.load()))
            try:
                try:
                    async with asyncio.timeout(20):
                        await client.connect()
                        valid = await client.is_user_authorized()
                except SESSION_REJECTED:
                    valid = False
                if valid:
                    await _save_login(
                        client, store, expected_phone, remember_phone, lang, reused=True
                    )
                    return
            finally:
                await client.disconnect()
        if not sys.stdin.isatty():
            raise PublicError(
                _text(
                    lang,
                    "Run auth yourself in an interactive terminal.",
                    "Открой «Войти в Telegram» в обычном окне PowerShell.",
                )
            )
        if method == "menu":
            method = _select_method(lang)
        client = _login_client(settings, StringSession())
        try:
            async with asyncio.timeout(20):
                await client.connect()
            try:
                if method == "qr":
                    await authorize_qr(client, lang)
                else:
                    await _authorize_code(client, phone, lang)
            except errors.SessionPasswordNeededError:
                await _authorize_password(client, settings, lang)
            await _save_login(client, store, expected_phone, remember_phone, lang)
        finally:
            await client.disconnect()


SESSION_MESSAGES = {
    SessionStatus.AUTHORIZED: (
        "Telegram confirmed the saved session.",
        "Telegram подтвердил. Сохранённая сессия действует.",
    ),
    SessionStatus.LOGIN_REQUIRED: (
        "Session missing or rejected. Open the local login launcher.",
        "Сессии нет или Telegram её отклонил. Открой «Войти в Telegram».",
    ),
    SessionStatus.BUSY: (
        "Another local Telegram request is using the session. Check skipped.",
        "Сессия занята другим запросом или входом. Проверка пропущена.",
    ),
    SessionStatus.TEMPORARILY_UNAVAILABLE: (
        "Telegram could not be reached or is rate-limiting.",
        "Telegram не ответил или ограничил запросы. Попробуй позже.",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Unofficial Telegram MCP; read-only by default")
    parser.add_argument("--version", action="version", version=f"telegram-mcp {__version__}")
    parser.add_argument("--env-file", type=Path, help="Explicit local .env path")
    sub = parser.add_subparsers(dest="action", required=True)
    auth = sub.add_parser("auth", help="Interactive user-only login; never an MCP tool")
    auth.add_argument(
        "--remember-phone",
        action="store_true",
        help="Save the verified account number locally for subsequent logins",
    )
    auth.add_argument("--method", choices=("code", "qr", "menu"), default="code")
    auth.add_argument("--lang", choices=("en", "ru"), default="en")
    check = sub.add_parser("session-check", help="Check a saved session without reading any chats")
    check.add_argument("--lang", choices=("en", "ru"), default="en")
    sub.add_parser("protect-env", help="Restrict .env file permissions to your account")
    serve = sub.add_parser("serve", help="Start MCP (write tools require explicit configuration)")
    serve.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    # Remote/Docker binding is explicit; default stays loopback with bearer/Host/Origin guards.
    serve.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")  # nosec B104
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--demo", action="store_true", help="Synthetic data only; no Telegram connection"
    )
    args = parser.parse_args()
    lang = getattr(args, "lang", "en")
    logging.basicConfig(stream=sys.stderr, level=logging.CRITICAL)
    try:
        if args.action == "protect-env":
            path = args.env_file or Path.cwd() / ".env"
            if not path.is_file():
                raise PublicError("Create your local .env from .env.example first.")
            protect_path(path)
            print("Local .env permissions restricted.")
            return
        settings = load_settings(args.env_file)
        if args.action == "auth":
            asyncio.run(
                authorize(
                    settings, remember_phone=args.remember_phone, method=args.method, lang=lang
                )
            )
            return
        if args.action == "session-check":
            status = asyncio.run(check_session(settings))
            print(_text(lang, *SESSION_MESSAGES[status]))
            raise SystemExit(status.value)
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
        print(
            _text(
                lang,
                f"Telegram rate limit. Retry after {exc.seconds} seconds.",
                f"Telegram ограничил вход. Повтори через {exc.seconds} сек.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (errors.PhoneCodeExpiredError, errors.EmailVerifyExpiredError):
        print(
            _text(
                lang,
                "The login code expired. Run auth again or choose QR.",
                "Код истёк. Открой «Войти в Telegram» снова или выбери вход по QR.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except errors.PhoneNumberFloodError:
        print(
            _text(
                lang,
                "Too many code requests. Use QR or wait before retrying.",
                "Слишком много запросов кода. Войди по QR или попробуй позже.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (errors.PhoneNumberInvalidError, errors.PhoneNumberBannedError):
        print(
            _text(
                lang,
                "Telegram rejected the phone number. Check it on a signed-in device.",
                "Telegram отклонил номер. Проверь его в своём приложении Telegram.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (errors.ApiIdInvalidError, errors.ApiIdPublishedFloodError):
        print(
            _text(
                lang,
                "Telegram rejected the app API credentials. Check your private config.",
                "Telegram отклонил API-данные приложения. Проверь локальный .env.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (OSError, TimeoutError, errors.ServerError, errors.TimedOutError):
        print(
            _text(
                lang,
                "Telegram did not respond. Check the network and try again.",
                "Telegram не ответил. Проверь подключение и попробуй ещё раз.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except errors.RPCError:
        print(
            _text(
                lang,
                "Telegram rejected this login step. Open the launcher and choose QR or code.",
                "Telegram отклонил шаг входа. Открой «Войти в Telegram» и выбери QR или код.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except SessionBusy:
        print(_text(lang, *SESSION_MESSAGES[SessionStatus.BUSY]), file=sys.stderr)
        raise SystemExit(SessionStatus.BUSY.value) from None
    except (PublicError, ReadOnlyViolation) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        print(
            _text(
                lang,
                "Startup failed. Check local configuration, permissions and connection.",
                "Не удалось запустить Telegram MCP. Проверь локальные настройки и подключение.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from None
