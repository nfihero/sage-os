"""Sage OS's own local engine (DECISIONS D22.3, D4.2): Sage OS installs and runs the stock llama.cpp
`llama-server`; it never rewrites it. Users pick a model from a curated catalog that says, for this machine,
whether it fits; the engine then serves it on an OpenAI-compatible endpoint that any connector can use.

  * Hardware: RAM from psutil; graphics cards of any vendor from the OS (sage_os_hub.hardware); Apple Silicon
    shares RAM with the GPU (Metal).
  * Binaries: the official ggml-org/llama.cpp GitHub release for this OS and GPU (CUDA, Vulkan, Metal, CPU),
    checked against the SHA-256 GitHub publishes. Or an existing build named in config ([engine] binary).
  * Models: GGUF files from Hugging Face, resumable, checked against the SHA-256 in catalog.json. Files
    already on disk ([engine] model_dirs) are offered too.
  * Downloads start only from the user's click in the UI.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import psutil

from ..hardware import gpus

CATALOG = Path(__file__).with_name("catalog.json")
RELEASES = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15"
HF_FILE = "https://huggingface.co/{repo}/resolve/main/{file}"
EXE = "llama-server.exe" if sys.platform == "win32" else "llama-server"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CTX = 16384               # per request slot: a book section + its notes fit (K12)
SMALL_CTX = 8192          # a micro model beside a game: chats and light jobs (G1)


class EngineError(Exception):
    pass


def hardware() -> dict:
    """What this computer can run models on."""
    vm = psutil.virtual_memory()
    hw = {"os": {"win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform), "arch": platform.machine().lower(),
          "ram_gb": round(vm.total / 2**30, 1), "ram_free_gb": round(vm.available / 2**30, 1), "gpu": None, "backend": "cpu"}
    if sys.platform == "darwin" and hw["arch"] in ("arm64", "aarch64"):
        hw["gpu"] = {"vendor": "apple", "name": "Apple Silicon (shares memory)", "vram_gb": hw["ram_gb"]}
        hw["backend"] = "metal"
        return hw
    cards = gpus()                          # any vendor, from the OS (G1, D29.1); no nvidia-smi
    if cards:
        g = cards[0]                         # the card with the most memory: the one models run on
        hw["gpu"] = {"vendor": g["vendor"], "name": g["name"], "vram_gb": round(g["vram_bytes"] / 2**30, 1),
                     "driver": g.get("driver")}
        if g["vendor"] == "nvidia":
            hw["backend"] = "cuda"
            return hw
    if sys.platform == "win32":
        hw["backend"] = "vulkan"             # AMD / Intel GPUs; Vulkan builds fall back to CPU if there's none
    return hw


def has_gpu(hw: dict) -> bool:
    """A GPU the engine can use: NVIDIA, Apple Silicon, or one Vulkan reported (a "vulkan" label alone is the build choice)."""
    return hw["backend"] in ("cuda", "metal") or bool(hw.get("gpu"))


def fit(size_bytes: int, hw: dict) -> tuple[str, float]:
    """-> ("fits" | "tight" | "too big", memory needed in GB) for a model file on this machine."""
    need = size_bytes / 2**30 * 1.1 + 1.2       # weights + KV cache for a 16K context (small for small models) + runtime
    if has_gpu(hw):
        need += 0.6                              # a second request slot on GPUs (see start)
    ram, gpu = hw["ram_gb"], hw.get("gpu")
    if hw["backend"] == "metal":
        state = "fits" if need <= ram * 0.65 else "tight" if need <= ram * 0.8 else "too big"
    elif gpu and hw["backend"] in ("cuda", "vulkan") and gpu.get("vram_gb", 0) >= 2:    # a card with its own memory
        vram = gpu["vram_gb"]
        state = "fits" if need <= vram - 0.6 else "tight" if need <= vram + ram * 0.5 else "too big"
    else:
        state = "fits" if need <= ram * 0.6 else "tight" if need <= ram * 0.75 else "too big"   # CPU: slower, still works
    return state, round(need, 1)


def pick_asset(assets: list[dict], tag: str, hw: dict) -> list[dict]:
    """The release files to download for this machine (the build, plus the CUDA runtime on Windows/NVIDIA)."""
    names = {a["name"]: a for a in assets}
    arch = "arm64" if hw["arch"] in ("arm64", "aarch64") else "x64"
    if hw["os"] == "windows":
        if hw["backend"] == "cuda":
            driver = int(str(hw["gpu"].get("driver", "0")).split(".")[0] or 0)
            cuda = "13.4" if driver >= 580 else "12.4"
            want = [f"llama-{tag}-bin-win-cuda-{cuda}-{arch}.zip", f"cudart-llama-bin-win-cuda-{cuda}-{arch}.zip"]
        else:
            want = [f"llama-{tag}-bin-win-{'vulkan' if hw['backend'] == 'vulkan' else 'cpu'}-{arch}.zip"]
    elif hw["os"] == "macos":
        want = [f"llama-{tag}-bin-macos-{arch}.tar.gz"]
    else:
        want = [f"llama-{tag}-bin-ubuntu-{'vulkan-' if hw.get('gpu') else ''}{arch}.tar.gz"]
    return [names[w] for w in want] if all(w in names for w in want) else []


@dataclass
class Job:
    kind: str                 # binary | model
    target: str               # model id or "llama-server"
    total: int = 0
    done: int = 0
    state: str = "running"    # queued | running | done | failed | cancelled
    error: str | None = None
    started: float = field(default_factory=time.time)
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict:
        return {"kind": self.kind, "target": self.target, "total": self.total, "done": self.done, "state": self.state,
                "error": self.error, "started": self.started}


class LocalEngine:
    def __init__(self, root: Path, port: int = 8790, binary: str | None = None, model_dirs: list[Path] | None = None,
                 on_change=None):
        self.root, self.port = Path(root), port
        self.models_dir = self.root / "models"
        self.bin_dir = self.root / "bin"
        self.configured_binary = Path(binary) if binary else None
        self.model_dirs = [self.models_dir] + [Path(d) for d in (model_dirs or [])]
        self.on_change = on_change or (lambda: None)
        self.proc: subprocess.Popen | None = None
        self.serving: dict | None = None          # {"id", "path", "started", "ready"}
        self.jobs: dict[str, Job] = {}
        self.api_key: str | None = None             # per start; only the hub knows it (never sent to the browser)
        self.lock = threading.RLock()
        self._hw: dict | None = None

    # -- facts --------------------------------------------------------------------------------------
    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def hardware(self, refresh: bool = False) -> dict:
        if self._hw is None or refresh:
            self._hw = hardware()
        return self._hw

    def binary(self) -> Path | None:
        if self.configured_binary and self.configured_binary.is_file():
            return self.configured_binary
        found = sorted(self.bin_dir.rglob(EXE)) if self.bin_dir.is_dir() else []
        return found[0] if found else None

    def catalog(self) -> list[dict]:
        hw = self.hardware()
        rows = json.loads(CATALOG.read_text(encoding="utf-8"))
        for m in rows:
            m["fit"], m["need_gb"] = fit(m["size"], hw)
            m["installed"] = (self.models_dir / m["file"]).is_file()
        return rows

    def local_models(self) -> list[dict]:
        """GGUF files already on this computer (the engine's folder plus [engine] model_dirs)."""
        hw, out, seen = self.hardware(), [], set()
        for d in self.model_dirs:
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.gguf")):
                name = p.name.lower()
                if p in seen or "mmproj" in name or name.endswith(".part"):
                    continue
                seen.add(p)
                state, need = fit(p.stat().st_size, hw)
                out.append({"id": "file:" + p.stem, "label": p.stem, "path": str(p), "size": p.stat().st_size,
                            "fit": state, "need_gb": need, "folder": str(d)})
        return out

    def status(self) -> dict:
        b = self.binary()
        with self.lock:
            serving = dict(self.serving) if self.serving else None
            if serving and self.proc and self.proc.poll() is not None:
                serving = None
            return {"hardware": self.hardware(), "binary": str(b) if b else None, "port": self.port,
                    "base_url": self.base_url, "serving": serving,
                    "jobs": {k: j.public() for k, j in self.jobs.items()}}

    # -- downloads ------------------------------------------------------------------------------------
    def claim(self, key: str, kind: str, target: str) -> Job:
        """Register a download before its thread starts, so a second request is refused at once."""
        with self.lock:
            j = self.jobs.get(key)
            if j and j.state in ("queued", "running"):
                raise EngineError(f"{target} is already downloading")
            self.jobs[key] = j = Job(kind, target, state="queued")
        return j

    def _job(self, key: str, kind: str, target: str) -> Job:
        """The claimed job for this download (or a new one when called directly), now running."""
        with self.lock:
            j = self.jobs.get(key)
            if not (j and j.state == "queued"):
                j = self.claim(key, kind, target)
            j.state = "running"
        return j

    def cancel(self, key: str):
        j = self.jobs.get(key)
        if j:
            j.cancel.set()

    def _fetch(self, url: str, dest: Path, job: Job, sha256: str | None, size: int | None = None):
        """Resumable download to dest (via dest.part), checked against sha256 when given."""
        part = dest.with_name(dest.name + ".part")
        dest.parent.mkdir(parents=True, exist_ok=True)
        have = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": "sage-os", **({"Range": f"bytes={have}-"} if have else {})}
        with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=httpx.Timeout(30, read=120)) as r:
            if r.status_code == 416:                       # already complete
                pass
            elif r.status_code not in (200, 206):
                raise EngineError(f"download failed: HTTP {r.status_code}")
            else:
                if r.status_code == 200:
                    have = 0                               # the server ignored Range: start over
                total = int(r.headers.get("content-length", 0)) + have
                job.total, job.done = total or (size or 0), have
                with open(part, "ab" if have else "wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        if job.cancel.is_set():
                            job.state = "cancelled"
                            return
                        f.write(chunk)
                        job.done += len(chunk)
                        if job.done % (32 << 20) < len(chunk):
                            self.on_change()
        if size and part.stat().st_size != size:
            raise EngineError("download incomplete; try again to resume")
        if sha256:
            h = hashlib.sha256()
            with open(part, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 22), b""):
                    h.update(chunk)
            if h.hexdigest() != sha256.lower():
                part.unlink(missing_ok=True)
                raise EngineError("the download didn't match its checksum and was deleted")
        os.replace(part, dest)

    def install_binary(self) -> None:
        """Download the official llama.cpp build for this machine (runs in a worker thread)."""
        job = self._job("binary", "binary", "llama-server")
        try:
            hw = self.hardware()
            rels = httpx.get(RELEASES, headers={"User-Agent": "sage-os"}, timeout=30).json()
            for rel in rels:
                assets = pick_asset(rel.get("assets", []), rel["tag_name"], hw)
                if assets:
                    break
            else:
                raise EngineError("no llama.cpp release has a build for this computer")
            dl = self.root / "download"
            target = self.bin_dir / rel["tag_name"]
            for a in assets:
                digest = (a.get("digest") or "").removeprefix("sha256:")
                if not re.fullmatch(r"[0-9a-f]{64}", digest):     # an executable is never installed unchecked
                    raise EngineError(f"GitHub gave no SHA-256 for {a['name']}; not installing it")
                path = dl / a["name"]
                self._fetch(a["browser_download_url"], path, job, digest, a.get("size"))
                if job.state == "cancelled":
                    return
                target.mkdir(parents=True, exist_ok=True)
                safe_extract(path, target)
                path.unlink(missing_ok=True)
            for p in target.rglob(EXE):
                if os.name != "nt":
                    p.chmod(0o755)
            if not any(target.rglob(EXE)):
                raise EngineError("the download didn't contain llama-server")
            job.state = "done"
        except Exception as exc:                          # noqa: BLE001 -- reported to the UI
            job.state, job.error = "failed", str(exc)
        finally:
            self.on_change()

    def download_model(self, model_id: str) -> None:
        m = next((x for x in self.catalog() if x["id"] == model_id), None)
        if not m:
            with self.lock:
                self.jobs.pop(f"model:{model_id}", None)
            raise EngineError(f"no model {model_id!r} in the catalog")
        job = self._job(f"model:{model_id}", "model", m["label"])
        try:
            self._fetch(HF_FILE.format(repo=m["repo"], file=m["file"]), self.models_dir / m["file"], job, m.get("sha256"), m.get("size"))
            if job.state != "cancelled":
                job.state = "done"
        except Exception as exc:                          # noqa: BLE001
            job.state, job.error = "failed", str(exc)
        finally:
            self.on_change()

    # -- serving --------------------------------------------------------------------------------------
    def resolve_model(self, model_id: str) -> Path:
        for m in self.catalog():
            if m["id"] == model_id and m["installed"]:
                return self.models_dir / m["file"]
        for m in self.local_models():
            if m["id"] == model_id:
                return Path(m["path"])
        raise EngineError(f"model {model_id!r} isn't on this computer yet")

    def start(self, model_id: str, small: bool = False) -> dict:
        """Serve a model. `small`: one 8K slot, for a micro model running beside a game (G1)."""
        b = self.binary()
        if not b:
            raise EngineError("llama-server isn't installed yet")
        path = self.resolve_model(model_id)
        self.stop()
        hw = self.hardware()
        # Locked down: llama-server answers any web page by default (CORS *, no key) and its /slots and web
        # UI can show recent prompts, which carry the user's notes. A fresh key per start, passed in the
        # environment (not the command line, which other processes can read); no web UI; no CORS origin.
        slots = 2 if has_gpu(hw) and not small else 1     # two on a GPU: a chat needn't wait behind a digest section
        ctx = SMALL_CTX if small else CTX
        args = [str(b), "-m", str(path), "--host", "127.0.0.1", "--port", str(self.port), "-c", str(ctx * slots),
                "--jinja", "--alias", model_id, "-np", str(slots), "-ngl", "999" if hw["backend"] != "cpu" else "0",
                "--no-webui", "--cors-origins", "http://127.0.0.1:1"]
        self.api_key = secrets.token_urlsafe(32)
        env = {**os.environ, "LLAMA_API_KEY": self.api_key}
        self.root.mkdir(parents=True, exist_ok=True)
        log = open(self.root / "server.log", "ab")
        try:
            proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, cwd=str(b.parent), env=env,
                                    creationflags=NO_WINDOW)
        finally:
            log.close()
        with self.lock:
            self.proc = proc
            self.serving = {"id": model_id, "path": str(path), "started": time.time(), "ready": False, "pid": proc.pid,
                            "small": small}
        (self.root / "server.pid").write_text(str(proc.pid))
        return self.serving

    def reap_orphan(self) -> int | None:
        """A hub that was killed (not shut down) leaves its llama-server holding GPU memory. On the next start,
        stop the one recorded in server.pid, but only if that pid is still a llama-server. -> its pid."""
        pidfile = self.root / "server.pid"
        try:
            pid = int(pidfile.read_text())
        except (OSError, ValueError):
            return None
        pidfile.unlink(missing_ok=True)
        try:
            p = psutil.Process(pid)
            if p.name().lower() != EXE.lower():
                return None
            p.terminate()
            p.wait(10)
        except (psutil.Error, OSError):
            return None
        return pid

    def alive(self) -> bool:
        """Is the served model's process still running? Raises (and clears `serving`) if it died."""
        with self.lock:
            proc = self.proc
        if proc and proc.poll() is not None:
            with self.lock:
                self.serving, self.proc = None, None
            raise EngineError(f"llama-server stopped (exit {proc.returncode}); see {self.root / 'server.log'}")
        return True

    def check_ready(self) -> bool:
        """Poll llama-server's /health (it loads the model before answering)."""
        with self.lock:
            proc, serving = self.proc, self.serving
        if not proc or not serving:
            return False
        if proc.poll() is not None:
            with self.lock:
                self.serving, self.proc = None, None
            raise EngineError(f"llama-server stopped (exit {proc.returncode}); see {self.root / 'server.log'}")
        try:
            ok = httpx.get(f"http://127.0.0.1:{self.port}/health", timeout=2).status_code == 200
        except httpx.HTTPError:
            ok = False
        if ok and not serving["ready"]:
            with self.lock:
                self.serving["ready"] = True
        return ok

    def stop(self):
        (self.root / "server.pid").unlink(missing_ok=True)
        with self.lock:
            proc, self.proc, self.serving = self.proc, None, None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()


def safe_extract(archive: Path, dest: Path):
    """Unpack a zip or tar.gz, refusing paths that escape `dest`."""
    root = dest.resolve()

    def ok(name: str) -> bool:
        p = (dest / name).resolve()
        return p == root or root in p.parents
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            bad = [n for n in z.namelist() if not ok(n)]
            if bad:
                raise EngineError("archive has unsafe paths")
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            if any(not ok(m.name) for m in t.getmembers()):
                raise EngineError("archive has unsafe paths")
            t.extractall(dest, filter="data")              # also refuses links that point outside dest
