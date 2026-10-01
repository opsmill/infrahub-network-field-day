#!/usr/bin/env python3
"""Reconcile FirewallAccess objects onto the lab's vSRX.

There is no Crossplane provider for Junos worth depending on, so this is the
piece that closes the loop: Crossplane composes a FirewallAccess, and this turns
it into an address object, an application object and a security policy on the
firewall -- then keeps checking that they are still there.

Design notes worth knowing before changing anything here:

* It POLLS rather than watches. A watch would react faster and would not notice
  that someone deleted a generated policy in the Junos CLI; a poll re-asserts
  the whole desired state every interval, which is the same drift correction
  Crossplane gives the Kubernetes side. `make xp-drift` proves that story for
  Cilium; deleting a generated policy on the firewall proves it here.

* It drives the CLI over SSH rather than NETCONF. Junos has perfectly good
  NETCONF and ncclient would be the obvious choice; the CLI needs no dependency
  beyond paramiko, and set-commands are what anyone debugging this will paste
  into `make fw-console` anyway.

* It commits only when something actually changed. `configure private`, then
  `show | compare`, then commit or rollback -- otherwise a reconcile every
  twenty seconds fills the rollback history with identical no-op commits and
  makes a real change impossible to find.

* Everything generated is named `aa-<resource name>`, so a human looking at the
  box can tell at a glance what is hand-written and what belongs to a request.
  Anything in that namespace with no matching FirewallAccess is an orphan and
  gets removed.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import paramiko

# ---------------------------------------------------------------- settings --

FW_HOST = os.environ.get("FW_HOST", "172.20.41.31")
FW_USER = os.environ.get("FW_USER", "admin")
# vrnetlab's default, which containerlab passes to the node and
# configs/fw/vsrx/junos.conf hashes into the committed config.
FW_PASSWORD = os.environ.get("FW_PASSWORD", "admin@123")
INTERVAL = int(os.environ.get("RECONCILE_INTERVAL", "20"))

OBJECT_PREFIX = "aa-"
FINALIZER = "otternet.lab/firewall-cleanup"

GROUP = "otternet.lab"
VERSION = "v1alpha1"
PLURAL = "firewallaccesses"


def log(*a):
    print(f"[fw-controller {datetime.now(timezone.utc):%H:%M:%S}]", *a, flush=True)


def now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def obj_name(name: str) -> str:
    return f"{OBJECT_PREFIX}{name}"


def subnet_parts(destination: str) -> tuple[str, int]:
    if "/" in destination:
        addr, bits = destination.split("/", 1)
        return addr, int(bits)
    return destination, 32


def dotted_mask(bits: int) -> str:
    mask = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF
    return ".".join(str((mask >> s) & 0xFF) for s in (24, 16, 8, 0))


# ------------------------------------------------------- kubernetes client --


class Kube:
    """The smallest possible in-cluster API client.

    Deliberately stdlib-only. The controller needs list, patch and patch-status
    on exactly one resource, and pulling in the kubernetes package for that
    would be most of the image size for none of the benefit.
    """

    SA = "/var/run/secrets/kubernetes.io/serviceaccount"

    def __init__(self):
        host = os.environ["KUBERNETES_SERVICE_HOST"]
        port = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS", "443")
        self.base = f"https://{host}:{port}"
        with open(f"{self.SA}/token") as fh:
            self.token = fh.read().strip()
        self.ctx = ssl.create_default_context(cafile=f"{self.SA}/ca.crt")

    def _request(self, method: str, path: str, body=None, content_type=None):
        req = urllib.request.Request(self.base + path, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/json")
        if body is not None:
            req.add_header("Content-Type", content_type or "application/json")
            req.data = json.dumps(body).encode()
        with urllib.request.urlopen(req, context=self.ctx, timeout=30) as resp:
            return json.loads(resp.read() or b"{}")

    def list_access(self):
        return self._request("GET", f"/apis/{GROUP}/{VERSION}/{PLURAL}").get("items", [])

    def patch_access(self, name: str, patch: dict):
        return self._request("PATCH", f"/apis/{GROUP}/{VERSION}/{PLURAL}/{name}", patch, "application/merge-patch+json")

    def patch_status(self, name: str, status: dict):
        return self._request(
            "PATCH",
            f"/apis/{GROUP}/{VERSION}/{PLURAL}/{name}/status",
            {"status": status},
            "application/merge-patch+json",
        )


# --------------------------------------------------------------- transport --


class Session:
    """An interactive SSH CLI session.

    Interactive shell rather than exec channels, because both CLIs are modal --
    `configure` changes what the next line means -- so the session has to be
    held open across a whole block.
    """

    def __init__(self, host, user, password, timeout=30):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            host,
            username=user,
            password=password,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        self.shell = self.client.invoke_shell(width=250, height=1000)
        self.shell.settimeout(timeout)
        self.prompt = None  # set by the driver once it knows the flavour

    def read(self, prompt: re.Pattern, idle=0.2, limit=25.0) -> str:
        buf, deadline = b"", time.time() + limit
        while time.time() < deadline:
            got = False
            while self.shell.recv_ready():
                buf += self.shell.recv(65536)
                got = True
            if prompt.search(buf):
                return buf.decode("utf-8", "replace")
            time.sleep(idle if not got else 0.02)
        text = buf.decode("utf-8", "replace")
        log(f"WARNING: no prompt within {limit}s; last output was {text[-120:]!r}")
        return text

    def send(self, line: str, prompt: re.Pattern | None = None) -> str:
        self.shell.send(line + "\n")
        return self.read(prompt or self.prompt)

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass


# ----------------------------------------------------------------- drivers --

JUNOS_ERRORS = [
    r"^error:",
    r"syntax error",
    r"unknown command",
    r"invalid value",
    r"missing argument",
    r"commit failed",
]


class JunosDriver:
    OPERATIONAL = re.compile(rb"(?:^|[\r\n])[\w.\-]+@[\w.\-]+>\s*$")
    CONFIG = re.compile(rb"(?:^|[\r\n])[\w.\-]+@[\w.\-]+#\s*$")
    EITHER = re.compile(rb"(?:^|[\r\n])[\w.\-]+@[\w.\-]+[>#]\s*$")

    def __init__(self, session: Session):
        self.s = session
        self.s.prompt = self.EITHER
        # Junos pages by default and a `show configuration` is long enough to
        # hit it, which stalls a scripted read on ---(more)--- forever.
        self.s.send("set cli screen-length 0")
        self.s.send("set cli screen-width 0")

    def _check(self, out: str, line: str, failures: list[str]) -> None:
        for pattern in JUNOS_ERRORS:
            if re.search(pattern, out, re.IGNORECASE | re.MULTILINE):
                detail = next((l.strip() for l in out.splitlines() if re.search(pattern, l, re.IGNORECASE)), pattern)
                failures.append(f"{line!r}: {detail}")
                return

    def list_managed(self) -> dict[str, str]:
        out = self.s.send('show configuration security policies | display set | match " policy aa-"')
        found = {}
        for m in re.finditer(r"from-zone (\S+) to-zone (\S+) policy (aa-\S+)", out):
            src, dst, pol = m.groups()
            found[pol] = f"{src}->{dst}/{pol}"
        return found

    def _configure(self, lines: list[str]) -> list[str]:
        """Apply a set-block, committing only if it actually changed something.

        `configure private` plus a compare-before-commit is the difference
        between a rollback history that shows real changes and one filled with
        fifty identical no-op commits, three a minute, because the reconcile
        loop keeps re-asserting state that was already correct.
        """
        failures: list[str] = []
        self.s.send("configure private", self.CONFIG)
        for line in lines:
            out = self.s.send(line, self.CONFIG)
            self._check(out, line, failures)

        diff = self.s.send("show | compare", self.CONFIG)
        # The echo of the command itself is in the buffer, so look for the
        # +/- lines a real diff produces rather than for any output at all.
        changed = any(l.startswith(("+", "-", "!")) for l in diff.splitlines() if l.strip() not in ("", "[edit]"))

        if failures or not changed:
            self.s.send("rollback", self.CONFIG)
            self.s.send("exit", self.OPERATIONAL)
            return failures

        out = self.s.send("commit and-quit", self.EITHER)
        self._check(out, "commit and-quit", failures)
        if "commit complete" not in out.lower() and not failures:
            failures.append(f"'commit and-quit': no commit confirmation: {out[-160:]!r}")
        if failures:
            # A failed commit leaves the session in configuration mode. Leaving
            # it there makes the NEXT object's `configure private` fail too, so
            # one bad grant would take every other grant down with it.
            self.s.send("rollback", self.CONFIG)
            self.s.send("exit", self.OPERATIONAL)
        return failures

    def apply(self, item, state) -> tuple[str, list[str]]:
        name = item["metadata"]["name"]
        spec = item["spec"]
        tag = obj_name(name)
        src = spec.get("sourceZone", "branch")
        dst = spec.get("destinationZone", "k8s-prod")
        pair = f"security policies from-zone {src} to-zone {dst} policy {tag}"
        addr, bits = subnet_parts(spec["destination"])
        note = f"otternet access broker: {name} for {spec.get('requester', 'unknown')}"

        lines = [f"set security address-book global address {tag} {addr}/{bits}"]
        apps = []
        for port in spec["ports"]:
            app = f"{tag}-p{port}"
            apps.append(app)
            lines += [
                f"set applications application {app} protocol tcp",
                f"set applications application {app} destination-port {port}",
            ]
        lines += [
            f"set {pair} match source-address {spec.get('sourceAddress', 'branch-users')}",
            f"set {pair} match destination-address {tag}",
        ]
        lines += [f"set {pair} match application {app}" for app in apps]
        lines += [
            f"set {pair} then permit",
            f"set {pair} then log session-init",
            f"set {pair} then log session-close",
        ]
        # `annotate` acts on a child of the current edit level, so it needs the
        # zone pair to be the current level -- a full path from the top is
        # rejected. The comment is what puts the requester's name on the box
        # next to the rule, which is most of the point of having it.
        lines += [
            f"edit security policies from-zone {src} to-zone {dst}",
            f'annotate policy {tag} "{note}"',
            "top",
        ]
        # No `insert` needed. Junos consults the default policy only after
        # every policy in the zone pair has been tried, so there is no trailing
        # deny for a grant to end up underneath -- appending is correct. The
        # anti-spoofing deny is already first in the pair and stays there.
        return f"{src}->{dst}/{tag}", self._configure(lines)

    def remove(self, name, state) -> None:
        tag = obj_name(name)
        ref = state.get("policyRef") or ""
        m = re.match(r"(\S+)->(\S+)/", ref)
        src, dst = m.groups() if m else ("branch", "k8s-prod")
        lines = [
            f"delete security policies from-zone {src} to-zone {dst} policy {tag}",
            f"delete security address-book global address {tag}",
        ]
        # One application object per port, and the ports are not carried in the
        # ref, so find them on the box rather than guessing. This runs in
        # operational mode, before _configure enters configuration mode.
        apps = self.s.send(f'show configuration applications | display set | match " {tag}-p"')
        for app in sorted(set(re.findall(rf"application ({re.escape(tag)}-p\d+)", apps))):
            lines.append(f"delete applications application {app}")
        self._configure(lines)


def connect() -> tuple[Session, JunosDriver]:
    """Open a session, and refuse to drive anything that is not Junos.

    The prompt check is cheap insurance rather than ceremony: every command this
    controller sends is Junos syntax, and against a different CLI they would
    fail one by one with parse errors that look like a bug in the grant rather
    than the wrong box being on the other end of the socket.
    """
    session = Session(FW_HOST, FW_USER, FW_PASSWORD)
    banner = session.read(re.compile(rb"(?:[\w.\-]+@[\w.\-]+[>#]|[\w.-]+\s*#)\s*$"), limit=30.0)
    last = banner.strip().splitlines()[-1] if banner.strip() else ""
    if not re.search(r"@[\w.\-]+\s*[>#]\s*$", last):
        session.close()
        raise RuntimeError(
            f"{FW_HOST} does not present a Junos prompt (got {last.strip()!r}); "
            "refusing to push Junos configuration at it"
        )
    return session, JunosDriver(session)


def set_ready(
    kube: Kube,
    name: str,
    ok: bool,
    reason: str,
    message: str,
    generation: int,
    state: dict,
    ports: list[int],
    current: dict | None = None,
):
    # A reconcile that changed nothing should not write anything: without this
    # the loop patches every object every interval, which fills the audit log
    # with noise and makes a real transition impossible to spot.
    existing = ((current or {}).get("conditions") or [{}])[0]
    if (
        existing.get("type") == "Ready"
        and existing.get("status") == ("True" if ok else "False")
        and existing.get("reason") == reason
        and existing.get("message") == message[:1024]
        and (current or {}).get("policyRef") == state.get("policyRef")
        and (current or {}).get("observedGeneration") == generation
    ):
        return

    status = {
        "conditions": [
            {
                "type": "Ready",
                "status": "True" if ok else "False",
                "reason": reason,
                "message": message[:1024],
                "lastTransitionTime": now_rfc3339(),
            }
        ],
        "observedGeneration": generation,
        "portSummary": ",".join(str(p) for p in ports),
    }
    if state.get("policyRef"):
        status["policyRef"] = state["policyRef"]
    try:
        kube.patch_status(name, status)
    except urllib.error.HTTPError as exc:
        log(f"status patch for {name} failed: {exc}")


def reconcile(kube: Kube) -> None:
    started = time.time()
    items = kube.list_access()
    wanted: set[str] = set()

    # Connect even with nothing declared: an orphan sweep against an empty list
    # is how a grant revoked while the controller was down gets cleaned up.
    session, driver = connect()
    try:
        managed = driver.list_managed()

        for item in items:
            meta = item["metadata"]
            name = meta["name"]
            spec = item.get("spec", {})
            status = item.get("status", {}) or {}
            generation = meta.get("generation", 0)
            state = {"policyRef": status.get("policyRef")}

            if meta.get("deletionTimestamp"):
                log(f"revoking {name} ({state.get('policyRef') or 'no ref recorded'})")
                driver.remove(name, state)
                kube.patch_access(
                    name, {"metadata": {"finalizers": [f for f in meta.get("finalizers", []) if f != FINALIZER]}}
                )
                continue

            if FINALIZER not in meta.get("finalizers", []):
                kube.patch_access(name, {"metadata": {"finalizers": meta.get("finalizers", []) + [FINALIZER]}})

            ref, failures = driver.apply(item, state)
            state["policyRef"] = ref
            wanted.add(obj_name(name))

            if failures:
                message = "; ".join(failures)
                log(f"{name}: JunosRejected: {message}")
                set_ready(kube, name, False, "JunosRejected", message, generation, state, spec.get("ports", []), status)
            else:
                set_ready(
                    kube,
                    name,
                    True,
                    "Applied",
                    f"{ref} permits {spec.get('sourceAddress')} -> "
                    f"{spec.get('destination')} on "
                    f"{','.join(str(p) for p in spec.get('ports', []))}",
                    generation,
                    state,
                    spec.get("ports", []),
                    status,
                )

        # ---- orphans -------------------------------------------------------
        # A generated policy with no FirewallAccess behind it is a rule nobody
        # asked for. That happens after a controller crash between the firewall
        # write and the finalizer removal, and it is exactly the case where a
        # firewall quietly accumulates access nobody can account for.
        for tag, ref in managed.items():
            if tag not in wanted:
                log(f"pruning orphaned policy {ref}")
                orphan = tag[len(OBJECT_PREFIX) :]
                driver.remove(orphan, {"policyRef": ref})
    finally:
        session.close()

    log(f"pass complete: {len(items)} object(s), {len(wanted)} active grant(s), {time.time() - started:.1f}s")


def main() -> int:
    log(f"reconciling FirewallAccess against {FW_HOST} every {INTERVAL}s")
    kube = Kube()
    while True:
        try:
            reconcile(kube)
        except Exception as exc:  # noqa: BLE001 -- a controller must not exit
            log(f"reconcile failed: {type(exc).__name__}: {exc}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
