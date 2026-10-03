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
