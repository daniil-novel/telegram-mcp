# Connect Telegram MCP to ChatGPT web

**English** · [Русский](chatgpt-tunnel.ru.md) · [Main guide](../README.md)

For ChatGPT web, the recommended connection is OpenAI's [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels). It connects a local MCP server over outbound HTTPS. No domain, public server or inbound firewall rule is needed. For Codex on the same computer, the local stdio plugin remains simpler.

The tunnel client requires a runtime API key even when you use a ChatGPT subscription. This key authenticates the connection to the tunnel service. The bridge does not make model API calls. The local stdio connection in Codex requires no OpenAI key.

1. Install Telegram MCP using the main guide. Authorize Telegram yourself in your terminal and confirm that local reading works.
2. Open [Tunnels](https://platform.openai.com/settings/organization/tunnels) in your OpenAI organization. Create a personal tunnel, associate your intended ChatGPT workspace and copy its `tunnel_id`. This ID is an identifier, not a secret key.
3. Download the official [tunnel-client](https://github.com/openai/tunnel-client/releases/latest) for your operating system. Check its release checksum, then run `tunnel-client help quickstart`.
4. Create a separate runtime key in [Platform settings](https://platform.openai.com/settings/organization/api-keys). Its principal needs **Tunnels Read + Use**. Creating/managing tunnels requires separate **Read + Manage** rights. Never use an admin key for the daemon. Enter the runtime key locally; do not put it in chat, this repository, command arguments or shell history.
5. Supply the key through a local secret mechanism as `CONTROL_PLANE_API_KEY`. Create a stdio profile with your actual tunnel ID and local paths:

```text
tunnel-client init --sample sample_mcp_stdio_local --profile telegram --tunnel-id <TUNNEL_ID> --mcp-command "<PYTHON> -m telegram_readonly_mcp --env-file <LOCAL_ENV_FILE> serve"
tunnel-client doctor --profile telegram --explain
tunnel-client run --profile telegram
```

Replace the angle-bracket placeholders. Quote paths containing spaces. A local command wrapper can supply nonsecret sending flags; leave credentials in their protected local configuration. The server remains read-only by default. Enable [sending](../README.md#7-enable-writes) separately if needed.

For managed background operation, use `tunnel-client runtimes connect --alias telegram --tunnel-id <TUNNEL_ID> --mcp-command "<MCP_COMMAND>" --runtime-api-key env:CONTROL_PLANE_API_KEY`, then `tunnel-client runtimes status telegram --json`. Verify a running, healthy, ready runtime. A saved profile alone does not prove connectivity. Check the installed version's help if flags differ.

6. While the runtime is online, open [ChatGPT plugins](https://chatgpt.com/plugins), choose **Add custom MCP server**, select **Tunnel** and enter your private tunnel ID. For this stdio profile, choose **No authentication** for the backend; the private tunnel controls access. Install the resulting plugin in the intended personal workspace.
7. Verify the discovered tools before requesting Telegram data. For read-only use expect seven read tools and no send, edit or delete actions. The [Telegram skill](../skills/telegram/) can be uploaded as a ZIP with the `telegram/` folder at its root. Add both the skill and the plugin to the conversation where supported.

The connection belongs to the selected account/workspace. It does not automatically copy local Codex plugins or skills to every account, workspace or device. Restart existing Codex sessions after a local plugin update.

The computer and tunnel runtime must stay online for discovery and tool calls. Configure operating-system startup separately if needed. This server has no auto-reply or incoming-event subscription. If you use HTTP instead of stdio, keep backend authentication; do not publish a port or remove protections to make the connection work.

For failures, check `doctor`, runtime status, workspace association and the runtime principal's tunnel permissions.
