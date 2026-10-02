#!/usr/bin/env python3
"""Run one portal template through the scaffolder API. Runs ON THE BRANCH DESKTOP.

    run_template.py <backstage token> <templateRef> '<values as JSON>'

The portal is reachable only from the branch side, so this is copied into the
desktop container and run there, with a token from `portal_signin.sh`. It is
what a branch user's click does -- the same template, the same steps, the same
signed-in identity -- without a browser.

Prints one line per step as it starts and finishes, then a final line
`RESULT {...}` carrying the task status, the wall clock and each step's
duration, which is what `scripts/demo_rehearsal.py` reads. Standard library
only: the desktop has python3 and nothing else.
"""

from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.request

PORTAL = "https://10.90.0.11:32001"
TIMEOUT = 900


def main() -> int:
    token, ref, values = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
    # The portal's certificate is self-signed; the desktop trusts it in Firefox,
    # not necessarily in python's bundle. What is under test is the template.
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def call(method: str, path: str, body: object = None) -> object:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(PORTAL + path, data, headers, method=method)  # noqa: S310 - fixed https URL
        with urllib.request.urlopen(request, context=context, timeout=60) as response:  # noqa: S310
            return json.load(response)

    start = time.monotonic()
    task = call("POST", "/api/scaffolder/v2/tasks", {"templateRef": ref, "values": values})
    task_id = task["id"]  # type: ignore[index]
    print(f"task {task_id}", flush=True)

    seen = 0
    started: dict[str, float] = {}
    steps: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    status = "processing"
    while time.monotonic() - start < TIMEOUT:
        events = call("GET", f"/api/scaffolder/v2/tasks/{task_id}/events?after={seen}")
        for event in events:  # type: ignore[union-attr]
            seen = max(seen, event["id"])
            body = event.get("body", {})
            step, state = body.get("stepId"), body.get("status")
            now = time.monotonic() - start
            if event["type"] == "log" and step and state:
                if state == "processing":
                    started[step] = now
                else:
                    steps[step] = {"status": state, "seconds": round(now - started.get(step, now), 1)}
                print(f"{now:6.1f}s  {step}: {state}", flush=True)
            elif event["type"] == "log" and "error" in (body.get("message") or "").lower():
                errors.append(body["message"][:600])
                print(f"{now:6.1f}s  {body['message'][:600]}", flush=True)
        status = call("GET", f"/api/scaffolder/v2/tasks/{task_id}")["status"]  # type: ignore[index]
        if status in {"completed", "failed", "cancelled"}:
            break
        time.sleep(2)

    result = {
        "task": task_id,
        "status": status,
        "seconds": round(time.monotonic() - start, 1),
        "steps": steps,
        "errors": errors,
    }
    print("RESULT " + json.dumps(result), flush=True)
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
