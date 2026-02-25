#!/usr/bin/env python3
"""
GPIO Power Manager — Elite Production Version (Hardened)

Features:
- Latching shutdown switch
- Momentary reset button
- Safe power-cut handshake
- Boot glitch protection
- Brownout monitoring
- Optional power-fail hold-up
- systemd watchdog support
- Auto-enforce read-only root
- Works on Pi 3 / 4 / 5
"""

import os
import time
import subprocess
import threading
from gpiozero import Button, OutputDevice
from signal import pause

# ---- systemd watchdog support (safe if not installed) ----
try:
    import sdnotify
    notifier = sdnotify.SystemdNotifier()
    SYSTEMD_NOTIFY = True
except Exception:
    notifier = None
    SYSTEMD_NOTIFY = False

# ============================================================
# CONFIG
# ============================================================

SHUTDOWN_PIN = 17
RESET_PIN    = 27
SAFEPOWER_PIN = 22

ENABLE_POWER_FAIL = False
POWER_FAIL_PIN    = 23

BOOT_IGNORE_TIME = 5.0
BOUNCE_TIME = 0.05

SHUTDOWN_SCRIPT = "/opt/shutdown.rpi"
RESTART_SCRIPT  = "/opt/restart.rpi"
RO_ENFORCE_SCRIPT = "/opt/pm-enable-ro-root.py"

BROWNOUT_CHECK_INTERVAL = 5.0
BROWNOUT_TRIGGER_COUNT  = 3
BROWNOUT_SHUTDOWN       = True

# ============================================================
# STATE
# ============================================================

boot_time = time.time()
shutdown_triggered = False
shutdown_lock = threading.Lock()
brownout_counter = 0
ro_check_done = False

# ============================================================
# SAFE POWER SIGNAL
# ============================================================

safe_out = OutputDevice(
    SAFEPOWER_PIN,
    active_high=True,
    initial_value=False
)

# ============================================================
# HELPERS
# ============================================================

def log(msg: str):
    print(f"[pm] {msg}", flush=True)


def run_script(path: str):
    if not os.path.exists(path):
        log(f"Missing script: {path}")
        return

    try:
        subprocess.Popen(
            [path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        log(f"Failed to execute {path}: {e}")


# ============================================================
# READ-ONLY ROOT ENFORCER
# ============================================================

def root_is_read_only() -> bool:
    try:
        out = subprocess.check_output(
            ["findmnt", "-n", "-o", "OPTIONS", "/"],
            text=True,
            timeout=2,
        )
        return "ro" in out.split(",")
    except Exception:
        return False


def enforce_ro_root_once():
    global ro_check_done

    if ro_check_done:
        return
    ro_check_done = True

    try:
        if root_is_read_only():
            log("RO root already active")
            return

        if not os.path.exists(RO_ENFORCE_SCRIPT):
            log("RO enforcement script missing")
            return

        log("Root is RW — enabling RO mode")
        subprocess.Popen(
            [RO_ENFORCE_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    except Exception as e:
        log(f"RO check failed: {e}")

# ============================================================
# POWER ACTIONS
# ============================================================

def safe_shutdown(reason="unknown"):
    global shutdown_triggered

    with shutdown_lock:
        if shutdown_triggered:
            return
        shutdown_triggered = True

    log(f"Shutdown initiated ({reason})")
    run_script(SHUTDOWN_SCRIPT)


def safe_reboot():
    log("Reset button pressed")
    run_script(RESTART_SCRIPT)

# ============================================================
# BROWNOUT MONITOR
# ============================================================

def check_undervoltage():
    try:
        out = subprocess.check_output(
            ["vcgencmd", "get_throttled"],
            text=True,
            timeout=2,
        ).strip()

        if "=" not in out:
            return False

        value = int(out.split("=")[1], 16)
        return bool(value & 0x1)

    except Exception as e:
        log(f"vcgencmd error: {e}")
        return False


def brownout_monitor():
    global brownout_counter

    log("Brownout monitor started")

    while True:
        time.sleep(BROWNOUT_CHECK_INTERVAL)

        if shutdown_triggered:
            continue

        if check_undervoltage():
            brownout_counter += 1
            log(f"Undervoltage detected ({brownout_counter})")

            if (
                BROWNOUT_SHUTDOWN and
                brownout_counter >= BROWNOUT_TRIGGER_COUNT
            ):
                log("Brownout threshold reached — shutting down")
                safe_shutdown("brownout")
        else:
            brownout_counter = 0

# ============================================================
# OPTIONAL POWER-FAIL
# ============================================================

if ENABLE_POWER_FAIL:
    power_fail_in = Button(
        POWER_FAIL_PIN,
        pull_up=True,
        bounce_time=0.02
    )

    def power_fail_triggered():
        if time.time() - boot_time < BOOT_IGNORE_TIME:
            return
        if shutdown_triggered:
            return

        log("POWER FAIL detected — initiating hold-up shutdown")
        safe_shutdown("power-fail")

    power_fail_in.when_released = power_fail_triggered
    log("Power-fail hold-up ENABLED")

# ============================================================
# GPIO BUTTONS
# ============================================================

shutdown_sw = Button(
    SHUTDOWN_PIN,
    pull_up=True,
    bounce_time=BOUNCE_TIME,
)

reset_btn = Button(
    RESET_PIN,
    pull_up=True,
    bounce_time=BOUNCE_TIME,
)

def shutdown_edge():
    if time.time() - boot_time < BOOT_IGNORE_TIME:
        log("Ignoring switch during boot window")
        return
    if shutdown_triggered:
        return
    if shutdown_sw.is_pressed:
        safe_shutdown("switch")

shutdown_sw.when_pressed = shutdown_edge
reset_btn.when_pressed = safe_reboot

# ============================================================
# SYSTEMD WATCHDOG THREAD
# ============================================================

def watchdog_ping():
    if not SYSTEMD_NOTIFY:
        return

    log("systemd watchdog enabled")

    while True:
        notifier.notify("WATCHDOG=1")
        time.sleep(20)

# ============================================================
# STARTUP TASKS
# ============================================================

threading.Thread(target=brownout_monitor, daemon=True).start()
threading.Thread(target=watchdog_ping, daemon=True).start()

# Run RO check shortly after boot
threading.Timer(10, enforce_ro_root_once).start()

if SYSTEMD_NOTIFY:
    notifier.notify("READY=1")

log("Power manager started — SAFE=LOW (running)")

pause()