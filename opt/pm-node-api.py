#!/usr/bin/env python3
"""
Lightweight node telemetry endpoint

Serves:
  GET /api/status

Very low overhead.
"""

import json
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = 8090
STATUS_FILE = Path("/boot/pm-fleet/status.json")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/status":
            self.send_response(404)
            self.end_headers()
            return

        if not STATUS_FILE.exists():
            body = b"{}"
        else:
            body = STATUS_FILE.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    print(f"[pm-node] serving on :{PORT}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()