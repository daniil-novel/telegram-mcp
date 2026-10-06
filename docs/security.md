# Security model

**English** · [Русский](security.ru.md) · [README](../README.md)

Unofficial Telegram MCP applies a limited local-account boundary, not a promise of complete security. This guide distinguishes code-enforced restrictions, GitHub repository controls and responsibilities of the connected client. For private reports and incident response, use [SECURITY.md](../SECURITY.md).

## Data flow and trust

```text
Your terminal: local credentials and authorization
        ↓
Local session + configured chat/action permissions
        ↓
Fixed MCP tools → guarded Telegram RPCs → Telegram
        ↓
Permitted text/captions/metadata → MCP client → its model/history
```

Application credentials and login are local. **Permitted message content, personal data and metadata still reach the client.** The server does not integrate directly with a model provider, but an MCP client can upload/store its responses. The [proposed privacy layer](../README.md#planned-privacy-layer) is a roadmap, not available functionality.

Telegram's session itself has account powers. The code's read-only mode is not a Telegram-issued token scope. Copying the session into a different client bypasses this program's guard; the OS user, installed Python/dependencies, MCP client and maintainer-reviewed source are trusted components.

## What the implementation enforces

| Threat or concern | Existing control | Remaining boundary |
| --- | --- | --- |
| Unexpected Telegram mutation | Fixed read tools; exact MTProto request-class allowlist, nested-wrapper checks and guards at both call/send boundaries | Modified code, compromised runtime or a stolen session is outside this boundary. |
| Writes to unwanted destinations | Disabled by default; separate exact write-ID allowlist; denylist wins and read ACL still applies | Once enabled, a permitted client can request configured writes. The server cannot independently prove a human approved each call. |
| Editing/deleting others' messages | Backend ownership checks for own outgoing messages; bounded batches and plain-text edits | Deletion may be irreversible; Telegram also applies its own permissions. |
| Extra write capabilities | Exact bounded request shape: no media, scheduling, impersonation, paid sends or arbitrary RPCs | A future capability needs explicit design and tests; annotations alone are only hints. |
| Cursor tampering/scope switching | HMAC-authenticated pagination bound to the query/ACL and process | Cursors are not an anonymizer or encrypted storage. Restarting invalidates them. |
| Session/config exposure | Hidden interactive authorization; external session location; private file ownership/permissions; Windows DPAPI; symlink/junction rejection | Linux/macOS sessions are not encrypted at rest. `.env` values and in-memory session data remain sensitive. |
| HTTP access by strangers | Bearer authentication before MCP calls; explicit Host/Origin policy; loopback default; bounded request body | Bearer holders share one account's permissions. This is not per-user authorization, TLS termination or a public OAuth service. |
| Prompt injection in chat content | Responses label `content_is_untrusted=true`; server/client skill warns about messages/titles/captions; ACL/RPC checks still apply | Labels/instructions are advisory, not a complete detector. A client can misuse allowed content, other tools or enabled writes. |
| Secrets echoed in error paths | MCP validation/unexpected backend errors use value-free diagnostics; input models hide values in error strings; logging is quiet | Successful permitted reads deliberately return text/metadata. Third-party clients and debug instrumentation have separate leak risks. |
| SQL or command text in messages | No SQL query backend, `eval`, shell-execution or URL-fetching tool for message content; sessions use Telethon `StringSession` | A downstream client that executes text introduces its own boundary. SQL-looking text is ordinary data here. |
| Unwanted background behavior | Background message updates, monitoring, read receipts and desktop notification production are absent | A connected client, browser or another integration can create notifications or store history. |

Read ACLs filter MCP output and targeted reads. Fetching the dialog list may still put denied-chat metadata/last messages in backend memory. Use a separate Telegram account when that distinction matters.

The relevant implementation is in [guard.py](../src/telegram_readonly_mcp/guard.py), [service.py](../src/telegram_readonly_mcp/service.py), [server.py](../src/telegram_readonly_mcp/server.py) and [security.py](../src/telegram_readonly_mcp/security.py). Review the actual revision you install.

## Safe use

- Start with stdio, read-only mode and the narrowest read allowlist you need. Review who can see the client's model responses/history.
- Keep login, session files and `.env` out of chat, issues, PRs, screenshots and shared/cloud-synced folders. Use the documented local `protect-env` command.
- Enable writes only for explicit destinations; inspect the exact chat, text and action in your client before approval. On unknown outcomes, read the targeted history before considering a retry.
- Keep HTTP loopback-only where possible. Remote deployments need their own secure transport, firewall and caller controls; a token does not create isolation between users.
- Do not run an unknown fork/branch on your real account. A virtual environment isolates packages, not access to your files/network. Use a disposable environment without real credentials.

## Repository review and automation

Public visibility permits cloning and forking; it does not grant original-repository write access. Contributors use **fork → feature branch → PR to `main`**, as documented in [CONTRIBUTING.md](../CONTRIBUTING.md). Only authorized maintainers can merge or change GitHub settings. Protecting the original repository does not make every public fork safe to run.

GitHub secret scanning/push protection, Dependabot alerts/security updates and private vulnerability reporting are enabled. GitHub's generic non-provider secret patterns are not enabled; custom or arbitrary Telegram credentials can escape provider-pattern detection. Fork workflows require approval for external contributors, and default Actions token permissions are read-only with Actions PR approval disabled.

A narrowly scoped branch exception lets the official Dependabot app create/update its dependency branches under `dependabot/`, including nested paths. It grants no exception for `main` and no automatic merge: the owner reviews Dependabot PRs, and the mandatory checks and CodeQL findings gate still apply.

The [CI workflow](../.github/workflows/ci.yml) runs account-free tests, lint, formatting and build checks across Windows/Linux/macOS. Configuration is not proof of a passing run: inspect the result for the exact commit in [Actions](https://github.com/daniil-novel/telegram-mcp/actions) and the recorded [validation evidence](../VALIDATION.md). Live Telegram writes and private conversations do not belong in CI fixtures or secrets.

### Main and original-repository branches

Four active GitHub rulesets separate review flexibility from mandatory checks:

- [Main core rules](https://github.com/daniil-novel/telegram-mcp/rules/24572891): changes through a PR, **13 mandatory checks**, up-to-date branches, resolved conversations and linear history. A separate CodeQL findings rule requires security threshold `all` and other-alert threshold `errors_and_warnings`. Force pushes/deletion are blocked. **No bypass actor**, including the owner, is configured for this ruleset.
- [Main review rules](https://github.com/daniil-novel/telegram-mcp/rules/24572892): one code-owner approval, dismissed when changes make it stale. The designated reviewer is **@daniil-novel**. This owner has a **PR-only review exception** so their own maintenance PR can merge after core checks pass.
- [Other original branches](https://github.com/daniil-novel/telegram-mcp/rules/24572895): branches outside `main` and the `dependabot/` namespace are restricted to the maintainer for creation/update/deletion. Community contributors work in forks; these restrictions do not control branches in someone else's fork.
- [Dependabot branches](https://github.com/daniil-novel/telegram-mcp/rules/24574015): only the owner and official Dependabot app (GitHub App ID `29110`) can create/update/delete branches matching `refs/heads/dependabot/*` or `refs/heads/dependabot/**/*`. Both patterns cover direct and nested dependency branches. The bot has no bypass in either `main` ruleset.

Contributor PRs are expected to receive the owner's review. GitHub's review exception is tied to the maintainer actor, not the PR's author; it should be used for the owner's own PRs. It does not bypass the separate core rules or enable direct `main` pushes. The policy does not claim an independent second-person review of owner-authored changes.

Rules/settings are server-side state, not copied by cloning. The administrator can change them; a compromised owner account or authorized settings change is outside this protection. Review [current rules](https://github.com/daniil-novel/telegram-mcp/rules), exact-commit checks and validation evidence. Automated checks cannot establish whether an intended behavior change is appropriate.

### Configured scanners

| Check | Scope | Limits |
| --- | --- | --- |
| Bandit 1.9.4 | Python source in `src` | Heuristic analysis; finding-free code can still be vulnerable. |
| pip-audit 2.10.1 | Hash-pinned runtime, development and scanner dependency export, checked on Windows/Linux | Known published advisories; platform markers apply and unknown vulnerabilities are not detected. |
| Gitleaks 8.30.1 | Reachable Git history; default patterns plus [Telegram API-hash/StringSession rules](../.gitleaks.toml); diagnostics redact matches | Limited patterns/context; arbitrary passwords and personal data can escape. Binary DPAPI files are not reliably covered. |
| actionlint 1.7.12 | GitHub workflow configuration | Workflow mistakes, not proof that an action/dependency is trustworthy. |
| Dependency review | Dependency changes in PRs; low-or-higher advisory severity blocks | Known advisories and supported dependency graph; not runtime behavior analysis. |
| CodeQL | Python and Actions, `security-extended`, build mode `none` | Configured static queries; it does not test live Telegram accounts, prompt intent or every PII disclosure. |

See [security.yml](../.github/workflows/security.yml) and [codeql.yml](../.github/workflows/codeql.yml). Workflows use pinned action commits and narrowly scoped permissions; CodeQL's analysis job has `security-events: write` to upload results. Regular CI jobs receive no Telegram/model secrets. Dependency audits validate the checked-in [hash-pinned export](../security-requirements.txt) against `uv.lock` and audit it without installing that exported dependency set.

The Python scanner commands are in [CONTRIBUTING.md](../CONTRIBUTING.md#3-run-account-free-checks). If you have installed the specified native tools from [Gitleaks releases](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) and [actionlint releases](https://github.com/rhysd/actionlint/releases/tag/v1.7.12), run from the repository root:

```text
gitleaks git --no-banner --redact=100 --config .gitleaks.toml --log-opts="--all" .
actionlint
```

A configured check or badge is not a passing result; inspect its exact-commit run. Do not disable checks, ignore unexplained findings or create broad allowlists merely to make a PR green.

## What scanners cannot promise

Static analysis and secret-pattern scanning can catch some risky code, known credential formats and vulnerable dependencies. They do not guarantee freedom from bugs, malicious intent, arbitrary passwords, personal data or prompt injection. A SQL string in Telegram is not a SQL injection vulnerability in this server; the relevant question is whether any component later treats it as executable code.

Tests use synthetic data to check enforced boundaries. They cannot establish zero leaks in every library, environment, client or future change. Quiet logs and generic operational errors reduce accidental detail, but debug instrumentation, third-party output and user-provided error text need review. Never paste raw diagnostics publicly.

Dependency/CI changes deserve the same scrutiny as runtime changes: installing a package or running a workflow executes code. Read the diff, lock changes, workflow permissions and action revisions before approving a run or merge. Never expose Telegram/model credentials to untrusted PR jobs. See [GitHub's secure workflow guidance](https://docs.github.com/en/actions/reference/security/secure-use).

For release evidence and unresolved verification limits, consult [VALIDATION.md](../VALIDATION.md). To report a suspected bypass or exposure, use the [private vulnerability form](https://github.com/daniil-novel/telegram-mcp/security/advisories/new) with synthetic reproduction steps.
