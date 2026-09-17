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
    peer_address: str | None = None
    """The IpamIPAddress id on the device's peering SVI (cycle 015)."""
    address_error: str | None = None
    """Why the address could not be derived, if it could not. Reported by
    validate_model rather than raised here, so every peer is inspected before
    the first failure is reported."""


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


PEERING_INTERFACE_ROLE = "peering"


def _peering_address(device: Any) -> tuple[str | None, str | None]:
    """The address on the device's peering SVI, or why there isn't one.

    Selected by interface **role**, not by VLAN id, name or position. Every
    real leaf carries a ``Loopback0`` alongside its ``Vlan110``, so a
    positional rule picks the wrong interface; and matching on the VLAN number
    would hardcode this lab's 110 into the generator, so a second cluster on a
    different VLAN would silently get no address.

    Returns:
        ``(address_id, None)`` on success, or ``(None, reason)``.
    """
    svis = [
        interface
        for interface in _edges_of(getattr(device, "interfaces", None))
        if _value(getattr(interface, "role", None)) == PEERING_INTERFACE_ROLE
    ]

    if not svis:
        return None, "has no interface with role 'peering'; the address cannot be derived"
    if len(svis) > 1:
        return None, f"has {len(svis)} interfaces with role 'peering'; the peering address is ambiguous"

    addresses = _edges_of(getattr(svis[0], "ip_addresses", None))
    if not addresses:
        return None, "has a peering interface carrying no address"
    if len(addresses) > 1:
        found = ", ".join(sorted(_value(a.address) or "?" for a in addresses))
        return None, (
            f"has a peering interface carrying several addresses ({found}); which one is the neighbour is ambiguous"
        )

    return addresses[0].id, None


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
                address_id, address_error = _peering_address(device)
                peers[device.id] = DerivedPeer(
                    device_id=device.id,
                    device_name=_value(getattr(device, "name", None)),
                    peer_asn=_value(getattr(asn_node, "asn", None)) if asn_node else None,
                    interface_id=endpoint.id,
                    peer_address=address_id,
                    address_error=address_error,
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


DECOMMISSIONED_STATUSES = frozenset({"decommissioning", "decommissioned"})


def is_withdrawn(service: Any) -> bool:
    """Whether this peering service should hold any sessions at all.

    `decommissioning` counts as gone rather than going: the alternative is a
    window in which the intent is withdrawn and the BGP sessions are still up.
    """
    status = getattr(service, "status", None)
    return status is not None and status.value in DECOMMISSIONED_STATUSES


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

    for peer in peers:
        if peer.peer_asn is None:
            msg = f"peer device {peer.device_name!r} has no asn; peer_asn cannot be derived"
            raise ValueError(msg)

        # V-6', V-8, V-9. Cycle 012 refused here because an address existed
        # only on an existing session, which made creating one impossible.
        # Cycle 014 modelled the leaves' peering SVIs, so the address is now
        # derived from the device -- and only a device that cannot supply one
        # is an error.
        if peer.address_error is not None:
            msg = f"peer device {peer.device_name!r} {peer.address_error}"
            raise ValueError(msg)

    return cluster


def build_session_payloads(cluster: ClusterNode, peers: list[DerivedPeer]) -> list[SessionPayload]:
    """One upsert payload per derived peer.

    Every payload is an adoption carrying ``peer_asn`` and the natural key.
    ``name``, ``enabled`` and ``peer_address`` are preserved by being left out,
    because ``save(allow_upsert=True)`` writes whatever it is given.

    Two shapes, because cycle 015 made the create path reachable again.

    An **adoption** names only the derived fields -- ``peer_asn`` and
    ``peer_address``. It is applied by fetching the existing node and setting
    those attributes, NOT by an upsert: an upsert validates every mandatory
    field, so "omit a field to preserve it" is not expressible that way.
    Fetch-and-modify preserves ``name`` and ``enabled`` by never touching them.

    A **create** carries the full set. Cycle 012 had no create shape and said
    so, correctly at the time: ``peer_address`` was recorded only on an
    existing session, so a peer without one had no address the generator was
    permitted to supply. Cycle 014 modelled the leaves' peering SVIs, so a
    cabled leaf now carries everything a session needs.
    """
    existing = _existing_by_device(cluster)
    payloads: list[SessionPayload] = []

    for peer in peers:
        session = existing.get(peer.device_id)
        if session is not None:
            payloads.append(
                SessionPayload(
                    device_name=peer.device_name,
                    is_adoption=True,
                    data={"peer_asn": peer.peer_asn, "peer_address": peer.peer_address},
                    existing_id=session.id,
                )
            )
            continue

        payloads.append(
            SessionPayload(
                device_name=peer.device_name,
                is_adoption=False,
                data={
                    "cluster": cluster.id,
                    "peer_device": peer.device_id,
                    "peer_asn": peer.peer_asn,
                    "peer_address": peer.peer_address,
                    # Not derivable -- a lab-facing label, per cycle 012's Q1.
                    # A genuinely new peer takes its device's name.
                    "name": peer.device_name,
                    "enabled": True,
                },
            )
        )

    return payloads


class FabricPeeringGenerator(InfrahubGenerator):
    """Derive a cluster's fabric BGP sessions from its cabling."""

    async def generate(self, data: dict) -> None:
        """Upsert one ClusterFabricPeering per cabled fabric device."""
        parsed = GenerateFabricPeeringQuery(**data)

        # Before anything else, as every other service generator here does.
        # Until cycle 037 this one ignored `status` entirely, so a peering
        # service marked decommissioned kept every session it had derived: the
        # service said gone and the fabric said up, and nothing reported it.
        service = parsed.target.edges[0].node if parsed.target.edges else None
        if service is not None and is_withdrawn(service):
            await self._withdraw(parsed, service)
            return

        cluster = validate_model(parsed)
        peers = derive_peers(cluster)
        payloads = build_session_payloads(cluster, peers)

        # R4: a derived value can now disagree with one that has been live.
        # Silently overwriting is defensible for peer_asn -- the fabric is
        # authoritative -- but an address change moves where BGP points, and an
        # operator should see that in the run output rather than in a later diff.
        existing = _existing_by_device(cluster)
        for peer in peers:
            session = existing.get(peer.device_id)
            if session is None:
                continue
            recorded = _node_of(session.peer_address)
            if recorded is not None and peer.peer_address and recorded.id != peer.peer_address:
                self.logger.warning(
                    "peer_address drift on %s: recorded %s, derived from the peering SVI; correcting",
                    peer.device_name,
                    _value(recorded.address),
                )

        session_ids: list[str] = []
        for payload in payloads:
            # Fetch and modify rather than upsert. An upsert mutation validates
            # every mandatory field on the node -- name, peer_address, peer_asn
            # -- so a payload that omits them to preserve them is rejected
            # outright. Fetching leaves untouched fields exactly as they were.
            if payload.is_adoption:
                session = await self.client.get(kind="ClusterFabricPeering", id=payload.existing_id)
                session.peer_asn.value = payload.data["peer_asn"]  # type: ignore[attr-defined]
                session.peer_address = payload.data["peer_address"]  # type: ignore[attr-defined]
                await session.save()
            else:
                session = await self.client.create(kind="ClusterFabricPeering", data=payload.data)
                await session.save(allow_upsert=True)
            session_ids.append(session.id)
            self.logger.info(
                "%s fabric peering to %s (asn %s)",
                "Adopted" if payload.is_adoption else "Created",
                payload.device_name,
                payload.data["peer_asn"],
            )

        await self._link_to_service(parsed, session_ids)

    async def _withdraw(self, parsed: GenerateFabricPeeringQuery, service: Any) -> None:
        """Remove the sessions an earlier run derived for this service.

        THE TRACKING CONTEXT DOES NOT COVER THIS. `update_group` opens with
        ``if not members: return``, so a run that writes nothing prunes nothing
        -- which is precisely a withdrawal. Tracking handles a *narrowing*, where
        the run still writes some sessions and the dropped ones fall out of a
        non-empty member set; it does not handle a service going away.

        Only sessions the service RECORDS are deleted. A `ClusterFabricPeering`
        that exists for some other reason is not this generator's to remove, and
        the same rule is what keeps adoption safe on the building path.
        """
        name = _value(service.name)

        # Read from the SERVICE, not from the parsed query. The query selects
        # `cluster.fabric_peerings` -- every session on the cluster, whoever made
        # it -- while `service.peerings` is what this service recorded, which is
        # the only set this generator may delete. Fetched through the client for
        # the same reason `_link_to_service` does: the relationship is not in
        # the query at all.
        live = await self.client.get(kind="ServiceFabricPeering", id=service.id)
        peerings = live.peerings  # type: ignore[attr-defined]
        await peerings.fetch()
        session_ids = list(peerings.peer_ids)

        if not session_ids:
            self.logger.info("Peering service %r is decommissioned; nothing to withdraw", name)
            return

        # The link goes first. Deleting a session the service still points at
        # leaves a dangling reference for as long as the second write takes, and
        # a failure in between would leave one permanently.
        await self._link_to_service(parsed, [])
        for session_id in session_ids:
            await self.client.delete(kind="ClusterFabricPeering", id=session_id)

        self.logger.info("Peering service %r is decommissioned; withdrew %s session(s)", name, len(session_ids))

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

        # A RelationshipManager is not a list: it must be fetched before its
        # members can be edited, and it is edited through add/remove rather
        # than assignment.
        peerings = service.peerings  # type: ignore[attr-defined]
        await peerings.fetch()

        current = set(peerings.peer_ids)
        wanted = set(session_ids)
        for missing in sorted(wanted - current):
            peerings.add(missing)
        for stale in sorted(current - wanted):
            peerings.remove(stale)

        if wanted != current:
            await service.save(update_group_context=False)
            self.logger.info("Linked %s session(s) to the service", len(wanted))
