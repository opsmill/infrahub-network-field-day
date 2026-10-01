"""Unit tests for the allocation consistency check.

The fixtures are the lab's real shapes -- K8S_NODES on 110 in K8S_PROD tagged
`k8s`, APP_HOSTS on 210, ACME_CLOUD and GLOBEX_CLOUD on 310/320 sharing the
`cloud` tag inside one tenant, the 10.230.0.0/16 segment pool, and the
`otternet` cluster's 10.112.240.0/24 VIP pool -- because the rules are about
relationships between those objects and invented shapes would satisfy them
trivially.

Every rule has a clean case beside its failing one: an empty result is only
evidence when a non-empty result from the same fixture, one field changed, is
proven next to it.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from checks.allocation_consistency_check import (
    check_fabric_vlan_ids,
    check_segment_subnets,
    check_vip_blocks,
    check_vlan_reference,
    collect_findings,
    service_vlans,
    tenant_subnets,
    vip_blocks,
)
from checks.allocation_consistency_check_query import AllocationConsistencyCheckQuery

FABRIC = ("fabric-otternet", "OTTERNET_FABRIC")
TAG_IDS = {"k8s": "tag-k8s", "app": "tag-app", "cloud": "tag-cloud", "border": "tag-border"}


def _wrap(value: Any) -> dict[str, Any]:
    return {"value": value}


def _named(node_id: str, name: str) -> dict[str, Any]:
    return {"id": node_id, "name": _wrap(name)}


def _many(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"edges": [{"node": node} for node in nodes]}


def _tags(*names: str) -> dict[str, Any]:
    return _many([_named(TAG_IDS[name], name) for name in names])


def _ipam_vlan(name: str, vlan_id: int) -> dict[str, Any]:
    return {"node": {"id": f"vlan-{name}", "name": _wrap(name), "vlan_id": _wrap(vlan_id)}}


def _tenant(name: str, base: int | None, vrfs: list[str], l2vlans: list[dict[str, Any]] | None = None) -> dict:
    return {
        "id": f"tenant-{name}",
        "name": _wrap(name),
        "mac_vrf_vni_base": _wrap(base),
        "fabrics": _many([_named(*FABRIC)]),
        "vrfs": _many([{"id": f"vrf-{vrf}"} for vrf in vrfs]),
        "l2vlans": _many(l2vlans or []),
    }


def _svi(name: str, svi_id: int, vrf: str, *tags: str, gateway: str, vlan_id: int | None = None) -> dict:
    return {
        "id": f"svi-{name}",
        "name": _wrap(name),
        "svi_id": _wrap(svi_id),
        "ip_address_virtual": _wrap(None),
        "ip_virtual_router_addresses": _wrap([gateway]),
        "vrf": {"node": _named(f"vrf-{vrf}", vrf)},
        "vlan": _ipam_vlan(name, svi_id if vlan_id is None else vlan_id),
        "rack_tags": _many([]),
        "avd_tags": _tags(*tags),
    }


def _l2vlan(name: str, vlan_id: int, *tags: str, vni_override: int | None = None) -> dict:
    return {
        "id": f"l2vlan-{name}",
        "name": _wrap(name),
        "vlan_id": _wrap(vlan_id),
        "vni_override": _wrap(vni_override),
        "vlan": {"node": None},
        "rack_tags": _many([]),
        "avd_tags": _tags(*tags),
    }


def _prefix(prefix: str, role: str, vrf: str | None = None) -> dict:
    return {
        "id": f"prefix-{prefix}",
        "prefix": _wrap(prefix),
        "role": _wrap(role),
        "vrf": {"node": None if vrf is None else _named(f"vrf-{vrf}", vrf)},
    }


def _segment(name: str, vrf: str, subnet: str | None) -> dict:
    return {
        "id": f"segment-{name}",
        "name": _wrap(name),
        "status": _wrap("active"),
        "vrf": {"node": _named(f"vrf-{vrf}", vrf)},
        "subnet": {"node": None if subnet is None else {"id": f"prefix-{subnet}", "prefix": _wrap(subnet)}},
    }


def _app(name: str, block: str | None, pools: list[str]) -> dict:
    return {
        "id": f"app-{name}",
        "name": _wrap(name),
        "status": _wrap("active"),
        "exposed": _wrap(block is not None),
        "vip_block_managed": _wrap(False),
        "vip_block": {"node": None if block is None else {"id": f"prefix-{block}", "prefix": _wrap(block)}},
        "cluster": {
            "node": {
                **_named("cluster-otternet", "otternet"),
                "vip_pools": _many([{"id": f"prefix-{pool}", "prefix": _wrap(pool)} for pool in pools]),
            }
        },
    }


POOL = "10.112.240.0/24"


@pytest.fixture
def lab() -> dict[str, Any]:
    """The seeded lab, as `objects/` loads it: clean on every rule."""
    return {
        "EvpnTenant": _many(
            [
                _tenant("TENANT_K8S", 11000, ["K8S_PROD"]),
                _tenant("TENANT_APP", 12000, ["APP_PROD"]),
                _tenant("TENANT_CLOUD", 13000, ["TENANT_ACME", "TENANT_GLOBEX"]),
                _tenant("TENANT_EXTERNAL", 15000, ["WAN", "BRANCH"]),
            ]
        ),
        "EvpnSvi": _many(
            [
                _svi("K8S_NODES", 110, "K8S_PROD", "k8s", gateway="10.110.0.1"),
                _svi("APP_HOSTS", 210, "APP_PROD", "app", gateway="10.210.0.1"),
                _svi("ACME_CLOUD", 310, "TENANT_ACME", "cloud", gateway="10.220.10.1"),
                _svi("GLOBEX_CLOUD", 320, "TENANT_GLOBEX", "cloud", gateway="10.220.20.1"),
            ]
        ),
        "ServiceNetworkSegment": _many([]),
        "IpamPrefix": _many(
            [
                _prefix("10.110.0.0/24", "tenant_host"),
                _prefix("10.210.0.0/24", "tenant_host"),
                _prefix("10.220.10.0/24", "tenant_cloud"),
                _prefix("10.220.20.0/24", "tenant_cloud"),
                _prefix("10.230.0.0/16", "tenant_host"),
                _prefix("10.112.240.0/24", "vip_pool"),
                _prefix("10.41.0.0/16", "fabric_supernet"),
            ]
        ),
        "CoreIPPrefixPool": _many(
            [
                {
                    **_named("pool-segments", "OTTERNET-Segment-Subnet-Pool"),
                    "resources": _many([{"__typename": "IpamPrefix", "id": "prefix-10.230.0.0/16"}]),
                }
            ]
        ),
        "ServiceFabricApp": _many(
            [
                _app("otternet-demo", "10.112.240.0/28", [POOL]),
                _app("otternet-metrics", "10.112.240.80/28", [POOL]),
                _app("otternet-telemetry", None, [POOL]),
            ]
        ),
    }


def _parse(data: dict[str, Any]) -> AllocationConsistencyCheckQuery:
    return AllocationConsistencyCheckQuery(**data)


def _with(data: dict[str, Any], kind: str, *nodes: dict[str, Any]) -> dict[str, Any]:
    changed = copy.deepcopy(data)
    changed[kind]["edges"].extend({"node": node} for node in nodes)
    return changed


# -- the baseline -------------------------------------------------------------


def test_the_lab_as_modelled_passes_every_rule(lab: dict[str, Any]) -> None:
    parsed = _parse(lab)
    assert collect_findings(parsed) == []
    # ...and it examined something, rather than passing over nothing.
    assert len(service_vlans(parsed)) == 4
    assert {str(subnet.network) for subnet in tenant_subnets(parsed)} == {
        "10.110.0.0/24",
        "10.210.0.0/24",
        "10.220.10.0/24",
        "10.220.20.0/24",
    }
    assert len(vip_blocks(parsed)) == 2


def test_subnet_vrfs_are_resolved_from_the_gateway_that_serves_them(lab: dict[str, Any]) -> None:
    resolved = {str(subnet.network): subnet.vrf and subnet.vrf[1] for subnet in tenant_subnets(_parse(lab))}
    assert resolved["10.110.0.0/24"] == "K8S_PROD"
    assert resolved["10.220.20.0/24"] == "TENANT_GLOBEX"


# -- rule 1: VLAN ids per fabric ----------------------------------------------


def test_same_id_on_a_shared_tag_is_reported(lab: dict[str, Any]) -> None:
    broken = _with(lab, "EvpnSvi", _svi("DUP_K8S", 110, "APP_PROD", "k8s", gateway="10.211.0.1"))
    findings = check_fabric_vlan_ids(_parse(broken))
    assert len(findings) == 1
    assert "'DUP_K8S'" in findings[0].message
    assert "'K8S_NODES'" in findings[0].message
    assert "VLAN 110" in findings[0].message
    assert findings[0].object_type == "EvpnSvi"


def test_same_id_on_disjoint_tags_in_another_tenant_is_clean(lab: dict[str, Any]) -> None:
    # The clean twin of the case above: same id, but tagged `border`, so no
    # switch carries both, and TENANT_APP's base gives it a different VNI.
    fine = _with(lab, "EvpnSvi", _svi("DUP_BORDER", 110, "APP_PROD", "border", gateway="10.211.0.1"))
    assert check_fabric_vlan_ids(_parse(fine)) == []


def test_same_id_in_two_vrfs_of_one_tenant_collides_on_the_vni(lab: dict[str, Any]) -> None:
    # Disjoint tags, so no switch carries both -- but both VRFs belong to
    # TENANT_CLOUD, so both render VNI 13310 fabric-wide.
    broken = _with(lab, "EvpnSvi", _svi("GLOBEX_DUP", 310, "TENANT_GLOBEX", "border", gateway="10.221.0.1"))
    findings = check_fabric_vlan_ids(_parse(broken))
    assert len(findings) == 1
    assert "VNI 13310" in findings[0].message
    assert "'ACME_CLOUD'" in findings[0].message
    assert "'GLOBEX_DUP'" in findings[0].message


def test_an_l2vlan_colliding_with_an_svi_is_reported(lab: dict[str, Any]) -> None:
    broken = copy.deepcopy(lab)
    broken["EvpnTenant"]["edges"][0]["node"]["l2vlans"] = _many([_l2vlan("K8S_STORAGE", 110, "k8s")])
    findings = check_fabric_vlan_ids(_parse(broken))
    assert len(findings) == 1
    assert "EvpnL2Vlan 'K8S_STORAGE'" in findings[0].message


def test_an_l2vlan_with_a_distinct_id_is_clean(lab: dict[str, Any]) -> None:
    fine = copy.deepcopy(lab)
    fine["EvpnTenant"]["edges"][0]["node"]["l2vlans"] = _many([_l2vlan("K8S_STORAGE", 111, "k8s")])
    assert check_fabric_vlan_ids(_parse(fine)) == []


def test_a_vni_override_onto_another_vlans_vni_is_reported(lab: dict[str, Any]) -> None:
    broken = copy.deepcopy(lab)
    broken["EvpnTenant"]["edges"][1]["node"]["l2vlans"] = _many([_l2vlan("APP_L2", 211, "border", vni_override=11110)])
    findings = check_fabric_vlan_ids(_parse(broken))
    assert len(findings) == 1
    assert "VNI 11110" in findings[0].message


def test_an_svi_disagreeing_with_its_ipam_vlan_is_reported(lab: dict[str, Any]) -> None:
    broken = copy.deepcopy(lab)
    broken["EvpnSvi"]["edges"][0]["node"]["vlan"] = _ipam_vlan("K8S_NODES", 111)
    findings = check_vlan_reference(_parse(broken))
    assert len(findings) == 1
    assert "renders VLAN 110" in findings[0].message
    assert "IpamVLAN 'K8S_NODES', which is VLAN 111" in findings[0].message
    assert check_vlan_reference(_parse(lab)) == []


# -- rule 2: tenant subnets per VRF -------------------------------------------


def test_a_segment_overlapping_a_hand_written_subnet_is_reported(lab: dict[str, Any]) -> None:
    broken = _with(lab, "IpamPrefix", _prefix("10.110.0.128/25", "tenant_host"))
    broken = _with(broken, "ServiceNetworkSegment", _segment("scratch-overlap", "K8S_PROD", "10.110.0.128/25"))
    findings = check_segment_subnets(_parse(broken))
    assert len(findings) == 1
    assert "10.110.0.0/24 (VRF K8S_PROD)" in findings[0].message
    assert "10.110.0.128/25 (VRF K8S_PROD, segment 'scratch-overlap')" in findings[0].message


def test_the_same_range_in_another_vrf_is_clean(lab: dict[str, Any]) -> None:
    # The clean twin: same subnet, but the segment puts it in APP_PROD, a
    # different routing domain from the K8S_PROD gateway serving 10.110.0.0/24.
    fine = _with(lab, "IpamPrefix", _prefix("10.110.0.128/25", "tenant_host"))
    fine = _with(fine, "ServiceNetworkSegment", _segment("elsewhere", "APP_PROD", "10.110.0.128/25"))
    assert check_segment_subnets(_parse(fine)) == []


def test_two_allocated_segments_overlapping_are_reported(lab: dict[str, Any]) -> None:
    broken = _with(lab, "IpamPrefix", _prefix("10.230.0.0/24", "tenant_host"), _prefix("10.230.0.0/23", "tenant_host"))
    broken = _with(
        broken,
        "ServiceNetworkSegment",
        _segment("seg-a", "K8S_PROD", "10.230.0.0/24"),
        _segment("seg-b", "K8S_PROD", "10.230.0.0/23"),
    )
    findings = check_segment_subnets(_parse(broken))
    assert len(findings) == 1
    assert "'seg-a'" in findings[0].message
    assert "'seg-b'" in findings[0].message


def test_segments_allocated_from_the_pool_are_not_judged_against_the_pool(lab: dict[str, Any]) -> None:
    # 10.230.0.0/16 contains every segment subnet by design; it is excluded as
    # a pool resource rather than reported once per allocation.
    fine = _with(lab, "IpamPrefix", _prefix("10.230.0.0/24", "tenant_host"), _prefix("10.230.1.0/24", "tenant_host"))
    fine = _with(
        fine,
        "ServiceNetworkSegment",
        _segment("seg-a", "K8S_PROD", "10.230.0.0/24"),
        _segment("seg-b", "K8S_PROD", "10.230.1.0/24"),
    )
    assert check_segment_subnets(_parse(fine)) == []


def test_one_subnet_recorded_by_two_segments_is_reported(lab: dict[str, Any]) -> None:
    broken = _with(lab, "IpamPrefix", _prefix("10.230.5.0/24", "tenant_host"))
    broken = _with(
        broken,
        "ServiceNetworkSegment",
        _segment("seg-a", "K8S_PROD", "10.230.5.0/24"),
        _segment("seg-b", "K8S_PROD", "10.230.5.0/24"),
    )
    findings = check_segment_subnets(_parse(broken))
    assert len(findings) == 1
    assert "subnet of 2 segments ('seg-a', 'seg-b')" in findings[0].message


def test_a_segment_not_yet_built_is_skipped(lab: dict[str, Any]) -> None:
    fine = _with(lab, "ServiceNetworkSegment", _segment("pending", "K8S_PROD", None))
    assert check_segment_subnets(_parse(fine)) == []


# -- rule 3: VIP blocks -------------------------------------------------------


def test_a_vip_block_outside_the_pool_is_reported(lab: dict[str, Any]) -> None:
    broken = copy.deepcopy(lab)
    broken["ServiceFabricApp"]["edges"][2]["node"] = _app("otternet-telemetry", "10.113.0.0/28", [POOL])
    findings = check_vip_blocks(_parse(broken))
    assert len(findings) == 1
    assert "'otternet-telemetry'" in findings[0].message
    assert "10.113.0.0/28" in findings[0].message
    assert "pools: 10.112.240.0/24" in findings[0].message
    assert findings[0].object_type == "ServiceFabricApp"


def test_a_vip_block_inside_the_pool_is_clean(lab: dict[str, Any]) -> None:
    fine = copy.deepcopy(lab)
    fine["ServiceFabricApp"]["edges"][2]["node"] = _app("otternet-telemetry", "10.112.240.16/28", [POOL])
    assert check_vip_blocks(_parse(fine)) == []


def test_a_cluster_with_no_pools_is_reported(lab: dict[str, Any]) -> None:
    broken = copy.deepcopy(lab)
    broken["ServiceFabricApp"]["edges"][2]["node"] = _app("otternet-telemetry", "10.112.240.16/28", [])
    findings = check_vip_blocks(_parse(broken))
    assert len(findings) == 1
    assert "pools: none" in findings[0].message


def test_overlapping_vip_blocks_are_reported(lab: dict[str, Any]) -> None:
    broken = copy.deepcopy(lab)
    broken["ServiceFabricApp"]["edges"][1]["node"] = _app("otternet-metrics", "10.112.240.0/27", [POOL])
    findings = check_vip_blocks(_parse(broken))
    assert len(findings) == 1
    assert "'otternet-demo'" in findings[0].message
    assert "'otternet-metrics'" in findings[0].message


# -- collection ---------------------------------------------------------------


def test_findings_from_every_rule_are_collected(lab: dict[str, Any]) -> None:
    broken = _with(lab, "EvpnSvi", _svi("DUP_K8S", 110, "APP_PROD", "k8s", gateway="10.211.0.1"))
    broken = _with(broken, "IpamPrefix", _prefix("10.110.0.128/25", "tenant_host"))
    broken = _with(broken, "ServiceNetworkSegment", _segment("scratch-overlap", "K8S_PROD", "10.110.0.128/25"))
    broken["ServiceFabricApp"]["edges"][2]["node"] = _app("otternet-telemetry", "10.113.0.0/28", [POOL])
    broken["EvpnSvi"]["edges"][1]["node"]["vlan"] = _ipam_vlan("APP_HOSTS", 211)
    kinds = sorted(finding.object_type for finding in collect_findings(_parse(broken)))
    assert kinds == ["EvpnSvi", "EvpnSvi", "IpamPrefix", "ServiceFabricApp"]


@pytest.mark.parametrize(
    "empty",
    [
        {
            "EvpnTenant": {"edges": []},
            "EvpnSvi": {"edges": []},
            "ServiceNetworkSegment": {"edges": []},
            "IpamPrefix": {"edges": []},
            "CoreIPPrefixPool": {"edges": []},
            "ServiceFabricApp": {"edges": []},
        }
    ],
)
def test_an_empty_graph_reports_nothing_rather_than_raising(empty: Any) -> None:
    assert collect_findings(_parse(empty)) == []
