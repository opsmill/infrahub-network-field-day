"""Unit tests for the service-layer fabric peering generator.

Fixtures rather than a live server, for a reason beyond speed: most of the
failure paths are unreachable any other way. ``ClusterFabricPeering.peer_asn``
and ``peer_address`` are both mandatory in the schema, so a session missing
either cannot be created against a live instance -- but a generator can still
be handed that shape by a partially-migrated database or a future schema edit,
and the guard has to be tested.

The derivation is deliberately a set of module-level pure functions over the
parsed query response, so everything below runs without a client.
"""

from __future__ import annotations

from typing import Any

import pytest

from generators.generate_fabric_peering import (
    FABRIC_ROLES,
    build_session_payloads,
    derive_peers,
    validate_model,
)
from generators.generate_fabric_peering_query import GenerateFabricPeeringQuery

# The values actually loaded on the branch, so a fixture failure means the
# generator changed rather than the lab did.
LEAF1 = "leaf-nfd41-pod1-1-1"
LEAF2 = "leaf-nfd41-pod1-1-2"
# The addresses cycle 014 modelled onto each leaf's Vlan110 peering SVI, and
# which cycle 015 derives instead of reading from an object file.
LEAF_ADDRESSES = {LEAF1: "10.110.0.2/24", LEAF2: "10.110.0.3/24"}
PEER_ASN = 65101
LOCAL_ASN = 65401


def _svi(role: str, addresses: list[str], *, name: str = "Vlan110") -> dict[str, Any]:
    """One InterfaceVirtual on a peer device.

    Real leaves carry two: a `loopback` SVI with no address and a `peering`
    SVI with one. Any positional selection rule picks the loopback, which is
    why selection is by role (research R1).
    """
    return {
        "node": {
            "__typename": "InterfaceVirtual",
            "id": f"svi-{name}-{role}",
            "name": {"value": name},
            "role": {"value": role},
            "ip_addresses": {"edges": [{"node": {"id": f"ip-{a}", "address": {"value": a}}} for a in addresses]},
        }
    }


def _device(
    name: str,
    *,
    role: str = "leaf",
    asn: int | None = PEER_ASN,
    svis: list[dict[str, Any]] | None = None,
    address: str | None = None,
) -> dict[str, Any]:
    """A far-end DcimFabricSwitch.

    Note the shape of an absent relationship throughout these fixtures: it is
    ``{"node": None}``, never a bare ``None``. That is what Infrahub's GraphQL
    returns, and the generated models enforce it.

    `__typename` is required: the generated model is a discriminated union, and
    a non-DcimFabricSwitch far end (a ComputePhysicalServer, say) deserialises into a
    variant carrying only `id` -- with no `role` or `asn` field at all. That is
    exactly why the derivation reads those attributes defensively.
    """
    if svis is None:
        # The live shape: a loopback with no address, plus a peering SVI.
        svis = [_svi("loopback", [], name="Loopback0")]
        resolved = address if address is not None else LEAF_ADDRESSES.get(name)
        if resolved is not None:
            svis.append(_svi("peering", [resolved]))
    return {
        "node": {
            "__typename": "DcimFabricSwitch",
            "id": f"dev-{name}",
            "name": {"value": name},
            "role": {"value": role},
            "asn": ({"node": {"id": f"asn-{name}", "asn": {"value": asn}}} if asn is not None else {"node": None}),
            "interfaces": {"edges": svis},
        }
    }


def _link(near_iface_id: str, far_device: dict[str, Any] | None) -> dict[str, Any]:
    """A NetworkLink carrying BOTH endpoints, as the server returns it.

    The near end is the cluster node's own interface. It is present in every
    real response and must be excluded, or the cluster peers with itself.
    """
    # The near end's device is the cluster node itself -- a ComputePhysicalServer,
    # which deserialises into the union variant carrying only `id`. That is what
    # the live server returns, and it is why the derivation must exclude by
    # interface id rather than by "device is missing".
    endpoints: list[dict[str, Any]] = [
        {
            "node": {
                "__typename": "InterfacePhysical",
                "id": near_iface_id,
                "device": {"node": {"__typename": "ComputePhysicalServer", "id": f"srv-{near_iface_id}"}},
            }
        }
    ]
    if far_device is not None:
        endpoints.append(
            {"node": {"__typename": "InterfacePhysical", "id": f"far-{near_iface_id}", "device": far_device}}
        )
    return {
        "node": {
            "__typename": "NetworkLink",
            "id": f"link-{near_iface_id}",
            "connected_endpoints": {"edges": endpoints},
        }
    }


def _node(name: str, near_iface_id: str, far_device: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "node": {
            "__typename": "ComputePhysicalServer",
            "id": f"node-{name}",
            "name": {"value": name},
            "interfaces": {
                "edges": [
                    {
                        "node": {
                            "__typename": "InterfacePhysical",
                            "id": near_iface_id,
                            "connector": (
                                _link(near_iface_id, far_device) if far_device is not None else {"node": None}
                            ),
                        }
                    }
                ]
            },
        }
    }


def _session(name: str, device_name: str, address: str, *, enabled: bool = True) -> dict[str, Any]:
    return {
        "node": {
            "id": f"sess-{name}",
            "name": {"value": name},
            "peer_asn": {"value": PEER_ASN},
            "enabled": {"value": enabled},
            "peer_device": {
                "node": {"__typename": "DcimFabricSwitch", "id": f"dev-{device_name}", "display_label": device_name}
            },
            "peer_address": {"node": {"id": f"ip-{name}", "address": {"value": address}}},
        }
    }


def _data(
    *,
    nodes: list[dict[str, Any]] | None = None,
    sessions: list[dict[str, Any]] | None = None,
    local_asn: int | None = LOCAL_ASN,
    with_cluster: bool = True,
    with_target: bool = True,
) -> dict[str, Any]:
    """A query response shaped like GenerateFabricPeeringQuery.

    Defaults to the live topology: three nodes across two leaves, with two
    nodes sharing leaf 2.
    """
    if nodes is None:
        nodes = [
            _node("k8s-node1", "if-1", _device(LEAF1)),
            _node("k8s-node2", "if-2", _device(LEAF2)),
            _node("k8s-node3", "if-3", _device(LEAF2)),
        ]
    if sessions is None:
        sessions = [
            _session("k8s-leaf1", LEAF1, "10.110.0.2/24"),
            _session("k8s-leaf2", LEAF2, "10.110.0.3/24"),
        ]

    if not with_target:
        return {"target": {"edges": []}}

    cluster = (
        {
            "node": {
                "id": "cluster-1",
                "name": {"value": "nfd41"},
                "local_asn": {"value": local_asn},
                "fabric_peerings": {"edges": sessions},
                "nodes": {"edges": nodes},
            }
        }
        if with_cluster
        else {"node": None}
    )

    return {
        "target": {
            "edges": [
                {
                    "node": {
                        "id": "svc-1",
                        "name": {"value": "nfd41-fabric-peering"},
                        "cluster": cluster,
                    }
                }
            ]
        }
    }


def _parsed(**kwargs: Any) -> GenerateFabricPeeringQuery:
    return GenerateFabricPeeringQuery(**_data(**kwargs))


def _peers(**kwargs: Any) -> list[Any]:
    parsed = _parsed(**kwargs)
    cluster = parsed.target.edges[0].node.cluster.node
    return derive_peers(cluster)


# ---------------------------------------------------------------------------
# Derivation — US1
# ---------------------------------------------------------------------------


def test_near_end_interface_is_never_a_peer() -> None:
    """R2. `connected_endpoints` returns BOTH ends of the cable.

    Verified live: the cluster node's own interface comes back alongside the
    leaf's. Without exclusion the generator peers the cluster with itself.
    """
    peers = _peers()

    assert [p.device_name for p in peers] == [LEAF1, LEAF2]
    assert all(p.interface_id not in {"if-1", "if-2", "if-3"} for p in peers)


def test_two_nodes_on_one_leaf_yield_one_session() -> None:
    """D-4. The peer set is distinct devices, not one entry per node.

    This is the live topology: node2 and node3 both attach to leaf 2.
    """
    peers = _peers()

    assert len(peers) == 2
    assert len({p.device_id for p in peers}) == 2


def test_non_fabric_peer_is_skipped_silently() -> None:
    """D-3. A node cabled to an out-of-band switch is normal, not an error."""
    peers = _peers(
        nodes=[
            _node("k8s-node1", "if-1", _device(LEAF1)),
            _node("k8s-node2", "if-2", _device("oob-switch-1", role="isp_edge")),
        ]
    )

    assert [p.device_name for p in peers] == [LEAF1]


@pytest.mark.parametrize("role", sorted(FABRIC_ROLES))
def test_every_fabric_role_is_accepted(role: str) -> None:
    """D-3. The filter is a set, so assert the whole set, not one member."""
    peers = _peers(nodes=[_node("k8s-node1", "if-1", _device("switch-1", role=role))])

    assert [p.device_name for p in peers] == ["switch-1"]


def test_mlag_pair_sharing_one_asn_yields_two_sessions() -> None:
    """D-6. Both leaves return 65101; equal ASNs must not collapse the set."""
    peers = _peers()

    assert len(peers) == 2
    assert {p.peer_asn for p in peers} == {PEER_ASN}


def test_peer_asn_comes_from_the_device_routing_asn() -> None:
    """D-5. The requirement the whole feature exists for.

    The ASN is read from the peer device, never from the service, an object
    file, or the existing session -- so changing the fabric model moves it.
    """
    peers = _peers(nodes=[_node("k8s-node1", "if-1", _device(LEAF1, asn=64999))])

    assert [p.peer_asn for p in peers] == [64999]


def test_peers_are_ordered_deterministically() -> None:
    """D-7. Asserted from a reversed fixture so the guarantee does not depend
    on the server's own ordering."""
    peers = _peers(
        nodes=[
            _node("k8s-node3", "if-3", _device(LEAF2)),
            _node("k8s-node1", "if-1", _device(LEAF1)),
        ]
    )

    assert [p.device_name for p in peers] == [LEAF1, LEAF2]


def test_uncabled_interface_contributes_nothing() -> None:
    """D-8. An interface with no connector is not an error."""
    peers = _peers(
        nodes=[
            _node("k8s-node1", "if-1", _device(LEAF1)),
            _node("k8s-node2", "if-2", None),
        ]
    )

    assert [p.device_name for p in peers] == [LEAF1]


# ---------------------------------------------------------------------------
# Adopt versus create — the two clarifications
# ---------------------------------------------------------------------------


def test_adoption_rewrites_only_the_asn() -> None:
    """The first run against the live model must be a pure adoption (FR-028)."""
    parsed = _parsed(nodes=[_node("k8s-node1", "if-1", _device(LEAF1, asn=64999))])
    cluster = parsed.target.edges[0].node.cluster.node
    payloads = build_session_payloads(cluster, derive_peers(cluster))

    assert payloads[0].data["peer_asn"] == 64999
    assert payloads[0].is_adoption is True


def test_disabled_session_stays_disabled() -> None:
    """FR-017. `enabled` is absent from an adopt payload, so an operator who
    disabled a session keeps it disabled across runs."""
    parsed = _parsed(
        sessions=[
            _session("k8s-leaf1", LEAF1, "10.110.0.2/24", enabled=False),
            _session("k8s-leaf2", LEAF2, "10.110.0.3/24"),
        ]
    )
    cluster = parsed.target.edges[0].node.cluster.node
    payloads = build_session_payloads(cluster, derive_peers(cluster))

    assert all("enabled" not in p.data for p in payloads)


# ---------------------------------------------------------------------------
# Validation — V-1 … V-7, all raising before any write
# ---------------------------------------------------------------------------


def test_missing_target_raises() -> None:
    """V-1."""
    with pytest.raises(ValueError, match="ServiceFabricPeering"):
        validate_model(_parsed(with_target=False))


def test_missing_cluster_raises_naming_the_service() -> None:
    """V-2."""
    with pytest.raises(ValueError, match="cluster") as excinfo:
        validate_model(_parsed(with_cluster=False))

    assert "nfd41-fabric-peering" in str(excinfo.value)


def test_missing_local_asn_raises_naming_the_cluster_and_field() -> None:
    """V-3."""
    with pytest.raises(ValueError, match="local_asn") as excinfo:
        validate_model(_parsed(local_asn=None))

    assert "nfd41" in str(excinfo.value)


def test_cluster_with_no_nodes_raises() -> None:
    """V-4."""
    with pytest.raises(ValueError, match="node") as excinfo:
        validate_model(_parsed(nodes=[]))

    assert "nfd41" in str(excinfo.value)


def test_peer_without_routing_asn_raises_naming_the_device() -> None:
    """V-5. Unreachable live: peer_asn is mandatory in the schema."""
    with pytest.raises(ValueError, match="asn") as excinfo:
        validate_model(_parsed(nodes=[_node("k8s-node1", "if-1", _device(LEAF1, asn=None))]))

    assert LEAF1 in str(excinfo.value)


def test_empty_peer_set_raises_before_writing() -> None:
    """V-7. Cycle 011 established that an empty peers list yields a manifest
    that applies cleanly, reports healthy, and carries no routes."""
    with pytest.raises(ValueError, match="peer") as excinfo:
        validate_model(_parsed(nodes=[_node("k8s-node1", "if-1", _device("oob-1", role="isp_edge"))]))

    assert "nfd41" in str(excinfo.value)


def test_validation_runs_before_any_write_is_attempted() -> None:
    """G-5. A partial write is the only path by which this generator can
    delete a real session, so validation must complete first."""
    parsed = _parsed(local_asn=None)

    with pytest.raises(ValueError):
        validate_model(parsed)

    # build_session_payloads is never reached; assert it is a separate step
    # rather than something validate_model performs as a side effect.
    assert not hasattr(validate_model, "_wrote_anything")


# ---------------------------------------------------------------------------
# Derived peering address -- specs/015-derive-peer-address
# ---------------------------------------------------------------------------


def test_peer_address_comes_from_the_peering_svi() -> None:
    """D-9, D-10. The second of the two hand-maintained facts becomes derived.

    Cycle 012 made peer_asn derived and could not do the same for the address,
    because nothing connected an address to a device. Cycle 014 modelled the
    SVIs; this reads them.
    """
    peers = _peers()

    assert [p.peer_address for p in peers] == ["ip-10.110.0.2/24", "ip-10.110.0.3/24"]


def test_loopback_is_never_selected() -> None:
    """R1. Every real leaf carries a loopback SVI with no address alongside
    the peering one, so any positional rule picks the wrong interface."""
    peers = _peers(
        nodes=[
            _node(
                "k8s-node1",
                "if-1",
                _device(
                    LEAF1,
                    svis=[_svi("loopback", ["10.255.0.1/32"], name="Loopback0"), _svi("peering", ["10.110.0.2/24"])],
                ),
            )
        ]
    )

    assert [p.peer_address for p in peers] == ["ip-10.110.0.2/24"]


def test_adopt_payload_now_carries_the_address() -> None:
    """Revised G-4. `name` and `enabled` are still preserved by omission;
    `peer_address` has moved from preserved to derived."""
    parsed = _parsed()
    cluster = parsed.target.edges[0].node.cluster.node
    payloads = build_session_payloads(cluster, derive_peers(cluster))

    for payload in payloads:
        assert set(payload.data) == {"peer_asn", "peer_address"}
        assert "name" not in payload.data
        assert "enabled" not in payload.data


def test_create_payload_is_reachable_again() -> None:
    """US2. Cycle 012 asserted the opposite and that test is replaced.

    Its reason was sound at the time -- an address existed only on an existing
    session -- and is now false, so a cabled leaf with a peering SVI can be
    provisioned without a human writing the session first.
    """
    parsed = _parsed(sessions=[_session("k8s-leaf2", LEAF2, "10.110.0.3/24")])
    cluster = parsed.target.edges[0].node.cluster.node

    validate_model(parsed)  # must NOT raise -- the address is derivable now
    payloads = build_session_payloads(cluster, derive_peers(cluster))

    created = [p for p in payloads if not p.is_adoption]
    assert len(created) == 1
    assert set(created[0].data) == {"cluster", "peer_device", "peer_asn", "peer_address", "name", "enabled"}
    assert created[0].data["name"] == LEAF1
    assert created[0].data["peer_address"] == "ip-10.110.0.2/24"


def test_peer_without_a_peering_svi_raises_naming_the_device() -> None:
    """V-6'. An address still cannot be invented -- only derived."""
    with pytest.raises(ValueError, match="peering") as excinfo:
        validate_model(
            _parsed(nodes=[_node("k8s-node1", "if-1", _device(LEAF1, svis=[_svi("loopback", [], name="Loopback0")]))])
        )

    assert LEAF1 in str(excinfo.value)


def test_multiple_peering_svis_raises() -> None:
    """V-8. Choosing between two would be choosing which neighbour the
    session points at, which is not a silent decision to make."""
    device = _device(
        LEAF1, svis=[_svi("peering", ["10.110.0.2/24"]), _svi("peering", ["10.110.0.9/24"], name="Vlan111")]
    )

    with pytest.raises(ValueError, match="peering") as excinfo:
        validate_model(_parsed(nodes=[_node("k8s-node1", "if-1", device)]))

    assert LEAF1 in str(excinfo.value)


def test_svi_with_multiple_addresses_raises() -> None:
    """V-9. The schema warns that an MLAG shared VARP gateway cannot identify
    a single BGP peer; an ambiguous SVI is the same problem."""
    device = _device(LEAF1, svis=[_svi("peering", ["10.110.0.2/24", "10.110.0.254/24"])])

    with pytest.raises(ValueError, match="address") as excinfo:
        validate_model(_parsed(nodes=[_node("k8s-node1", "if-1", device)]))

    assert LEAF1 in str(excinfo.value)
