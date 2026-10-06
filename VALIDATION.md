# Validation — 0.2.1

Evidence cutoff: 2026-10-06. The 0.2.1 security changes were checked on synthetic
data only, without accessing a real Telegram account, `.env`, or session.

## Security patch checks

- Windows CPython 3.11.5: **157 tests passed in 13.07 seconds**; Ruff lint/format
  passed. The suite includes 54 adversarial hardening cases and strengthened
  request-identity testing alongside the previous 103 cases.
- Cases cover backend/schema/startup diagnostic redaction, strict numeric IDs
  and copied models, chat/peer ownership, changed-ACL cursors, path traversal,
  dangling symlinks, installed-wheel Git/worktree storage, optimized Python,
  malicious message text, HTTP authorization/body bounds and `no-store`.
- Bandit 1.9.4: **0 findings, 0 errors across 1719 production lines**;
  production checks are explicit rather than removable asserts.
  The only targeted suppression is B104 for the deliberately selectable
  `0.0.0.0` Docker/remote bind; the default remains loopback with auth guards.
- pip-audit 2.10.1 checked all 69 registry packages in the updated lock,
  including runtime, development, scanner and conditional-platform packages:
  **0 known advisories, 0 skipped packages** at the cutoff. Hash-locked export
  auditing also passed. An advisory database is not a proof against unknown bugs.
- actionlint 1.7.12 checked all three workflows with no diagnostics. This local
  check did not run optional shellcheck/pyflakes; the hosted Linux check can use
  tools present on its runner.
- Gitleaks 8.30.1 found no secrets in the baseline working-tree archive and all
  four prior commits with default rules and redacted output. Project rules add
  literal Telegram API hashes and StringSession formats. Synthetic rule checks
  validate format detection/redaction; arbitrary secrets or personal data can
  still evade pattern-based detection.
- The final 64-file Git-visible source snapshot and four prior commits also
  passed default plus project secret rules: **0 findings**. Synthetic checks
  detected all eight positive forms, accepted all seven placeholders/expressions,
  and kept markers out of redacted diagnostics.
- Tool binaries were downloaded from their official GitHub releases and verified
  against SHA-256 release metadata before execution. Actions use full commit
  pins; CI uses uv 0.12.21. Runtime/scanner dependencies use the reviewed uv lock.

The new [Security](.github/workflows/security.yml) and
[CodeQL](.github/workflows/codeql.yml) workflows configure recurring and PR
checks. Configuration is separate from completed results: inspect checks and
code-scanning alerts for the exact revision in
[GitHub Actions](https://github.com/daniil-novel/telegram-mcp/actions).
CodeQL was not executed locally. Do not interpret successful static analysis,
unit tests or repository rules as a promise of no prompt injection, PII leakage
through permitted message content, account compromise or unknown vulnerabilities.

## Previous 0.2.0 evidence

The sections below are historical results tied to the stated 0.2.0 commits;
they do not claim that a later runtime revision is identical.

Validation cutoff: 2026-10-06. All Telegram responses used in tests are synthetic.
No real Telegram message was sent, edited, deleted, marked read or downloaded.

### Completed locally

- Windows, CPython 3.11.5, pinned Telethon 1.45.0 and MCP SDK 1.30.0.
- Full suite: **103 passed in 10.83 seconds**. Includes all 41 previous tests and
  62 new write-mode cases. The final run used a normal Windows process because
  the restricted execution environment denies named pipes and ACL changes that
  are required by stdio and private-file tests.
- Ruff lint and formatting: passed; 22 Python files already formatted.
- New `telegram-mcp` CLI and legacy `telegram-readonly-mcp` CLI: help works.
- PowerShell installer and authorization scripts: syntax parsed successfully.
- Source distribution and wheel built successfully with `uv build --offline`.
- Release file/config syntax and local Markdown links/fences: validated.
- Independent write/security review: two found issues were fixed (uncertain
  server-error write outcomes and service-message read compatibility); no
  remaining actionable blocker in the reviewed implementation.

### Completed in GitHub Actions

The [CI run 37444145637](https://github.com/daniil-novel/telegram-mcp/actions/runs/37444145637)
completed successfully on 2026-10-06 for source commit
`ffa88352fceaa11dad63b8e1d7916316dd9474a6` (push event, attempt 1).
The run status, all five job results and each job's decoded logs were inspected
through GitHub's API; results below are actual completed checks.

| Hosted runner | CPython in job log | Synthetic tests | Job result |
| --- | --- | --- | --- |
| Ubuntu (`ubuntu-latest`) | 3.11.16 | 103 passed in 9.60s | Success |
| Ubuntu (`ubuntu-latest`) | 3.12.14 | 103 passed in 10.32s | Success |
| Ubuntu (`ubuntu-latest`) | 3.13.15 | 103 passed in 10.35s | Success |
| Windows (`windows-latest`) | 3.11.9 | 103 passed in 8.02s | Success |
| macOS (`macos-latest`) | 3.11.9 | 103 passed in 6.86s | Success |

Every job passed the frozen dependency installation, Ruff lint and formatting,
the full test suite, and building both `telegram_mcp-0.2.0.tar.gz` and
`telegram_mcp-0.2.0-py3-none-any.whl`. The workflow uses no real Telegram
credentials; tests use fake Telegram responses, fictional demo data and
temporary session files. These checks verify installation, test behavior and
package builds on the listed hosted runners, not live Telegram operations or
Docker execution. This evidence is bound to the source commit above. The later
Windows installer migration was syntax-checked locally; its commands were not
executed end to end. The Telegram runtime code is unchanged from that CI run.

### Behavior covered

- Seven read tools by default; three write tools appear only when enabled.
- False/default flag, empty write ACL, exact chat IDs, read ACL/deny precedence,
  auth-mode refusal and ACL denial before opening the backend.
- Fixed request classes, recursive wrappers, exact request bytes/object identity,
  caller task and ACL at both Telethon `_call` and `_sender.send` boundaries.
- Plain text, no markup/link previews, silent sends; Unicode text bounds,
  strict IDs/booleans, duplicate and oversized deletion lists.
- Own-message edit/delete, foreign/incoming/service messages refused, all batch
  IDs validated before deletion, actual peer verification for nonchannel IDs,
  channel-specific deletion and explicit `revoke=true` requirement.
- Unknown write outcome after connection loss, timeout, server failure or
  duplicate-random-ID response. No application-level automatic write retry.
- Fake-Telethon responses, synthetic demo round trip, real MCP stdio and
  authenticated HTTP discovery/calls, tool annotations and malformed inputs.
- Existing read ACL, archive/search/unread/pagination/cursors/timezone intervals,
  private session storage and local-only interactive authorization behavior.
- MCP initialization and tool discovery do not open the Telegram connection.

### Images and documentation

The login image is a real unauthenticated capture; no number/code was entered.
The post-login images are labeled illustrations with placeholders. All images
were visually inspected. Actual personal notifications/messages and credentials
are excluded from the repository. English and Russian READMEs provide reciprocal
language links and OS-specific setup; image provenance is in docs/images/README.md.

### Limits of the evidence

- Live send/edit/delete was intentionally not performed against the user's
  account. Telegram's live permissions/edit windows/rate limits still apply.
- Hosted Linux/macOS/Windows and Python 3.11/3.12/3.13 checks passed as recorded
  above. Other Python/OS combinations and users' live environments were not
  verified by that matrix.
- Docker Engine was unavailable locally. Container build/login is not verified
  here; Windows DPAPI sessions cannot be copied into a Linux container.
- No public HTTPS/OAuth gateway for ChatGPT web is deployed by this project.
- The supplied desktop toast's cause was not reproduced. Source and installed
  runtime contain no toast sender or background Telegram update subscription.
  Telegram Web/client notifications are a possible separate source; this release
  does not claim an OS notification permission was changed.
