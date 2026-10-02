from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_ten_demo_evaluation_answers_via_real_mcp(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "0")
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "telegram_readonly_mcp", "serve", "--demo"]
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        async def call(name, **params):
            result = await session.call_tool(name, {"params": params})
            assert not result.isError
            assert result.structuredContent["source"] == "demo"
            return result.structuredContent

        async def walk(name, **params):
            collected = []
            for _ in range(30):
                page = await call(name, **params)
                collected.extend(page["items"])
                if not page["has_more"]:
                    return collected
                params["cursor"] = page["next_cursor"]
            raise AssertionError("Cursor walk did not end")

        dialogs = await walk("list_dialogs", limit=1)
        archived = next(d for d in dialogs if d["archived"])
        assert (await call("get_message", chat_id=archived["id"], message_id=3))["message"]
        filtered = (await call("list_dialogs", query="ГРУППА"))["items"][0]
        assert (await call("get_latest_messages", chat_id=filtered["id"]))["items"]
        history = []
        before = 0
        while True:
            page = await call("get_chat_history", chat_id=101, limit=2, before_id=before)
            history.extend(page["items"])
            if not page["has_more"]:
                break
            before = page["next_before_id"]
        group = next(d for d in dialogs if d["kind"] == "group")
        assert (await call("get_chat_history", chat_id=group["id"]))["items"]
        one = await call("get_message", chat_id=group["id"], message_id=3)
        global_search = await walk("search_messages", query="задача", limit=2)
        private = next(d for d in dialogs if d["kind"] == "private")
        chat_search = await walk("search_messages", query="задача", chat_id=private["id"], limit=2)
        latest = await walk("get_latest_messages", limit=1, per_chat_limit=2)
        unread = await walk("get_unread_messages", limit=1)
        between = []
        before = 0
        while True:
            page = await call(
                "messages_between",
                chat_id=private["id"],
                limit=1,
                start="2026-10-02T12:00:02+03:00",
                end="2026-10-02T12:00:04+03:00",
                before_id=before,
            )
            between.extend(page["items"])
            if not page["has_more"]:
                break
            before = page["next_before_id"]
        answers = [
            str(len(dialogs)),
            str(archived["id"]),
            str(filtered["id"]),
            str(len(history)),
            one["message"]["text"],
            str(len({(m["chat_id"], m["id"]) for m in global_search})),
            str(len(chat_search)),
            str(len(latest)),
            str(len(unread)),
            ",".join(str(m["id"]) for m in between),
        ]
        source = Path(__file__).resolve().parents[1] / "evaluations" / "demo.xml"
        expected = [item.findtext("answer") for item in ET.parse(source).getroot()]
        assert len(expected) == 10
        assert answers == expected
