#!/usr/bin/env python3
"""
Fleet auto-discovery beacon (PRODUCTION v4)

Features:
- Per-device key support
- Automatic key rotation support
- Active + staged key handling
- Epoch advertisement
- Legacy shared-secret fallback
- Replay protection timestamp
- Hardened networking
- Backward safe
"""

import socket
import json
import time
import hmac
import hashlib
import sys
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

PORT = 8091
INTERVAL = 5

DEVICE_KEY_FILE = Path("/etc/pm-device-key")
NEXT_KEY_FILE   = Path("/etc/pm-device-key.next")
SECRET_FILE     = Path("/etc/pm-fleet-secret")  # legacy fallback
DEVICE_FILE     = Path("/etc/pm-device.json")
EPOCH_FILE      = Path("/var/lib/pm-key-epoch")

VERSION = "4.0"

# ============================================================
# HELPERS
# ============================================================

def log(msg):
    print(f"[pm-node] {msg}", flush=True)


# ------------------------------------------------------------
# epoch handling
# ------------------------------------------------------------

def get_epoch():
    try:
        return int(EPOCH_FILE.read_text().strip())
    except Exception:
        return 1


# ------------------------------------------------------------
# key loading
# ------------------------------------------------------------

def load_active_key():
    if DEVICE_KEY_FILE.exists():
        key = DEVICE_KEY_FILE.read_text().strip()
        if len(key) < 16:
            log("FATAL: device key too short")
            sys.exit(1)
        return key.encode()

    # fallback
    if SECRET_FILE.exists():
        key = SECRET_FILE.read_text().strip()
        log("using legacy fleet secret")
        return key.encode()

    log("FATAL: no key material found")
    sys.exit(1)


def load_next_key():
    if NEXT_KEY_FILE.exists():
        try:
            key = NEXT_KEY_FILE.read_text().strip()
            if len(key) >= 16:
                return key.encode()
        except Exception:
            pass
    return None


# ------------------------------------------------------------
# device info
# ------------------------------------------------------------

def load_device():
    if not DEVICE_FILE.exists():
        log("WARNING: missing device file")
        return {"device_id": "unknown"}

    try:
        return json.loads(DEVICE_FILE.read_text())
    except Exception:
        return {"device_id": "unknown"}


def get_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


# ------------------------------------------------------------
# signing
# ------------------------------------------------------------

def sign_payload(payload, key):
    clean = dict(payload)
    clean.pop("sig", None)

    msg = json.dumps(
        clean,
        sort_keys=True,
        separators=(",", ":")
    ).encode()

    return hmac.new(key, msg, hashlib.sha256).hexdigest()


# ============================================================
# MAIN
# ============================================================

def main():
    active_key = load_active_key()
    next_key = load_next_key()
    device = load_device()

    epoch = get_epoch()
    advertised_epoch = epoch

    # If next key exists → advertise next epoch
    if next_key:
        advertised_epoch = epoch + 1
        log("rotation staged — advertising next epoch")
    else:
        log("using active epoch")

    if device.get("device_id") in (None, "", "unknown"):
        log("WARNING: device_id not properly set")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    log("secure beacon started")

    while True:
        try:
            payload = {
                "type": "pm-node",
                "version": VERSION,
                "device": device,
                "hostname": get_hostname(),
                "port": 8090,
                "ts": int(time.time()),
                "epoch": advertised_epoch,
            }

            # sign with ACTIVE key (important for safe rollover)
            payload["sig"] = sign_payload(payload, active_key)

            sock.sendto(
                json.dumps(payload).encode(),
                ("255.255.255.255", PORT),
            )

        except Exception as e:
            log(f"beacon error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()