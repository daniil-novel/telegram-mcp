"""Configured login credentials and session reuse, without any Telegram network traffic."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError
from telethon import errors
from telethon.crypto import AuthKey
from telethon.sessions import StringSession

from telegram_readonly_mcp import cli
from telegram_readonly_mcp.config import Settings, load_settings
from telegram_readonly_mcp.exceptions import PublicError
from telegram_readonly_mcp.security import SessionStore


def synthetic_session():
    # A structurally valid, fictional session exercises real serialization and protected storage.
    session = StringSession()
    session.set_dc(2, "149.154.167.50", 443)
    session.auth_key = AuthKey(b"\x02" * 256)
    return session


@pytest.fixture
def login(monkeypatch, tmp_path):
    state = SimpleNamespace(
        authorized=False,
        twofa=False,
        reject_password=False,
        phone="10000000000",
        prompts=[],
        inputs=[],
        codes=[],
        sign_ins=[],
        disconnected=False,
        loaded=None,
    )
    settings = Settings(api_id=1, api_hash=SecretStr("a" * 32), session_dir=tmp_path / "session")

    class OfflineClient:
        # Fake only the Telegram boundary; settings and session protection remain real.
        def __init__(self, session, *_args, **_kwargs):
            state.loaded = session.save()
            self.session = session

        async def connect(self):
            self.session = synthetic_session()

        async def disconnect(self):
            state.disconnected = True

        async def is_user_authorized(self):
            return state.authorized

        async def send_code_request(self, phone):
            state.codes.append(phone)

        async def sign_in(self, **kwargs):
            state.sign_ins.append(kwargs)
            if "code" in kwargs and state.twofa:
                raise errors.SessionPasswordNeededError(request=None)
            if "password" in kwargs and state.reject_password:
                raise errors.PasswordHashInvalidError(request=None)
            state.authorized = True

        async def get_me(self):
            return SimpleNamespace(bot=False, phone=state.phone)

    def hidden(prompt):
        state.prompts.append(prompt)
        assert state.inputs, "Unexpected interactive prompt"
        return state.inputs.pop(0)

    monkeypatch.setattr(cli, "GuardedTelegramClient", OfflineClient)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.getpass, "getpass", hidden)
    return state, settings


@pytest.mark.parametrize("twofa", [False, True])
@pytest.mark.parametrize("stored", [False, True])
async def test_configured_credentials_prompt_only_for_one_time_code(login, twofa, stored, capsys):
    state, settings = login
    if stored:
        # Reauthorization of a rejected saved session follows the same one-code flow.
        SessionStore(settings.session_dir).save(synthetic_session().save())
    password = "  literal-${UNCHANGED}-password  "
    state.twofa = twofa
    state.inputs = [" 12345 "]
    settings = settings.model_copy(
        update={
            "phone": SecretStr("+10000000000"),
            "twofa_password": SecretStr(password),
        }
    )
    await cli.authorize(settings)
    assert state.codes == ["+10000000000"]
    assert len(state.prompts) == 1 and "login code" in state.prompts[0]
    assert state.sign_ins[0] == {"phone": "+10000000000", "code": "12345"}
    assert state.sign_ins[1:] == ([{"password": password}] if twofa else [])
    assert state.disconnected and SessionStore(settings.session_dir).load()
    output = capsys.readouterr()
    for secret in (password, "12345", "+10000000000"):
        assert secret not in output.out + output.err


@pytest.mark.parametrize("configured_phone", [False, True])
async def test_authorized_stored_session_needs_no_terminal_or_prompts(
    login,
    monkeypatch,
    configured_phone,
    capsys,
):
    state, settings = login
    session = synthetic_session().save()
    SessionStore(settings.session_dir).save(session)
    state.authorized = True
    if configured_phone:
        settings = settings.model_copy(update={"phone": SecretStr("+1 (000) 000-0000")})
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    await cli.authorize(settings)
    assert state.loaded == session
    assert state.prompts == state.codes == state.sign_ins == []
    assert state.disconnected
    output = capsys.readouterr()
    assert output.out == "Authorized. Session stored locally; no messages were read or changed.\n"
    assert not output.err


@pytest.mark.parametrize("stored", [False, True])
async def test_first_or_revoked_session_cannot_request_code_without_terminal(
    login,
    monkeypatch,
    stored,
):
    state, settings = login
    if stored:
        SessionStore(settings.session_dir).save(synthetic_session().save())
    settings = settings.model_copy(
        update={
            "phone": SecretStr("+10000000000"),
            "twofa_password": SecretStr("synthetic-password"),
        }
    )
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    with pytest.raises(PublicError, match="interactive terminal"):
        await cli.authorize(settings)
    assert state.prompts == state.codes == state.sign_ins == []
    assert state.disconnected


async def test_configured_bad_password_fails_once_without_prompt_or_secret_output(login, capsys):
    state, settings = login
    state.twofa = state.reject_password = True
    state.inputs = ["12345"]
    password = "synthetic-rejected-password"
    settings = settings.model_copy(
        update={
            "phone": SecretStr("+10000000000"),
            "twofa_password": SecretStr(password),
        }
    )
    with pytest.raises(PublicError, match="Correct or remove") as caught:
        await cli.authorize(settings)
    assert state.sign_ins == [
        {"phone": "+10000000000", "code": "12345"},
        {"password": password},
    ]
    assert len(state.prompts) == 1 and state.disconnected
    assert not SessionStore(settings.session_dir).path.exists()
    output = capsys.readouterr()
    assert password not in str(caught.value) + output.out + output.err


async def test_missing_2fa_password_has_bounded_hidden_retries(login):
    state, settings = login
    state.twofa = state.reject_password = True
    state.inputs = ["12345", "wrong-one", "wrong-two", "wrong-three"]
    settings = settings.model_copy(update={"phone": SecretStr("+10000000000")})
    with pytest.raises(PublicError, match="Invalid 2FA password"):
        await cli.authorize(settings)
    assert len([call for call in state.sign_ins if "password" in call]) == 3
    assert len([prompt for prompt in state.prompts if "2FA password" in prompt]) == 3
    assert state.disconnected


async def test_mismatched_configured_phone_preserves_existing_session(login, monkeypatch, capsys):
    state, settings = login
    state.authorized = True
    store = SessionStore(settings.session_dir)
    store.save(synthetic_session().save())
    before = store.path.read_bytes()
    settings = settings.model_copy(update={"phone": SecretStr("+19999999999")})
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    with pytest.raises(PublicError, match="does not match TELEGRAM_PHONE") as caught:
        await cli.authorize(settings)
    assert store.path.read_bytes() == before
    assert state.prompts == state.codes == state.sign_ins == []
    assert state.disconnected
    output = capsys.readouterr()
    for phone in ("10000000000", "19999999999"):
        assert phone not in str(caught.value) + output.out + output.err


async def test_one_time_code_environment_is_ignored(login, monkeypatch):
    state, settings = login
    state.inputs = ["12345"]
    settings = settings.model_copy(update={"phone": SecretStr("+10000000000")})
    monkeypatch.setenv("TELEGRAM_LOGIN_CODE", "never-use-this-code")
    monkeypatch.setenv("TELEGRAM_CODE", "never-use-this-code")
    await cli.authorize(settings)
    assert state.sign_ins == [{"phone": "+10000000000", "code": "12345"}]
    assert len(state.prompts) == 1


def test_dotenv_bom_literal_password_and_secret_redaction(tmp_path, monkeypatch):
    for name in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE", "TELEGRAM_2FA_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PASSWORD_PART", "must-not-be-expanded")
    env = tmp_path / "login.env"
    # Single quotes preserve meaningful leading/trailing spaces; BOM must not hide the first key.
    env.write_text(
        "TELEGRAM_API_ID=1\nTELEGRAM_API_HASH=" + "a" * 32 + "\nTELEGRAM_PHONE=+10000000000\n"
        "TELEGRAM_2FA_PASSWORD='  ${PASSWORD_PART}-literal  '\n",
        encoding="utf-8-sig",
    )
    settings = load_settings(env)
    assert settings.api_id == 1
    assert settings.phone.get_secret_value() == "+10000000000"
    assert settings.twofa_password.get_secret_value() == "  ${PASSWORD_PART}-literal  "
    for secret in ("+10000000000", "${PASSWORD_PART}-literal", "a" * 32):
        assert secret not in repr(settings) + settings.model_dump_json()
    # Environment values keep their existing precedence, including deliberate empty overrides.
    monkeypatch.setenv("TELEGRAM_PHONE", "+19999999999")
    monkeypatch.setenv("TELEGRAM_2FA_PASSWORD", "")
    overridden = load_settings(env)
    assert overridden.phone.get_secret_value() == "+19999999999"
    assert overridden.twofa_password.get_secret_value() == ""


@pytest.mark.parametrize("field", ["phone", "twofa_password"])
def test_invalid_secret_types_do_not_expose_inputs_in_validation_messages(tmp_path, field):
    secret = "synthetic-validation-secret"
    with pytest.raises(ValidationError) as caught:
        Settings(session_dir=tmp_path, **{field: [secret]})
    assert secret not in str(caught.value) + repr(caught.value)
