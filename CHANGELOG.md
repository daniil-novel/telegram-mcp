# Changelog

User-visible changes are recorded here. Entries under Unreleased are prepared changes, not a claim that a version has been published to a package registry.

## [Unreleased]

## [0.2.2] - 2026-10-06

### Documentation

- Keep the standard MIT license and explain required copyright/license notices,
  optional visible attribution and reuse without whole-project copyleft.
- Add English/Russian licensing guides with Telegram API/content terms,
  AI-consent boundaries and unresolved client obligations. No platform approval
  or immunity from third-party claims is promised.
- Record the licenses of the five inspected direct dependencies, including
  bundled LGPL components in pywin32, and distinguish Telegram artwork rights.

### Packaging

- Include LICENSE, NOTICE and THIRD_PARTY_NOTICES.md in Python distributions and
  make the same notice files available to the container build.

## [0.2.1] - 2026-10-06

### Security

- Redact unexpected backend, schema and startup errors so submitted values and library diagnostics do not escape through MCP or startup output.
- Normalize session paths and reject dangling links before storage; retain private local storage and platform-specific session protection.
- Validate exact read IDs and limits again at execution, check cached/returned Telegram peers and suppress mismatched message metadata.
- Enforce runtime checks even under optimized Python and send HTTP responses with `Cache-Control: no-store`.
- Add adversarial account-free regression coverage and pinned Bandit, dependency, secret, workflow and CodeQL checks for pull requests.

### Community

- Document fork-based contributions and designated-maintainer review. Add CODEOWNERS, issue/PR templates and weekly Dependabot updates.
- Protect main through separate mandatory-check and review rules; the owner can waive a second review only through a PR, without waiving core checks.
- Improve both READMEs with navigation, status badges, a security model and an optional star request.

### Documentation

- Propose a local privacy filter with encrypted local storage, data minimization,
  pseudonymization and an optional local LLM judge. Include researched model
  candidates, limitations and acceptance checks; this is not an implemented feature.

## [0.2.0] - 2026-10-06

### Added

- Optional `TELEGRAM_WRITE_ENABLED` configuration, with an exact write-destination allowlist. Read-only remains the default.
- Tools for sending literal text, editing the user's own outgoing messages and deleting the user's own outgoing messages.
- English and Russian setup guides with language links, Windows/Linux/macOS commands, Telegram API walkthrough illustrations and Codex examples.
- Contribution and security guidance, MIT license and account-free CI configuration.

### Changed

- Public-facing project name and repository use `telegram-mcp`; the legacy CLI/module and session storage paths remain compatible.
- Send operations default to silent delivery and disable link previews.
- Documentation distinguishes this request-driven server from client/browser notifications and background monitors.

### Security

- Write destinations must pass the exact write allowlist and read ACL. Empty write allowlists deny all writes, and wildcards are rejected.
- Editing/deletion are restricted to the user's outgoing messages. Uncertain write outcomes must not be retried automatically.

## [0.1.0]

### Added

- Initial guarded read-only Telegram MCP with seven read tools, local authorization, protected external session storage, ACLs and pagination.
- Local stdio, authenticated HTTP, synthetic demo and Docker configuration.

No historical publication date is inferred for this initial version.
