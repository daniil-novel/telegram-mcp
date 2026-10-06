from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    api_id: int = Field(default=0, ge=0)
    api_hash: SecretStr = SecretStr("")
    session_dir: Path
    allow_ids: frozenset[int] | None = None
    deny_ids: frozenset[int] = frozenset()
    write_enabled: StrictBool = False
    write_allow_ids: frozenset[int] = frozenset()
    http_token: SecretStr = SecretStr("")
    allowed_hosts: tuple[str, ...] = ("127.0.0.1:8765", "localhost:8765")
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:8765", "http://localhost:8765")
    timeout_seconds: int = 45
    scan_chats: int = 20

    @field_validator("write_allow_ids", mode="before")
    @classmethod
    def exact_write_ids(cls, value: object) -> object:
        if not isinstance(value, (set, frozenset, list, tuple)) or any(
            type(item) is not int or item == 0 or not -(2**63) < item < 2**63 for item in value
        ):
            raise ValueError("Write ACL must contain exact nonzero numeric chat IDs.")
        return value

    def require_credentials(self) -> None:
        if not self.api_id or not re.fullmatch(
            r"[0-9a-fA-F]{32}", self.api_hash.get_secret_value()
        ):
            raise ValueError("Fill TELEGRAM_API_ID and TELEGRAM_API_HASH in your local .env first.")


def _ids(value: str, *, allow_wildcard: bool = False) -> frozenset[int] | None:
    if value.strip() == "*" and allow_wildcard:
        return None
    try:
        result = frozenset(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError:
        raise ValueError(
            "ACL must contain marked numeric chat IDs or '*' for allowed IDs."
        ) from None
    if 0 in result:
        raise ValueError("Chat ID 0 is invalid.")
    return result


def _write_ids(value: str) -> frozenset[int]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if any(not re.fullmatch(r"-?[1-9][0-9]*", item) for item in items):
        raise ValueError(
            "TELEGRAM_WRITE_ALLOWED_CHAT_IDS needs exact numeric IDs; '*' is forbidden."
        )
    result = frozenset(int(item) for item in items)
    if any(not -(2**63) < item < 2**63 for item in result):
        raise ValueError("Write chat IDs must fit in a signed 64-bit integer.")
    return result


def _write_enabled(value: str) -> bool:
    if value.strip().lower() not in {"true", "false"}:
        raise ValueError("TELEGRAM_WRITE_ENABLED must be true or false.")
    return value.strip().lower() == "true"


def load_settings(env_file: Path | None = None) -> Settings:
    # Explicit file, no upward .env discovery. Real environment takes precedence.
    values = {**dotenv_values(env_file or Path.cwd() / ".env"), **os.environ}

    def value(key: str, default: str = "") -> str:
        return str(values.get(key) or default)

    base = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        / "TelegramReadOnlyMCP"
        if os.name == "nt"
        else Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
        / "telegram-readonly-mcp"
    )
    # Empty allowed list is deny-all; only absence defaults to '*'.
    allowed = values.get("TELEGRAM_ALLOWED_CHAT_IDS", "*")
    try:
        api_id = int(value("TELEGRAM_API_ID", "0"))
    except ValueError:
        raise ValueError("TELEGRAM_API_ID must be an integer.") from None
    hosts = tuple(
        x.strip() for x in value("MCP_ALLOWED_HOSTS", "127.0.0.1:8765,localhost:8765").split(",")
    )
    origins = tuple(
        x.strip()
        for x in value("MCP_ALLOWED_ORIGINS", "http://127.0.0.1:8765,http://localhost:8765").split(
            ","
        )
    )
    if any(not item or "*" in item for item in (*hosts, *origins)):
        raise ValueError("HTTP hosts/origins must be explicit; wildcards are forbidden.")
    return Settings(
        api_id=api_id,
        api_hash=SecretStr(value("TELEGRAM_API_HASH")),
        session_dir=Path(value("TELEGRAM_SESSION_DIR", str(base))).expanduser().absolute(),
        allow_ids=_ids(str(allowed or ""), allow_wildcard=True),
        deny_ids=_ids(value("TELEGRAM_DENIED_CHAT_IDS")) or frozenset(),
        write_enabled=_write_enabled(value("TELEGRAM_WRITE_ENABLED", "false")),
        write_allow_ids=_write_ids(value("TELEGRAM_WRITE_ALLOWED_CHAT_IDS")),
        http_token=SecretStr(value("MCP_HTTP_TOKEN")),
        allowed_hosts=hosts,
        allowed_origins=origins,
    )
