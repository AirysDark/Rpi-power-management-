#!/bin/bash
set -euo pipefail

INSTALL_DIR="/opt/retroflag-picase"
SERVICE_FILE="/etc/systemd/system/retroflag-picase.service"

# re-mount "/" and "/boot" filesystems as read/write
remount_rw() {
    echo "Re-mounting readonly filesystems as read/write."
    mount -o remount,rw "/"
    mount -o remount,rw "/boot"
}

echo "[1/6] Installing dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-rpi.gpio

echo "[2/6] Installing files to ${INSTALL_DIR} ..."
sudo mkdir -p "${INSTALL_DIR}"
sudo install -m 0755 opt/service.py "${INSTALL_DIR}/service.py"
sudo install -m 0755 opt/shutdown.retropie "${INSTALL_DIR}/shutdown.retropie"

echo "[3/6] Installing systemd service ..."
sudo install -m 0644 etc/retroflag-picase.service "${SERVICE_FILE}"
sudo systemctl daemon-reload

# Optional: help user add useful overlays on Raspberry Pi OS
BOOTCFG="/boot/config.txt"
if [ -f /boot/firmware/config.txt ]; then
  BOOTCFG="/boot/firmware/config.txt"
fi

echo "[4/6] (Optional) Add recommended GPIO overlays (gpio-shutdown, gpio-safepower)"
echo "    File: ${BOOTCFG}"
# Only append if not present
if ! grep -q "^dtoverlay=gpio-shutdown" "${BOOTCFG}" 2>/dev/null; then
  echo "dtoverlay=gpio-shutdown,gpio_pin=17,active_low=1,gpio_pull=up" | sudo tee -a "${BOOTCFG}" >/dev/null
fi
if ! grep -q "^dtoverlay=gpio-poweroff" "${BOOTCFG}" 2>/dev/null; then
  echo "dtoverlay=gpio-safepower,gpiopin=22,active_low=0" | sudo tee -a "${BOOTCFG}" >/dev/null
fi

echo "[5/6] Enabling and starting service ..."
sudo systemctl enable retroflag-picase.service
sudo systemctl restart retroflag-picase.service

echo "[6/6] Done."
echo "Check status:   sudo systemctl status retroflag-picase.service"
echo "Reboot to apply overlays (optional but recommended): sudo reboot"
