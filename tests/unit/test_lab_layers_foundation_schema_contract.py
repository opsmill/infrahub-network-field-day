"""Contract tests for the foundational layer of the NFD41 lab schema feature.

Covers the three shared files every story in
``specs/010-lab-service-layer-model`` depends on: the new
``OrganizationCustomer`` node, and the additive role choices on the existing
``DcimDevice`` and ``IpamPrefix`` dropdowns.

The pre-existing choice assertions are the additive-compatibility guarantee in
``specs/010-lab-service-layer-model/contracts/schema-kinds.md`` section 7: this
feature may only ever add choices, because removing one would invalidate seed
data and generator output that already selects it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parents[2]

# Device roles that existed before this feature. None may disappear.
LEGACY_DEVICE_ROLES = {
    "super_spine",
    "spine",
    "leaf",
    "border_leaf",
    "l2leaf",
    "l2spine",
    "l3spine",
    "p",
    "pe",
    "rr",
}

# The non-EOS roles this feature adds. See research.md R7: none of these may be
# added to ROLE_TO_AVD_TYPE, because get_avd_type raises ValueError on an
# unmapped role and mapping one would let a non-EOS device render as EOS.
# No `firewall` value: the adopted marketplace security schema supplies
# SecurityFirewall, which inherits DcimGenericDevice and DcimPhysicalDevice, so
# a firewall is its own device kind rather than a DcimDevice carrying a role.
NEW_DEVICE_ROLES = {
    "isp_edge",
    "isp_core",
    "internet_edge",
    "customer_edge",
    "branch_router",
    "k8s_node",
}

# Prefix roles that existed before this feature. None may disappear.
LEGACY_PREFIX_ROLES = {
    "supernet",
    "pod_super_spine_spine",
    "pod_leaf_spine",
    "loopback",
    "loopback-vtep",
    "fabric_point_to_point",
    "dci",
    "fabric_supernet",
    "mlag",
    "mlag_peering",
    "technical",
    "management",
    "backfill",
}

NEW_PREFIX_ROLES = {
    "pod",
    "service",
    "vip_pool",
    "wan_customer",
    "branch_lan",
    "tenant_cloud",
    "tenant_host",
    "off_fabric_point_to_point",
    "internet",
}


def _load_yaml(path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _nodes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return list(schema.get("nodes", []))


def _extension_nodes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    return list(schema.get("extensions", {}).get("nodes", []))


def _node(schema: dict[str, Any], namespace: str, name: str) -> dict[str, Any]:
    for node in _nodes(schema):
        if node.get("namespace") == namespace and node.get("name") == name:
            return node
    raise AssertionError(f"{namespace}{name} node not found")


def _extension_node(schema: dict[str, Any], kind: str) -> dict[str, Any]:
    for node in _extension_nodes(schema):
        if node.get("kind") == kind:
            return node
    raise AssertionError(f"{kind} extension not found")


def _attributes(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {attr["name"]: attr for attr in node.get("attributes", [])}


def _choice_names(attribute: dict[str, Any]) -> set[str]:
    return {choice["name"] for choice in attribute.get("choices", [])}


def _device_role_choices() -> set[str]:
    device = _extension_node(_load_yaml("schemas/dcim_extensions.yml"), "DcimDevice")
    return _choice_names(_attributes(device)["role"])


def _prefix_role_choices() -> set[str]:
    prefix = _extension_node(_load_yaml("schemas/ipam_extensions.yml"), "IpamPrefix")
    return _choice_names(_attributes(prefix)["role"])


def test_adopted_tenancy_schema_provides_an_organization_tenant() -> None:
    """Replaces a locally-authored OrganizationCustomer.

    infrahub/tenancy gives OrganizationTenant, which inherits
    OrganizationGeneric -- so it can be a ServiceGeneric.owner -- and also
    wires tenancy into devices, prefixes, addresses and locations, which the
    local version did not.
    """
    tenant = _node(_load_yaml("schemas/tenancy/tenancy.yml"), "Organization", "Tenant")

    assert tenant["inherit_from"] == ["OrganizationGeneric"]


def test_tenancy_extends_dcim_and_ipam_with_tenant_back_references() -> None:
    """What made adopting this better than keeping the local kind."""
    extended = {node["kind"] for node in _extension_nodes(_load_yaml("schemas/tenancy/tenancy.yml"))}

    assert {"DcimGenericDevice", "IpamPrefix", "IpamIPAddress"} <= extended


def test_no_locally_authored_customer_kind_remains() -> None:
    """The regression this test exists to prevent."""
    assert not (REPO_ROOT / "schemas/organization_extensions.yml").exists()


def test_device_role_choices_include_the_new_non_eos_roles() -> None:
    assert _device_role_choices() >= NEW_DEVICE_ROLES


def test_device_role_choices_retain_every_legacy_role() -> None:
    assert _device_role_choices() >= LEGACY_DEVICE_ROLES


def test_prefix_role_choices_include_the_new_lab_roles() -> None:
    assert _prefix_role_choices() >= NEW_PREFIX_ROLES


def test_prefix_role_choices_retain_every_legacy_role() -> None:
    assert _prefix_role_choices() >= LEGACY_PREFIX_ROLES


def test_new_device_roles_are_absent_from_the_avd_role_map() -> None:
    """research.md R7: the invariant that keeps non-EOS devices out of pyAVD.

    ``get_avd_type`` raises ValueError for any role missing from
    ROLE_TO_AVD_TYPE. That loud failure is the desired behaviour for a
    firewall or an ISP router -- mapping one here would instead let a non-EOS
    device be rendered as EOS, which is silently wrong.
    """
    from solution_arista_avd.avd import ROLE_TO_AVD_TYPE

    overlap = NEW_DEVICE_ROLES & set(ROLE_TO_AVD_TYPE)
    assert not overlap, f"non-EOS roles must not be AVD-mapped: {sorted(overlap)}"
