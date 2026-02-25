#!/usr/bin/env python3
"""
Pi Storage Hardener

Safely hardens the root filesystem mount options to reduce SD corruption.

Features:
- Auto-detect root device
- Verify ext4
- Preserve existing mount flags
- Remove old commit values
- Inject safe options
- Create fstab backup
- Idempotent (safe to re-run)
"""

import subprocess
import shutil
import time
import re
from pathlib import Path
import sys

FSTAB = Path("/etc/fstab")

REQUIRED_FLAGS = [
    "noatime",
    "errors=remount-ro",
]

COMMIT_VALUE = "commit=30"


# ============================================================
# Helpers
# ============================================================

def log(msg: str):
    print(f"[storage] {msg}", flush=True)


def run(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def get_root_info():
    root_dev = run(["findmnt", "-n", "-o", "SOURCE", "/"])
    root_fs = run(["findmnt", "-n", "-o", "FSTYPE", "/"])
    return root_dev, root_fs


def backup_fstab():
    ts = int(time.time())
    backup = FSTAB.with_name(f"fstab.bak.{ts}")
    shutil.copy2(FSTAB, backup)
    log(f"Backup created: {backup}")


def normalize_opts(opts: str) -> str:
    parts = [o.strip() for o in opts.split(",") if o.strip()]

    # Remove old commit values
    parts = [p for p in parts if not p.startswith("commit=")]

    # Ensure required flags
    for flag in REQUIRED_FLAGS:
        if flag not in parts:
            parts.append(flag)

    # Add our commit value
    parts.append(COMMIT_VALUE)

    # Remove duplicates while preserving order
    seen = set()
    cleaned = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            cleaned.append(p)

    return ",".join(cleaned)


# ============================================================
# Main
# ============================================================

def main():
    log("Detecting root filesystem...")

    try:
        root_dev, root_fs = get_root_info()
    except Exception as e:
        log(f"Failed to detect root: {e}")
        return 1

    log(f"Root device: {root_dev}")
    log(f"Filesystem: {root_fs}")

    if root_fs != "ext4":
        log("Not ext4 — skipping")
        return 0

    if not FSTAB.exists():
        log("fstab missing — abort")
        return 1

    backup_fstab()

    lines = FSTAB.read_text().splitlines()
    new_lines = []
    modified = False

    root_pattern = re.compile(r"\s/\s")

    for line in lines:
        stripped = line.strip()

        # Skip comments and blank lines
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        if root_pattern.search(line):
            parts = line.split()

            if len(parts) < 4:
                new_lines.append(line)
                continue

            old_opts = parts[3]
            new_opts = normalize_opts(old_opts)

            if new_opts != old_opts:
                log(f"Updating mount options:")
                log(f"  old: {old_opts}")
                log(f"  new: {new_opts}")
                parts[3] = new_opts
                modified = True

            new_lines.append("\t".join(parts))
        else:
            new_lines.append(line)

    if modified:
        FSTAB.write_text("\n".join(new_lines) + "\n")
        log("fstab updated successfully")
        log("Reboot recommended")
    else:
        log("fstab already optimal — no changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())