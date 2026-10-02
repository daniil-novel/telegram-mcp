"""Interactive login regressions with the real Telethon methods and fake RPCs."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr
from telethon import errors, functions, types
from telethon.client import auth as telethon_auth
from telethon.crypto import AuthKey
from telethon.network.mtprotosender import MTProtoSender

from telegram_readonly_mcp import cli
from telegram_readonly_mcp.config import Settings
from telegram_readonly_mcp.guard import GuardedTelegramClient, assert_read_request
from telegram_readonly_mcp.security import SessionStore


def test_blank_secret_reprompt_and_preserve_password_whitespace(monkeypatch, capsys):
    values = iter(["", "  synthetic password  "])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(values))
    assert cli.required_hidden_input("Password: ", strip=False) == "  synthetic password  "
    output = capsys.readouterr()
    assert "Nothing entered" in output.err
    assert "synthetic password" not in output.err


def test_blank_secret_never_passes_to_telethon(monkeypatch):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "")
    with pytest.raises(ValueError, match="No value entered"):
        cli.required_hidden_input("Password: ", strip=False)


@pytest.mark.parametrize("two_factor", [False, True])
async def test_real_login_flow_without_network(monkeypatch, tmp_path, capsys, two_factor):
    user = types.User(id=101, access_hash=11, first_name="Synthetic", bot=False)
    requests = []
    state = {"authorized": False, "password_attempts": 0, "disconnected": False}

    def fake_send(sender, request, ordered=False):
        assert_read_request(request, authentication=True)
        while isinstance(request, functions.InvokeWithoutUpdatesRequest):
            request = request.query
        requests.append(type(request))
        future = asyncio.get_running_loop().create_future()
        if isinstance(request, functions.updates.GetStateRequest):
            future.set_exception(errors.AuthKeyUnregisteredError(request))
        elif isinstance(request, functions.users.GetUsersRequest):
            if state["authorized"]:
                future.set_result([user])
            else:
                future.set_exception(errors.AuthKeyUnregisteredError(request))
        elif isinstance(request, functions.auth.SendCodeRequest):
            future.set_result(
                types.auth.SentCode(types.auth.SentCodeTypeApp(length=5), "synthetic-code-hash")
            )
        elif isinstance(request, functions.auth.SignInRequest):
            if two_factor:
                future.set_exception(errors.SessionPasswordNeededError(request))
            else:
                state["authorized"] = True
                future.set_result(types.auth.Authorization(user=user))
        elif isinstance(request, functions.account.GetPasswordRequest):
            future.set_result(types.PasswordKdfAlgoUnknown())
        elif isinstance(request, functions.auth.CheckPasswordRequest):
            state["password_attempts"] += 1
            if state["password_attempts"] == 1:
                future.set_exception(errors.PasswordHashInvalidError(request))
            else:
                state["authorized"] = True
                future.set_result(types.auth.Authorization(user=user))
        else:
            raise AssertionError("Login tried an unexpected RPC")
        return future

    class OfflineClient(GuardedTelegramClient):
        async def connect(self):
            self.session.set_dc(2, "149.154.167.50", 443)
            self.session.auth_key = AuthKey(b"\x01" * 256)

        async def disconnect(self):
            state["disconnected"] = True

    def fake_srp(password_info, password):
        assert password in ("synthetic-wrong-password", "  synthetic-correct-password  ")
        return types.InputCheckPasswordSRP(1, b"synthetic-a", b"synthetic-m1")

    values = [" +10000000000 ", " 12345 "]
    if two_factor:
        values.extend(["", "synthetic-wrong-password", "  synthetic-correct-password  "])
    inputs = iter(values)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(inputs))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(MTProtoSender, "send", fake_send)
    monkeypatch.setattr(telethon_auth.pwd_mod, "compute_check", fake_srp)
    monkeypatch.setattr(cli, "GuardedTelegramClient", OfflineClient)
    directory = tmp_path / "private-session"
    await cli.authorize(Settings(api_id=1, api_hash=SecretStr("a" * 32), session_dir=directory))
    assert state["authorized"] and state["disconnected"]
    assert state["password_attempts"] == (2 if two_factor else 0)
    assert SessionStore(directory).load()
    assert set(requests) <= {
        functions.updates.GetStateRequest,
        functions.users.GetUsersRequest,
        functions.auth.SendCodeRequest,
        functions.auth.SignInRequest,
        functions.account.GetPasswordRequest,
        functions.auth.CheckPasswordRequest,
    }
    output = capsys.readouterr()
    assert "Authorized" in output.out
    for secret in (
        "+10000000000",
        "12345",
        "synthetic-wrong-password",
        "synthetic-correct-password",
    ):
        assert secret not in output.out + output.err
