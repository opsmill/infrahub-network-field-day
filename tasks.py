import json
import os
import shlex
import shutil
import sys
import time
from pathlib import Path
from time import sleep

import httpx
from invoke import Context, task

# If no version is indicated, we will take the latest
VERSION = os.getenv("INFRAHUB_IMAGE_VER", None)
CURRENT_DIRECTORY = Path(__file__).resolve()
MAIN_DIRECTORY_PATH = Path(__file__).parent

COMPOSE_FILES = "-f docker-compose.yml -f docker-compose.override.yml"
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
    compose_cmd = f"docker compose {COMPOSE_FILES} build"
    if not cache:
        compose_cmd += " --no-cache"
    with ctx.cd(MAIN_DIRECTORY_PATH):
        ctx.run(compose_cmd, pty=True)


@task
def destroy(ctx: Context) -> None:
    """
    Stop and remove containers, networks, and volumes.
    """
    ctx.run(f"docker compose {COMPOSE_FILES} down -v", pty=True)


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
    }
)
def avd(ctx: Context, branch: str = "", topology: bool = False, artifacts: bool = True) -> None:
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

    generators = (*TOPOLOGY_GENERATORS, *AVD_GENERATORS) if topology else AVD_GENERATORS
    if topology:
        print(" - Building topology as well (destructive against an existing fabric)")

    for generator in generators:
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

    if branch:
        print(f"\n - Done on '{branch}'. Review the diff, then merge with `infrahubctl branch merge {branch}`.")


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

# The lab's own two applications, which Infrahub does not model. They stay the
# lab's, and the operator never sees them: it only ever deletes a resource that
# leaves a manifest it delivered itself.
LAB_OWNED_APPS = ("nfd41-access", "nfd41-observability")


def _lab_kubeconfig(lab_dir: str = "") -> Path:
    return find_lab_directory(lab_dir) / "k8s/.kubeconfig/kubeconfig.yaml"


@task(
    help={
        "lab-dir": "Path to the lab repository. Defaults to NFD41_LAB_DIR, else a search beside this checkout.",
        "handover": "Delete the lab's copies of the resources Infrahub models, so Vidra can own them.",
    }
)
def cluster(ctx: Context, lab_dir: str = "", handover: bool = True) -> None:
    """
    Bring up the Kubernetes half: Cilium, then Crossplane and the platform APIs.

    Both installers belong to the lab repository and are run from here rather
    than reimplemented -- the CNI and the Crossplane compositions are the lab's,
    the same way the topology is.

    Cilium has to come first and cannot be managed by Crossplane: it *is* the pod
    network, so a controller that needs a pod network to run cannot be the thing
    that creates one. The k3s nodes sit NotReady until it lands, which is
    expected rather than a fault.

    `--handover` (the default) then deletes the two claims the lab's bootstrap
    applied which Infrahub models -- the demo application and the fabric peering.
    They are recreated by `invoke vidra` from Infrahub's own artifacts, which is
    the point of the exercise. Pass `--no-handover` to leave the lab in charge of
    them and skip Vidra entirely.
    """
    lab_path = find_lab_directory(lab_dir)
    kubeconfig = _lab_kubeconfig(lab_dir)
    print(f" - Lab repository: {lab_path}")

    print(" - Installing Cilium (the CNI; nodes stay NotReady until it is ready)")
    ctx.run(f"{shlex.quote(str(lab_path / 'k8s/bootstrap/install-cilium.sh'))}", pty=True)

    print(" - Installing Crossplane, the providers, the XRDs and the compositions")
    ctx.run(f"{shlex.quote(str(lab_path / 'k8s/bootstrap/install-crossplane.sh'))}", pty=True)

    if handover:
        print("\n - Handing the Infrahub-modelled resources over to Vidra")
        for kind, name in INFRAHUB_OWNED_RESOURCES:
            ctx.run(
                f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))} delete {kind} {name} --ignore-not-found",
                pty=True,
                warn=True,
            )
        print(f"   The lab keeps {', '.join(LAB_OWNED_APPS)}; Infrahub owns the two above.")

    print("\n - Cluster ready. Install the operator with `invoke vidra`.")


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


def _wait_for_syncs(ctx: Context, kubeconfig: Path, timeout: int = 300) -> None:
    """Report each sync's state, and what it actually delivered.

    `syncState: Succeeded` is not evidence that anything arrived -- the sync
    compares a checksum, and an `artefactName` that does not match
    `.infrahub.yml` exactly returns an empty set, which succeeds. So the
    VidraResource count is printed alongside it; that is the number that answers
    "did it deliver?".
    """
    kube = f"kubectl --kubeconfig {shlex.quote(str(kubeconfig))}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = ctx.run(
            f"{kube} get infrahubsync -o jsonpath="
            '\'{range .items[*]}{.metadata.name}{"\\t"}{.status.syncState}{"\\n"}{end}\'',
            hide=True,
            warn=True,
        )
        rows = [r for r in (result.stdout or "").strip().splitlines() if r.strip()]
        if rows and all(r.split("\t")[-1] in {"Succeeded", "Failed"} for r in rows):
            break
        sleep(10)

    ctx.run(
        f"{kube} get infrahubsync -o custom-columns="
        "NAME:.metadata.name,STATE:.status.syncState,LAST:.status.lastSyncTime,ERROR:.status.lastError",
        pty=True,
        warn=True,
    )
    print("\n - Delivered resources (this is the number that answers 'did it arrive?'):")
    ctx.run(
        f"{kube} get vidraresource -o custom-columns=NAME:.metadata.name,STATE:.status.DeployState",
        pty=True,
        warn=True,
    )


@task
def stop(ctx: Context) -> None:
    """
    Stop containers and remove networks.
    """
    ctx.run(f"docker compose {COMPOSE_FILES} down", pty=True)


@task(help={"component": "Optional name of a specific service to restart."})
def restart(ctx: Context, component: str = "") -> None:
    """
    Restart all services or a specific one using docker-compose.
    """
    if component:
        ctx.run(f"docker compose {COMPOSE_FILES} restart {component}", pty=True)
        return

    ctx.run(f"docker compose {COMPOSE_FILES} restart", pty=True)


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
    ctx.run(f"docker compose {COMPOSE_FILES} up -d", pty=True)
