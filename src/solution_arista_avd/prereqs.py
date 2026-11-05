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
from dataclasses import dataclass
from pathlib import Path

OK = "ok"
WARN = "warn"
FAIL = "FAIL"

# The full lab needs about 36.5 GB for its nodes (lab/scripts/preflight.sh). The Infrahub stack,
# the reconciler and the portal build add roughly 10 GB on top.
LAB_MEMORY_GB = 48
INFRAHUB_MEMORY_GB = 8
NODE_MAJOR_VERSIONS = (22, 24)
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
) -> list[Result]:
    """Every prerequisite for the bootstrap that was asked for. `lab=False` is `--no-lab`."""
    results: list[Result] = []
    results.extend(check_docker(which, run))
    total = memory_gb if memory_gb is not None else _memory_gb()
    results.extend(
        (
            check_tool("git", "the repository and the demo branches", which),
            check_tool("curl", "the readiness waits", which),
            check_memory(total, LAB_MEMORY_GB if lab else INFRAHUB_MEMORY_GB),
        )
    )
    if not lab:
        return results

    results.extend(
        (
            check_tool("containerlab", "the lab", which, 'bash -c "$(curl -sL https://get.containerlab.dev)"'),
            check_sudo(run),
            check_kvm(kvm),
            check_tool("openssl", "the portal certificate", which),
            check_node(which, run),
        )
    )
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
