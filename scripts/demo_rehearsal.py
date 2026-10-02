#!/usr/bin/env python3
"""Rehearse docs/docs/demo-runbook.md against the live lab, stopping short of every merge.

    uv run python scripts/demo_rehearsal.py                   # every act, about ten minutes
    uv run python scripts/demo_rehearsal.py --only four,five  # a subset
    uv run python scripts/demo_rehearsal.py --keep            # leave the branches to look at

WHY IT EXISTS. The runbook's acts were written from the templates and the
generators beneath them, and the first time they were rehearsed end to end three
of its claims were wrong in ways nothing else reported: a generated grant's
proposed change carried no border-leaf configuration, the Grafana form lacked
two required fields, and the "no route" gate was already open. Every one of
those passed `verify_bootstrap.sh`, because that script proves the lab is built,
not that the demo tells the truth about it.

WHAT IT CHANGES. Branches and proposed changes in Infrahub, all of them deleted
at the end -- including when an act fails. WITHOUT --merge NOTHING IS MERGED, and nothing touches
a device or the cluster: the acts that end in a merge are rehearsed up to the
merge, which is where the runbook's claims about review live. The requests go
through the portal as `alice`, from the branch desktop, exactly as a branch user
would make them.

Acts, in the order run:

  preflight  the read-only checks in "Before anyone is watching"
  four       scripts/demo_break_isolation.sh, its red check, and --revert
  one        "Exposed application, with access", up to the merge
  two        "Application Access Grant (generated)" on Grafana, up to the merge,
             then the same grant withdrawn on its branch (act three's UI path)
  monitoring act two's step 6: a monitoring profile edit, up to the merge
  five       the MCP server, as mcp-agent: reads, a branch, a proposed change,
             and the refusal on main

  merge      ONLY WITH --merge, AND IT CHANGES THE LAB. Acts two and three for
             real: a Grafana grant merged, the reconciler pushing fw1 and the
             border leaf, Vidra delivering the pod policy, alice signing in to
             Grafana from the branch desktop; then the portal's Revoke template,
             merged too; then the lab compared with a snapshot taken first and
             `make -C lab verify` run. About twenty minutes.

    uv run python scripts/demo_rehearsal.py --merge          # preflight, then the merge cycle
    uv run python scripts/demo_rehearsal.py --resume-revoke grafana-<ref>  # finish one that stopped

Exit status is non-zero when any check fails. WARN is reserved for a claim that
held only after help, so a rehearsal that needed a retry says so.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess  # noqa: S404 - docker and the repo's own scripts, fixed argv
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

REPO = Path(__file__).resolve().parents[1]
ADDRESS = os.environ.get("INFRAHUB_ADDRESS", "http://localhost:8000")
TOKEN = os.environ.get("INFRAHUB_API_TOKEN", "06438eb2-8019-4776-878c-0941b1f1d1ec")
HEADERS = {"X-INFRAHUB-KEY": TOKEN}
MCP_URL = os.environ.get("INFRAHUB_MCP_URL", "http://127.0.0.1:8001/mcp")
DESK = "clab-otternet-branch-desktop"
RECONCILER = "infrahub-deployment-reconciler-1"
BRANCH_LAN = "10.70.0.0/24"
EOS = "AVD EOS Configuration"
JUNOS = "Junos Configuration"

RESULTS: list[tuple[str, str, str]] = []
TIMINGS: list[tuple[str, float]] = []
CREATED_BRANCHES: list[str] = []
# Branches whose proposed change --merge merged, until the cycle has put the lab back.
MERGED: list[str] = []


# ----------------------------------------------------------------- reporting


def record(level: str, what: str, detail: str = "") -> None:
    colour = {"PASS": "32", "FAIL": "31", "WARN": "33"}[level]
    print(f"  \033[{colour}m{level}\033[0m  {what}" + (f"  ({detail})" if detail else ""), flush=True)
    RESULTS.append((level, what, detail))


def check(ok: bool, what: str, detail: str = "") -> bool:
    record("PASS" if ok else "FAIL", what, detail)
    return ok


@contextmanager
def timed(label: str) -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
    finally:
        TIMINGS.append((label, time.monotonic() - start))


def stage(name: str) -> None:
    print(f"\n\033[1;36m==> {name}\033[0m", flush=True)


# ------------------------------------------------------------------ Infrahub


def gql(query: str, variables: dict[str, Any] | None = None, branch: str = "main") -> dict[str, Any]:
    response = httpx.post(
        f"{ADDRESS}/graphql/{branch}",
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
        timeout=120,
    )
    payload = response.json()
    if payload.get("errors"):
        msg = json.dumps(payload["errors"])[:400]
        raise RuntimeError(msg)
    return payload["data"]


def wait_until(predicate: Callable[[], Any], timeout: float, interval: float = 5) -> Any:
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value or time.monotonic() > deadline:
            return value
        time.sleep(interval)


def proposed_change(branch: str) -> dict[str, Any] | None:
    edges = gql(
        """query ($b: String!) { CoreProposedChange(source_branch__value: $b) { edges { node {
             id state { value }
             validations { edges { node { display_label state { value } conclusion { value }
               checks { edges { node { conclusion { value } message { value } } } } } } } } } } }""",
        {"b": branch},
    )["CoreProposedChange"]["edges"]
    return edges[0]["node"] if edges else None


def settled_validators(branch: str, timeout: float = 600) -> list[dict[str, Any]]:
    """The proposed change's validators once every one is complete and the set has stopped moving."""
    previous: str = ""
    stable = 0
    deadline = time.monotonic() + timeout
    validators: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        pc = proposed_change(branch)
        validators = [edge["node"] for edge in pc["validations"]["edges"]] if pc else []
        snapshot = json.dumps(sorted((v["display_label"], v["state"]["value"]) for v in validators))
        pending = [v for v in validators if v["state"]["value"] != "completed"]
        # The integrity validators complete before the rest are even created, so
        # "all complete" means nothing until a user-defined check is among them:
        # the global ones have no targets and run on every proposed change.
        started = any(v["display_label"].startswith("Check:") for v in validators)
        stable = stable + 1 if (snapshot == previous and not pending and started) else 0
        if stable >= 3:
            break
        previous = snapshot
        time.sleep(10)
    return validators


def check_all_green(validators: list[dict[str, Any]], what: str) -> bool:
    red = sorted({v["display_label"] for v in validators if v["conclusion"]["value"] != "success"})
    return check(not red and bool(validators), what, ", ".join(red) or f"{len(validators)} validators")


def artifacts(branch: str) -> dict[tuple[str, str], dict[str, Any]]:
    edges = gql(
        """{ CoreArtifact { edges { node {
             name { value } checksum { value } storage_id { value } object { node { display_label } } } } } }""",
        branch=branch,
    )["CoreArtifact"]["edges"]
    return {(e["node"]["name"]["value"], e["node"]["object"]["node"]["display_label"]): e["node"] for e in edges}


def changed_artifacts(branch: str) -> dict[tuple[str, str], tuple[list[str], list[str]]]:
    """Every artifact whose checksum differs from main's, as (lines removed, lines added)."""
    main, ours = artifacts("main"), artifacts(branch)
    changed: dict[tuple[str, str], tuple[list[str], list[str]]] = {}
    for key, node in ours.items():
        before = main.get(key)
        if before and before["checksum"]["value"] == node["checksum"]["value"]:
            continue
        new = storage(node["storage_id"]["value"])
        old = storage(before["storage_id"]["value"]) if before else []
        changed[key] = (sorted(set(old) - set(new)), sorted(set(new) - set(old)))
    return changed


def storage(storage_id: str | None) -> list[str]:
    if not storage_id:
        return []
    response = httpx.get(f"{ADDRESS}/api/storage/object/{storage_id}", headers=HEADERS, timeout=60)
    return response.text.splitlines()


def changed_eos(branch: str) -> dict[str, tuple[list[str], list[str]]]:
    return {target: diff for (name, target), diff in changed_artifacts(branch).items() if name == EOS}


def rerun_artifact_checks(branch: str) -> None:
    pc = proposed_change(branch)
    if pc:
        gql(
            "mutation ($id: String!) { CoreProposedChangeRunCheck(data: {id: $id, check_type: ARTIFACT}) { ok } }",
            {"id": pc["id"]},
        )


def cleanup(branches: list[str]) -> None:
    for branch in branches:
        for edge in gql(
            "query ($b: String!) { CoreProposedChange(source_branch__value: $b) { edges { node { id state { value } } } } }",
            {"b": branch},
        )["CoreProposedChange"]["edges"]:
            pc = edge["node"]
            if pc["state"]["value"] == "open":
                gql(
                    'mutation ($id: String!) { CoreProposedChangeUpdate(data: {id: $id, state: {value: "closed"}}) { ok } }',
                    {"id": pc["id"]},
                )
            gql("mutation ($id: String!) { CoreProposedChangeDelete(data: {id: $id}) { ok } }", {"id": pc["id"]})
        if gql("query ($b: String!) { Branch(name: $b) { name } }", {"b": branch})["Branch"]:
            gql("mutation ($b: String!) { BranchDelete(data: {name: $b}) { ok } }", {"b": branch})
        print(f"  cleaned up {branch}", flush=True)


# ----------------------------------------------------------- the desktop side


def run(*command: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603


def desk(*command: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    return run("docker", "exec", DESK, *command, timeout=timeout)


def run_template(ref: str, values: dict[str, Any]) -> dict[str, Any]:
    """Submit a portal template as alice, from the branch desktop, and wait for it."""
    for name in ("portal_signin.sh", "run_template.py"):
        run("docker", "cp", str(REPO / "scripts" / "portal" / name), f"{DESK}:/tmp/{name}")
    desk("chmod", "+x", "/tmp/portal_signin.sh")  # noqa: S108 - inside the desktop container
    result = desk(
        "sh",
        "-c",
        'T=$(/tmp/portal_signin.sh); [ -n "$T" ] || { echo "sign-in failed"; exit 1; }; '
        'python3 /tmp/run_template.py "$T" "$1" "$2"',
        "_",
        ref,
        json.dumps(values),
        timeout=960,
    )
    print("\n".join("    " + line for line in result.stdout.splitlines() if not line.startswith("RESULT")))
    line = next((line for line in result.stdout.splitlines() if line.startswith("RESULT ")), "")
    return (
        json.loads(line[7:])
        if line
        else {"status": "no result", "errors": [result.stdout[-400:] + result.stderr[-400:]]}
    )


# ------------------------------------------------------------------- the acts


def act_preflight() -> None:
    stage("Preflight: the read-only checks")
    env = run("docker", "exec", RECONCILER, "env").stdout
    check("OTTERNET_RECONCILE_INTERVAL=120" in env, "the reconciler runs at demo cadence (120 s)")
    check("OTTERNET_RECONCILE_FIREWALL_EVERY=1" in env, "the reconciler compares the firewall every cycle")
    logs = run("docker", "logs", "--tail", "20", RECONCILER)
    cycles = [line for line in (logs.stdout + logs.stderr).splitlines() if " cycle " in line]
    last = cycles[-1] if cycles else ""
    check("differed=0" in last and "failed=0" in last, "the last reconcile cycle found nothing to do", last[-90:])

    repo = gql("{ CoreRepository { edges { node { sync_status { value } } } } }")["CoreRepository"]["edges"]
    check(all(e["node"]["sync_status"]["value"] == "in-sync" for e in repo), "the repository is in sync")
    others = sorted(
        b["name"] for b in gql("{ Branch { name status } }")["Branch"] if b["name"] != "main" and b["status"] == "OPEN"
    )
    if others:
        record("WARN", "open branches besides main are on the branch selector", ", ".join(others))

    accounts = run("uv", "run", "python", str(REPO / "scripts" / "provision_portal_accounts.py"), "--check")
    check(accounts.returncode == 0, "every portal user has an Infrahub account")
    # A generator instance whose target was deleted fails that generator's
    # validator on EVERY proposed change, unrelated ones included, so a red
    # check in act one or two would be this and not the request.
    instances = gql("{ CoreGeneratorInstance { edges { node { name { value } object { node { id } } } } } }")[
        "CoreGeneratorInstance"
    ]["edges"]
    dangling = sorted(e["node"]["name"]["value"] for e in instances if not e["node"]["object"]["node"])
    check(not dangling, "no generator instance points at a deleted node", ", ".join(dangling))
    check(
        httpx.get(MCP_URL.replace("/mcp", "/health"), timeout=10).json().get("status") == "healthy",
        "the MCP server is healthy",
    )

    for vip, what in (("10.112.240.81", "Grafana"), ("10.112.240.0", "otternet-demo")):
        code = desk("curl", "-s", "-m", "8", "-o", "/dev/null", "-w", "%{http_code}", f"http://{vip}/").stdout
        check(code == "000", f"the branch cannot reach {what} yet", f"HTTP {code}")
    rules = desk_firewall("show configuration security policies from-zone branch to-zone k8s-prod | display set")
    check(
        "svc-" not in rules and "branch-to-access-portal" in rules,
        "branch -> k8s-prod carries only the hand-written rules",
    )


def desk_firewall(command: str) -> str:
    return run(
        "docker", "exec", "-i", "clab-otternet-fw1", "sshpass", "-p", "admin@123", "ssh",
        "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
        "admin@127.0.0.1", command,
    ).stdout  # fmt: skip


def act_four() -> None:
    stage("Act four: a check catching a broken service")
    branch = os.environ.get("OTTERNET_DEMO_BREAK_BRANCH", "demo-broken-isolation")
    CREATED_BRANCHES.append(branch)
    with timed("act four: break it, until the check is red"):
        result = run(str(REPO / "scripts" / "demo_break_isolation.sh"), timeout=600)
    print("\n".join("    " + line for line in result.stdout.splitlines()[-6:]))
    check(result.returncode == 0, "demo_break_isolation.sh ran", result.stderr[-200:])
    validators = settled_validators(branch)
    red = {v["display_label"] for v in validators if v["conclusion"]["value"] != "success"}
    check(red == {"Check: wan-service-consistency"}, "only wan-service-consistency is red", ", ".join(sorted(red)))
    messages = " ".join(
        c["node"]["message"]["value"] or ""
        for v in validators
        if v["display_label"] == "Check: wan-service-consistency"
        for c in v["checks"]["edges"]
    )
    check("'acme'" in messages and "'globex'" in messages, "the failure names both tenants")
    with timed("act four: --revert"):
        run(str(REPO / "scripts" / "demo_break_isolation.sh"), "--revert")
    gone = not gql("query ($b: String!) { Branch(name: $b) { name } }", {"b": branch})["Branch"]
    check(gone and proposed_change(branch) is None, "--revert removed the branch and the proposed change")


def act_one(reference: str) -> None:
    stage("Act one: ask for an application (up to the merge)")
    app = "otter-shop"
    branch = f"implement_{app}_{reference}"
    CREATED_BRANCHES.append(branch)
    values = {
        "app_name": app,
        "description": "A rehearsal of the demo; never merged",
        "namespace_name": app,
        "cluster": "otternet",
        "vrf": "K8S_PROD",
        "owner": "acme",
        "chart_repository": "https://cowboysysop.github.io/charts/",
        "chart_name": "whoami",
        "chart_version": "6.0.0",
        "advertised_services": ["junos-http"],
        "service_selector": ["otternet.lab/advertise=true"],
        "vip_block_size": 28,
        "values_file_content": (
            "replicaCount: 1\n\nservice:\n  type: LoadBalancer\n  externalTrafficPolicy: Local\n"
            '  ports:\n    http: 80\n\ncommonLabels:\n  otternet.lab/advertise: "true"\n'
        ),
        "source_site": "branch-office",
        "justification": "demo rehearsal",
        "request_reference": reference,
    }
    with timed("act one: portal request, start to proposed change"):
        result = run_template("template:default/exposed-app-with-access-request", values)
    if not check(
        result["status"] == "completed",
        "the curated template completed as alice",
        "; ".join(result.get("errors", []))[:300],
    ):
        return
    steps = result["steps"]
    TIMINGS.append(
        (
            "act one: of that, the AVD pass",
            steps["run_avd_hostvars"]["seconds"] + steps["run_avd_structured_config"]["seconds"],
        )
    )

    grant = gql(
        "{ ServiceAppAccess { edges { node { name { value } status { value } requester { value } } } } }", branch=branch
    )["ServiceAppAccess"]["edges"]
    mine = [g["node"] for g in grant if g["node"]["name"]["value"] == f"{app}-access"]
    check(bool(mine) and mine[0]["status"]["value"] == "active", "the grant is active on the branch")
    check(bool(mine) and mine[0]["requester"]["value"] == "alice@otternet.lab", "alice is the grant's requester")
    vip = gql(
        "query ($n: String!) { ServiceFabricApp(name__value: $n) { edges { node { vip_block { node { display_label } } } } } }",
        {"n": app},
        branch=branch,
    )["ServiceFabricApp"]["edges"][0]["node"]["vip_block"]["node"]["display_label"].split()[0]

    with timed("act one: proposed change opened, until every validator is done"):
        validators = settled_validators(branch)
    check_all_green(validators, "every validator on the proposed change is green")

    changed = changed_artifacts(branch)
    names = {name for name, _ in changed}
    check(
        names >= {EOS, JUNOS, "Crossplane FabricApp"},
        "EOS, Junos and FabricApp artifacts re-rendered",
        ", ".join(sorted(names)),
    )
    eos = {target: diff for (name, target), diff in changed.items() if name == EOS}
    added = [line.strip() for diff in eos.values() for line in diff[1]]
    check(
        len(eos) == 1 and len(added) == 1 and re.fullmatch(rf"seq \d+ permit {re.escape(vip)}", added[0]) is not None,
        "exactly one switch gains exactly one line, the VIP block's permit",
        f"{', '.join(eos)}: {added}",
    )
    junos_added = " ".join(changed.get((JUNOS, "fw1"), ([], []))[1])
    check(f"policy svc-{app}-access" in junos_added and vip in junos_added, "fw1 gains the rule and the VIP's address")


def act_two(reference: str) -> None:
    stage("Act two: a branch user asks for Grafana (up to the merge), then withdraws it")
    name = f"grafana-{reference}"
    branch = f"implement_{name}"
    CREATED_BRANCHES.append(branch)
    values = {
        "mode": "create",
        "name": name,
        "application": "component:default/otternet-metrics",
        "owner": "branch",
        "source_site": "resource:default/branch-office",
        "justification": "demo rehearsal",
    }
    with timed("act two: portal grant, start to proposed change"):
        result = run_template("template:default/app-access-request", values)
    if not check(
        result["status"] == "completed",
        "the generated grant template completed as alice",
        "; ".join(result.get("errors", []))[:300],
    ):
        return
    with timed("act two: proposed change opened, until every validator is done"):
        validators = settled_validators(branch)
    check_all_green(validators, "every validator on the proposed change is green")

    changed = changed_artifacts(branch)
    junos_added = " ".join(changed.get((JUNOS, "fw1"), ([], []))[1])
    check(
        f"policy svc-{name}" in junos_added and "10.112.240.80/28" in junos_added,
        "fw1 gains the rule for Grafana's VIP block",
    )
    allowed = " ".join(changed.get(("Crossplane FabricApp", "otternet-metrics"), ([], []))[1])
    check(BRANCH_LAN in allowed, "Grafana's own pod policy gains the branch LAN")

    # THE FABRIC CONSEQUENCE, which a generated template does not run for itself.
    # It arrives through the pipeline's hostvar pass, and the EOS artifact used to
    # be validated before that pass had written anything.
    start = time.monotonic()
    eos = wait_until(lambda: changed_eos(branch), timeout=120, interval=10)
    if eos:
        TIMINGS.append(("act two: validators done, until the border leaf's diff", time.monotonic() - start))
    else:
        rerun_artifact_checks(branch)
        eos = wait_until(lambda: changed_eos(branch), timeout=120, interval=5)
        if eos:
            record("WARN", "the border leaf's diff appeared only after re-running the artifact checks")
    added = [line.strip() for diff in (eos or {}).values() for line in diff[1]]
    check(len(added) == 1 and "10.112.240.80/28" in added[0], "the border leaf gains Grafana's block", str(added))

    # Act three's UI path, on this branch: status is how a grant is withdrawn.
    before = artifacts("main")
    with timed("act three (UI path): decommissioning, until fw1 is back to main"):
        gql(
            """mutation ($n: String!) { ServiceAppAccessUpdate(context: {account: {id: "alice"}},
                 data: {hfid: [$n], status: {value: "decommissioning"}}) { ok } }""",
            {"n": name},
            branch=branch,
        )
        restored = wait_until(
            lambda: artifacts(branch)[JUNOS, "fw1"]["checksum"]["value"] == before[JUNOS, "fw1"]["checksum"]["value"],
            timeout=180,
        )
    check(bool(restored), "withdrawing the grant returns fw1's configuration to main's, byte for byte")
    app = gql(
        """{ ServiceFabricApp(name__value: "otternet-metrics") { edges { node {
             allowed_source_prefixes { edges { node { display_label } } } } } } }""",
        branch=branch,
    )["ServiceFabricApp"]["edges"][0]["node"]
    sources = " ".join(e["node"]["display_label"] for e in app["allowed_source_prefixes"]["edges"])
    check(BRANCH_LAN not in sources, "and the branch LAN leaves Grafana's pod policy")


def act_monitoring() -> None:
    stage("Act two, step 6: monitoring is intent (up to the merge)")
    branch = f"rehearsal-monitoring-{secrets.token_hex(2)}"
    CREATED_BRANCHES.append(branch)
    gql("mutation ($b: String!) { BranchCreate(data: {name: $b, sync_with_git: false}) { ok } }", {"b": branch})
    ids = gql(
        """{ MonitoringProfile(name__value: "fabric-core") { edges { node { id } } }
             MonitoringMeasurement(name__value: "bgp-neighbor-state") { edges { node { id } } } }""",
        branch=branch,
    )
    gql(
        """mutation ($p: String!, $m: String!) {
             RelationshipRemove(data: {id: $p, name: "measurements", nodes: [{id: $m}]}) { ok } }""",
        {
            "p": ids["MonitoringProfile"]["edges"][0]["node"]["id"],
            "m": ids["MonitoringMeasurement"]["edges"][0]["node"]["id"],
        },
        branch=branch,
    )
    gql(
        """mutation ($b: String!) { CoreProposedChangeCreate(data: {name: {value: "rehearsal: stop watching fabric BGP"},
             source_branch: {value: $b}, destination_branch: {value: "main"}}) { ok } }""",
        {"b": branch},
    )
    with timed("monitoring: proposed change opened, until every validator is done"):
        validators = settled_validators(branch)
    check_all_green(validators, "every validator on the proposed change is green")
    changed = changed_artifacts(branch)
    check(
        {name for name, _ in changed} == {"Telemetry Collector Configuration"},
        "only the collector's configuration changes",
        ", ".join(sorted(name for name, _ in changed)),
    )
    removed = " ".join(line for diff in changed.values() for line in diff[0])
    added = " ".join(line for diff in changed.values() for line in diff[1])
    check("bgp_neighbor" in removed and "bgp_neighbor" not in added, "it loses the BGP subscriptions")


class Mcp:
    """The smallest streamable-HTTP MCP client that will do: JSON-RPC, one session."""

    def __init__(self, url: str) -> None:
        self.url, self.session, self.next_id = url, "", 0
        self.http = httpx.Client(timeout=120)
        init = self.request("initialize", {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "demo-rehearsal", "version": "1"},
        })  # fmt: skip
        self.server = init.get("serverInfo", {})
        self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def post(self, body: dict[str, Any]) -> httpx.Response:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        response = self.http.post(self.url, json=body, headers=headers)
        self.session = response.headers.get("mcp-session-id", self.session)
        return response

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.next_id += 1
        response = self.post({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})
        if "text/event-stream" in response.headers.get("content-type", ""):
            # A stream can carry log notifications before the reply, so the
            # reply is the message bearing this request's id, not the first one.
            messages = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]
        else:
            messages = [response.json()]
        reply = next((m for m in messages if m.get("id") == self.next_id), {})
        if "result" not in reply:
            raise RuntimeError(reply.get("error") or messages)
        return reply["result"]

    def tool(self, name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        try:
            result = self.request("tools/call", {"name": name, "arguments": arguments})
        except RuntimeError as exc:  # a refusal may come back as a JSON-RPC error instead
            return False, str(exc)
        body = "\n".join(part.get("text", "") for part in result.get("content", []))
        return not result.get("isError"), body


def main_env(name: str) -> str:
    """A value from the main checkout's `.env`, which is the one compose reads -- also from a worktree."""
    common = run("git", "-C", str(REPO), "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    env = Path(common).parent / ".env" if common else REPO / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.exists() else []:
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    return ""


def act_five() -> None:
    stage("Act five: the agent, through the MCP server")
    with timed("act five: the MCP session"):
        mcp = Mcp(MCP_URL)
        tools = {tool["name"] for tool in mcp.request("tools/list", {})["tools"]}
        check(
            {"query_graphql", "find_reachable", "node_upsert", "propose_changes", "reset_session_branch"} <= tools,
            "the server offers its read, write and proposed-change tools",
            f"{len(tools)} tools, {mcp.server.get('name')} {mcp.server.get('version')}",
        )
        ok, body = mcp.tool("find_reachable", {
            "source": "ServiceFabricApp__otternet-demo", "target_kinds": ["ClusterKubernetes", "IpamPrefix"],
        })  # fmt: skip
        check(
            ok and "ClusterKubernetes" in body and "10.112.240.0/28" in body,
            "otternet-demo reaches its cluster and its VIP block",
        )
        ok, body = mcp.tool("find_reachable", {"source": "IpamVRF__K8S_PROD", "target_kinds": ["DcimFabricSwitch"]})
        switches = sorted(set(re.findall(r"display_label: ((?:leaf|spine)-otternet[\w-]+)", body)))
        check(ok and bool(switches), "K8S_PROD reaches the switches it is on", ", ".join(switches))

        ok, body = mcp.tool("reset_session_branch", {"branch": "main"})
        check(not ok and "not allowed" in body, "the MCP server refuses to make main its session branch")
        ok, body = mcp.tool("node_upsert", {
            "kind": "ServiceFabricApp", "hfid": ["otternet-demo"], "data": {"description": "rehearsal: an agent's edit"},
        })  # fmt: skip
        session = json.loads(body).get("branch", "") if ok else ""
        if session:
            CREATED_BRANCHES.append(session)
        check(session.startswith("mcp/session-"), "a write lands on a session branch", session)
        ok, body = mcp.tool("propose_changes", {"title": "rehearsal: an agent's edit", "description": "Never merged."})
        check(ok and session in body, "the agent opens a proposed change from it")

    # Infrahub's own refusal, not the MCP server's: mcp-agent straight at /graphql/main.
    password = main_env("INFRAHUB_MCP_PASSWORD")
    login = httpx.post(f"{ADDRESS}/api/auth/login", json={"username": "mcp-agent", "password": password}, timeout=30)
    if not check(login.status_code == 200, "mcp-agent signs in"):
        return
    demo = gql('{ ServiceFabricApp(name__value: "otternet-demo") { edges { node { id } } } }')
    refused = httpx.post(
        f"{ADDRESS}/graphql/main",
        json={
            "query": 'mutation ($id: String!) { ServiceFabricAppUpdate(data: {id: $id, description: {value: "x"}}) { ok } }',
            "variables": {"id": demo["ServiceFabricApp"]["edges"][0]["node"]["id"]},
        },
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        timeout=30,
    )
    check("PERMISSION_DENIED" in refused.text, "Infrahub refuses mcp-agent's write to main", refused.text[:120])


# ------------------------------------------------- --merge: THIS CHANGES THE LAB
#
# Everything above stops at a merge. This half merges, lets the reconciler push
# fw1 and the border leaf, watches Vidra deliver, signs alice in to Grafana from
# the branch desktop, revokes through the portal's Revoke template, merges that,
# and then proves the lab is back where it started. The Revoke template can only
# be rehearsed this way: its picker lists grants on main.

LEAF = "leaf-otternet-pod1-3-1"
LEAF_CONTAINER = "clab-otternet-border-leaf1"
GRAFANA = "otternet-metrics"
GRAFANA_VIP = "10.112.240.81"
GRAFANA_BLOCK = "10.112.240.80/28"
FABRIC_APP = "Crossplane FabricApp"
SNAPSHOT_FILE = Path(os.environ.get("OTTERNET_REHEARSAL_SNAPSHOT", "/tmp/otternet-demo-rehearsal-snapshot.json"))  # noqa: S108
# Junos re-salts every `## SECRET-DATA` value on a load, so these lines may move
# while the configuration means exactly the same thing. They are compared apart.
SECRET = re.compile(r"## SECRET-DATA|encrypted-password|\$9\$|\$6\$")


def main_checkout() -> Path:
    common = run("git", "-C", str(REPO), "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    return Path(common).parent if common else REPO


def git_branches() -> set[str]:
    refs = run("git", "-C", str(main_checkout()), "for-each-ref", "--format=%(refname:short)", "refs/heads")
    return set(refs.stdout.split())


def kubectl(*args: str) -> subprocess.CompletedProcess[str]:
    config = os.environ.get("KUBECONFIG") or str(main_checkout() / "lab" / "k8s" / ".kubeconfig" / "kubeconfig.yaml")
    return run("kubectl", "--kubeconfig", config, *args, timeout=60)


def fw_config() -> str:
    return desk_firewall("show configuration | display set")


def leaf_config() -> str:
    return run("docker", "exec", LEAF_CONTAINER, "Cli", "-p", "15", "-c", "show running-config").stdout


def grafana_gate() -> dict[str, Any]:
    """Grafana's pod-level gate: the FabricApp's allowFrom and the policy Cilium enforces."""
    app = kubectl("get", "fabricapp", GRAFANA, "-o", "json")
    cnp = kubectl("-n", GRAFANA, "get", "ciliumnetworkpolicy", "allow-ingress", "-o", "json")
    allow_from = json.loads(app.stdout)["spec"]["policy"]["allowFrom"] if app.returncode == 0 else None
    cidrs = (
        sorted(c for rule in json.loads(cnp.stdout)["spec"]["ingress"] for c in rule.get("fromCIDR", []))
        if cnp.returncode == 0
        else None
    )
    return {"allowFrom": allow_from, "fromCIDR": cidrs}


def desk_http(url: str) -> str:
    return desk("curl", "-s", "-m", "8", "-o", "/dev/null", "-w", "%{http_code}", url).stdout


def grant_bookkeeping() -> list[str]:
    """generate-app-access's own records on main: its generator instances and tracking groups.

    Deleting a grant deletes neither, and an instance left pointing at a deleted
    grant breaks the generator for EVERY later proposed change: Infrahub's
    `request_generator_definition_run` reads each instance's `object.peer.id` and
    raises `Node must have at least one identifier` on the dangling one, so the
    `generate-app-access` validator goes red on requests that have nothing to do
    with the deleted grant. Measured: the first rehearsal of this mode did exactly
    that, and the next grant's proposed change could not be merged.
    """
    return sorted(f"{kind} {label}" for kind, _, label in _grant_records())


def _grant_records() -> list[tuple[str, str, str]]:
    """(kind, id, label) for every generate-app-access instance and tracking group on main."""
    data = gql(
        """{ CoreGeneratorInstance { edges { node { id name { value } definition { node { name { value } } } } } }
             CoreGeneratorGroup { edges { node { id name { value } description { value } } } } }"""
    )
    records = [
        ("CoreGeneratorInstance", e["node"]["id"], e["node"]["name"]["value"])
        for e in data["CoreGeneratorInstance"]["edges"]
        if e["node"]["definition"]["node"]["name"]["value"] == "generate-app-access"
    ]
    records += [
        ("CoreGeneratorGroup", e["node"]["id"], f"{e['node']['name']['value']} ({e['node']['description']['value']})")
        for e in data["CoreGeneratorGroup"]["edges"]
        if e["node"]["name"]["value"].startswith("generate-app-access-")
    ]
    return records


def delete_grant(name: str) -> None:
    """Delete a grant from main, and generate-app-access's records of it with it."""
    for kind, node_id, label in _grant_records():
        if label in {f"generate-app-access: {name}", f"name: {name}"} or label.endswith(f"(name: {name})"):
            gql(f"mutation ($id: String!) {{ {kind}Delete(data: {{id: $id}}) {{ ok }} }}", {"id": node_id})
    grant = gql("query ($n: String!) { ServiceAppAccess(name__value: $n) { edges { node { id } } } }", {"n": name})[
        "ServiceAppAccess"
    ]["edges"]
    for edge in grant:
        gql("mutation ($id: String!) { ServiceAppAccessDelete(data: {id: $id}) { ok } }", {"id": edge["node"]["id"]})


def snapshot() -> dict[str, Any]:
    """Everything the merge cycle may touch and must put back."""
    states = gql(
        """{ DeploymentState { edges { node { name { value } status { value }
             last_artifact_checksum { value } suspend { value } last_error { value } } } } }"""
    )["DeploymentState"]["edges"]
    return {
        "fw1": fw_config(),
        "leaf": leaf_config(),
        "artifacts": {
            f"{name} / {target}": node["checksum"]["value"] for (name, target), node in artifacts("main").items()
        },
        "deployment": {
            s["node"]["name"]["value"]: {
                key: s["node"][key]["value"] for key in ("status", "last_artifact_checksum", "suspend", "last_error")
            }
            for s in states
        },
        "grants": sorted(
            e["node"]["name"]["value"]
            for e in gql("{ ServiceAppAccess { edges { node { name { value } } } } }")["ServiceAppAccess"]["edges"]
        ),
        "grant_bookkeeping": grant_bookkeeping(),
        "gate": grafana_gate(),
        # Not the mirrors: Infrahub copies every branch of the checkout it
        # clones, and other sessions' worktrees create them mid-run. A mirror
        # does not reliably say `sync_with_git`, so it is excluded by name.
        "branches": sorted(b["name"] for b in gql("{ Branch { name } }")["Branch"] if b["name"] not in git_branches()),
        "open_changes": sorted(
            e["node"]["name"]["value"]
            for e in gql('{ CoreProposedChange(state__value: "open") { edges { node { name { value } } } } }')[
                "CoreProposedChange"
            ]["edges"]
        ),
    }


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Record one PASS/FAIL per part of the lab; True when everything is back."""
    ok = True
    old_fw, new_fw = before["fw1"].splitlines(), after["fw1"].splitlines()
    if old_fw == new_fw:
        check(True, "fw1's running configuration is byte-for-byte the snapshot", f"{len(new_fw)} lines")
    else:
        plain = [line for line in old_fw if not SECRET.search(line)] == [
            line for line in new_fw if not SECRET.search(line)
        ]
        moved = sorted(set(old_fw) ^ set(new_fw))
        ok &= check(
            plain,
            "fw1's running configuration equals the snapshot, apart from re-salted secrets",
            f"{len(moved)} lines differ: {moved[:4]}",
        )
    old_leaf, new_leaf = before["leaf"].splitlines(), after["leaf"].splitlines()
    ok &= check(
        old_leaf == new_leaf,
        "the border leaf's running configuration is byte-for-byte the snapshot",
        f"{len(new_leaf)} lines" if old_leaf == new_leaf else str(sorted(set(old_leaf) ^ set(new_leaf))[:6]),
    )
    moved_artifacts = sorted(
        key for key in before["artifacts"].keys() | after["artifacts"].keys()
        if before["artifacts"].get(key) != after["artifacts"].get(key)
    )  # fmt: skip
    ok &= check(
        not moved_artifacts,
        "every artifact on main has the snapshot's checksum",
        ", ".join(moved_artifacts) or f"{len(after['artifacts'])} artifacts",
    )
    moved_states = sorted(
        name for name in before["deployment"].keys() | after["deployment"].keys()
        if before["deployment"].get(name) != after["deployment"].get(name)
    )  # fmt: skip
    ok &= check(
        not moved_states,
        "every DeploymentState matches the snapshot (status, artifact checksum, suspend, error)",
        ", ".join(f"{n}: {before['deployment'].get(n)} -> {after['deployment'].get(n)}" for n in moved_states)[:400]
        or f"{len(after['deployment'])} devices",
    )
    for key, what in (
        ("grants", "the ServiceAppAccess objects on main are the snapshot's"),
        ("grant_bookkeeping", "generate-app-access keeps no instance or tracking group for the grant"),
        ("gate", "Grafana's pod policy is the snapshot's"),
        ("branches", "the Infrahub branches are the snapshot's"),
        ("open_changes", "the open proposed changes are the snapshot's"),
    ):
        ok &= check(
            before[key] == after[key], what, f"{before[key]} -> {after[key]}" if before[key] != after[key] else ""
        )
    return ok


def merge_change(branch: str) -> float:
    """Merge the branch's proposed change; the wall-clock time the merge returned."""
    pc = proposed_change(branch)
    if not pc:
        msg = f"no proposed change for {branch}"
        raise RuntimeError(msg)
    start = time.monotonic()
    result = gql(
        "mutation ($id: String!) { CoreProposedChangeMerge(data: {id: $id}, wait_until_completion: true) { ok } }",
        {"id": pc["id"]},
    )
    TIMINGS.append((f"merge {branch}: CoreProposedChangeMerge", time.monotonic() - start))
    if not result["CoreProposedChangeMerge"]["ok"]:
        msg = f"merging {branch} returned ok=false"
        raise RuntimeError(msg)
    # Merged: the proposed change stays as history, so the cleanup must not delete it.
    CREATED_BRANCHES.remove(branch)
    MERGED.append(branch)
    return time.time()


def reconciler_cycles(since: float) -> list[str]:
    logs = run("docker", "logs", "--since", str(int(since)), RECONCILER)
    return [line for line in (logs.stdout + logs.stderr).splitlines() if re.search(r" cycle \d+: compared=", line)]


def pushed_and_confirmed(since: float) -> bool:
    """A cycle since `since` that pushed, followed by one that found nothing to do."""
    cycles = reconciler_cycles(since)
    first_push = next((i for i, line in enumerate(cycles) if not re.search(r"pushed=0\b", line)), None)
    return first_push is not None and any("differed=0" in line for line in cycles[first_push + 1 :])


def watch(prefix: str, since: float, conditions: dict[str, Callable[[], bool]], timeout: float) -> dict[str, float]:
    """Poll every condition until all hold; the seconds from `since` at which each first held."""
    pending, seen = dict(conditions), {}
    while pending and time.time() - since < timeout:
        for label, condition in list(pending.items()):
            try:
                held = bool(condition())
            except Exception:  # noqa: BLE001 - a probe that fails has simply not held yet
                held = False
            if held:
                seen[label] = time.time() - since
                pending.pop(label)
                print(f"    +{seen[label]:6.1f} s  {label}", flush=True)
        if pending:
            time.sleep(5)
    for label in conditions:
        if label in seen:
            TIMINGS.append((f"{prefix}: merge until {label}", seen[label]))
        check(label in seen, f"{prefix}: {label}", "" if label in seen else f"not within {timeout:.0f} s")
    return seen


def catalog_has(entity: str) -> bool:
    """Whether the portal's catalogue lists the entity yet, asked as alice from the desktop."""
    result = desk(
        "sh",
        "-c",
        'T=$(/tmp/portal_signin.sh); curl -sk -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $T" '
        '"https://10.90.0.11:32001/api/catalog/entities/by-name/component/default/$1"',
        "_",
        entity,
    )
    return result.stdout.strip() == "200"


def leaf_permits(block: str) -> bool:
    out = run("docker", "exec", LEAF_CONTAINER, "Cli", "-c", "show ip prefix-list PL-DC-ADVERTISED-BRANCH").stdout
    return f"permit {block}" in out


def fw_rule(name: str) -> bool:
    return f"svc-{name}" in desk_firewall(
        "show configuration security policies from-zone branch to-zone k8s-prod | display set"
    )


def grafana_signin() -> str:
    run("docker", "cp", str(REPO / "scripts" / "portal" / "grafana_signin.sh"), f"{DESK}:/tmp/grafana_signin.sh")
    return desk("sh", "/tmp/grafana_signin.sh", timeout=90).stdout.strip()  # noqa: S108 - inside the container


def act_merge(reference: str, via: str = "template") -> None:
    stage("Merge cycle: THIS CHANGES THE LAB -- grant Grafana, merge, revoke, merge, restore")
    before = snapshot()
    # On disk, so `--resume-revoke` can finish a cycle that stopped after the
    # grant merged and still prove the lab came back to THIS state.
    SNAPSHOT_FILE.write_text(json.dumps(before), encoding="utf-8")
    print(f"    snapshot: fw1 {len(before['fw1'].splitlines())} lines, border leaf "
          f"{len(before['leaf'].splitlines())} lines, {len(before['artifacts'])} artifacts, "
          f"{len(before['deployment'])} devices, grants on main {before['grants']}")  # fmt: skip
    if not check(not before["grants"], "no grant exists on main before the cycle", ", ".join(before["grants"])):
        return
    if not check(
        not before["grant_bookkeeping"],
        "generate-app-access keeps no records on main",
        ", ".join(before["grant_bookkeeping"]),
    ):
        return
    if not check(
        all(s["status"] == "in_sync" for s in before["deployment"].values()), "every device is in_sync to start"
    ):
        return
    if not check(desk_http(f"http://{GRAFANA_VIP}/api/health") == "000", "the branch cannot reach Grafana to start"):
        return

    name = f"grafana-{reference}"
    grant_branch = f"implement_{name}"
    CREATED_BRANCHES.append(grant_branch)
    with timed("merge cycle: act two, portal grant, start to proposed change"):
        result = run_template(
            "template:default/app-access-request",
            {
                "mode": "create",
                "name": name,
                "application": f"component:default/{GRAFANA}",
                "owner": "branch",
                "source_site": "resource:default/branch-office",
                "justification": "demo rehearsal, merged and then revoked",
            },
        )
    if not check(result["status"] == "completed", "act two: the grant template completed as alice"):
        return
    with timed("merge cycle: act two, proposed change opened, until every validator is done"):
        green = check_all_green(settled_validators(grant_branch), "act two: every validator is green")
    if not green:  # Infrahub refuses the merge anyway; stopping here leaves the lab untouched
        return
    # The border leaf's diff arrives through the pipeline's hostvar pass, last.
    # Merging before it lands would carry the attribute and not the rendered line.
    eos = wait_until(lambda: changed_eos(grant_branch), timeout=180, interval=10)
    if not eos:
        rerun_artifact_checks(grant_branch)
        eos = wait_until(lambda: changed_eos(grant_branch), timeout=120, interval=5)
    if not check(list(eos or {}) == [LEAF], "act two: the border leaf's diff is on the proposed change", str(eos)):
        return

    merged = merge_change(grant_branch)
    print(f"    merged {grant_branch}", flush=True)
    watch(
        "act two",
        merged,
        {
            "Vidra delivers Grafana's pod policy with the branch LAN": lambda: (
                BRANCH_LAN in (grafana_gate()["fromCIDR"] or [])
            ),
            "fw1 carries the rule": lambda: fw_rule(name),
            f"the border leaf permits {GRAFANA_BLOCK}": lambda: leaf_permits(GRAFANA_BLOCK),
            "Grafana answers the branch desktop with HTTP 200": lambda: (
                desk_http(f"http://{GRAFANA_VIP}/api/health") == "200"
            ),
            "the reconciler has pushed and then confirmed": lambda: pushed_and_confirmed(merged),
        },
        timeout=600,
    )
    role = grafana_signin()
    check(role == "Viewer", "act two: alice signs in to Grafana through Dex from the branch desktop", role)
    after_grant = artifacts("main")
    check(
        after_grant[JUNOS, "fw1"]["checksum"]["value"] != before["artifacts"][f"{JUNOS} / fw1"],
        "act two: fw1's artifact on main moved",
    )

    act_revoke(name, reference, before, via)


def revoke_via_status(name: str, branch: str, before: dict[str, Any]) -> bool:
    """The Revoke template's steps, without its `infrahub:generators:await` step.

    Act three's UI path: set `status` on a branch and let the event rule's ONE
    generator run withdraw the grant. The template's await step runs the
    generator a second time, and until `_delete_if_present` is deployed the two
    race and the template fails (see generators/generate_app_access.py). This is
    the recovery that does not depend on which generator Infrahub is running.
    """
    gql("mutation ($b: String!) { BranchCreate(data: {name: $b, sync_with_git: false}) { ok } }", {"b": branch})
    gql(
        """mutation ($n: String!) { ServiceAppAccessUpdate(context: {account: {id: "alice"}},
             data: {hfid: [$n], status: {value: "decommissioning"}}) { ok } }""",
        {"n": name},
        branch=branch,
    )
    withdrawn = wait_until(
        lambda: (
            artifacts(branch)[JUNOS, "fw1"]["checksum"]["value"] == before["artifacts"][f"{JUNOS} / fw1"]
            and gql(
                "query ($n: String!) { ServiceAppAccess(name__value: $n) { edges { node { status { value } } } } }",
                {"n": name},
                branch=branch,
            )["ServiceAppAccess"]["edges"][0]["node"]["status"]["value"]
            == "decommissioned"
        ),
        timeout=300,
        interval=10,
    )
    if not check(bool(withdrawn), "act three (status path): the generator withdrew the grant on its branch"):
        return False
    for definition in ("generate-avd-device-hostvar", "generate-avd-device-structured-config"):
        generator_id = gql(
            "query ($n: String!) { CoreGeneratorDefinition(name__value: $n) { edges { node { id } } } }",
            {"n": definition},
            branch=branch,
        )["CoreGeneratorDefinition"]["edges"][0]["node"]["id"]
        gql(
            """mutation ($id: String!) {
                 CoreGeneratorDefinitionRun(data: {id: $id}, wait_until_completion: true) { ok } }""",
            {"id": generator_id},
            branch=branch,
        )
    gql(
        """mutation ($n: String!, $b: String!) { CoreProposedChangeCreate(data: {name: {value: $n},
             source_branch: {value: $b}, destination_branch: {value: "main"}}) { ok } }""",
        {"n": f"Revoke {name}", "b": branch},
    )
    return True


def act_revoke(name: str, reference: str, before: dict[str, Any], via: str = "template") -> None:
    """Act three, then the restore -- for a grant merged on main."""
    grant_branch = f"implement_{name}"
    revoke_branch = f"revoke_{name}_{reference}"
    CREATED_BRANCHES.append(revoke_branch)
    if via == "status":
        with timed("merge cycle: act three, status set on a branch, to proposed change"):
            if not revoke_via_status(name, revoke_branch, before):
                return
    else:
        wait_until(lambda: catalog_has(name), timeout=180, interval=10)
        if not check(catalog_has(name), "act three: the Revoke picker can see the merged grant"):
            return
        with timed("merge cycle: act three, Revoke template, start to proposed change"):
            result = run_template(
                "template:default/revoke-access-request",
                {"grant": f"component:default/{name}", "reason": "demo rehearsal", "request_reference": reference},
            )
        if not check(result["status"] == "completed", "act three: the Revoke template completed as alice"):
            return
    with timed("merge cycle: act three, proposed change opened, until every validator is done"):
        green = check_all_green(settled_validators(revoke_branch), "act three: every validator is green")
    if not green:  # the grant stays merged: the finally block says how to recover
        return
    eos = changed_eos(revoke_branch)
    removed = [line.strip() for diff in eos.values() for line in diff[0]]
    check(
        list(eos) == [LEAF] and len(removed) == 1 and GRAFANA_BLOCK in removed[0],
        "act three: the border leaf loses exactly the grant's line",
        str(removed),
    )
    revoked_fw = artifacts(revoke_branch)[JUNOS, "fw1"]["checksum"]["value"]
    check(
        revoked_fw == before["artifacts"][f"{JUNOS} / fw1"],
        "act three: fw1's artifact on the branch is back to the snapshot's",
    )

    merged = merge_change(revoke_branch)
    print(f"    merged {revoke_branch}", flush=True)
    watch(
        "act three",
        merged,
        {
            "Vidra closes Grafana's pod policy": lambda: grafana_gate() == before["gate"],
            "fw1 no longer carries the rule": lambda: not fw_rule(name),
            f"the border leaf no longer permits {GRAFANA_BLOCK}": lambda: not leaf_permits(GRAFANA_BLOCK),
            "Grafana stops answering the branch desktop": lambda: (
                desk_http(f"http://{GRAFANA_VIP}/api/health") == "000"
            ),
            "the reconciler has pushed and then confirmed": lambda: pushed_and_confirmed(merged),
        },
        timeout=600,
    )

    # RESTORE. The revocation leaves the grant on main as `decommissioned`: a
    # record, not configuration. The demo's starting point has no grant at all,
    # and the Revoke picker would offer this one forever, so it goes -- and its
    # generator instance and tracking group with it (see grant_bookkeeping).
    grant = gql(
        "query ($n: String!) { ServiceAppAccess(name__value: $n) { edges { node { id status { value } } } } }",
        {"n": name},
    )["ServiceAppAccess"]["edges"]
    check(
        bool(grant) and grant[0]["node"]["status"]["value"] == "decommissioned",
        "the merged revocation left the grant decommissioned on main",
    )
    delete_grant(name)
    for branch in (grant_branch, revoke_branch):
        if gql("query ($b: String!) { Branch(name: $b) { name } }", {"b": branch})["Branch"]:
            gql("mutation ($b: String!) { BranchDelete(data: {name: $b}) { ok } }", {"b": branch})
            print(f"    deleted the merged branch {branch}; its proposed change stays as history", flush=True)
    MERGED.clear()
    # One more confirmed cycle, so DeploymentState is read after the last push settled.
    since = time.time()
    wait_until(lambda: any("differed=0" in line for line in reconciler_cycles(since)), timeout=300, interval=10)
    last = (reconciler_cycles(since) or [""])[-1]
    check(
        "compared=14 differed=0 pushed=0 failed=0" in last, "the reconciler reports compared=14 differed=0", last[-90:]
    )
    stage("Restore: comparing the lab with the snapshot")
    if not compare_snapshots(before, snapshot()):
        record("FAIL", "RESTORE FAILED: stop and recover by hand before anything else", "see the differences above")
        return
    with timed("merge cycle: make -C lab verify"):
        verify = run("make", "-C", str(main_checkout() / "lab"), "verify", timeout=1200)
    summary = next((line for line in verify.stdout.splitlines() if " passed, " in line), "")
    if check(
        verify.returncode == 0 and " 0 failed" in summary,
        "make -C lab verify passes",
        re.sub(r"\x1b\[[0-9;]*m", "", summary),
    ):
        SNAPSHOT_FILE.unlink(missing_ok=True)


def act_resume_revoke(name: str, reference: str, via: str) -> None:
    stage(f"Resuming the merge cycle: THIS CHANGES THE LAB -- revoke {name}, merge, restore")
    if not SNAPSHOT_FILE.exists():
        record("FAIL", "no saved snapshot to restore to", str(SNAPSHOT_FILE))
        return
    before = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    MERGED.append(f"implement_{name}")
    grant = gql(
        "query ($n: String!) { ServiceAppAccess(name__value: $n) { edges { node { status { value } } } } }", {"n": name}
    )["ServiceAppAccess"]["edges"]
    if check(bool(grant) and grant[0]["node"]["status"]["value"] == "active", f"{name} is an active grant on main"):
        act_revoke(name, reference, before, via)


# ---------------------------------------------------------------------- main

ACTS = ("preflight", "four", "one", "two", "monitoring", "five")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default=",".join(ACTS), help=f"comma-separated acts, from {', '.join(ACTS)}")
    parser.add_argument(
        "--reference", default=f"rehearsal-{secrets.token_hex(2)}", help="request reference for the portal acts"
    )
    parser.add_argument("--keep", action="store_true", help="leave the branches and proposed changes for inspection")
    parser.add_argument(
        "--merge",
        action="store_true",
        help="CHANGES THE LAB: the preflight, then grant Grafana, merge, revoke, merge, and assert the lab restored",
    )
    parser.add_argument(
        "--resume-revoke",
        metavar="GRANT",
        help="CHANGES THE LAB: finish a --merge cycle that stopped after GRANT merged -- revoke, merge, restore",
    )
    parser.add_argument(
        "--revoke-via",
        choices=("template", "status"),
        default="template",
        help="act three through the portal's Revoke template (the demo), or by setting status on a branch",
    )
    args = parser.parse_args()
    if args.resume_revoke:
        chosen = ["resume"]
    elif args.merge:
        chosen = ["preflight", "merge"]
    else:
        chosen = [act for act in ACTS if act in args.only.split(",")]

    table: dict[str, Callable[[], None]] = {
        "preflight": act_preflight,
        "four": act_four,
        "one": lambda: act_one(args.reference),
        "two": lambda: act_two(args.reference),
        "monitoring": act_monitoring,
        "five": act_five,
        "merge": lambda: act_merge(args.reference, args.revoke_via),
        "resume": lambda: act_resume_revoke(args.resume_revoke, args.reference, args.revoke_via),
    }
    try:
        for act in chosen:
            try:
                table[act]()
            except Exception as exc:  # noqa: BLE001 - one act failing must not skip the cleanup or the rest
                record("FAIL", f"act {act} raised", f"{type(exc).__name__}: {exc}"[:300])
    finally:
        if MERGED:
            print(
                "\n\033[1;31mTHE LAB IS NOT RESTORED.\033[0m Merged and not yet undone: "
                + ", ".join(MERGED)
                + ".\nIf only the grant merged, finish the cycle -- revoke, merge, delete the grant, and"
                " compare with the snapshot saved in "
                + str(SNAPSHOT_FILE)
                + ":\n    uv run python scripts/demo_rehearsal.py --resume-revoke "
                + MERGED[0].removeprefix("implement_")
                + "\nSee docs/docs/demo-runbook.md, Recovery.",
                flush=True,
            )
        if CREATED_BRANCHES and not args.keep:
            stage("Cleaning up")
            cleanup(CREATED_BRANCHES)
        elif CREATED_BRANCHES:
            print(f"\nLeft in place: {', '.join(CREATED_BRANCHES)}")

    stage("Timings")
    for label, seconds in TIMINGS:
        print(f"  {seconds:6.1f} s  {label}")
    failed = [r for r in RESULTS if r[0] == "FAIL"]
    warned = [r for r in RESULTS if r[0] == "WARN"]
    print(f"\n{len(RESULTS) - len(failed) - len(warned)} passed, {len(warned)} warned, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
