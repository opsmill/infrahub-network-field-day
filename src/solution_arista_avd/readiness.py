"""`invoke ready`: is the environment good to go, as a person about to demonstrate it needs it?

`invoke doctor` looks for quiet failures in a development environment. This module
answers a different question: after `invoke bootstrap`, does everything a demonstration
relies on exist and work? Each check names one thing a presenter would otherwise find
out on stage: the application catalogue, the event rules, the MCP server and the two
identities it serves, the Requester Access role, the network-admin account, the repository mode, the portal's
picker.

Structure follows `doctor.py`:

* **decisions** (`decide_*`) are pure. They take plain data and return a `Result`.
  `tests/unit/test_readiness.py` pins each one with a passing and a failing input.
* **probes** (`probe_*`) do the I/O and hand the result to a decision. A probe that
  cannot reach what it needs raises `Unavailable` and the runner reports `SKIP`.

Host-side only. Nothing that runs in the Infrahub image imports this.
"""

from __future__ import annotations

import json
import os
import re
import subprocess  # noqa: S404 - fixed-argv calls, never a shell string
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import yaml

from solution_arista_avd import envfile
from solution_arista_avd.doctor import Environment, Result, Status, Unavailable, _run

if TYPE_CHECKING:
    from collections.abc import Callable

# Accounts that get an MCP API token of their own, so a client can act as that person.
# Dex also has `bob`, who exists to be a user with no access; nothing registers him with
# the MCP server, so he gets no token.
MCP_TOKEN_USERS = ("alice",)
MCP_SERVER_URL = "http://127.0.0.1:8001/mcp"
MCP_HEALTH_URL = "http://127.0.0.1:8001/health"
MCP_AGENT = "mcp-agent"
# The local account for the network team: not Dex, not a Super Administrator.
NETWORK_ADMIN = "alex"
NETWORK_ADMIN_PASSWORD_VAR = "INFRAHUB_NETWORK_ADMIN_PASSWORD"  # noqa: S105 -- the variable's name, not a password
# The one server in .mcp.json. Claude Code acts as alice and as no other identity.
MCP_SERVER_NAME = "otternet-infrahub"
# The observability namespaces Vidra's delivery creates, and the Secrets that `invoke cluster` puts in them.
# Only key names are ever read from the cluster; a Secret's values are never fetched or printed.
OBSERVABILITY_NAMESPACES = ("otternet-metrics", "otternet-telemetry")
OBSERVABILITY_SECRETS: dict[str, dict[str, tuple[str, ...]]] = {
    "otternet-metrics": {
        "grafana-admin": ("admin-user", "admin-password"),
        "grafana-oidc": ("client-secret",),
    },
    "otternet-telemetry": {"telemetry-credentials": ("GNMI_USERNAME", "GNMI_PASSWORD")},
}
SECRETS_FIX = "uv run invoke observability-secrets"
# How long `invoke cluster` waits for each namespace. Measured namespaces appear within minutes of the
# delivery starting; the wait is twice the 300 s that `_wait_for_syncs` allows for the claims.
NAMESPACE_WAIT_SECONDS = 600
GRAFANA_SELECTOR = "app.kubernetes.io/name=grafana"
STUCK_CONTAINER_REASONS = ("CreateContainerConfigError",)
DEFAULT_BRANCH_DEMO = "demo-main"
EXPECTED_TASK_WORKERS = 2
# A merge takes about 20 to 100 seconds. A proposed change still in `merging` after this many minutes belongs to a
# merge whose task worker stopped, not to one that is running.
STUCK_MERGE_MINUTES = 15
DESKTOP = "clab-otternet-branch-desktop"
SIGNIN_REMOTE = "/tmp/portal_signin.sh"  # noqa: S108 - a path inside the branch desktop container
PORTAL = "https://10.90.0.11:32001"
# The development token in docker-compose.override.yml, the same fallback verify_bootstrap.sh uses.
DEV_API_TOKEN = "06438eb2-8019-4776-878c-0941b1f1d1ec"  # noqa: S105 - committed development default, not a secret


def token_var(user: str) -> str:
    """The `.env` variable holding the user's MCP token: `alice` gives INFRAHUB_MCP_TOKEN_ALICE."""
    return "INFRAHUB_MCP_TOKEN_" + user.upper().replace("-", "_")


# --------------------------------------------------------------------------- expectations read from the repository


def _yaml_documents(path: Path) -> list[dict[str, Any]]:
    return [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(doc, dict)]


def expected_catalogue(root: Path) -> dict[str, bool]:
    """Catalogue entry name to `requestable`, as `objects/35a_otternet_app_catalogue.yml` declares them."""
    entries: dict[str, bool] = {}
    for doc in _yaml_documents(root / "objects/35a_otternet_app_catalogue.yml"):
        spec = doc.get("spec") or {}
        if spec.get("kind") != "ServiceApplicationDefinition":
            continue
        for item in spec.get("data") or []:
            entries[str(item["name"])] = bool(item.get("requestable", False))
    return entries


def expected_trigger_objects(root: Path) -> dict[str, set[str]]:
    """Kind to the names `triggers.yml` declares: generator actions, group actions and both rule kinds."""
    found: dict[str, set[str]] = {}
    for doc in _yaml_documents(root / "triggers.yml"):
        spec = doc.get("spec") or {}
        kind = str(spec.get("kind", ""))
        if kind:
            found.setdefault(kind, set()).update(str(item["name"]) for item in spec.get("data") or [])
    return found


def expected_menu_identifiers(root: Path) -> set[str]:
    """`namespace + name` of every entry in `menus/*.yml`, at any depth."""
    found: set[str] = set()

    def walk(items: list[dict[str, Any]]) -> None:
        for item in items:
            found.add(f"{item['namespace']}{item['name']}")
            walk((item.get("children") or {}).get("data") or [])

    for path in sorted((root / "menus").glob("*.yml")):
        for doc in _yaml_documents(path):
            if doc.get("kind") == "Menu":
                walk(doc["spec"]["data"])
    return found


def expected_seeded_apps(root: Path) -> set[str]:
    """Names of the `ServiceFabricApp` objects the seed data declares."""
    names: set[str] = set()
    for path in sorted((root / "objects").glob("*.yml")):
        for doc in _yaml_documents(path):
            spec = doc.get("spec") or {}
            if spec.get("kind") == "ServiceFabricApp":
                names.update(str(item["name"]) for item in spec.get("data") or [])
    return names


# --------------------------------------------------------------------------- decisions


def decide_catalogue(expected: dict[str, bool], found: dict[str, tuple[bool, str]]) -> Result:
    """`found`: name to (requestable, status). The picker offers requestable AND active entries."""
    name = "application catalogue"
    missing = sorted(set(expected) - set(found))
    if missing:
        return Result(name, Status.FAIL, f"missing entries: {', '.join(missing)}", "uv run invoke load")
    wrong = sorted(n for n, want in expected.items() if found[n][0] != want)
    if wrong:
        return Result(name, Status.FAIL, f"requestable differs from the seed data for: {', '.join(wrong)}")
    requestable = sorted(n for n, want in expected.items() if want)
    return Result(name, Status.PASS, f"{len(found)} entries; requestable: {', '.join(requestable)}")


def decide_declared(label: str, expected: set[str], found: set[str], fix: str) -> Result:
    """Every name a file declares exists in Infrahub."""
    missing = sorted(expected - found)
    if missing:
        shown = ", ".join(missing[:6]) + (f" and {len(missing) - 6} more" if len(missing) > 6 else "")
        return Result(label, Status.FAIL, f"{len(missing)} of {len(expected)} missing: {shown}", fix)
    return Result(label, Status.PASS, f"all {len(expected)} present")


def decide_seeded_apps(expected: set[str], rows: dict[str, tuple[bool, bool]]) -> Result:
    """`rows`: application name to (has a catalogue entry, definition_pinned)."""
    name = "seeded applications are pinned from the catalogue"
    missing = sorted(expected - set(rows))
    unpinned = sorted(n for n in expected & set(rows) if not (rows[n][0] and rows[n][1]))
    if missing or unpinned:
        parts = []
        if missing:
            parts.append(f"missing: {', '.join(missing)}")
        if unpinned:
            parts.append(f"without a catalogue entry or pin: {', '.join(unpinned)}")
        return Result(name, Status.FAIL, "; ".join(parts), "uv run invoke load")
    return Result(name, Status.PASS, ", ".join(sorted(expected)))


def decide_mcp_server(running: bool, health: dict[str, Any] | None) -> Result:
    name = "MCP server runs in token-passthrough mode"
    if not running:
        return Result(name, Status.FAIL, "the infrahub-mcp container is not running", "uv run invoke mcp")
    if not health:
        return Result(name, Status.FAIL, f"{MCP_HEALTH_URL} did not answer", "uv run invoke mcp")
    mode = health.get("auth_mode")
    if mode != "token-passthrough":
        return Result(name, Status.FAIL, f"auth_mode is {mode!r}", "uv run invoke mcp")
    return Result(name, Status.PASS, f"{MCP_HEALTH_URL} reports auth_mode token-passthrough")


def decide_identity(label: str, expected: str, got: str, variable: str, fix: str) -> Result:
    """A tool call with the token in `variable` answered `AccountProfile` with `got`."""
    if not got:
        return Result(label, Status.FAIL, f"{variable} is missing or the MCP server refused it", fix)
    if got != expected:
        return Result(label, Status.FAIL, f"{variable} authenticates as {got!r}, expected {expected!r}", fix)
    return Result(label, Status.PASS, f"a tool call with {variable} returns AccountProfile {expected}")


def decide_script_check(label: str, returncode: int, output: str, fix: str) -> Result:
    """The outcome of a `scripts/provision_*.py --check` run."""
    if returncode == 0:
        return Result(label, Status.PASS, (output.strip().splitlines() or ["ok"])[-1])
    problems = [line.removeprefix("PROBLEM: ") for line in output.splitlines() if line.strip()]
    return Result(label, Status.FAIL, "; ".join(problems[:3]) or f"exit status {returncode}", fix)


def decide_mcp_config(config: dict[str, Any], env_names: set[str], users: tuple[str, ...]) -> Result:
    """`.mcp.json` has exactly one server, `otternet-infrahub`, sending alice's token, and `.env` has that variable."""
    name = ".mcp.json servers match the variables the scripts write"
    servers = config.get("mcpServers") or {}
    wanted = {MCP_SERVER_NAME: token_var(users[0])}
    problems: list[str] = [f"unexpected server {extra!r}" for extra in sorted(set(servers) - set(wanted))]
    for server, variable in wanted.items():
        entry = servers.get(server)
        if entry is None:
            problems.append(f"no server {server!r}")
            continue
        header = str((entry.get("headers") or {}).get("Authorization", ""))
        if header != f"Bearer ${{{variable}}}":
            problems.append(f"{server} sends {header!r}, expected 'Bearer ${{{variable}}}'")
        if variable not in env_names:
            problems.append(f"{variable} is not in .env")
    if problems:
        return Result(name, Status.FAIL, "; ".join(problems), "uv run invoke mcp; uv run invoke mcp-tokens")
    return Result(name, Status.PASS, ", ".join(f"{s} uses {v}" for s, v in wanted.items()))


def decide_claude_mcp_list(output: str, servers: list[str]) -> Result:
    """`claude mcp list` prints one line per server ending in a status; each wanted server must be connected."""
    name = "`claude mcp list` shows the servers connected"
    problems = []
    for server in servers:
        line = next((ln for ln in output.splitlines() if ln.startswith(f"{server}:")), "")
        if not line:
            problems.append(f"{server} is not listed")
        elif "Connected" not in line and "✓" not in line:
            problems.append(f"{server}: {line.split(':', 1)[1].strip()}")
    if problems:
        return Result(
            name,
            Status.FAIL,
            "; ".join(problems),
            "start Claude Code from a shell that ran `set -a; source .env; set +a`",
        )
    return Result(name, Status.PASS, ", ".join(servers))


def decide_repository(
    repo: dict[str, str],
    *,
    expect_readwrite: bool,
    workers: int,
    remote_main: str,
    remote_demo_main: str,
    trees_equal: bool | None,
) -> Result:
    """Read-write repository on `demo-main`, in sync, demo-main equal to main, two task workers."""
    name = "repository is read-write on demo-main, in sync, demo-main equals main"
    if not repo:
        return Result(name, Status.FAIL, "no repository is registered", "uv run invoke load")
    readwrite = repo.get("kind") == "CoreRepository" and repo.get("default_branch") == DEFAULT_BRANCH_DEMO
    if not readwrite:
        if expect_readwrite:
            return Result(
                name,
                Status.FAIL,
                f"{repo.get('kind')} on {repo.get('default_branch') or repo.get('ref') or '?'}, not read-write on demo-main",
                "uv run invoke bootstrap --fresh with INFRAHUB_REPOSITORY_MODE=readwrite (docs/docs/demo-builder.md)",
            )
        return Result(
            name, Status.SKIP, "this stack is not read-write; set INFRAHUB_REPOSITORY_MODE=readwrite to require it"
        )
    problems: list[str] = []
    fixes: list[str] = []
    if repo.get("sync_status") != "in-sync":
        problems.append(f"sync_status {repo.get('sync_status') or 'unknown'}")
        fixes.append(
            "wait for the repository to reach in-sync, or read `docker compose logs task-worker` for the failed import"
        )
    if workers != EXPECTED_TASK_WORKERS:
        problems.append(f"{workers} task workers, expected {EXPECTED_TASK_WORKERS}")
        fixes.append("a stopped task worker is started again by `uv run invoke start`")
    demo_main_differs = False
    if not remote_demo_main:
        problems.append("demo-main does not exist on the remote")
        demo_main_differs = True
    elif remote_demo_main == remote_main or trees_equal:
        pass
    else:
        problems.append(f"demo-main ({remote_demo_main[:10]}) differs from main ({remote_main[:10]})")
        demo_main_differs = True
    if demo_main_differs:
        fixes.append(
            "a demo-main behind main after a merge to main: `uv run invoke demo-advance` brings it level through Infrahub "
            "(after `git pull --ff-only origin main`); after a bootstrap it is stale and `uv run invoke bootstrap --fresh` recreates it; "
            "after a demonstration use `uv run invoke demo-restore`"
        )
    if problems:
        return Result(name, Status.FAIL, "; ".join(problems), "; ".join(fixes))
    same = "same commit" if remote_demo_main == remote_main else "same tree, different commits"
    return Result(name, Status.PASS, f"in-sync, {workers} task workers, demo-main and main: {same}")


def decide_leftover_branches(branches: list[dict[str, Any]]) -> Result:
    """Any non-default Infrahub branch left behind, which includes an MCP session branch."""
    name = "no leftover Infrahub branches"
    extra = sorted(b["name"] for b in branches if not b.get("is_default"))
    if extra:
        mcp = [n for n in extra if n.startswith("mcp/session-")]
        detail = f"{len(extra)} branch(es): {', '.join(extra[:5])}"
        if mcp:
            detail += f" ({len(mcp)} MCP session branch(es))"
        return Result(name, Status.WARN, detail, "delete a finished one with `uv run infrahubctl branch delete <name>`")
    return Result(name, Status.PASS, "only the default branch")


def decide_stuck_merges(
    proposed_changes: list[dict[str, str]], now: datetime, minutes: int = STUCK_MERGE_MINUTES
) -> Result:
    """A proposed change left in state `merging` after its merge crashed.

    Each row holds `name`, `source_branch` and `updated_at` (ISO 8601). Infrahub does not move the record out of
    `merging` when the task worker that ran the merge stops, so the record stays there for good and
    nothing else reports it.
    """
    name = "no proposed change stuck in merging"
    stuck = []
    for row in proposed_changes:
        try:
            changed = datetime.fromisoformat(row["updated_at"])
        except (KeyError, ValueError):
            stuck.append(f"{row.get('name', '?')} (no usable update time)")
            continue
        if changed.tzinfo is None:
            changed = changed.replace(tzinfo=UTC)
        age = (now - changed).total_seconds() / 60
        if age >= minutes:
            stuck.append(f"{row.get('name', '?')} on {row.get('source_branch', '?')} ({age:.0f} min)")
    if not stuck:
        return Result(name, Status.PASS, f"none in state merging for more than {minutes} minutes")
    return Result(
        name,
        Status.WARN,
        f"{len(stuck)} in state merging for more than {minutes} minutes: {'; '.join(stuck[:3])}",
        "a merge crashed: run `uv run invoke start`, then `uv run invoke demo-reset`, confirm that the merge did not "
        "reach `main`, then delete the record (see demo-builder.md, 'A proposed change stuck in merging')",
    )


def decide_stage_branch(stage: str, exists: bool, merge_base: str, main_tip: str) -> Result:
    """The staged capability branch is cut from the commit `main` is on now, or `demo-release` writes old files back."""
    name = f"local {stage} is cut from the current main"
    if not exists:
        return Result(
            name, Status.SKIP, f"{stage} does not exist; `uv run invoke demo-stage` builds it for the builder act"
        )
    if merge_base != main_tip:
        return Result(
            name,
            Status.WARN,
            f"cut from {merge_base[:10]}, main is {main_tip[:10]}",
            "uv run invoke demo-stage --force",
        )
    return Result(name, Status.PASS, f"cut from {main_tip[:10]}")


def decide_picker(found: set[str], expected: set[str]) -> Result:
    """The portal's picker offers exactly the requestable catalogue entries."""
    name = "portal picker lists the requestable catalogue entries"
    if found != expected:
        return Result(
            name,
            Status.FAIL,
            f"picker has {sorted(found)}, requestable entries are {sorted(expected)}",
            "uv run invoke backstage-build tooling; the portal refreshes its catalogue on a timer",
        )
    return Result(name, Status.PASS, ", ".join(sorted(found)))


def decide_shell_environment(stale: list[str]) -> Result:
    """The shell that runs the check holds no generated credential that differs from `.env`."""
    name = "this shell's credential variables match .env"
    if stale:
        return Result(
            name,
            Status.WARN,
            f"{', '.join(stale)} differ from .env (a shell that loaded .env before the stack was rebuilt)",
            "open a new shell, or run `set -a; source .env; set +a`, before starting Claude Code",
        )
    return Result(name, Status.PASS, "no differing variable")


def decide_proposed_change(opened: bool, detail: str) -> Result:
    name = "alice can open a proposed change"
    if not opened:
        return Result(name, Status.FAIL, detail, "uv run python scripts/provision_requester_access.py")
    return Result(name, Status.PASS, detail)


def decide_alice_main_write(written: bool, detail: str) -> Result:
    name = "alice cannot write to main"
    if written:
        return Result(name, Status.FAIL, detail, "uv run python scripts/provision_requester_access.py")
    return Result(name, Status.PASS, detail)


# --------------------------------------------------------------------------- probes


def namespace_wait_error(missing: list[str], waited: int) -> str:
    """The message that stops `invoke cluster` when an observability namespace never appeared."""
    names = ", ".join(missing)
    return (
        f"The namespace(s) {names} did not appear after waiting {waited} s each, so their Secrets were not created "
        "and Grafana or Telegraf cannot start (their pods stay in CreateContainerConfigError).\n"
        "Vidra creates these namespaces by delivering the FabricApp claims from Infrahub. What to check:\n"
        "  kubectl get vidraresource -A\n"
        "  kubectl get fabricapp\n"
        "  kubectl -n vidra-system logs deploy/vidra-vidra-operator-controller-manager --tail=100\n"
        "Why delivery is delayed is not known: one bootstrap created otternet-metrics 4.5 hours late, with no cause found.\n"
        f"Once the namespace exists, run: {SECRETS_FIX}"
    )


def decide_observability_namespaces(found: set[str]) -> Result:
    missing = [n for n in OBSERVABILITY_NAMESPACES if n not in found]
    name = "observability namespaces"
    if missing:
        return Result(
            name,
            Status.FAIL,
            f"missing: {', '.join(missing)} (Vidra has not delivered them; check `kubectl get vidraresource -A`)",
            f"once they exist: {SECRETS_FIX}",
        )
    return Result(name, Status.PASS, ", ".join(OBSERVABILITY_NAMESPACES))


def decide_observability_secrets(found: dict[str, dict[str, set[str]]]) -> Result:
    """`found` maps namespace to Secret name to the key names it holds. Values are never passed in."""
    name = "observability Secrets"
    problems = []
    for namespace, secrets in OBSERVABILITY_SECRETS.items():
        for secret, keys in secrets.items():
            held = found.get(namespace, {}).get(secret)
            if held is None:
                problems.append(f"{namespace}/{secret} does not exist")
                continue
            absent = [k for k in keys if k not in held]
            if absent:
                problems.append(f"{namespace}/{secret} lacks key(s) {', '.join(absent)}")
    if problems:
        return Result(name, Status.FAIL, "; ".join(problems), SECRETS_FIX)
    count = sum(len(v) for v in OBSERVABILITY_SECRETS.values())
    return Result(name, Status.PASS, f"{count} Secrets exist with their keys (values not read)")


def decide_grafana_pod(pods: list[tuple[str, str, list[str]]]) -> Result:
    """`pods` is (name, phase, waiting reasons of its containers and init containers)."""
    name = "Grafana pod"
    if not pods:
        return Result(name, Status.WARN, "no Grafana pod in otternet-metrics yet (still being delivered?)", SECRETS_FIX)
    stuck = [(pod, reasons) for pod, _phase, reasons in pods if any(r in STUCK_CONTAINER_REASONS for r in reasons)]
    if stuck:
        pod, reasons = stuck[0]
        return Result(
            name,
            Status.FAIL,
            f"{pod} is stuck in {', '.join(sorted(set(reasons) & set(STUCK_CONTAINER_REASONS)))}: a Secret it references is missing",
            SECRETS_FIX,
        )
    return Result(name, Status.PASS, ", ".join(f"{pod} {phase}" for pod, phase, _ in pods))


def _api_token() -> str:
    return os.environ.get("INFRAHUB_API_TOKEN") or DEV_API_TOKEN


def _env(root: Path) -> Environment:
    return Environment(root=root, token=_api_token())


def _env_values(root: Path) -> dict[str, str]:
    path = envfile.env_file(root)
    if not path.exists():
        return {}
    names = re.findall(r"^([A-Z][A-Z0-9_]*)=", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    return {name: envfile.read_env(path, name) for name in names}


def mcp_tool_call(token: str, query: str, url: str = MCP_SERVER_URL) -> dict[str, Any]:
    """One `query_graphql` tool call over MCP's streamable HTTP transport, with `token` as the Bearer header."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=30) as client:
            init = client.post(
                url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "invoke-ready", "version": "1"},
                    },
                },
            )
            session = init.headers.get("mcp-session-id")
            if session:
                headers["mcp-session-id"] = session
            client.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
            call = client.post(
                url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "query_graphql", "arguments": {"query": query}},
                },
            )
    except httpx.HTTPError as exc:
        msg = f"the MCP server at {url} did not answer ({type(exc).__name__})"
        raise Unavailable(msg) from exc
    for line in call.text.splitlines():
        if line.startswith("data:"):
            try:
                result = json.loads(line[5:]).get("result") or {}
            except ValueError:
                return {}
            if result.get("isError"):
                return {}
            return dict(result.get("structuredContent") or {})
    return {}


def account_through_mcp(token: str) -> str:
    """The account the MCP server says `token` belongs to, or the empty string."""
    if not token:
        return ""
    data = mcp_tool_call(token, "query { AccountProfile { name { value } } }")
    return str(((data.get("AccountProfile") or {}).get("name") or {}).get("value") or "")


def probe_catalogue(env: Environment) -> Result:
    data = env.graphql(
        "{ ServiceApplicationDefinition { edges { node { name { value } requestable { value } status { value } } } } }"
    )
    found = {
        e["node"]["name"]["value"]: (bool(e["node"]["requestable"]["value"]), str(e["node"]["status"]["value"]))
        for e in (data.get("ServiceApplicationDefinition") or {}).get("edges") or []
    }
    return decide_catalogue(expected_catalogue(env.root), found)


def probe_triggers(env: Environment) -> Result:
    expected = expected_trigger_objects(env.root)
    wanted: set[str] = set()
    found: set[str] = set()
    for kind, names in sorted(expected.items()):
        data = env.graphql(f"{{ {kind} {{ edges {{ node {{ name {{ value }} }} }} }} }}")
        present = {e["node"]["name"]["value"] for e in (data.get(kind) or {}).get("edges") or []}
        wanted |= {f"{kind}:{n}" for n in names}
        found |= {f"{kind}:{n}" for n in names & present}
    return decide_declared(
        "triggers.yml objects, including the group rules",
        wanted,
        found,
        "uv run infrahubctl object load triggers.yml",
    )


def probe_menus(env: Environment) -> Result:
    data = env.graphql("{ CoreMenuItem { edges { node { namespace { value } name { value } } } } }")
    found = {
        f"{e['node']['namespace']['value']}{e['node']['name']['value']}"
        for e in (data.get("CoreMenuItem") or {}).get("edges") or []
    }
    return decide_declared("menus", expected_menu_identifiers(env.root), found, "uv run invoke load-menu")


def probe_seeded_apps(env: Environment) -> Result:
    data = env.graphql(
        "{ ServiceFabricApp { edges { node { name { value } definition_pinned { value } definition { node { id } } } } } }"
    )
    rows = {
        e["node"]["name"]["value"]: (
            bool((e["node"].get("definition") or {}).get("node")),
            bool(e["node"]["definition_pinned"]["value"]),
        )
        for e in (data.get("ServiceFabricApp") or {}).get("edges") or []
    }
    return decide_seeded_apps(expected_seeded_apps(env.root), rows)


def probe_mcp_server(env: Environment) -> Result:  # noqa: ARG001
    proc = _run(["docker", "ps", "-q", "--filter", "label=com.docker.compose.service=infrahub-mcp"])
    running = bool(proc.stdout.split())
    health: dict[str, Any] | None = None
    if running:
        try:
            health = httpx.get(MCP_HEALTH_URL, timeout=5).json()
        except (httpx.HTTPError, ValueError):
            health = None
    return decide_mcp_server(running, health)


def probe_agent_identity(env: Environment) -> Result:
    token = _env_values(env.root).get("INFRAHUB_MCP_TOKEN", "")
    return decide_identity(
        "mcp-agent token (used by the demo rehearsal, not by Claude Code) works through MCP",
        MCP_AGENT,
        account_through_mcp(token),
        "INFRAHUB_MCP_TOKEN",
        "uv run invoke mcp",
    )


def _script_check(env: Environment, label: str, script: str, args: list[str], fix: str) -> Result:
    proc = _run([sys.executable, str(env.root / "scripts" / script), "--check", *args], cwd=env.root, timeout=120)
    return decide_script_check(label, proc.returncode, proc.stdout + proc.stderr, fix)


def probe_agent_role(env: Environment) -> Result:
    return _script_check(env, "mcp-agent exists with its role", "provision_mcp_agent.py", [], "uv run invoke mcp")


def probe_requester_role(env: Environment) -> Result:
    return _script_check(
        env,
        "Infrahub Users holds only Requester Access",
        "provision_requester_access.py",
        [],
        "uv run invoke mcp",
    )


def probe_network_admin(env: Environment) -> Result:
    # The script's `--check` covers: the account exists, it is in `Network Admins` only and not in
    # `Super Administrators` or `Infrahub Users`, the role holds exactly the defined permissions, and the
    # password in `.env` signs in.
    return _script_check(
        env,
        "alex signs in and holds only Network Admin Access",
        "provision_network_admin.py",
        [],
        "uv run invoke network-admin",
    )


def probe_portal_accounts(env: Environment) -> Result:
    return _script_check(
        env, "every portal user has an Infrahub account", "provision_portal_accounts.py", [], "uv run invoke tooling"
    )


def probe_user_identity(env: Environment, user: str) -> Result:
    variable = token_var(user)
    token = _env_values(env.root).get(variable, "")
    return decide_identity(
        f"{user}'s MCP token works through MCP",
        user,
        account_through_mcp(token),
        variable,
        "uv run invoke mcp-tokens",
    )


def probe_alice_proposed_change(env: Environment) -> Result:
    """Open a proposed change with alice's token on a throw-away branch, then delete both."""
    user = MCP_TOKEN_USERS[0]
    token = _env_values(env.root).get(token_var(user), "")
    if not token:
        return decide_proposed_change(False, f"{token_var(user)} is not in .env")
    branch = "ready-check-" + os.urandom(3).hex()
    admin = {"X-INFRAHUB-KEY": env.token}
    own = {"X-INFRAHUB-KEY": token}

    def post(headers: dict[str, str], query: str, path: str = "graphql") -> dict[str, Any]:
        response = httpx.post(f"{env.address}/{path}", json={"query": query}, headers=headers, timeout=60)
        return dict(response.json())

    proposed_id = ""
    try:
        post(admin, f'mutation {{ BranchCreate(data: {{name: "{branch}", sync_with_git: false}}) {{ ok }} }}')
        reply = post(
            own,
            "mutation { CoreProposedChangeCreate(data: {"
            f'name: {{value: "{branch}"}}, source_branch: {{value: "{branch}"}}, destination_branch: {{value: "main"}}'
            "}) { ok object { id } } }",
        )
        if reply.get("errors"):
            return decide_proposed_change(False, str(reply["errors"][0].get("message", "refused"))[:160])
        proposed_id = str(reply["data"]["CoreProposedChangeCreate"]["object"]["id"])
        return decide_proposed_change(True, f"{user} opened and the check deleted proposed change {proposed_id[:8]}")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise Unavailable(f"could not run the proposed change check ({type(exc).__name__})") from exc
    finally:
        try:
            if proposed_id:
                post(admin, f'mutation {{ CoreProposedChangeDelete(data: {{id: "{proposed_id}"}}) {{ ok }} }}')
            post(admin, f'mutation {{ BranchDelete(data: {{name: "{branch}"}}) {{ ok }} }}')
        except (httpx.HTTPError, ValueError):
            pass


def probe_alice_main_write(env: Environment) -> Result:
    """Ask for a scratch tag on `main` with alice's token. A refusal is the expected answer."""
    user = MCP_TOKEN_USERS[0]
    token = _env_values(env.root).get(token_var(user), "")
    if not token:
        msg = f"{token_var(user)} is not in .env"
        raise Unavailable(msg)
    tag = "ready-check-" + os.urandom(3).hex()
    try:
        response = httpx.post(
            f"{env.address}/graphql",
            json={
                "query": f'mutation {{ BuiltinTagCreate(data: {{name: {{value: "{tag}"}}}}) {{ ok object {{ id }} }} }}'
            },
            headers={"X-INFRAHUB-KEY": token},
            timeout=60,
        )
        reply = dict(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise Unavailable(f"could not run the main write check ({type(exc).__name__})") from exc
    if reply.get("errors"):
        return decide_alice_main_write(False, str(reply["errors"][0].get("message", "refused"))[:160])
    try:
        created = str(reply["data"]["BuiltinTagCreate"]["object"]["id"])
        httpx.post(
            f"{env.address}/graphql",
            json={"query": f'mutation {{ BuiltinTagDelete(data: {{id: "{created}"}}) {{ ok }} }}'},
            headers={"X-INFRAHUB-KEY": env.token},
            timeout=60,
        )
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    return decide_alice_main_write(True, f"{user} created a tag on main; the check deleted it")


def _git(root: Path, *args: str) -> str:
    return _run(["git", *args], cwd=root).stdout.strip()


def probe_repository(env: Environment) -> Result:
    data = env.graphql(
        "{ CoreGenericRepository { edges { node { __typename sync_status { value } "
        "... on CoreRepository { default_branch { value } } ... on CoreReadOnlyRepository { ref { value } } } } } }"
    )
    edges = (data.get("CoreGenericRepository") or {}).get("edges") or []
    repo: dict[str, str] = {}
    if edges:
        node = edges[0]["node"]
        repo = {
            "kind": str(node["__typename"]),
            "sync_status": str((node.get("sync_status") or {}).get("value") or ""),
            "default_branch": str((node.get("default_branch") or {}).get("value") or ""),
            "ref": str((node.get("ref") or {}).get("value") or ""),
        }
    workers = len(
        _run(["docker", "ps", "-q", "--filter", "label=com.docker.compose.service=task-worker"]).stdout.split()
    )
    root = envfile.main_checkout(env.root)
    _git(root, "fetch", "--quiet", "origin", "main", DEFAULT_BRANCH_DEMO)
    remote_main = _git(root, "rev-parse", "origin/main")
    remote_demo = _git(root, "rev-parse", f"origin/{DEFAULT_BRANCH_DEMO}") if repo.get("default_branch") else ""
    trees_equal: bool | None = None
    if remote_demo and remote_demo != remote_main:
        trees_equal = (
            _run(["git", "diff", "--quiet", "origin/main", f"origin/{DEFAULT_BRANCH_DEMO}"], cwd=root).returncode == 0
        )
    return decide_repository(
        repo,
        expect_readwrite=os.environ.get("INFRAHUB_REPOSITORY_MODE") == "readwrite",
        workers=workers,
        remote_main=remote_main,
        remote_demo_main=remote_demo,
        trees_equal=trees_equal,
    )


def probe_shell_environment(env: Environment) -> Result:
    return decide_shell_environment(envfile.stale_credentials(os.environ, envfile.env_file(env.root)))


def probe_branches(env: Environment) -> Result:
    data = env.graphql("{ Branch { name is_default } }")
    if "Branch" not in data:
        msg = "Infrahub returned no branch list"
        raise Unavailable(msg)
    return decide_leftover_branches(data["Branch"] or [])


def probe_stuck_merges(env: Environment) -> Result:
    data = env.graphql(
        '{ CoreProposedChange(state__value: "merging") { edges { node { name { value } '
        "source_branch { value } state { updated_at } } } } }"
    )
    if "CoreProposedChange" not in data:
        msg = "Infrahub returned no proposed change list"
        raise Unavailable(msg)
    rows = [
        {
            "name": str(edge["node"]["name"]["value"]),
            "source_branch": str(edge["node"]["source_branch"]["value"]),
            "updated_at": str((edge["node"]["state"] or {}).get("updated_at") or ""),
        }
        for edge in data["CoreProposedChange"]["edges"]
    ]
    return decide_stuck_merges(rows, datetime.now(UTC))


def probe_stage_branch(env: Environment) -> Result:
    stage = "stage/internet-access"
    root = envfile.main_checkout(env.root)
    exists = _run(["git", "rev-parse", "--verify", "--quiet", stage], cwd=root).returncode == 0
    main_tip = _git(root, "rev-parse", "origin/main")
    merge_base = _git(root, "merge-base", "origin/main", stage) if exists else ""
    return decide_stage_branch(stage, exists, merge_base, main_tip)


def probe_picker(env: Environment) -> Result:
    """Ask the portal for the entries tagged `requestable`, from the branch desktop, as alice."""
    present = _run(["docker", "ps", "-q", "--filter", f"name={DESKTOP}"]).stdout.split()
    if not present:
        msg = f"{DESKTOP} is not running"
        raise Unavailable(msg)
    script = env.root / "scripts/portal/portal_signin.sh"
    _run(["docker", "cp", str(script), f"{DESKTOP}:{SIGNIN_REMOTE}"])
    _run(["docker", "exec", DESKTOP, "chmod", "+x", SIGNIN_REMOTE])
    command = (
        f'T=$({SIGNIN_REMOTE}); [ -n "$T" ] || exit 1; '
        'curl -s -H "Authorization: Bearer $T" --max-time 25 '
        f'"{PORTAL}/api/catalog/entities?filter=kind=resource,metadata.tags=requestable"'
    )
    proc = _run(["docker", "exec", DESKTOP, "sh", "-c", command], timeout=120)
    try:
        entities = json.loads(proc.stdout)
    except ValueError as exc:
        msg = "the portal did not answer the catalogue query"
        raise Unavailable(msg) from exc
    found = {str(e["metadata"]["name"]) for e in entities}
    expected = {n for n, requestable in expected_catalogue(env.root).items() if requestable}
    return decide_picker(found, expected)


def probe_claude_mcp_list(env: Environment) -> Result:
    if not _run(["which", "claude"]).stdout.strip():
        msg = "the claude command is not installed"
        raise Unavailable(msg)
    values = _env_values(env.root)
    child_env = {**os.environ, **values}
    try:
        proc = subprocess.run(
            ["claude", "mcp", "list"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            cwd=env.root,
            env=child_env,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        msg = "`claude mcp list` timed out"
        raise Unavailable(msg) from exc
    return decide_claude_mcp_list(proc.stdout, [MCP_SERVER_NAME])


def probe_mcp_config(env: Environment) -> Result:
    root = envfile.main_checkout(env.root)
    config = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    return decide_mcp_config(config, set(_env_values(env.root)), MCP_TOKEN_USERS)


def _kubeconfig(root: Path) -> Path:
    """The lab's kubeconfig: KUBECONFIG if set, else the one under the lab directory in the main checkout."""
    given = os.environ.get("KUBECONFIG")
    if given:
        return Path(given)
    lab = os.environ.get("OTTERNET_LAB_DIR")
    base = Path(lab) if lab else envfile.main_checkout(root) / "lab"
    return base / "k8s/.kubeconfig/kubeconfig.yaml"


def _kubectl(env: Environment, *args: str) -> str:
    """Run a read-only kubectl against the lab; a missing kubeconfig or an unreachable cluster is Unavailable."""
    kubeconfig = _kubeconfig(env.root)
    if not kubeconfig.is_file():
        msg = f"no kubeconfig at {kubeconfig} (the cluster is not up, or set KUBECONFIG)"
        raise Unavailable(msg)
    proc = _run(["kubectl", "--kubeconfig", str(kubeconfig), "--request-timeout=20s", *args], timeout=60)
    if proc.returncode != 0:
        msg = f"kubectl could not read the cluster: {proc.stderr.strip()[:200]}"
        raise Unavailable(msg)
    return proc.stdout


def probe_observability_namespaces(env: Environment) -> Result:
    out = _kubectl(env, "get", "namespace", "-o", 'go-template={{range .items}}{{.metadata.name}}{{"\\n"}}{{end}}')
    return decide_observability_namespaces(set(out.split()))


def probe_observability_secrets(env: Environment) -> Result:
    """Secret names and key names only: the template prints keys, so no value leaves kubectl."""
    template = 'go-template={{range .items}}{{.metadata.name}}={{range $k, $v := .data}}{{$k}},{{end}}{{"\\n"}}{{end}}'
    found: dict[str, dict[str, set[str]]] = {}
    for namespace in OBSERVABILITY_SECRETS:
        out = _kubectl(env, "-n", namespace, "get", "secret", "-o", template)
        rows: dict[str, set[str]] = {}
        for line in out.splitlines():
            secret, _, keys = line.partition("=")
            if secret:
                rows[secret] = {k for k in keys.split(",") if k}
        found[namespace] = rows
    return decide_observability_secrets(found)


def probe_grafana_pod(env: Environment) -> Result:
    template = (
        "go-template={{range .items}}{{.metadata.name}} {{.status.phase}} "
        "{{range .status.containerStatuses}}{{if .state.waiting}}{{.state.waiting.reason}},{{end}}{{end}}"
        "{{range .status.initContainerStatuses}}{{if .state.waiting}}{{.state.waiting.reason}},{{end}}{{end}}"
        '{{"\\n"}}{{end}}'
    )
    out = _kubectl(env, "-n", "otternet-metrics", "get", "pod", "-l", GRAFANA_SELECTOR, "-o", template)
    pods = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            reasons = [x for x in (parts[2].split(",") if len(parts) > 2 else []) if x]
            pods.append((parts[0], parts[1], reasons))
    return decide_grafana_pod(pods)


CHECKS: tuple[tuple[str, Callable[[Environment], Result]], ...] = (
    ("application catalogue", probe_catalogue),
    ("triggers.yml objects", probe_triggers),
    ("menus", probe_menus),
    ("seeded applications", probe_seeded_apps),
    ("MCP server", probe_mcp_server),
    ("mcp-agent role", probe_agent_role),
    ("mcp-agent token", probe_agent_identity),
    ("Requester Access role", probe_requester_role),
    ("network-admin account", probe_network_admin),
    ("portal accounts", probe_portal_accounts),
    *((f"{u} MCP token", lambda env, u=u: probe_user_identity(env, u)) for u in MCP_TOKEN_USERS),
    ("alice proposed change", probe_alice_proposed_change),
    ("alice main write", probe_alice_main_write),
    ("repository", probe_repository),
    ("leftover branches", probe_branches),
    ("stuck merges", probe_stuck_merges),
    ("stage branch", probe_stage_branch),
    ("portal picker", probe_picker),
    ("observability namespaces", probe_observability_namespaces),
    ("observability Secrets", probe_observability_secrets),
    ("Grafana pod", probe_grafana_pod),
    (".mcp.json", probe_mcp_config),
    ("shell environment", probe_shell_environment),
    ("claude mcp list", probe_claude_mcp_list),
)


def run_checks(
    root: Path,
    checks: tuple[tuple[str, Callable[[Environment], Result]], ...] = CHECKS,
) -> list[Result]:
    """Run every check. One that cannot run is a SKIP with its reason, never a crash."""
    env = _env(root)
    results = []
    for name, probe in checks:
        try:
            results.append(probe(env))
        except Unavailable as exc:
            results.append(Result(name, Status.SKIP, str(exc)))
        except Exception as exc:  # noqa: BLE001 - a broken probe must not hide the others
            results.append(Result(name, Status.SKIP, f"probe error: {type(exc).__name__}: {exc}"))
    return results


def repository_environment_problems(environ: dict[str, str] | os._Environ[str]) -> list[str]:
    """What is wrong with the environment a bootstrap needs, before anything is destroyed.

    Every bootstrap needs `INFRAHUB_API_TOKEN`: the step that uploads the application payloads reads it from
    the environment and stops without it, five minutes in and after the teardown. A read-write stack needs the remote's URL, a token with
    write access, and Infrahub told to import the `demo/` branches; without the last, a demo branch pushed
    to the remote is never imported and the release waits until it times out.
    """
    problems = []
    if not environ.get("INFRAHUB_API_TOKEN"):
        problems.append(
            "INFRAHUB_API_TOKEN is not set (the token infrahubctl uses; for a local stack, INFRAHUB_INITIAL_ADMIN_TOKEN)"
        )
    if environ.get("INFRAHUB_REPOSITORY_MODE") != "readwrite":
        return problems
    if not environ.get("INFRAHUB_REPOSITORY_URL"):
        problems.append("INFRAHUB_REPOSITORY_MODE=readwrite needs INFRAHUB_REPOSITORY_URL")
    if not environ.get("NFD_GITHUB_TOKEN"):
        problems.append("INFRAHUB_REPOSITORY_MODE=readwrite needs NFD_GITHUB_TOKEN (write access to the remote)")
    if "demo/" not in environ.get("INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES", ""):
        problems.append('INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES must include "demo/.*", for example \'["demo/.*"]\'')
    return problems


def human_steps(root: Path) -> list[str]:
    """What a person still has to do. Names variables, never values."""
    variables = [token_var(u) for u in MCP_TOKEN_USERS]
    env_file = envfile.env_file(root)
    return [
        f"Start Claude Code from a shell that has loaded {env_file}: `cd {envfile.main_checkout(root)} && set -a; source .env; set +a; claude`.",
        f"That file holds {', '.join(variables)}; .mcp.json sends it as the Bearer header, so Claude Code acts as alice. Do not print or commit it.",
        "Approve the otternet-infrahub server the first time Claude Code asks.",
        f"To edit network data and merge a proposed change, sign in to the Infrahub UI as `{NETWORK_ADMIN}` "
        f"with the password in {env_file} (variable {NETWORK_ADMIN_PASSWORD_VAR}; do not print or commit it). "
        "This is a local account, not a Dex sign-in, and it is not a Super Administrator.",
    ]


def render_summary(results: list[Result], root: Path) -> str:
    """The readiness summary: one line per check, the count, and what a person still has to do."""
    lines = [r.render() for r in results]
    counts = {s: sum(1 for r in results if r.status is s) for s in Status}
    lines.extend(["", ", ".join(f"{counts[s]} {s.value}" for s in Status), "", "What you still have to do:"])
    lines += [f"  - {step}" for step in human_steps(root)]
    return "\n".join(lines)


def exit_code(results: list[Result]) -> int:
    return 1 if any(r.status is Status.FAIL for r in results) else 0
