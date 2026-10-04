#!/usr/bin/env python3
"""Run the whole demo against the live lab, merges included, with a PASS/FAIL line per check.

    uv run invoke demo-run                              # acts one and two, then the builder, then the builder's reset
    uv run invoke demo-run --acts builder               # one act
    uv run invoke demo-run --acts one,two --restore     # then put the lab back to the baseline

Acts, in the order the runbook shows them:

  one      the portal request "Exposed application, with access" as `alice`, its proposed change
           and every review check, the merge, and the application answering HTTP 200 from the
           branch desktop
  two      the portal request for access to Grafana as `alice`, the merge, Grafana answering the
           branch desktop and `alice` signing in through Dex
  builder  `invoke demo-stage` has built the staged branch; `invoke demo-release`, every validator
           green, the merge through the CoreProposedChangeMerge mutation, `statement 30` on isp-pe1,
           acme answered by the internet host and globex not, then `invoke demo-reset`

IT CHANGES THE LAB. The acts leave an application, two grants and the builder capability merged
(unless the builder's reset runs); `--restore` runs `invoke demo-restore` afterwards, which returns
the lab to the seeded baseline. The helpers are scripts/demo_rehearsal.py's. Exit status is
non-zero when any check fails.
"""

from __future__ import annotations

import argparse
import re
import subprocess  # noqa: S404 - invoke and docker, fixed argv
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_rehearsal as dr

if TYPE_CHECKING:
    from collections.abc import Callable

REPO = Path(__file__).resolve().parents[1]
MAIN = dr.main_checkout()
ACTS = ("one", "two", "builder")
APP = "otter-shop"
STATEMENT_30 = "RM-ACME-IMPORT statement 30"
ROUTER = "clab-otternet-isp-pe1"
INTERNET_HOST = "198.51.100.10"


def invoke(*args: str, timeout: int = 1500) -> tuple[int, str]:
    """Run `uv run invoke ...` from this checkout, echoing its output indented; returns (status, output)."""
    proc = subprocess.run(  # noqa: S603
        ["uv", "run", "invoke", *args],  # noqa: S607
        cwd=REPO, capture_output=True, text=True, timeout=timeout, check=False,
    )  # fmt: skip
    text = proc.stdout + proc.stderr
    print(
        "\n".join("    " + line for line in re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text).splitlines()[-25:]), flush=True
    )
    return proc.returncode, text


def remote_tip(branch: str) -> str:
    out = dr.run("git", "-C", str(MAIN), "ls-remote", "origin", f"refs/heads/{branch}").stdout.split()
    return out[0] if out else ""


def remote_branches(pattern: str) -> list[str]:
    return dr.run("git", "-C", str(MAIN), "ls-remote", "--heads", "origin", pattern).stdout.split()[1::2]


def tree_equal(a: str, b: str) -> bool:
    """Whether two commits hold the same tree, fetching both from the remote first."""
    dr.run("git", "-C", str(MAIN), "fetch", "-q", "origin", "demo-main")
    return dr.run("git", "-C", str(MAIN), "diff", "--quiet", a, b).returncode == 0


def router_has_statement_30() -> bool:
    out = dr.run(
        "docker", "exec", ROUTER, "sr_cli", "info from running /routing-policy policy RM-ACME-IMPORT statement 30"
    )
    return "PL-DEFAULT" in out.stdout + out.stderr


def customer_http(customer: str) -> str:
    out = dr.run(
        "docker", "exec", f"clab-otternet-cust-{customer}-host", "sh", "-c",
        f"curl -s -m 5 -o /dev/null -w '%{{http_code}}' http://{INTERNET_HOST}/ || true",
    )  # fmt: skip
    return out.stdout.strip()[-3:]


def isp_artifact_text() -> str:
    for (_name, target), node in dr.artifacts("main").items():
        if "isp-pe1" in target:
            return "\n".join(dr.storage(node["storage_id"]["value"]))
    return ""


def svc_ip(namespace: str) -> str:
    out = dr.kubectl("-n", namespace, "get", "svc", "-o", "jsonpath={.items[*].status.loadBalancer.ingress[0].ip}")
    return out.stdout.strip().split()[0] if out.returncode == 0 and out.stdout.strip() else ""


def fabricapp_ready(name: str) -> bool:
    out = dr.kubectl("get", "fabricapp", name, "-o", "jsonpath={.status.conditions[?(@.type=='Ready')].status}")
    return out.stdout.strip() == "True"


# ------------------------------------------------------------------------------------------ acts


def act_one(reference: str) -> None:
    dr.stage("ACT ONE: deploy an application with access, through the portal, as alice")
    started = time.monotonic()
    dr.act_one(reference)
    branch = f"implement_{APP}_{reference}"
    if branch not in dr.CREATED_BRANCHES:
        dr.record("FAIL", "act one did not leave its branch to merge")
        return
    block = dr.gql(
        "query ($n: String!) { ServiceFabricApp(name__value: $n) { edges { node { vip_block { node { display_label } } } } } }",
        {"n": APP},
        branch=branch,
    )["ServiceFabricApp"]["edges"][0]["node"]["vip_block"]["node"]["display_label"].split()[0]
    dr.check(
        dr.desk_http(f"http://{block.split('/')[0]}/") != "200",
        "before the merge the branch cannot reach the application's address",
        block,
    )
    if any(r[0] == "FAIL" for r in dr.RESULTS):
        dr.record("FAIL", "act one stops before the merge: a check above failed")
        return
    merged = dr.merge_change(branch)
    dr.watch(
        "act one",
        merged,
        {
            "Vidra delivers the FabricApp (Ready)": lambda: fabricapp_ready(APP),
            "the Service has an external IP": lambda: bool(svc_ip(APP)),
            "fw1 carries the rule": lambda: dr.fw_rule(f"{APP}-access"),
            f"the border leaf permits {block}": lambda: dr.leaf_permits(block),
            "the application answers the branch desktop with HTTP 200": lambda: (
                bool(svc_ip(APP)) and dr.desk_http(f"http://{svc_ip(APP)}/") == "200"
            ),
            "the reconciler has pushed and then confirmed": lambda: dr.pushed_and_confirmed(merged),
        },
        timeout=900,
    )
    dr.TIMINGS.append(("act one: total", time.monotonic() - started))


def act_two(reference: str) -> None:
    dr.stage("ACT TWO: gain access to Grafana through the service portal")
    started = time.monotonic()
    before = dr.desk_http(f"http://{dr.GRAFANA_VIP}/api/health")
    dr.check(before != "200", "before the grant the branch cannot reach Grafana", before)
    name = f"grafana-{reference}"
    branch = f"implement_{name}"
    dr.CREATED_BRANCHES.append(branch)
    with dr.timed("act two: portal request, start to proposed change"):
        result = dr.run_template(
            "template:default/app-access-request",
            {
                "mode": "create", "name": name, "application": f"component:default/{dr.GRAFANA}",
                "owner": "branch", "source_site": "resource:default/branch-office", "justification": "demo run",
            },
        )  # fmt: skip
    if not dr.check(
        result["status"] == "completed",
        "the Grafana grant template completed as alice",
        "; ".join(result.get("errors", []))[:300],
    ):
        return
    with dr.timed("act two: proposed change opened, until every validator is done"):
        green = dr.check_all_green(
            dr.settled_validators(branch), "every validator on the grant's proposed change is green"
        )
    eos = dr.wait_until(lambda: dr.changed_eos(branch), timeout=180, interval=10)
    if not eos:
        dr.rerun_artifact_checks(branch)
        eos = dr.wait_until(lambda: dr.changed_eos(branch), timeout=120, interval=5)
        if eos:
            dr.record("WARN", "the border leaf's diff appeared only after re-running the artifact checks")
    dr.check(list(eos or {}) == [dr.LEAF], "the border leaf's diff is on the proposed change", str(list(eos or {})))
    if not green:
        return
    merged = dr.merge_change(branch)
    dr.watch(
        "act two",
        merged,
        {
            "fw1 carries the rule": lambda: dr.fw_rule(name),
            f"the border leaf permits {dr.GRAFANA_BLOCK}": lambda: dr.leaf_permits(dr.GRAFANA_BLOCK),
            "Vidra delivers Grafana's pod policy with the branch LAN": lambda: (
                dr.BRANCH_LAN in (dr.grafana_gate()["fromCIDR"] or [])
            ),
            "Grafana answers the branch desktop with HTTP 200": lambda: (
                dr.desk_http(f"http://{dr.GRAFANA_VIP}/api/health") == "200"
            ),
            "the reconciler has pushed and then confirmed": lambda: dr.pushed_and_confirmed(merged),
        },
        timeout=900,
    )
    role = dr.grafana_signin()
    dr.check(role == "Viewer", "alice signs in to Grafana through Dex from the branch desktop", role)
    dr.TIMINGS.append(("act two: total", time.monotonic() - started))


def merge_by_mutation(pc_id: str) -> bool:
    start = time.monotonic()
    result = dr.gql(
        "mutation ($id: String!) { CoreProposedChangeMerge(data: {id: $id}, wait_until_completion: true) { ok } }",
        {"id": pc_id},
    )
    dr.TIMINGS.append(("builder: CoreProposedChangeMerge", time.monotonic() - start))
    return bool(result["CoreProposedChangeMerge"]["ok"])


def act_builder(name: str, reset: bool) -> None:
    dr.stage(f"THE BUILDER BRANCH: release stage/{name}, review it, merge it" + (", take it out" if reset else ""))
    started = time.monotonic()
    upstream = remote_tip("main")
    demo_main_before = remote_tip("demo-main")
    dr.run("git", "-C", str(MAIN), "fetch", "-q", "origin", "demo-main")

    with dr.timed("builder: demo-release, start to Ready"):
        status, output = invoke("demo-release", "--name", name)
    dr.check(status == 0 and "Ready:" in output, "demo-release finished and says Ready", f"exit {status}")
    match = re.search(r"as (demo/[\w./-]+) ===", output)
    pc_match = re.search(r"proposed-changes/([0-9a-f-]+)", output)
    if status != 0 or not match or not pc_match:
        return
    branch, pc_id = match.group(1), pc_match.group(1)
    validators = dr.settled_validators(branch, timeout=120)  # already waited for by the release; a read, not a wait
    dr.check_all_green(validators, "every validator of the proposed change is green after Ready")
    diff = (
        dr.gql("query ($b: String!) { DiffTree(branch: $b) { num_removed num_conflicts } }", {"b": branch}).get(
            "DiffTree"
        )
        or {}
    )
    dr.check(
        diff.get("num_removed") == 0 and diff.get("num_conflicts") == 0,
        "the diff removes nothing and has no conflicts",
        str(diff),
    )

    if any(r[0] == "FAIL" for r in dr.RESULTS):
        dr.record("FAIL", "the builder stops before the merge: a check above failed")
        return
    dr.check(merge_by_mutation(pc_id), "the proposed change merged through CoreProposedChangeMerge")
    moved = dr.wait_until(lambda: remote_tip("demo-main") != demo_main_before, timeout=180, interval=5)
    dr.check(bool(moved), "the merge moved demo-main on the remote")
    dr.check(remote_tip("main") == upstream, "upstream main is untouched", upstream[:10])
    merged_at = time.monotonic()
    got = dr.wait_until(lambda: STATEMENT_30 in isp_artifact_text(), timeout=240, interval=5)
    dr.TIMINGS.append(("builder: merge until the artifact carries statement 30", time.monotonic() - merged_at))
    dr.check(bool(got), "the isp-pe1 artifact carries statement 30")
    got = dr.wait_until(router_has_statement_30, timeout=420, interval=10)
    dr.TIMINGS.append(("builder: merge until isp-pe1 runs statement 30", time.monotonic() - merged_at))
    dr.check(bool(got), "isp-pe1 runs statement 30")
    got = dr.wait_until(lambda: customer_http("acme") == "200", timeout=120, interval=5)
    dr.TIMINGS.append(("builder: merge until acme gets HTTP 200", time.monotonic() - merged_at))
    dr.check(bool(got), "acme gets HTTP 200 from the internet host", customer_http("acme"))
    dr.check(customer_http("globex") != "200", "globex does not", customer_http("globex"))

    if reset:
        with dr.timed("builder: demo-reset"):
            status, _ = invoke("demo-reset", "--name", name, timeout=1500)
        dr.check(status == 0, "demo-reset finished", f"exit {status}")
        dr.check(tree_equal(demo_main_before, "origin/demo-main"), "demo-main holds the baseline's tree again")
        dr.check(not remote_branches("refs/heads/demo/*"), "no demo/ branch is left on the remote")
        dr.check(remote_tip("main") == upstream, "upstream main is still untouched")
        names = [b["name"] for b in dr.gql("{ Branch { name } }")["Branch"]]
        dr.check(not [n for n in names if n.startswith("demo/")], "Infrahub has no demo/ branch")
        dr.check(
            not dr.gql('{ __type(name: "ServiceInternetAccess") { name } }')["__type"], "the capability's kind is gone"
        )
        gone = dr.wait_until(lambda: not router_has_statement_30(), timeout=420, interval=10)
        dr.check(bool(gone), "isp-pe1 is back to the baseline (no statement 30)")
        dr.check(
            bool(dr.wait_until(lambda: customer_http("acme") != "200", timeout=120, interval=5)),
            "acme has no internet again",
        )
    dr.TIMINGS.append(("builder: total", time.monotonic() - started))


# ------------------------------------------------------------------------------------------ main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--acts", default=",".join(ACTS), help=f"comma-separated, from {', '.join(ACTS)}")
    parser.add_argument("--reference", default="demo1", help="request reference for the portal acts")
    parser.add_argument("--name", default="internet-access", help="the builder capability (stage/<name>)")
    parser.add_argument("--no-builder-reset", action="store_true", help="leave the builder capability merged")
    parser.add_argument("--restore", action="store_true", help="afterwards run `invoke demo-restore`")
    args = parser.parse_args()
    chosen = [a for a in ACTS if a in args.acts.split(",")]
    unknown = set(args.acts.split(",")) - set(ACTS)
    if unknown:
        parser.error(f"unknown acts: {', '.join(sorted(unknown))}")

    table: dict[str, Callable[[], None]] = {
        "one": lambda: act_one(args.reference),
        "two": lambda: act_two(args.reference),
        "builder": lambda: act_builder(args.name, not args.no_builder_reset),
    }
    for act in chosen:
        try:
            table[act]()
        except Exception as exc:  # noqa: BLE001 - one act failing must not hide the rest
            dr.record("FAIL", f"act {act} raised", f"{type(exc).__name__}: {exc}"[:300])
    if args.restore:
        dr.stage("RESTORE: invoke demo-restore")
        with dr.timed("restore: demo-restore"):
            status, _ = invoke("demo-restore", "--name", args.name, timeout=3000)
        dr.check(status == 0, "demo-restore finished and verified the baseline", f"exit {status}")

    dr.stage("Timings")
    for label, seconds in dr.TIMINGS:
        print(f"  {seconds:6.1f} s  {label}")
    failed = [r for r in dr.RESULTS if r[0] == "FAIL"]
    warned = [r for r in dr.RESULTS if r[0] == "WARN"]
    print(f"\n{len(dr.RESULTS) - len(failed) - len(warned)} passed, {len(warned)} warned, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
