#!/usr/bin/env python3
"""
Power Manager I/O Freeze Helper (Production)

Safely freezes and unfreezes critical filesystems
to reduce corruption risk during shutdown/reboot.

Design goals:
- Never block shutdown
- Safe if fsfreeze missing
- Safe on read-only root
- Timeout protected
- Idempotent
- Works on Pi 3/4/5
"""

import subprocess
import shutil
import time
import sys

# ============================================================
# CONFIG
# ============================================================

FREEZE_TARGETS = [
    "/",  # root filesystem
]

FREEZE_HOLD_SECONDS = 1
FSFREEZE_TIMEOUT = 3


# ============================================================
# HELPERS
# ============================================================

def log(msg: str):
    print(f"[pm-freeze] {msg}", flush=True)


def has_fsfreeze() -> bool:
    return shutil.which("fsfreeze") is not None


def is_mountpoint(path: str) -> bool:
    result = subprocess.run(
        ["mountpoint", "-q", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def is_read_only(path: str) -> bool:
    try:
        out = subprocess.check_output(
            ["findmnt", "-n", "-o", "OPTIONS", path],
            text=True,
            timeout=2,
        )
        return "ro" in out.split(",")
    except Exception:
        return False


def freeze_mount(path: str):
    if not is_mountpoint(path):
        log(f"Skip (not mountpoint): {path}")
        return

    if is_read_only(path):
        log(f"Skip (already read-only): {path}")
        return

    try:
        subprocess.run(
            ["fsfreeze", "-f", path],
            timeout=FSFREEZE_TIMEOUT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        log(f"Frozen: {path}")
    except subprocess.TimeoutExpired:
        log(f"Freeze timeout: {path}")
    except Exception as e:
        log(f"Freeze error {path}: {e}")


def unfreeze_mount(path: str):
    if not is_mountpoint(path):
        return

    try:
        subprocess.run(
            ["fsfreeze", "-u", path],
            timeout=FSFREEZE_TIMEOUT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        log(f"Unfrozen: {path}")
    except subprocess.TimeoutExpired:
        log(f"Unfreeze timeout: {path}")
    except Exception as e:
        log(f"Unfreeze error {path}: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    if not has_fsfreeze():
        log("fsfreeze not available — skipping")
        return 0

    log("Freezing filesystems")

    for mp in FREEZE_TARGETS:
        freeze_mount(mp)

    time.sleep(FREEZE_HOLD_SECONDS)

    log("Unfreezing filesystems")

    for mp in FREEZE_TARGETS:
        unfreeze_mount(mp)

    return 0


if __name__ == "__main__":
    sys.exit(main())