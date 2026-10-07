"""Google Drive connector (DECISIONS D22.5): Google Docs, Sheets and Slides read through the Drive API.

Drive for desktop shows Google-native files as small stubs (.gdoc, .gsheet, .gslides) whose text lives only
online; Windows can't even read them. With the user's consent (OAuth, read-only scope) Sage OS finds each
stub's file in Drive by its path and exports it as Word, Excel or PowerPoint, which the source library then
copies and indexes like any other file. Drive itself is never written.

  * The OAuth client is the user's own (a "Desktop app" client from Google Cloud, in testing mode), saved
    as data/google-oauth-client.json. A public release needs Google's verification for this scope (D22).
  * The refresh token is kept in data/google-token.json (data/ is never committed) and never leaves the
    hub: not logged, not sent to the browser.
  * Sign-in happens in the user's browser on Google's own page; Sage OS never sees the password.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

SCOPE = "https://www.googleapis.com/auth/drive.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/drive/v3"
# stub extension -> (Google mime type, export mime type, extension of the exported copy)
NATIVE = {
    ".gdoc": ("application/vnd.google-apps.document",
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    ".gsheet": ("application/vnd.google-apps.spreadsheet",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    ".gslides": ("application/vnd.google-apps.presentation",
                 "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
}
ROOTS = {"My Drive": "root"}        # top folders of a Drive for desktop mount that map to Drive's own tree
EXPORT_LIMIT = 10 * 1024 * 1024     # Drive refuses exports above 10 MB


class DriveError(Exception):
    pass


class GoogleDrive:
    def __init__(self, client_path: Path, token_path: Path):
        self.client_path, self.token_path = Path(client_path), Path(token_path)
        self.lock = threading.Lock()
        self._pending: dict[str, tuple[str, str, float]] = {}    # state -> (verifier, redirect, created)
        self._folders: dict[tuple[str, str], str | None] = {}   # (parent id, name) -> folder id, per sync

    # -- state ---------------------------------------------------------------------------------------
    def _client(self) -> dict | None:
        try:
            raw = json.loads(self.client_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        c = raw.get("installed") or raw.get("web") or {}
        return c if c.get("client_id") and c.get("client_secret") else None

    def _token(self) -> dict | None:
        try:
            return json.loads(self.token_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _save_token(self, tok: dict):
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.token_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(tok), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.token_path)

    def status(self) -> dict:
        tok = self._token()
        return {"configured": self._client() is not None, "connected": bool(tok and tok.get("refresh_token")),
                "client_file": str(self.client_path), "account": (tok or {}).get("account")}

    @property
    def connected(self) -> bool:
        return self.status()["connected"]

    # -- consent (OAuth 2.0 for installed apps, with PKCE) ----------------------------------------------
    def start(self, redirect: str) -> str:
        c = self._client()
        if not c:
            raise DriveError(f"No Google OAuth client found at {self.client_path}.")
        state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        now = time.time()
        with self.lock:
            self._pending = {k: v for k, v in self._pending.items() if now - v[2] < 900}
            self._pending[state] = (verifier, redirect, now)
        return AUTH_URL + "?" + urlencode({
            "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
            "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
            "access_type": "offline", "prompt": "consent"})

    def finish(self, code: str, state: str) -> None:
        with self.lock:
            pending = self._pending.pop(state, None)
        if not pending or time.time() - pending[2] > 900:
            raise DriveError("This sign-in link expired or wasn't started from Sage OS. Start again from Sources.")
        verifier, redirect, _ = pending
        c = self._client()
        if not c:
            raise DriveError(f"The Google OAuth client at {self.client_path} is missing or unreadable.")
        r = httpx.post(TOKEN_URL, data={"client_id": c["client_id"], "client_secret": c["client_secret"], "code": code,
                                        "code_verifier": verifier, "grant_type": "authorization_code",
                                        "redirect_uri": redirect}, timeout=20)
        if r.status_code != 200:
            raise DriveError(f"Google refused the sign-in ({r.status_code}).")
        tok = r.json()
        if not tok.get("refresh_token"):
            raise DriveError("Google didn't grant lasting access. Remove Sage OS at myaccount.google.com/permissions and try again.")
        tok["expires_at"] = time.time() + int(tok.get("expires_in", 0)) - 60
        self._save_token(tok)
        try:                                       # which account, so the UI can say so (no other personal data)
            about = self._get("/about", {"fields": "user(emailAddress)"})
            tok["account"] = about.get("user", {}).get("emailAddress")
            self._save_token(tok)
        except DriveError:
            pass

    def disconnect(self) -> None:
        tok = self._token()
        if tok:
            try:
                httpx.post("https://oauth2.googleapis.com/revoke", data={"token": tok.get("refresh_token") or tok.get("access_token")}, timeout=10)
            except httpx.HTTPError:
                pass
        self.token_path.unlink(missing_ok=True)

    # -- API -------------------------------------------------------------------------------------------
    def _access(self) -> str:
        with self.lock:
            tok = self._token()
            if not tok or not tok.get("refresh_token"):
                raise DriveError("Google Drive isn't connected.")
            if tok.get("access_token") and tok.get("expires_at", 0) > time.time():
                return tok["access_token"]
            c = self._client()
            if not c:
                raise DriveError(f"No Google OAuth client found at {self.client_path}.")
            r = httpx.post(TOKEN_URL, data={"client_id": c["client_id"], "client_secret": c["client_secret"],
                                            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=20)
            if r.status_code != 200:
                raise DriveError("Google Drive access has expired or was revoked. Connect it again from Sources.")
            new = r.json()
            tok.update(access_token=new["access_token"], expires_at=time.time() + int(new.get("expires_in", 0)) - 60)
            self._save_token(tok)
            return tok["access_token"]

    def _get(self, path: str, params: dict | None = None, raw: bool = False):
        r = httpx.get(API + path, params=params, headers={"Authorization": f"Bearer {self._access()}"}, timeout=60)
        if r.status_code == 404:
            raise DriveError("not found in Drive")
        if r.status_code == 403 and "exportSizeLimitExceeded" in r.text:
            raise DriveError("too large for Google to export (over 10 MB)")
        if r.status_code != 200:
            raise DriveError(f"Drive API error {r.status_code}")
        return r.content if raw else r.json()

    @staticmethod
    def _q(name: str) -> str:
        return name.replace("\\", "\\\\").replace("'", "\\'")

    def _child(self, parent: str, name: str, mime: str | None = None) -> dict | None:
        q = f"'{parent}' in parents and name = '{self._q(name)}' and trashed = false"
        q += f" and mimeType = '{mime}'" if mime else " and mimeType = 'application/vnd.google-apps.folder'"
        files = self._get("/files", {"q": q, "fields": "files(id,name,mimeType,modifiedTime)", "pageSize": 10,
                                     "orderBy": "modifiedTime desc"}).get("files", [])
        return files[0] if files else None

    def begin_sync(self):
        self._folders.clear()

    def resolve(self, rel: str) -> dict:
        """A Drive-for-desktop path such as "My Drive/Deal Club/Draft Email.gdoc" -> the Drive file
        {id, name, mimeType, modifiedTime}. Raises DriveError if it can't be found."""
        parts = rel.split("/")
        ext = Path(parts[-1]).suffix.lower()
        if ext not in NATIVE:
            raise DriveError("not a Google Docs, Sheets or Slides file")
        if parts[0] not in ROOTS:
            raise DriveError(f"files under {parts[0]!r} can't be looked up in Drive yet")
        parent = ROOTS[parts[0]]
        for folder in parts[1:-1]:
            key = (parent, folder)
            if key not in self._folders:
                hit = self._child(parent, folder)
                self._folders[key] = hit["id"] if hit else None
            parent = self._folders[key]
            if parent is None:
                raise DriveError(f"folder {folder!r} not found in Drive")
        hit = self._child(parent, parts[-1][: -len(ext)], NATIVE[ext][0])
        if not hit:
            raise DriveError("not found in Drive")
        return hit

    def export(self, file_id: str, ext: str) -> bytes:
        data = self._get(f"/files/{file_id}/export", {"mimeType": NATIVE[ext][1]}, raw=True)
        if len(data) > EXPORT_LIMIT:
            raise DriveError("export too large")
        return data
