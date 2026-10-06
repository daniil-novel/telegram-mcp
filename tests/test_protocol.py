from __future__ import annotations

import json
import sys

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from telegram_readonly_mcp.backend import DemoBackend
from telegram_readonly_mcp.config import Settings
from telegram_readonly_mcp.server import create_http_app, create_server
from telegram_readonly_mcp.service import READ_TOOLS


async def test_real_stdio_protocol_all_tools_without_telegram(monkeypatch):
    # Demo must ignore even bogus Telegram credentials/session paths.
    monkeypatch.setenv("TELEGRAM_API_ID", "0")
    monkeypatch.setenv("TELEGRAM_SESSION_DIR", "Z:/nonexistent-no-demo-access")
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "telegram_readonly_mcp", "serve", "--demo"]
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        initialized = await session.initialize()
        assert "untrusted" in initialized.instructions
        tools = (await session.list_tools()).tools
        assert {t.name for t in tools} == READ_TOOLS
        assert all(t.annotations.readOnlyHint and not t.annotations.destructiveHint for t in tools)
        examples = {
            "list_dialogs": {"limit": 2},
            "get_chat_history": {"chat_id": 101, "limit": 2},
            "get_message": {"chat_id": 101, "message_id": 3},
            "search_messages": {"query": "задача", "limit": 2},
            "get_latest_messages": {"limit": 2},
            "get_unread_messages": {"limit": 2},
            "messages_between": {
                "chat_id": 101,
                "start": "2026-10-02T09:00:02Z",
                "end": "2026-10-02T09:00:04Z",
            },
        }
        for name, params in examples.items():
            result = await session.call_tool(name, {"params": params})
            assert not result.isError, result
            assert result.structuredContent["source"] == "demo"
        bad = await session.call_tool("send_message", {"chat_id": 101, "text": "never sent"})
        assert bad.isError
        invalid = await session.call_tool(
            "get_chat_history", {"params": {"chat_id": 101, "limit": 10000}}
        )
        assert invalid.isError


async def test_http_auth_host_origin_and_full_protocol(tmp_path):
    class Counted(DemoBackend):
        opens = 0
        closes = 0

        async def open(self):
            self.opens += 1

        async def close(self):
            self.closes += 1

    backend = Counted()
    mcp, _ = create_server(Settings(session_dir=tmp_path), backend=backend)
    token = "test-only-synthetic-http-token-0123456789"
    app = create_http_app(mcp, token)
    async with app.app.router.lifespan_context(app.app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
        ) as client:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "offline-test", "version": "1"},
                },
            }
            headers = {
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {token}",
            }
            for authorization in (None, "Bearer wrong"):
                test_headers = {"Accept": headers["Accept"]}
                if authorization:
                    test_headers["Authorization"] = authorization
                response = await client.post("/mcp", json=payload, headers=test_headers)
                assert response.status_code == 401
            assert (await client.post("/mcp", json=payload, headers=headers)).status_code == 200
            hostile = await client.post(
                "/mcp", json=payload, headers={**headers, "Host": "evil.example"}
            )
            assert hostile.status_code == 421
            hostile = await client.post(
                "/mcp", json=payload, headers={**headers, "Origin": "https://evil.example"}
            )
            assert hostile.status_code == 403
            response = await client.post(
                "/mcp",
                headers=headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            assert {t["name"] for t in response.json()["result"]["tools"]} == READ_TOOLS
            # Discovery must stay quiet: it never connects to Telegram or polls messages.
            assert backend.opens == 0
            response = await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "list_dialogs", "arguments": {"params": {"limit": 1}}},
                },
            )
            assert response.status_code == 200
            result = response.json()["result"]
            assert not result.get("isError")
            assert result["structuredContent"]["source"] == "demo"
            assert "Telegram Read-only MCP" not in json.dumps(result)
        assert backend.opens == 1 and backend.closes == 0
    assert backend.closes == 1


async def test_stdio_without_credentials_initializes_but_refuses_read(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_API_ID", "0")
    monkeypatch.setenv("TELEGRAM_API_HASH", "")
    monkeypatch.setenv("TELEGRAM_SESSION_DIR", str(tmp_path / "not-created"))
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "telegram_readonly_mcp", "--env-file", str(tmp_path / "absent.env"), "serve"],
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        assert {t.name for t in (await session.list_tools()).tools} == READ_TOOLS
        result = await session.call_tool("list_dialogs", {"params": {"limit": 1}})
        assert result.isError
        assert "Fill TELEGRAM_API_ID" in result.content[0].text
    assert not (tmp_path / "not-created").exists()
