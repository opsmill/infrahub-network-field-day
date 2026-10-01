"""The handover has to cover every claim the lab's installer applies.

`invoke cluster` runs the lab's `install-crossplane.sh` and then
deletes the claims it applied: the two Infrahub models, which Vidra re-delivers,
and the two it does not, which stay gone. The list lives in `tasks.py` as
`HANDOVER_DELETIONS` and the claims live in the lab, so the two drift
silently -- a lab that adds a third application deploys it on every bootstrap
and nothing here says so.

`scripts/verify_bootstrap.sh` counts the applications afterwards and would catch
it, but only at the end of a twenty-minute rebuild. This asserts the same thing
against the files.

The lab is committed under `lab/`, so this skips only when OTTERNET_LAB_DIR
points somewhere without one -- and fails, rather than passing quietly, when it
is present and no claim can be parsed out of it. An empty set matching nothing is the
failure this test would otherwise become.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

import tasks

# `kubectl apply -f "$LAB_DIR/<path>"`, which is how every manifest in
# install-crossplane.sh is applied.
APPLY = re.compile(r'kubectl apply -f "\$LAB_DIR/([^"]+)"')

# The API group of the lab's own XRDs. Claims are the only things in it that
# carry a name the handover could delete; the XRDs and Compositions beside them
# are `apiextensions.crossplane.io`.
CLAIM_GROUP = "otternet.lab/"


def _lab_directory() -> Path | None:
    """The lab under lab/, or None when OTTERNET_LAB_DIR points somewhere without one."""
    try:
        return tasks.find_lab_directory()
    except SystemExit:
        return None


def _claims_the_installer_applies() -> set[tuple[str, str]]:
    lab = _lab_directory()
    if lab is None:
        pytest.skip("no lab found; OTTERNET_LAB_DIR points somewhere without otternet.clab.yml")

    installer = lab / "k8s/bootstrap/install-crossplane.sh"
    if not installer.is_file():
        pytest.skip(f"{installer} is not present in the lab checkout")

    claims: set[tuple[str, str]] = set()
    for relative in APPLY.findall(installer.read_text()):
        manifest = lab / relative
        if not manifest.is_file():
            continue
        for document in yaml.safe_load_all(manifest.read_text()):
            if not isinstance(document, dict):
                continue
            if not str(document.get("apiVersion", "")).startswith(CLAIM_GROUP):
                continue
            claims.add((str(document["kind"]).lower(), str(document["metadata"]["name"])))
    return claims


def test_the_handover_deletes_every_claim_the_lab_applies() -> None:
    claims = _claims_the_installer_applies()

    # Parsing nothing would make every assertion below vacuous, which is the
    # shape of the failure this file exists to prevent.
    assert claims, "no claims parsed out of install-crossplane.sh; the parser, not the lab, is wrong"

    assert claims == set(tasks.HANDOVER_DELETIONS), (
        "install-crossplane.sh applies claims the handover does not delete: "
        f"{sorted(claims - set(tasks.HANDOVER_DELETIONS))}. A claim the handover misses is "
        "deployed by every bootstrap and modelled by nothing."
    )


def test_the_modelled_claims_are_the_ones_vidra_redelivers() -> None:
    """The two halves of the handover, and why the split is not cosmetic.

    Everything in `HANDOVER_DELETIONS` is deleted; only what Infrahub models
    comes back. Collapsing the two lists into one would leave the unmodelled
    applications waiting for a redelivery that never arrives -- or, the other
    way round, leave the modelled ones deleted for good.
    """
    modelled = set(tasks.INFRAHUB_OWNED_RESOURCES)
    unmodelled = {("fabricapp", name) for name in tasks.LAB_ONLY_APPS}

    assert modelled & unmodelled == set()
    assert modelled | unmodelled == set(tasks.HANDOVER_DELETIONS)


def test_the_lab_kube_prometheus_stack_is_never_applied_beside_infrahubs() -> None:
    """Cycle 034. Two kube-prometheus-stack releases contend for the same CRDs.

    Infrahub delivers `otternet-metrics` through Vidra, which goes up before
    Crossplane, so the lab's `otternet-observability` would be created in the
    same window and the second release would fail `invalid ownership metadata`.
    Deleting it afterwards, as the handover does for the others, is too late --
    so the installer is told not to apply it, and this holds both halves: the
    lab honours the flag, and `invoke cluster` sets it.
    """
    lab = _lab_directory()
    if lab is None:
        pytest.skip("no lab found; OTTERNET_LAB_DIR points somewhere without otternet.clab.yml")
    installer = (lab / "k8s/bootstrap/install-crossplane.sh").read_text()
    guarded = re.search(
        r'if \[\[ "\$\{OTTERNET_SKIP_OBSERVABILITY:-0\}" != "1" \]\]; then\s+'
        r'kubectl apply -f "\$LAB_DIR/crossplane/apps/20-observability.yaml"',
        installer,
    )
    assert guarded, "install-crossplane.sh no longer guards the observability claim behind OTTERNET_SKIP_OBSERVABILITY"

    source = Path(tasks.__file__).read_text(encoding="utf-8")
    assert '"OTTERNET_SKIP_OBSERVABILITY": "1"' in source, "invoke cluster no longer sets OTTERNET_SKIP_OBSERVABILITY"


def test_every_sr_linux_startup_config_is_one_the_renderer_produces() -> None:
    """ContainerLab refuses the whole topology over a missing startup-config.

    `lab/wan/rendered/` is gitignored, so every file a router boots from has to be
    one `wan/render.py` writes -- `invoke lab` renders before it deploys. A node
    renamed in the topology but not in `tenants.yml` would otherwise be found at
    deploy time, with every other node already refused alongside it.
    """
    import subprocess  # noqa: S404 - one fixed-argv call to the committed renderer
    import sys

    lab = Path(__file__).resolve().parents[2] / "lab"
    subprocess.run([sys.executable, str(lab / "wan/render.py")], check=True, capture_output=True)  # noqa: S603
    nodes = yaml.safe_load((lab / "otternet.clab.yml").read_text(encoding="utf-8"))["topology"]["nodes"]
    routers = {name: node for name, node in nodes.items() if (node or {}).get("kind") == "nokia_srlinux"}

    assert set(routers) == {"isp-pe1", "isp-pe2", "internet-rtr", "cust-acme-ce", "cust-globex-ce", "branch-rtr"}
    for name, node in routers.items():
        assert node["startup-config"] == f"wan/rendered/{name}/config.cli"
        assert (lab / node["startup-config"]).is_file(), f"{name}: render.py writes no {node['startup-config']}"


def test_no_node_binds_the_retired_frr_socket_directories() -> None:
    """The frr_exporter sidecars and their `wan/run/<router>` binds went with FRR."""
    lab = Path(__file__).resolve().parents[2] / "lab"
    nodes = yaml.safe_load((lab / "otternet.clab.yml").read_text(encoding="utf-8"))["topology"]["nodes"]
    binds = [bind for node in nodes.values() for bind in (node or {}).get("binds", []) or []]
    assert not [bind for bind in binds if str(bind).startswith("wan/run/")]
    assert not [name for name in nodes if name.endswith("-exporter")]
