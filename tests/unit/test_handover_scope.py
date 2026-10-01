"""The handover has to cover every claim the lab's installer applies.

`invoke cluster` runs the lab repository's `install-crossplane.sh` and then
deletes the claims it applied: the two Infrahub models, which Vidra re-delivers,
and the two it does not, which stay gone. The list lives in `tasks.py` as
`HANDOVER_DELETIONS` and the claims live in the lab repository, so the two drift
silently -- a lab that adds a third application deploys it on every bootstrap
and nothing here says so.

`scripts/verify_bootstrap.sh` counts the applications afterwards and would catch
it, but only at the end of a twenty-minute rebuild. This asserts the same thing
against the files.

The lab repository is a sibling checkout rather than a dependency, so this skips
when it is absent -- and fails, rather than passing quietly, when it is present
and no claim can be parsed out of it. An empty set matching nothing is the
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
    """The lab checkout, or None -- it is a sibling repository, not a dependency."""
    try:
        return tasks.find_lab_directory()
    except SystemExit:
        return None


def _claims_the_installer_applies() -> set[tuple[str, str]]:
    lab = _lab_directory()
    if lab is None:
        pytest.skip("the sibling lab repository is not checked out beside this one")

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
        pytest.skip("the sibling lab repository is not checked out beside this one")
    installer = (lab / "k8s/bootstrap/install-crossplane.sh").read_text()
    guarded = re.search(
        r'if \[\[ "\$\{OTTERNET_SKIP_OBSERVABILITY:-0\}" != "1" \]\]; then\s+'
        r'kubectl apply -f "\$LAB_DIR/crossplane/apps/20-observability.yaml"',
        installer,
    )
    assert guarded, "install-crossplane.sh no longer guards the observability claim behind OTTERNET_SKIP_OBSERVABILITY"

    source = Path(tasks.__file__).read_text(encoding="utf-8")
    assert '"OTTERNET_SKIP_OBSERVABILITY": "1"' in source, "invoke cluster no longer sets OTTERNET_SKIP_OBSERVABILITY"


def test_every_frr_socket_bind_source_is_created_before_deploy(tmp_path: Path) -> None:
    """ContainerLab refuses the whole topology over a missing bind path.

    The first bootstrap with the frr_exporter sidecars died at `invoke lab` on
    exactly that: `Failed to verify bind path: stat .../wan/run/branch-rtr`.
    """
    topology = tmp_path / "otternet.clab.yml"
    topology.write_text(
        yaml.safe_dump(
            {
                "topology": {
                    "nodes": {
                        "isp-pe1": {"binds": ["wan/run/isp-pe1:/var/run/frr", "wan/rendered/x:/etc/frr/x:ro"]},
                        "isp-pe1-exporter": {"binds": ["wan/run/isp-pe1:/var/run/frr"]},
                        "host": {},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    created = tasks._ensure_socket_directories(tmp_path, topology)
    assert created == [tmp_path / "wan/run/isp-pe1"]
    assert (tmp_path / "wan/run/isp-pe1").is_dir()
    assert not (tmp_path / "wan/rendered").exists(), "only socket directories are created"
    assert tasks._ensure_socket_directories(tmp_path, topology) == []
