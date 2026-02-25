#!/usr/bin/env python3
"""
Crash-only log capture (Self-healing)

If previous boot was unclean, dump journal to /boot.
Also ensures pm-mark-clean-shutdown helper exists.

Safe for RO-root systems.
"""

import subprocess
from pathlib import Path
import os

MARKER = Path("/run/pm_clean_shutdown")
LOG_DUMP = Path("/usr/local/bin/pm-log-dump")
MARK_SCRIPT = Path("/usr/local/bin/pm-mark-clean-shutdown")

MARK_SCRIPT_CONTENT = """#!/usr/bin/env bash
set -euo pipefail
touch /run/pm_clean_shutdown
"""


# ============================================================
# HELPERS
# ============================================================

def log(msg: str):
    print(f"[pm-crash] {msg}", flush=True)


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
# SELF-HEAL: ensure marker helper exists
# ============================================================

def ensure_marker_helper():
    if MARK_SCRIPT.exists():
        return

    log("Installing pm-mark-clean-shutdown helper")

    try:
        MARK_SCRIPT.write_text(MARK_SCRIPT_CONTENT)
        os.chmod(MARK_SCRIPT, 0o755)
    except Exception as e:
        log(f"Failed to install marker helper: {e}")


# ============================================================
# LOGIC
# ============================================================

def was_clean_shutdown() -> bool:
    return MARKER.exists()


def clear_marker():
    try:
        MARKER.unlink(missing_ok=True)
    except Exception:
        pass


def dump_logs():
    if not LOG_DUMP.exists():
        log("pm-log-dump missing — cannot capture logs")
        return

    log("UNCLEAN SHUTDOWN DETECTED — dumping logs")
    run_quiet([str(LOG_DUMP)])


# ============================================================
# MAIN
# ============================================================

def main():
    ensure_marker_helper()

    if was_clean_shutdown():
        log("Previous shutdown clean")
        clear_marker()
        return

    dump_logs()
    clear_marker()


if __name__ == "__main__":
    main()