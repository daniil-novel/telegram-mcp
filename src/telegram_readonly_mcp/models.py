from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChatId = Annotated[int, Field(strict=True, gt=-(2**63), lt=2**63)]
MessageId = Annotated[int, Field(strict=True, gt=0, le=2**31 - 1)]


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
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, frozen=True, hide_input_in_errors=True
    )

    @field_validator("chat_id", check_fields=False)
    @classmethod
    def nonzero_chat_id(cls, value: int | None) -> int | None:
        if value == 0:
            raise ValueError("Chat ID 0 is invalid.")
        return value


class PageInput(Input):
    limit: int = Field(
        default=50, strict=True, ge=1, le=200, description="Maximum records on this page."
    )
    cursor: str | None = Field(
        default=None, max_length=4096, description="Opaque continuation from previous page."
    )


class DialogsInput(PageInput):
    query: str | None = Field(
        default=None, max_length=200, description="Case-insensitive title filter."
    )


class HistoryInput(Input):
    chat_id: ChatId = Field(description="Marked numeric chat ID returned by list_dialogs.")
    limit: int = Field(default=50, strict=True, ge=1, le=200)
    before_id: int = Field(
        default=0,
        strict=True,
        ge=0,
        le=2**31 - 1,
        description="Exclusive older-than message ID; 0 starts at latest.",
    )


class MessageInput(Input):
    chat_id: ChatId
    message_id: MessageId


class SearchInput(PageInput):
    query: str = Field(min_length=1, max_length=256, description="Telegram text search query.")
    chat_id: ChatId | None = Field(
        default=None, description="Omit to search across all allowed dialogs."
    )


class AcrossInput(PageInput):
    chat_id: ChatId | None = Field(default=None, description="Omit to walk all allowed dialogs.")
    per_chat_limit: int = Field(
        default=10,
        strict=True,
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


class WriteInput(BaseModel):
    # Literal text must retain leading/trailing whitespace. No coercion of IDs or booleans.
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    chat_id: ChatId

    @field_validator("chat_id")
    @classmethod
    def nonzero_chat_id(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Chat ID 0 is invalid.")
        return value


class TextWriteInput(WriteInput):
    text: str = Field(min_length=1, max_length=4096, description="Literal plain text; no markup.")

    @field_validator("text")
    @classmethod
    def telegram_text_limit(cls, value: str) -> str:
        if not value.strip() or len(value.encode("utf-16-le")) // 2 > 4096:
            raise ValueError("Text must be nonblank and at most 4096 UTF-16 code units.")
        return value


class SendMessageInput(TextWriteInput):
    reply_to_message_id: MessageId | None = None
    silent: bool = Field(default=True, description="Suppress the recipient notification sound.")


class EditMessageInput(TextWriteInput):
    message_id: MessageId


class DeleteMessagesInput(WriteInput):
    message_ids: list[MessageId] = Field(min_length=1, max_length=100)
    revoke: bool = Field(
        default=True, description="Delete for everyone; channel deletion always does."
    )

    @field_validator("message_ids")
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("Message IDs must be unique.")
        return value


class WriteMessageResult(MessageResult):
    operation: Literal["send_message", "edit_message"]
    chat_id: int
    # An accepted send can have no parsed Message in an unusual Telegram response.
    accepted: bool = True


class DeleteMessagesResult(BaseModel):
    operation: Literal["delete_messages"] = "delete_messages"
    chat_id: int
    requested_message_ids: list[int]
    revoke: bool
    accepted: bool = True
    source: Literal["telegram", "demo"]
