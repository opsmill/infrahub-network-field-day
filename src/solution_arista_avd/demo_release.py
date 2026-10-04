"""`invoke demo-release`: bring a staged capability branch into Infrahub on cue.

The only live action is a push (or a branch rename on the remote); the rest has to
follow on its own. Five facts shape it:

* **Read-write** (``INFRAHUB_REPOSITORY_MODE=readwrite``): the repository is a
  ``CoreRepository`` with ``default_branch: demo-main``. Infrahub imports remote
  branches matching ``INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES`` as Infrahub branches
  by itself, and a merge pushes to ``demo-main``: Infrahub maps its own ``main`` to
  ``default_branch`` (``_get_mapped_remote_branch``), so the real ``main`` is never
  written. The push needs a write credential.
* **Read-only** (the default): the repository is a ``CoreReadOnlyRepository``
  tracking one ``ref``. No branch is created from Git and nothing is pushed, but
  someone has to set the ref on an Infrahub branch; merging then moves it on ``main``.
* The prepared work lives on ``stage/<name>``, which never matches the filter, so
  it can sit on the remote unsynced. Pushing it to ``demo/<name>-<run>`` is the trigger.
* The staged branch's ``.infrahub.yml`` declares ``schemas:`` and ``objects:``, so the
  repository import carries the schema and the data as well as the code. ``main``
  declares neither, so nothing else loads them.
* A commit Infrahub has pulled is never rewritten, so every release uses a new
  ``-<run>`` suffix, and ``demo-main`` is reset forward (a commit with the baseline's
  tree), not by deleting it.

Only pure functions live here; ``tasks.py`` does the I/O. Host-side only.
"""

from __future__ import annotations

import json
import re

STAGE_PREFIX = "stage/"
DEMO_PREFIX = "demo/"
DEFAULT_DEMO_BRANCH = "demo-main"
MODES = ("readonly", "readwrite")
# Remote branches Infrahub should import as Infrahub branches in read-write mode.
# `main` is deliberately absent: the repository's default branch is `demo-main`, which
# Infrahub already treats as its own `main`.
DEMO_IMPORT_FILTER = json.dumps([f"{DEMO_PREFIX}.*"], separators=(",", ":"))

# Only characters that are safe in a Git ref, an Infrahub branch name and a shell word.
_SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


class DemoReleaseError(ValueError):
    """A release that cannot be built from the arguments it was given."""


def _checked(name: str) -> str:
    if not _SAFE_NAME.fullmatch(name):
        msg = f"{name!r} is not a usable demo name: lowercase letters, digits and hyphens, starting with one"
        raise DemoReleaseError(msg)
    return name


def stage_branch(name: str) -> str:
    """The local (and optionally remote) branch holding the prepared work."""
    return f"{STAGE_PREFIX}{_checked(name)}"


def demo_branch(name: str, run: int) -> str:
    """The remote branch whose creation makes Infrahub import the work."""
    if run < 1:
        msg = f"run must be 1 or more, got {run}"
        raise DemoReleaseError(msg)
    return f"{DEMO_PREFIX}{_checked(name)}-{run}"


def refspec(name: str, run: int) -> str:
    """``git push origin <refspec>``: the staged branch, published under the synced name."""
    return f"{stage_branch(name)}:{demo_branch(name, run)}"


def render_repository(
    url: str,
    *,
    mode: str = "readonly",
    ref: str = "main",
    default_branch: str = DEFAULT_DEMO_BRANCH,
    repository_name: str = "test-repository",
    credential: str | None = None,
) -> str:
    """The repository object file for a remote, as ``infrahubctl object load`` reads it.

    ``credential`` is the name of a ``CoreCredential`` that already exists on the
    stack. The secret itself is never written here.
    """
    if mode not in MODES:
        msg = f"mode must be one of {MODES}, got {mode!r}"
        raise DemoReleaseError(msg)
    if not url.startswith(("https://", "http://", "ssh://", "git@")):
        msg = f"{url!r} does not look like a Git remote URL"
        raise DemoReleaseError(msg)
    read_write = mode == "readwrite"
    if read_write and not credential:
        msg = "a read-write repository pushes, so it needs a credential"
        raise DemoReleaseError(msg)
    if not (default_branch if read_write else ref).strip():
        msg = "a default branch (read-write) or a ref (read-only) is required"
        raise DemoReleaseError(msg)
    lines = [
        "---",
        "apiVersion: infrahub.app/v1",
        "kind: Object",
        "spec:",
        f"  kind: {'CoreRepository' if read_write else 'CoreReadOnlyRepository'}",
        "  data:",
        f"    - name: {repository_name}",
        f"      location: {json.dumps(url)}",
        f"      default_branch: {json.dumps(default_branch)}" if read_write else f"      ref: {json.dumps(ref)}",
    ]
    if credential:
        lines.append(f"      credential: {json.dumps(credential)}")
    return "\n".join(lines) + "\n"


def render_credential(name: str, username: str, password: str) -> str:
    """A username and token credential object file, for the caller to load and delete."""
    return (
        "---\n"
        "apiVersion: infrahub.app/v1\n"
        "kind: Object\n"
        "spec:\n"
        "  kind: CorePasswordCredential\n"
        "  data:\n"
        f"    - name: {json.dumps(name)}\n"
        f"      username: {json.dumps(username)}\n"
        f"      password: {json.dumps(password)}\n"
    )


def proposed_change_mutation(source_branch: str, name: str, description: str) -> str:
    """The GraphQL that opens a proposed change into ``main``."""
    return (
        "mutation { CoreProposedChangeCreate(data: {"
        f" name: {{ value: {json.dumps(name)} }}"
        f" description: {{ value: {json.dumps(description)} }}"
        f" source_branch: {{ value: {json.dumps(source_branch)} }}"
        ' destination_branch: { value: "main" }'
        " }) { object { id } } }"
    )


def set_ref_mutation(repository_id: str, ref: str) -> str:
    """The GraphQL that points the read-only repository at another ref."""
    return (
        "mutation { CoreReadOnlyRepositoryUpdate(data: {"
        f" id: {json.dumps(repository_id)} ref: {{ value: {json.dumps(ref)} }}"
        " }) { ok } }"
    )


def absent_schema(namespace: str, name: str) -> str:
    """A schema file that marks one node absent: how a loaded kind is taken back out."""
    return (
        'version: "1.0"\n'
        "nodes:\n"
        f"  - name: {json.dumps(name)}\n"
        f"    namespace: {json.dumps(namespace)}\n"
        "    state: absent\n"
    )


def parse_patterns(raw: str) -> list[str]:
    """The JSON array ``INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES`` holds."""
    try:
        patterns = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES is not a JSON array: {raw!r}"
        raise DemoReleaseError(msg) from exc
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        msg = f"INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES is not a JSON array of strings: {raw!r}"
        raise DemoReleaseError(msg)
    return patterns


def is_imported(patterns: list[str], branch: str) -> bool:
    """Infrahub's own rule: a name or regex, tried with ``re.fullmatch``."""
    return any(re.fullmatch(pattern, branch) for pattern in patterns)


# Task states that mean Infrahub is still working on the branch.
ACTIVE_TASK_STATES = ("SCHEDULED", "PENDING", "RUNNING", "PAUSED", "CANCELLING")
# Task states that mean something on the branch went wrong.
FAILED_TASK_STATES = ("FAILED", "CRASHED")


def decide_settled(
    *,
    expected_commit: str,
    commit: str,
    sync_status: str,
    kind_present: bool,
    object_count: int,
    active_tasks: int,
    failed_tasks: list[str],
    require_capability: bool = True,
    workers_synced: bool = True,
) -> tuple[bool, str]:
    """Whether a released branch is fully imported, and if not, what it is still waiting for.

    A proposed change opened earlier judges a branch that is half there: its checks can
    pass over data that is not loaded yet. So "settled" needs all of: the pushed commit
    imported and in sync, the schema and the objects present (a repository import carries
    both), and no task still queued or running for the branch. A failed task is not a
    reason to keep waiting, so it is reported separately by the caller. A branch that
    takes the capability back out sets ``require_capability`` off: it has no schema or
    objects of its own to wait for.

    ``workers_synced`` is whether every task worker's own clone has the commit on its local
    branch. Measured: the graph records the import before the workers pull, and a merge made
    in that gap reads the stale local branch, merges a commit ``demo-main`` already holds,
    and changes nothing ("Already up to date"), so the data merges and the code does not.
    """
    if failed_tasks:
        return False, f"failed tasks on the branch: {', '.join(failed_tasks)}"
    if commit != expected_commit:
        return False, f"the import of {expected_commit[:10]} (the branch is at {commit[:10] or 'nothing'})"
    if sync_status != "in-sync":
        return False, f"the repository to be in-sync (it is {sync_status or 'unknown'})"
    if require_capability and not kind_present:
        return False, "the schema to load"
    if require_capability and object_count < 1:
        return False, "the objects to load"
    if not workers_synced:
        return False, "every task worker to pull the commit into its own clone"
    if active_tasks:
        return False, f"{active_tasks} task(s) still queued or running on the branch"
    return True, ""


# A validator is finished in this state; its conclusion says whether it passed.
VALIDATOR_DONE_STATE = "completed"
VALIDATOR_PASSED = "success"


def decide_validators(validators: list[dict[str, str]]) -> tuple[str, str]:
    """Where a proposed change's validators stand: ``("pending" | "failed" | "passed", detail)``.

    Each validator is ``{"label": ..., "state": ..., "conclusion": ..., "started_at": ...}``. A check
    run twice (the release asks again so the checks judge the final branch) leaves one validator per
    run under the same label; only the latest by ``started_at`` counts, because the first can have
    raced the import. Passed needs every one
    completed with a ``success`` conclusion, and at least one user-defined check among them
    (``Check: ...``): the integrity validators complete before the rest are even created, so
    "all complete" over that set alone means nothing. A failure is reported as soon as a
    completed validator has not succeeded, with the failing names, even while others still run,
    because nothing a later validator does can make it pass.
    """
    latest: dict[str, dict[str, str]] = {}
    for v in validators:
        seen = latest.get(v["label"])
        # An empty start time is a validator created and not begun yet: the newest of all.
        if seen is None or (v.get("started_at") or "~") >= (seen.get("started_at") or "~"):
            latest[v["label"]] = v
    validators = list(latest.values())
    failing = sorted(
        v["label"] for v in validators if v["state"] == VALIDATOR_DONE_STATE and v["conclusion"] != VALIDATOR_PASSED
    )
    if failing:
        return "failed", f"validators that did not pass: {', '.join(failing)}"
    running = sorted(v["label"] for v in validators if v["state"] != VALIDATOR_DONE_STATE)
    if running:
        return "pending", f"{len(running)} validator(s) still running: {', '.join(running[:3])}"
    if not any(v["label"].startswith("Check:") for v in validators):
        return "pending", "the user-defined checks to start"
    return "passed", f"{len(validators)} validators passed"


def worker_needs_realignment(current: str, default_branch: str, head: str, remote_tip: str) -> bool:
    """Whether a task worker's main worktree is off the default branch or behind or beside the remote's tip.

    Measured, with ``default_branch: demo-main``: a worker can keep its worktree on the clone's own default
    (``main``), and Infrahub's ``git push origin demo-main`` then fails there after the graph has merged.
    Separately, the periodic sync broadcasts one worker's local default branch as the commit every worker
    hard-resets to, so after a merge the pool converges on a stale commit; the next merge builds on it and
    its push is a silent non-fast-forward. Both are cured by every worker sitting on the default branch at
    the remote's tip, which is a fixed point of that broadcast.
    """
    return bool(current) and (current != default_branch or head != remote_tip)


def declare_schemas_and_objects(infrahub_yml: str, schema_files: list[str], object_files: list[str]) -> str:
    """``.infrahub.yml`` with ``schemas:`` and ``objects:`` sections appended.

    The staged branch declares them so one repository import carries the schema and the data as
    well as the code. ``main`` declares neither, so refusing a file that already has them keeps a
    staged branch from being built on top of one that was already staged.
    """
    if re.search(r"^(schemas|objects):", infrahub_yml, re.MULTILINE):
        msg = ".infrahub.yml already declares schemas or objects"
        raise DemoReleaseError(msg)
    if not schema_files or not object_files:
        msg = "both schema files and object files are required"
        raise DemoReleaseError(msg)
    lines = [
        "schemas:",
        *[f"  - {path}" for path in sorted(schema_files)],
        "objects:",
        *[f"  - {p}" for p in object_files],
    ]
    return infrahub_yml.rstrip("\n") + "\n" + "\n".join(lines) + "\n"
