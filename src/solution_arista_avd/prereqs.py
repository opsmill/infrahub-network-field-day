"""Host prerequisites for `invoke bootstrap`, checked before anything is built or destroyed.

A missing tool or image used to surface only at the step that needed it: ContainerLab at the lab
step, Node at the portal build, `kubectl` at the cluster step. By then the stack had been destroyed
and rebuilt and the AVD chain had run, about fifteen minutes in. These checks run first, so a new
machine learns everything it lacks in one list.

Each check returns a `Result`; nothing here raises or exits, so the checks are testable without a
real host. `run_checks` takes the probes as arguments for the same reason.
"""

from __future__ import annotations

import re
import shutil
import subprocess  # noqa: S404 - fixed-argv calls, never a shell string
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

OK = "ok"
WARN = "warn"
FAIL = "FAIL"

# The full lab needs about 36.5 GB for its nodes (lab/scripts/preflight.sh). The Infrahub stack,
# the reconciler and the portal build add roughly 10 GB on top.
LAB_MEMORY_GB = 48
# --no-lab: the stack, plus the 3 GB tooling node (Dex, the portal).
INFRAHUB_MEMORY_GB = 12
NODE_MAJOR_VERSIONS = (22, 24)
# Measured on a full environment: about 20 GB of images, 12 GB of volumes, 10 GB of build cache, and
# the k3s nodes' own images on top. A first run on an empty machine needs about this much free.
FIRST_RUN_DISK_GB = 60
MINIMUM_DISK_GB = 20
# Host ports the stack publishes (docker-compose*.yml; backstage's 3001 is build-only and never runs)
# and the one the lab publishes (Guacamole in lab/otternet.clab.yml).
STACK_PORTS = (2004, 3000, 4200, 6362, 7474, 7687, 8000, 8001, 8002, 8003, 15692)
LAB_PORTS = (8080,)
# Sites the run downloads from. Infrahub alone needs the first group; the lab and the clusters need
# the second. Any HTTP answer counts as reachable: only a timeout or a refused connection does not.
INFRAHUB_SITES = ("registry.opsmill.io", "registry-1.docker.io", "github.com", "pypi.org")
LAB_SITES = (
    "ghcr.io",
    "quay.io",
    "registry.yarnpkg.com",
    "helm.cilium.io",
    "charts.crossplane.io",
    "infrahub-operator.github.io",
)
# Containers of this environment: a port they hold is freed and taken again by bootstrap itself.
OWN_CONTAINER_PREFIXES = ("infrahub-", "clab-otternet-")
# lab/scripts/host-limits.sh raises the inotify limits to these before every deploy. The cEOS
# switches raise them much further when they boot, but the k3s nodes start at the same time.
INOTIFY_MINIMUM = {"fs.inotify.max_user_instances": 8192, "fs.inotify.max_user_watches": 1048576}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class Result:
    status: str
    name: str
    detail: str = ""


Which = Callable[[str], str | None]
Runner = Callable[[list[str]], tuple[int, str]]


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _memory_gb(meminfo: Path = Path("/proc/meminfo")) -> float | None:
    try:
        match = re.search(r"^MemTotal:\s+(\d+) kB", meminfo.read_text(encoding="utf-8"), re.MULTILINE)
    except OSError:
        return None
    return int(match.group(1)) / 1024 / 1024 if match else None


def check_tool(name: str, why: str, which: Which, install: str = "") -> Result:
    if which(name):
        return Result(OK, name)
    hint = f" -- {install}" if install else ""
    return Result(FAIL, name, f"missing; needed for {why}{hint}")


def check_docker(which: Which, run: Runner) -> list[Result]:
    if not which("docker"):
        return [Result(FAIL, "docker", "missing -- https://docs.docker.com/engine/install/")]
    results = []
    code, out = run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if code:
        results.append(
            Result(
                FAIL, "docker daemon", "not usable without sudo -- add yourself to the docker group, then log in again"
            )
        )
    else:
        results.append(Result(OK, "docker daemon", out))
    code, out = run(["docker", "compose", "version", "--short"])
    if code:
        results.append(Result(FAIL, "docker compose", "the Compose v2 plugin is missing"))
    else:
        results.append(Result(OK, "docker compose", out))
    return results


def check_node(which: Which, run: Runner) -> Result:
    if not which("node"):
        return Result(FAIL, "node", "missing; the service portal is built with Node 22 or 24 -- https://nodejs.org")
    code, out = run(["node", "--version"])
    match = re.match(r"v(\d+)\.", out)
    if code or not match:
        return Result(FAIL, "node", f"could not read the version: {out}")
    major = int(match.group(1))
    if major not in NODE_MAJOR_VERSIONS:
        return Result(FAIL, "node", f"{out}; the portal needs Node 22 or 24")
    if not which("corepack") and not which("yarn"):
        return Result(FAIL, "node", f"{out}, but neither corepack nor yarn is installed -- run: corepack enable")
    return Result(OK, "node", out)


def check_sudo(run: Runner) -> Result:
    code, _ = run(["sudo", "-n", "true"])
    if code:
        return Result(
            FAIL,
            "sudo",
            "needs a password; ContainerLab and the tooling bridge run under sudo and bootstrap runs unattended. "
            "Allow passwordless sudo, or run `sudo -v` just before bootstrap",
        )
    return Result(OK, "sudo", "passwordless")


def check_kvm(kvm: Path = Path("/dev/kvm")) -> Result:
    if not kvm.exists():
        return Result(
            FAIL,
            "kvm",
            "/dev/kvm is missing; the vSRX firewall is a VM. On a cloud instance this needs nested "
            "virtualisation or a bare-metal instance type",
        )
    # ContainerLab runs as root, so whether this user can open /dev/kvm does not matter.
    return Result(OK, "kvm", str(kvm))


def check_memory(total_gb: float | None, needed_gb: int) -> Result:
    if total_gb is None:
        return Result(WARN, "memory", "could not read /proc/meminfo")
    if total_gb < needed_gb:
        return Result(FAIL, "memory", f"{total_gb:.0f} GB installed; this needs about {needed_gb} GB")
    return Result(OK, "memory", f"{total_gb:.0f} GB installed")


def check_disk(free_gb: float | None, where: str) -> Result:
    if free_gb is None:
        return Result(WARN, "disk", f"could not read the free space on {where}")
    if free_gb < MINIMUM_DISK_GB:
        return Result(FAIL, "disk", f"{free_gb:.0f} GB free on {where}; this needs at least {MINIMUM_DISK_GB} GB")
    if free_gb < FIRST_RUN_DISK_GB:
        return Result(
            WARN,
            "disk",
            f"{free_gb:.0f} GB free on {where}; a first run on an empty machine needs about {FIRST_RUN_DISK_GB} GB",
        )
    return Result(OK, "disk", f"{free_gb:.0f} GB free on {where}")


def check_inotify(values: dict[str, int | None]) -> Result:
    """A low limit is a warning, not a failure: `invoke lab` raises it with lab/scripts/host-limits.sh."""
    low = [f"{key} is {have}" for key, have in values.items() if have is not None and have < INOTIFY_MINIMUM[key]]
    if low:
        return Result(WARN, "inotify", "; ".join(low) + " -- the lab deploy raises it (lab/scripts/host-limits.sh)")
    return Result(OK, "inotify")


def check_ports(wanted: tuple[int, ...], listening: set[int], ours: set[int]) -> Result:
    busy = sorted(set(wanted) & (listening - ours))
    if busy:
        ports = ", ".join(str(p) for p in busy)
        return Result(FAIL, "ports", f"{ports} already in use by something else -- `sudo ss -ltnp` shows what")
    return Result(OK, "ports", "free, or held by this environment")


def check_network(sites: tuple[str, ...], reachable: Callable[[str], bool]) -> Result:
    """A warning, not a failure: a proxy may let Docker and Helm through while a direct check fails."""
    with ThreadPoolExecutor(max_workers=len(sites)) as pool:
        answers = dict(zip(sites, pool.map(reachable, sites), strict=True))
    unreachable = [site for site, ok in answers.items() if not ok]
    if unreachable:
        return Result(WARN, "network", f"cannot reach {', '.join(unreachable)}; the run downloads from them")
    return Result(OK, "network", f"{len(sites)} download sites reachable")


def _reachable(site: str) -> bool:
    code, _ = _run(["curl", "-sS", "-o", "/dev/null", "--max-time", "8", "-I", f"https://{site}/"])
    return code == 0


def _listening_ports() -> set[int]:
    """TCP ports in LISTEN state, read from /proc so no root is needed."""
    ports: set[int] = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) > 3 and fields[3] == "0A":  # 0A is LISTEN
                ports.add(int(fields[1].rsplit(":", 1)[1], 16))
    return ports


def _own_ports(run: Runner) -> set[int]:
    code, out = run(["docker", "ps", "--format", "{{.Names}}\t{{.Ports}}"])
    if code:
        return set()
    ports: set[int] = set()
    for line in out.splitlines():
        name, _, published = line.partition("\t")
        if name.startswith(OWN_CONTAINER_PREFIXES):
            ports.update(int(p) for p in re.findall(r":(\d+)->", published))
    return ports


def _sysctl(key: str) -> int | None:
    try:
        return int(Path("/proc/sys", *key.split(".")).read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _docker_root(run: Runner) -> str:
    code, out = run(["docker", "info", "--format", "{{.DockerRootDir}}"])
    return out if code == 0 and out.startswith("/") else "/var/lib/docker"


def _free_gb(path: str) -> float | None:
    try:
        return shutil.disk_usage(path).free / 1024**3
    except OSError:
        return None


def check_lab_images(images_script: Path, run: Runner) -> Result:
    """The cEOS, vSRX and desktop images, reported by `lab/scripts/images.sh --check`.

    A missing image is a warning, not a failure: bootstrap fetches the images with the same script
    straight after these checks, and stops there if it cannot.
    """
    code, out = run([str(images_script), "--check"])
    if code:
        plain = ANSI.sub("", out)
        missing = [
            line.split("FAIL", 1)[1].split(" -- ", 1)[0].strip() for line in plain.splitlines() if "FAIL" in line
        ]
        return Result(WARN, "lab images", "; ".join(missing) + " -- bootstrap fetches them next")
    return Result(OK, "lab images", "cEOS, vSRX and branch desktop present")


def run_checks(
    lab: bool,
    cluster: bool,
    lab_dir: Path,
    which: Which = shutil.which,
    run: Runner = _run,
    memory_gb: float | None = None,
    kvm: Path = Path("/dev/kvm"),
    free_disk_gb: Callable[[str], float | None] = _free_gb,
    sysctl: Callable[[str], int | None] = _sysctl,
    listening: Callable[[], set[int]] = _listening_ports,
    reachable: Callable[[str], bool] = _reachable,
) -> list[Result]:
    """Every prerequisite for the bootstrap that was asked for. `lab=False` is `--no-lab`."""
    results: list[Result] = []
    results.extend(check_docker(which, run))
    docker_root = _docker_root(run)
    results.extend(
        (
            check_disk(free_disk_gb(docker_root), docker_root),
            check_ports(STACK_PORTS + (LAB_PORTS if lab else ()), listening(), _own_ports(run)),
            check_network(INFRAHUB_SITES + (LAB_SITES if lab else ()), reachable),
        )
    )
    total = memory_gb if memory_gb is not None else _memory_gb()
    results.extend(
        (
            check_tool("git", "the repository and the demo branches", which),
            check_tool("curl", "the readiness waits", which),
            check_memory(total, LAB_MEMORY_GB if lab else INFRAHUB_MEMORY_GB),
        )
    )
    # The tooling node (Dex, the portal) runs with or without the lab.
    results.extend(
        (
            check_tool("containerlab", "the lab", which, 'bash -c "$(curl -sL https://get.containerlab.dev)"'),
            check_sudo(run),
            check_inotify({key: sysctl(key) for key in INOTIFY_MINIMUM}),
            check_tool("openssl", "the portal certificate", which),
            check_node(which, run),
        )
    )
    if not lab:
        return results

    results.append(check_kvm(kvm))
    if cluster:
        results.extend(
            (
                check_tool("kubectl", "the Kubernetes step", which, "https://kubernetes.io/docs/tasks/tools/"),
                check_tool("helm", "the Kubernetes step", which, "https://helm.sh/docs/intro/install/"),
            )
        )
    docker_usable = any(r.name == "docker daemon" and r.status == OK for r in results)
    if docker_usable:
        results.append(check_lab_images(lab_dir / "scripts/images.sh", run))
    return results


def failed(results: list[Result]) -> bool:
    return any(r.status == FAIL for r in results)


def render(results: list[Result]) -> str:
    colour = {OK: "\033[1;32m", WARN: "\033[1;33m", FAIL: "\033[1;31m"}
    lines = []
    for r in results:
        detail = f"  {r.detail}" if r.detail else ""
        lines.append(f"  {colour[r.status]}{r.status:<4}\033[0m  {r.name}{detail}")
    return "\n".join(lines)
