from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parents[2]
OBJECT_FILES = sorted((REPO_ROOT / "objects").glob("*.yml"))


def _documents(path: Path) -> list[dict[str, Any]]:
    return [document for document in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(document, dict)]


def _object_rows(kind: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for object_file in OBJECT_FILES:
        for document in _documents(object_file):
            spec = document.get("spec", {})
            if spec.get("kind") == kind:
                rows.extend(spec.get("data", []))
    return rows


def test_every_network_fabric_legacy_pool_assignment_is_in_fabric_ip_pools() -> None:
    legacy_fields = ["mgmt_pool", "uplink_pool", "vtep_pool", "loopback_pool", "dci_pool"]

    for fabric in _object_rows("NetworkFabric"):
        fabric_ip_pools = set(fabric.get("fabric_ip_pools", []))
        for field in legacy_fields:
            legacy_pool = fabric.get(field)
            if legacy_pool:
                assert legacy_pool in fabric_ip_pools, f"{fabric['name']} missing {field} in fabric_ip_pools"


def test_every_network_pod_legacy_mlag_assignment_is_in_pod_ip_pools() -> None:
    for fabric in _object_rows("NetworkFabric"):
        for pod in fabric.get("children", {}).get("data", []):
            pod_ip_pools = set(pod.get("pod_ip_pools", []))
            for field in ("mlag_peer_pool", "mlag_l3_pool"):
                legacy_pool = pod.get(field)
                if legacy_pool:
                    assert legacy_pool in pod_ip_pools, f"{pod['name']} missing {field} in pod_ip_pools"


# Roles the pool model replaced. A prefix still carrying one of these is not
# picked up by the role-driven pool collection, so the fabric silently falls back
# to a generated default pool instead of the prefix that was authored for it.
RETIRED_PREFIX_ROLES = {"pod_leaf_spine", "pod_super_spine_spine", "technical"}


def test_no_prefix_carries_a_retired_role() -> None:
    """Every seeded prefix uses an explicit pool role, not a pre-migration one."""
    offenders = {
        row["prefix"]: row["role"] for row in _object_rows("IpamPrefix") if row.get("role") in RETIRED_PREFIX_ROLES
    }
    assert not offenders, f"prefixes with retired roles: {offenders}"


def test_exactly_one_fabric_supernet_is_seeded() -> None:
    """The deterministic fallback needs one supernet to carve from, and only one.

    Two would make which prefix a generated fallback pool comes from depend on
    query order.
    """
    supernets = [row["prefix"] for row in _object_rows("IpamPrefix") if row.get("role") == "fabric_supernet"]
    assert len(supernets) == 1, f"expected one fabric_supernet prefix, found {supernets}"


def test_mlag_prefixes_use_the_explicit_mlag_roles() -> None:
    """Both MLAG pools are role-tagged, and distinctly.

    The peer link and the L3 peering across it are separate pools; giving both
    the same role makes the pod pick one of them for both purposes.
    """
    roles = {row["prefix"]: row.get("role") for row in _object_rows("IpamPrefix")}
    assert sorted(prefix for prefix, role in roles.items() if role == "mlag")
    assert sorted(prefix for prefix, role in roles.items() if role == "mlag_peering")
