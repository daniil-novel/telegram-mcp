# Advanced use

**English** · [Русский](advanced.ru.md) · [Main setup guide](../README.md)

Use local stdio first. The following options are for users who need an HTTP client or container; they do not create a public ChatGPT endpoint.

## Authenticated local HTTP

1. Complete the main guide's installation, `.env` and local authorization steps.
2. In your terminal, generate a separate random HTTP token:

```text
uv run --frozen python -c "import secrets; print(secrets.token_urlsafe(48))"
```

3. Copy the value locally into `.env` as `MCP_HTTP_TOKEN`. Do not substitute API hash or Telegram session; do not put the token in a URL or issue.
4. Start the server from the repository and leave this terminal open:

```text
uv run --frozen telegram-mcp serve --transport http
```

The default endpoint is `http://127.0.0.1:8765/mcp`. Requests require `Authorization: Bearer YOUR_HTTP_TOKEN`, including initialize, list tools and call tool. Tokens must be ASCII, at least 32 characters, without whitespace. Host and Origin are checked against explicit `.env` allowlists; wildcards are rejected. HTTP access logging is disabled. **Ctrl+C** stops the server.

For Codex, append the following to its existing user config:

```toml
[mcp_servers.telegram_http]
url = 'http://127.0.0.1:8765/mcp'
bearer_token_env_var = 'TELEGRAM_MCP_HTTP_TOKEN'
startup_timeout_sec = 60
tool_timeout_sec = 60
```

The **client process** must inherit `TELEGRAM_MCP_HTTP_TOKEN` containing the same token; Codex does not read the server's `.env` for HTTP authentication. For a CLI launch, set it in the terminal before starting `codex`:

```powershell
# Windows PowerShell — substitute your HTTP token locally.
$env:TELEGRAM_MCP_HTTP_TOKEN = '<YOUR_HTTP_TOKEN>'
codex
```

```bash
# Linux/macOS — substitute your HTTP token locally.
export TELEGRAM_MCP_HTTP_TOKEN='<YOUR_HTTP_TOKEN>'
codex
```

These examples place a token in shell history. On a shared machine, use your client's secure credential mechanism or prefer stdio. Setting a variable in a terminal does not update an already running desktop app. Do not enable both stdio and HTTP instances for the same session unnecessarily.

If an HTTP client uses a system proxy, exclude `127.0.0.1`/`localhost` in that client's proxy configuration. For a different port, update both the server arguments and Host/Origin lists. `--host 0.0.0.0` exposes all network interfaces; outside a container's controlled loopback publication, it requires your own network-access controls. The HTTP backend is not a multi-user service.

## Docker

Requires Docker with a running Linux-container engine and Docker Compose. Docker is optional; stdio does not require it. Fill in `.env` first, including a random `MCP_HTTP_TOKEN`.

From the repository on Windows, Linux or macOS:

```text
docker compose build
docker compose run --rm --no-deps telegram auth
docker compose up telegram
```

Enter the phone/code/2FA yourself in the interactive container terminal. The session is stored in the dedicated Compose volume. A Windows DPAPI session cannot be moved into a Linux container: authorize again inside the container.

The container runs as UID 10001, with a read-only root filesystem, no Linux capabilities and no privilege escalation. Its session volume is writable for authorization/storage protection. Compose publishes the endpoint only on **127.0.0.1:8765**. These are configuration properties; live build/run evidence is listed in [VALIDATION.md](../VALIDATION.md).

Account-free HTTP demo:

```text
docker compose run --rm --service-ports telegram serve --transport http --host 0.0.0.0 --demo
```

Demo requires the HTTP token but ignores Telegram credentials. Stop with **Ctrl+C**. For the regular service:

```text
docker compose down
```

Do not add `-v` if you want to keep the session volume. Updating containers does not require deleting other containers, images or volumes.

## Browser/cloud clients

An ordinary hosted browser/cloud MCP client cannot reach `localhost` on your laptop. ChatGPT web does not read local Codex `config.toml` or start this stdio executable; see [official MCP guidance](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

This repository supplies a local backend with a static bearer token. It does **not** supply public hosting, a domain, TLS termination or a complete MCP OAuth gateway. Do not remove authentication or publish the backend directly as a shortcut.

A remote deployment would require a correctly authenticated HTTPS endpoint, owner-bound access, network controls and a secure implementation compatible with the intended client's authentication model. A static backend token is not itself OAuth. The file in `configs/chatgpt-developer-mode.example.json` is background reference for an advanced integration, not an importable ready-made endpoint. Verify the current client documentation before using it.
