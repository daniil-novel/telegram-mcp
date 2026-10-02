from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.exists():
            info = item.lstat()
            if item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Secret storage must not use symlinks or Windows junctions.")


def protect_path(path: Path) -> None:
    """Restrict to current account (+SYSTEM on Windows), never broad chmod on parents."""
    reject_links(path)
    if os.name == "nt":
        import ntsecuritycon
        import win32api
        import win32con
        import win32security

        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        try:
            user_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        finally:
            token.Close()
        system_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid)
        acl = win32security.ACL()
        flags = win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE if path.is_dir() else 0
        for sid in (user_sid, system_sid):
            acl.AddAccessAllowedAceEx(
                win32security.ACL_REVISION_DS, flags, ntsecuritycon.FILE_ALL_ACCESS, sid
            )
        win32security.SetNamedSecurityInfo(
            str(path),
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION
            | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            None,
            None,
            acl,
            None,
        )
    else:
        if path.stat().st_uid != os.getuid():
            raise PermissionError("Secret storage must be owned by the current user.")
        path.chmod(0o700 if path.is_dir() else 0o600)


class SessionStore:
    """StringSession outside the project: DPAPI on Windows, owner-only file on POSIX."""

    def __init__(self, directory: Path):
        self.directory = directory.absolute()
        reject_links(self.directory)
        project = Path(__file__).resolve().parents[2]
        if self.directory.is_relative_to(project):
            raise ValueError("TELEGRAM_SESSION_DIR must be outside the project.")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        protect_path(self.directory)
        self.path = self.directory / ("session.dpapi" if os.name == "nt" else "session.secret")

    def load(self) -> str:
        reject_links(self.path)
        if not self.path.exists():
            raise ValueError(
                "No local Telegram session. Run the 'auth' command in your own terminal."
            )
        protect_path(self.path)
        blob = self.path.read_bytes()
        if os.name == "nt":
            import win32crypt

            blob = win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1]
        return blob.decode("ascii")

    def save(self, session: str) -> None:
        reject_links(self.path)
        blob = session.encode("ascii")
        if os.name == "nt":
            import win32crypt

            blob = win32crypt.CryptProtectData(blob, "Telegram read-only MCP", None, None, None, 1)
        fd, name = tempfile.mkstemp(prefix="session-", suffix=".tmp", dir=self.directory)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
            protect_path(temporary)
            os.replace(temporary, self.path)
            protect_path(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def is_private(self) -> bool:
        if os.name == "nt":
            return self.path.exists()  # DACL is enforced by load/save; content is DPAPI encrypted.
        return self.path.exists() and stat.S_IMODE(self.path.stat().st_mode) == 0o600
