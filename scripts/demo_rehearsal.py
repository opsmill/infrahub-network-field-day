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
at the end -- including when an act fails. NOTHING IS MERGED, and nothing touches
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


def check_all_green(validators: list[dict[str, Any]], what: str) -> None:
    red = sorted({v["display_label"] for v in validators if v["conclusion"]["value"] != "success"})
    check(not red and bool(validators), what, ", ".join(red) or f"{len(validators)} validators")


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


# ---------------------------------------------------------------------- main

ACTS = ("preflight", "four", "one", "two", "monitoring", "five")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default=",".join(ACTS), help=f"comma-separated acts, from {', '.join(ACTS)}")
    parser.add_argument(
        "--reference", default=f"rehearsal-{secrets.token_hex(2)}", help="request reference for the portal acts"
    )
    parser.add_argument("--keep", action="store_true", help="leave the branches and proposed changes for inspection")
    args = parser.parse_args()
    chosen = [act for act in ACTS if act in args.only.split(",")]

    table: dict[str, Callable[[], None]] = {
        "preflight": act_preflight,
        "four": act_four,
        "one": lambda: act_one(args.reference),
        "two": lambda: act_two(args.reference),
        "monitoring": act_monitoring,
        "five": act_five,
    }
    try:
        for act in chosen:
            try:
                table[act]()
            except Exception as exc:  # noqa: BLE001 - one act failing must not skip the cleanup or the rest
                record("FAIL", f"act {act} raised", f"{type(exc).__name__}: {exc}"[:300])
    finally:
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
