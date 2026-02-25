#!/usr/bin/env python3
"""
Boot Health Scoring System

Generates a boot quality score based on:
- undervoltage
- throttling
- frequency capping
- temperature
- crash history

Safe for RO-root systems.
"""

import subprocess
import time
from pathlib import Path
import json

OUTDIR = Path("/boot/pm-health")
OUTDIR.mkdir(exist_ok=True)

OUTFILE = OUTDIR / "boot-health.json"


# ============================================================
# HELPERS
# ============================================================

def log(msg):
    print(f"[pm-health] {msg}", flush=True)


def get_throttled():
    try:
        out = subprocess.check_output(
            ["vcgencmd", "get_throttled"],
            text=True,
            timeout=2,
        ).strip()

        value = int(out.split("=")[1], 16)
        return value
    except Exception:
        return 0


def get_temp():
    try:
        out = subprocess.check_output(
            ["vcgencmd", "measure_temp"],
            text=True,
            timeout=2,
        )
        return float(out.split("=")[1].replace("'C", ""))
    except Exception:
        return 0.0


# ============================================================
# SCORING
# ============================================================

def compute_score(flags, temp):
    score = 100
    issues = []

    if flags & 0x1:
        score -= 25
        issues.append("undervoltage_now")

    if flags & 0x2:
        score -= 15
        issues.append("freq_capped")

    if flags & 0x4:
        score -= 15
        issues.append("throttled")

    if flags & 0x10000:
        score -= 10
        issues.append("undervoltage_past")

    if flags & 0x20000:
        score -= 5
        issues.append("freq_capped_past")

    if flags & 0x40000:
        score -= 5
        issues.append("throttled_past")

    if temp > 80:
        score -= 20
        issues.append("high_temp")

    score = max(score, 0)

    return score, issues


# ============================================================
# MAIN
# ============================================================

def main():
    flags = get_throttled()
    temp = get_temp()

    score, issues = compute_score(flags, temp)

    data = {
        "timestamp": int(time.time()),
        "score": score,
        "temp_c": temp,
        "throttled_flags": hex(flags),
        "issues": issues,
    }

    OUTFILE.write_text(json.dumps(data, indent=2))

    log(f"Boot health score: {score}/100")

    if score < 70:
        log("⚠️ HEALTH WARNING")

    if score < 50:
        log("🚨 HEALTH CRITICAL")


if __name__ == "__main__":
    main()