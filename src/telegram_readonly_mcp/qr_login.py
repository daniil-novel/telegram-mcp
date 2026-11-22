from __future__ import annotations

import asyncio
from base64 import urlsafe_b64encode
from datetime import UTC, datetime

import qrcode
from telethon import functions, types

from .exceptions import PublicError
from .guard import GuardedTelegramClient


class QrWindow:
    def __init__(self, lang: str):
        import tkinter as tk

        self.closed = False
        self.window = tk.Tk()
        self.window.withdraw()
        self.window.title("Вход в Telegram MCP" if lang == "ru" else "Sign in to Telegram MCP")
        self.window.resizable(False, False)
        directions = (
            "На телефоне открой Telegram → Настройки → Устройства → Подключить устройство.\n"
            "Сканируй этот QR в нужном аккаунте и подтверди вход."
            if lang == "ru"
            else "On your phone, open Telegram → Settings → Devices → Link Desktop Device.\n"
            "Scan this QR in the correct account and confirm the login."
        )
        tk.Label(self.window, text=directions, wraplength=460, padx=20, pady=12).pack()
        self.canvas = tk.Canvas(self.window, background="white", highlightthickness=0)
        self.canvas.pack()
        self.countdown = tk.Label(self.window, pady=8)
        self.countdown.pack()
        tk.Button(
            self.window, text="Отмена" if lang == "ru" else "Cancel", command=self.cancel
        ).pack(pady=(0, 12))
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.bind("<Escape>", lambda _event: self.cancel())
        self.lang = lang

    def cancel(self) -> None:
        self.closed = True
        self.window.withdraw()

    def show(self, token: bytes) -> None:
        # The URI and image exist in memory only, never in logs, files or a browser.
        value = urlsafe_b64encode(token).decode("ascii").rstrip("=")
        code = qrcode.QRCode(border=4)
        code.add_data(f"tg://login?token={value}")
        matrix = code.get_matrix()
        pixel = 8
        size = len(matrix) * pixel
        self.canvas.configure(width=size, height=size)
        self.canvas.delete("all")
        for y, row in enumerate(matrix):
            for x, dark in enumerate(row):
                if dark:
                    self.canvas.create_rectangle(
                        x * pixel,
                        y * pixel,
                        (x + 1) * pixel,
                        (y + 1) * pixel,
                        fill="black",
                        width=0,
                    )
        self.window.deiconify()
        self.window.lift()

    async def wait_for_scan(self, event: asyncio.Event, expires: datetime) -> bool:
        while not self.closed and not event.is_set():
            seconds = (expires - datetime.now(UTC)).total_seconds()
            if seconds <= 0:
                return False
            self.countdown.configure(
                text=f"Обновление QR через {int(seconds) + 1} сек."
                if self.lang == "ru"
                else f"QR refreshes in {int(seconds) + 1}s"
            )
            self.window.update()
            await asyncio.sleep(0.1)
        if self.closed:
            raise PublicError("Окно QR закрыто." if self.lang == "ru" else "QR window closed.")
        return True

    def close(self) -> None:
        self.window.destroy()


async def authorize_qr(client: GuardedTelegramClient, lang: str) -> None:
    try:
        window = QrWindow(lang)
    except Exception:
        raise PublicError(
            "Не удалось открыть окно QR. Запусти вход снова и выбери код."
            if lang == "ru"
            else "Could not open the QR window. Run auth again and choose code."
        ) from None
    request = functions.auth.ExportLoginTokenRequest(client.api_id, client.api_hash, [])
    try:
        for _ in range(3):
            with client.watch_login_token() as scanned:
                async with asyncio.timeout(20):
                    response = await client(request)
                if not isinstance(response, types.auth.LoginToken):
                    break
                window.show(response.token)
                if not await window.wait_for_scan(scanned, response.expires):
                    continue
            # Return to no-updates mode before confirming the login or switching DCs.
            async with asyncio.timeout(20):
                response = await client(request)
            if not isinstance(response, types.auth.LoginToken):
                break
        else:
            raise PublicError(
                "Время QR вышло. Запусти вход снова."
                if lang == "ru"
                else "The QR session timed out. Run auth again."
            )
        async with asyncio.timeout(20):
            if isinstance(response, types.auth.LoginTokenMigrateTo):
                await client._switch_dc(response.dc_id)
                response = await client(functions.auth.ImportLoginTokenRequest(response.token))
        if not isinstance(response, types.auth.LoginTokenSuccess):
            raise PublicError(
                "Telegram не подтвердил QR. Запусти вход снова."
                if lang == "ru"
                else "Telegram did not confirm the QR scan. Run auth again."
            )
        await client._on_login(response.authorization.user)
    finally:
        window.close()
