#!/usr/bin/env python3
"""
Fleet email alert engine
"""

import smtplib
import json
from email.message import EmailMessage
from pathlib import Path

CONFIG = Path("/etc/pm-alert.json")
STATUS = Path("/boot/pm-fleet/status.json")


def load(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def send_mail(cfg, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    msg.set_content(body)

    with smtplib.SMTP(cfg["smtp"], cfg["port"]) as s:
        if cfg.get("tls"):
            s.starttls()
        if cfg.get("user"):
            s.login(cfg["user"], cfg["pass"])
        s.send_message(msg)


def main():
    cfg = load(CONFIG)
    status = load(STATUS)

    score = status.get("boot_health", {}).get("score", 100)

    if score < 50:
        send_mail(
            cfg,
            "🚨 Pi health critical",
            f"Health score: {score}"
        )


if __name__ == "__main__":
    main()