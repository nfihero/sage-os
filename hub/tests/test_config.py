"""Per-machine config (D21): config.local.toml over config.toml, and paths that work on Windows and macOS."""
from pathlib import Path

import pytest

from sage_os_hub.config import ROOT, load, merge


def test_local_file_overrides_tables_key_by_key_and_lists_whole(tmp_path):
    (tmp_path / "config.toml").write_text(
        '[hub]\nport = 8787\nkeep_events = 10\n[hermes]\nhome = "C:/hermes"\ngateway = "http://127.0.0.1:8642"\n'
        '[[sources]]\nname = "drive"\npath = "G:/"\n[agents]\nhermes = ["default"]\n', encoding="utf-8")
    (tmp_path / "config.local.toml").write_text(
        '[hub]\nport = 8790\n[hermes]\nhome = "~/.hermes"\n[agents]\nhermes = []\n'
        '[[sources]]\nname = "mac-drive"\npath = "~/Drive"\n', encoding="utf-8")
    cfg = load(tmp_path / "config.toml")
    assert cfg.port == 8790 and cfg.keep_events == 10                    # merged key by key
    assert cfg.gateway == "http://127.0.0.1:8642"                         # untouched key kept
    assert cfg.hermes_home == Path.home() / ".hermes"                     # ~ expanded
    assert cfg.hermes_profiles == []
    assert [s["name"] for s in cfg.sources] == ["mac-drive"]              # list replaced whole
    assert Path(cfg.sources[0]["path"]) == Path.home() / "Drive"


def test_local_file_alone_is_enough(tmp_path):
    (tmp_path / "config.local.toml").write_text('[bookshelf]\nvault = "notes"\n', encoding="utf-8")
    assert load(tmp_path / "config.toml").vault == ROOT / "notes"         # relative to the sage-os root


def test_no_config_at_all_gives_defaults(tmp_path):
    cfg = load(tmp_path / "config.toml")
    assert cfg.port == 8787 and cfg.hermes_home.name in ("hermes", ".hermes")   # per-OS default


def test_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}, "l": [1]}
    out = merge(base, {"a": {"y": 2}, "l": [2]})
    assert out == {"a": {"x": 1, "y": 2}, "l": [2]} and base == {"a": {"x": 1}, "l": [1]}


def test_tracked_config_has_no_local_file_committed():
    assert "config.local.toml" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()


def test_byte_order_mark_is_accepted(tmp_path):
    """Notepad saves UTF-8 with a BOM; the config must still load (6 Oct)."""
    p = tmp_path / "config.toml"
    p.write_bytes(b"\xef\xbb\xbf[hub]\nport = 9999\n")
    (tmp_path / "config.local.toml").write_bytes(b"\xef\xbb\xbf[engine]\nport = 8799\n")
    c = load(p)
    assert c.port == 9999 and c.engine_port == 8799


def test_bundled_app_keeps_this_computers_settings_in_app_data(tmp_path, monkeypatch):
    """F1 (D38): inside the desktop app the bundle is replaced by every update, so config.local.toml lives in app
    data, and the bundle's config.toml is read from the bundle."""
    from sage_os_hub import config
    bundle, data = tmp_path / "bundle", tmp_path / "data"
    bundle.mkdir()
    data.mkdir()
    (bundle / "config.toml").write_text('[hub]\nport = 8787\n', encoding="utf-8")
    (data / "config.local.toml").write_text('[hub]\nport = 8797\n', encoding="utf-8")
    monkeypatch.setattr(config, "FROZEN", True)
    monkeypatch.setattr(config, "ROOT", bundle)
    monkeypatch.setenv("SAGE_OS_DATA", str(data))
    monkeypatch.delenv("SAGE_OS_CONFIG", raising=False)
    assert config.local_config_path() == data / "config.local.toml"
    cfg = config.load()
    assert cfg.port == 8797 and cfg.local_config == data / "config.local.toml"


def test_every_data_file_ships_with_the_package():
    """The desktop app's hub is built from an installed package (D38): a data file that pyproject doesn't declare is
    missing from the app (0.22.1 shipped without the model catalog)."""
    import subprocess
    import tomllib
    from pathlib import Path
    hub = Path(__file__).resolve().parents[1]
    declared = tomllib.loads((hub / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]["sage_os_hub"]
    tracked = subprocess.run(["git", "ls-files", "sage_os_hub"], cwd=hub, capture_output=True, text=True).stdout.split()
    data = [f.removeprefix("sage_os_hub/") for f in tracked if not f.endswith(".py")]
    assert data and all(f in declared for f in data), (data, declared)
