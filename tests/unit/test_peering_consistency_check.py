"""Unit tests for the peering consistency check.

Fixtures rather than a live instance, because most violations cannot be created
against a live one: the generator refuses to write them and the schema forbids
some outright. A proposed change can still contain them, which is exactly why
the check exists.
"""

from __future__ import annotations

from typing import Any

from checks.peering_consistency_check import (
    check_address_matches_svi,
    check_asn_matches_device,
    check_one_service_per_cluster,
    check_peer_is_cabled,
    check_peer_role,
    check_svi_node_agreement,
    collect_findings,
)
from checks.peering_consistency_check_query import PeeringConsistencyCheckQuery

LEAF1 = "leaf-nfd41-pod1-1-1"
LEAF2 = "leaf-nfd41-pod1-1-2"
ASN = 65101
ADDR1 = "10.110.0.2/24"
ADDR2 = "10.110.0.3/24"
PEERING_VLAN = 110


def _svi(
    device: str,
    *,
    role: str = "peering",
    vlan: int = PEERING_VLAN,
    addresses: list[str] | None = None,
    name: str = "Vlan110",
) -> dict[str, Any]:
    return {
        "node": {
            "__typename": "InterfaceVirtual",
            "id": f"svi-{device}-{name}",
            "name": {"value": name},
            "role": {"value": role},
            "dot1q_id": {"value": vlan},
            "device": {"node": {"__typename": "DcimDevice", "id": f"dev-{device}", "display_label": device}},
            "ip_addresses": {
                "edges": [{"node": {"id": f"ip-{a}", "address": {"value": a}}} for a in (addresses or [])]
            },
        }
    }


def _session(
    name: str, device: str, *, asn: int = ASN, address: str | None = None, role: str = "leaf", cluster: str = "nfd41"
) -> dict[str, Any]:
    return {
        "node": {
            "__typename": "ClusterFabricPeering",
            "id": f"sess-{name}",
            "name": {"value": name},
            "peer_asn": {"value": asn},
            "cluster": {"node": {"id": f"cl-{cluster}", "name": {"value": cluster}}},
            "peer_device": {
                "node": {
                    "__typename": "DcimDevice",
                    "id": f"dev-{device}",
                    "display_label": device,
                    "name": {"value": device},
                    "role": {"value": role},
                    "asn": {"node": {"id": f"asn-{device}", "asn": {"value": ASN}}},
                }
            },
            "peer_address": (
                {"node": {"id": f"ip-{address}", "address": {"value": address}}} if address else {"node": None}
            ),
        }
    }


def _service(name: str, cluster: str = "nfd41") -> dict[str, Any]:
    return {
        "node": {
            "__typename": "ServiceFabricPeering",
            "id": f"svc-{name}",
            "name": {"value": name},
            "cluster": {"node": {"id": f"cl-{cluster}", "name": {"value": cluster}}},
        }
    }


def _evpn_node(device: str, address: str, *, vlan: int = PEERING_VLAN) -> dict[str, Any]:
    return {
        "node": {
            "__typename": "EvpnSviNode",
            "id": f"evpn-{device}-{vlan}",
            "ip_address": {"value": address},
            "device": {"node": {"__typename": "DcimDevice", "id": f"dev-{device}", "display_label": device}},
            "svi": {"node": {"id": f"evpnsvi-{vlan}", "svi_id": {"value": vlan}}},
        }
    }


def _cluster(*, cabled: list[str] | None = None, name: str = "nfd41") -> dict[str, Any]:
    if cabled is None:
        cabled = [LEAF1, LEAF2]
    nodes = []
    for idx, device in enumerate(cabled):
        near = f"if-node{idx}"
        nodes.append(
            {
                "node": {
                    "__typename": "ComputePhysicalServer",
                    "id": f"node-{idx}",
                    "interfaces": {
                        "edges": [
                            {
                                "node": {
                                    "__typename": "InterfacePhysical",
                                    "id": near,
                                    "connector": {
                                        "node": {
                                            "__typename": "NetworkLink",
                                            "id": f"link-{idx}",
                                            "connected_endpoints": {
                                                "edges": [
                                                    {
                                                        "node": {
                                                            "__typename": "InterfacePhysical",
                                                            "id": near,
                                                            "device": {
                                                                "node": {
                                                                    "__typename": "ComputePhysicalServer",
                                                                    "id": f"srv-{idx}",
                                                                }
                                                            },
                                                        }
                                                    },
                                                    {
                                                        "node": {
                                                            "__typename": "InterfacePhysical",
                                                            "id": f"far-{idx}",
                                                            "device": {
                                                                "node": {
                                                                    "__typename": "DcimDevice",
                                                                    "id": f"dev-{device}",
                                                                }
                                                            },
                                                        }
                                                    },
                                                ]
                                            },
                                        }
                                    },
                                }
                            }
                        ]
                    },
                }
            }
        )
    return {
        "node": {
            "__typename": "ClusterKubernetes",
            "id": f"cl-{name}",
            "name": {"value": name},
            "nodes": {"edges": nodes},
        }
    }


def _data(
    *,
    services: list[dict[str, Any]] | None = None,
    sessions: list[dict[str, Any]] | None = None,
    svis: list[dict[str, Any]] | None = None,
    evpn_nodes: list[dict[str, Any]] | None = None,
    clusters: list[dict[str, Any]] | None = None,
) -> PeeringConsistencyCheckQuery:
    """A clean, self-consistent model by default -- what the generator produces."""
    if services is None:
        services = [_service("nfd41-fabric-peering")]
    if sessions is None:
        sessions = [_session("k8s-leaf1", LEAF1, address=ADDR1), _session("k8s-leaf2", LEAF2, address=ADDR2)]
    if svis is None:
        svis = [_svi(LEAF1, addresses=[ADDR1]), _svi(LEAF2, addresses=[ADDR2])]
    if evpn_nodes is None:
        evpn_nodes = [_evpn_node(LEAF1, ADDR1), _evpn_node(LEAF2, ADDR2)]
    if clusters is None:
        clusters = [_cluster()]
    return PeeringConsistencyCheckQuery(
        ServiceFabricPeering={"edges": services},
        ClusterFabricPeering={"edges": sessions},
        InterfaceVirtual={"edges": svis},
        EvpnSviNode={"edges": evpn_nodes},
        ClusterKubernetes={"edges": clusters},
    )


# ---------------------------------------------------------------------------
# The most important test
# ---------------------------------------------------------------------------


def test_clean_model_passes() -> None:
    """G-1. A check that fails a generator-produced model is worse than no
    check: it and the generator disagree, and neither can then be trusted."""
    assert [f for f in collect_findings(_data()) if f.is_error] == []


def test_empty_model_passes() -> None:
    """SC-008. Asserted deliberately rather than left to chance -- an empty
    result set passing by accident is the vacuous-pass failure mode."""
    empty = _data(services=[], sessions=[], svis=[], evpn_nodes=[], clusters=[])

    assert collect_findings(empty) == []


# ---------------------------------------------------------------------------
# C-1 .. C-5
# ---------------------------------------------------------------------------


def test_asn_mismatch_is_reported() -> None:
    """C-1. The device is authoritative, so a hand-edited session is drift."""
    findings = check_asn_matches_device(_data(sessions=[_session("k8s-leaf1", LEAF1, asn=64999, address=ADDR1)]))

    assert len(findings) == 1
    assert "64999" in findings[0].message
    assert str(ASN) in findings[0].message


def test_address_mismatch_is_reported() -> None:
    """C-2."""
    findings = check_address_matches_svi(_data(sessions=[_session("k8s-leaf1", LEAF1, address="10.110.0.99/24")]))

    assert len(findings) == 1
    assert "10.110.0.99/24" in findings[0].message
    assert ADDR1 in findings[0].message


def test_two_services_on_one_cluster_is_reported() -> None:
    """C-3. Cycle 012's evidence recorded that both would fight over the same
    sessions on every generator run."""
    findings = check_one_service_per_cluster(_data(services=[_service("first"), _service("second")]))

    assert len(findings) == 2
    assert all("claimed by 2 peering services" in f.message for f in findings)


def test_uncabled_peer_is_reported() -> None:
    """C-4. A session to a device the cluster cannot reach is not a session."""
    findings = check_peer_is_cabled(_data(clusters=[_cluster(cabled=[LEAF1])]))

    assert len(findings) == 1
    assert LEAF2 in findings[0].message


def test_non_leaf_peer_is_reported() -> None:
    """C-5. An out-of-band switch is not a fabric peer."""
    findings = check_peer_role(_data(sessions=[_session("k8s-leaf1", LEAF1, address=ADDR1, role="isp_edge")]))

    assert len(findings) == 1
    assert "isp_edge" in findings[0].message


# ---------------------------------------------------------------------------
# C-6 / C-7 -- the duplication cycle 014 flagged
# ---------------------------------------------------------------------------


def test_svi_node_disagreement_is_reported() -> None:
    """C-6. The fabric holds two copies of each peering address and nothing
    enforced agreement until now."""
    findings = check_svi_node_agreement(_data(evpn_nodes=[_evpn_node(LEAF1, "10.110.0.77/24")]))

    errors = [f for f in findings if f.is_error]
    assert len(errors) == 1
    assert "10.110.0.77/24" in errors[0].message


def test_svi_node_matching_is_by_device_and_vlan() -> None:
    """R5. A device carries several SVI nodes. Matching on device alone would
    compare a peering SVI against an unrelated tenant SVI and report a
    difference that is not drift."""
    findings = check_svi_node_agreement(
        _data(
            svis=[_svi(LEAF1, addresses=[ADDR1]), _svi(LEAF1, vlan=210, addresses=["10.210.0.1/24"], name="Vlan210")],
            evpn_nodes=[_evpn_node(LEAF1, ADDR1), _evpn_node(LEAF1, "10.210.0.1/24", vlan=210)],
        )
    )

    assert [f for f in findings if f.is_error] == []


def test_svi_node_without_a_matching_interface_is_advisory() -> None:
    """C-7, R3. The SDK has no log_warning, so this must be log_info or it
    would block a merge for something that is not necessarily wrong: not every
    SVI node is a peering SVI."""
    findings = check_svi_node_agreement(_data(evpn_nodes=[_evpn_node(LEAF1, ADDR1, vlan=999)]))

    assert len(findings) == 1
    assert findings[0].is_error is False


# ---------------------------------------------------------------------------
# Reporting behaviour
# ---------------------------------------------------------------------------


def test_every_violation_is_reported() -> None:
    """G-2, SC-007. Stopping at the first forces a merge-fix-merge cycle per
    independent problem."""
    findings = collect_findings(
        _data(
            services=[_service("first"), _service("second")],
            sessions=[
                _session("k8s-leaf1", LEAF1, asn=64999, address="10.110.0.99/24"),
                _session("k8s-leaf2", LEAF2, address=ADDR2, role="isp_edge"),
            ],
        )
    )
    errors = [f for f in findings if f.is_error]

    # two services + asn + address + non-leaf role
    assert len(errors) >= 5


def test_every_error_carries_attribution() -> None:
    """G-3. Without an id and type the failure cannot be attributed in the
    proposed-change UI."""
    findings = collect_findings(_data(sessions=[_session("k8s-leaf1", LEAF1, asn=64999, address="10.110.0.99/24")]))

    for finding in findings:
        assert finding.object_id
        assert finding.object_type
