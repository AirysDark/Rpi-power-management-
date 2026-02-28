# Rpi Supervisor

Production-grade lifecycle, power, integrity and fleet management system
for Raspberry Pi 3 / 4 / 5.

Rpi Supervisor provides:

-   Safe hardware shutdown control
-   Brownout detection and protection
-   Read-only root enforcement
-   Crash-only boot detection
-   Watchdog heartbeat monitoring
-   Secure device key rotation
-   UDP node discovery
-   Fleet dashboard aggregation
-   Remote authenticated command execution
-   Automatic Git-based update system with rollback protection

Designed for embedded, kiosk, infrastructure, and fleet deployments.

------------------------------------------------------------------------


```bash
rm -rf /run/rpi-supervisor && mkdir -p /run/rpi-supervisor && curl -L https://github.com/AirysDark/rpi-supervisor/archive/refs/heads/main.zip -o /run/rpi-supervisor.zip && unzip -q /run/rpi-supervisor.zip -d /run && mv /run/rpi-supervisor-main /run/rpi-supervisor && rm /run/rpi-supervisor.zip && chmod +x /run/rpi-supervisor/install.sh && sudo /run/rpi-supervisor/install.sh
```
# 🧠 Architecture Overview

Rpi Supervisor consists of two layers:

## 1️⃣ Node Layer (Runs on each Pi)

Main daemon: - `rsupd` --- Core supervisor process

Supporting components: - `rsup-beacon` --- Secure UDP discovery beacon -
`rsup-node-api` --- Local status API (HTTP) - `rsup-cmd-agent` ---
Secure remote command agent - `rsup-boot-health` --- Boot scoring
system - `rsup-crash-capture` --- Crash-only log capture - `rsup-update`
--- Safe Git-based auto-updater - `rsup-key-rotate` --- Device key
rotation - `rsup-enable-ro-root` --- RO root enforcement -
`rsup-iofreeze` --- Pre-shutdown I/O freeze

------------------------------------------------------------------------

## 2️⃣ Fleet Layer (Central Server)

-   `rsup-fleetd` --- Fleet collector daemon
-   Web dashboard
-   Per-device key trust database
-   Remote command relay
-   Key promotion engine

------------------------------------------------------------------------

# 📂 Directory Layout

## Node

    /opt/rpi-supervisor/
        bin/
        version

    /etc/rpi-supervisor/
        device.json
        supervisor.conf
        device-key
        device-key.next
        update-channel

    /var/lib/rpi-supervisor/
        key-epoch
        boot-health.json

    /run/rpi-supervisor/
        watchdog.state
        clean-shutdown.flag

------------------------------------------------------------------------

## Fleet

    /opt/rpi-supervisor-fleet/
        rsup-fleetd
        pm-fleet-keys.json
        nodes.json
        web/

------------------------------------------------------------------------

# 🔐 Security Model

### Per-Device Keys

Each node has:

    /etc/rpi-supervisor/device-key
    /etc/rpi-supervisor/device-key.next
    /var/lib/rpi-supervisor/key-epoch

The fleet server stores:

``` json
{
  "devices": {
    "pi-01": {
      "active_key": "HEX",
      "next_key": "HEX",
      "epoch": 3
    }
  }
}
```

Features:

-   HMAC signed beacons
-   HMAC signed remote commands
-   Replay protection
-   Timestamp skew enforcement
-   Automatic next-key promotion
-   Epoch tracking

No shared fleet secret required.

------------------------------------------------------------------------

# 🔌 Hardware Features

-   Latching shutdown switch
-   Momentary reset button
-   SAFE power-cut signal output
-   Brownout detection (vcgencmd)
-   Optional power-fail hold-up input
-   Boot glitch protection

------------------------------------------------------------------------

# 📡 Node API

Default: `http://localhost:8090`

Endpoints:

    GET /health
    GET /api/status

------------------------------------------------------------------------

# 🛰 Fleet Dashboard

Default: `http://fleet-server:8088`

Features:

-   Auto-discovery
-   Offline detection
-   Boot health scoring
-   Remote reboot/shutdown/update
-   Key rotation trigger
-   Fleet health summary bar

------------------------------------------------------------------------

# 🔄 Update System

Rpi Supervisor updates from Git:

    /etc/rpi-supervisor/update-channel

Example:

    main
    beta
    stable

Update flow:

1.  Fetch origin
2.  Fast-forward only merge
3.  Restart service
4.  Full health validation:
    -   rsupd active
    -   API responds 200
    -   status endpoint valid JSON
    -   beacon socket bound
    -   watchdog heartbeat alive
    -   config loads
5.  If any fail → automatic rollback

Safe for production deployments.

------------------------------------------------------------------------

# ⚡ Read-Only Root Support

Designed for RO-root systems.

Requirements during update: - Temporary RW mount - Git operations
allowed

Runtime: - /run used for transient state - No persistent writes required

------------------------------------------------------------------------

# 🧯 Crash Detection

On shutdown: - `clean-shutdown.flag` written

On boot: - If missing → crash detected - Crash capture runs - Boot
health score reduced

------------------------------------------------------------------------

# 📈 Boot Health Scoring

Tracks:

-   Clean shutdowns
-   Brownouts
-   Watchdog failures
-   Crash loops

Score returned via API and shown in dashboard.

------------------------------------------------------------------------

# 🛠 Installation (Node)

``` bash
git clone https://github.com/AirysDark/rpi-supervisor /opt/rpi-supervisor
sudo systemctl enable rsupd
sudo systemctl start rsupd
```

------------------------------------------------------------------------

# 🛠 Installation (Fleet)

``` bash
git clone https://github.com/AirysDark/rpi-supervisor-fleet /opt/rpi-supervisor-fleet
sudo systemctl enable rsup-fleetd
sudo systemctl start rsup-fleetd
```

------------------------------------------------------------------------

# 📊 Production Capabilities

✔ Power-safe shutdown control\
✔ Embedded-safe operation\
✔ Secure device authentication\
✔ Fleet-scale remote control\
✔ Automatic safe updates\
✔ Rollback protection\
✔ Brownout-aware\
✔ Watchdog integrated\
✔ RO-root compatible

------------------------------------------------------------------------

# 🎯 Intended Use Cases

-   Digital signage
-   Edge compute nodes
-   Kiosk systems
-   Industrial controllers
-   Distributed Raspberry Pi clusters
-   Remote unattended deployments

------------------------------------------------------------------------

# 📜 License

MIT License

------------------------------------------------------------------------

# 🚀 Roadmap

-   Signed release verification
-   Fleet update orchestration
-   OTA staging directory swap
-   Alert engine integration
-   Fleet health quorum logic
