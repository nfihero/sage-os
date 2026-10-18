# PyInstaller recipe for the hub inside the desktop app (F1, D38). Run from the repo root after `npm run build` in ui/:
#   hub\.venv\Scripts\python -m PyInstaller hub/packaging/sage-os-hub.spec --noconfirm --distpath build --workpath build/work
# Output: build/sage-os-hub/ (an executable plus _internal/), which the desktop app ships as its "hub" resource.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve().parents[1]
if not (ROOT / "ui" / "dist" / "index.html").is_file():
    raise SystemExit("build the UI first: cd ui && npm run build")

datas = [(str(ROOT / "config.toml"), "."), (str(ROOT / "ui" / "dist"), "ui/dist")]
# the model catalog straight from the source tree: an installed package only has it if its package data was declared
datas += [(str(ROOT / "hub" / "sage_os_hub" / "engine" / "catalog.json"), "sage_os_hub/engine")]
datas += [(str(ROOT / "hub" / "sage_os_hub" / "pricing.json"), "sage_os_hub")]
datas += copy_metadata("keyring")      # keyring finds its OS backends (Windows, macOS) through its entry points
hidden = (collect_submodules("sage_os_hub") + collect_submodules("uvicorn") + collect_submodules("mcp", filter=lambda n: not n.startswith("mcp.cli"))
          + collect_submodules("claude_agent_sdk") + collect_submodules("keyring")    # keyring picks its OS backend at run time
          + collect_submodules("zeroconf") + collect_submodules("ifaddr"))   # devices finding each other (P1)

a = Analysis([str(ROOT / "hub" / "packaging" / "run_hub.py")], pathex=[str(ROOT / "hub")], datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "pytest", "PyInstaller"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="sage-os-hub", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="sage-os-hub", upx=False)
