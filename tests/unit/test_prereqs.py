"""Host prerequisite checks that `invoke bootstrap` runs before it changes anything.

The probes (`which`, the command runner, memory, /dev/kvm) are passed in, so no test needs the real
host. The last tests read `tasks.py` as text to pin where bootstrap runs the checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from solution_arista_avd import prereqs

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

REPO = Path(__file__).resolve().parents[2]
ALL_TOOLS = {"docker", "git", "curl", "containerlab", "openssl", "node", "corepack", "kubectl", "helm"}


def which_from(tools: set[str]):
    return lambda name: f"/usr/bin/{name}" if name in tools else None


def runner(failing: frozenset[str] = frozenset(), node: str = "v22.23.2", images_ok: bool = True):
    def run(cmd: list[str]) -> tuple[int, str]:
        key = cmd[0] if cmd[0] != "docker" else " ".join(cmd[:2])
        if cmd[0].endswith("images.sh"):
            return (
                (0, "ok")
                if images_ok
                else (1, "  \x1b[1;31mFAIL\x1b[0m  vSRX vrnetlab/juniper_vsrx:22.3R1.11 missing -- run: x")
            )
        if key in failing:
            return 1, "error"
        if cmd[0] == "node":
            return 0, node
        return 0, "1.0"

    return run


def run_all(
    tmp_path: Path,
    tools: Iterable[str] = ALL_TOOLS,
    run: Callable[[list[str]], tuple[int, str]] | None = None,
    memory: float = 128.0,
    lab: bool = True,
    cluster: bool = True,
    disk: float = 200.0,
    inotify: int = 62800,
    listening: frozenset[int] = frozenset(),
    unreachable: frozenset[str] = frozenset(),
) -> list[prereqs.Result]:
    kvm = tmp_path / "kvm"
    kvm.touch()
    return prereqs.run_checks(
        lab=lab,
        cluster=cluster,
        lab_dir=tmp_path,
        which=which_from(set(tools)),
        run=run or runner(),
        memory_gb=memory,
        kvm=kvm,
        free_disk_gb=lambda _path: disk,
        sysctl=lambda key: inotify if key.endswith("instances") else 25600000,
        listening=lambda: listening,
        reachable=lambda site: site not in unreachable,
    )


def by_name(results: list[prereqs.Result]) -> dict[str, prereqs.Result]:
    return {r.name: r for r in results}


def test_a_complete_host_passes(tmp_path: Path) -> None:
    results = run_all(tmp_path)
    assert not prereqs.failed(results), prereqs.render(results)


def test_a_missing_tool_fails_and_names_it(tmp_path: Path) -> None:
    results = by_name(run_all(tmp_path, tools=ALL_TOOLS - {"containerlab"}))
    assert results["containerlab"].status == prereqs.FAIL
    assert "get.containerlab.dev" in results["containerlab"].detail


def test_sudo_with_a_password_fails(tmp_path: Path) -> None:
    results = by_name(run_all(tmp_path, run=runner(failing={"sudo"})))
    assert results["sudo"].status == prereqs.FAIL


def test_docker_without_group_membership_fails(tmp_path: Path) -> None:
    results = by_name(run_all(tmp_path, run=runner(failing={"docker info"})))
    assert results["docker daemon"].status == prereqs.FAIL
    # The image check needs a usable daemon, so it is not run at all.
    assert "lab images" not in results


def test_wrong_node_major_version_fails(tmp_path: Path) -> None:
    results = by_name(run_all(tmp_path, run=runner(node="v20.11.0")))
    assert results["node"].status == prereqs.FAIL


def test_missing_kvm_fails(tmp_path: Path) -> None:
    results = prereqs.run_checks(
        lab=True,
        cluster=True,
        lab_dir=tmp_path,
        which=which_from(ALL_TOOLS),
        run=runner(),
        memory_gb=128.0,
        kvm=tmp_path / "absent",
        free_disk_gb=lambda _path: 200.0,
        sysctl=lambda _key: 1 << 30,
        listening=set,
        reachable=lambda _site: True,
    )
    assert by_name(results)["kvm"].status == prereqs.FAIL


def test_too_little_memory_for_the_lab_fails(tmp_path: Path) -> None:
    assert by_name(run_all(tmp_path, memory=32.0))["memory"].status == prereqs.FAIL


def test_a_missing_lab_image_is_a_warning_because_bootstrap_fetches_it(tmp_path: Path) -> None:
    results = run_all(tmp_path, run=runner(images_ok=False))
    image = by_name(results)["lab images"]
    assert image.status == prereqs.WARN
    assert "juniper_vsrx" in image.detail
    assert "\x1b" not in image.detail
    assert not prereqs.failed(results)


def test_no_lab_needs_the_infrahub_and_tooling_node_tools(tmp_path: Path) -> None:
    tools = {"docker", "git", "curl", "containerlab", "openssl", "node", "corepack"}
    results = by_name(run_all(tmp_path, tools=tools, memory=16.0, lab=False))
    assert not prereqs.failed(list(results.values()))
    assert "containerlab" in results
    assert "lab images" not in results
    assert "kvm" not in {name.lower() for name in results}


def test_no_cluster_leaves_out_kubectl_and_helm(tmp_path: Path) -> None:
    results = by_name(run_all(tmp_path, tools=ALL_TOOLS - {"kubectl", "helm"}, cluster=False))
    assert not prereqs.failed(list(results.values()))


TASKS = (REPO / "tasks.py").read_text(encoding="utf-8")
BOOTSTRAP = TASKS.split("def bootstrap(", 1)[1].split("def _bootstrap_infrahub_only", 1)[0]


def test_bootstrap_checks_the_host_and_fetches_images_before_destroying_anything() -> None:
    check = BOOTSTRAP.index("_check_prereqs(")
    images = BOOTSTRAP.index("lab_images(ctx, lab_dir=lab_dir)")
    fresh = BOOTSTRAP.index("if fresh:")
    assert check < images < fresh


def test_the_lab_task_fetches_images_before_the_deploy() -> None:
    lab = TASKS.split("def lab(", 1)[1].split("\ndef ", 1)[0]
    # The last deploy is the full one; the tooling-only deploy before it needs none of the local images.
    assert lab.index("lab_images(ctx") < lab.rindex("deploy -t")


def test_every_image_variable_in_the_topology_survives_sudo() -> None:
    import re

    topology = (REPO / "lab/otternet.clab.yml").read_text(encoding="utf-8")
    variables = set(re.findall(r"\$\{(OTTERNET_[A-Z_]+):=", topology))
    passthrough = TASKS.split("CLAB_ENV_PASSTHROUGH = ", 1)[1].split("\n)\n", 1)[0]
    names = set(re.findall(r"OTTERNET_[A-Z_]+", passthrough))
    missing = sorted(variables - names)
    assert not missing, missing


def test_little_disk_fails_and_some_disk_warns(tmp_path: Path) -> None:
    assert by_name(run_all(tmp_path, disk=10.0))["disk"].status == prereqs.FAIL
    assert by_name(run_all(tmp_path, disk=40.0))["disk"].status == prereqs.WARN
    assert by_name(run_all(tmp_path, disk=100.0))["disk"].status == prereqs.OK


def test_the_default_inotify_limit_warns_because_the_deploy_raises_it(tmp_path: Path) -> None:
    results = run_all(tmp_path, inotify=128)
    inotify = by_name(results)["inotify"]
    assert inotify.status == prereqs.WARN
    assert "host-limits.sh" in inotify.detail
    assert not prereqs.failed(results)


def test_host_limits_script_raises_what_prereqs_expects() -> None:
    script = (REPO / "lab/scripts/host-limits.sh").read_text(encoding="utf-8")
    for key, value in prereqs.INOTIFY_MINIMUM.items():
        assert f"[{key}]={value}" in script


def test_the_lab_task_raises_the_limits_before_the_deploy() -> None:
    lab = TASKS.split("def lab(", 1)[1].split("\ndef ", 1)[0]
    assert lab.index("host-limits.sh") < lab.index("deploy -t")


def test_a_port_held_by_something_else_fails() -> None:
    result = prereqs.check_ports((3000, 8000), listening={3000, 22}, ours=set())
    assert result.status == prereqs.FAIL
    assert "3000" in result.detail
    assert "8000" not in result.detail


def test_a_port_held_by_this_environment_passes() -> None:
    assert prereqs.check_ports((3000, 8000), listening={3000, 8000}, ours={3000, 8000}).status == prereqs.OK


def test_a_busy_port_fails_the_whole_check(tmp_path: Path) -> None:
    assert prereqs.failed(run_all(tmp_path, listening=frozenset({8080})))
    assert not prereqs.failed(
        run_all(tmp_path, listening=frozenset({8080}), lab=False, tools=ALL_TOOLS - {"kubectl", "helm"})
    )


def test_the_port_list_matches_the_compose_files() -> None:
    import re

    text = "".join(
        (REPO / name).read_text(encoding="utf-8") for name in ("docker-compose.yml", "docker-compose.override.yml")
    )
    mapping = r'^\s+- "?(?:[0-9.]+:)?(?:\$\{[A-Z_]+:-)?(\d+)\}?:\d+"?\s*$'
    published = {int(m) for m in re.findall(mapping, text, re.MULTILINE)}
    # 3001 is the portal's build-only service, which never runs on the host.
    assert published - {3001} == set(prereqs.STACK_PORTS)


def test_the_lab_port_list_matches_the_topology() -> None:
    import re

    topology = (REPO / "lab/otternet.clab.yml").read_text(encoding="utf-8")
    published = {int(m) for m in re.findall(r"^\s+- \"?(\d+):\d+\"?\s*$", topology, re.MULTILINE)}
    assert published == set(prereqs.LAB_PORTS)


def test_an_unreachable_site_is_a_warning_that_names_it(tmp_path: Path) -> None:
    results = run_all(tmp_path, unreachable=frozenset({"charts.crossplane.io"}))
    network = by_name(results)["network"]
    assert network.status == prereqs.WARN
    assert "charts.crossplane.io" in network.detail
    assert not prereqs.failed(results)


def test_no_lab_checks_only_the_infrahub_sites(tmp_path: Path) -> None:
    results = run_all(tmp_path, unreachable=frozenset({"ghcr.io"}), lab=False, tools={"docker", "git", "curl"})
    assert by_name(results)["network"].status == prereqs.OK


def test_crossplane_comes_from_ghcr_not_xpkg() -> None:
    import re

    packages = (REPO / "lab/crossplane/providers/00-packages.yaml").read_text(encoding="utf-8")
    refs = re.findall(r"^\s+package:\s*(\S+)", packages, re.MULTILINE)
    assert refs
    assert all(ref.startswith("ghcr.io/crossplane-contrib/") for ref in refs), refs
    install = (REPO / "lab/k8s/bootstrap/install-crossplane.sh").read_text(encoding="utf-8")
    assert "--set image.repository=ghcr.io/crossplane/crossplane" in install
