import json
import os
import shlex
import shutil
import subprocess  # noqa: S404 - one fixed-argv git call, never a shell string
import sys
import time
from collections.abc import Callable
from pathlib import Path
from time import sleep
from typing import Any

import httpx
from invoke import Context, Exit, task

# If no version is indicated, we will take the latest
VERSION = os.getenv("INFRAHUB_IMAGE_VER", None)
CURRENT_DIRECTORY = Path(__file__).resolve()
MAIN_DIRECTORY_PATH = Path(__file__).parent

COMPOSE_FILES = "-f docker-compose.yml -f docker-compose.override.yml"


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
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=MAIN_DIRECTORY_PATH,
    )
    if result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = (MAIN_DIRECTORY_PATH / common).resolve()
        if common.name == ".git":
            return common.parent
    return MAIN_DIRECTORY_PATH


def compose_cmd() -> str:
    """`docker compose` pinned to the stack's real project directory."""
    root = compose_root()
    return (
        f"docker compose --project-directory {shlex.quote(str(root))} "
        f"-f {shlex.quote(str(root / 'docker-compose.yml'))} "
        f"-f {shlex.quote(str(root / 'docker-compose.override.yml'))}"
    )


INFRAHUB_ADDRESS = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")

os.environ.setdefault("INFRAHUB_USERNAME", "admin")
os.environ.setdefault("INFRAHUB_PASSWORD", "infrahub")
os.environ.setdefault("INFRAHUB_ADDRESS", INFRAHUB_ADDRESS)

SEMAPHORE_URL = "http://localhost:3000"
SEMAPHORE_ADMIN = "admin"
SEMAPHORE_ADMIN_PASSWORD = "semaphore"  # noqa: S105
SEMAPHORE_PLAYBOOK_PATH = "/opt/semaphore/playbooks"
# Host path bind-mounted into the Semaphore container as the ContainerLab
# staging directory, so files deploy_clab.yml pulls are reachable from the host.
CLAB_STAGING_DIR = "lab/clab-staging"

# The committed ContainerLab topology this project provisions, in the sibling
# NFD41 lab repository. That repository owns the topology -- which nodes exist
# and how they are wired -- and this one owns their configuration.
LAB_TOPOLOGY = "nfd41.clab.yml"

# Image variables the topology interpolates. ContainerLab runs under sudo, which
# scrubs the environment, so they have to be named to survive.
CLAB_ENV_PASSTHROUGH = "NFD41_CEOS_IMAGE,NFD41_CEOS_MEMORY,NFD41_VSRX_IMAGE,NFD41_FRR_IMAGE,NFD41_GUACAMOLE_IMAGE"

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
    """
    ctx.run(f"{compose_cmd()} down -v", pty=True)


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


def ensure_clab_staging_dir() -> Path:
    """Create the ContainerLab staging directory the Semaphore container writes to.

    docker-compose.override.yml bind-mounts this into the container, so the files
    deploy_clab.yml pulls land on the host instead of a container layer that is
    discarded on recreate.

    It must exist *before* the container is created, and must be writable by both
    the container's uid and the host user's, which differ. Getting either wrong
    fails without naming the cause:

      - absent at container start: Docker creates it owned by root, and the
        staging write fails with EACCES.
      - mode 0755: the same EACCES, because the container's uid is not the owner.
      - deleted while the container runs: the container keeps a stale mountpoint
        and every path under it fails with ENOENT, which takes a container
        recreate to fix - and that discards Semaphore's sqlite state.

    Called from both `start` and `init-semaphore` so the ordering holds either
    way. Staging inside the lab/ mount instead was tried and does not work: a
    writable bind mount still obeys POSIX permissions, so the container cannot
    mkdir inside a host directory it does not own.
    """
    staging_dir = Path(__file__).parent / CLAB_STAGING_DIR
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.chmod(0o777)
    print(f"Staging directory {CLAB_STAGING_DIR} ready (mode 0777, shared with the Semaphore container).")
    return staging_dir


def _semaphore_staging_host_path(context: Context, container_path: str) -> str:
    """Host path backing the Semaphore container's staging directory.

    Asks Docker for the real bind source rather than assuming it matches this
    checkout. They diverge whenever the stack was started from a different
    directory — a git worktree being the obvious case — and a wrong path here is
    worse than none, because it sends people to an empty directory that looks
    like a failed run.
    """
    fallback = str((Path(__file__).parent / CLAB_STAGING_DIR).resolve())
    fmt = "{{range .Mounts}}{{if eq .Destination " + f'"{container_path}"' + "}}{{.Source}}{{end}}{{end}}"
    result = context.run(
        f"docker inspect $(docker ps -q --filter name=semaphore | head -1) --format '{fmt}'",
        hide=True,
        warn=True,
    )
    if result and result.ok and result.stdout.strip():
        return str(result.stdout.strip())
    return fallback


@task(name="init-semaphore")
def init_semaphore(
    context: Context,
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
    ensure_clab_staging_dir()

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

    print("ContainerLab inventory...")
    # deploy_clab.yml targets localhost plus the `clab_hosts` group, not the
    # Infrahub dynamic inventory of DcimDevice objects.
    clab_inv_id = api.find_or_create(
        f"/api/project/{project_id}/inventory",
        f"/api/project/{project_id}/inventory",
        "ContainerLab",
        {
            "name": "ContainerLab",
            "project_id": project_id,
            "inventory": "inventory_clab.yml",
            "type": "file",
            "ssh_key_id": key_id,
        },
    )

    print("ContainerLab environment...")
    clab_container_staging = f"{SEMAPHORE_PLAYBOOK_PATH.rsplit('/', 1)[0]}/clab-staging"
    # The variables deploy_clab.yml needs must live in the environment, NOT in
    # survey_vars. Verified against Semaphore v2.17.12: a declared survey var is
    # recorded on the task's `params` but is never forwarded to ansible-playbook
    # as an extra var, so the playbook fails with "fabric is undefined" — with or
    # without an explicit `type` on the survey var. Only the environment's JSON
    # reaches the playbook. Override per run in the task's Environment field.
    #
    # clab_staging_dir is deliberately not the playbook's /opt/containerlab
    # default: with clab_hosts resolving to localhost, that localhost is this
    # container, which cannot write to /opt. This path is owned by the semaphore
    # user. A real deployment points clab_hosts at a ContainerLab host and
    # overrides this.
    clab_env_id = api.find_or_create(
        f"/api/project/{project_id}/environment",
        f"/api/project/{project_id}/environment",
        "ContainerLab",
        {
            "name": "ContainerLab",
            "project_id": project_id,
            "json": json.dumps(
                {
                    "fabric": "NFD41_FABRIC",
                    "clab_staging_dir": clab_container_staging,
                    # Reported back by the playbook so a run tells you where the
                    # files are on the Docker host, not just inside the container.
                    "clab_staging_host_dir": _semaphore_staging_host_path(context, clab_container_staging),
                }
            ),
            "env": "{}",
        },
    )

    print("ContainerLab task template...")
    # Runs with --skip-tags deploy, so Semaphore fetches the artifacts, stages
    # every file the topology references, and validates them - but does not run
    # `containerlab deploy`. That step cannot work from here: this container has
    # no containerlab binary and no Docker socket, so an unskipped run always
    # ends on the "containerlab is not on PATH" assertion.
    #
    # To deploy, point clab_hosts (ansible/inventory_clab.yml) at a ContainerLab
    # host reachable over SSH and clear the arguments below, or run
    # `make -C lab deploy-from-infrahub FABRIC=<name>` from a checkout.
    api.find_or_create(
        f"/api/project/{project_id}/templates",
        f"/api/project/{project_id}/templates",
        "Fetch ContainerLab Files",
        {
            "name": "Fetch ContainerLab Files",
            "project_id": project_id,
            "repository_id": repo_id,
            "inventory_id": clab_inv_id,
            "environment_id": clab_env_id,
            "playbook": "deploy_clab.yml",
            "type": "task",
            "app": "ansible",
            "arguments": json.dumps(["--skip-tags", "deploy"]),
            "allow_override_args_in_task": True,
        },
    )

    print("=== Semaphore init complete ===")


def get_repository_sync_status(name: str) -> str | None:
    query = """
    query CheckRepoSync($name: String!) {
      CoreRepository(name__value: $name) {
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
    edges = data.get("data", {}).get("CoreRepository", {}).get("edges", [])
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
    ctx.run("infrahubctl object load repository.yml")
    wait_for_repository_sync("test-repository")
    ctx.run("infrahubctl object load repository_checks.yml")
    ctx.run("infrahubctl object load triggers.yml")
    # Application payloads are CoreFileObject attachments, and `object load`
    # cannot upload file content. Without this an application loads with no
    # workload and its Crossplane artifact renders an empty manifests list.
    ctx.run("python scripts/seed_app_payloads.py --branch main")


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
        "merge": "Merge the branch into main when the chain succeeds, then wait for the artifacts to render.",
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
        print(f"\n - Merged. Main now carries the chain's output; '{branch}' can be deleted.")
    elif branch:
        print(f"\n - Done on '{branch}'. Review the diff, then merge with `invoke avd --branch {branch} --merge`.")


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
    names = ("AVD EOS Configuration", "FRR Configuration", "Junos Configuration")
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


def find_lab_directory(explicit: str = "") -> Path:
    """Locate the sibling NFD41 lab repository.

    `../lab` is right from a normal checkout and wrong from a git worktree, where
    the repository root sits several levels deeper under `.emdash/worktrees/`.
    Rather than hard-code either, walk up from this file looking for a directory
    holding the topology. Set NFD41_LAB_DIR to override.
    """
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not (candidate / LAB_TOPOLOGY).is_file():
            raise SystemExit(f"No {LAB_TOPOLOGY} in {candidate}")
        return candidate

    if env_dir := os.getenv("NFD41_LAB_DIR"):
        return find_lab_directory(env_dir)

    for parent in [MAIN_DIRECTORY_PATH.resolve(), *MAIN_DIRECTORY_PATH.resolve().parents]:
        candidate = parent.parent / "lab"
        if (candidate / LAB_TOPOLOGY).is_file():
            return candidate.resolve()

    raise SystemExit(
        f"Could not find the lab repository. Looked for a directory containing {LAB_TOPOLOGY} "
        "beside this checkout and each of its parents. Set NFD41_LAB_DIR to point at it."
    )


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
        "lab-dir": "Path to the lab repository. Defaults to NFD41_LAB_DIR, else a search beside this checkout.",
        "destroy": "Tear the lab down instead of deploying it.",
        "wait": "Block until every fabric switch answers eAPI before returning.",
    }
)
def lab(ctx: Context, lab_dir: str = "", destroy: bool = False, wait: bool = True) -> None:
    """
    Bring up the ContainerLab topology with management connectivity.

    Deploys the sibling lab repository's committed topology as-is. That
    repository owns which nodes exist and how they are wired; this one owns their
    configuration. Nothing here renders a topology.

    The fabric comes up **unconfigured on purpose**. The cEOS nodes are given no
    `startup-config` -- only `CLAB_MGMT_VRF` and a management address -- so they
    boot reachable and empty, which is exactly the state `invoke provision` then
    fills from Infrahub. The firewall and the FRR routers boot from the lab
    repository's own files and are re-provisioned from Infrahub the same way.

    Run `invoke provision` next.
    """
    lab_path = find_lab_directory(lab_dir)
    topology = lab_path / LAB_TOPOLOGY
    print(f" - Lab repository: {lab_path}")

    # ContainerLab needs root for netns and bridge work; --preserve-env keeps the
    # image variables the topology interpolates.
    clab = f"sudo --preserve-env={CLAB_ENV_PASSTHROUGH} containerlab"

    if destroy:
        print(f" - Destroying lab from {topology.name}")
        ctx.run(f"{clab} destroy -t {shlex.quote(str(topology))} --cleanup", pty=True)
        return

    # THE TOOLING BRIDGE, BEFORE THE DEPLOY, and it is not optional.
    #
    # `br-nfd41-tool` is a `kind: bridge` node, which means ContainerLab expects
    # the HOST to already have it -- it does not create one. A missing bridge is
    # refused outright, before any node starts:
    #
    #   ERROR  Bridge "br-nfd41-tool" referenced in topology but does not exist.
    #
    # A host bridge does not survive a reboot, so this is not a once-per-machine
    # setup step; it is a precondition of every deploy. The script is idempotent
    # and also lays down the route back to the branch LAN, which is why it runs
    # here rather than being left to whoever remembers.
    bridge = lab_path / "scripts/tooling-bridge.sh"
    if bridge.is_file():
        print(" - Ensuring the tooling bridge exists")
        ctx.run(shlex.quote(str(bridge)), pty=True)

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
        "kind": "Provision one family only: eos, frr, or junos.",
    }
)
def provision(ctx: Context, branch: str = "", dry_run: bool = False, only: str = "", kind: str = "") -> None:
    """
    Push Infrahub's rendered configuration onto the running lab.

    The second half of the bring-up: `invoke lab` gives every device management
    connectivity, and this makes each one match the artifact Infrahub rendered
    for it -- EOS switches over eAPI, the firewall and the FRR routers through
    their containers.

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
) -> None:
    """
    Reconcile the running lab against Infrahub, continuously.

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
    ("fabricapp", "nfd41-demo"),
    ("fabricpeering", "nfd41"),
)

# The lab's own two applications, which Infrahub does not model: the access
# broker and the kube-prometheus-stack. The handover deletes them, so a finished
# bootstrap carries only the applications Infrahub declares -- an unmodelled
# application in the cluster is state no proposed change can explain, and both of
# these predate the service layer that now requests applications.
#
# Vidra never sees them either way; it only ever deletes a resource that leaves a
# manifest it delivered itself. They are the lab's installer's, and deleting them
# here is the only seam: `install-crossplane.sh` has no flag to skip a claim, so
# they are applied, waited on, and then removed.
LAB_ONLY_APPS = ("nfd41-access", "nfd41-observability")

# Everything the handover deletes: the two the lab declares and Infrahub owns,
# which Vidra then re-delivers, and the two that simply go.
HANDOVER_DELETIONS = INFRAHUB_OWNED_RESOURCES + tuple(("fabricapp", name) for name in LAB_ONLY_APPS)

# The namespace the demo application composes. Waiting on this, rather than on
# composed-object names, is what makes the teardown check correct -- see
# _wait_for_teardown.
APP_NAMESPACE = "nfd41-demo"


class _Missing:
    """Stands in for a command that did not run, so `.ok` is always answerable."""

    ok = False


MISSING = _Missing()


def _lab_kubeconfig(lab_dir: str = "") -> Path:
    return find_lab_directory(lab_dir) / "k8s/.kubeconfig/kubeconfig.yaml"


@task(
    help={
        "lab-dir": "Path to the lab repository. Defaults to NFD41_LAB_DIR, else a search beside this checkout.",
        "handover": "Delete the lab's claims, so the cluster carries only what Infrahub declares.",
    }
)
def cluster(ctx: Context, lab_dir: str = "", handover: bool = True) -> None:
    """
    Bring up the Kubernetes half: Cilium, then Vidra, then Crossplane.

    The installers for the CNI and Crossplane belong to the lab repository and
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
    print(f" - Lab repository: {lab_path}")

    print(" - Installing Cilium (the CNI; nodes stay NotReady until it is ready)")
    ctx.run(f"{shlex.quote(str(lab_path / 'k8s/bootstrap/install-cilium.sh'))}", pty=True)

    _wait_for_cluster_dns(ctx, kubeconfig)

    print(" - Installing Vidra before the platform, so it owns what it delivers")
    ctx.run("scripts/install_vidra.sh", pty=True, env={"KUBECONFIG": str(kubeconfig)})

    print(" - Installing Crossplane, the providers, the XRDs and the compositions")
    ctx.run(f"{shlex.quote(str(lab_path / 'k8s/bootstrap/install-crossplane.sh'))}", pty=True)

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

    print("\n - Cluster ready.")


@task(
    help={
        "lab-dir": "Path to the lab repository. Defaults to NFD41_LAB_DIR, else a search beside this checkout.",
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
        create new content in namespace nfd41-demo because it is being terminated

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
        # named `<claim>-<hash>`, and the peering claim is called `nfd41`, which is
        # a prefix of `nfd41-access-...` and `nfd41-observability-...` too. Those
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

    Measured, not supposed: after the handover deleted `fabricapp/nfd41-demo`
    and `fabricpeering/nfd41`, both syncs read `Succeeded` and both resources
    stayed absent.

    Deleting and re-applying the InfrahubSync resets its checksum state, and
    delivery follows within seconds. Deleting the *VidraResource* instead does
    not work -- the sync still considers itself current and never re-applies.
    """
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    syncs = MAIN_DIRECTORY_PATH / "vidra/infrahub-syncs.yaml"
    print(" - Resetting the syncs so Vidra re-delivers (an unchanged checksum would skip the apply)")
    ctx.run(f"{kube} delete -f {shlex.quote(str(syncs))} --ignore-not-found --timeout=120s", pty=True, warn=True)
    ctx.run(f"{kube} apply -f {shlex.quote(str(syncs))}", pty=True, warn=True)


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

    So the loop asks the API server whether `fabricapp/nfd41-demo` and
    `fabricpeering/nfd41` are there, and the sync table is printed afterwards as
    context rather than as the verdict.
    """
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    deadline = time.time() + timeout
    missing: list[str] = []
    while time.time() < deadline:
        missing = []
        for kind, name in INFRAHUB_OWNED_RESOURCES:
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
        f"{kube} get {','.join(k for k, _ in INFRAHUB_OWNED_RESOURCES)}",
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
    ctx.run("scripts/deploy_tooling.sh", pty=True)


# `bootstrap` takes a --cluster flag, which shadows the task of the same name
# inside its body. Alias it here so the call site stays readable.
_cluster_task = cluster


@task(
    help={
        "branch": "Branch the AVD chain runs on before being merged. Created if absent.",
        "lab-dir": "Path to the lab repository. Defaults to NFD41_LAB_DIR, else a search beside this checkout.",
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
        avd        the generation chain ON A BRANCH, then merged to main
        lab        the ContainerLab topology, management connectivity only
        provision  every device configured from its rendered artifact
        tooling    Dex and the Backstage portal, in the tooling cluster
        cluster    Cilium, Vidra, Crossplane, and the resource handover

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

    if cluster:
        print("\n=== Bringing up Kubernetes ===")
        _cluster_task(ctx, lab_dir=lab_dir)

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
    Stop containers and remove networks.
    """
    ctx.run(f"{compose_cmd()} down", pty=True)


@task(help={"component": "Optional name of a specific service to restart."})
def restart(ctx: Context, component: str = "") -> None:
    """
    Restart all services or a specific one using docker-compose.
    """
    if component:
        ctx.run(f"{compose_cmd()} restart {component}", pty=True)
        return

    ctx.run(f"{compose_cmd()} restart", pty=True)


@task
def load_menu(ctx: Context) -> None:
    """
    Load schemas into InfraHub using infrahubctl.
    """
    ctx.run("infrahubctl menu load menus/", pty=True)


@task
def load_schema(ctx: Context) -> None:
    """
    Load schemas into InfraHub using infrahubctl.
    """
    ctx.run("infrahubctl schema load schemas", pty=True)


@task
def test(ctx: Context) -> None:
    """
    Run tests using pytest.
    """
    ctx.run("pytest tests", pty=True)


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


@task(help={"override": "Redownload the compose file even if it already exists."})
def download_compose_file(ctx: Context, override: bool = False) -> Path:  # noqa: ARG001
    """
    Download docker-compose.yml from InfraHub if missing or override is True.
    """
    compose_file = Path("./docker-compose.yml")

    if compose_file.exists() and not override:
        return compose_file

    response = httpx.get("https://infrahub.opsmill.io")
    response.raise_for_status()

    compose_file.write_text(response.content.decode(), encoding="utf-8")

    return compose_file


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
    """Run Linter to check all Python files."""
    print(" - Check code with yamllint")
    exec_cmd = "yamllint ."
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(exec_cmd, pty=True)


@task
def lint_mypy(ctx: Context) -> None:
    """Run Linter to check all Python files."""
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
    # Before compose creates the containers: a bind-mount source that does not
    # exist yet is created by Docker as root, which the Semaphore container then
    # cannot write to.
    ensure_clab_staging_dir()
    ctx.run(f"{compose_cmd()} up -d", pty=True)
