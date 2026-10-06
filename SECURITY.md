# Security

**English** · [Русский](#по-русски)

## Scope and limits

The server restricts use of a Telegram personal-account session. Telegram does not issue a read-only user-session scope; possession of the underlying session can grant account powers outside this program. The guard cannot protect against a compromised OS user, stolen session, modified source/runtime or malicious MCP client.

Read-only is the default. Writes require both `TELEGRAM_WRITE_ENABLED=true` and exact destination IDs in `TELEGRAM_WRITE_ALLOWED_CHAT_IDS`; read ACLs still apply. Never assume a client's tool annotations alone enforce this boundary.

Windows sessions use current-user DPAPI and restricted ACLs. Linux/macOS session files use owner-only permissions and are **not encrypted at rest**. Session storage is outside the repository. The server creates no message/contact database, but an MCP client may store responses and expose them to its model.

Telegram texts/titles/captions are untrusted data. They do not authorize instructions, command execution or writes. The server's prompt-injection guidance is advisory to the client; it cannot guarantee a model will follow it. Human approval is required by the client workflow, while server-side code enforces configured destination/action limits. The proposed anonymizer is **not implemented**.

The server uses no SQL query backend and never evaluates message text as a SQL query or shell command. This does not protect a downstream client that chooses to execute that text. HTTP requires a separate random bearer token, explicit Host/Origin checks and restricted network access; stdio is recommended. This backend is not a public multi-user service or a complete OAuth gateway.

See the [detailed security model](docs/security.md) for threat boundaries, repository controls and scanner limitations. Automated checks are not a certification or a guarantee of zero vulnerabilities or data leaks.

## Report a vulnerability

Private vulnerability reporting is enabled. Use [**Security → Report a vulnerability**](https://github.com/daniil-novel/telegram-mcp/security/advisories/new) while signed in to GitHub. Reports are private to the maintainer and authorized security collaborators, not public issues. If the form becomes unavailable, open an issue asking for a private channel **without exploit details, affected private data or credentials**.

Include affected version/commit, minimal synthetic reproduction, expected boundary and actual behavior. Do not send a real session/API hash, phone/login code, password or chat transcript. The maintainer cannot use your Telegram login to diagnose a bug.

No guaranteed response time or long-term support window is promised. Start with the latest `main` revision and recorded [validation evidence](VALIDATION.md). Older copies should be updated before exposing HTTP or enabling writes.

## If access or a secret is exposed

1. Disable the MCP connection and stop its processes.
2. In the official Telegram client, open **Settings → Devices** and terminate the affected session. Deleting a local file alone does not revoke a copied session.
3. Remove exposed material from accessible locations. A Git ignore rule is not a revocation or a way to erase Git history.
4. For an exposed HTTP token, generate a new one, update the server and client locally, and restart both connections.
5. Reauthorize locally only after securing the machine/runtime. Never send the new credentials to an assistant or issue.

For API credential exposure, consult Telegram's current developer controls/support rather than assuming the API hash can always be rotated in place.

## По-русски

[English](#security) · **Русский**

### Границы защиты

Сессия Telegram имеет полномочия аккаунта; чтение по умолчанию ограничивается кодом сервера. Кража сессии, взлом ОС, изменение исходников/runtime и вредоносный MCP-клиент этой защитой не покрываются.

Запись требует `TELEGRAM_WRITE_ENABLED=true` и точных ID в `TELEGRAM_WRITE_ALLOWED_CHAT_IDS`; ограничения чтения также действуют. Одних аннотаций инструментов недостаточно для защиты.

Windows использует DPAPI текущего пользователя и ограниченные ACL. На Linux/macOS файл защищён правами, но **не зашифрован на диске**. Сессии хранятся вне репозитория. База сообщений/контактов не создаётся, но клиент способен сохранять ответы и передавать их модели.

Текст, названия и подписи Telegram — недоверенные данные. Они не разрешают команды или запись. Инструкции против prompt injection рекомендательны для клиента; нельзя гарантировать, что модель им последует. Подтверждение человеком требуется в процессе клиента, а сервер исполняет ограничения получателя/действия. Запланированный анонимизатор **ещё не реализован**.

SQL-backend нет: текст сообщения не исполняется как SQL-запрос или shell-команда. Это не защищает клиент, который сам решит исполнить текст. HTTP требует отдельного случайного bearer-токена, Host/Origin-проверок и сетевых ограничений; рекомендуется stdio. Это не публичный многопользовательский сервис и не полноценный OAuth-шлюз.

Подробнее: [модель безопасности](docs/security.ru.md). Автоматические проверки не являются сертификацией и не гарантируют отсутствие уязвимостей/утечек.

### Сообщить об уязвимости

Приватные сообщения включены. Войдите в GitHub и откройте [**Security → Report a vulnerability**](https://github.com/daniil-novel/telegram-mcp/security/advisories/new). Отчёт доступен maintainer и авторизованным security collaborators, а не как публичный issue. Если форма недоступна, создайте issue с просьбой о приватном канале **без деталей эксплуатации, личных данных и credentials**.

Укажите версию/commit, минимальное вымышленное воспроизведение, ожидаемую границу и фактическое поведение. Не отправляйте настоящую сессию/API hash, номер/код, пароль или переписку. Ваш Telegram-вход не нужен для диагностики.

Гарантированный срок ответа и долгосрочная поддержка не обещаны. Начните с актуального `main` и [подтверждённых проверок](VALIDATION.md). Старые копии стоит обновить до подключения HTTP или записи.

### При утечке доступа или секрета

1. Отключите MCP и остановите его процессы.
2. В официальном Telegram откройте **Настройки → Устройства** и завершите затронутую сессию. Удаление локального файла не отзывает скопированную сессию.
3. Уберите утёкшие данные из доступных мест. `.gitignore` не отзывает секрет и не удаляет историю Git.
4. Замените утёкший HTTP-токен локально в сервере и клиенте, затем перезапустите подключения.
5. Войдите заново локально только после защиты компьютера/runtime. Не отправляйте новые credentials ассистенту или в issue.

При утечке API credentials обратитесь к актуальным настройкам разработчика/поддержке Telegram: не предполагается, что API hash всегда можно заменить на месте.
