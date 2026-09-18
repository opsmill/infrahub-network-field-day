"""Turn a requested network segment into the three objects it actually is.

`ServiceNetworkSegment` is the first service kind in this repository that
**allocates rather than selects**. `ServiceL3vpn` and its WAN siblings name
technical objects that already exist, so a generator beneath them would have
nothing to create. A segment states a size, a tenant and a routing domain, and
this generator takes the next free subnet and the next free VLAN id and builds
the `IpamPrefix`, `IpamVLAN` and `EvpnSvi` that a tenant network is made of --
the same three objects `objects/24_otternet_tenants.yml` and
`objects/27_otternet_vrf_services.yml` write out by hand, four times each.

FIVE THINGS THAT LOOK ARBITRARY AND ARE NOT.

* **`avd_tags` is mandatory and a rack is not a substitute.** AVD renders an SVI
  onto a device only where `svis[].tags` intersects that device's node-group
  filter, and in this fabric those filters are AvdTags: `{"tags": ["k8s"]}` on
  K8S_LEAFS. `EvpnSvi.rack_tags` exists, looks like the scoping mechanism, and
  contributes the rack's NAME -- `K8S_LEAFS` -- which matches no filter.
  Measured on a branch: an untagged SVI rendered on zero switches; tagged `k8s`
  the same SVI appeared on exactly the two K8S leaves. An empty tag list is
  therefore not "the whole fabric", it is nowhere, with a rendered
  configuration that simply lacks the interface and no error anywhere.

* **The pools are resolved by ROLE, not by name.** A default of
  `"OTTERNET-Segment-Subnet-Pool"` would make this generator specific to one
  lab's object files and would fail with a message naming a string that appears
  in no schema. `SEGMENT_PREFIX_ROLE` and the `IpamVLAN.vlan_id` pairing are
  statements about the model instead: the pool that allocates tenant host
  subnets, and the pool that allocates VLAN ids. Both demand exactly one
  candidate, because an ambiguity is not something to guess at.

* **The VLAN and the SVI take the segment's own name, and a collision raises.**
  A segment IS its VLAN, so a prefix would make every generated segment read
  differently from the four hand-written ones beside it. The cost is that a
  request named `K8S_NODES` would upsert onto an existing object -- and then
  delete it on decommissioning. So an object carrying our name that the service
  does not already record is refused, and adopting one is an explicit act:
  point the service's `vlan` or `svi` at it first.

* **Allocation is keyed on the service's ID, never its name.** The identifier is
  what makes `allocate_next_ip_prefix` idempotent; keyed on a name, a rename
  would allocate a second subnet and orphan the first. Keyed on the id, a
  renamed segment keeps its addressing and a deleted-then-recreated one
  correctly gets new addressing.

* **Nothing here reaches a switch on its own.** The writes land in the graph,
  and `generate-avd-device-hostvar` is registered `execute_after_merge: false`
  because the AVD chain is expensive and is run explicitly. The model is
  correct immediately; the switch follows on the next `invoke avd`, exactly as
  it does for any other fabric change.
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_network
from typing import Any

from infrahub_sdk.generator import InfrahubGenerator

from .generate_network_segment_query import (
    GenerateNetworkSegmentQuery,
    GenerateNetworkSegmentQueryTargetEdgesNode,
)

SegmentNode = GenerateNetworkSegmentQueryTargetEdgesNode

# The role a prefix carries when it is tenant host addressing. Declared on the
# supernet in objects/21_otternet_pools.yml and on every subnet allocated from it,
# which is what lets the subnet pool be found without naming it.
SEGMENT_PREFIX_ROLE = "tenant_host"

# What identifies the VLAN pool: a CoreNumberPool allocating this attribute on
# this kind IS the VLAN pool, whatever it happens to be called.
VLAN_POOL_NODE = "IpamVLAN"
VLAN_POOL_ATTRIBUTE = "vlan_id"

# The two statuses that mean "take it away". Everything else builds -- including
# `error`, so a failed run that is corrected rebuilds rather than needing its
# status reset by hand.
WITHDRAWN_STATUSES = frozenset({"decommissioning", "decommissioned"})

# IpamVLAN.status is mandatory; `role` is how the lab's own VLANs are marked.
VLAN_STATUS = "active"
VLAN_ROLE = "server"


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


def _only(candidates: list[Any], *, what: str, remedy: str) -> Any:
    """The single candidate, or a refusal naming both failure directions.

    Zero and several are the same class of problem -- the generator cannot tell
    which object the request meant -- and both are reported with the way out,
    because a message that says only "ambiguous" sends the reader to the wrong
    file.
    """
    if len(candidates) == 1:
        return candidates[0]
    found = "none" if not candidates else f"{len(candidates)}"
    msg = f"expected exactly one {what}, found {found}; {remedy}"
    raise ValueError(msg)


def resolve_subnet_pool(parsed: GenerateNetworkSegmentQuery, segment: SegmentNode) -> str:
    """The pool a segment's subnet comes from.

    A named pool wins outright. Otherwise the pool whose resources carry
    `tenant_host` is the segment pool by definition, which is a statement about
    what the pool is for rather than about what it was called.
    """
    named = _node_of(segment.subnet_pool)
    if named is not None:
        return named.id

    candidates = [
        node.id
        for node in _edges_of(parsed.core_ip_prefix_pool)
        if any(_value(getattr(resource, "role", None)) == SEGMENT_PREFIX_ROLE for resource in _edges_of(node.resources))
    ]
    return _only(
        candidates,
        what=f"CoreIPPrefixPool whose resources carry role {SEGMENT_PREFIX_ROLE!r}",
        remedy="name one on the segment's `subnet_pool`",
    )


def resolve_vlan_pool(parsed: GenerateNetworkSegmentQuery, segment: SegmentNode) -> str:
    """The pool a segment's VLAN id comes from."""
    named = _node_of(segment.vlan_pool)
    if named is not None:
        return named.id

    candidates = [
        node.id
        for node in _edges_of(parsed.core_number_pool)
        if _value(node.node) == VLAN_POOL_NODE and _value(node.node_attribute) == VLAN_POOL_ATTRIBUTE
    ]
    return _only(
        candidates,
        what=f"CoreNumberPool allocating {VLAN_POOL_NODE}.{VLAN_POOL_ATTRIBUTE}",
        remedy="name one on the segment's `vlan_pool`",
    )


def resolve_l2domain(parsed: GenerateNetworkSegmentQuery) -> str:
    """The layer-two domain the VLAN belongs to.

    `IpamVLAN.l2domain` is mandatory and the request does not name one, because
    a requester asking for a network has no opinion about which L2 domain it
    lands in. One domain exists in this fabric; several would need the request
    to say, and this raises rather than picking.
    """
    return _only(
        [node.id for node in _edges_of(parsed.ipam_l_2_domain)],
        what="IpamL2Domain",
        remedy="the segment schema would need an `l2domain` relationship to disambiguate",
    )


def adopted_id(existing: list[Any], recorded_id: str | None) -> str | None:
    """The id of an object this service already owns, refusing a collision.

    ``existing`` is everything carrying the name this generator would write.
    Nothing there is the normal first run. Something there that the service
    already records is this generator's own output from an earlier run, and is
    written again -- that is what keeps it inside the tracking group, the
    mistake that made `generate-app-access` delete the objects its own rule
    pointed at.

    Something there that the service does NOT record is a hand-written object
    wearing the requested name. Upserting onto it would work, right up until the
    segment was decommissioned and took a lab VLAN with it.
    """
    if not existing:
        return None
    ids = {node.id for node in existing}
    if recorded_id in ids:
        return recorded_id
    msg = (
        "an object already carries this segment's name and the service does not record it; "
        "rename the segment, or point the service at the existing object first to adopt it"
    )
    raise ValueError(msg)


def gateway_address(prefix: str) -> str:
    """The first usable address of a subnet, in host notation.

    `10.230.0.0/24` becomes `10.230.0.1/24`, which is what every hand-written
    segment in this lab uses and what `EvpnSvi.ip_address_virtual` expects.
    """
    network = ip_network(prefix, strict=False)
    return f"{next(network.hosts())}/{network.prefixlen}"


@dataclass(frozen=True)
class SegmentContext:
    """Everything a validated request needs, resolved before the first write."""

    segment: SegmentNode
    name: str
    description: str | None
    vrf_id: str
    tenant_name: str | None
    avd_tag_ids: list[str]
    prefix_length: int
    subnet_pool_id: str
    vlan_pool_id: str
    l2domain_id: str
    requested_vlan_id: int | None
    """A VLAN id the requester named. Empty is the normal case."""
    recorded_subnet_id: str | None
    recorded_subnet_prefix: str | None
    recorded_vlan_id: str | None
    recorded_vlan_number: int | None
    recorded_svi_id: str | None
    existing_vlans: list[Any]
    existing_svis: list[Any]


def validate_model(parsed: GenerateNetworkSegmentQuery) -> SegmentContext:
    """Resolve and check everything before anything is written.

    Every failure here leaves the graph untouched, which is the point of doing
    it in one place: a half-built segment -- a subnet with no VLAN, or a VLAN
    with no gateway -- is worse than no segment at all, because it consumes an
    allocation nothing points at.
    """
    segment = parsed.target.edges[0].node if parsed.target.edges else None
    if segment is None:
        msg = "no ServiceNetworkSegment matched the requested name"
        raise ValueError(msg)

    name = _value(segment.name)
    if not name:
        msg = "the segment has no name, so its VLAN and SVI cannot be named"
        raise ValueError(msg)

    vrf = _node_of(segment.vrf)
    if vrf is None:
        msg = f"segment {name!r} names no VRF; the gateway has no routing domain to live in"
        raise ValueError(msg)

    # Mandatory in the schema, checked again here because a schema loaded
    # before the mandatory-ness was added leaves older objects without it --
    # and the failure that follows is a segment rendering onto nothing.
    avd_tag_ids = [node.id for node in _edges_of(segment.avd_tags)]
    if not avd_tag_ids:
        msg = (
            f"segment {name!r} names no AVD tags, so its SVI would match no node-group filter "
            "and render on no switch at all"
        )
        raise ValueError(msg)

    prefix_length = _value(segment.prefix_length)
    if prefix_length is None:
        msg = f"segment {name!r} states no prefix length, so nothing can be allocated for it"
        raise ValueError(msg)

    recorded_subnet = _node_of(segment.subnet)
    recorded_vlan = _node_of(segment.vlan)
    recorded_svi = _node_of(segment.svi)

    return SegmentContext(
        segment=segment,
        name=name,
        description=_value(segment.description),
        vrf_id=vrf.id,
        tenant_name=_value(getattr(_node_of(segment.tenant), "name", None)),
        avd_tag_ids=avd_tag_ids,
        prefix_length=int(prefix_length),
        subnet_pool_id=resolve_subnet_pool(parsed, segment),
        vlan_pool_id=resolve_vlan_pool(parsed, segment),
        l2domain_id=resolve_l2domain(parsed),
        requested_vlan_id=(None if _value(segment.vlan_id) is None else int(_value(segment.vlan_id))),
        recorded_subnet_id=None if recorded_subnet is None else recorded_subnet.id,
        recorded_subnet_prefix=None if recorded_subnet is None else _value(recorded_subnet.prefix),
        recorded_vlan_id=None if recorded_vlan is None else recorded_vlan.id,
        recorded_vlan_number=(
            None
            if recorded_vlan is None or _value(recorded_vlan.vlan_id) is None
            else int(_value(recorded_vlan.vlan_id))
        ),
        recorded_svi_id=None if recorded_svi is None else recorded_svi.id,
        existing_vlans=_edges_of(parsed.existing_vlan),
        existing_svis=_edges_of(parsed.existing_svi),
    )


def is_withdrawn(segment: SegmentNode) -> bool:
    return _value(segment.status) in WITHDRAWN_STATUSES


class NetworkSegmentGenerator(InfrahubGenerator):
    """Materialize a requested segment as a subnet, a VLAN and a gateway."""

    async def generate(self, data: dict) -> None:
        """Build what the request asks for, or take it away."""
        parsed = GenerateNetworkSegmentQuery(**data)

        segment = parsed.target.edges[0].node if parsed.target.edges else None
        if segment is None:
            msg = "no ServiceNetworkSegment matched the requested name"
            raise ValueError(msg)

        # Before anything else, exactly as `generate-app-access` checks
        # `approved`: a decommissioned segment materializes nothing and removes
        # whatever an earlier run left behind.
        if is_withdrawn(segment):
            await self._withdraw(segment)
            return

        try:
            context = validate_model(parsed)
        except ValueError:
            await self._set_status(segment.id, "error")
            raise

        subnet_id, subnet_prefix = await self._allocate_subnet(context)
        vlan_id, vlan_number = await self._upsert_vlan(context, subnet_id)
        svi_id = await self._upsert_svi(context, vlan_id, vlan_number, subnet_prefix)

        await self._record(context, subnet_id=subnet_id, vlan_id=vlan_id, svi_id=svi_id)
        await self._set_status(segment.id, "active")

        self.logger.info(
            "Segment %r is %s on VLAN %s in %s; run `invoke avd` to reach the switches",
            context.name,
            subnet_prefix,
            vlan_number,
            context.tenant_name or "its tenant",
        )

    async def _allocate_subnet(self, context: SegmentContext) -> tuple[str, str]:
        """Take the next free subnet, or return the one already taken.

        KEYED ON THE SERVICE'S ID. The identifier is what makes the allocation
        idempotent -- Infrahub returns the same prefix for the same identifier
        -- so a re-run reuses the subnet rather than consuming a second one.
        Keying it on the name instead would mean a rename silently allocated a
        new subnet and orphaned the old.
        """
        if context.recorded_subnet_id is not None and context.recorded_subnet_prefix is not None:
            recorded = ip_network(context.recorded_subnet_prefix, strict=False)
            if recorded.prefixlen != context.prefix_length:
                # An honest report rather than a silent resize. Infrahub keys
                # the allocation on the identifier, so the pool returns the
                # subnet it already handed out whatever length is asked for now.
                self.logger.warning(
                    "Segment %r asks for a /%s and already holds %s; an allocated subnet is not "
                    "resized. Decommission and re-request it to change the size",
                    context.name,
                    context.prefix_length,
                    context.recorded_subnet_prefix,
                )
            return context.recorded_subnet_id, context.recorded_subnet_prefix

        pool = await self.client.get(kind="CoreIPPrefixPool", id=context.subnet_pool_id)
        prefix = await self.client.allocate_next_ip_prefix(
            resource_pool=pool,
            identifier=f"segment-{context.segment.id}",
            member_type="prefix",
            prefix_length=context.prefix_length,
            # Without a role the allocated subnet is indistinguishable from
            # fabric infrastructure addressing, and `resolve_subnet_pool` finds
            # the pool by exactly this value.
            data={"role": SEGMENT_PREFIX_ROLE, "description": f"{context.name} segment subnet"},
        )
        value = str(prefix.prefix.value)  # type: ignore[union-attr]
        self.logger.info("Allocated %s for segment %r", value, context.name)
        return prefix.id, value

    async def _upsert_vlan(self, context: SegmentContext, subnet_id: str) -> tuple[str, int]:
        """The VLAN, with an id that is named, remembered, or allocated.

        Three sources in falling order of authority: a requester who named an
        id gets it, a segment already built keeps the id it has, and everything
        else takes the next free one from the pool. `from_pool` is used ONLY on
        the third path -- passing it on a re-run would ask the pool for a second
        number for a VLAN that already has one.
        """
        adopted = adopted_id(context.existing_vlans, context.recorded_vlan_id)

        data: dict[str, Any] = {
            "name": context.name,
            "description": context.description or f"{context.name} segment",
            "status": VLAN_STATUS,
            "role": VLAN_ROLE,
            "l2domain": context.l2domain_id,
            "prefixes": [subnet_id],
        }

        number = context.requested_vlan_id or context.recorded_vlan_number
        if number is not None:
            data["vlan_id"] = number
        else:
            data["vlan_id"] = {"from_pool": {"id": context.vlan_pool_id}}

        if adopted is not None:
            data["id"] = adopted

        vlan = await self.client.create(kind="IpamVLAN", data=data)
        await vlan.save(allow_upsert=True)

        # Read back rather than assumed: on the allocating path the number is
        # chosen by the pool and is not in `data` at all.
        allocated = int(vlan.vlan_id.value)  # type: ignore[union-attr]
        self.logger.info("Segment %r holds VLAN %s", context.name, allocated)
        return vlan.id, allocated

    async def _upsert_svi(
        self,
        context: SegmentContext,
        vlan_id: str,
        vlan_number: int,
        subnet_prefix: str,
    ) -> str:
        """The gateway.

        `svi_id` equals the VLAN id, which is both the convention every
        hand-written SVI here follows and what `EvpnSvi`'s
        `[vrf, svi_id]` uniqueness constraint makes load-bearing: two segments
        in one VRF cannot share a VLAN id, and the constraint says so rather
        than leaving it to this generator to remember.

        `ip_address_virtual` rather than `ip_virtual_router_addresses`: the
        anycast gateway needs nothing else, while VARP is only correct
        alongside per-node addresses, which a segment does not create. An SVI
        given VARP and no node addresses has no address of its own at all.
        """
        adopted = adopted_id(context.existing_svis, context.recorded_svi_id)

        data: dict[str, Any] = {
            "name": context.name,
            "svi_id": vlan_number,
            "description": context.description or f"{context.name} gateway",
            "enabled": True,
            "vrf": context.vrf_id,
            "vlan": vlan_id,
            "ip_address_virtual": gateway_address(subnet_prefix),
            # THE FIELD THAT DECIDES WHETHER ANY OF THIS RENDERS. See the module
            # docstring: no intersection with a node-group filter means no
            # interface on any switch, silently.
            "avd_tags": context.avd_tag_ids,
        }
        if adopted is not None:
            data["id"] = adopted

        svi = await self.client.create(kind="EvpnSvi", data=data)
        await svi.save(allow_upsert=True)
        self.logger.info("Segment %r has a gateway at %s", context.name, gateway_address(subnet_prefix))
        return svi.id

    async def _record(self, context: SegmentContext, *, subnet_id: str, vlan_id: str, svi_id: str) -> None:
        """Point the service at what this run produced.

        ``update_group_context=False`` is not optional. The segment is this
        generator's *target*, not something it owns; letting it join the
        tracking group would make it a deletion candidate on any later run that
        did not touch it.
        """
        service = await self.client.get(kind="ServiceNetworkSegment", id=context.segment.id)
        service.subnet = subnet_id  # type: ignore[attr-defined]
        service.vlan = vlan_id  # type: ignore[attr-defined]
        service.svi = svi_id  # type: ignore[attr-defined]
        await service.save(update_group_context=False)

    async def _withdraw(self, segment: SegmentNode) -> None:
        """Remove what an earlier run built, and release what it allocated.

        THE TRACKING CONTEXT DOES NOT COVER THIS, and assuming it did was a real
        bug in `generate-app-access`. `InfrahubGroupContext.update_group` opens
        with ``if not members: return``, so a run that writes nothing prunes
        nothing -- a decommissioned segment would keep its subnet, its VLAN and
        its gateway while reporting success.

        DELETION FOLLOWS REFERENCES, so the order is fixed: the SVI points at
        the VLAN and the VLAN at the prefix. Deleting the prefix last is also
        what returns the subnet to its pool, so a decommissioned segment stops
        consuming addressing rather than merely stopping being visible.

        Only what the SERVICE RECORDS is deleted. An object that merely shares
        the name was refused at build time and is not this generator's to
        remove.
        """
        name = _value(segment.name)
        removed = 0

        for kind, related in (
            ("EvpnSvi", _node_of(segment.svi)),
            ("IpamVLAN", _node_of(segment.vlan)),
            ("IpamPrefix", _node_of(segment.subnet)),
        ):
            if related is None:
                continue
            await self.client.delete(kind=kind, id=related.id)
            removed += 1

        if not removed:
            self.logger.info("Segment %r is decommissioned; nothing to withdraw", name)
            await self._set_status(segment.id, "decommissioned")
            return

        service = await self.client.get(kind="ServiceNetworkSegment", id=segment.id)
        service.subnet = None  # type: ignore[attr-defined]
        service.vlan = None  # type: ignore[attr-defined]
        service.svi = None  # type: ignore[attr-defined]
        await service.save(update_group_context=False)

        await self._set_status(segment.id, "decommissioned")
        self.logger.info(
            "Withdrew %s object(s) for segment %r and released its subnet; "
            "run `invoke avd` to remove the interface from the switches",
            removed,
            name,
        )

    async def _set_status(self, segment_id: str, status: str) -> None:
        """Record the outcome on the service.

        ``error`` is distinct from ``provisioning`` on purpose: both leave no
        technical objects behind, and "tried to build and failed" is otherwise
        indistinguishable from "not built yet".
        """
        service = await self.client.get(kind="ServiceNetworkSegment", id=segment_id)
        if _value(service.status) == status:  # type: ignore[attr-defined]
            return
        service.status.value = status  # type: ignore[union-attr]
        await service.save(update_group_context=False)
        self.logger.info("Segment status set to %s", status)
