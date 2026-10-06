# Validation — 0.2.0

Validation cutoff: 2026-10-06. All Telegram responses used in tests are synthetic.
No real Telegram message was sent, edited, deleted, marked read or downloaded.

## Completed locally

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

## Behavior covered

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

## Images and documentation

The login image is a real unauthenticated capture; no number/code was entered.
The post-login images are labeled illustrations with placeholders. All images
were visually inspected. Actual personal notifications/messages and credentials
are excluded from the repository. English and Russian READMEs provide reciprocal
language links and OS-specific setup; image provenance is in docs/images/README.md.

## Limits of the evidence

- Live send/edit/delete was intentionally not performed against the user's
  account. Telegram's live permissions/edit windows/rate limits still apply.
- Linux/macOS and Python 3.12/3.13 checks are configured in GitHub Actions; their
  actual status must be read from the workflow, not inferred from Windows tests.
- Docker Engine was unavailable locally. Container build/login is not verified
  here; Windows DPAPI sessions cannot be copied into a Linux container.
- No public HTTPS/OAuth gateway for ChatGPT web is deployed by this project.
- The supplied desktop toast's cause was not reproduced. Source and installed
  runtime contain no toast sender or background Telegram update subscription.
  Telegram Web/client notifications are a possible separate source; this release
  does not claim an OS notification permission was changed.
