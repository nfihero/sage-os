"""python -m sage_os_hub            -- starts the hub on the configured localhost port.
python -m sage_os_hub --log FILE   -- the same, logging to FILE (the desktop app runs it this way, W1).
python -m sage_os_hub move-data  -- moves an install from before D25 (data/ next to the code) into app data."""
import faulthandler
import logging
import socket
import sys
from pathlib import Path

import uvicorn

from .app import create_app
from .config import ROOT, app_data_dir, load


def move_data():
    from .storage import move_legacy
    cfg = load()
    with socket.socket() as s:
        if s.connect_ex((cfg.host, cfg.port)) == 0:
            raise SystemExit(f"the hub is running on port {cfg.port}: stop it first, then move the data")
    r = move_legacy(ROOT / "data", app_data_dir())
    print(f"Moved {r['files']} files to {r['to']} (notes are in Library/Notes).")
    print(f"The old folder is kept as {r['old_kept_as']}; delete it once you've checked Sage OS starts.")


def main():
    if sys.argv[1:] == ["move-data"]:
        return move_data()
    cfg = load()
    if cfg.host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(f"refusing to bind {cfg.host}: the hub listens on localhost only "
                         "(remote access goes through Tailscale Serve)")
    args = sys.argv[1:]
    log_file = args[args.index("--log") + 1] if "--log" in args and args.index("--log") + 1 < len(args) else None
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        filename=log_file, encoding="utf-8" if log_file else None)
    logging.getLogger("sage_os").info("data: %s · library: %s", cfg.data_dir, cfg.library or "(old data/ layout)")
    # a crash inside native code (GPU counters, SQLite) leaves a stack trace instead of a silent exit
    crash_log = open(log_file, "a", encoding="utf-8") if log_file else sys.stderr
    faulthandler.enable(crash_log, all_threads=True)
    app = create_app(cfg)
    server = uvicorn.Server(uvicorn.Config(app, host=cfg.host, port=cfg.port, log_level="warning",
                                           log_config=None if log_file else uvicorn.config.LOGGING_CONFIG))
    app.state.quit = lambda: setattr(server, "should_exit", True)      # POST /api/quit (the desktop app's Quit)
    server.run()


if __name__ == "__main__":
    main()
