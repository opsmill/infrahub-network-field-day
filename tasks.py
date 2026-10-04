import json
import os
import shlex
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from time import sleep
from typing import Any

import httpx
from invoke import Context, Exit, task

MAIN_DIRECTORY_PATH = Path(__file__).parent


def compose_root() -> Path:
    """The checkout whose compose files define the stack.

    From a normal checkout this is simply the repository. From a **git worktree**
    it is the main checkout, and the difference matters twice over:

      - `docker compose` derives its project name from the directory, so running
        it from a worktree makes a SECOND stack rather than acting on the running
        one. Both then want port 8000, and `invoke destroy` from a worktree
        silently does nothing because it is addressing a project that does not
        exist.
      - docker-compose.override.yml mounts `./:/upstream`, and Infrahub clones
        that path over git. A worktree's `.git` is a file pointing into the main
        repository, so a clone of it fails outright -- the worktree cannot be the
        repository Infrahub reads.

    `git rev-parse --git-common-dir` gives the shared git directory for both
    cases; its parent is the checkout to use.
    """
    from solution_arista_avd.envfile import main_checkout

    return main_checkout(MAIN_DIRECTORY_PATH)


def compose_cmd() -> str:
    """`docker compose` pinned to the stack's real project directory."""
    root = compose_root()
    return (
        f"docker compose --project-directory {shlex.quote(str(root))} "
        f"-f {shlex.quote(str(root / 'docker-compose.yml'))} "
        f"-f {shlex.quote(str(root / 'docker-compose.override.yml'))}"
    )


def infrahub_version() -> str:
    """The Infrahub release this project targets: the Dockerfile's `ARG` default.

    That line is the one source. The compose files keep a literal fallback for a
    bare `docker compose` run, and tests/unit/test_pinned_versions.py fails
    when any of those fallbacks disagrees with it.
    """
    dockerfile = compose_root() / "Dockerfile"
    for line in dockerfile.read_text(encoding="utf-8").splitlines():
        if line.startswith("ARG INFRAHUB_BASE_VERSION="):
            return line.split("=", 1)[1].strip()
    msg = f"{dockerfile} declares no ARG INFRAHUB_BASE_VERSION default"
    raise RuntimeError(msg)


# Every compose command below inherits this, so `invoke` builds and runs the
# version the Dockerfile names; an exported INFRAHUB_BASE_VERSION still wins.
os.environ.setdefault("INFRAHUB_BASE_VERSION", infrahub_version())

INFRAHUB_ADDRESS = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")

os.environ.setdefault("INFRAHUB_USERNAME", "admin")
os.environ.setdefault("INFRAHUB_PASSWORD", "infrahub")
os.environ.setdefault("INFRAHUB_ADDRESS", INFRAHUB_ADDRESS)

SEMAPHORE_URL = "http://localhost:3000"
SEMAPHORE_ADMIN = "admin"
SEMAPHORE_ADMIN_PASSWORD = "semaphore"  # noqa: S105
SEMAPHORE_PLAYBOOK_PATH = "/opt/semaphore/playbooks"

# The committed ContainerLab topology this project provisions, under lab/. The
# lab owns the topology -- which nodes exist and how they are wired -- and
# Infrahub owns their configuration.
LAB_TOPOLOGY = "otternet.clab.yml"

# Image variables the topology interpolates. ContainerLab runs under sudo, which
# scrubs the environment, so they have to be named to survive.
CLAB_ENV_PASSTHROUGH = (
    "OTTERNET_CEOS_IMAGE,OTTERNET_CEOS_MEMORY,OTTERNET_VSRX_IMAGE,OTTERNET_SRL_IMAGE,OTTERNET_GUACAMOLE_IMAGE"
)

# Markdown authored by this project. Vendored agent content (.agents, .claude,
# .specify), spec-kit process artifacts (specs/), and PyAVD-rendered output
# (lab/avd) are excluded in [tool.rumdl]; these paths are what remains.
# CLAUDE.md is omitted because it symlinks to AGENTS.md.
MARKDOWN_PATHS = "README.md AGENTS.md docs/ lab/README.md schemas/"

# Prose linting covers the published documentation tree only.
PROSE_PATHS = "docs/docs"

# Pinned so local runs match the CI job. Vale ships as a Go binary with no PyPI
# distribution, so it cannot be a uv dev dependency like the other linters.
VALE_VERSION = "3.17.1"


@task
def build(ctx: Context, cache: bool = True) -> None:
    """
    Build the docker image.
    """
    command = f"{compose_cmd()} build"
    if not cache:
        command += " --no-cache"
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(command, pty=True)


@task
def destroy(ctx: Context) -> None:
    """
    Stop and remove containers, networks, and volumes.

    Every profile is enabled so the services behind one -- the reconciler and the
    MCP server -- go too. Without it `down` skips them, and the MCP server, being
    on the compose network, keeps that network in use so it cannot be removed.
    """
    ctx.run(f"{compose_cmd()} --profile '*' down -v", pty=True)


class _SemaphoreClient:
    """Thin wrapper around httpx.Client for Semaphore API calls."""

    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=10)

    def wait_until_ready(self) -> None:
        delay = 2
        for attempt in range(1, 9):
            try:
                self._client.get("/api/ping")
                print("Semaphore is reachable.")
                return
            except httpx.HTTPError:
                print(f"Waiting for Semaphore (attempt {attempt}/8, retry in {delay}s)...")
                time.sleep(delay)
                delay = min(delay * 2, 60)
        print("ERROR: Semaphore not reachable after 8 attempts.")
        sys.exit(1)

    def login(self, admin: str, password: str) -> None:
        resp = self._client.post("/api/auth/login", json={"auth": admin, "password": password})
        if resp.status_code not in {200, 204}:
            print(f"ERROR: Login failed (status={resp.status_code}).")
            sys.exit(1)
        print("Authenticated successfully.")

    def find_or_create(
        self,
        list_url: str,
        create_url: str,
        name: str,
        payload: dict[str, object],
    ) -> int:
        """Find an existing resource by name or create it. Returns the resource id."""
        items: list[dict[str, object]] = self._client.get(list_url).json()
        for item in items:
            if item.get("name") == name:
                rid = int(str(item["id"]))
                print(f"  '{name}' already exists (id={rid}).")
                return rid

        resp = self._client.post(create_url, json=payload)
        resp.raise_for_status()
        rid = int(resp.json()["id"])
        print(f"  '{name}' created (id={rid}).")
        return rid


@task(name="init-semaphore")
def init_semaphore(
    context: Context,  # noqa: ARG001 - invoke passes it to every task
    url: str = SEMAPHORE_URL,
    admin: str = SEMAPHORE_ADMIN,
    password: str = SEMAPHORE_ADMIN_PASSWORD,
    playbook_path: str = SEMAPHORE_PLAYBOOK_PATH,
) -> None:
    """Seed Semaphore with the project, repository, inventory, and task template.

    Fully idempotent — each resource is looked up by name before creation.
    Safe to run multiple times; existing resources are reused.
    """
    print("=== Semaphore Init ===")

    api = _SemaphoreClient(url)
    api.wait_until_ready()
    api.login(admin, password)

    print("Project...")
    project_id = api.find_or_create(
        "/api/projects",
        "/api/projects",
        "Service Catalog",
        {"name": "Service Catalog", "alert": False, "max_parallel_tasks": 0},
    )

    print("Key store...")
    key_id = api.find_or_create(
        f"/api/project/{project_id}/keys",
        f"/api/project/{project_id}/keys",
        "None",
        {"name": "None", "type": "none", "project_id": project_id},
    )

    print("Repository...")
    repo_id = api.find_or_create(
        f"/api/project/{project_id}/repositories",
        f"/api/project/{project_id}/repositories",
        "Local",
        {
            "name": "Local",
            "project_id": project_id,
            "git_url": playbook_path,
            "git_branch": "",
            "ssh_key_id": key_id,
        },
    )

    print("Inventory...")
    inv_id = api.find_or_create(
        f"/api/project/{project_id}/inventory",
        f"/api/project/{project_id}/inventory",
        "Infrahub",
        {
            "name": "Infrahub",
            "project_id": project_id,
            "inventory": "inventory.yml",
            "type": "file",
            "ssh_key_id": key_id,
        },
    )

    print("Environment...")
    env_id = api.find_or_create(
        f"/api/project/{project_id}/environment",
        f"/api/project/{project_id}/environment",
        "Empty",
        {"name": "Empty", "project_id": project_id, "json": "{}", "env": "{}"},
    )

    print("Task template...")
    api.find_or_create(
        f"/api/project/{project_id}/templates",
        f"/api/project/{project_id}/templates",
        "Deploy",
        {
            "name": "Deploy",
            "project_id": project_id,
            "repository_id": repo_id,
            "inventory_id": inv_id,
            "environment_id": env_id,
            "playbook": "deploy.yml",
            "type": "task",
            "app": "ansible",
        },
    )

    print("=== Semaphore init complete ===")


def get_repository_sync_status(name: str) -> str | None:
    query = """
    query CheckRepoSync($name: String!) {
      CoreGenericRepository(name__value: $name) {
        edges {
          node {
            sync_status { value }
          }
        }
      }
    }
    """
    resp = httpx.post(
        f"{INFRAHUB_ADDRESS}/graphql",
        json={"query": query, "variables": {"name": name}},
        timeout=10,
    )
    data = resp.json()
    edges = data.get("data", {}).get("CoreGenericRepository", {}).get("edges", [])
    if not edges:
        return None
    return str(edges[0]["node"]["sync_status"]["value"])


def wait_for_repository_sync(name: str, timeout: int = 300, interval: int = 5) -> None:
    """Poll Infrahub until the named repository reaches 'in_sync' status."""
    elapsed = 0
    while elapsed < timeout:
        try:
            status = get_repository_sync_status(name)
            if status:
                print(f"Repository '{name}' sync_status: {status}")
                if status == "in-sync":
                    return
        except httpx.HTTPError as exc:
            print(f"Waiting for Infrahub API ({exc})")
        sleep(interval)
        elapsed += interval

    msg = f"Repository '{name}' did not reach 'in_sync' within {timeout}s"
    raise TimeoutError(msg)


@task(pre=[init_semaphore])
def load(ctx: Context) -> None:
    load_schema(ctx)
    load_menu(ctx)
    sleep(5)
    ctx.run("infrahubctl object load objects/")
    _load_repository(ctx)
    wait_for_repository_sync("test-repository")
    ctx.run("infrahubctl object load repository_checks.yml")
    ctx.run("infrahubctl object load triggers.yml")
    # Application payloads are CoreFileObject attachments, and `object load`
    # cannot upload file content. Without this an application loads with no
    # workload and its Crossplane artifact renders an empty manifests list.
    ctx.run("python scripts/seed_app_payloads.py --branch main")


def _load_repository(ctx: Context) -> None:
    """Register the repository: the checkout by default, a Git remote for the demo.

    `INFRAHUB_REPOSITORY_URL` registers the remote instead of `/upstream`, in the
    mode `INFRAHUB_REPOSITORY_MODE` names:

    * `readonly` (default): a read-only repository tracking `main`. Infrahub pushes
      nothing and creates no branch from Git; the demo moves its ref.
    * `readwrite`: a `CoreRepository` whose `default_branch` is `demo-main`. Infrahub
      imports `demo/*` branches by itself and a merge pushes to `demo-main`, never to
      the real `main`. The token in `NFD_GITHUB_TOKEN` is the credential and needs
      write access; it goes to Infrahub through a temporary file and is not kept.

    Choose the mode on a fresh stack. Infrahub refuses to change a repository's kind
    in place, and to delete one while trigger actions reference its generators. A
    read-write stack also needs `INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES` set to
    `["demo/.*"]` before `invoke start`.
    """
    url = os.environ.get("INFRAHUB_REPOSITORY_URL", "")
    if not url:
        ctx.run("infrahubctl object load repository.yml")
        return
    import tempfile

    from solution_arista_avd import demo_release as dr

    mode = os.environ.get("INFRAHUB_REPOSITORY_MODE", "readonly")
    token = os.environ.get("NFD_GITHUB_TOKEN", "")
    if mode == "readwrite":
        if not token:
            raise Exit(
                "INFRAHUB_REPOSITORY_MODE=readwrite needs NFD_GITHUB_TOKEN (write access to the remote).", code=1
            )
        _check_push_access(ctx, url, token)
        _ensure_remote_branch(ctx, dr.DEFAULT_DEMO_BRANCH)
    credential = "demo-remote" if mode == "readwrite" else None
    with tempfile.TemporaryDirectory() as tmp:
        if credential:
            cred_file = Path(tmp) / "credential.yml"
            cred_file.write_text(
                dr.render_credential(credential, os.environ.get("INFRAHUB_REPOSITORY_USER", "x-access-token"), token),
                encoding="utf-8",
            )
            cred_file.chmod(0o600)
            ctx.run(f"infrahubctl object load {shlex.quote(str(cred_file))}", pty=True)
        repo_file = Path(tmp) / "repository.yml"
        repo_file.write_text(
            dr.render_repository(
                url, mode=mode, ref=os.environ.get("INFRAHUB_REPOSITORY_REF", "main"), credential=credential
            ),
            encoding="utf-8",
        )
        print(f" - Repository 'test-repository' -> {url} ({mode})")
        ctx.run(f"infrahubctl object load {shlex.quote(str(repo_file))}", pty=True)


def _check_push_access(ctx: Context, url: str, token: str) -> None:
    """Fail now, not after a bootstrap, if `token` cannot push to `url`.

    Infrahub pushes the branches it syncs and the merges it makes, so a token that can
    only read lets the stack come up and then fail at the first merge. A dry-run push
    must authenticate for write, so it tells the two apart without creating anything.
    The token reaches git through GIT_ASKPASS reading the environment, not a command line.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        askpass = Path(tmp) / "askpass"
        askpass.write_text('#!/bin/sh\necho "$NFD_GITHUB_TOKEN"\n', encoding="utf-8")
        askpass.chmod(0o700)
        user = os.environ.get("INFRAHUB_REPOSITORY_USER", "x-access-token")
        with ctx.cd(MAIN_DIRECTORY_PATH):
            result = ctx.run(
                f"git -c credential.helper= -c credential.username={shlex.quote(user)} "
                f"push --dry-run {shlex.quote(url)} HEAD:refs/heads/demo-push-check",
                env={"GIT_ASKPASS": str(askpass), "GIT_TERMINAL_PROMPT": "0", "NFD_GITHUB_TOKEN": token},
                hide=True,
                warn=True,
            )
    if result is None or not result.ok:
        # A failed invoke Result is falsy, so test for None, not truthiness, to keep its stderr.
        detail = (result.stderr if result is not None else "").strip().splitlines()
        raise Exit(
            "NFD_GITHUB_TOKEN cannot push to the remote, and a read-write repository needs it to.\n"
            f"  git said: {detail[0] if detail else 'no output'}\n"
            "  A fine-grained token needs 'Contents: Read and write' on this repository, and the "
            "organisation may need to approve it. The username does not matter.",
            code=1,
        )


def _ensure_remote_branch(ctx: Context, branch: str) -> None:
    """Create `branch` on the remote at the tip of `main` if it is not there yet."""
    if _remote_tip(ctx, branch):
        return
    print(f" - Creating '{branch}' on the remote at the tip of main")
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run("git fetch --quiet origin main", pty=True)
        ctx.run(f"git push origin FETCH_HEAD:refs/heads/{shlex.quote(branch)}", pty=True)


# ---------------------------------------------------------------------------
# The demo: a staged capability branch arrives from the Git remote on cue.
# ---------------------------------------------------------------------------

DEMO_NAME = "internet-access"
# The object file the capability adds. `object load` upserts, so the rest of it is already there.
DEMO_OBJECTS = "objects/37_otternet_wan_services.yml"
# The kind it adds, so a rehearsal can take it back out.
DEMO_KIND = "ServiceInternetAccess"
DEMO_SCHEMA_NAMESPACE = "Service"
DEMO_SCHEMA_NAME = "InternetAccess"

_REPOSITORY_QUERY = (
    "{ CoreGenericRepository { edges { node { __typename id location { value } sync_status { value } "
    "... on CoreRepository { commit { value } default_branch { value } } "
    "... on CoreReadOnlyRepository { commit { value } ref { value } } } } } }"
)


def _wait_for(condition: Callable[[], bool], what: str, timeout: int, interval: int = 5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        print(f"   waiting for {what}", flush=True)
        sleep(interval)
    msg = f"Timed out after {timeout}s waiting for {what}"
    raise Exit(msg, code=1)


def _repository(branch: str = "") -> dict[str, str]:
    """The repository as `branch` sees it: kind, id, location, commit, sync status; empty if there is none."""
    edges = (_graphql(_REPOSITORY_QUERY, branch).get("CoreGenericRepository") or {}).get("edges") or []
    if not edges:
        return {}
    node = edges[0]["node"]
    value = lambda key: str((node.get(key) or {}).get("value") or "")  # noqa: E731
    return {
        "kind": str(node["__typename"]),
        "id": str(node["id"]),
        "location": value("location"),
        "default_branch": value("default_branch"),
        "commit": value("commit"),
        "ref": value("ref"),
        "sync_status": value("sync_status"),
    }


def _remote_tip(ctx: Context, branch: str) -> str:
    with ctx.cd(MAIN_DIRECTORY_PATH):
        result = ctx.run(f"git ls-remote origin {shlex.quote(f'refs/heads/{branch}')}", hide=True, warn=True)
    line = (result.stdout.strip().splitlines() or [""])[0] if result else ""
    return line.split()[0] if line else ""


def _branch_tasks(branch: str, states: tuple[str, ...]) -> list[str]:
    """Titles of the tasks on `branch` in any of `states`."""
    data = _graphql(
        f'{{ InfrahubTask(branch: "{branch}", state: [{", ".join(states)}], limit: 100) '
        "{ count edges { node { title } } } }"
    )
    edges = (data.get("InfrahubTask") or {}).get("edges") or []
    return [str(e["node"]["title"]) for e in edges]


def _workers_have_commit(repo_id: str, branch: str, expected: str) -> bool:
    """Whether every task worker's own clone has `expected` on its local `branch`.

    A merge reads the source branch's commit from the worker's local branch, which a periodic
    pull updates after the import is recorded in the graph. Merging inside that gap merges a
    stale commit that the default branch already holds, and nothing happens.
    """
    import subprocess  # noqa: S404 - fixed argv, no shell

    listing = subprocess.run(
        ["docker", "ps", "-q", "--filter", "label=com.docker.compose.service=task-worker"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    containers = listing.stdout.split()
    if not containers:
        return False
    clone = f"/opt/infrahub/git/{repo_id}/main"
    for container in containers:
        head = subprocess.run(  # noqa: S603
            ["docker", "exec", container, "git", "-C", clone, "rev-parse", f"refs/heads/{branch}"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
        )
        if head.returncode != 0 or head.stdout.strip() != expected:
            return False
    return True


def _branch_settled(branch: str, expected: str, require_capability: bool = True, repo_id: str = "") -> tuple[bool, str]:
    """Whether `branch` is fully imported (see `decide_settled`), and what it still waits for."""
    from solution_arista_avd import demo_release as dr

    current = _repository(branch)
    kind_present = bool(_graphql(f'{{ __type(name: "{DEMO_KIND}") {{ name }} }}', branch).get("__type"))
    objects = 0
    if kind_present:
        edges = (_graphql(f"{{ {DEMO_KIND} {{ edges {{ node {{ id }} }} }} }}", branch).get(DEMO_KIND) or {}).get(
            "edges"
        )
        objects = len(edges or [])
    return dr.decide_settled(
        expected_commit=expected,
        commit=current.get("commit", ""),
        sync_status=current.get("sync_status", ""),
        kind_present=kind_present,
        object_count=objects,
        active_tasks=len(_branch_tasks(branch, dr.ACTIVE_TASK_STATES)),
        failed_tasks=_branch_tasks(branch, dr.FAILED_TASK_STATES),
        require_capability=require_capability,
        workers_synced=_workers_have_commit(repo_id, branch, expected) if repo_id else True,
    )


def _wait_until_settled(
    branch: str, expected: str, timeout: int, require_capability: bool = True, repo_id: str = ""
) -> None:
    """Block until the branch is fully imported, on two polls in a row.

    One poll is not enough: the commit is recorded before the objects and definitions
    finish loading, and a task can queue the moment another completes.
    """
    deadline = time.monotonic() + timeout
    consecutive = 0
    while time.monotonic() < deadline:
        settled, waiting = _branch_settled(branch, expected, require_capability, repo_id)
        if not settled and waiting.startswith("failed tasks"):
            raise Exit(f"The import of '{branch}' failed: {waiting}", code=1)
        consecutive = consecutive + 1 if settled else 0
        if consecutive >= 2:
            print(f" - '{branch}' is fully imported", flush=True)
            return
        print(f"   waiting for {waiting or 'the branch to stay settled'}", flush=True)
        sleep(5)
    raise Exit(f"Timed out after {timeout}s waiting for '{branch}' to be fully imported", code=1)


def _validator_rows(pc_id: str) -> list[dict[str, str]]:
    """The proposed change's validators as `decide_validators` reads them; empty if Infrahub cannot say."""
    query = (
        '{ CoreProposedChange(ids: ["' + pc_id + '"]) { edges { node { validations { edges { node { '
        "display_label state { value } conclusion { value } started_at { value } } } } } } } }"
    )
    edges = (_graphql(query).get("CoreProposedChange") or {}).get("edges") or []
    if not edges:
        return []
    return [
        {
            "label": str(v["node"]["display_label"]),
            "state": str(v["node"]["state"]["value"]),
            "conclusion": str(v["node"]["conclusion"]["value"]),
            "started_at": str((v["node"].get("started_at") or {}).get("value") or ""),
        }
        for v in edges[0]["node"]["validations"]["edges"]
    ]


def _wait_for_validators(pc_id: str, timeout: int) -> None:
    """Block until every validator has finished and passed, stable on two polls; exit with the failing names."""
    from solution_arista_avd import demo_release as dr

    deadline = time.monotonic() + timeout
    consecutive = 0
    previous = ""
    while time.monotonic() < deadline:
        rows = _validator_rows(pc_id)
        state, detail = dr.decide_validators(rows)
        if state == "failed":
            raise Exit(f"The proposed change does not pass: {detail}", code=1)
        snapshot = repr(sorted((r["label"], r["state"], r["conclusion"]) for r in rows))
        consecutive = consecutive + 1 if state == "passed" and snapshot == previous else 0
        if consecutive >= 1:  # the same all-passed picture on two polls in a row
            print(f" - All {len(rows)} validators passed", flush=True)
            return
        previous = snapshot if state == "passed" else ""
        print(f"   waiting for the validators ({detail})", flush=True)
        sleep(10)
    raise Exit(f"Timed out after {timeout}s waiting for the validators of the proposed change", code=1)


def _regenerate_artifacts() -> None:
    """Re-render every artifact against what `main` now holds.

    Moving the code back does not always re-render: measured, a reset left the `isp-pe1`
    artifact (and then the router) carrying the capability it had just removed until the
    definitions were regenerated. The call is idempotent, and the reconciler pushes only
    what moved.
    """
    print(" - Regenerating artifacts", flush=True)
    for name, definition_id in sorted(_artifact_definition_ids().items()):
        response = httpx.post(
            f"{INFRAHUB_ADDRESS}/api/artifact/generate/{definition_id}",
            headers={"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")},
            timeout=300,
        )
        if response.status_code >= 400:
            print(f"   {name}: HTTP {response.status_code}", flush=True)


@task(help={"user": "Username to store (default INFRAHUB_REPOSITORY_USER, else x-access-token)"})
def demo_credential(ctx: Context, user: str = "") -> None:
    """Replace the stored `demo-remote` credential with the current NFD_GITHUB_TOKEN, in place.

    For a running read-write stack whose token turned out to be unable to push, or has
    expired: the repository keeps its link to the credential, so nothing is re-registered.
    """
    token = os.environ.get("NFD_GITHUB_TOKEN", "")
    if not token:
        raise Exit("NFD_GITHUB_TOKEN is not set. Run `source ~/.zshrc` first.", code=1)
    repo = _repository()
    if repo.get("kind") != "CoreRepository":
        raise Exit("The registered repository is not read-write; there is no push credential to replace.", code=1)
    _check_push_access(ctx, repo["location"], token)
    edges = (
        _graphql('{ CorePasswordCredential(name__value: "demo-remote") { edges { node { id } } } }').get(
            "CorePasswordCredential"
        )
        or {}
    ).get("edges") or []
    if not edges:
        raise Exit("No 'demo-remote' credential is registered.", code=1)
    username = user or os.environ.get("INFRAHUB_REPOSITORY_USER", "x-access-token")
    mutation = (
        "mutation($id: String!, $user: String!, $secret: String!) { CorePasswordCredentialUpdate(data: "
        "{id: $id, username: {value: $user}, password: {value: $secret}}) { ok } }"
    )
    response = httpx.post(
        f"{INFRAHUB_ADDRESS}/graphql",
        json={"query": mutation, "variables": {"id": edges[0]["node"]["id"], "user": username, "secret": token}},
        headers={"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")},
        timeout=30,
    )
    ok = ((response.json().get("data") or {}).get("CorePasswordCredentialUpdate") or {}).get("ok")
    if not ok:
        raise Exit("Infrahub refused to update the credential.", code=1)
    print("The demo-remote credential now holds the current token.")


def _copy_stage_onto_branch(ctx: Context, location: str, branch: str, stage: str) -> str:
    """Put the staged branch's tree on `branch` as one new commit and push it. Returns the new tip.

    Fetches the remote branch Infrahub just published, takes the tree of the local `stage`
    branch, commits it on top and pushes: a fast-forward, so nothing Infrahub holds is rewritten.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone"
        ctx.run(f"git clone --quiet --branch {shlex.quote(branch)} {shlex.quote(location)} {shlex.quote(str(clone))}")
        with ctx.cd(clone):
            ctx.run(f"git fetch --quiet {shlex.quote(str(MAIN_DIRECTORY_PATH))} {shlex.quote(f'refs/heads/{stage}')}")
            ctx.run("git read-tree -u --reset FETCH_HEAD")
            ctx.run(
                "git -c user.name=demo-release -c user.email=demo-release@example.invalid "
                f"commit --quiet --allow-empty -m {shlex.quote(f'Release {stage}')}"
            )
            ctx.run(f"git push --quiet origin {shlex.quote(branch)}")
            return ctx.run("git rev-parse HEAD", hide=True).stdout.strip()


@task(
    help={
        "name": f"Capability name; builds stage/<name> (default {DEMO_NAME})",
        "baseline": "The commit that removed the capability (default: found by its subject on main)",
        "objects": f"Object file the capability adds (default {DEMO_OBJECTS})",
        "force": "Replace an existing stage branch. It must never have been pushed under a name Infrahub follows",
    }
)
def demo_stage(
    ctx: Context, name: str = DEMO_NAME, baseline: str = "", objects: str = DEMO_OBJECTS, force: bool = False
) -> None:
    """Build stage/<name>: main with the capability put back, and the schema and object declared for import.

    It is the baseline's revert, so the implementation is the one that was removed, plus the
    `schemas:` and `objects:` sections the repository import needs to carry the schema and the data.
    It is a prepared implementation, not a Spec Kit run; replace the revert with one when there is one.
    """
    import tempfile

    from solution_arista_avd import demo_release as dr

    stage = dr.stage_branch(name)
    with ctx.cd(MAIN_DIRECTORY_PATH):
        exists = ctx.run(f"git rev-parse --verify --quiet {shlex.quote(stage)}", hide=True, warn=True).ok
        if exists and not force:
            raise Exit(f"'{stage}' exists. Use --force to rebuild it.", code=1)
        if not baseline:
            baseline = ctx.run(
                "git log main --no-merges --format=%H -n 1 --grep='remove the internet-access service kind to a baseline'",
                hide=True,
            ).stdout.strip()
        if not baseline:
            raise Exit("Could not find the baseline commit. Pass --baseline <sha>.", code=1)
        if exists:
            ctx.run(f"git branch -D {shlex.quote(stage)}", hide=True)
        ctx.run(f"git branch {shlex.quote(stage)} main", hide=True)
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "stage"
            ctx.run(f"git worktree add --quiet {shlex.quote(str(tree))} {shlex.quote(stage)}", hide=True)
            failure = ""
            try:
                with ctx.cd(tree):
                    reverted = ctx.run(f"git revert --no-edit {shlex.quote(baseline)}", hide=True, warn=True)
                    if not reverted.ok:
                        failure = f"Reverting {baseline[:10]} failed:\n{reverted.stderr}"
                    else:
                        files = [
                            f
                            for f in ctx.run("git ls-files schemas", hide=True).stdout.split()
                            if f.endswith((".yml", ".yaml"))
                        ]
                        config = tree / ".infrahub.yml"  # ctx.cd does not move Python's own cwd
                        config.write_text(
                            dr.declare_schemas_and_objects(config.read_text(encoding="utf-8"), files, [objects]),
                            encoding="utf-8",
                        )
                        ctx.run("git add .infrahub.yml", hide=True)
                        ctx.run(
                            "git -c user.name=demo-stage -c user.email=demo-stage@example.invalid commit --quiet "
                            "-m 'feat(stage): let the repository import carry the schema and the object'",
                            hide=True,
                        )
            finally:
                ctx.run(f"git worktree remove --force {shlex.quote(str(tree))}", hide=True, warn=True)
            if failure:
                ctx.run(f"git branch -D {shlex.quote(stage)}", hide=True, warn=True)
                raise Exit(failure, code=1)
        tip = ctx.run(f"git rev-parse --short {shlex.quote(stage)}", hide=True).stdout.strip()
    print(f"{stage} is at {tip}: main with {baseline[:10]} reverted, and the import declarations added.")


def _worker_branch_refs(repo_id: str) -> list[str]:
    """Every `demo/` branch ref in each task worker's clone; a deleted Infrahub branch leaves its ref there."""
    import subprocess  # noqa: S404 - fixed argv, no shell

    if not repo_id:
        return []
    listing = subprocess.run(
        ["docker", "ps", "-q", "--filter", "label=com.docker.compose.service=task-worker"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    refs: list[str] = []
    for container in listing.stdout.split():
        out = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "docker",
                "exec",
                container,
                "git",
                "-C",
                f"/opt/infrahub/git/{repo_id}/main",
                "for-each-ref",
                "--format=%(refname:short)",
                "refs/heads/demo",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        refs += out.stdout.split()
    return refs


def _ensure_workers_on_default_branch(repo: dict[str, str]) -> None:
    """Put every task worker's main worktree on the repository's default branch, or say why it cannot be.

    See `worker_needs_default_branch`: a merge pushes only from a worker on `demo-main`, so one on `main`
    makes a git-synced merge succeed in the graph and fail to reach the remote. The switch keeps the
    worktree's commit (`checkout -B`), so nothing Infrahub has merged there is lost.
    """
    import subprocess  # noqa: S404 - fixed argv, no shell

    from solution_arista_avd import demo_release as dr

    if repo.get("kind") != "CoreRepository" or not repo.get("id"):
        return
    default = repo["default_branch"]
    clone = f"/opt/infrahub/git/{repo['id']}/main"
    listing = subprocess.run(
        ["docker", "ps", "-q", "--filter", "label=com.docker.compose.service=task-worker"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    for container in listing.stdout.split():

        def git(*args: str, container: str = container) -> subprocess.CompletedProcess[str]:
            return subprocess.run(  # noqa: S603
                ["docker", "exec", container, "git", "-C", clone, *args],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
            )

        current = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if not dr.worker_needs_default_branch(current, default):
            continue
        if git("status", "--porcelain").stdout.strip():
            raise Exit(f"Worker {container[:12]} is on '{current}' with local changes; fix its clone by hand.", code=1)
        switched = git("checkout", "-q", "-B", default, "HEAD")
        if switched.returncode != 0:
            raise Exit(f"Could not put worker {container[:12]} on '{default}': {switched.stderr.strip()}", code=1)
        print(f" - Worker {container[:12]} was on '{current}'; it is on '{default}' now", flush=True)


def _taken_branch_names(ctx: Context, repo_id: str) -> list[str]:
    """Every name a release branch could collide with: Infrahub's branches, the remote's and the workers' refs."""
    with ctx.cd(MAIN_DIRECTORY_PATH):
        remote = ctx.run("git ls-remote --heads origin 'refs/heads/demo/*'", hide=True, warn=True)
    remote_names = [line.split("\t", 1)[1] for line in (remote.stdout.splitlines() if remote else []) if "\t" in line]
    return [*(_branches() or {}), *remote_names, *_worker_branch_refs(repo_id)]


@task(
    help={
        "name": f"Capability name; releases stage/<name> (default {DEMO_NAME})",
        "run": "Release number. 0 (the default) takes the next one no branch, remote ref or worker clone has used",
        "timeout": "Seconds to wait for the import (default 600)",
        "proposed_change": "Open the proposed change once the branch is imported (default true)",
    }
)
def demo_release(
    ctx: Context, name: str = DEMO_NAME, run: int = 0, timeout: int = 600, proposed_change: bool = True
) -> None:
    """Publish stage/<name> as demo/<name>-<run> and wait for Infrahub to have it, schema and data included.

    In read-write mode the push is the whole trigger and this task only watches; you can
    run the `git push` yourself, or rename the branch on the remote. In read-only mode
    Infrahub does not follow branches, so this also creates the Infrahub branch and sets
    the ref on it. Either way the staged `.infrahub.yml` carries the schema and the data.
    """
    from solution_arista_avd import demo_release as dr

    stage = dr.stage_branch(name)
    with ctx.cd(MAIN_DIRECTORY_PATH):
        tip = ctx.run(f"git rev-parse --verify {shlex.quote(stage)}", hide=True, warn=True)
    if not tip or not tip.ok:
        raise Exit(f"No local branch '{stage}'. Create it first; see docs/docs/demo-builder.md.", code=1)
    commit = tip.stdout.strip()
    repo = _repository()
    if not repo:
        raise Exit("No repository is registered. Bootstrap with INFRAHUB_REPOSITORY_URL set.", code=1)
    _ensure_workers_on_default_branch(repo)
    if run < 1:
        from solution_arista_avd import demo_restore as restore_module

        run = restore_module.next_run(name, _taken_branch_names(ctx, repo["id"]))
        print(f" - Using release number {run} (the next one no branch has used)", flush=True)
    demo = dr.demo_branch(name, run)
    read_write = repo["kind"] == "CoreRepository"
    if demo in (_branches() or {}):
        raise Exit(
            f"Infrahub already has '{demo}'. Use `--run {run + 1}`, or `invoke demo-reset --run {run}` first.", code=1
        )

    print(f"\n=== Releasing {stage} ({commit[:10]}) as {demo} ===", flush=True)
    if read_write:
        # A branch created with sync-with-git on is the only kind whose merge also merges git
        # (branches Infrahub creates from the remote have it off, and it cannot be changed).
        # Infrahub then creates the git branch itself and pushes it; the staged content goes
        # on top as one commit.
        print(f" - Creating the Infrahub branch '{demo}' with Sync with Git", flush=True)
        ctx.run(f"infrahubctl branch create {shlex.quote(demo)} --sync-with-git", pty=True)
        _wait_for(lambda: bool(_remote_tip(ctx, demo)), f"Infrahub to publish '{demo}' on the remote", timeout)
        print(" - Copying the staged content onto it and pushing", flush=True)
        expected = _copy_stage_onto_branch(ctx, repo["location"], demo, stage)
    else:
        with ctx.cd(MAIN_DIRECTORY_PATH):
            ctx.run(f"git push origin {shlex.quote(dr.refspec(name, run))}", pty=True)
        print(f" - Creating the Infrahub branch '{demo}' and setting the repository ref on it", flush=True)
        ctx.run(f"infrahubctl branch create {shlex.quote(demo)}", pty=True)
        _graphql(dr.set_ref_mutation(repo["id"], demo), demo)
        expected = commit

    print(" - Waiting for the branch to be fully imported", flush=True)
    _wait_until_settled(demo, expected, timeout, repo_id=repo["id"] if read_write else "")

    if not proposed_change:
        print(f"\nBranch '{demo}' is ready. Open a proposed change from it into main.")
        return
    mutation = dr.proposed_change_mutation(
        demo, f"Add {name}", f"Prepared implementation of {name}, released from {stage} at {commit[:10]}."
    )
    pc_id = ((_graphql(mutation).get("CoreProposedChangeCreate") or {}).get("object") or {}).get("id")
    if not pc_id:
        print(f"\nBranch '{demo}' is ready, but the proposed change could not be opened. Open it in the UI.")
        return
    # Creating one starts its validators at once; asking again makes them judge the final branch.
    _graphql(f'mutation {{ CoreProposedChangeRunCheck(data: {{id: "{pc_id}", check_type: ALL}}) {{ ok }} }}')
    print(" - Waiting for the proposed change's validators", flush=True)
    _wait_for_validators(pc_id, timeout)
    print(f"\nReady: {INFRAHUB_ADDRESS}/proposed-changes/{pc_id}")


def _restore_baseline_onto_branch(ctx: Context, location: str, branch: str, stage: str, default_branch: str) -> str:
    """Make `branch` hold the baseline's tree and descend from `default_branch`'s tip; push it.

    The baseline is the merge-base of `branch` and the local `stage` branch. Infrahub creates the
    git branch for a new Infrahub branch at the old baseline, not at the merged tip, and the
    baseline is already an ancestor of `default_branch`, so merging it would change nothing. The
    branch therefore takes a commit holding the baseline tree and then a `-s ours` merge of the
    default branch's tip, which keeps that tree and makes Infrahub's merge a fast-forward that
    really restores it. Returns the new tip.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone"
        ctx.run(f"git clone --quiet --branch {shlex.quote(branch)} {shlex.quote(location)} {shlex.quote(str(clone))}")
        with ctx.cd(clone):
            ctx.run(
                f"git fetch --quiet {shlex.quote(str(MAIN_DIRECTORY_PATH))} "
                f"{shlex.quote(f'refs/heads/{stage}:refs/tmp/stage')}"
            )
            ctx.run(f"git fetch --quiet origin {shlex.quote(f'refs/heads/{default_branch}:refs/tmp/default')}")
            base = ctx.run("git merge-base HEAD refs/tmp/stage", hide=True).stdout.strip()
            who = "git -c user.name=demo-reset -c user.email=demo-reset@example.invalid"
            if not ctx.run(f"git diff --quiet HEAD {shlex.quote(base)}", warn=True).ok:
                ctx.run(f"git read-tree -u --reset {shlex.quote(base)}")
                ctx.run(f"{who} commit --quiet -m {shlex.quote(f'Restore the baseline {base[:10]}')}")
            if not ctx.run("git merge-base --is-ancestor refs/tmp/default HEAD", warn=True).ok:
                ctx.run(
                    f"{who} merge --quiet -s ours --no-edit -m 'Take the merged tip, keep the baseline' refs/tmp/default"
                )
            ctx.run(f"git push --quiet origin {shlex.quote(branch)}")
            return ctx.run("git rev-parse HEAD", hide=True).stdout.strip()


def _delete_demo_branch(ctx: Context, branch: str) -> None:
    """Delete `branch` in Infrahub and on the remote, whichever of them still has it."""
    if branch in (_branches() or {}):
        ctx.run(f"infrahubctl branch delete {shlex.quote(branch)}", pty=True)
    else:
        print(f" - Infrahub has no '{branch}'")
    if _remote_tip(ctx, branch):
        with ctx.cd(MAIN_DIRECTORY_PATH):
            ctx.run(f"git push origin --delete {shlex.quote(branch)}", pty=True, warn=True)


def _code_is_merged(ctx: Context, default_branch: str, stage: str) -> bool:
    """Whether the default branch's tree differs from the baseline the staged branch was cut from.

    The kind existing is not enough: an interrupted reset can have removed the data and left the
    merged code, or the other way round. The baseline is the merge-base of the default branch and
    the local staged branch.
    """
    with ctx.cd(MAIN_DIRECTORY_PATH):
        fetched = ctx.run(
            f"git fetch --quiet origin {shlex.quote(f'+refs/heads/{default_branch}:refs/tmp/default')}",
            warn=True,
            hide=True,
        )
        if not fetched or not fetched.ok:
            return True
        base = ctx.run(
            f"git merge-base refs/tmp/default {shlex.quote(f'refs/heads/{stage}')}", hide=True, warn=True
        ).stdout.strip()
        return (
            bool(base)
            and not ctx.run(f"git diff --quiet {shlex.quote(base)} refs/tmp/default", warn=True, hide=True).ok
        )


def _take_capability_back_out(
    ctx: Context, repo_id: str, location: str, default_branch: str, name: str, run: int, timeout: int
) -> None:
    """Undo a merged release through Infrahub itself, with a branch whose merge restores the baseline.

    Infrahub never imports a commit pushed to `demo-main` from outside: the remote `main`
    shadows it ("Ignoring import of mismatched default branch"), and a stray commit there makes
    Infrahub's next merge push non-fast-forward. Its own merges are the path that works, so the
    reset is one: a branch with Sync with Git on, the baseline tree committed on it, the kind's
    data and schema node removed on it, then merged.
    """
    import tempfile

    from solution_arista_avd import demo_release as dr

    # A fresh name every attempt. Deleting a branch in Infrahub does not delete the workers' local
    # ref, so reusing a name hands Infrahub a branch that already sits on the old commit: it sees
    # nothing to import and waits forever.
    reset = f"{dr.demo_branch(name, run)}-reset-{int(time.time())}"
    before = _repository().get("commit", "")
    for leftover in sorted(b for b in (_branches() or {}) if b.startswith(f"{dr.demo_branch(name, run)}-reset")):
        _delete_demo_branch(ctx, leftover)  # from an interrupted attempt
    print(f" - Creating '{reset}' with Sync with Git", flush=True)
    ctx.run(f"infrahubctl branch create {shlex.quote(reset)} --sync-with-git", pty=True)
    _wait_for(lambda: bool(_remote_tip(ctx, reset)), f"Infrahub to publish '{reset}'", timeout)
    tip = _restore_baseline_onto_branch(ctx, location, reset, dr.stage_branch(name), default_branch)
    _wait_until_settled(reset, tip, timeout, require_capability=False, repo_id=repo_id)
    if _graphql(f'{{ __type(name: "{DEMO_KIND}") {{ name }} }}', reset).get("__type"):
        for edge in (_graphql(f"{{ {DEMO_KIND} {{ edges {{ node {{ id }} }} }} }}", reset).get(DEMO_KIND) or {}).get(
            "edges", []
        ):
            print(f" - Deleting {DEMO_KIND} {edge['node']['id']} on '{reset}'", flush=True)
            _graphql(f'mutation {{ {DEMO_KIND}Delete(data: {{id: "{edge["node"]["id"]}"}}) {{ ok }} }}', reset)
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "absent.yml"
            absent.write_text(dr.absent_schema(DEMO_SCHEMA_NAMESPACE, DEMO_SCHEMA_NAME), encoding="utf-8")
            print(f" - Removing the {DEMO_KIND} schema node on '{reset}'", flush=True)
            ctx.run(f"infrahubctl schema load {shlex.quote(str(absent))} --branch {shlex.quote(reset)}", pty=True)
    print(f" - Merging '{reset}'", flush=True)
    ctx.run(f"infrahubctl branch merge {shlex.quote(reset)}", pty=True)
    _wait_for(
        lambda: _repository().get("commit") not in {"", before} and _repository().get("sync_status") == "in-sync",
        "Infrahub's main to take the restored baseline",
        timeout,
    )
    _delete_demo_branch(ctx, reset)


@task(
    help={
        "name": f"Capability name (default {DEMO_NAME})",
        "run": "The release to remove. 0 (the default) is the latest one in use",
        "timeout": "Seconds to wait for the import (default 600)",
    }
)
def demo_reset(ctx: Context, name: str = DEMO_NAME, run: int = 0, timeout: int = 600) -> None:
    """Undo a release so the demo can be rehearsed again, merged or not.

    Order matters: the code goes back first, so nothing on `main` names the kind; then the
    kind's objects and schema node are removed if the merge put them there; then the
    Infrahub branch and the remote branch go. Never reuse the name afterwards: the next
    release takes `--run <n+1>`.
    """
    import tempfile

    from solution_arista_avd import demo_release as dr

    repo = _repository()
    _ensure_workers_on_default_branch(repo)
    if run < 1:
        from solution_arista_avd import demo_restore as restore_module

        run = restore_module.latest_run(name, _taken_branch_names(ctx, repo.get("id", "")))
        print(f" - Resetting release number {run} (the latest in use)", flush=True)
    demo = dr.demo_branch(name, run)
    merged = bool(_graphql(f'{{ __type(name: "{DEMO_KIND}") {{ name }} }}').get("__type"))
    if repo.get("kind") == "CoreRepository":
        # An interrupted reset can leave the data removed and the code merged, so ask git as well.
        if merged or _code_is_merged(ctx, repo["default_branch"], dr.stage_branch(name)):
            _take_capability_back_out(ctx, repo["id"], repo["location"], repo["default_branch"], name, run, timeout)
    elif repo.get("kind") == "CoreReadOnlyRepository" and repo["ref"] != "main":
        main_tip = _remote_tip(ctx, "main")
        print(" - Pointing the repository back at main", flush=True)
        _graphql(dr.set_ref_mutation(repo["id"], "main"))
        _wait_for(lambda: _repository().get("commit") == main_tip, f"the import of {main_tip[:10]}", timeout)
    if merged and repo.get("kind") != "CoreRepository":
        for edge in (_graphql(f"{{ {DEMO_KIND} {{ edges {{ node {{ id }} }} }} }}").get(DEMO_KIND) or {}).get(
            "edges", []
        ):
            print(f" - Deleting {DEMO_KIND} {edge['node']['id']}", flush=True)
            _graphql(f'mutation {{ {DEMO_KIND}Delete(data: {{id: "{edge["node"]["id"]}"}}) {{ ok }} }}')
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "absent.yml"
            absent.write_text(dr.absent_schema(DEMO_SCHEMA_NAMESPACE, DEMO_SCHEMA_NAME), encoding="utf-8")
            print(f" - Removing the {DEMO_KIND} schema node", flush=True)
            ctx.run(f"infrahubctl schema load {shlex.quote(str(absent))}", pty=True)
    _regenerate_artifacts()
    for leftover in sorted(b for b in (_branches() or {}) if b.startswith(f"{demo}-reset")):
        _delete_demo_branch(ctx, leftover)  # an attempt that was interrupted or had nothing to undo
    _delete_demo_branch(ctx, demo)
    print(f"\nNext release: invoke demo-release --name {name}  (it takes the next unused number, {run + 1} or later)")


def _rehearsal() -> Any:
    """`scripts/demo_rehearsal.py` as a module: its helpers drive the portal, the devices and the cluster."""
    import importlib.util

    path = Path(__file__).resolve().parent / "scripts" / "demo_rehearsal.py"
    spec = importlib.util.spec_from_file_location("demo_rehearsal", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["demo_rehearsal"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _demo_services(kind: str) -> dict[str, dict[str, str]]:
    """Every `kind` object on main: name -> status and, for an application, namespace and VIP block."""
    extra = " namespace_name { value } vip_block { node { prefix { value } } }" if kind == "ServiceFabricApp" else ""
    query = f"{{ {kind} {{ edges {{ node {{ id name {{ value }} status {{ value }}{extra} }} }} }} }}"
    found: dict[str, dict[str, str]] = {}
    for edge in (_graphql(query).get(kind) or {}).get("edges") or []:
        node = edge["node"]
        block = ((node.get("vip_block") or {}).get("node") or {}).get("prefix") or {}
        found[str(node["name"]["value"])] = {
            "id": str(node["id"]),
            "status": str(node["status"]["value"]),
            "namespace": str((node.get("namespace_name") or {}).get("value") or ""),
            "block": str(block.get("value") or ""),
        }
    return found


def _generator_runs(branch: str) -> None:
    """Regenerate every switch's host vars and structured config on `branch`, as the proposed change would see them."""
    for definition in ("generate-avd-device-hostvar", "generate-avd-device-structured-config"):
        found = _graphql(
            f'{{ CoreGeneratorDefinition(name__value: "{definition}") {{ edges {{ node {{ id }} }} }} }}', branch
        )
        generator_id = found["CoreGeneratorDefinition"]["edges"][0]["node"]["id"]
        _graphql(
            f'mutation {{ CoreGeneratorDefinitionRun(data: {{id: "{generator_id}"}}, wait_until_completion: true) {{ ok }} }}',
            branch,
        )


def _delete_leftover_restore_branches() -> None:
    """A restore branch from an interrupted run: unmerged, so it carries nothing worth keeping."""
    from solution_arista_avd import demo_restore as restore_module

    rehearsal = _rehearsal()
    leftovers = [b for b in (_branches() or {}) if restore_module.is_restore_branch(b)]
    if leftovers:
        print(f" - Removing the branch left by an interrupted restore: {', '.join(leftovers)}", flush=True)
        rehearsal.cleanup(leftovers)


def _withdraw_demo_services(timeout: int) -> dict[str, Any] | None:
    """Withdraw every demo-created grant and application on one branch, and merge it.

    Returns what the merge removed, for the convergence checks, or None when there was nothing to do.
    On one branch, in order: each grant set `decommissioning` and the generator awaited, then each
    application; the switches regenerated; then the withdrawn objects and their generator instances and
    groups deleted ON THE BRANCH. Deleting there, and not after the merge, is deliberate: the
    Crossplane artifact of a withdrawn application cannot render (its VIP block is released, and the
    transform refuses an exposed application with no block), so the proposed change would be red, and
    deleting the application removes the artifact, which is also what makes Vidra delete the resource.
    """
    from pathlib import Path as _Path

    from solution_arista_avd import demo_restore as restore_module

    rehearsal = _rehearsal()
    seeds = restore_module.seeded_names(
        p.read_text(encoding="utf-8") for p in sorted((_Path(__file__).resolve().parent / "objects").glob("*.yml"))
    )
    grants, apps = _demo_services("ServiceAppAccess"), _demo_services("ServiceFabricApp")
    todo_grants = restore_module.demo_created(grants, seeds["ServiceAppAccess"])
    todo_apps = restore_module.demo_created(apps, seeds["ServiceFabricApp"])
    if not todo_grants and not todo_apps:
        print(" - No demo-created grant or application on main", flush=True)
        return None
    print(f" - Withdrawing grants {todo_grants} then applications {todo_apps}", flush=True)
    branch = f"{restore_module.RESTORE_BRANCH_PREFIX}{int(time.time())}"
    rehearsal.gql(
        "mutation ($b: String!) { BranchCreate(data: {name: $b, sync_with_git: false}) { ok } }", {"b": branch}
    )

    def withdraw(kind: str, names: list[str]) -> None:
        for name in names:
            rehearsal.gql(
                f'mutation ($n: String!) {{ {kind}Update(data: {{hfid: [$n], status: {{value: "decommissioning"}}}}) {{ ok }} }}',
                {"n": name},
                branch=branch,
            )
        gone = rehearsal.wait_until(
            lambda: all(_demo_services_on(kind, branch).get(n, {}).get("status") == "decommissioned" for n in names),
            timeout=300,
            interval=5,
        )
        if not gone:
            raise Exit(f"The generator did not withdraw {kind} {names} on '{branch}' within 300 s.", code=1)
        print(f"   {kind} {names}: decommissioned", flush=True)

    if todo_grants:
        withdraw("ServiceAppAccess", todo_grants)
    if todo_apps:
        withdraw("ServiceFabricApp", todo_apps)
    print(" - Regenerating the fabric on the branch", flush=True)
    _generator_runs(branch)

    names = set(todo_grants) | set(todo_apps)
    records = rehearsal.gql(
        """{ CoreGeneratorInstance { edges { node { id name { value } } } }
             CoreGeneratorGroup { edges { node { id name { value } description { value } } } } }""",
        branch=branch,
    )
    rows = [
        ("CoreGeneratorInstance", e["node"]["id"], e["node"]["name"]["value"])
        for e in records["CoreGeneratorInstance"]["edges"]
    ]
    rows += [
        ("CoreGeneratorGroup", e["node"]["id"], str(e["node"]["description"]["value"] or ""))
        for e in records["CoreGeneratorGroup"]["edges"]
    ]
    for kind, node_id in restore_module.generator_records_for(names, rows):
        rehearsal.gql(
            f"mutation ($id: String!) {{ {kind}Delete(data: {{id: $id}}) {{ ok }} }}", {"id": node_id}, branch=branch
        )
    # Deleting an object does NOT delete its artifacts: the Crossplane FabricApp artifact stays on `main`
    # with no object, Vidra still sees it, and the application stays in the cluster for good. Measured:
    # the namespace and the FabricApp were gone 50 s after the orphan artifact was deleted.
    doomed_ids = {grants[n]["id"] for n in todo_grants} | {apps[n]["id"] for n in todo_apps}
    artifacts = rehearsal.gql("{ CoreArtifact { edges { node { id object { node { id } } } } } }", branch=branch)
    for edge in artifacts["CoreArtifact"]["edges"]:
        owner = (edge["node"]["object"]["node"] or {}).get("id")
        if owner in doomed_ids:
            rehearsal.gql(
                "mutation ($id: String!) { CoreArtifactDelete(data: {id: $id}) { ok } }",
                {"id": edge["node"]["id"]},
                branch=branch,
            )
    for kind, group in (("ServiceAppAccess", todo_grants), ("ServiceFabricApp", todo_apps)):
        source = grants if kind == "ServiceAppAccess" else apps
        for name in group:
            rehearsal.gql(
                f"mutation ($id: String!) {{ {kind}Delete(data: {{id: $id}}) {{ ok }} }}",
                {"id": source[name]["id"]},
                branch=branch,
            )
    print(f" - Deleted {sorted(names)} and their generator records on '{branch}'", flush=True)

    mutation = (
        "mutation { CoreProposedChangeCreate(data: {"
        ' name: { value: "Restore the demo baseline" }'
        f' source_branch: {{ value: "{branch}" }} destination_branch: {{ value: "main" }}'
        " }) { object { id } } }"
    )
    pc_id = ((_graphql(mutation).get("CoreProposedChangeCreate") or {}).get("object") or {}).get("id")
    if not pc_id:
        raise Exit(f"Could not open the proposed change for '{branch}'.", code=1)
    _wait_for_validators(pc_id, timeout)
    print(" - Merging", flush=True)
    result = httpx.post(
        f"{INFRAHUB_ADDRESS}/graphql",
        json={
            "query": f'mutation {{ CoreProposedChangeMerge(data: {{id: "{pc_id}"}}, wait_until_completion: true) {{ ok }} }}'
        },
        headers={"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")},
        timeout=300,
    )
    if not ((result.json().get("data") or {}).get("CoreProposedChangeMerge") or {}).get("ok"):
        raise Exit(f"Infrahub refused the merge of '{branch}': {result.text[:300]}", code=1)
    return {
        "since": time.time(),
        "branch": branch,
        "apps": {n: apps[n] for n in todo_apps},
        "grants": todo_grants,
    }


def _demo_services_on(kind: str, branch: str) -> dict[str, dict[str, str]]:
    query = f"{{ {kind} {{ edges {{ node {{ id name {{ value }} status {{ value }} }} }} }} }}"
    return {
        str(e["node"]["name"]["value"]): {"status": str(e["node"]["status"]["value"])}
        for e in (_graphql(query, branch).get(kind) or {}).get("edges") or []
    }


def _wait_converged(removed: dict[str, Any], timeout: int) -> None:
    """Wait for the lab to follow the merge: devices pushed and confirmed, cluster and address pool cleared."""
    rehearsal = _rehearsal()
    since = removed["since"]
    conditions: dict[str, Callable[[], bool]] = {
        "the reconciler has pushed and then confirmed": lambda: rehearsal.pushed_and_confirmed(since),
    }

    def namespace_gone(namespace: str) -> Callable[[], bool]:
        return lambda: "NotFound" in rehearsal.kubectl("get", "namespace", namespace).stderr

    def fabricapp_gone(app: str) -> Callable[[], bool]:
        return lambda: "NotFound" in rehearsal.kubectl("get", "fabricapp", app).stderr

    def block_released(block: str) -> Callable[[], bool]:
        return lambda: (
            not ((_graphql(f'{{ IpamPrefix(prefix__value: "{block}") {{ count }} }}').get("IpamPrefix")) or {}).get(
                "count"
            )
        )

    for name, app in removed["apps"].items():
        if app["namespace"]:
            conditions[f"{name}: namespace {app['namespace']} is gone from the cluster"] = namespace_gone(
                app["namespace"]
            )
        conditions[f"{name}: its FabricApp is gone"] = fabricapp_gone(name)
        if app["block"]:
            conditions[f"{name}: the VIP block {app['block']} is released"] = block_released(app["block"])
    seen = rehearsal.watch("restore", since, conditions, timeout=timeout)
    missing = [c for c in conditions if c not in seen]
    if missing:
        raise Exit("The lab did not converge: " + "; ".join(missing), code=1)


def _delete_orphan_artifacts() -> None:
    """Delete artifacts on main whose object is gone: Vidra keeps delivering them, so their resource never leaves."""
    rehearsal = _rehearsal()
    edges = rehearsal.gql("{ CoreArtifact { edges { node { id name { value } object { node { id } } } } } }")[
        "CoreArtifact"
    ]["edges"]
    for edge in edges:
        if not (edge["node"]["object"]["node"] or {}).get("id"):
            print(
                f" - Deleting the orphan artifact '{edge['node']['name']['value']}' ({edge['node']['id']})", flush=True
            )
            rehearsal.gql(
                "mutation ($id: String!) { CoreArtifactDelete(data: {id: $id}) { ok } }", {"id": edge["node"]["id"]}
            )


def _delete_dangling_generator_records() -> None:
    """Delete generator instances on main whose object is gone, and the tracking groups of the same name.

    Deleting an instance on the restore branch does not reach main (measured: all three were still
    there after the merge), and one pointing at a deleted node turns the generator red on every later
    proposed change. A group is removed when it is a `generate-*` tracking group with no member.
    """
    import re

    rehearsal = _rehearsal()
    data = rehearsal.gql(
        """{ CoreGeneratorInstance { edges { node { id name { value } object { node { id } } } } }
             CoreGeneratorGroup { edges { node { id name { value } description { value } members { count } } } } }"""
    )
    for edge in data["CoreGeneratorInstance"]["edges"]:
        if not (edge["node"]["object"]["node"] or {}).get("id"):
            print(f" - Deleting the dangling generator instance '{edge['node']['name']['value']}'", flush=True)
            rehearsal.gql(
                "mutation ($id: String!) { CoreGeneratorInstanceDelete(data: {id: $id}) { ok } }",
                {"id": edge["node"]["id"]},
            )
    for edge in data["CoreGeneratorGroup"]["edges"]:
        node = edge["node"]
        tracking = re.fullmatch(r"generate-[a-z-]+-[0-9a-f]{32}", node["name"]["value"]) is not None
        if tracking and (node["description"]["value"] or "").startswith("name: ") and not node["members"]["count"]:
            print(
                f" - Deleting the empty tracking group '{node['name']['value']}' ({node['description']['value']})",
                flush=True,
            )
            rehearsal.gql(
                "mutation ($id: String!) { CoreGeneratorGroupDelete(data: {id: $id}) { ok } }", {"id": node["id"]}
            )


def _delete_merged_branches(ctx: Context) -> None:
    """Delete every Infrahub branch whose proposed change merged. The proposed change stays as history."""
    merged = {
        e["node"]["source_branch"]["value"]
        for e in (
            _graphql(
                '{ CoreProposedChange(state__value: "merged") { edges { node { source_branch { value } } } } }'
            ).get("CoreProposedChange")
            or {}
        ).get("edges")
        or []
    }
    branches = _branches() or {}
    for branch in sorted(merged):
        if branch in branches and not branches[branch]:
            print(f" - Deleting the merged branch '{branch}'", flush=True)
            ctx.run(f"infrahubctl branch delete {shlex.quote(branch)}", pty=True, warn=True)


@task(
    help={
        "name": f"The builder capability to reset (default {DEMO_NAME})",
        "timeout": "Seconds each wait may take (default 600)",
        "no_verify": "Skip the preflight and `make -C lab verify` at the end",
    }
)
def demo_restore(ctx: Context, name: str = DEMO_NAME, timeout: int = 600, no_verify: bool = False) -> None:
    """Return the whole lab to the seeded baseline after a demo. Idempotent; safe to run again if interrupted.

    In order: the builder capability is reset (`demo-reset`); every grant and application a presenter
    created is withdrawn on one branch and merged; the devices, the cluster and the address pool are
    awaited; the merged branches are deleted; then the preflight and `make -C lab verify` prove it.
    Anything it cannot return to the baseline it says so, and the fallback is `invoke bootstrap --fresh`.
    """
    rehearsal = _rehearsal()
    started = time.monotonic()
    repo = _repository()
    if not repo:
        raise Exit("No repository is registered. Bootstrap first.", code=1)
    upstream_before = _remote_tip(ctx, "main")

    print("\n=== 1. The builder capability ===", flush=True)
    with ctx.cd(MAIN_DIRECTORY_PATH):
        has_stage = ctx.run(
            f"git rev-parse --verify --quiet refs/heads/stage/{shlex.quote(name)}", hide=True, warn=True
        ).ok
    if not has_stage:
        demo_stage(ctx, name=name)
    demo_reset(ctx, name=name, timeout=timeout)

    print("\n=== 2. Grants and applications a presenter created ===", flush=True)
    _delete_leftover_restore_branches()
    removed = _withdraw_demo_services(timeout)
    _delete_orphan_artifacts()
    _delete_dangling_generator_records()

    print("\n=== 3. Waiting for the devices and the cluster ===", flush=True)
    if removed:
        _wait_converged(removed, timeout)
    else:
        since = time.time()
        rehearsal.wait_until(
            lambda: any("differed=0" in line for line in rehearsal.reconciler_cycles(since)), timeout=300, interval=10
        )

    print("\n=== 4. Merged branches ===", flush=True)
    _delete_merged_branches(ctx)

    upstream_after = _remote_tip(ctx, "main")
    if upstream_before != upstream_after:
        raise Exit(f"Upstream main moved during the restore: {upstream_before[:10]} -> {upstream_after[:10]}", code=1)
    if not no_verify:
        print("\n=== 5. Proving the baseline ===", flush=True)
        rehearsal.act_preflight()
        failed = [r for r in rehearsal.RESULTS if r[0] == "FAIL"]
        warned = [r for r in rehearsal.RESULTS if r[0] == "WARN"]
        if failed or warned:
            raise Exit(f"The restore is not clean: {[r[1] for r in failed + warned]}", code=1)
        ctx.run(f"make -C {shlex.quote(str(rehearsal.main_checkout() / 'lab'))} verify", pty=False)
    print(f"\nRestored in {time.monotonic() - started:.0f} s. Upstream main is untouched ({upstream_after[:10]}).")


@task(
    help={
        "acts": "Comma-separated acts to run, from one, two, builder (default all three)",
        "reference": "Request reference for the portal acts (default demo1)",
        "name": f"The builder capability (default {DEMO_NAME})",
        "no_builder_reset": "Leave the builder capability merged instead of taking it back out",
        "restore": "Afterwards run `invoke demo-restore` to return the lab to the baseline",
    }
)
def demo_run(
    ctx: Context,
    acts: str = "one,two,builder",
    reference: str = "demo1",
    name: str = DEMO_NAME,
    no_builder_reset: bool = False,
    restore: bool = False,
) -> None:
    """Run the whole demo against the live lab, merges included: a PASS/FAIL line per check and a timing table.

    CHANGES THE LAB. Exits non-zero on any FAIL. See scripts/demo_full_run.py and docs/docs/demo-builder.md.
    """
    command = [
        "uv", "run", "python", "scripts/demo_full_run.py",
        "--acts", acts, "--reference", reference, "--name", name,
    ]  # fmt: skip
    if no_builder_reset:
        command.append("--no-builder-reset")
    if restore:
        command.append("--restore")
    ctx.run(" ".join(shlex.quote(c) for c in command), pty=False)


# The AVD chain, and the reason it is split in two.
#
# TOPOLOGY_GENERATORS build the fabric: devices, racks and -- the part that
# matters most -- the spine-to-leaf cabling. They are BUILD-TIME ONLY. Re-running
# them against a fabric that already exists is destructive: `generate-pod` takes
# each spine from nine interfaces to four, deleting the leaf-role ports that
# racks 1 and 2 are cabled to, and `generate-rack` then fails on rack 3 with an
# IndexError because its slice of spine ports is empty. Measured, not supposed.
#
# AVD_GENERATORS turn the topology into PyAVD inputs and then into per-device
# AVD facts. These ARE idempotent: a second run on a branch reports "Hostvars
# unchanged" and "0 updated, 7 unchanged", and leaves every interface alone.
#
# So the default is the safe pair. Building a fabric from nothing is the
# exception and asks for it explicitly.
TOPOLOGY_GENERATORS = (
    "generate-fabric",
    "generate-pod",
    "generate-rack",
)

AVD_GENERATORS = (
    "generate-avd-device-hostvar",
    "generate-avd-device-structured-config",
)


def _artifact_definition_ids(branch: str = "") -> dict[str, str]:
    """Every artifact definition, by name, as the given branch sees them."""
    query = "query{CoreArtifactDefinition{edges{node{id name{value}}}}}"
    response = httpx.post(
        f"{INFRAHUB_ADDRESS}/graphql/{branch}" if branch else f"{INFRAHUB_ADDRESS}/graphql",
        json={"query": query},
        headers={"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")},
        timeout=60,
    )
    response.raise_for_status()
    edges = response.json()["data"]["CoreArtifactDefinition"]["edges"]
    return {e["node"]["name"]["value"]: e["node"]["id"] for e in edges}


@task(
    help={
        "branch": "Branch to run on. Created if absent. Omit to run against main.",
        "topology": (
            "Also run the fabric/pod/rack generators. BUILD-TIME ONLY -- they are "
            "destructive against a fabric that already has cabling."
        ),
        "artifacts": "Regenerate every artifact definition once the chain completes.",
        "merge": (
            "Merge the branch into main when the chain succeeds, wait for the artifacts to render, "
            "then delete the merged branch."
        ),
    }
)
def avd(ctx: Context, branch: str = "", topology: bool = False, artifacts: bool = True, merge: bool = False) -> None:
    """
    Run the AVD generation chain, optionally on its own branch.

    The usual case is data changing -- a new VRF, a re-addressed interface, a
    service added -- and wanting the switch configuration to follow. That is the
    default: regenerate the PyAVD hostvars, the structured configs, and the
    artifacts rendered from them.

    Use `--branch` for anything you intend to review. The chain writes a lot of
    derived data, and doing that straight onto `main` leaves nowhere to see what
    changed before it becomes the source of truth. On a branch you can diff it,
    raise a proposed change, and merge or discard.

    Use `--topology` only on an instance where the fabric has not been built yet,
    such as immediately after `invoke load`. A fresh load seeds objects but runs
    no generators, so there is no spine-to-leaf cabling and PyAVD renders
    switches with no uplinks and no underlay or overlay BGP -- roughly 155 lines
    for a spine instead of 239, with every artifact still reporting Ready. That
    silence is what this flag is for. Against an existing fabric it will damage
    it; see the note above TOPOLOGY_GENERATORS.
    """
    if branch:
        existing = ctx.run("infrahubctl branch list", hide=True, warn=True)
        if existing and branch in (existing.stdout or ""):
            print(f" - Branch '{branch}' already exists, reusing it")
        else:
            print(f" - Creating branch '{branch}'")
            ctx.run(f"infrahubctl branch create {branch}", pty=True)

    target = f" --branch {branch}" if branch else ""

    if topology:
        print(" - Building the topology")
        _run_topology_generators(ctx, branch, target)
        # Cables to ports the rack generator has just created, so they cannot
        # be in objects/. An upsert, so safe against a fabric already built.
        print(" - Cabling the MLAG peer links")
        ctx.run(f"infrahubctl object load objects_post_topology/{target}", pty=True)

    for generator in AVD_GENERATORS:
        print(f" - Running {generator}")
        ctx.run(f"infrahubctl generator {generator}{target}", pty=True)

    if artifacts:
        # Artifacts render from data the chain has just rewritten, and one
        # generated beforehand keeps its old content until something asks again.
        # There is no GraphQL mutation for this; the REST endpoint is the only
        # way to ask.
        print(" - Regenerating artifacts")
        for name, definition_id in sorted(_artifact_definition_ids(branch).items()):
            response = httpx.post(
                f"{INFRAHUB_ADDRESS}/api/artifact/generate/{definition_id}",
                # The branch matters. Without it the endpoint regenerates against
                # main, and on a branch you get the confusing result that
                # `infrahubctl transform --branch X` renders your change while the
                # stored artifact never moves.
                params={"branch": branch} if branch else None,
                headers={"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")},
                timeout=300,
            )
            print(f"   {name}: HTTP {response.status_code}")

    if branch and merge:
        print(f"\n - Merging '{branch}' into main")
        ctx.run(f"infrahubctl branch merge {shlex.quote(branch)}", pty=True)
        _wait_for_artifacts(ctx)
        _delete_merged_branch(ctx, branch)
        print("\n - Merged. Main now carries the chain's output.")
    elif branch:
        print(f"\n - Done on '{branch}'. Review the diff, then merge with `invoke avd --branch {branch} --merge`.")


def _branches() -> dict[str, bool] | None:
    """Every Infrahub branch, mapped to whether it is the default; None if Infrahub could not say."""
    data = _graphql("{ Branch { name is_default } }")
    if "Branch" not in data:
        return None
    return {row["name"]: bool(row.get("is_default")) for row in data["Branch"] or []}


def _delete_merged_branch(ctx: Context, branch: str) -> None:
    """Delete a branch `--merge` has just merged, idempotently.

    Left behind, `build-fabric` sat in every branch picker after every
    bootstrap: a branch whose whole content is already on main, which reads as
    work in progress to anyone opening the UI. It is deleted only AFTER the
    merge returned and the artifact wait finished -- `ctx.run` raises on a
    failed merge, so a branch whose merge did not happen is never reached here.

    Idempotent in both directions: a branch that is already gone is reported
    and skipped, and when Infrahub cannot be asked the branch is LEFT, because
    deleting a branch on a guess is the one outcome here that cannot be undone.
    The default branch is never deleted, whatever it is called.
    """
    branches = _branches()
    if branches is None:
        print(f" - Could not list branches; leaving '{branch}'. Delete it with `infrahubctl branch delete {branch}`.")
        return
    if branch not in branches:
        print(f" - Branch '{branch}' is already gone")
        return
    if branches[branch]:
        print(f" - '{branch}' is the default branch; not deleting it")
        return
    print(f" - Deleting the merged branch '{branch}'")
    ctx.run(f"infrahubctl branch delete {shlex.quote(branch)}", pty=True)


def _graphql(query: str, branch: str = "") -> dict[str, Any]:
    """One GraphQL read against a branch, returning `data` or an empty mapping."""
    url = f"{INFRAHUB_ADDRESS}/graphql/{branch}" if branch else f"{INFRAHUB_ADDRESS}/graphql"
    try:
        response = httpx.post(
            url,
            json={"query": query},
            headers={"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("data") or {}
    except (httpx.HTTPError, ValueError):
        return {}


def _rack_generation(branch: str) -> tuple[int, int]:
    """`(racks, racks whose generation_complete is true)` on this branch."""
    data = _graphql("{LocationRack{edges{node{generation_complete{value}}}}}", branch)
    edges = (data.get("LocationRack") or {}).get("edges") or []
    done = sum(1 for e in edges if ((e["node"].get("generation_complete") or {}).get("value")) is True)
    return len(edges), done


def _wait_until(predicate: Callable[[], bool], timeout: int, interval: int = 10) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        sleep(interval)
    return predicate()


def _run_topology_generators(ctx: Context, branch: str, target: str, timeout: int = 420) -> None:
    """Build fabric, pods and racks -- running each stage only if it has not already run.

    **The generators cascade, and running them all explicitly runs them twice.**
    `generate-fabric` writes each pod's checksum, and that write fires
    `trigger-pod-generator-update-checksum`; `generate-pod` writes each rack's
    checksum and fires the rack generator the same way, calling
    `trigger_rack_generation` directly for the racks whose checksum it did not
    change. Every pod and rack is therefore generated exactly once already.

    Running `generate-pod` and `generate-rack` on top of that is a second pass,
    and the second pass is destructive: it trims each spine's leaf-role ports and
    re-allocates them, deleting the cabling the first pass created. Measured
    across three clean rebuilds, which produced 10, 0 and 4 of the 10 expected
    spine-leaf links -- and a spine rendered with no `router bgp` at all, from
    artifacts that reported Ready.

    So each stage waits for the cascade and runs explicitly only if nothing
    happened. That also makes `--topology` safe to re-run against a built fabric,
    which it previously was not: with every rack already complete, both stages
    are skipped rather than destroying the cabling.
    """
    print(" - Running generate-fabric")
    ctx.run(f"infrahubctl generator generate-fabric{target}", pty=True)

    racks, complete = _rack_generation(branch)
    if racks == 0:
        print(" - Waiting for the pod cascade to create the racks")
        if not _wait_until(lambda: _rack_generation(branch)[0] > 0, timeout):
            print("   no racks appeared; running generate-pod explicitly")
            ctx.run(f"infrahubctl generator generate-pod{target}", pty=True)
            _wait_until(lambda: _rack_generation(branch)[0] > 0, timeout)
    else:
        print(f" - {racks} rack(s) already present; not running generate-pod again")

    racks, complete = _rack_generation(branch)
    if complete < racks or racks == 0:
        print(f" - Waiting for the rack cascade to finish cabling ({complete}/{racks} complete)")
        if not _wait_until(lambda: _all_racks_done(branch), timeout):
            racks, complete = _rack_generation(branch)
            print(f"   {complete}/{racks} complete; running generate-rack explicitly")
            ctx.run(f"infrahubctl generator generate-rack{target}", pty=True)
            _wait_until(lambda: _all_racks_done(branch), timeout)
    racks, complete = _rack_generation(branch)
    print(f" - Topology built: {complete}/{racks} rack(s) generated")


def _all_racks_done(branch: str) -> bool:
    racks, complete = _rack_generation(branch)
    return racks > 0 and complete == racks


# How long the artifact wait watches for movement before believing a render is
# finished. Six samples of ten seconds: the post-merge render of this fabric's
# fourteen artifacts starts and finishes inside a minute, and a shorter window
# was measured settling on pre-merge checksums. See _wait_for_artifacts.
SAMPLE_SECONDS = 10
STABLE_SAMPLES = 6


def _wait_for_artifacts(ctx: Context, timeout: int = 600) -> None:  # noqa: ARG001
    """Block until every configuration artifact on main is populated and stable.

    Artifact generation is **asynchronous**: the REST endpoint returns 200 and
    the rendering happens in a task afterwards, and a merge kicks off another
    round through Infrahub's branch-merge-post-process flow. Sampling right after
    either one finds artifacts that exist, report `Ready`, and are empty.

    That matters because `invoke provision` reads these. Pushing an empty
    artifact would replace a switch's configuration with nothing, so the
    bootstrap waits here rather than racing.

    **Non-empty is not enough, and neither is one quiet interval.** Both were
    measured, in that order:

    * An artifact still holding its PRE-merge content is populated, so the
      original wait returned immediately on a merge that removed something. The
      reconcile cycle that followed compared every device against stale output,
      reported `compared=14 differed=0`, and left the deleted interface on both
      leaves. Nothing errored.
    * Requiring two consecutive agreeing samples did not fix it, because the two
      samples agreed on the OLD checksums -- the post-merge render had not begun
      ten seconds after the merge, so the wait settled on exactly the stale
      values it was meant to exclude. Measured the same way, with the same
      `differed=0` and the same interface left behind.

    So stability has to be asserted over a window long enough for the render to
    have started: `STABLE_SAMPLES` consecutive agreeing samples, and any movement
    resets the count. The floor is empirical -- the post-merge render of this
    fabric's fourteen artifacts begins and completes well inside it -- and it is
    a floor rather than a guarantee, which is why the timeout path says what it
    could not establish rather than claiming success.

    Waiting instead for every checksum to MOVE would be exact and would never
    terminate: an artifact whose content genuinely did not change never moves,
    which is most of them on most merges.
    """
    names = ("AVD EOS Configuration", "SR Linux Configuration", "Junos Configuration")
    headers = {"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")}
    query = "{CoreArtifact{edges{node{id name{value}checksum{value}}}}}"
    print(" - Waiting for the rendered artifacts to carry content")
    deadline = time.time() + timeout
    empty = -1
    wanted: list[str] = []
    previous: dict[str, str] | None = None
    stable = 0
    while time.time() < deadline:
        current: dict[str, str] = {}
        try:
            response = httpx.post(
                f"{INFRAHUB_ADDRESS}/graphql/main", json={"query": query}, headers=headers, timeout=60
            )
            response.raise_for_status()
            edges = response.json()["data"]["CoreArtifact"]["edges"]
            nodes = [e["node"] for e in edges if e["node"]["name"]["value"] in names]
            wanted = [node["id"] for node in nodes]
            current = {node["id"]: (node.get("checksum") or {}).get("value") or "" for node in nodes}
            empty = sum(
                1
                for aid in wanted
                if not httpx.get(f"{INFRAHUB_ADDRESS}/api/artifact/{aid}", headers=headers, timeout=60).text.strip()
            )
        except (httpx.HTTPError, KeyError, TypeError):
            empty = -1
            current = {}
        stable = stable + 1 if current and current == previous else 0
        if empty == 0 and wanted and stable >= STABLE_SAMPLES:
            print(f"   all {len(wanted)} configuration artifacts populated and stable")
            return
        previous = current
        sleep(SAMPLE_SECONDS)

    if empty == 0:
        print(f"   WARNING: artifact checksums were still moving after {timeout}s -- a push may use stale output")
    else:
        print(f"   WARNING: {empty} artifact(s) still empty after {timeout}s -- `invoke provision` would push nothing")


def _remove_orphaned_lab_nodes(ctx: Context, topology: Path) -> None:
    """Remove containers labelled with this lab that its topology no longer declares.

    `containerlab destroy -t` removes only the nodes the CURRENT file lists. A
    node deleted from the topology -- the six FRR `-exporter` sidecars when the
    WAN moved to SR Linux -- survives every destroy, and the next deploy is then
    refused with "The 'otternet' lab has already been deployed", having removed
    nothing. That is how a `bootstrap --fresh` failed after the re-platform.
    Every ContainerLab container carries `containerlab=<lab>` and
    `clab-node-name=<node>`, so the orphans are exactly the labelled containers
    whose node name the file does not declare.
    """
    import yaml

    spec = yaml.safe_load(topology.read_text(encoding="utf-8"))
    lab = spec["name"]
    declared = set((spec.get("topology") or {}).get("nodes") or {})
    result = ctx.run(
        f"docker ps -a --filter label=containerlab={shlex.quote(lab)} "
        "--format '{{.Names}} {{.Label \"clab-node-name\"}}'",
        hide=True,
        warn=True,
    )
    orphans = [
        line.split()[0]
        for line in (result.stdout if result else "").splitlines()
        if line.strip() and (len(line.split()) < 2 or line.split()[1] not in declared)
    ]
    if orphans:
        print(f" - Removing {len(orphans)} container(s) the topology no longer declares: {', '.join(orphans)}")
        ctx.run(f"docker rm -f {' '.join(shlex.quote(name) for name in orphans)}", hide=True)


def find_lab_directory(explicit: str = "") -> Path:
    """Locate the OTTERNET lab: `lab/` in the MAIN checkout.

    The main checkout rather than this one, for the reason `compose_root` gives:
    there is one lab, and its runtime state -- ContainerLab's `clab-otternet/`,
    the k3s kubeconfigs -- lives under its directory.
    A worktree resolving to its own copy would deploy a second set of bind paths
    and read kubeconfigs that were never written. Set OTTERNET_LAB_DIR to
    override.
    """
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not (candidate / LAB_TOPOLOGY).is_file():
            raise SystemExit(f"No {LAB_TOPOLOGY} in {candidate}")
        return candidate

    if env_dir := os.getenv("OTTERNET_LAB_DIR"):
        return find_lab_directory(env_dir)

    candidate = compose_root() / "lab"
    if (candidate / LAB_TOPOLOGY).is_file():
        return candidate.resolve()

    raise SystemExit(f"No {LAB_TOPOLOGY} in {candidate}. Set OTTERNET_LAB_DIR to point at the lab.")


def _wait_for_eapi(ctx: Context, timeout: int = 600) -> None:
    """Block until every fabric switch answers eAPI, or the timeout expires.

    cEOS takes minutes to boot, and provisioning a switch that is still coming up
    fails in a way that looks like a configuration error rather than impatience.
    """
    addresses = sorted(_fabric_mgmt_addresses())
    if not addresses:
        print(" - No fabric switch management addresses in Infrahub; skipping the wait")
        return

    print(f" - Waiting for eAPI on {len(addresses)} switch(es), up to {timeout}s")
    deadline = time.time() + timeout
    pending = set(addresses)
    while pending and time.time() < deadline:
        for address in sorted(pending):
            result = ctx.run(
                f"curl -sk -o /dev/null -m 3 -w '%{{http_code}}' https://{address}/command-api",
                hide=True,
                warn=True,
            )
            # 401/405 both mean the listener is up; only a connection failure is 000.
            if result and result.stdout.strip() not in {"000", ""}:
                pending.discard(address)
                print(f"   {address} up ({len(addresses) - len(pending)}/{len(addresses)})")
        if pending:
            sleep(10)

    if pending:
        print(f" - Still unreachable after {timeout}s: {', '.join(sorted(pending))}")


def _fabric_mgmt_addresses() -> list[str]:
    """Every fabric switch's management address, from Infrahub."""
    query = "query{DcimFabricSwitch{edges{node{mgmt_ip{node{address{value}}}}}}}"
    try:
        response = httpx.post(
            f"{INFRAHUB_ADDRESS}/graphql",
            json={"query": query},
            headers={"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")},
            timeout=30,
        )
        response.raise_for_status()
        edges = response.json()["data"]["DcimFabricSwitch"]["edges"]
    except (httpx.HTTPError, KeyError, TypeError):
        return []

    addresses = []
    for edge in edges:
        node = (edge["node"].get("mgmt_ip") or {}).get("node") or {}
        value = (node.get("address") or {}).get("value")
        if value:
            addresses.append(value.split("/", 1)[0])
    return addresses


@task(
    help={
        "lab-dir": "Path to the lab. Defaults to OTTERNET_LAB_DIR, else lab/ in the main checkout.",
        "destroy": "Tear the lab down instead of deploying it.",
        "wait": "Block until every fabric switch answers eAPI before returning.",
    }
)
def lab(ctx: Context, lab_dir: str = "", destroy: bool = False, wait: bool = True) -> None:
    """
    Bring up the ContainerLab topology with management connectivity.

    Deploys the committed topology in lab/ as-is. The lab owns which nodes exist
    and how they are wired; Infrahub owns their configuration. Nothing here
    renders a topology.

    The fabric comes up **unconfigured on purpose**. The cEOS nodes are given no
    `startup-config` -- only `CLAB_MGMT_VRF` and a management address -- so they
    boot reachable and empty, which is exactly the state `invoke provision` then
    fills from Infrahub. The firewall and the SR Linux routers boot from the
    lab's own files and are re-provisioned from Infrahub the same way.

    Run `invoke provision` next.
    """
    lab_path = find_lab_directory(lab_dir)
    topology = lab_path / LAB_TOPOLOGY
    print(f" - Lab: {lab_path}")

    # ContainerLab needs root for netns and bridge work; --preserve-env keeps the
    # image variables the topology interpolates.
    clab = f"sudo --preserve-env={CLAB_ENV_PASSTHROUGH} containerlab"

    if destroy:
        print(f" - Destroying lab from {topology.name}")
        ctx.run(f"{clab} destroy -t {shlex.quote(str(topology))} --cleanup", pty=True)
        _remove_orphaned_lab_nodes(ctx, topology)
        return

    # Before a deploy too: an orphan left by an earlier topology makes
    # ContainerLab refuse the deploy outright ("already been deployed").
    _remove_orphaned_lab_nodes(ctx, topology)

    # THE TOOLING BRIDGE, BEFORE THE DEPLOY, and it is not optional.
    #
    # `br-otter-tool` is a `kind: bridge` node, which means ContainerLab expects
    # the HOST to already have it -- it does not create one. A missing bridge is
    # refused outright, before any node starts:
    #
    #   ERROR  Bridge "br-otter-tool" referenced in topology but does not exist.
    #
    # A host bridge does not survive a reboot, so this is not a once-per-machine
    # setup step; it is a precondition of every deploy. The script is idempotent
    # and also lays down the route back to the branch LAN, which is why it runs
    # here rather than being left to whoever remembers.
    bridge = lab_path / "scripts/tooling-bridge.sh"
    if bridge.is_file():
        print(" - Ensuring the tooling bridge exists")
        ctx.run(shlex.quote(str(bridge)), pty=True)

    # THE WAN'S BOOT CONFIGURATION, RENDERED BEFORE THE DEPLOY. Every SR Linux
    # router names lab/wan/rendered/<node>/config.cli as its startup-config, and
    # every WAN host bind-mounts an init.sh beside it -- gitignored generated
    # output, so on a fresh clone the topology is refused for a missing file
    # before any node starts. The lab's own Makefile
    # renders it in `make deploy`; this drives ContainerLab directly, so it has to
    # as well. The renderer needs only Jinja and YAML, which this environment
    # already has, and it is idempotent.
    renderer = lab_path / "wan/render.py"
    if renderer.is_file():
        print(" - Rendering the WAN boot configuration")
        ctx.run(f"{shlex.quote(sys.executable)} {shlex.quote(str(renderer))}", hide="out")

    print(f" - Deploying {topology.name} (cEOS takes a few minutes to boot)")
    ctx.run(f"{clab} deploy -t {shlex.quote(str(topology))} --reconfigure", pty=True)

    if wait:
        _wait_for_eapi(ctx)

    print("\n - Lab is up with management connectivity. Configure it with `invoke provision`.")


@task(
    help={
        "branch": "Infrahub branch to read artifacts from. Omit to use main.",
        "dry-run": "List what would be pushed without changing any device.",
        "only": "Provision a single device by its Infrahub name.",
        "kind": "Provision one family only: eos, srl, or junos.",
    }
)
def provision(ctx: Context, branch: str = "", dry_run: bool = False, only: str = "", kind: str = "") -> None:
    """
    Push Infrahub's rendered configuration onto the running lab.

    The second half of the bring-up: `invoke lab` gives every device management
    connectivity, and this makes each one match the artifact Infrahub rendered
    for it -- EOS switches over eAPI, the firewall and the SR Linux routers
    through their containers.

    Re-run it whenever the model changes. Each push is a replace, not a merge, so
    removing something from the model removes it from the device.

    Requires the artifacts to exist: run `invoke avd` first, or `invoke avd
    --topology` on a freshly loaded instance.
    """
    flags = []
    if branch:
        flags.append(f"--branch {shlex.quote(branch)}")
    if dry_run:
        flags.append("--dry-run")
    if only:
        flags.append(f"--only {shlex.quote(only)}")
    if kind:
        flags.append(f"--kind {shlex.quote(kind)}")

    ctx.run(f"python scripts/provision_lab.py {' '.join(flags)}".strip(), pty=True)


@task(
    help={
        "once": "Run a single cycle and stop, instead of looping.",
        "converge": "Cycle until every device is confirmed, then stop. Used to bootstrap a cold fabric.",
        "dry_run": "Report what each device would change, push nothing, write no state.",
        "branch": "Compare against this branch (dry run only; deploys are main-only).",
        "interval": "Seconds between cycles. Refused below 60.",
    }
)
def reconcile(
    ctx: Context,
    once: bool = False,
    converge: bool = False,
    dry_run: bool = False,
    branch: str = "",
    interval: int = 0,
    now: bool = False,
) -> None:
    """
    Reconcile the running lab against Infrahub, continuously.

    `--now` starts nothing itself: it asks the RUNNING loop, in the
    `deployment-reconciler` container, for a cycle over every device within a
    second. The loop already wakes early when an artifact's checksum moves and
    holds still; this is for when you do not want to wait for that, or for a
    device someone changed by hand.

    The difference from `invoke provision` is who decides when. `provision`
    pushes because you asked; this compares every device against its rendered
    artifact on a timer and pushes only the ones that actually differ -- so a
    merge reaches the fabric without anyone typing anything, and a device
    someone edited by hand is put back.

    Each device computes its own diff, so drift is visible even when the
    artifact has not changed. State goes to `DeploymentState` in Infrahub, which
    is where an operator looks to see whether their merge arrived.

    **It pushes without asking.** Set `suspend` on a device's `DeploymentState`
    to take that one device out of the loop without stopping the service.
    """
    if now:
        # The trigger file lives inside the container, so the request is made
        # there; a container that is not running fails here, loudly, rather
        # than leaving a file no loop will ever read.
        ctx.run(
            f"{compose_cmd()} --profile reconcile exec -T deployment-reconciler python scripts/reconcile.py --now",
            pty=True,
        )
        return

    flags = []
    if once:
        flags.append("--once")
    if converge:
        flags.append("--converge")
    if dry_run:
        flags.append("--dry-run")
    if branch:
        flags.append(f"--branch {shlex.quote(branch)}")
    if interval:
        flags.append(f"--interval {interval}")

    ctx.run(f"python scripts/reconcile.py {' '.join(flags)}".strip(), pty=True)


# The two Crossplane resources Infrahub models and Vidra delivers. The lab
# repository declares the same two in crossplane/platform/10-peering.yaml and
# crossplane/apps/10-demo.yaml, and its bootstrap applies them -- which is right
# for a standalone lab and wrong here. Vidra refuses to adopt a resource it did
# not create ("already exists but is not managed by this operator"), so whichever
# copy exists first wins and the other never arrives. These are handed over
# before the operator is installed.
INFRAHUB_OWNED_RESOURCES = (
    ("fabricapp", "otternet-demo"),
    ("fabricpeering", "otternet"),
)

# The lab's own two applications, which Infrahub does not model: the access
# broker and the kube-prometheus-stack. The handover deletes them, so a finished
# bootstrap carries only the applications Infrahub declares -- an unmodelled
# application in the cluster is state no proposed change can explain, and both of
# these predate the service layer that now requests applications.
#
# Vidra never sees them either way; it only ever deletes a resource that leaves a
# manifest it delivered itself. They are the lab's installer's, and deleting them
# here is the seam: the access broker is applied, waited on, and then removed.
#
# `otternet-observability` is NOT applied any more (cycle 034):
# `OTTERNET_SKIP_OBSERVABILITY` keeps the lab's kube-prometheus-stack out of a
# cluster that receives Infrahub's own `otternet-metrics`. It stays listed so the
# delete is defensive, and so test_handover_scope.py's parse of the installer --
# which still contains the guarded apply line -- keeps matching this list.
LAB_ONLY_APPS = ("otternet-access", "otternet-observability")

# Everything the handover deletes: the two the lab declares and Infrahub owns,
# which Vidra then re-delivers, and the two that simply go.
HANDOVER_DELETIONS = INFRAHUB_OWNED_RESOURCES + tuple(("fabricapp", name) for name in LAB_ONLY_APPS)

# What Vidra delivers that the lab never declared (cycle 034): the observability
# applications and the Telegraf configuration rendered from the monitoring
# profiles. Kept apart from INFRAHUB_OWNED_RESOURCES because that list is also
# half of HANDOVER_DELETIONS, and these were never the lab's to delete.
INFRAHUB_ONLY_RESOURCES = (
    ("fabricapp", "otternet-metrics"),
    ("fabricapp", "otternet-telemetry"),
    ("configmap", "telegraf-intent -n otternet-telemetry"),
)

# Every resource the cluster should hold once delivery has converged.
INFRAHUB_DELIVERED_RESOURCES = INFRAHUB_OWNED_RESOURCES + INFRAHUB_ONLY_RESOURCES

# Grafana's Dex client secret. A lab literal, committed beside the client in
# tooling/10-dex.yaml exactly as the portal's and Infrahub's are -- the two must
# agree, so this is one constant rather than an environment variable that could
# drift from the file.
GRAFANA_DEX_CLIENT_SECRET = "grafana-dex-secret"  # noqa: S105 -- lab literal, see tooling/10-dex.yaml

# The namespace the demo application composes. Waiting on this, rather than on
# composed-object names, is what makes the teardown check correct -- see
# _wait_for_teardown.
APP_NAMESPACE = "otternet-demo"


class _Missing:
    """Stands in for a command that did not run, so `.ok` is always answerable."""

    ok = False


MISSING = _Missing()


def _lab_kubeconfig(lab_dir: str = "") -> Path:
    return find_lab_directory(lab_dir) / "k8s/.kubeconfig/kubeconfig.yaml"


@task(
    help={
        "lab-dir": "Path to the lab. Defaults to OTTERNET_LAB_DIR, else lab/ in the main checkout.",
        "handover": "Delete the lab's claims, so the cluster carries only what Infrahub declares.",
    }
)
def cluster(ctx: Context, lab_dir: str = "", handover: bool = True) -> None:
    """
    Bring up the Kubernetes half: Cilium, then Vidra, then Crossplane.

    The installers for the CNI and Crossplane belong to the lab (lab/) and
    are run from here rather than reimplemented -- they are the lab's, the same
    way the topology is.

    Cilium is first and cannot be managed by Crossplane: it *is* the pod network,
    so a controller that needs a pod network to run cannot be the thing that
    creates one. The k3s nodes sit NotReady until it lands, which is expected
    rather than a fault.

    **Vidra goes up second, before the platform it delivers into, and the order
    is deliberate.** Its syncs fail while the XRDs are absent and retry every
    `requeueSyncAfter`, so it costs nothing -- and it means the resources
    Infrahub models are created by Vidra first-hand rather than adopted from
    somebody else. That matters because the operator's recovery is weak in ways
    that are easy to mistake for health:

      - It refuses to adopt a resource it did not create, so whichever writer
        gets there first keeps it.
      - A resource deleted after a successful sync stays missing for up to
        `requeueResourcesAfter` (ten minutes), with the sync reporting
        `Succeeded` throughout, because an unchanged checksum skips the apply.
      - Deleting its VidraResource does not cause redelivery at all; the sync
        still considers itself current. Recovering needs the InfrahubSync
        deleted and re-applied, which resets its checksum state.

    All three were measured against this lab, which is why Vidra owning the
    resource from the start is worth the ordering.

    `--handover` (the default) deletes every claim the lab's bootstrap applies,
    and that is two different things rather than one:

      - The demo application and the fabric peering are **modelled**, so Vidra
        re-delivers them on its next sync, within `requeueSyncAfter`.
      - The access broker and the observability stack are **not**, so they stay
        gone. A finished bootstrap then carries only the applications Infrahub
        declares, which is what makes the cluster explainable from the graph.

    The delete is the one seam between "the lab's cluster" and "Infrahub's
    resources", and it is a delete rather than a skip because the lab's script
    has no flag to leave a claim unapplied.
    """
    lab_path = find_lab_directory(lab_dir)
    kubeconfig = _lab_kubeconfig(lab_dir)
    print(f" - Lab: {lab_path}")

    print(" - Installing Cilium (the CNI; nodes stay NotReady until it is ready)")
    ctx.run(f"{shlex.quote(str(lab_path / 'k8s/bootstrap/install-cilium.sh'))}", pty=True)

    _wait_for_cluster_dns(ctx, kubeconfig)

    print(" - Installing Vidra before the platform, so it owns what it delivers")
    ctx.run("scripts/install_vidra.sh", pty=True, env={"KUBECONFIG": str(kubeconfig)})

    print(" - Installing Crossplane, the providers, the XRDs and the compositions")
    # OTTERNET_SKIP_OBSERVABILITY, whatever `handover` says. Infrahub delivers
    # its own kube-prometheus-stack (`otternet-metrics`), and two releases of
    # that chart contend for the same CRDs: the second fails `invalid ownership
    # metadata`. Vidra goes up before Crossplane, so both would be created in the
    # same window and deleting the lab's afterwards is too late. `--no-handover`
    # does not change that -- it keeps the lab's other claims, not a second
    # Prometheus operator.
    ctx.run(
        f"{shlex.quote(str(lab_path / 'k8s/bootstrap/install-crossplane.sh'))}",
        pty=True,
        env={"OTTERNET_SKIP_OBSERVABILITY": "1"},
    )

    if handover:
        print("\n - Removing the lab's claims, so only what Infrahub declares is left")
        for kind, name in HANDOVER_DELETIONS:
            # --wait=false, because a claim's finalizer holds the delete open
            # until Crossplane has torn its composed resources down, and the
            # observability stack takes minutes to go. _wait_for_teardown polls
            # for the same condition, so the four tear down in parallel rather
            # than one after another.
            ctx.run(
                f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))} "
                f"delete {kind} {name} --ignore-not-found --wait=false",
                pty=True,
                warn=True,
            )
        print(f"   {', '.join(LAB_ONLY_APPS)} are unmodelled and stay gone; Infrahub owns the other two.")
        _wait_for_teardown(ctx, kubeconfig)
        _force_resync(ctx, kubeconfig)
        print("\n - Waiting for Vidra to deliver them from Infrahub")
        _wait_for_syncs(ctx, kubeconfig)
    else:
        print("\n - Handover skipped: the lab keeps all four claims and Vidra will not adopt them.")

    _observability_secrets(ctx, kubeconfig)
    _wait_for_observability(ctx, kubeconfig)

    print("\n - Cluster ready.")


@task(
    help={
        "lab-dir": "Path to the lab. Defaults to OTTERNET_LAB_DIR, else lab/ in the main checkout.",
        "wait": "Block until both syncs report a terminal state.",
    }
)
def vidra(ctx: Context, lab_dir: str = "", wait: bool = True) -> None:
    """
    Install the Vidra operator, so a merge in Infrahub becomes cluster state.

    The operator polls each artifact's checksum on `main` and applies the
    manifest when it moves. Because the syncs are pinned to `main`, the trigger
    is a **merge**: work on a feature branch regenerates that branch's artifacts
    and they go nowhere.

    Run `invoke cluster` first -- the manifests Vidra delivers are Crossplane
    claims, so the XRDs and compositions have to exist or they have no controller
    and sit there unreconciled.
    """
    kubeconfig = _lab_kubeconfig(lab_dir)
    env = {"KUBECONFIG": str(kubeconfig)}
    ctx.run("scripts/install_vidra.sh", pty=True, env=env)

    if wait:
        print("\n - Waiting for both syncs to reach a terminal state")
        _wait_for_syncs(ctx, kubeconfig)


def _env_value(name: str) -> str:
    """A value from `.env`, or the empty string. The file is gitignored.

    The main checkout's `.env`, because that is the one compose reads.
    """
    from solution_arista_avd.envfile import env_file, read_env

    return read_env(env_file(MAIN_DIRECTORY_PATH), name)


def _ensure_env_value(name: str, comment: str) -> str:
    """The value of `name` in `.env`, generating and persisting one if absent.

    Generated once and then kept, so a rebuild does not rotate a password a
    person has already written down.
    """
    import secrets

    from solution_arista_avd.envfile import env_file, upsert_env

    existing = _env_value(name)
    if existing:
        return existing
    value = secrets.token_urlsafe(24)
    upsert_env(env_file(MAIN_DIRECTORY_PATH), name, value, comment)
    return value


def _wait_for_namespace(ctx: Context, kubeconfig: Path, namespace: str, timeout: int = 300) -> bool:
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (ctx.run(f"{kube} get ns {namespace} --no-headers", hide=True, warn=True) or MISSING).ok:
            return True
        sleep(5)
    return False


def _apply_secret(ctx: Context, kubeconfig: Path, namespace: str, name: str, data: dict[str, str]) -> None:
    """Create or update a Secret idempotently -- `apply` of a rendered manifest,
    never `create`, so a second run is a no-op rather than `AlreadyExists`.

    The values go through a temporary file rather than the command line, so they
    never appear in a process listing.
    """
    import base64
    import tempfile

    manifest = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name, "namespace": namespace, "labels": {"app.kubernetes.io/managed-by": "invoke"}},
        "type": "Opaque",
        "data": {key: base64.b64encode(value.encode()).decode() for key, value in data.items()},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=True, encoding="utf-8") as handle:
        json.dump(manifest, handle)
        handle.flush()
        ctx.run(
            f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))} apply -f {shlex.quote(handle.name)}",
            hide=True,
            warn=True,
        )


def _observability_secrets(ctx: Context, kubeconfig: Path) -> None:
    """The three Secrets the observability applications reference by name.

    None of these values is in the graph or in an artifact: the rendered values
    name the Secrets and nothing more. They can only be created once Vidra's
    delivery has made the namespaces, and until then the pods wait in
    `CreateContainerConfigError` -- which heals by itself the moment this runs.
    """
    print("\n - Creating the observability Secrets (credentials never pass through Infrahub)")
    if _wait_for_namespace(ctx, kubeconfig, "otternet-metrics"):
        _apply_secret(ctx, kubeconfig, "otternet-metrics", "grafana-oidc", {"client-secret": GRAFANA_DEX_CLIENT_SECRET})
        admin_password = _ensure_env_value(
            "GRAFANA_ADMIN_PASSWORD", "Grafana's break-glass admin, for operators only (people sign in through Dex)."
        )
        _apply_secret(
            ctx,
            kubeconfig,
            "otternet-metrics",
            "grafana-admin",
            {"admin-user": "admin", "admin-password": admin_password},
        )
        print("   otternet-metrics: grafana-oidc, grafana-admin")
    else:
        print("   WARNING: namespace otternet-metrics never appeared; Grafana will wait for its Secrets")

    if _wait_for_namespace(ctx, kubeconfig, "otternet-telemetry"):
        # The same local account the reconciler pushes EOS configuration as --
        # and the SR Linux routers' login too, rendered from the same hash.
        _apply_secret(
            ctx,
            kubeconfig,
            "otternet-telemetry",
            "telemetry-credentials",
            {
                "GNMI_USERNAME": os.getenv("OTTERNET_EOS_USERNAME", "admin"),
                "GNMI_PASSWORD": os.getenv("OTTERNET_EOS_PASSWORD", "admin"),
            },
        )
        print("   otternet-telemetry: telemetry-credentials")
    else:
        print("   WARNING: namespace otternet-telemetry never appeared; Telegraf will wait for its Secret")


def _wait_for_observability(ctx: Context, kubeconfig: Path, timeout: int = 900) -> None:
    """Wait for Grafana and Telegraf themselves, not for their claims' conditions.

    kube-prometheus-stack takes minutes on this host, and a FabricApp reads
    Ready as soon as its Helm release is accepted -- which says nothing about
    whether Grafana is answering.
    """
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    print(" - Waiting for Grafana and Telegraf (kube-prometheus-stack takes several minutes)")
    for namespace, selector in (
        ("otternet-metrics", "app.kubernetes.io/name=grafana"),
        ("otternet-telemetry", "app.kubernetes.io/name=telegraf"),
    ):
        deadline = time.time() + timeout
        ready = False
        while time.time() < deadline and not ready:
            ready = (
                ctx.run(
                    f"{kube} -n {namespace} wait pod -l {selector} --for=condition=Ready --timeout=30s",
                    hide=True,
                    warn=True,
                )
                or MISSING
            ).ok
            if not ready:
                sleep(10)
        print(f"   {namespace}: {'ready' if ready else f'NOT ready after {timeout}s'}")


def _wait_for_cluster_dns(ctx: Context, kubeconfig: Path, timeout: int = 300) -> None:
    """Wait for in-cluster DNS before anything that needs the cluster from inside.

    Crossplane's own bootstrap preflights ClusterIP reachability, external DNS
    and pod egress, and dies with `in-cluster networking preflight failed` if any
    of them is not up yet. Run by hand there is always a gap between installing
    the CNI and installing Crossplane, and the check passes. Run back to back by
    `invoke cluster` there is not, and it fails -- measured: CoreDNS cannot
    schedule at all until Cilium exists, so it is still starting when Crossplane
    asks.

    `install-cilium.sh` already waits for the nodes to go Ready, which is not the
    same thing: a node is Ready as soon as the CNI answers, while CoreDNS is a
    pod that then has to be scheduled and become available.

    Note that Vidra's own preflight passing says nothing about this one. It
    checks egress to the management gateway on the node network; Crossplane needs
    DNS and a ClusterIP.
    """
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    print(" - Waiting for in-cluster DNS (Crossplane preflights it and dies if it is not up)")
    result = ctx.run(f"{kube} -n kube-system rollout status deploy/coredns --timeout={timeout}s", pty=True, warn=True)
    if not (result and result.ok):
        print("   CoreDNS did not report available; Crossplane's preflight may fail")


def _wait_for_teardown(ctx: Context, kubeconfig: Path, timeout: int = 600) -> None:
    """Wait for a deleted claim's composed resources to finish disappearing.

    Deleting a FabricApp only *starts* the teardown: Crossplane deletes each
    composed Object, and the application's Namespace then sits in `Terminating`
    while Kubernetes reaps what is inside it. Letting Vidra recreate the claim
    during that window is what the handover used to do, and it produces a mess
    that does not resolve on its own:

        create failed: ... deployments.apps "frontend" is forbidden: unable to
        create new content in namespace otternet-demo because it is being terminated

    The new composed Objects fail against the dying namespace, a second
    composed Namespace Object appears alongside the first, and the FabricApp
    stays `Ready=False` indefinitely -- measured at nine minutes before it was
    cleaned up by hand.

    So: wait for the composed Objects to go, and for the namespace with them,
    before anything recreates the claim.

    It waits on the unmodelled applications too, which are not recreated by
    anybody. That is not for the race -- it is so the function's return means
    what the caller reports: nothing the lab claimed is left.
    """
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    print(" - Waiting for the composed resources to finish tearing down")
    deadline = time.time() + timeout
    outstanding: list[str] = []
    while time.time() < deadline:
        # Wait on the application NAMESPACE, not on composed-object names.
        # Matching objects by name prefix does not work here: composed objects are
        # named `<claim>-<hash>`, and the peering claim is called `otternet`, which is
        # a prefix of `otternet-access-...` and `otternet-observability-...` too. Those
        # were the lab's own applications, left in place at the time, so the filter
        # matched them forever and the wait always timed out.
        #
        # The namespace is the right thing to wait on regardless: it is what the
        # new composed resources collide with while it is Terminating.
        namespace = ctx.run(f"{kube} get ns {APP_NAMESPACE} --no-headers", hide=True, warn=True)
        outstanding = [
            f"{kind}/{name}"
            for kind, name in HANDOVER_DELETIONS
            if (ctx.run(f"{kube} get {kind} {name} --no-headers", hide=True, warn=True) or MISSING).ok
        ]
        if namespace and namespace.ok:
            outstanding.append(f"ns/{APP_NAMESPACE}")
        if not outstanding:
            print("   torn down")
            return
        sleep(10)

    print(
        f"   still tearing down after {timeout}s ({', '.join(outstanding)}); "
        "recreating anyway may leave a stuck namespace"
    )


def _force_resync(ctx: Context, kubeconfig: Path) -> None:
    """Make Vidra re-deliver every artifact, whether or not its checksum moved.

    Necessary after the handover, and the reason is the operator's weakest
    behaviour. A sync compares the artifact's **checksum**; unchanged means it
    skips the download and the apply entirely. So deleting a delivered resource
    -- which is exactly what the handover does -- leaves the sync reporting
    `Succeeded` over a cluster that no longer has the resource, and nothing
    re-applies it until the VidraResource reconcile fires on
    `requeueResourcesAfter`. That is ten minutes of a fabric peering that does
    not exist.

    Measured, not supposed: after the handover deleted `fabricapp/otternet-demo`
    and `fabricpeering/otternet`, both syncs read `Succeeded` and both resources
    stayed absent.

    Deleting and re-applying the InfrahubSync resets its checksum state, and
    delivery follows within seconds. Deleting the *VidraResource* instead does
    not work -- the sync still considers itself current and never re-applies.
    """
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    syncs = MAIN_DIRECTORY_PATH / "vidra/infrahub-syncs.yaml"
    print(" - Resetting the syncs so Vidra re-delivers (an unchanged checksum would skip the apply)")
    ctx.run(f"{kube} delete -f {shlex.quote(str(syncs))} --ignore-not-found --timeout=120s", pty=True, warn=True)
    # DELETING A SYNC TEARS DOWN WHAT IT DELIVERED, and that includes the
    # applications only Infrahub declares -- `otternet-metrics` and
    # `otternet-telemetry`, which Vidra delivered before the handover ran.
    # Re-applying at once recreated their claims while the first namespaces were
    # still Terminating, and left TWO composed Namespace objects per app: the
    # orphan, stuck deleting with `deletionPolicy: Delete`, kept deleting the
    # namespace the live one kept recreating. Measured on the first bootstrap
    # with them: namespaces aged in seconds for 25 minutes, taking the Secrets
    # and Telegraf's ConfigMap with them every time. So wait for them to go.
    _wait_for_namespaces_gone(ctx, kubeconfig, [name for kind, name in INFRAHUB_ONLY_RESOURCES if kind == "fabricapp"])
    ctx.run(f"{kube} apply -f {shlex.quote(str(syncs))}", pty=True, warn=True)


def _wait_for_namespaces_gone(ctx: Context, kubeconfig: Path, namespaces: list[str], timeout: int = 600) -> None:
    """Block until every named namespace has finished terminating."""
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    deadline = time.time() + timeout
    remaining = list(namespaces)
    while remaining and time.time() < deadline:
        remaining = [
            ns for ns in remaining if (ctx.run(f"{kube} get ns {ns} --no-headers", hide=True, warn=True) or MISSING).ok
        ]
        if remaining:
            sleep(10)
    if remaining:
        print(f"   WARNING: {', '.join(remaining)} still terminating after {timeout}s; re-applying the syncs anyway")
    else:
        print("   observability namespaces torn down; re-applying the syncs")


def _wait_for_syncs(ctx: Context, kubeconfig: Path, timeout: int = 300) -> None:
    """Wait until the resources Infrahub owns actually exist in the cluster.

    **This waits on the resources, not on `syncState`, deliberately.** A sync
    compares the artifact's checksum, so an unchanged checksum skips the
    download and the apply and still reports `Succeeded` -- over a cluster that
    may have none of them. An `artefactName` that does not match
    `.infrahub.yml` exactly fails the same way: an empty result set is a
    success. Waiting on the sync state would therefore return happily from a
    cluster where nothing was delivered, which is the failure that looks most
    like health.

    So the loop asks the API server whether every resource in
    INFRAHUB_DELIVERED_RESOURCES is there -- the demo, the peering, the two
    observability applications and Telegraf's ConfigMap -- and the sync table is
    printed afterwards as context rather than as the verdict.
    """
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    deadline = time.time() + timeout
    missing: list[str] = []
    while time.time() < deadline:
        missing = []
        for kind, name in INFRAHUB_DELIVERED_RESOURCES:
            found = ctx.run(f"{kube} get {kind} {name} --no-headers", hide=True, warn=True)
            if not (found and found.ok):
                missing.append(f"{kind}/{name}")
        if not missing:
            break
        sleep(10)

    ctx.run(
        f"{kube} get infrahubsync -o custom-columns="
        "NAME:.metadata.name,STATE:.status.syncState,LAST:.status.lastSyncTime,ERROR:.status.lastError",
        pty=True,
        warn=True,
    )
    print("\n - Resources Infrahub owns (this is the verdict, not the sync state):")
    ctx.run(
        f"{kube} get fabricapp,fabricpeering",
        pty=True,
        warn=True,
    )
    if missing:
        print(
            f"\n   WARNING: {', '.join(missing)} still absent after {timeout}s. "
            "The sync may read Succeeded regardless -- an unchanged checksum skips the apply. "
            "Re-run `invoke cluster` or delete and re-apply vidra/infrahub-syncs.yaml."
        )


@task(
    help={"no-cache": "Rebuild the image from scratch, ignoring the layer cache."},
)
def backstage_build(ctx: Context, no_cache: bool = False) -> None:
    """
    Build the service portal: the JavaScript bundle, then the image around it.

    **BOTH STEPS, because the Dockerfile builds nothing.** It unpacks
    `packages/backend/dist/bundle.tar.gz`, which `yarn build:backend` produces on
    the host -- so a `docker compose build` on its own packages whatever bundle
    was last built and reports success. A change to plugin source then does not
    ship, and nothing says so: the image is new, its layers are new, and its
    JavaScript is old. `app-config*.yaml` is COPYed separately and DOES ship,
    which is what makes the failure so confusing -- configuration changes arrive
    and code changes do not.

    The compose service is `profiles: ["build-only"]` -- the portal RUNS in the
    tooling cluster, not on the host -- so this builds the image and starts
    nothing. `invoke tooling` is what carries it across to the node.

    Use `--no-cache` to force the image layers as well; the bundle is rebuilt
    either way.
    """
    backstage = compose_root() / "backstage"
    if not backstage.is_dir():
        raise Exit(f"{backstage} is missing")

    # A BOUNDED HEAP, because this usually runs on a host that is also running
    # the lab. Node sizes its old space against total system memory, so on a
    # 61GB box it will happily grow past what is actually free with thirty
    # containers up -- and the build is then killed rather than failing, which
    # looks like an infrastructure hiccup rather than a resource limit.
    env = {"NODE_OPTIONS": "--max-old-space-size=4096"}

    # `cd`, NOT `yarn --cwd`. This repository pins Yarn 4 through `.yarnrc.yml`
    # and `.yarn/`, and Yarn finds that only by being run from inside the
    # project. `yarn --cwd <dir>` is resolved before the directory is consulted,
    # so Corepack decides there is no project, falls back to Yarn Classic, and
    # asks whether to download it:
    #
    #   ! Corepack is about to download .../yarn-1.22.22.tgz
    #   ? Do you want to continue? [Y/n]
    #
    # Nobody is watching that prompt, so the build sits on it indefinitely --
    # which looks exactly like a slow typecheck. It sat for twenty-five minutes
    # before anyone read the output rather than the clock.
    #
    # `tsc` first: `build:backend` bundles without typechecking, so a type error
    # would otherwise reach the image and only fail at runtime.
    print(" - Typechecking and bundling the portal")
    with ctx.cd(str(backstage)):
        ctx.run("yarn tsc", pty=True, env=env)
        ctx.run("yarn build:backend", pty=True, env=env)

    flag = " --no-cache" if no_cache else ""
    print(" - Building the image around it")
    ctx.run(f"{compose_cmd()} --profile build-only build{flag} backstage", pty=True)


@task
def tooling(ctx: Context) -> None:
    """
    Deploy the tooling cluster's contents: Dex, and the Backstage portal.

    **This is the one part of the lab Infrahub does not deliver, and cannot.**
    Dex is the identity provider Infrahub authenticates users against and
    Backstage is where people request services, so anything waiting on an
    Infrahub merge to exist would have to exist before it could be merged. The
    tooling network is L2-adjacent to the host for the same reason -- see
    `lab/scripts/tooling-bridge.sh`.

    Independent of `invoke cluster`, which brings up the WORKLOAD cluster behind
    the fabric. These are two clusters with two purposes; neither waits on the
    other.

    Idempotent: re-run it to roll out a manifest edit or a rebuilt image.
    """
    if not Path("scripts/deploy_tooling.sh").is_file():
        raise Exit("scripts/deploy_tooling.sh is missing")
    # THE PORTAL'S OWN ACCOUNT FIRST, because the deploy renders its token into
    # the backstage Secret and refuses without one. `backstage-portal` reads
    # everything and writes only on branches -- the portal used to hold the
    # stack's Super Administrator token. Idempotent: a token that still works is
    # kept, so a re-run does not rotate what a running portal holds.
    print(" - Provisioning the portal's own Infrahub account")
    ctx.run("python scripts/provision_portal_account.py", pty=True)
    ctx.run("scripts/deploy_tooling.sh", pty=True)

    # EVERY PORTAL USER NEEDS AN INFRAHUB ACCOUNT BEFORE THEIR FIRST REQUEST.
    # The portal writes as the signed-in user through the mutation `context`,
    # and that account exists only once the person has signed in to Infrahub at
    # least once -- so without this a first request dies at the create step,
    # after its branch has already been created, naming an account rather than
    # the thing to do about it. Idempotent, and best effort: a portal with no
    # accounts provisioned still works for anyone who signs in by hand.
    print(" - Provisioning an Infrahub account for each portal user")
    ctx.run("python scripts/provision_portal_accounts.py", pty=True, warn=True)


@task
def mcp(ctx: Context) -> None:
    """
    Start the Infrahub MCP server beside Infrahub, signed in as `mcp-agent`.

    **The account first, then the container**, because the container reads the
    account's password from `.env` at start. `scripts/provision_mcp_agent.py`
    creates `mcp-agent` -- read everything, write only on branches, open a
    proposed change -- and writes that password on first run. The upstream
    example signs in as `agent` instead, which here is a Super Administrator the
    task workers run as: a back door past the review gate for anything that can
    reach the port.

    The server listens on http://127.0.0.1:8001/mcp. Idempotent.
    """
    ctx.run("python scripts/provision_mcp_agent.py", pty=True)
    # --force-recreate so a password rotated in .env reaches a running container,
    # and --no-deps because without it the recreate cascades to infrahub-server.
    ctx.run(f"{compose_cmd()} --profile mcp up -d --no-deps --force-recreate infrahub-mcp", pty=True)
    print(" - Infrahub MCP server: http://127.0.0.1:8001/mcp")


@task
def metrics_exporter(ctx: Context) -> None:
    """
    Start the Infrahub exporter beside Infrahub, reading as `metrics-exporter`.

    The graph as Prometheus metrics, for Grafana's organisation dashboards:
    devices by family, services by status, tenants, proposed changes and
    deployment state. Prometheus in the workload cluster scrapes it at
    172.20.41.1:8002.

    **The account first, then the container**, because the container reads the
    account's token from `.env` at start. `scripts/provision_metrics_exporter.py`
    creates a view-only account and mints its token; the exporter never holds a
    Super Administrator's credential.

    Built from a pinned upstream commit, because none is published. Idempotent.

    Also starts the service-lifecycle exporter (cycle 035) on 8003, with the same
    token: every service request's stage, across branches, which the Infrahub
    exporter cannot report because it reads one branch. Telegraf scrapes it, as
    the `service-lifecycle` monitoring profile says.
    """
    ctx.run("python scripts/provision_metrics_exporter.py", pty=True)
    # --build, because the image comes from a git context and a first run has
    # none; --force-recreate so a re-minted token reaches a running container;
    # --no-deps so the recreate does not cascade to infrahub-server.
    ctx.run(
        f"{compose_cmd()} --profile metrics up -d --build --no-deps --force-recreate infrahub-exporter",
        pty=True,
    )
    # The service-lifecycle exporter (cycle 035), beside it and with the same
    # token. The project image, so no --build: it runs the bind-mounted checkout.
    ctx.run(
        f"{compose_cmd()} --profile metrics up -d --no-deps --force-recreate service-lifecycle-exporter",
        pty=True,
    )
    for url, marker, name, service in (
        ("http://127.0.0.1:8002/metrics", "infrahub_dcimgenericdevice_info", "Infrahub exporter", "infrahub-exporter"),
        (
            "http://127.0.0.1:8003/metrics",
            "otternet_service_lifecycle_up 1",
            "Service-lifecycle exporter",
            "service-lifecycle-exporter",
        ),
    ):
        # 300s for the lifecycle exporter: its first poll reads a day of events.
        deadline = time.time() + 300
        while time.time() < deadline:
            try:
                body = httpx.get(url, timeout=5).text
            except httpx.HTTPError:
                body = ""
            if marker in body:
                print(f" - {name}: {url}")
                break
            sleep(5)
        else:
            print(f" - WARNING: the {name} answered nothing useful in time; check `docker compose logs {service}`")


# `bootstrap` takes a --cluster flag, which shadows the task of the same name
# inside its body. Alias it here so the call site stays readable.
_cluster_task = cluster


@task(
    help={
        "branch": "Branch the AVD chain runs on before being merged. Created if absent.",
        "lab-dir": "Path to the lab. Defaults to OTTERNET_LAB_DIR, else lab/ in the main checkout.",
        "cluster": "Also bring up Kubernetes: Cilium, Vidra, Crossplane and the handover.",
        "fresh": "Destroy the stack and the lab first, so the run starts from nothing.",
    }
)
def bootstrap(
    ctx: Context, branch: str = "build-fabric", lab_dir: str = "", cluster: bool = True, fresh: bool = False
) -> None:
    """
    Bring the whole environment up, from nothing, in one command.

    Everything this project can automate, in the order the dependencies actually
    impose:

        start      the Infrahub stack
        load       schema, menus, seed data
        avd        the generation chain ON A BRANCH, merged to main, then deleted
        lab        the ContainerLab topology, management connectivity only
        provision  every device configured from its rendered artifact
        tooling    Dex and the Backstage portal, in the tooling cluster
        mcp        the Infrahub MCP server, signed in as `mcp-agent`
        metrics    the Infrahub exporter, reading as `metrics-exporter`
        cluster    Cilium, Vidra, Crossplane, the resource handover, and the
                   observability Secrets Grafana and Telegraf wait for

    **The chain runs on a branch and is merged here rather than by hand.** That
    is not ceremony: the topology generators write a great deal of derived data,
    and running them straight onto main leaves nowhere to see what changed --
    and no way back if they damage a fabric that already has cabling. The merge
    then waits for the artifacts to render, because generation is asynchronous
    and `provision` would otherwise push empty configuration onto the switches.

    Use `--fresh` to destroy the stack and the lab first. Without it the task is
    safe to re-run, with one exception worth stating: the topology generators
    inside `avd --topology` are destructive against a fabric that already has
    cabling, so a second bootstrap onto a populated instance wants `--fresh`.
    """
    if fresh:
        print("=== Destroying the lab ===")
        lab(ctx, lab_dir=lab_dir, destroy=True)
        print("\n=== Destroying the Infrahub stack ===")
        destroy(ctx)

    print("\n=== Starting Infrahub ===")
    start(ctx)
    _wait_for_infrahub()

    print("\n=== Loading schema, menus and seed data ===")
    load(ctx)

    print(f"\n=== Running the AVD chain on '{branch}' and merging it ===")
    avd(ctx, branch=branch, topology=True, merge=True)

    print("\n=== Deploying the lab ===")
    lab(ctx, lab_dir=lab_dir)

    print("\n=== Reconciling every device against Infrahub ===")
    # The reconciler rather than `provision`, so the bootstrap exercises the same
    # code path that keeps the fabric correct afterwards -- and so
    # `scripts/verify_bootstrap.sh` validates that path rather than a second one.
    #
    # `--converge` rather than a single cycle: a cold device differs, so the
    # first cycle pushes it, and `last_confirmed_at` deliberately does not move
    # on a push. Confirmation needs a later comparison that finds no difference,
    # so one cycle would leave the fabric correct but unconfirmed.
    reconcile(ctx, converge=True)

    # The tooling cluster, before the workload one. It does not need the fabric
    # -- that is the point of it -- but it does need the firewall configured, so
    # that a branch user can reach the portal the moment the bootstrap ends.
    print("\n=== Building the service portal ===")
    backstage_build(ctx)
    print("\n=== Deploying the tooling cluster ===")
    tooling(ctx)

    print("\n=== Starting the MCP server ===")
    mcp(ctx)

    # Before the cluster, so Prometheus has organisation metrics to scrape the
    # moment Grafana comes up, and verify_bootstrap.sh's dashboard check has
    # data rather than a first-scrape race.
    print("\n=== Starting the Infrahub exporter ===")
    metrics_exporter(ctx)

    if cluster:
        print("\n=== Bringing up Kubernetes ===")
        _cluster_task(ctx, lab_dir=lab_dir)

    # THE LOOP, not just the one-off convergence above. Without it a merge
    # reaches no device, and the deployment view keeps reporting the green it
    # recorded during the bootstrap -- a state that looks identical whether the
    # loop is running or was never started. `verify_bootstrap.sh` asserts the
    # container is up for exactly that reason.
    print("\n=== Starting the deployment reconciler ===")
    ctx.run(f"{compose_cmd()} --profile reconcile up -d deployment-reconciler", pty=True, warn=True)

    print("\n=== Bootstrap complete ===")
    print("   The lab is running and every device matches Infrahub.")
    if cluster:
        print("   Merging a service-layer change on main now reaches the cluster through Vidra.")


def _wait_for_infrahub(timeout: int = 600) -> None:
    """Block until the API answers, so the next step is not racing the stack."""
    print(" - Waiting for Infrahub to answer")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{INFRAHUB_ADDRESS}/api/config", timeout=5).status_code == 200:
                print("   reachable")
                return
        except httpx.HTTPError:
            pass
        sleep(10)
    raise SystemExit(f"Infrahub did not answer on {INFRAHUB_ADDRESS} within {timeout}s")


@task
def stop(ctx: Context) -> None:
    """
    Stop containers and remove networks, including the services behind a profile
    (see `destroy`).
    """
    ctx.run(f"{compose_cmd()} --profile '*' down", pty=True)


@task(help={"component": "Optional name of a specific service to restart."})
def restart(ctx: Context, component: str = "") -> None:
    """
    Restart all services or a specific one using docker-compose.
    """
    if component:
        ctx.run(f"{compose_cmd()} restart {component}", pty=True)
        return

    ctx.run(f"{compose_cmd()} restart", pty=True)


def _declared_menu_identifiers() -> set[str]:
    """`namespace + name` of every entry in menus/*.yml, at any depth."""
    import yaml

    found: set[str] = set()

    def walk(items: list[dict[str, Any]]) -> None:
        for item in items:
            found.add(f"{item['namespace']}{item['name']}")
            walk((item.get("children") or {}).get("data") or [])

    for path in sorted((MAIN_DIRECTORY_PATH / "menus").glob("*.yml")):
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if isinstance(doc, dict) and doc.get("kind") == "Menu":
                walk(doc["spec"]["data"])
    return found


def _prune_menu(branch: str = "") -> None:
    """Delete menu items the repository no longer declares.

    `infrahubctl menu load` and the repository import both UPSERT by
    namespace + name and delete nothing, so an entry renamed or removed in
    menus/menu.yml stays in the sidebar under its old name -- a duplicate, or
    an empty section header. Infrahub's own items (namespace `Builtin`,
    `protected`) are never touched.
    """
    declared = _declared_menu_identifiers()
    if not declared:
        print(" - No menu entries declared; refusing to prune everything.")
        return
    data = _graphql(
        "{ CoreMenuItem { edges { node { id namespace { value } name { value } protected { value } } } } }",
        branch,
    )
    stale = [
        edge["node"]
        for edge in (data.get("CoreMenuItem") or {}).get("edges", [])
        if not edge["node"]["protected"]["value"]
        and edge["node"]["namespace"]["value"] != "Builtin"
        and f"{edge['node']['namespace']['value']}{edge['node']['name']['value']}" not in declared
    ]
    for node in stale:
        _graphql(f'mutation {{ CoreMenuItemDelete(data: {{ id: "{node["id"]}" }}) {{ ok }} }}', branch)
        print(f" - Pruned stale menu item {node['namespace']['value']}{node['name']['value']}")


@task(help={"branch": "Branch to load onto (default main)", "prune": "Delete items menus/ no longer declares"})
def load_menu(ctx: Context, branch: str = "", prune: bool = True) -> None:
    """Load the menu into Infrahub using infrahubctl, then prune stale items."""
    branch_arg = f" --branch {shlex.quote(branch)}" if branch else ""
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(f"infrahubctl menu load menus/{branch_arg}", pty=True)
    if prune:
        _prune_menu(branch)


@task
def load_schema(ctx: Context) -> None:
    """Load schemas into Infrahub using infrahubctl."""
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run("infrahubctl schema load schemas", pty=True)


@task
def doctor(ctx: Context) -> None:  # noqa: ARG001
    """
    Check the environment for the known quiet failures; exit 1 on any FAIL.

    Stale reconciler image, a stray reconcile process, a stale schema.graphql, a
    wedged repository sync, dangling generator instances, branches syncing with
    git, and a missing tooling bridge. A check that cannot run (stack down) is
    reported as SKIP. The logic lives in solution_arista_avd.doctor.
    """
    from solution_arista_avd import doctor as checks

    results = checks.run_checks(checks.Environment(root=compose_root()))
    for result in results:
        print(result.render())
    print(f"\n{checks.summary(results)}")
    if checks.exit_code(results):
        raise Exit(code=1)


@task(help={"integration": "Also run tests/integration, which starts an Infrahub stack in Docker (minutes)."})
def test(ctx: Context, integration: bool = False) -> None:
    """Run the unit tests -- what CI runs -- and optionally the integration suite."""
    target = "tests" if integration else "tests/unit"
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(f"pytest {target}", pty=True)


@task(
    help={
        "proposed_change_id": "Submitted proposed change ID.",
        "branch": "Destination branch containing workspace tracking.",
    }
)
def submit_cv_workspace(ctx: Context, proposed_change_id: str, branch: str = "main") -> None:
    """Manually retry CloudVision submission for a linked submitted proposed change."""
    command = (
        f"python -m checks.cv_workspace_lifecycle {shlex.quote(proposed_change_id)} --branch {shlex.quote(branch)}"
    )
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(command, pty=True)


@task
def docs(ctx: Context) -> None:
    """Build the documentation site."""
    print(" - Build the Docusaurus site")
    exec_cmds = ["pnpm install --frozen-lockfile", "pnpm run build"]
    with ctx.cd(MAIN_DIRECTORY_PATH / "docs"):
        for cmd in exec_cmds:
            ctx.run(cmd, pty=True)


@task(name="format")
def format_python(ctx: Context) -> None:
    """Run RUFF to format all Python files."""

    exec_cmds = ["ruff format .", "ruff check . --fix", f"rumdl fmt {MARKDOWN_PATHS}"]
    with ctx.cd(MAIN_DIRECTORY_PATH):
        for cmd in exec_cmds:
            ctx.run(cmd, pty=True)


@task
def lint_yaml(ctx: Context) -> None:
    """Run yamllint over every YAML file."""
    print(" - Check code with yamllint")
    exec_cmd = "yamllint ."
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(exec_cmd, pty=True)


@task
def lint_mypy(ctx: Context) -> None:
    """Type-check the library with mypy, the gate CI enforces.

    CI also runs mypy over `generators` and `transforms`, advisory only: they
    are not yet fully typed. Run `mypy generators transforms` to see that.
    """
    print(" - Check code with mypy")
    exec_cmd = "mypy --show-error-codes src/solution_arista_avd"
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(exec_cmd, pty=True)


@task
def lint_ruff(ctx: Context) -> None:
    """Run Ruff lint and format checks for all Python files."""
    exec_cmds = [
        (" - Check code with ruff", "ruff check ."),
        (" - Check code formatting with ruff", "ruff format --check ."),
    ]
    with ctx.cd(MAIN_DIRECTORY_PATH):
        for message, cmd in exec_cmds:
            print(message)
            ctx.run(cmd, pty=True)


@task
def lint_markdown(ctx: Context) -> None:
    """Run Linter to check authored Markdown files."""
    print(" - Check Markdown with rumdl")
    exec_cmd = f"rumdl check {MARKDOWN_PATHS}"
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(exec_cmd, pty=True)


@task
def lint_prose(ctx: Context) -> None:
    """Run Linter to check documentation prose."""
    print(" - Check prose with Vale")
    if not shutil.which("vale"):
        # Vale is a Go binary with no PyPI distribution, so `uv sync` cannot
        # provide it. Skip rather than fail, so contributors without it can still
        # run the rest of the suite; CI installs it and remains the gate.
        print(
            f"   skipped: vale not found on PATH. Install v{VALE_VERSION} from "
            "https://github.com/errata-ai/vale/releases, then run `vale sync`."
        )
        return
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run("vale sync", pty=True)
        ctx.run(f"vale {PROSE_PATHS}", pty=True)


@task(name="lint")
def lint_all(ctx: Context) -> None:
    """Run all linters."""
    lint_yaml(ctx)
    lint_ruff(ctx)
    lint_mypy(ctx)
    lint_markdown(ctx)
    lint_prose(ctx)


@task
def start(ctx: Context) -> None:
    """
    Start the services using docker-compose in detached mode.
    """
    ctx.run(f"{compose_cmd()} up -d", pty=True)
