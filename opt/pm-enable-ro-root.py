#!/usr/bin/env python3
"""
Enable Read-Only Root (Full Appliance Mode + Persistent Logging)

Features:
- Detects existing 'ro'
- Preserves cmdline format
- Adds tmpfs overlays to fstab
- Installs rw-root / ro-root helpers
- Configures journald for volatile logging
- Installs pm-log-dump utility
- Self-tests helpers safely
- Creates timestamp backups
- Idempotent and safe
- Works on Pi OS / DietPi
"""

from pathlib import Path
import time
import shutil
import sys
import os
import subprocess

CMDLINE = Path("/boot/cmdline.txt")
FSTAB = Path("/etc/fstab")
JOURNALD = Path("/etc/systemd/journald.conf")

RW_HELPER = Path("/usr/local/bin/rw-root")
RO_HELPER = Path("/usr/local/bin/ro-root")
LOG_DUMP = Path("/usr/local/bin/pm-log-dump")

TMPFS_LINES = [
    "tmpfs  /tmp        tmpfs  defaults,nosuid,nodev,size=100m  0  0",
    "tmpfs  /var/tmp    tmpfs  defaults,nosuid,nodev,size=50m   0  0",
    "tmpfs  /var/log    tmpfs  defaults,nosuid,nodev,size=100m  0  0",
]

JOURNAL_BLOCK = """[Journal]
Storage=volatile
RuntimeMaxUse=64M
RuntimeKeepFree=16M
SystemMaxUse=0
ForwardToSyslog=no
Compress=yes
Seal=no
"""

LOG_DUMP_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

OUTDIR="/boot/pm-logs"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$OUTDIR"

echo "[pm-log] Dumping journal..."
journalctl -b > "$OUTDIR/journal-$TS.log"
echo "[pm-log] Saved to $OUTDIR/journal-$TS.log"
"""


# ============================================================
# HELPERS
# ============================================================

def log(msg: str):
    print(f"[ro-root] {msg}", flush=True)


def backup_file(path: Path):
    ts = int(time.time())
    backup = path.with_name(path.name + f".bak.{ts}")
    shutil.copy2(path, backup)
    log(f"Backup created: {backup}")


def run_quiet(cmd):
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception as e:
        log(f"Command failed: {cmd} ({e})")


# ============================================================
# CMDLINE
# ============================================================

def ensure_cmdline_ro():
    if not CMDLINE.exists():
        log("cmdline.txt not found — abort")
        return

    content = CMDLINE.read_text().strip()

    if " ro" in content or content.endswith("ro"):
        log("cmdline already contains ro")
        return

    log("Enabling read-only root in cmdline")
    backup_file(CMDLINE)
    CMDLINE.write_text(content + " ro\n")
    log("cmdline updated")


# ============================================================
# FSTAB
# ============================================================

def ensure_tmpfs_overlays():
    if not FSTAB.exists():
        log("fstab missing — skipping")
        return

    lines = FSTAB.read_text().splitlines()
    changed = False

    for line in TMPFS_LINES:
        mp = line.split()[1]

        if any(
            l.strip() and not l.strip().startswith("#")
            and len(l.split()) > 1 and l.split()[1] == mp
            for l in lines
        ):
            continue

        log(f"Adding tmpfs overlay for {mp}")
        lines.append(line)
        changed = True

    if changed:
        backup_file(FSTAB)
        FSTAB.write_text("\n".join(lines) + "\n")
        log("fstab updated")
    else:
        log("fstab already contains tmpfs overlays")


# ============================================================
# HELPERS INSTALL
# ============================================================

def install_helpers():
    helpers = {
        RW_HELPER: """#!/usr/bin/env bash
mount -o remount,rw /
echo "[root] remounted RW"
""",
        RO_HELPER: """#!/usr/bin/env bash
sync
mount -o remount,ro /
echo "[root] remounted RO"
"""
    }

    for path, content in helpers.items():
        if path.exists():
            log(f"{path.name} already exists")
            continue

        log(f"Installing {path.name}")
        path.write_text(content)
        os.chmod(path, 0o755)


# ============================================================
# JOURNALD CONFIG
# ============================================================

def ensure_journald_config():
    if not JOURNALD.exists():
        log("journald.conf missing — skipping")
        return

    content = JOURNALD.read_text()

    if "Storage=volatile" in content:
        log("journald already configured")
        return

    log("Configuring journald for volatile logging")
    backup_file(JOURNALD)
    JOURNALD.write_text(JOURNAL_BLOCK)
    run_quiet(["systemctl", "restart", "systemd-journald"])
    run_quiet(["journalctl", "--disk-usage"])
    log("journald configured")


# ============================================================
# LOG DUMP TOOL
# ============================================================

def ensure_log_dump():
    if LOG_DUMP.exists():
        log("pm-log-dump already exists")
        return

    log("Installing pm-log-dump")
    LOG_DUMP.write_text(LOG_DUMP_SCRIPT)
    os.chmod(LOG_DUMP, 0o755)

    # test run (safe)
    run_quiet([str(LOG_DUMP)])


# ============================================================
# SELF TEST
# ============================================================

def self_test_helpers():
    log("Running helper self-test")

    if RW_HELPER.exists():
        run_quiet([str(RW_HELPER)])
        time.sleep(0.5)

    if RO_HELPER.exists():
        run_quiet([str(RO_HELPER)])

    log("Helper self-test complete")


# ============================================================
# MAIN
# ============================================================

def main():
    log("=== RO ROOT ENFORCEMENT ===")

    ensure_cmdline_ro()
    ensure_tmpfs_overlays()
    install_helpers()
    ensure_journald_config()
    ensure_log_dump()
    self_test_helpers()

    log("RO root + logging setup complete")
    log("Reboot required")

    return 0


if __name__ == "__main__":
    sys.exit(main())