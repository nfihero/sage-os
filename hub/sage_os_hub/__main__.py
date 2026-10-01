"""python -m sage_os_hub  -- starts the hub on the configured localhost port."""
import logging

import uvicorn

from .app import create_app
from .config import load


def main():
    cfg = load()
    if cfg.host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(f"refusing to bind {cfg.host}: the hub listens on localhost only "
                         "(remote access goes through Tailscale Serve)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(cfg), host=cfg.host, port=cfg.port, log_level="warning")


if __name__ == "__main__":
    main()
