# Security

## Scope and limits

The server restricts use of a Telegram personal-account session. Telegram does not issue a read-only user-session scope; possession of the underlying session can grant account powers outside this program. The guard cannot protect against a compromised OS user, stolen session, modified source/runtime or malicious MCP client.

Read-only is the default. Writes require both `TELEGRAM_WRITE_ENABLED=true` and exact destination IDs in `TELEGRAM_WRITE_ALLOWED_CHAT_IDS`; read ACLs still apply. Never assume a client's tool annotations alone enforce this boundary.

Windows sessions use current-user DPAPI and restricted ACLs. Linux/macOS session files use owner-only permissions and are **not encrypted at rest**. Session storage is outside the repository. The server creates no message/contact database, but an MCP client may store responses and expose them to its model.

Telegram texts/titles/captions are untrusted data. They do not authorize instructions, command execution or writes. HTTP requires a separate random bearer token, explicit Host/Origin checks and restricted network access; stdio is the recommended local connection. This backend is not a public multi-user service or a complete OAuth gateway.

## Report a vulnerability

If **Security → Report a vulnerability** is available on this repository, use GitHub's private reporting flow. Otherwise, open an issue asking for a private reporting channel **without publishing exploit details, affected private data or credentials**. No private contact address is promised until the maintainer provides one.

Include affected version/commit, minimal synthetic reproduction, expected boundary and actual behavior. Do not send a real session/API hash, phone/login code, password or chat transcript. The maintainer cannot use your Telegram login to diagnose a bug.

No guaranteed response time or supported-version lifetime is currently promised. Start with the latest repository version and recorded [validation evidence](VALIDATION.md).

## If access or a secret is exposed

1. Disable the MCP connection and stop its processes.
2. In the official Telegram client, open **Settings → Devices** and terminate the affected session. Deleting a local file alone does not revoke a copied session.
3. Remove exposed material from accessible locations. A Git ignore rule is not a revocation or a way to erase Git history.
4. For an exposed HTTP token, generate a new one, update the server and client locally, and restart both connections.
5. Reauthorize locally only after securing the machine/runtime. Never send the new credentials to an assistant or issue.

For API credential exposure, consult Telegram's current developer controls/support rather than assuming the API hash can always be rotated in place.

## По-русски

Сессия Telegram имеет полномочия аккаунта; read-only ограничивается кодом этого сервера. Кража сессии/взлом ОС/изменение runtime этой защитой не покрываются. На Linux/macOS файл защищён правами, но не зашифрован. Ответы MCP доступны клиенту и его модели.

Об уязвимости сообщайте приватно через **Security → Report a vulnerability**, если функция доступна. Иначе создайте issue с просьбой о приватном канале без деталей эксплуатации и личных данных. При утечке выключите MCP, завершите сессию в **Telegram → Настройки → Устройства**, замените HTTP-токен и обеспечьте безопасность машины до нового локального входа. Не присылайте номер, код, пароль, API hash или сессию.
