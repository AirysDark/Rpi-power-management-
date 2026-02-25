#!/usr/bin/env python3
"""
Power Manager Auto-Updater (Hardened + Rollback Safe)

Features:
- Safe fast-forward pull
- Detects if repo exists
- Network-safe
- Clean logging
- Service health verification
- Automatic rollback on failure
- Works on Pi 3/4/5
"""

import subprocess
import sys
import os
import time
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

REPO_DIR = Path("/opt")
BRANCH = "main"
SERVICE = "power-manager"

HEALTH_WAIT = 8            # seconds after restart
ENABLE_ROLLBACK = True

# ============================================================
# HELPERS
# ============================================================

def log(msg: str):
    print(f"[pm-update] {msg}", flush=True)


def run(cmd, check=True):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def get_rev(ref: str) -> str:
    return run(["git", "rev-parse", ref]).stdout.strip()


def service_healthy() -> bool:
    """Check if power-manager is running."""
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE]
    )
    return result.returncode == 0


def restart_service():
    subprocess.run(["systemctl", "restart", SERVICE], check=False)


def rollback_to(commit: str):
    log(f"ROLLBACK → {commit[:7]}")
    subprocess.run(["git", "reset", "--hard", commit], check=False)
    restart_service()

# ============================================================
# MAIN
# ============================================================

def main():
    log("Checking for updates...")

    if not is_git_repo(REPO_DIR):
        log("Not a git repository — skipping")
        return 0

    os.chdir(REPO_DIR)

    # --------------------------------------------------------
    # Fetch
    # --------------------------------------------------------
    try:
        run(["git", "fetch", "origin", BRANCH])
    except subprocess.CalledProcessError as e:
        log(f"Fetch failed: {e.stderr.strip()}")
        return 0  # non-fatal

    # --------------------------------------------------------
    # Compare revisions
    # --------------------------------------------------------
    try:
        local = get_rev("HEAD")
        remote = get_rev(f"origin/{BRANCH}")
    except subprocess.CalledProcessError as e:
        log(f"rev-parse failed: {e.stderr.strip()}")
        return 0

    if local == remote:
        log("Already up to date")
        return 0

    log(f"Update found — snapshot {local[:7]}")

    # --------------------------------------------------------
    # Pull update
    # --------------------------------------------------------
    try:
        run(["git", "pull", "--ff-only", "origin", BRANCH])
    except subprocess.CalledProcessError as e:
        log(f"Pull failed: {e.stderr.strip()}")
        return 1

    log("Update applied — restarting service")
    restart_service()

    # --------------------------------------------------------
    # Health check window
    # --------------------------------------------------------
    log("Waiting for service health check...")
    time.sleep(HEALTH_WAIT)

    if service_healthy():
        log("Service healthy — update kept")
        return 0

    log("Service FAILED after update")

    # --------------------------------------------------------
    # Rollback if enabled
    # --------------------------------------------------------
    if ENABLE_ROLLBACK:
        rollback_to(local)

        time.sleep(HEALTH_WAIT)

        if service_healthy():
            log("Rollback successful")
            return 0
        else:
            log("Rollback FAILED — manual intervention required")
            return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())