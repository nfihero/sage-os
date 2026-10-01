"""Client for Hermes' public gateway API (sessions, streaming chat, run approvals).

The per-profile API key is read from the profile's .env at call time and never logged or
returned to the browser.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import AsyncIterator

import httpx


def _read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _read_model_block(path: Path) -> dict[str, str]:
    """Scalar keys of the top-level ``model:`` mapping in a Hermes config.yaml (no YAML dependency)."""
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    inside = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            inside = line.rstrip() == "model:"
            continue
        if inside and ":" in line:
            k, v = line.strip().split(":", 1)
            v = v.split(" #", 1)[0].strip().strip('"').strip("'")
            if v:
                out[k.strip()] = v
    return out


class HermesAPI:
    def __init__(self, gateway: str, hermes_home: Path):
        self.gateway = gateway.rstrip("/")
        self.home = hermes_home

    def _profile_dir(self, profile: str) -> Path:
        return self.home / ("profiles/" + profile if profile != "default" else "")

    def _key(self, profile: str) -> str | None:
        env = self._profile_dir(profile) / ".env"
        return _read_env(env).get("API_SERVER_KEY") or _read_env(self.home / ".env").get("API_SERVER_KEY")

    def _runtime_pin(self, profile: str) -> dict:
        """Pin each turn to the profile's configured model/provider.

        Workaround for a Hermes api_server bug: from the second turn on, the session row's stored
        model makes the gateway re-resolve the *resolved* provider name ("custom", which is what
        llamacpp/ollama/vllm aliases become) instead of the configured alias, and bare "custom"
        falls back to the "no-key-required" placeholder, so the managed llama.cpp router answers
        401. An explicit provider+model with require_model_lock takes the lock branch, which
        resolves the configured alias (and its real key) on every turn. Read per call, so a model
        switch in Hermes is picked up on the next turn. Side effect: a locked turn skips Hermes'
        fallback_model chain.
        """
        cfg = _read_model_block(self._profile_dir(profile) / "config.yaml")
        model, provider = cfg.get("default"), cfg.get("provider")
        if not model or not provider or provider == "auto":
            return {}
        return {"model": model, "provider": provider, "require_model_lock": True}

    def _url(self, profile: str, path: str) -> str:
        return f"{self.gateway}/p/{profile}{path}"

    def _headers(self, profile: str) -> dict:
        key = self._key(profile)
        return {"Authorization": f"Bearer {key}"} if key else {}

    async def messages(self, profile: str, session_id: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(self._url(profile, f"/api/sessions/{session_id}/messages"), headers=self._headers(profile))
            r.raise_for_status()
            body = r.json()
        return body.get("data", body if isinstance(body, list) else [])

    async def create_session(self, profile: str, title: str | None = None) -> dict:
        payload = {"source": "api_server"}
        if title:
            payload["title"] = title
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(self._url(profile, "/api/sessions"), headers=self._headers(profile), json=payload)
            r.raise_for_status()
            body = r.json()
        return body.get("session", body)

    async def chat_stream(self, profile: str, session_id: str, message: str) -> AsyncIterator[tuple[str, dict]]:
        """Yields (event_name, payload) from the SSE stream until the run ends."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=None)) as c:
            async with c.stream("POST", self._url(profile, f"/api/sessions/{session_id}/chat/stream"),
                                headers=self._headers(profile) | {"Accept": "text/event-stream"},
                                json={"message": message, **self._runtime_pin(profile)}) as r:
                if r.status_code >= 400:
                    body = (await r.aread()).decode(errors="replace")
                    raise RuntimeError(f"Hermes returned {r.status_code}: {body[:300]}")
                name, data = "message", []
                async for line in r.aiter_lines():
                    if line.startswith("event:"):
                        name = line[6:].strip()
                    elif line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif line == "" and data:
                        raw = "\n".join(data)
                        try:
                            payload = json.loads(raw)
                        except ValueError:
                            payload = {"raw": raw}
                        yield name, payload
                        name, data = "message", []

    async def approve(self, profile: str, run_id: str, choice: str, request_id: str | None = None) -> dict:
        body = {"choice": choice}
        if request_id:
            body["request_id"] = request_id
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(self._url(profile, f"/v1/runs/{run_id}/approval"), headers=self._headers(profile), json=body)
            r.raise_for_status()
            return r.json()

    async def stop(self, profile: str, run_id: str) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(self._url(profile, f"/v1/runs/{run_id}/stop"), headers=self._headers(profile), json={})
