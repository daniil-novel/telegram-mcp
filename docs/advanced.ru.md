# Расширенное использование

[English](advanced.md) · **Русский** · [Основная инструкция](../README.ru.md)

Начните с локального stdio. Эти варианты нужны для HTTP-клиента или контейнера; публичный endpoint ChatGPT они не создают.

## Локальный HTTP с аутентификацией

1. Выполните установку, настройку `.env` и локальный вход по основной инструкции.
2. В своём терминале создайте отдельный случайный токен HTTP:

```text
uv run --frozen python -c "import secrets; print(secrets.token_urlsafe(48))"
```

3. Локально скопируйте результат в `.env` как `MCP_HTTP_TOKEN`. Не подставляйте API hash или сессию; не помещайте токен в URL/issue.
4. Запустите из папки репозитория и оставьте терминал открытым:

```text
uv run --frozen telegram-mcp serve --transport http
```

Адрес по умолчанию: `http://127.0.0.1:8765/mcp`. Требуется `Authorization: Bearer YOUR_HTTP_TOKEN` для initialize, списка и вызова инструментов. Токен: ASCII, от 32 символов, без пробелов. Host/Origin проверяются по явным спискам `.env`, wildcard запрещён. Логи HTTP-доступа отключены. **Ctrl+C** останавливает сервер.

Для Codex добавьте в существующий пользовательский конфиг:

```toml
[mcp_servers.telegram_http]
url = 'http://127.0.0.1:8765/mcp'
bearer_token_env_var = 'TELEGRAM_MCP_HTTP_TOKEN'
startup_timeout_sec = 60
tool_timeout_sec = 60
```

**Процесс клиента** должен унаследовать `TELEGRAM_MCP_HTTP_TOKEN` с тем же токеном: для HTTP-авторизации Codex не читает серверный `.env`. При запуске CLI задайте переменную в терминале перед `codex`:

```powershell
# Windows PowerShell — подставьте свой HTTP-токен локально.
$env:TELEGRAM_MCP_HTTP_TOKEN = '<YOUR_HTTP_TOKEN>'
codex
```

```bash
# Linux/macOS — подставьте свой HTTP-токен локально.
export TELEGRAM_MCP_HTTP_TOKEN='<YOUR_HTTP_TOKEN>'
codex
```

В этих примерах токен попадает в историю команд. На общем компьютере используйте защищённое хранение клиента или stdio. Переменная терминала не меняет окружение уже запущенного настольного приложения. Не запускайте одновременно stdio и HTTP для одной сессии без необходимости.

Если HTTP-клиент использует системный прокси, исключите `127.0.0.1`/`localhost` в настройках самого клиента. Для другого порта измените аргументы сервера и списки Host/Origin. `--host 0.0.0.0` открывает все интерфейсы: вне контейнера с контролируемой loopback-публикацией нужны ваши меры ограничения сети. Backend не является многопользовательским сервисом.

## Docker

Нужны Docker с запущенным движком Linux-контейнеров и Docker Compose. Docker необязателен для stdio. Заранее заполните `.env`, включая случайный `MCP_HTTP_TOKEN`.

Из папки репозитория на Windows, Linux или macOS:

```text
docker compose build
docker compose run --rm --no-deps telegram auth
docker compose up telegram
```

Введите номер/код/2FA сами в интерактивном терминале контейнера. Сессия сохраняется в отдельном volume Compose. Windows DPAPI-сессию нельзя перенести в Linux-контейнер: авторизуйтесь внутри заново.

Контейнер работает как UID 10001: корневая файловая система read-only, Linux capabilities отсутствуют, повышение привилегий запрещено. Volume сессии доступен для записи при авторизации/защите хранения. Compose публикует endpoint только на **127.0.0.1:8765**. Это свойства конфигурации; evidence реальной сборки/запуска приведён в [VALIDATION.md](../VALIDATION.md).

HTTP demo без аккаунта:

```text
docker compose run --rm --service-ports telegram serve --transport http --host 0.0.0.0 --demo
```

Для demo нужен HTTP-токен, Telegram credentials игнорируются. Остановить: **Ctrl+C**. Обычный сервис:

```text
docker compose down
```

Не добавляйте `-v`, если хотите сохранить volume сессии. Для обновления не требуется удалять чужие контейнеры, образы или volumes.

## Браузерные и облачные клиенты

Обычный размещённый в облаке MCP-клиент не видит `localhost` вашего ноутбука. ChatGPT web не читает локальный Codex `config.toml` и не запускает этот stdio-процесс; см. [официальную документацию MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

Репозиторий содержит локальный backend со статическим bearer-токеном. Публичного хостинга, домена, TLS-терминации и полного MCP OAuth gateway **нет**. Не снимайте аутентификацию и не публикуйте backend напрямую.

Для удалённого размещения нужны HTTPS endpoint с корректной аутентификацией, доступ, привязанный к владельцу, сетевые ограничения и реализация, совместимая с выбранным клиентом. Статический backend-токен сам по себе не OAuth. `configs/chatgpt-developer-mode.example.json` — справочный материал для сложной интеграции, не импортируемый готовый endpoint. Перед использованием проверьте актуальную документацию клиента.
