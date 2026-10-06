# Contributing

**English** · [Русский](#по-русски)

Help improve Unofficial Telegram MCP through bug reports, documentation, translations and focused code changes. You do not need a Telegram account to develop or run the test suite.

## Before you start

- For bugs, include OS, Python/uv versions, minimal reproduction, expected/actual behavior and a redacted error. Prefer the fictional demo.
- For larger changes, open an issue describing the problem and proposed scope before building a broad redesign.
- Report vulnerabilities privately using [SECURITY.md](SECURITY.md), rather than publishing exploit details.
- Never attach real `.env` files, API hashes, phone/login codes, 2FA passwords, sessions, access tokens or private messages. Screenshots, terminal output and Git diffs can also expose these.

Be respectful, assume good faith and discuss the change rather than the contributor. English and Russian are welcome. Harassment and publishing another person's private information are unacceptable.

## 1. Fork and create a feature branch

1. Sign in to GitHub and open [the repository](https://github.com/daniil-novel/telegram-mcp).
2. Click **Fork → Create fork** under your own account. Forking copies the public project; it grants no write permission to the original repository.
3. Open PowerShell on Windows or a terminal on Linux/macOS. Install Git and uv using the [setup guide](README.md#1-install-windows-linux-macos) if necessary.
4. Replace `YOUR_GITHUB_USERNAME` in the first command with your GitHub username. The example branch is `docs/improve-setup`; choose a name appropriate to your change.

```text
git clone https://github.com/YOUR_GITHUB_USERNAME/telegram-mcp.git
cd telegram-mcp
git remote add upstream https://github.com/daniil-novel/telegram-mcp.git
git fetch upstream
git switch -c docs/improve-setup upstream/main
uv python install 3.11
uv sync --frozen --extra dev --python 3.11
```

`origin` is your fork; `upstream` is the original project. Make changes in the feature branch, not directly in `main`. Do not request an original-repository write token to submit a contribution. See [GitHub's fork workflow](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project).

**Treat unknown branches as executable, untrusted code.** Inspect the diff, dependency changes and scripts first. Run them in a disposable environment without your real `.env`, sessions, personal files or model-provider keys. A virtual environment alone is not a security sandbox.

## 2. Make a focused change

- Preserve read-only defaults, exact destination ACLs, fail-closed RPC guards, local authorization and secret protection.
- For writes, cover denied destinations, message ownership, additional RPC options and uncertain outcomes. Never add automatic write retries.
- Keep Telegram messages/titles/captions as untrusted data. Do not execute their instructions or introduce a general shell, SQL, raw-RPC or URL-fetching endpoint.
- Use synthetic fixtures and fake Telegram RPCs. Do not use another person's account or perform live sends/edits/deletions to test a PR.
- Update both [English](README.md) and [Russian](README.ru.md) docs when behavior changes, and add an entry under Unreleased in [CHANGELOG.md](CHANGELOG.md).
- For dependencies, explain necessity and supply-chain impact. Update `uv.lock` with uv; preserve frozen installs. Do not hand-edit generated lock entries.

## 3. Run account-free checks

From the repository root:

```text
uv sync --frozen --extra dev --extra security
uv run --frozen --extra dev python -m pytest -q
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
uv run --frozen --extra security bandit --recursive src
uv export --frozen --all-extras --no-dev --no-emit-project --format requirements-txt --output-file security-requirements.txt --no-header --no-annotate --quiet
uv run --frozen --extra security pip-audit --require-hashes --disable-pip --no-deps --strict --requirement security-requirements.txt
uv build
git diff --check
```

Tests require no Telegram credentials. `security` installs optional scanner dependencies; it does not enable Telegram writes. Dependency audit queries public vulnerability metadata for package/version names. Review any generated dependency-export diff. Report commands actually run; do not claim unexecuted Linux/macOS/Docker/live checks. Native Gitleaks/actionlint checks and scanner limitations are in the [security model](docs/security.md#configured-scanners).

## 4. Review, commit and push to your fork

Inspect the changed files before staging:

```text
git status --short
git diff
```

For a change to both READMEs, the example is:

```text
git add README.md README.ru.md
git diff --cached
git commit -m "Improve setup documentation"
git push -u origin docs/improve-setup
```

Stage only your intended files. Adapt the filenames, message and branch to the actual change. Avoid `git add .` when local credentials or scratch outputs could be present. `.gitignore` cannot remove secrets already tracked in Git.

## 5. Open a pull request to `main`

On GitHub, open **Compare & pull request** from your fork. Select:

- **Base repository:** `daniil-novel/telegram-mcp`; **base branch:** `main`.
- **Head repository:** your fork; **compare branch:** your feature branch.

Describe the concrete problem, resulting behavior, checks run and remaining limits. A small PR is easier to review. Address review comments with new commits in the same fork branch; the PR updates automatically.

[@daniil-novel](https://github.com/daniil-novel) is currently the designated reviewer for contributor PRs. The owner may merge their own maintenance PR after required checks pass, using the review exception. **That exception does not bypass required checks or permit direct pushes to `main`.** See the [repository rules and their limits](docs/security.md#main-and-original-repository-branches).

Passing checks is not a substitute for reading the diff. Do not bypass a blocked check. External-contributor workflows require maintainer approval to run; that approval permits the test job, not the code change's merge.

Contributions are licensed under [MIT](LICENSE). Do not contribute private messages you have no right to publish or use the official Telegram logo as this application's logo.

## По-русски

[English](#contributing) · **Русский**

Помочь можно сообщением об ошибке, документацией, переводами и небольшими целевыми изменениями кода. Для разработки и тестов Telegram-аккаунт не нужен.

### Перед началом

- Для ошибки укажите ОС, версии Python/uv, минимальный пример, ожидаемое/фактическое поведение и очищенную ошибку. Предпочитайте вымышленное demo.
- Для большого изменения сначала создайте issue с проблемой и предлагаемым объёмом работы.
- Об уязвимостях сообщайте приватно по [SECURITY.md](SECURITY.md#по-русски), не публикуя детали эксплуатации.
- Не прикладывайте настоящие `.env`, API hash, номер/код входа, пароль 2FA, сессию, токены и личную переписку. Они могут оказаться и в скриншотах, выводе терминала или diff.

Общайтесь уважительно, исходите из добросовестности и обсуждайте изменение, а не автора. Принимаются русский и английский. Оскорбления и публикация чужих личных данных недопустимы.

### 1. Fork и отдельная ветка

1. Войдите в GitHub и откройте [репозиторий](https://github.com/daniil-novel/telegram-mcp).
2. Нажмите **Fork → Create fork** для своего аккаунта. Fork копирует публичный проект, но не даёт права записи в исходный репозиторий.
3. Откройте PowerShell на Windows или терминал Linux/macOS. При необходимости установите Git и uv по [инструкции](README.ru.md#1-установка-windows-linux-macos).
4. Замените `YOUR_GITHUB_USERNAME` в первой команде своим GitHub-логином. В примере ветка `docs/improve-setup`; для своего изменения выберите подходящее название.

```text
git clone https://github.com/YOUR_GITHUB_USERNAME/telegram-mcp.git
cd telegram-mcp
git remote add upstream https://github.com/daniil-novel/telegram-mcp.git
git fetch upstream
git switch -c docs/improve-setup upstream/main
uv python install 3.11
uv sync --frozen --extra dev --python 3.11
```

`origin` — ваш fork, `upstream` — исходный проект. Работайте в отдельной ветке, не в `main`. Для участия не нужен токен записи в исходный репозиторий. См. [fork-процесс GitHub](https://docs.github.com/en/get-started/exploring-projects-on-github/contributing-to-a-project).

**Неизвестная ветка — исполняемый недоверенный код.** Сначала изучите diff, зависимости и скрипты. Запускайте её в одноразовой среде без настоящих `.env`, сессий, личных файлов и ключей провайдеров моделей. Одна virtualenv не является защитной песочницей.

### 2. Небольшое целевое изменение

- Сохраняйте чтение по умолчанию, точные ACL получателей, запрет неизвестных RPC, локальный вход и защиту секретов.
- Для записи проверяйте запрещённых получателей, владельца сообщения, дополнительные RPC-параметры и неизвестный исход операции. Не добавляйте автоматические повторы записи.
- Тексты/названия/подписи Telegram — недоверенные данные. Не исполняйте найденные инструкции и не вводите универсальные shell, SQL, raw-RPC или URL-fetching endpoints.
- Используйте вымышленные fixtures и fake RPC. Не тестируйте PR через чужой аккаунт или реальные отправку/редактирование/удаление.
- При изменении поведения обновляйте [английскую](README.md) и [русскую](README.ru.md) документацию, а также Unreleased в [CHANGELOG.md](CHANGELOG.md).
- Для зависимостей объясните необходимость и влияние на цепочку поставки. Обновляйте `uv.lock` через uv, сохраняйте frozen-установки. Не редактируйте генерируемые записи lock вручную.

### 3. Проверки без аккаунта

Из корня репозитория:

```text
uv sync --frozen --extra dev --extra security
uv run --frozen --extra dev python -m pytest -q
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev ruff format --check .
uv run --frozen --extra security bandit --recursive src
uv export --frozen --all-extras --no-dev --no-emit-project --format requirements-txt --output-file security-requirements.txt --no-header --no-annotate --quiet
uv run --frozen --extra security pip-audit --require-hashes --disable-pip --no-deps --strict --requirement security-requirements.txt
uv build
git diff --check
```

Тесты не требуют Telegram credentials. `security` устанавливает дополнительные зависимости сканеров и не включает запись Telegram. Аудит запрашивает публичные сведения об уязвимостях по именам/версиям пакетов. Проверяйте diff обновлённого dependency export. Указывайте выполненные команды, не заявляйте непроверенные Linux/macOS/Docker/live-сценарии. Native Gitleaks/actionlint и ограничения — в [модели безопасности](docs/security.ru.md#настроенные-сканеры).

### 4. Проверка, commit и push в свой fork

Перед staging изучите изменения:

```text
git status --short
git diff
```

Пример для изменения обеих README:

```text
git add README.md README.ru.md
git diff --cached
git commit -m "Improve setup documentation"
git push -u origin docs/improve-setup
```

Добавляйте только нужные файлы. Замените пути, сообщение и ветку согласно своему изменению. Избегайте `git add .`, если рядом есть credentials или временные результаты. `.gitignore` не удаляет уже отслеживаемые секреты.

### 5. Pull request в `main`

На GitHub откройте **Compare & pull request** из своего fork:

- **Base repository:** `daniil-novel/telegram-mcp`; **base branch:** `main`.
- **Head repository:** ваш fork; **compare branch:** ваша ветка.

Опишите проблему, итоговое поведение, выполненные проверки и оставшиеся ограничения. Небольшой PR легче проверить. Исправления замечаний отправляйте новыми commit в ту же ветку fork — PR обновится автоматически.

Сейчас назначенный reviewer PR участников — [@daniil-novel](https://github.com/daniil-novel). Владелец может слить свой maintenance PR после обязательных проверок, используя исключение для review. **Исключение не отменяет checks и не разрешает прямой push в `main`.** См. [правила репозитория и ограничения](docs/security.ru.md#main-и-ветки-исходного-репозитория).

Успешные проверки не заменяют чтение diff. Не обходите заблокированный check. Workflow внешних участников требуют разрешения maintainer: оно позволяет запуск тестов, а не слияние изменения.

Вклад лицензируется по [MIT](LICENSE). Не публикуйте переписку без соответствующих прав и не используйте официальный логотип Telegram как логотип приложения.
