import configparser
from pathlib import Path

CONF = Path("/etc/rpi-supervisor/fleet.conf")

def load_fleet_server():
    cfg = configparser.ConfigParser()

    if not CONF.exists():
        raise RuntimeError("fleet.conf missing")

    cfg.read(CONF)

    if not cfg.has_section("fleet"):
        raise RuntimeError("fleet section missing")

    server = cfg.get("fleet", "server_host", fallback="")

    if not server:
        raise RuntimeError("server_host not set")

    return server