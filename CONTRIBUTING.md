# Contributing

Thanks for helping improve Unofficial Telegram MCP. English and Russian issues and pull requests are welcome.

## Report a bug

Include OS, Python/uv versions, reproduction steps, expected/actual behavior and a redacted error. Use demo data when possible. Never attach `.env`, API hash, phone/login codes, 2FA password, session files or private messages. For vulnerabilities, follow [SECURITY.md](SECURITY.md).

## Develop locally

Fork and clone the repository, then run from its root:

```text
uv python install 3.11
uv sync --frozen --extra dev --python 3.11
uv run --frozen --extra dev python -m pytest -q
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
uv build
```

Tests need no Telegram credentials. Demo uses fixed fictional data. Do not use a maintainer's real account or perform live writes to test a contribution. Changes to Telegram behavior should include targeted fake-RPC tests and an honest statement of any live/platform verification limits.

## Pull requests

- Explain the user-visible problem and resulting behavior.
- Preserve read-only defaults, explicit destination ACLs, fail-closed RPC guards, local authorization and secret protection.
- For write changes, cover denied destinations, ownership checks and uncertain outcomes; do not add automatic write retries.
- Update both [English](README.md) and [Russian](README.ru.md) setup instructions if behavior changes. Check links, examples and image captions.
- Update [CHANGELOG.md](CHANGELOG.md) under Unreleased. Refresh `uv.lock` using uv only when dependencies change.
- Record checks actually run; do not claim unexecuted Linux/macOS/Docker/live checks.

The configured GitHub Actions workflow exercises account-free checks on Windows, Linux and macOS. A workflow file's presence is not proof that its checks have passed; inspect the run for your commit.

Contributions are licensed under the repository's [MIT license](LICENSE). Do not contribute Telegram credentials, copyrighted private messages or the official Telegram logo as an application logo.

## По-русски

Принимаются issue и PR на русском. Описывайте проблему, ОС, версии, шаги воспроизведения и проверенные результаты. Не прикладывайте секреты/личную переписку. Тесты выполняются без Telegram-аккаунта. Сохраняйте режим чтения по умолчанию, ограничения записи, локальный вход и guard. При изменении интерфейса обновляйте обе версии README и Unreleased в CHANGELOG. Уязвимости — по [SECURITY.md](SECURITY.md), а не через публичное раскрытие деталей.
