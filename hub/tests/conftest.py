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


class MemoryKeyring:
    """Stands in for the OS keychain in tests (D40): nothing touches the real Credential Manager or Keychain."""
    def __init__(self):
        self.store = {}

    def get_password(self, service, user):
        return self.store.get((service, user))

    def set_password(self, service, user, password):
        self.store[(service, user)] = password

    def delete_password(self, service, user):
        self.store.pop((service, user), None)


@pytest.fixture(autouse=True)
def memory_keychain(monkeypatch):
    from sage_os_hub import keys
    kr = MemoryKeyring()
    real_init = keys.Keys.__init__

    def init(self, backend=None):
        real_init(self, backend or kr)
    monkeypatch.setattr(keys.Keys, "__init__", init)
    return kr
