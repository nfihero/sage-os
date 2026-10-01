"""Model providers: any OpenAI-compatible endpoint (llama.cpp, Ollama, LM Studio, cloud APIs).

Sage OS doesn't run models itself (D4); it lists what each endpoint serves and, later, lets an
agent or task pick one. API keys are resolved at call time from an environment variable or the
owning app's own file -- never stored in config.toml, logged, or sent to the browser.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import httpx


@dataclass
class ModelProvider:
    id: str
    label: str
    base_url: str                      # including the version prefix, e.g. http://127.0.0.1:11434/v1
    kind: str = "local"                # "local" | "cloud"
    key_source: str = ""               # where the key comes from, for the UI: "env FOO", "Hermes router"
    key: Callable[[], str | None] = field(default=lambda: None, repr=False)

    def info(self) -> dict:
        return {"id": self.id, "label": self.label, "base_url": self.base_url, "kind": self.kind,
                "key_source": self.key_source or None,
                "key_present": bool(self.key()) if self.key_source else None}

    async def models(self, timeout: float = 3.0) -> list[dict]:
        """GET {base_url}/models -> [{"id", "state"}]; state is llama.cpp's load status when given."""
        key = self.key()
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.get(f"{self.base_url.rstrip('/')}/models",
                            headers={"Authorization": f"Bearer {key}"} if key else {})
            r.raise_for_status()
            body = r.json()
        rows = body.get("data", []) if isinstance(body, dict) else []
        return [{"id": m.get("id"), "state": (m.get("status") or {}).get("value")}
                for m in rows if isinstance(m, dict) and m.get("id")]
