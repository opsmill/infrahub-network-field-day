#!/usr/bin/env python3
"""The self-service access portal a branch user actually clicks.

It owns no state. Everything it shows is read back from the Kubernetes API and
everything it does is a create, a patch or a delete of an AppAccess -- so the
portal can be restarted, bypassed with kubectl, or removed entirely, and the
answer to "who has access to what" does not change. That is the point of
putting the request on the platform API instead of in a database behind a form.

Stdlib only, deliberately: the whole app is one file and one `python:3.12-slim`
layer, which is small enough to import into three k3s nodes by hand.
"""

from __future__ import annotations

import html
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CATALOG_PATH = os.environ.get("CATALOG_PATH", "/etc/access/catalog.json")
LISTEN_PORT = int(os.environ.get("PORT", "8080"))
GROUP, VERSION = "otternet.lab", "v1alpha1"


# ------------------------------------------------------- kubernetes client --


class Kube:
    SA = "/var/run/secrets/kubernetes.io/serviceaccount"

    def __init__(self):
        host = os.environ["KUBERNETES_SERVICE_HOST"]
        port = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS", "443")
        self.base = f"https://{host}:{port}"
        with open(f"{self.SA}/token") as fh:
            self.token = fh.read().strip()
        self.ctx = ssl.create_default_context(cafile=f"{self.SA}/ca.crt")

    def call(self, method, path, body=None, content_type=None):
        req = urllib.request.Request(self.base + path, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/json")
        if body is not None:
            req.add_header("Content-Type", content_type or "application/json")
            req.data = json.dumps(body).encode()
        with urllib.request.urlopen(req, context=self.ctx, timeout=20) as resp:
            return json.loads(resp.read() or b"{}")

    def list(self, plural):
        try:
            return self.call("GET", f"/apis/{GROUP}/{VERSION}/{plural}").get("items", [])
        except urllib.error.HTTPError as exc:
            if exc.code == 404:  # CRD not installed yet
                return []
            raise

    def create_appaccess(self, obj):
        return self.call("POST", f"/apis/{GROUP}/{VERSION}/appaccesses", obj)

    def patch_appaccess(self, name, patch):
        return self.call("PATCH", f"/apis/{GROUP}/{VERSION}/appaccesses/{name}", patch, "application/merge-patch+json")

    def delete_appaccess(self, name):
        return self.call("DELETE", f"/apis/{GROUP}/{VERSION}/appaccesses/{name}")


# -------------------------------------------------------------------- view --

STYLE = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin:0; background:#111820; color:#e8eef5;
       font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
header { background:#18232f; border-bottom:1px solid #26364a; padding:18px 28px; }
h1 { margin:0; font-size:19px; letter-spacing:.2px; }
header p { margin:4px 0 0; color:#8fa3b8; font-size:13px; }
main { max-width:960px; margin:0 auto; padding:24px 28px 48px; }
.card { background:#18232f; border:1px solid #26364a; border-radius:10px;
        padding:18px 20px; margin-bottom:14px; }
.row { display:flex; align-items:flex-start; gap:18px; justify-content:space-between; }
.app-name { font-weight:600; font-size:16px; }
.app-desc { color:#8fa3b8; font-size:13px; margin-top:3px; }
dl { display:grid; grid-template-columns:auto 1fr; gap:2px 12px;
     margin:12px 0 0; font-size:12.5px; color:#8fa3b8; }
dt { color:#607287; }
dd { margin:0; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.badge { display:inline-block; padding:3px 10px; border-radius:20px;
         font-size:12px; font-weight:600; white-space:nowrap; }
.b-none    { background:#243244; color:#8fa3b8; }
.b-pending { background:#4a3a12; color:#f3c969; }
.b-working { background:#123a4a; color:#69c9f3; }
.b-granted { background:#123a24; color:#5fd08a; }
.b-error   { background:#4a1a1a; color:#f38b8b; }
button { font:inherit; font-weight:600; border:0; border-radius:7px;
         padding:8px 15px; cursor:pointer; }
.primary { background:#2f6fb5; color:#fff; }
.approve { background:#2f8f57; color:#fff; }
.danger  { background:#3a2530; color:#f0a0b8; }
input, textarea { font:inherit; background:#111820; color:#e8eef5;
                  border:1px solid #2c3e54; border-radius:7px; padding:7px 10px; }
form.inline { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
a { color:#69a9f3; }
.note { color:#6d829a; font-size:12.5px; margin-top:22px; }
.path { font-family:ui-monospace,monospace; font-size:12px; color:#8fa3b8;
        background:#111820; border:1px solid #26364a; border-radius:7px;
        padding:10px 12px; margin-top:6px; white-space:pre-wrap; }
"""

BADGES = {
    "none": ("b-none", "No access"),
    "pending": ("b-pending", "Awaiting approval"),
    "working": ("b-working", "Provisioning"),
    "granted": ("b-granted", "Access granted"),
    "error": ("b-error", "Failed"),
}


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def page(body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="6">
<title>Application access &mdash; branch office</title>
<style>{STYLE}</style></head>
<body>
<header>
  <h1>Application access</h1>
  <p>Branch office self-service &mdash; requests are granted through the
     datacentre firewall, not around it.</p>
</header>
<main>{body}</main>
</body></html>""".encode()


def render(catalog, requests_by_app, fw_by_name) -> bytes:
    out = []
    for entry in catalog:
        key = entry["key"]
        req = requests_by_app.get(key)
        state, detail = "none", []

        if req:
            spec = req.get("spec", {})
            status = req.get("status", {}) or {}
            fw = fw_by_name.get(req["metadata"]["name"], {})
            fw_status = fw.get("status") or {}
            fw_ready = next((c for c in fw_status.get("conditions", []) if c.get("type") == "Ready"), {})

            if not spec.get("approved"):
                state = "pending"
            elif fw_ready.get("status") == "True":
                state = "granted"
            elif fw_ready.get("status") == "False":
                state = "error"
            else:
                state = "working"

            detail = [
                ("Requested by", spec.get("requester")),
                ("Reason", spec.get("justification") or "—"),
                ("Approved by", spec.get("approvedBy") or "—"),
                ("Address", status.get("vip") or spec.get("access", {}).get("vip")),
                ("Firewall policy", fw_status.get("policyId") or "not applied yet"),
            ]
            if fw_ready.get("status") == "False":
                detail.append(("Error", fw_ready.get("message")))

        cls, label = BADGES[state]
        provision = "deployed on demand" if entry.get("provision") else "already running"
        vip = entry.get("vip", "")

        actions = ""
        if state == "none":
            actions = f"""
            <form class="inline" method="post" action="/request">
              <input type="hidden" name="app" value="{esc(key)}">
              <input name="requester" value="branchuser" size="12" aria-label="Your name">
              <input name="justification" placeholder="Why do you need it?" size="26">
              <button class="primary" type="submit">Request access</button>
            </form>"""
        elif state == "pending":
            actions = f"""
            <form class="inline" method="post" action="/approve">
              <input type="hidden" name="app" value="{esc(key)}">
              <input name="approver" value="netops" size="10" aria-label="Approver">
              <button class="approve" type="submit">Approve</button>
            </form>
            <form class="inline" method="post" action="/revoke">
              <input type="hidden" name="app" value="{esc(key)}">
              <button class="danger" type="submit">Withdraw</button>
            </form>"""
        else:
            link = (
                f'<a href="http://{esc(vip)}/" target="_blank">Open http://{esc(vip)}/</a>'
                if state == "granted"
                else ""
            )
            actions = f"""
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
              {link}
              <form class="inline" method="post" action="/revoke">
                <input type="hidden" name="app" value="{esc(key)}">
                <button class="danger" type="submit">Revoke access</button>
              </form>
            </div>"""

        rows = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in detail)
        out.append(f"""
        <section class="card">
          <div class="row">
            <div>
              <div class="app-name">{esc(entry["displayName"])}</div>
              <div class="app-desc">{esc(entry.get("description", ""))}
                &middot; {esc(provision)} &middot; {esc(vip)}</div>
            </div>
            <span class="badge {cls}">{esc(label)}</span>
          </div>
          {f"<dl>{rows}</dl>" if rows else ""}
          <div style="margin-top:14px">{actions}</div>
        </section>""")

    out.append("""
    <p class="note">Every button here is a write to the Kubernetes API and
    nothing else. Approving a request flips one field on an AppAccess; Crossplane
    composes the application and a FirewallAccess from it, and the fw-controller
    turns that into a security policy on the vSRX. Revoking
    deletes the AppAccess and the policy goes with it.</p>
    <div class="path">kubectl get appaccess
kubectl get firewallaccess
kubectl describe appaccess access-&lt;app&gt;</div>""")
    return page("".join(out))


# ------------------------------------------------------------------ server --


class Handler(BaseHTTPRequestHandler):
    server_version = "otternet-access-portal"
    catalog: list = []
    kube: Kube = None

    def log_message(self, fmt, *args):
        print(f"[portal] {self.address_string()} {fmt % args}", flush=True)

    # -- helpers --

    def _entry(self, key):
        return next((e for e in self.catalog if e["key"] == key), None)

    def _form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode()
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def _redirect(self):
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def _fail(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode())

    # -- routes --

    def do_GET(self):
        if self.path.startswith("/healthz"):
            return self._fail(200, "ok")
        if self.path != "/":
            return self._fail(404, "not found")
        try:
            requests_by_app = {a["spec"]["app"]: a for a in self.kube.list("appaccesses")}
            fw_by_name = {f["metadata"]["name"]: f for f in self.kube.list("firewallaccesses")}
        except Exception as exc:  # noqa: BLE001
            return self._fail(500, f"cannot reach the Kubernetes API: {exc}")

        body = render(self.catalog, requests_by_app, fw_by_name)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        form = self._form()
        entry = self._entry(form.get("app", ""))
        if entry is None:
            return self._fail(400, "unknown application")
        name = f"access-{entry['key']}"

        try:
            if self.path == "/request":
                obj = {
                    "apiVersion": f"{GROUP}/{VERSION}",
                    "kind": "AppAccess",
                    "metadata": {"name": name},
                    "spec": {
                        "app": entry["key"],
                        "displayName": entry["displayName"],
                        "requester": form.get("requester") or "branchuser",
                        "justification": form.get("justification") or "",
                        # An entry the catalog marks as auto-approved skips the
                        # gate entirely -- the request is still recorded, and
                        # the difference between the two paths is one field.
                        "approved": not entry.get("requiresApproval", True),
                        "approvedBy": "" if entry.get("requiresApproval", True) else "auto",
                        "source": entry.get("source", {}),
                        "access": {"vip": entry["vip"], "ports": entry.get("ports", [80])},
                        **({"provision": entry["provision"]} if entry.get("provision") else {}),
                    },
                }
                self.kube.create_appaccess(obj)
            elif self.path == "/approve":
                self.kube.patch_appaccess(
                    name,
                    {
                        "spec": {
                            "approved": True,
                            "approvedBy": form.get("approver") or "netops",
                        }
                    },
                )
            elif self.path == "/revoke":
                self.kube.delete_appaccess(name)
            else:
                return self._fail(404, "not found")
        except urllib.error.HTTPError as exc:
            return self._fail(502, f"Kubernetes API said {exc.code}: {exc.read().decode()}")

        self._redirect()


def main():
    with open(CATALOG_PATH) as fh:
        Handler.catalog = json.load(fh)["applications"]
    Handler.kube = Kube()
    print(f"[portal] serving {len(Handler.catalog)} catalog entries on :{LISTEN_PORT}", flush=True)
    ThreadingHTTPServer(("", LISTEN_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
