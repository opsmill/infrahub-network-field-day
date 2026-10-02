"""`invoke doctor`: check the development environment for the known quiet failures.

Every check here comes from an incident that failed without saying so. They are
split in two on purpose:

* **decisions** (`decide_*`, `parse_*`) are pure: they take plain data and return
  a `Result`. They are what `tests/unit/test_doctor.py` pins, with a healthy and a
  failing fixture side by side, because an empty result is only evidence when a
  non-empty one is proven beside it.
* **probes** (`probe_*`) do the I/O (docker, git, pgrep, GraphQL) and hand the
  result to a decision. A probe that cannot reach what it needs raises `Unavailable`
  and the runner turns that into `SKIP: <reason>`; no check crashes the command
  because the stack is down.

Host-side only. Nothing that runs in the Infrahub image imports this.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess  # noqa: S404 - fixed-argv calls, never a shell string
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable

# A stale image is a nuisance for a few minutes and a wrong reconciler after that.
IMAGE_STALE_WARN_SECONDS = 0
IMAGE_STALE_FAIL_SECONDS = 24 * 3600

BRIDGE = "br-otter-tool"
RECONCILER_SERVICE = "deployment-reconciler"
RECONCILE_SCRIPT = "scripts/reconcile.py"


class Status(StrEnum):
    PASS = "PASS"  # noqa: S105
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class Result:
    name: str
    status: Status
    detail: str = ""
    fix: str = ""

    def render(self) -> str:
        line = f"{self.status.value:<5} {self.name}"
        if self.detail:
            line += f": {self.detail}"
        if self.fix and self.status in (Status.WARN, Status.FAIL):
            line += f"\n      -> {self.fix}"
        return line


class Unavailable(Exception):  # noqa: N818 - a signal, not an error
    """What a probe needs is not there (stack down, tool missing); the check is skipped."""


# --------------------------------------------------------------------------- decisions


def parse_timestamp(value: str) -> datetime:
    """An RFC 3339 timestamp as docker or git prints it, to an aware UTC datetime."""
    text = value.strip()
    if not text:
        msg = "empty timestamp"
        raise ValueError(msg)
    text = text.replace("Z", "+00:00")
    # Docker prints nanoseconds; datetime accepts at most microseconds.
    text = re.sub(r"(\.\d{6})\d+", r"\1", text)
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


# The reconciler never imports the doctor, so a change to it does not make the image stale.
IMAGE_PATH_EXCLUDES = (":(exclude)src/solution_arista_avd/doctor.py",)


def decide_image_staleness(image_created: datetime, newest_source_commit: datetime) -> Result:
    """The reconciler runs the IMAGE's installed copy of the package, not the bind mount."""
    name = "reconciler image is current"
    behind = (newest_source_commit - image_created).total_seconds()
    if behind <= IMAGE_STALE_WARN_SECONDS:
        return Result(name, Status.PASS, f"image built {image_created:%Y-%m-%d %H:%M}Z, after the newest source commit")
    detail = (
        f"image built {image_created:%Y-%m-%d %H:%M}Z, newest pyproject.toml/uv.lock/src commit "
        f"{newest_source_commit:%Y-%m-%d %H:%M}Z ({behind / 3600:.1f}h newer)"
    )
    status = Status.FAIL if behind > IMAGE_STALE_FAIL_SECONDS else Status.WARN
    return Result(name, status, detail, "run `uv run invoke build`, then recreate the deployment-reconciler container")


def parse_pgrep(output: str, own_pid: int | None = None) -> list[int]:
    """PIDs from `pgrep -af scripts/reconcile.py`, excluding pgrep itself, shells quoting it, and `own_pid`."""
    pids: list[int] = []
    for line in output.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        pid, cmdline = int(parts[0]), parts[1]
        if pid == own_pid or cmdline.startswith(("pgrep", "tini")):
            continue
        if RECONCILE_SCRIPT not in cmdline:
            continue
        # A `sh -c "... scripts/reconcile.py"` wrapper around the real process, or this command's own shell.
        if re.match(r"(\S*/)?(ba|z|da)?sh\s+-c\b", cmdline):
            continue
        pids.append(pid)
    return pids


def decide_reconcile_processes(host_pids: list[int], container_running: bool) -> Result:
    """More than one reconciler is two writers racing over the same devices."""
    name = "exactly one reconcile loop"
    total = len(host_pids) + (1 if container_running else 0)
    where = []
    if host_pids:
        where.append("host PIDs " + ", ".join(str(p) for p in host_pids))
    if container_running:
        where.append("container deployment-reconciler")
    if total <= 1:
        return Result(name, Status.PASS, where[0] if where else "no reconciler running")
    return Result(
        name,
        Status.FAIL,
        f"{total} running: " + "; ".join(where),
        "kill the strays (`kill <pid>`); `pkill -f 'invoke reconcile'` does not reach the child script",
    )


_FIELD_WITH_ARGS = re.compile(r"^(\s*\w+)\((.*)\)(:.*)$")
_IMPLEMENTS = re.compile(r"^(.*? implements )(.+?)( \{)$")


def normalise_schema(text: str) -> list[str]:
    """The SDL as a sorted list of lines with each field's arguments sorted.

    Measured: two exports of the same loaded schema differ only in the ORDER of
    attributes (so of field arguments), of fields inside a type, and of the
    interfaces in `type X implements A & B`, depending on the order the server
    loaded them in. The exporter is deterministic for a given
    load, not across loads, so comparing bytes reports drift that is not there.
    """
    lines = []
    for raw in text.splitlines():
        implements = _IMPLEMENTS.match(raw)
        if implements:
            raw = f"{implements.group(1)}{' & '.join(sorted(implements.group(2).split(' & ')))}{implements.group(3)}"  # noqa: PLW2901
        match = _FIELD_WITH_ARGS.match(raw)
        if match:
            args = ", ".join(sorted(match.group(2).split(", ")))
            raw = f"{match.group(1)}({args}){match.group(3)}"  # noqa: PLW2901
        lines.append(raw)
    return sorted(lines)


def decide_schema_freshness(committed: str, exported: str) -> Result:
    name = "schema.graphql matches the loaded schema"
    if normalise_schema(committed) == normalise_schema(exported):
        return Result(name, Status.PASS)
    return Result(
        name,
        Status.WARN,
        "schema.graphql differs from the schema Infrahub has loaded",
        "uv run infrahubctl graphql export-schema --destination schema.graphql "
        "(then regenerate return types for any .gql that changed)",
    )


def _is_ancestor_hint(commit: str) -> str:
    return (
        f"recovery (AGENTS.md, Repository sync): `git merge -s ours {commit}` on main keeps the tree and records the "
        "orphan as a parent so the clone fast-forwards; or re-clone the CoreRepository (loses artifact history)"
    )


def decide_repository_sync(
    repositories: list[dict[str, str]],
    is_ancestor: Callable[[str], bool | None],
) -> Result:
    """`repositories` rows: name, commit, sync_status, operational_status."""
    name = "repository sync"
    if not repositories:
        return Result(name, Status.FAIL, "no CoreRepository is registered", "uv run invoke load")
    problems: list[str] = []
    fix = ""
    for repo in repositories:
        rname = repo.get("name", "?")
        sync = repo.get("sync_status", "")
        oper = repo.get("operational_status", "")
        commit = repo.get("commit", "")
        if sync != "in-sync":
            problems.append(f"{rname}: sync_status {sync or 'unknown'}")
            fix = (
                "an error-import is not retried until the commit changes: make a new commit on main "
                "(AGENTS.md, Repository sync); check `docker compose logs task-worker --since 10m | grep -i 'Failed to synchronize'`"
            )
        if oper not in ("online", ""):
            problems.append(f"{rname}: operational_status {oper}")
        if commit:
            ancestor = is_ancestor(commit)
            if ancestor is False:
                problems.append(f"{rname}: stored commit {commit[:12]} is not an ancestor of HEAD (diverged history)")
                fix = _is_ancestor_hint(commit)
    if problems:
        return Result(name, Status.FAIL, "; ".join(problems), fix)
    return Result(name, Status.PASS, ", ".join(f"{r['name']} in-sync at {r['commit'][:12]}" for r in repositories))


def dangling_generator_instances(rows: list[dict[str, Any]]) -> list[str]:
    """Names of CoreGeneratorInstance rows whose `object` peer no longer resolves."""
    dangling = []
    for row in rows:
        node = ((row.get("object") or {}).get("node")) or {}
        if not node.get("id"):
            label = (row.get("name") or {}).get("value") or row.get("id") or "?"
            dangling.append(str(label))
    return sorted(dangling)


def decide_dangling_instances(rows: list[dict[str, Any]]) -> Result:
    name = "no dangling generator instances"
    dangling = dangling_generator_instances(rows)
    if not dangling:
        return Result(name, Status.PASS, f"{len(rows)} instances, all resolve")
    return Result(
        name,
        Status.FAIL,
        f"{len(dangling)} instance(s) whose object is gone: " + ", ".join(dangling),
        "delete each CoreGeneratorInstance (and its empty CoreGeneratorGroup, description `name: <service>`); "
        "until then the generator's validator is red on every proposed change (AGENTS.md, Services expand on their branch)",
    )


def stray_synced_branches(branches: list[dict[str, Any]]) -> list[str]:
    return sorted(b["name"] for b in branches if not b.get("is_default") and b.get("sync_with_git"))


def decide_branches(branches: list[dict[str, Any]]) -> Result:
    name = "no non-default branch syncs with git"
    strays = stray_synced_branches(branches)
    if not strays:
        return Result(name, Status.PASS, f"{len(branches)} branch(es)")
    return Result(
        name,
        Status.WARN,
        "sync_with_git is true on: " + ", ".join(strays),
        "each such branch registers ~171 Prefect automations and imports the repository; "
        '`infrahubctl branch delete <name>` (check INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES is ["main"])',
    )


def decide_bridge(bridge_exists: bool, lab_expected: bool) -> Result:
    name = f"{BRIDGE} bridge exists"
    if bridge_exists:
        return Result(name, Status.PASS)
    if not lab_expected:
        return Result(name, Status.SKIP, "the lab is not running, so the bridge is not needed yet")
    return Result(
        name,
        Status.WARN,
        "the lab is up but the bridge is missing (it does not survive a reboot)",
        "lab/scripts/tooling-bridge.sh (ContainerLab refuses to deploy without it)",
    )


# ------------------------------------------------------------------------------ probes


def _run(argv: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    if shutil.which(argv[0]) is None:
        msg = f"{argv[0]} is not installed"
        raise Unavailable(msg)
    try:
        return subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, check=False, cwd=cwd, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"`{' '.join(argv[:3])}` timed out"
        raise Unavailable(msg) from exc


@dataclass
class Environment:
    """What the probes need to know about where they run."""

    root: Path
    address: str = field(default_factory=lambda: os.environ.get("INFRAHUB_ADDRESS", "http://localhost:8000"))
    token: str = field(default_factory=lambda: os.environ.get("INFRAHUB_API_TOKEN", ""))

    def graphql(self, query: str) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.address}/graphql",
                json={"query": query},
                headers={"X-INFRAHUB-KEY": self.token},
                timeout=30,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            msg = f"Infrahub at {self.address} did not answer ({type(exc).__name__})"
            raise Unavailable(msg) from exc
        if body.get("errors") and not body.get("data"):
            msg = f"Infrahub refused the query: {body['errors'][0].get('message', 'unknown error')}"
            raise Unavailable(msg)
        return body.get("data") or {}


def _reconciler_container() -> str | None:
    proc = _run(["docker", "ps", "-q", "--filter", f"label=com.docker.compose.service={RECONCILER_SERVICE}"])
    if proc.returncode != 0:
        msg = "docker is not answering"
        raise Unavailable(msg)
    ids = proc.stdout.split()
    return ids[0] if ids else None


def probe_image_staleness(env: Environment) -> Result:
    container = _reconciler_container()
    if container is None:
        msg = f"the {RECONCILER_SERVICE} container is not running (profile `reconcile`)"
        raise Unavailable(msg)
    image = _run(["docker", "inspect", "--format", "{{.Image}}", container]).stdout.strip()
    created = _run(["docker", "image", "inspect", "--format", "{{.Created}}", image]).stdout.strip()
    if not created:
        msg = "could not read the image's build time"
        raise Unavailable(msg)
    log = _run(
        ["git", "log", "-1", "--format=%cI", "--", "pyproject.toml", "uv.lock", "src/", *IMAGE_PATH_EXCLUDES],
        cwd=env.root,
    )
    if not log.stdout.strip():
        msg = "git reports no commit touching pyproject.toml, uv.lock or src/"
        raise Unavailable(msg)
    return decide_image_staleness(parse_timestamp(created), parse_timestamp(log.stdout))


def _in_container(pid: int) -> bool:
    try:
        cgroup = Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8")
    except OSError:
        return False
    return any(marker in cgroup for marker in ("docker", "containerd", "kubepods"))


def probe_reconcile_processes(env: Environment) -> Result:  # noqa: ARG001
    proc = _run(["pgrep", "-af", RECONCILE_SCRIPT])
    # The container's own process is visible in the host's process table; it is the container, not a stray.
    host = [pid for pid in parse_pgrep(proc.stdout, own_pid=os.getpid()) if not _in_container(pid)]
    try:
        container = _reconciler_container() is not None
    except Unavailable:
        container = False
    return decide_reconcile_processes(host, container)


def probe_schema_freshness(env: Environment) -> Result:
    committed_path = env.root / "schema.graphql"
    if not committed_path.exists():
        msg = "no schema.graphql is committed"
        raise Unavailable(msg)
    env.graphql("{ InfrahubInfo { version } }")  # fail fast, as SKIP, when the stack is down
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "schema.graphql"
        # `infrahubctl graphql export-schema` takes no --branch: it always exports main's.
        proc = _run(["infrahubctl", "graphql", "export-schema", "--destination", str(target)], cwd=env.root)
        if proc.returncode != 0 or not target.exists():
            msg = "infrahubctl could not export the schema"
            raise Unavailable(msg)
        exported = target.read_text(encoding="utf-8")
    return decide_schema_freshness(committed_path.read_text(encoding="utf-8"), exported)


# The generic, so a read-only repository (the demo's) is seen as well as a CoreRepository;
# `commit` lives on each kind rather than on the generic.
REPOSITORY_QUERY = (
    "{ CoreGenericRepository { edges { node { name { value } sync_status { value } operational_status { value } "
    "... on CoreRepository { commit { value } } ... on CoreReadOnlyRepository { commit { value } } } } } }"
)


def parse_repositories(data: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for edge in (data.get("CoreGenericRepository") or {}).get("edges") or []:
        node = edge["node"]
        rows.append(
            {
                key: str((node.get(key) or {}).get("value") or "")
                for key in ("name", "commit", "sync_status", "operational_status")
            }
        )
    return rows


def probe_repository_sync(env: Environment) -> Result:
    repositories = parse_repositories(env.graphql(REPOSITORY_QUERY))

    def is_ancestor(commit: str) -> bool | None:
        proc = _run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=env.root)
        # 1 is "not an ancestor"; anything else (128: unknown object) is a clone that cannot see the commit.
        if proc.returncode == 0:
            return True
        # A read-only repository tracking a staged demo branch imports a commit that is on a branch
        # rather than on HEAD. It is not diverged history while some ref here contains it.
        held = _run(["git", "for-each-ref", "--contains", commit, "--count=1", "refs/"], cwd=env.root)
        return held.returncode == 0 and bool(held.stdout.strip())

    return decide_repository_sync(repositories, is_ancestor)


def probe_dangling_instances(env: Environment) -> Result:
    data = env.graphql("{ CoreGeneratorInstance { edges { node { id name { value } object { node { id } } } } } }")
    rows = [edge["node"] for edge in (data.get("CoreGeneratorInstance") or {}).get("edges") or []]
    return decide_dangling_instances(rows)


def probe_branches(env: Environment) -> Result:
    data = env.graphql("{ Branch { name is_default sync_with_git } }")
    if "Branch" not in data:
        msg = "Infrahub returned no branch list"
        raise Unavailable(msg)
    return decide_branches(data["Branch"] or [])


def probe_bridge(env: Environment) -> Result:  # noqa: ARG001
    proc = _run(["ip", "link", "show", BRIDGE])
    containers = _run(["docker", "ps", "-q", "--filter", "name=clab-otternet-"])
    lab_expected = bool(containers.stdout.split())
    return decide_bridge(proc.returncode == 0, lab_expected)


CHECKS: tuple[tuple[str, Callable[[Environment], Result]], ...] = (
    ("reconciler image is current", probe_image_staleness),
    ("exactly one reconcile loop", probe_reconcile_processes),
    ("schema.graphql matches the loaded schema", probe_schema_freshness),
    ("repository sync", probe_repository_sync),
    ("no dangling generator instances", probe_dangling_instances),
    ("no non-default branch syncs with git", probe_branches),
    (f"{BRIDGE} bridge exists", probe_bridge),
)


def run_checks(
    env: Environment,
    checks: tuple[tuple[str, Callable[[Environment], Result]], ...] = CHECKS,
) -> list[Result]:
    """Run every check; one that cannot run is a SKIP with its reason, never a crash."""
    results = []
    for name, probe in checks:
        try:
            results.append(probe(env))
        except Unavailable as exc:
            results.append(Result(name, Status.SKIP, str(exc)))
        except Exception as exc:  # noqa: BLE001 - a broken probe must not hide the others
            results.append(Result(name, Status.SKIP, f"probe error: {type(exc).__name__}: {exc}"))
    return results


def exit_code(results: list[Result]) -> int:
    return 1 if any(r.status is Status.FAIL for r in results) else 0


def summary(results: list[Result]) -> str:
    counts = {s: sum(1 for r in results if r.status is s) for s in Status}
    return ", ".join(f"{counts[s]} {s.value}" for s in Status)
