#!/usr/bin/env python3
"""
Fleet Telemetry Agent

Collects system health and writes fleet status.
Optional HTTP push.

RO-root safe.
"""

import json
import time
import subprocess
from pathlib import Path
import socket
import os

DEVICE_FILE = Path("/etc/pm-device.json")
HEALTH_FILE = Path("/boot/pm-health/boot-health.json")
OUTDIR = Path("/boot/pm-fleet")
OUTDIR.mkdir(exist_ok=True)

STATUS_FILE = OUTDIR / "status.json"

# Optional remote endpoint (set to "" to disable)
FLEET_ENDPOINT = ""


# ============================================================
# HELPERS
# ============================================================

def log(msg):
    print(f"[pm-fleet] {msg}", flush=True)


def get_uptime():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0


def get_hostname():
    return socket.gethostname()


def get_load():
    try:
        return os.getloadavg()[0]
    except Exception:
        return 0


def read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


# ============================================================
# MAIN
# ============================================================

def main():
    device = read_json(DEVICE_FILE)
    health = read_json(HEALTH_FILE)

    status = {
        "timestamp": int(time.time()),
        "device": device,
        "hostname": get_hostname(),
        "uptime_sec": get_uptime(),
        "boot_health": health,
    }

    STATUS_FILE.write_text(json.dumps(status, indent=2))
    log("Status updated")

    # Optional push
    if FLEET_ENDPOINT:
        try:
            subprocess.run(
                [
                    "curl",
                    "-s",
                    "-X",
                    "POST",
                    "-H",
                    "Content-Type: application/json",
                    "-d",
                    json.dumps(status),
                    FLEET_ENDPOINT,
                ],
                timeout=5,
            )
            log("Pushed to fleet server")
        except Exception as e:
            log(f"Push failed: {e}")


if __name__ == "__main__":
    main()