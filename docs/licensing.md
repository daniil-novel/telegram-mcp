# Licensing, attribution and platform rules

**English** · [Русский](licensing.ru.md) · [README](../README.md)

Sources checked on **2026-10-06**. This explanation does not change [LICENSE](../LICENSE) or certify compliance with Telegram's terms.

## Code and author credit

This project's original code and documentation use standard **MIT**, with `Copyright (c) 2026 daniil-novel`. Copies or substantial portions must retain its copyright and permission notices. Include the complete LICENSE in source/package distributions; a link alone is not a replacement. [MIT text](https://opensource.org/license/mit).

MIT allows commercial use and distribution under other terms, including without publishing source. It does **not** make the whole incorporating application MIT-licensed or require visible credit in every UI. Preserve other components' licenses too. [MIT overview](https://choosealicense.com/licenses/mit/).

Practical attribution: keep LICENSE with vendored code or third-party-license materials. Identify your additions separately, without replacing the original author's notice. “Includes Unofficial Telegram MCP by daniil-novel” with a project link is welcome as optional acknowledgment, not an extra license condition. A source-availability requirement would need a separately chosen license, not an invented MIT clause.

## Independent implementation and third-party rights

The project wraps documented MTProto operations through the **third-party Telethon library**, using a fixed MCP interface and code guards. It is not Telegram's official SDK or an endorsed Telegram/OpenAI product. Telethon 1.45.0 has its own MIT license and author notice; retain these when redistributing its code/package. [Telethon license](https://github.com/LonamiWebs/Telethon/blob/v1/LICENSE).

The Unofficial Telegram name and original diagrams do not grant rights to Telegram marks, website artwork or chat content. Underlying Telegram artwork is excluded from this project's MIT grant. The official Telegram logo is not this application's logo. See [Setup images](images/README.md) and [third-party notices](../THIRD_PARTY_NOTICES.md).

## Platform-use questions remain unresolved

[API Terms §1.5](https://core.telegram.org/api/terms) restrict AI/data uses. The [content terms](https://telegram.org/tos/content-licensing) describe possible exceptions with individual, explicit, informed, ongoing consent from every relevant user, limited to the specific content/context. Consent is not transferable across chats. We recommend respecting withdrawal so consent remains ongoing.

Our recommendation: do not treat your API ID, account access, local inference or anonymization as permission for AI processing. The utility does not collect or verify such consent. Technical Codex compatibility is not platform authorization. This is not a conclusion that every AI inference is unlawful; the actual context and applicable terms need review.

Two further gaps need review against [API Terms §§1.4 and 3.3](https://core.telegram.org/api/terms): this utility does not send read/typing/presence updates and does not implement sponsored-channel-message support. Neither feature is claimed to satisfy Telegram's client obligations. A user consent exception should not be assumed to waive unrelated client requirements.

MIT's warranty/liability disclaimer is subject to applicable law. It does not bind Telegram, license others' content or prevent a rights holder from making a claim. No project document can guarantee that Telegram will never object. Recheck current terms and seek qualified advice when a proposed deployment depends on a legal interpretation.
