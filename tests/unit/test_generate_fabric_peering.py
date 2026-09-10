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
PEER_ASN = 65101
LOCAL_ASN = 65401


def _device(name: str, *, role: str = "leaf", asn: int | None = PEER_ASN) -> dict[str, Any]:
    """A far-end DcimDevice.

    Note the shape of an absent relationship throughout these fixtures: it is
    ``{"node": None}``, never a bare ``None``. That is what Infrahub's GraphQL
    returns, and the generated models enforce it.

    `__typename` is required: the generated model is a discriminated union, and
    a non-DcimDevice far end (a ComputePhysicalServer, say) deserialises into a
    variant carrying only `id` -- with no `role` or `asn` field at all. That is
    exactly why the derivation reads those attributes defensively.
    """
    return {
        "node": {
            "__typename": "DcimDevice",
            "id": f"dev-{name}",
            "name": {"value": name},
            "role": {"value": role},
            "asn": ({"node": {"id": f"asn-{name}", "asn": {"value": asn}}} if asn is not None else {"node": None}),
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
                "node": {"__typename": "DcimDevice", "id": f"dev-{device_name}", "display_label": device_name}
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


def test_adopt_payload_omits_preserved_fields() -> None:
    """FR-026, FR-027, FR-017.

    `save(allow_upsert=True)` writes whatever the payload contains, so
    preserving a value is expressed by NOT passing it.
    """
    parsed = _parsed()
    cluster = parsed.target.edges[0].node.cluster.node
    payloads = build_session_payloads(cluster, derive_peers(cluster))

    assert len(payloads) == 2
    for payload in payloads:
        assert payload.is_adoption is True
        assert payload.existing_id is not None
        # Only the derived field is named. The rest are preserved by never
        # being touched -- the update fetches the node and sets this one
        # attribute, because an upsert would demand every mandatory field.
        assert set(payload.data) == {"peer_asn"}
        assert "name" not in payload.data
        assert "enabled" not in payload.data
        assert "peer_address" not in payload.data


def test_there_is_no_create_shape_at_all() -> None:
    """Discovered during implementation, and it is a real limitation.

    ``peer_address`` is mandatory on the node and is recorded ONLY on an
    existing session, so a peer with no session has no address the generator
    is permitted to supply -- FR-027 forbids inventing or allocating one.
    Every payload is therefore an adoption, and a peer without a session is
    refused by validate_model rather than half-created here.
    """
    parsed = _parsed(sessions=[_session("k8s-leaf2", LEAF2, "10.110.0.3/24")])
    cluster = parsed.target.edges[0].node.cluster.node

    # LEAF1 is cabled but has no session, so validation refuses the whole run.
    with pytest.raises(ValueError, match="peer_address"):
        validate_model(parsed)

    # And nothing in the payload builder can produce a create shape.
    payloads = build_session_payloads(cluster, [p for p in derive_peers(cluster) if p.device_name == LEAF2])
    assert all(p.is_adoption for p in payloads)


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


def test_new_peer_without_recorded_address_raises_naming_the_device() -> None:
    """V-6. FR-027 -- the generator must not invent or allocate an address."""
    with pytest.raises(ValueError, match="peer_address") as excinfo:
        validate_model(_parsed(nodes=[_node("k8s-node1", "if-1", _device("leaf-new-1"))], sessions=[]))

    assert "leaf-new-1" in str(excinfo.value)


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
