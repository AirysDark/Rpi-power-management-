#!/usr/bin/env python3
"""
Fleet Dashboard Collector (Hybrid + Secure + Per-Device Keys)

Supports:
- static nodes.json
- UDP auto-discovery (SIGNED)
- per-device key verification
- automatic key promotion
- replay protection
- offline detection
- stale cleanup
- secure remote commands

Production hardened.
"""

import json
import urllib.request
import urllib.error
import socket
import threading
import time
import hmac
import hashlib
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os

# ============================================================
# CONFIG
# ============================================================

PORT = 8088
DISCOVERY_PORT = 8091
NODE_TIMEOUT = 25
TIMESTAMP_SKEW = 120

WEB_ROOT = Path("/opt/pm-fleet-dashboard/web")
NODES_FILE = Path("/opt/pm-fleet-dashboard/nodes.json")
KEYS_FILE = Path("/opt/pm-fleet-dashboard/pm-fleet-keys.json")

os.chdir(WEB_ROOT)

# runtime node cache
discovered_nodes = {}

# ============================================================
# HELPERS
# ============================================================

def log(msg):
    print(f"[pm-fleet] {msg}", flush=True)


# ------------------------------------------------------------
# KEY DATABASE
# ------------------------------------------------------------

def load_keys():
    if not KEYS_FILE.exists():
        return {"devices": {}}
    try:
        return json.loads(KEYS_FILE.read_text())
    except Exception as e:
        log(f"keys load error: {e}")
        return {"devices": {}}


def save_keys(data):
    try:
        KEYS_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        log(f"keys save error: {e}")


def get_device_record(device_id):
    db = load_keys()
    return db.get("devices", {}).get(device_id)


def promote_next_key(device_id):
    db = load_keys()
    dev = db.get("devices", {}).get(device_id)
    if not dev:
        return

    next_key = dev.get("next_key")
    if not next_key:
        return

    log(f"Promoting next key for {device_id}")

    dev["active_key"] = next_key
    dev["next_key"] = None
    dev["epoch"] = dev.get("epoch", 0) + 1

    save_keys(db)


# ------------------------------------------------------------
# HMAC
# ------------------------------------------------------------

def sign_payload(payload, key_bytes):
    msg = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(key_bytes, msg, hashlib.sha256).hexdigest()


def verify_with_key(payload, sig, key_str):
    if not key_str:
        return False
    key_bytes = key_str.encode()
    calc = sign_payload(payload, key_bytes)
    return hmac.compare_digest(calc, sig)


# ============================================================
# UDP AUTO-DISCOVERY (PER-DEVICE SECURE)
# ============================================================

def discovery_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", DISCOVERY_PORT))

    log("UDP discovery listener started (per-device secure)")

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            msg = json.loads(data.decode())

            if msg.get("type") != "pm-node":
                continue

            sig = msg.pop("sig", "")
            ts = msg.get("ts", 0)

            # ---- timestamp protection ----
            if abs(time.time() - ts) > TIMESTAMP_SKEW:
                continue

            device = msg.get("device", {})
            device_id = device.get("device_id")

            if not device_id:
                continue

            rec = get_device_record(device_id)
            if not rec:
                log(f"Unknown device: {device_id}")
                continue

            # ---- verify active ----
            if verify_with_key(msg, sig, rec.get("active_key")):
                pass

            # ---- verify next (promotion path) ----
            elif verify_with_key(msg, sig, rec.get("next_key")):
                promote_next_key(device_id)

            else:
                log(f"Rejected beacon from {device_id} (bad sig)")
                continue

            discovered_nodes[addr[0]] = {
                "ip": addr[0],
                "port": msg.get("port", 8090),
                "device": device,
                "hostname": msg.get("hostname", ""),
                "last_seen": time.time(),
            }

        except Exception:
            pass


# ============================================================
# NODE FETCH
# ============================================================

def fetch_node(ip, port, fallback_device=None):
    url = f"http://{ip}:{port}/api/status"

    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            data = json.loads(r.read().decode())
            data["ip"] = ip
            return data
    except Exception:
        return {
            "device": fallback_device or {"device_id": ip},
            "hostname": "offline",
            "boot_health": {"score": 0},
            "uptime_sec": 0,
            "ip": ip,
        }


# ============================================================
# COLLECT FLEET
# ============================================================

def collect_status():
    now = time.time()
    results = []
    seen_ips = set()

    # ---------- static nodes ----------
    for node in load_nodes():
        ip = node.get("ip")
        port = node.get("port", 8090)

        if not ip:
            continue

        seen_ips.add(ip)
        results.append(fetch_node(ip, port, {"device_id": node.get("name", ip)}))

    # ---------- cleanup stale ----------
    stale = [
        ip for ip, n in discovered_nodes.items()
        if now - n["last_seen"] > NODE_TIMEOUT
    ]

    for ip in stale:
        del discovered_nodes[ip]

    # ---------- discovered ----------
    for ip, node in discovered_nodes.items():
        if ip in seen_ips:
            continue

        results.append(
            fetch_node(ip, node["port"], node.get("device"))
        )

    return results


# ============================================================
# REMOTE COMMAND (PER-DEVICE SIGNED)
# ============================================================

def send_command(ip, cmd):
    # find device by IP
    device_id = None
    for node in discovered_nodes.values():
        if node["ip"] == ip:
            device_id = node["device"].get("device_id")
            break

    if not device_id:
        return False

    rec = get_device_record(device_id)
    if not rec:
        return False

    key = rec.get("active_key")
    if not key:
        return False

    payload = {
        "cmd": cmd,
        "ts": int(time.time()),
    }

    payload["sig"] = sign_payload(payload, key.encode())

    url = f"http://{ip}:8092/api/cmd"

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        urllib.request.urlopen(req, timeout=3)
        return True

    except urllib.error.URLError:
        return False


# ============================================================
# STATIC NODE LOADER
# ============================================================

def load_nodes():
    if not NODES_FILE.exists():
        return []
    try:
        return json.loads(NODES_FILE.read_text())
    except Exception as e:
        log(f"nodes.json error: {e}")
        return []


# ============================================================
# HTTP HANDLER
# ============================================================

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/fleet":
            data = collect_status()
            body = json.dumps(data).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/cmd":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))

            ip = data.get("ip")
            cmd = data.get("cmd")

            if not ip or not cmd:
                raise ValueError("bad payload")

            ok = send_command(ip, cmd)

            self.send_response(200 if ok else 500)
            self.end_headers()

        except Exception:
            self.send_response(400)
            self.end_headers()


# ============================================================
# MAIN
# ============================================================

def main():
    log("Collector starting")

    threading.Thread(target=discovery_listener, daemon=True).start()

    log(f"Dashboard running on :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()