# Third-party notices / Уведомления о сторонних компонентах

[English](#english) | [Русский](#русский)

## English

Telegram MCP's own source code is licensed under MIT; see [LICENSE](LICENSE).
Third-party dependencies and Telegram materials retain their own rights and
licenses. The project's MIT license does not relicense them.

### Direct runtime dependencies

This inventory was checked against the actual license files and metadata of
these installed versions on 2026-10-06. It covers the five direct runtime
requirements, not every transitive dependency or native binary. Uvicorn is a
version range in the project; the inspected lock/runtime version is shown here.

| Component | Inspected version | Observed license | Primary version source |
| --- | --- | --- | --- |
| Telethon | 1.45.0 | MIT; copyright 2016–Present LonamiWebs | [PyPI](https://pypi.org/project/Telethon/1.45.0/) |
| MCP Python SDK (`mcp`) | 1.30.0 | MIT; copyright 2024 Anthropic, PBC | [PyPI](https://pypi.org/project/mcp/1.30.0/) |
| python-dotenv | 1.2.4 | BSD-3-Clause; notices for Saurabh Kumar, Ted Tieken and Jacob Kaplan-Moss | [PyPI](https://pypi.org/project/python-dotenv/1.2.4/) |
| Uvicorn | 0.54.0 | BSD-3-Clause; copyright 2017–present Encode OSS Ltd. | [PyPI](https://pypi.org/project/uvicorn/0.54.0/) |
| pywin32 (Windows only) | 312 | Metadata says PSF; the wheel contains several component licenses, described below | [PyPI](https://pypi.org/project/pywin32/312/) |

MIT requires retaining the original copyright and permission notices in copies
or substantial portions. BSD-3-Clause requires retaining copyright, conditions
and disclaimers in source distributions and reproducing them in accompanying
materials for binary distributions; names cannot be used for endorsement
without permission. Preserve the complete original license texts when
redistributing these components. This summary does not replace those texts.

### pywin32 contains multiple licenses

Its PSF metadata is not a complete inventory of the wheel:

- `win32`, `com` and Pythonwin include BSD-3-Clause notices for Mark Hammond
  and, for COM, Greg Stein.
- Bundled `adodbapi` is **LGPL-2.1-or-later**. This is explicit in the
  [build 312 source header](https://raw.githubusercontent.com/mhammond/pywin32/b312/adodbapi/adodbapi.py).
  The wheel includes its Python source and LGPL text. Redistribution
  must preserve its notices and license; object-only distribution requires
  corresponding library source. A combined executable that uses it also needs
  assessment of the LGPL replacement/relinking requirements. Mere aggregation
  does not automatically relicense independent MCP code.
- The bundled IDLE license file includes historical PSF, BeOpen, CNRI and CWI
  Python agreements. Keep those agreements and notices; applicable terms for
  modified derivatives require a summary of changes.
- Scintilla includes a historical permissive notice for Neil Hodgson, requiring
  its copyright in copies and copyright/permission notice in supporting
  documentation. Use the included text rather than assuming a modern MIT text.
- MAPIStubLibrary includes MIT terms and a Microsoft copyright notice.
- ISAPI includes a Blackdog Software permissive notice in `isapicon.py`, with
  copyright/documentation and advertising-name restrictions.

Telegram MCP imports Windows security/DPAPI modules (`win32api`, `win32con`,
`win32security`, `win32crypt` and `ntsecuritycon`), not `adodbapi`, Pythonwin or
ISAPI. The full pywin32 wheel still includes the other components.

### Distribution scope and Telegram materials

The project's Python wheel contains its own package and metadata, and declares
dependencies for separate installation. It does not vendor dependency code.
If distributing a complete runtime, frozen application or container, include
the original licenses/notices for **all** shipped components and fulfill any
applicable source/replacement requirements. Recheck transitive dependencies and
native binary notices for that actual bundle; this direct-dependency inventory
is not a certification of complete distribution compliance.

No vendored official Telegram client source tree was found in the tracked repository files.
`docs/images/telegram-login.png` is an unauthenticated screenshot of
`my.telegram.org/auth`, including Telegram website UI/artwork; those original
materials are third-party material, not granted MIT rights by this project.
The other two setup PNGs are clearly labelled original illustrations with
placeholder values. See [image provenance](docs/images/README.md).
Telegram names and brands identify the service; this is an unofficial project.

## Русский

Собственный исходный код Telegram MCP распространяется по MIT; см.
[LICENSE](LICENSE). Зависимости и материалы Telegram сохраняют свои права и
лицензии. MIT этого проекта не меняет их лицензии.

### Прямые зависимости времени выполнения

Перечень проверен по реальным файлам лицензий и метаданным установленных версий
2026-10-06. Он охватывает пять прямых зависимостей, а не все транзитивные
зависимости или нативные библиотеки. В проекте Uvicorn задан диапазоном версий;
в таблице указана проверенная версия из зафиксированной среды.

| Компонент | Проверенная версия | Обнаруженная лицензия | Первоисточник версии |
| --- | --- | --- | --- |
| Telethon | 1.45.0 | MIT; copyright 2016–Present LonamiWebs | [PyPI](https://pypi.org/project/Telethon/1.45.0/) |
| MCP Python SDK (`mcp`) | 1.30.0 | MIT; copyright 2024 Anthropic, PBC | [PyPI](https://pypi.org/project/mcp/1.30.0/) |
| python-dotenv | 1.2.4 | BSD-3-Clause; уведомления Saurabh Kumar, Ted Tieken и Jacob Kaplan-Moss | [PyPI](https://pypi.org/project/python-dotenv/1.2.4/) |
| Uvicorn | 0.54.0 | BSD-3-Clause; copyright 2017–present Encode OSS Ltd. | [PyPI](https://pypi.org/project/uvicorn/0.54.0/) |
| pywin32 (только Windows) | 312 | В метаданных указана PSF; wheel содержит несколько лицензий компонентов, см. ниже | [PyPI](https://pypi.org/project/pywin32/312/) |

MIT требует сохранять исходные уведомления об авторских правах и разрешениях в
копиях или существенных частях кода. BSD-3-Clause требует сохранять уведомления,
условия и отказ от гарантий в исходниках, а при распространении бинарников —
в сопроводительных материалах; имена авторов нельзя использовать для одобрения
продукта без разрешения. При распространении компонентов сохраняйте полные
оригинальные тексты лицензий. Этот перечень их не заменяет.

### В pywin32 несколько лицензий

Указание PSF в метаданных не описывает весь состав wheel:

- `win32`, `com` и Pythonwin содержат BSD-3-Clause уведомления Mark Hammond,
  а COM — также Greg Stein.
- Включённый `adodbapi` использует **LGPL-2.1-or-later**, что прямо указано в
  [заголовке исходника сборки 312](https://raw.githubusercontent.com/mhammond/pywin32/b312/adodbapi/adodbapi.py).
  Wheel включает Python-исходники и текст LGPL. При распространении
  нужно сохранять уведомления и лицензию; распространение только объектного
  кода требует соответствующих исходников библиотеки. Для объединённого
  исполняемого файла, который использует её, нужно также учитывать требования
  LGPL к замене/перелинковке. Простое включение отдельных компонентов в одну
  поставку не меняет автоматически лицензию независимого кода MCP.
- Лицензия включённого IDLE содержит исторические соглашения Python от PSF,
  BeOpen, CNRI и CWI. Сохраняйте соглашения и уведомления; применимые условия
  изменённых производных работ требуют описания изменений.
- Scintilla содержит историческое разрешение Neil Hodgson: copyright сохраняется
  в копиях, copyright и разрешение — в сопроводительной документации. Используйте
  включённый текст, не предполагая современную MIT.
- MAPIStubLibrary содержит MIT и уведомление об авторских правах Microsoft.
- ISAPI содержит разрешение Blackdog Software в `isapicon.py`, с требованиями
  к уведомлениям/документации и ограничением использования имени в рекламе.

Telegram MCP импортирует модули Windows для защиты файлов и DPAPI (`win32api`,
`win32con`, `win32security`, `win32crypt`, `ntsecuritycon`), а не `adodbapi`,
Pythonwin или ISAPI. Однако полный wheel pywin32 содержит и остальные компоненты.

### Состав поставки и материалы Telegram

Python-wheel проекта содержит собственный пакет и метаданные; зависимости
объявлены для отдельной установки. Их код не встроен в wheel MCP.
При распространении готовой среды, исполняемой сборки или контейнера приложите
оригинальные лицензии и уведомления **всех** включённых компонентов и выполните
применимые требования к исходникам и замене библиотек. Для конкретной сборки
отдельно проверьте транзитивные зависимости и нативные библиотеки. Перечень
прямых зависимостей не подтверждает выполнение всех условий полной поставки.

В репозитории не обнаружено встроенного дерева исходников официальных клиентов
Telegram. `docs/images/telegram-login.png` — снимок страницы `my.telegram.org/auth`
без входа, включая интерфейс и рисунок сайта Telegram. Исходные материалы сайта
являются сторонними; MIT проекта не предоставляет прав на них.
Два других PNG для настройки — явно обозначенные собственные иллюстрации с
условными значениями. См. [происхождение изображений](docs/images/README.md).
Название Telegram обозначает используемый сервис; проект является неофициальным.
