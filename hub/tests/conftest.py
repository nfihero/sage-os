"""Every test gets its own app-data folder and its own config.local.toml (D25), so no test reads or writes
the real ones. (9 Oct: a storage test wrote the user's real config.local.toml; this guard is why.)"""
import pytest

from sage_os_hub import config


@pytest.fixture(autouse=True)
def isolated_data(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("SAGE_OS_DATA", str(tmp_path_factory.mktemp("appdata")))
    local = tmp_path_factory.mktemp("cfg") / "config.local.toml"
    real_post_init = config.Config.__post_init__

    def post_init(self):
        if self.local_config == config.ROOT / "config.local.toml":
            self.local_config = local
        real_post_init(self)
    monkeypatch.setattr(config.Config, "__post_init__", post_init)
