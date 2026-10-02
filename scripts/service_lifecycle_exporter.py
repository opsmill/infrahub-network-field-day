#!/usr/bin/env python3
"""Serve where every service request is in the pipeline, for the collector to scrape (cycle 035).

    python scripts/service_lifecycle_exporter.py            # the compose service, profile `metrics`
    curl 'http://127.0.0.1:8003/metrics?kinds=ServiceGeneric'

The logic is `solution_arista_avd.service_lifecycle`; this is the timer and the
HTTP server around it, and nothing else. It has NO configuration of its own:
the kinds it reports are the scrape's `?kinds=` parameter, which the collector's
artifact renders from the `service-lifecycle` monitoring profile. Without the
parameter it reports every kind.

Env:  INFRAHUB_ADDRESS                     default http://infrahub-server:8000
      INFRAHUB_API_TOKEN                   the `metrics-exporter` account's token (view only)
      OTTERNET_LIFECYCLE_POLL              seconds between polls, default 15
      OTTERNET_LIFECYCLE_LISTEN            default 0.0.0.0:8003
"""

from __future__ import annotations

import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

# The checkout's own copy, ahead of whatever the image installed: the compose
# service bind-mounts the repository, and this way a change here needs no
# `invoke build` to take effect.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solution_arista_avd.service_lifecycle import Exporter

ADDRESS = os.environ.get("INFRAHUB_ADDRESS", "http://infrahub-server:8000").rstrip("/")
TOKEN = os.environ.get("INFRAHUB_API_TOKEN", "")
POLL = float(os.environ.get("OTTERNET_LIFECYCLE_POLL", "15"))
LISTEN = os.environ.get("OTTERNET_LIFECYCLE_LISTEN", "0.0.0.0:8003")


def make_gql(client: httpx.Client) -> Any:
    def gql(query: str, variables: dict[str, Any], branch: str) -> dict[str, Any]:
        response = client.post(f"{ADDRESS}/graphql/{branch}", json={"query": query, "variables": variables})
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(str(payload["errors"])[:400])
        return payload.get("data") or {}

    return gql


def serve(exporter: Exporter) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path not in ("/metrics", "/"):
                self.send_error(404)
                return
            kinds = {k for value in parse_qs(url.query).get("kinds", []) for k in value.split(",") if k}
            body = exporter.metrics(kinds or None).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: Any) -> None:
            return  # one line per scrape every 30s is noise

    host, _, port = LISTEN.rpartition(":")
    server = ThreadingHTTPServer((host or "0.0.0.0", int(port)), Handler)  # noqa: S104
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    if not TOKEN:
        print("INFRAHUB_API_TOKEN is empty: run scripts/provision_metrics_exporter.py first", file=sys.stderr)
        return 2
    client = httpx.Client(headers={"X-INFRAHUB-KEY": TOKEN}, timeout=60)
    exporter = Exporter(make_gql(client), poll_seconds=POLL)
    serve(exporter)
    print(f"service-lifecycle exporter on {LISTEN}, polling {ADDRESS} every {POLL:.0f}s", flush=True)
    while True:
        started = time.monotonic()
        exporter.poll_safely()
        if not exporter.up:
            print(
                f"poll failed ({exporter.errors} so far), keeping the last snapshot: {exporter.last_error}", flush=True
            )
        time.sleep(max(1.0, POLL - (time.monotonic() - started)))


if __name__ == "__main__":
    sys.exit(main())
