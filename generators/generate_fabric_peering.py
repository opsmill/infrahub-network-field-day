"""Service-layer fabric peering generator.

Materializes the technical objects beneath a `ServiceFabricPeering`: one
`ClusterFabricPeering` per fabric device the cluster's nodes are cabled to.
This is the generator that sits underneath the services schema, and it closes
the loop cycle 010 opened and cycle 011 half-built -- order a service, the
generator derives the sessions, the transform renders the manifest.

Before this, `objects/34_nfd41_cluster.yml` declared those sessions by hand,
including each leaf's BGP AS. That second copy is what the lab's own notes warn
about:

    Change either side without the other and BGP either does not come up or
    comes up and carries nothing.

`peer_asn` now comes from the peer device's own `RoutingAsn` -- the same node
AVD renders the switch from -- so the two ends cannot drift apart.

Two things about this generator are deliberate and easy to get wrong:

* **The near end is excluded by interface id.** `NetworkLink.connected_endpoints`
  returns *both* ends of the cable, including the cluster node's own interface.
  Filtering by device kind happens to work today only because cluster nodes are
  `ComputePhysicalServer` rather than `DcimDevice`; filtering by id is what is
  actually meant.
* **Adoption fetches and modifies; it does not upsert.** An upsert mutation
  validates every mandatory field on the node -- `name`, `peer_address`,
  `peer_asn` -- so a payload that omits them in order to preserve them is
  rejected outright. Fetching the existing session and setting one attribute
  leaves the others exactly as they were. Only `peer_asn` is ever rewritten.

An incomplete model raises before anything is written. That ordering is load
bearing rather than tidy: the tracking context deletes previously-managed
objects this run did not touch, so a partial write is the one path by which this
generator can delete a real session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from infrahub_sdk.generator import InfrahubGenerator

from .generate_fabric_peering_query import (
    GenerateFabricPeeringQuery,
    GenerateFabricPeeringQueryTargetEdgesNodeClusterNode,
)

# Readable alias for the verbose generated class, following
# transforms/avd_anta_catalog.py. The deeper ones are reached through
# attribute access rather than named, because their generated names run past
# 200 characters.
ClusterNode = GenerateFabricPeeringQueryTargetEdgesNodeClusterNode

# Fabric devices a cluster node can legitimately attach to. A node cabled to
# anything else -- an out-of-band switch, a firewall -- contributes no session.
FABRIC_ROLES = frozenset({"leaf", "border_leaf", "l2leaf"})


@dataclass(frozen=True)
class DerivedPeer:
    """One fabric device the cluster should peer with, and why."""

    device_id: str
    device_name: str
    peer_asn: int | None
    interface_id: str
    """The far-end interface. Kept so the near end can be proven excluded."""


@dataclass
class SessionPayload:
    """A single upsert, and whether it adopts an existing session."""

    device_name: str
    is_adoption: bool
    data: dict[str, Any] = field(default_factory=dict)
    existing_id: str | None = None


def _value(wrapper: Any) -> Any:
    """Unwrap an Infrahub ``{"value": ...}`` wrapper, tolerating absence."""
    return wrapper.value if wrapper is not None else None


def _node_of(relationship: Any) -> Any:
    """Unwrap a cardinality-one relationship, tolerating absence."""
    return relationship.node if relationship is not None else None


def _edges_of(relationship: Any) -> list[Any]:
    """Unwrap a cardinality-many relationship into its nodes, skipping nulls."""
    if relationship is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def derive_peers(cluster: ClusterNode) -> list[DerivedPeer]:
    """The fabric devices this cluster's nodes are cabled to.

    Distinct by device, filtered to fabric roles, sorted by device name so an
    unchanged model produces an unchanged write order.

    The near end is excluded by interface id: every link returns both of its
    endpoints, and one of them is always the interface the traversal arrived
    through.
    """
    peers: dict[str, DerivedPeer] = {}

    for node in _edges_of(cluster.nodes):
        for interface in _edges_of(getattr(node, "interfaces", None)):
            near_id = interface.id
            link = _node_of(getattr(interface, "connector", None))
            if link is None:
                continue

            for endpoint in _edges_of(getattr(link, "connected_endpoints", None)):
                if endpoint.id == near_id:
                    continue

                device = _node_of(getattr(endpoint, "device", None))
                if device is None:
                    continue

                role = _value(getattr(device, "role", None))
                if role not in FABRIC_ROLES:
                    continue

                asn_node = _node_of(getattr(device, "asn", None))
                peers[device.id] = DerivedPeer(
                    device_id=device.id,
                    device_name=_value(getattr(device, "name", None)),
                    peer_asn=_value(getattr(asn_node, "asn", None)) if asn_node else None,
                    interface_id=endpoint.id,
                )

    return sorted(peers.values(), key=lambda peer: peer.device_name or "")


def _existing_by_device(cluster: ClusterNode) -> dict[str, Any]:
    """Index the cluster's current sessions by the device they peer with."""
    index: dict[str, Any] = {}
    for session in _edges_of(cluster.fabric_peerings):
        device = _node_of(session.peer_device)
        if device is not None:
            index[device.id] = session
    return index


def validate_model(parsed: GenerateFabricPeeringQuery) -> ClusterNode:
    """Check everything before a single object is written.

    Raises:
        ValueError: naming the object and the field, for each of V-1 … V-7 in
            the feature's data model. Raising here rather than mid-write is
            what stops a partial run from deleting sessions the tracking
            context no longer sees.
    """
    service = parsed.target.edges[0].node if parsed.target.edges else None
    if service is None:
        msg = "no ServiceFabricPeering matched the requested name"
        raise ValueError(msg)

    service_name = _value(service.name)
    cluster = _node_of(service.cluster)
    if cluster is None:
        msg = f"service {service_name!r} has no cluster; there is nothing to derive sessions for"
        raise ValueError(msg)

    cluster_name = _value(cluster.name)
    if _value(cluster.local_asn) is None:
        msg = f"cluster {cluster_name!r} has no local_asn; a BGP session cannot come up without one"
        raise ValueError(msg)

    if not _edges_of(cluster.nodes):
        msg = f"cluster {cluster_name!r} has no nodes; there is no cabling to derive peers from"
        raise ValueError(msg)

    peers = derive_peers(cluster)
    if not peers:
        msg = (
            f"cluster {cluster_name!r} has no cabled fabric peer; rendering an empty peers "
            "list would produce a manifest that applies cleanly and carries nothing"
        )
        raise ValueError(msg)

    existing = _existing_by_device(cluster)
    for peer in peers:
        if peer.peer_asn is None:
            msg = f"peer device {peer.device_name!r} has no asn; peer_asn cannot be derived"
            raise ValueError(msg)

        if peer.device_id not in existing:
            msg = (
                f"peer device {peer.device_name!r} is cabled to the cluster but has no "
                "ClusterFabricPeering recording its peer_address; this generator derives "
                "peer_asn but does not invent or allocate an address (FR-027). Add the "
                "session with its address, or model the leaf's peering SVI so the address "
                "becomes derivable"
            )
            raise ValueError(msg)

    return cluster


def build_session_payloads(cluster: ClusterNode, peers: list[DerivedPeer]) -> list[SessionPayload]:
    """One upsert payload per derived peer.

    Every payload is an adoption carrying ``peer_asn`` and the natural key.
    ``name``, ``enabled`` and ``peer_address`` are preserved by being left out,
    because ``save(allow_upsert=True)`` writes whatever it is given.

    There is deliberately no "create" shape. ``peer_address`` is mandatory on
    the node and is recorded only on an existing session, so a peer with no
    session has no address this generator is allowed to supply -- FR-027
    forbids inventing or allocating one. ``validate_model`` refuses that case
    before this function is reached, which is what keeps the two shapes from
    collapsing into a half-populated third.

    The payload names only the field to change. It is applied by fetching the
    existing node and setting that attribute, NOT by an upsert: an upsert
    validates every mandatory field on the node, so "omit a field to preserve
    it" is not expressible that way. Fetch-and-modify preserves ``name``,
    ``enabled`` and ``peer_address`` because it never touches them.
    """
    existing = _existing_by_device(cluster)

    return [
        SessionPayload(
            device_name=peer.device_name,
            is_adoption=True,
            data={"peer_asn": peer.peer_asn},
            existing_id=existing[peer.device_id].id,
        )
        for peer in peers
    ]


class FabricPeeringGenerator(InfrahubGenerator):
    """Derive a cluster's fabric BGP sessions from its cabling."""

    async def generate(self, data: dict) -> None:
        """Upsert one ClusterFabricPeering per cabled fabric device."""
        parsed = GenerateFabricPeeringQuery(**data)

        cluster = validate_model(parsed)
        peers = derive_peers(cluster)
        payloads = build_session_payloads(cluster, peers)

        session_ids: list[str] = []
        for payload in payloads:
            # Fetch and modify rather than upsert. An upsert mutation validates
            # every mandatory field on the node -- name, peer_address, peer_asn
            # -- so a payload that omits them to preserve them is rejected
            # outright. Fetching leaves untouched fields exactly as they were.
            session = await self.client.get(kind="ClusterFabricPeering", id=payload.existing_id)
            session.peer_asn.value = payload.data["peer_asn"]  # type: ignore[attr-defined]
            await session.save()
            session_ids.append(session.id)
            self.logger.info(
                "Adopted fabric peering to %s (asn %s)",
                payload.device_name,
                payload.data["peer_asn"],
            )

        await self._link_to_service(parsed, session_ids)

    async def _link_to_service(self, parsed: GenerateFabricPeeringQuery, session_ids: list[str]) -> None:
        """Point the ordering service at the sessions this run produced.

        The transform reads ``service.peerings`` to build the manifest, so a
        session that is not linked here never reaches the cluster no matter how
        correctly it was derived.

        ``update_group_context=False`` is not optional. The service is this
        generator's *target*, not something it owns; letting it join the
        tracking group would make it a deletion candidate on any later run that
        did not touch it.
        """
        service_node = parsed.target.edges[0].node
        service = await self.client.get(kind="ServiceFabricPeering", id=service_node.id)
        service.peerings = session_ids  # type: ignore[attr-defined]
        await service.save(allow_upsert=True, update_group_context=False)
