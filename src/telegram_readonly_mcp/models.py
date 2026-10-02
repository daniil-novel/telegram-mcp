from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Message(BaseModel):
    id: int
    chat_id: int
    date: datetime
    text: str
    sender_id: int | None = None
    outgoing: bool = False
    reply_to_id: int | None = None
    media_type: str | None = None
    service_action: str | None = None
    text_truncated: bool = False
    edited_at: datetime | None = None


class Dialog(BaseModel):
    id: int
    title: str
    kind: Literal["private", "group", "channel"]
    unread_count: int = 0
    read_inbox_max_id: int = 0
    archived: bool = False
    latest: Message | None = None


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PageInput(Input):
    limit: int = Field(default=50, ge=1, le=200, description="Maximum records on this page.")
    cursor: str | None = Field(
        default=None, max_length=4096, description="Opaque continuation from previous page."
    )


class DialogsInput(PageInput):
    query: str | None = Field(
        default=None, max_length=200, description="Case-insensitive title filter."
    )


class HistoryInput(Input):
    chat_id: int = Field(description="Marked numeric chat ID returned by list_dialogs.")
    limit: int = Field(default=50, ge=1, le=200)
    before_id: int = Field(
        default=0, ge=0, description="Exclusive older-than message ID; 0 starts at latest."
    )


class MessageInput(Input):
    chat_id: int
    message_id: int = Field(gt=0)


class SearchInput(PageInput):
    query: str = Field(min_length=1, max_length=256, description="Telegram text search query.")
    chat_id: int | None = Field(
        default=None, description="Omit to search across all allowed dialogs."
    )


class AcrossInput(PageInput):
    chat_id: int | None = Field(default=None, description="Omit to walk all allowed dialogs.")
    per_chat_limit: int = Field(
        default=10,
        ge=1,
        le=200,
        description="Recent messages per dialog for get_latest_messages only.",
    )


class BetweenInput(HistoryInput):
    start: datetime = Field(
        description="Inclusive ISO 8601 start with timezone, e.g. 2026-10-01T00:00:00+03:00."
    )
    end: datetime = Field(description="Exclusive ISO 8601 end with timezone.")

    @field_validator("start", "end")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("A timezone offset is required.")
        return value


class Page(BaseModel):
    items: list[Dialog] | list[Message]
    has_more: bool = False
    next_cursor: str | None = None
    next_before_id: int | None = None
    fetched_at: datetime
    source: Literal["telegram", "demo"]
    order: str
    scope: str = "allowed dialogs"
    scan_limited: bool = False
    content_is_untrusted: bool = True


class MessageResult(BaseModel):
    message: Message | None
    source: Literal["telegram", "demo"]
    content_is_untrusted: bool = True
