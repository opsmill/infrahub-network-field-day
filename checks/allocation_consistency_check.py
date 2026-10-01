"""Allocation consistency check.

`generate-network-segment` and `generate-fabric-app` are the two generators that
**allocate rather than select**, and every allocation they make sits beside
numbers and blocks a human typed into `objects/` or the UI. Nothing compared the
two. A requester can name a VLAN id another tenant already renders, a subnet
inside someone else's, or a VIP block outside the pool the leaves accept, and the
model loads, the proposed change merges, and the first symptom is on a switch.

THREE RULES, and each is about a domain the schema's own uniqueness constraints
do not cover.

* **A VLAN id is unique per FABRIC, not per `IpamL2Domain`.** `IpamVLAN` already
  carries the uniqueness constraint `[vlan_id, l2domain]`, so the duplicate the
  schema can see is refused at write time. What it cannot see is the domain AVD
  renders into: the hostvar generator emits every `EvpnTenant` naming a fabric
  into that fabric's `network_services`, and the id it emits is
  `EvpnSvi.svi_id` or `EvpnL2Vlan.vlan_id` -- constrained only per VRF and per
  tenant respectively, and never `IpamVLAN.vlan_id` at all. So three things are
  reported:

  - two network-service VLANs on one fabric with the same id whose tag sets
    intersect, which means at least one switch is asked to carry both;
  - two with the same VNI on one fabric (`vni_override`, else
    `mac_vrf_vni_base + id`), which collides fabric-wide whatever the tags say;
  - an SVI or L2 VLAN whose id disagrees with the `IpamVLAN` it names, because
    that is what makes the IpamVLAN constraint -- and the segment VLAN pool --
    guarantee nothing about what renders.

  Same id with DISJOINT tags in different tenants is legitimate (no switch
  carries both and the VNIs differ) and is not reported.

* **Tenant subnets do not overlap within a VRF.** The candidates are every
  segment's recorded subnet plus every `tenant_host` and `tenant_cloud` prefix.
  A pool's own resources are excluded: `10.230.0.0/16` contains every segment
  subnet by design. Segment subnets carry no `vrf` -- the generator allocates
  them with a role and a description only -- so a prefix's VRF is resolved, in
  order, from the segment recording it, its own `vrf`, and the VRF of the SVI
  whose gateway lies inside it. A prefix whose VRF cannot be resolved is compared
  against every VRF, because nothing proves it separate. One subnet recorded by
  two segments is reported too: withdrawing either would delete the other's.

* **A VIP block sits inside its cluster's `vip_pools` and overlaps no other
  application's.** Those pools are the only supernets the leaves' inbound route
  policy permits (`10.112.240.0/24 le 32`), so a block outside them is
  advertised by the cluster and refused by the fabric -- silently, the
  application deploying and taking a VIP nobody can reach. Two overlapping
  blocks hand the same address to two LoadBalancers.

STATUS IS NOT CONSULTED. A decommissioning segment or application still holds
its allocation until its generator returns it, and a hand-declared block is
never returned; judging only live services would excuse a real collision
because of a label -- the same stance `wan-service-consistency` takes.

GLOBAL, with no `targets`: "two objects claim one number" has no natural group
to iterate, exactly like the other global checks beside it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network, ip_interface, ip_network
from itertools import combinations
from typing import Any

from infrahub_sdk.checks import InfrahubCheck

from .allocation_consistency_check_query import AllocationConsistencyCheckQuery

KIND_SVI = "EvpnSvi"
KIND_L2VLAN = "EvpnL2Vlan"
KIND_PREFIX = "IpamPrefix"
KIND_SEGMENT = "ServiceNetworkSegment"
KIND_APP = "ServiceFabricApp"

# The prefixes a tenant gateway serves. `tenant_host` is what the segment pool
# allocates and what the hand-written K8S/APP subnets carry; `tenant_cloud` is
# the per-WAN-tenant cloud subnets. A hand-named segment subnet can collide with
# either.
TENANT_SUBNET_ROLES = frozenset({"tenant_host", "tenant_cloud"})

Network = IPv4Network | IPv6Network


@dataclass(frozen=True)
class Finding:
    """One violation, with everything needed to attribute it in the UI."""

    message: str
    object_id: str
    object_type: str


def _value(wrapper: Any) -> Any:
    return wrapper.value if wrapper is not None else None


def _node_of(relationship: Any) -> Any:
    return relationship.node if relationship is not None else None


def _edges_of(relationship: Any) -> list[Any]:
    if relationship is None or relationship.edges is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def _network(value: Any) -> Network | None:
    if not value:
        return None
    try:
        return ip_network(str(value), strict=False)
    except ValueError:
        return None


def _overlaps(left: Network, right: Network) -> bool:
    return left.version == right.version and left.overlaps(right)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Rule 1: VLAN ids and VNIs per fabric
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceVlan:
    """One VLAN as AVD renders it: an SVI or a tenant L2 VLAN."""

    object_id: str
    kind: str
    name: str
    vlan_id: int | None
    vni: int | None
    tags: frozenset[str]
    tenant_name: str | None
    fabrics: tuple[tuple[str, str], ...]
    """``(fabric_id, fabric_name)`` for every fabric the tenant is deployed on."""
    scope: str
    """Where it lives, for messages: the VRF for an SVI, the tenant for an L2 VLAN."""
    ipam_vlan: tuple[str, int | None] | None
    """``(name, vlan_id)`` of the IpamVLAN it names, if any."""

    @property
    def label(self) -> str:
        return f"{self.kind} {self.name!r} ({self.scope})"


def _tags(rack_tags: Any, avd_tags: Any) -> frozenset[str]:
    """The rendered tag set: rack names plus AvdTag names, as `_build_svi_tags` emits it."""
    return frozenset(
        name for node in (*_edges_of(rack_tags), *_edges_of(avd_tags)) if (name := _value(node.name)) is not None
    )


def _int(value: Any) -> int | None:
    return None if value is None else int(value)


def _vni(base: int | None, vlan_id: int | None, override: int | None = None) -> int | None:
    if override is not None:
        return override
    if base is None or vlan_id is None:
        # An overlay-free tenant renders no VNI at all.
        return None
    return base + vlan_id


def _ipam_vlan(relationship: Any) -> tuple[str, int | None] | None:
    node = _node_of(relationship)
    if node is None:
        return None
    return (_value(node.name) or node.id, _int(_value(node.vlan_id)))


def service_vlans(parsed: AllocationConsistencyCheckQuery) -> list[ServiceVlan]:
    """Every SVI and L2 VLAN, resolved to its tenant and fabrics."""
    tenant_of_vrf: dict[str, Any] = {}
    vlans: list[ServiceVlan] = []

    for tenant in _edges_of(parsed.evpn_tenant):
        fabrics = tuple(sorted((fabric.id, _value(fabric.name) or fabric.id) for fabric in _edges_of(tenant.fabrics)))
        base = _int(_value(tenant.mac_vrf_vni_base))
        tenant_name = _value(tenant.name) or tenant.id
        for vrf in _edges_of(tenant.vrfs):
            tenant_of_vrf[vrf.id] = (tenant_name, base, fabrics)
        for l2vlan in _edges_of(tenant.l_2_vlans):
            vlan_id = _int(_value(l2vlan.vlan_id))
            vlans.append(
                ServiceVlan(
                    object_id=l2vlan.id,
                    kind=KIND_L2VLAN,
                    name=_value(l2vlan.name) or l2vlan.id,
                    vlan_id=vlan_id,
                    vni=_vni(base, vlan_id, _int(_value(l2vlan.vni_override))),
                    tags=_tags(l2vlan.rack_tags, l2vlan.avd_tags),
                    tenant_name=tenant_name,
                    fabrics=fabrics,
                    scope=f"tenant {tenant_name}",
                    ipam_vlan=_ipam_vlan(l2vlan.vlan),
                )
            )

    for svi in _edges_of(parsed.evpn_svi):
        vrf = _node_of(svi.vrf)
        tenant_name, base, fabrics = tenant_of_vrf.get(vrf.id if vrf is not None else "", (None, None, ()))
        vlan_id = _int(_value(svi.svi_id))
        vrf_name = (_value(vrf.name) or vrf.id) if vrf is not None else "no VRF"
        vlans.append(
            ServiceVlan(
                object_id=svi.id,
                kind=KIND_SVI,
                name=_value(svi.name) or svi.id,
                vlan_id=vlan_id,
                vni=_vni(base, vlan_id),
                tags=_tags(svi.rack_tags, svi.avd_tags),
                tenant_name=tenant_name,
                fabrics=fabrics,
                scope=f"VRF {vrf_name}" + (f", tenant {tenant_name}" if tenant_name else ""),
                ipam_vlan=_ipam_vlan(svi.vlan),
            )
        )

    return sorted(vlans, key=lambda vlan: (vlan.kind, vlan.name, vlan.object_id))


def check_fabric_vlan_ids(parsed: AllocationConsistencyCheckQuery) -> list[Finding]:
    """Rule 1a and 1b: no shared VLAN id on a common switch, no shared VNI on a fabric."""
    findings: list[Finding] = []

    by_fabric: dict[tuple[str, str], list[ServiceVlan]] = defaultdict(list)
    for vlan in service_vlans(parsed):
        for fabric in vlan.fabrics:
            by_fabric[fabric].append(vlan)

    for (_, fabric_name), members in sorted(by_fabric.items(), key=lambda item: item[0][1]):
        for left, right in combinations(members, 2):
            shared_tags = left.tags & right.tags
            if left.vlan_id is not None and left.vlan_id == right.vlan_id and shared_tags:
                findings.append(
                    Finding(
                        message=(
                            f"{left.label} and {right.label} both render VLAN {left.vlan_id} on fabric "
                            f"{fabric_name!r}, and both are tagged {', '.join(sorted(shared_tags))!r} -- so at "
                            "least one switch is asked to carry the same VLAN id twice."
                        ),
                        object_id=right.object_id,
                        object_type=right.kind,
                    )
                )
            elif left.vni is not None and left.vni == right.vni:
                findings.append(
                    Finding(
                        message=(
                            f"{left.label} (VLAN {left.vlan_id}) and {right.label} (VLAN {right.vlan_id}) both "
                            f"render VNI {left.vni} on fabric {fabric_name!r}. A VNI is fabric-wide whatever the "
                            "tags say, so the two would be bridged into one broadcast domain."
                        ),
                        object_id=right.object_id,
                        object_type=right.kind,
                    )
                )

    return findings


def check_vlan_reference(parsed: AllocationConsistencyCheckQuery) -> list[Finding]:
    """Rule 1c: the rendered id agrees with the IpamVLAN it names."""
    findings: list[Finding] = []

    for vlan in service_vlans(parsed):
        if vlan.ipam_vlan is None:
            continue
        ipam_name, ipam_id = vlan.ipam_vlan
        if ipam_id is None or vlan.vlan_id is None or ipam_id == vlan.vlan_id:
            continue
        findings.append(
            Finding(
                message=(
                    f"{vlan.label} renders VLAN {vlan.vlan_id} but names IpamVLAN {ipam_name!r}, which is VLAN "
                    f"{ipam_id}. AVD renders the {vlan.kind}'s own id, so the IpamVLAN's uniqueness and the "
                    "segment VLAN pool guarantee nothing about what reaches the switch."
                ),
                object_id=vlan.object_id,
                object_type=vlan.kind,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Rule 2: tenant subnets per VRF
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TenantSubnet:
    prefix_id: str
    network: Network
    role: str | None
    vrf: tuple[str, str] | None
    """``(vrf_id, vrf_name)``, or None when it cannot be resolved."""
    segments: tuple[str, ...]
    """Names of the segments recording this prefix as their subnet."""

    @property
    def label(self) -> str:
        owner = f", segment {', '.join(repr(name) for name in self.segments)}" if self.segments else ""
        where = f"VRF {self.vrf[1]}" if self.vrf else "VRF unresolved"
        return f"{KIND_PREFIX} {self.network} ({where}{owner})"


def _gateway_vrfs(parsed: AllocationConsistencyCheckQuery) -> list[tuple[Any, tuple[str, str]]]:
    """``(gateway address, (vrf_id, vrf_name))`` for every SVI gateway."""
    gateways: list[tuple[Any, tuple[str, str]]] = []
    for svi in _edges_of(parsed.evpn_svi):
        vrf = _node_of(svi.vrf)
        if vrf is None:
            continue
        addresses = [_value(svi.ip_address_virtual), *(_value(svi.ip_virtual_router_addresses) or [])]
        for address in addresses:
            if not address:
                continue
            try:
                gateways.append((ip_interface(str(address)).ip, (vrf.id, _value(vrf.name) or vrf.id)))
            except ValueError:
                continue
    return gateways


def tenant_subnets(parsed: AllocationConsistencyCheckQuery) -> list[TenantSubnet]:
    """Every subnet a tenant gateway serves, with its VRF resolved where possible."""
    pool_resources = {
        resource.id
        for pool in _edges_of(parsed.core_ip_prefix_pool)
        for resource in _edges_of(pool.resources)
        if resource.id is not None
    }

    segment_vrfs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    segment_names: dict[str, list[str]] = defaultdict(list)
    for segment in _edges_of(parsed.service_network_segment):
        subnet = _node_of(segment.subnet)
        if subnet is None:
            continue
        segment_names[subnet.id].append(_value(segment.name) or segment.id)
        segment_vrf = _node_of(segment.vrf)
        if segment_vrf is not None:
            segment_vrfs[subnet.id].append((segment_vrf.id, _value(segment_vrf.name) or segment_vrf.id))

    gateways = _gateway_vrfs(parsed)
    subnets: list[TenantSubnet] = []

    for prefix in _edges_of(parsed.ipam_prefix):
        role = _value(prefix.role)
        recorded = prefix.id in segment_names
        if not recorded and (role not in TENANT_SUBNET_ROLES or prefix.id in pool_resources):
            continue
        network = _network(_value(prefix.prefix))
        if network is None:
            continue

        vrf: tuple[str, str] | None = None
        if segment_vrfs.get(prefix.id):
            vrf = min(segment_vrfs[prefix.id])
        elif (own := _node_of(prefix.vrf)) is not None:
            vrf = (own.id, _value(own.name) or own.id)
        else:
            served = {
                vrf_ref for address, vrf_ref in gateways if address.version == network.version and address in network
            }
            if len(served) == 1:
                vrf = next(iter(served))

        subnets.append(
            TenantSubnet(
                prefix_id=prefix.id,
                network=network,
                role=role,
                vrf=vrf,
                segments=tuple(sorted(segment_names.get(prefix.id, []))),
            )
        )

    return sorted(subnets, key=lambda subnet: (subnet.network.version, subnet.network, subnet.prefix_id))


def check_segment_subnets(parsed: AllocationConsistencyCheckQuery) -> list[Finding]:
    """Rule 2: no two tenant subnets overlap in one VRF, and no subnet has two segments."""
    findings: list[Finding] = []
    subnets = tenant_subnets(parsed)

    findings.extend(
        Finding(
            message=(
                f"{KIND_PREFIX} {subnet.network} is recorded as the subnet of {len(subnet.segments)} "
                f"segments ({', '.join(repr(name) for name in subnet.segments)}). Withdrawing either would "
                "delete the other's subnet."
            ),
            object_id=subnet.prefix_id,
            object_type=KIND_PREFIX,
        )
        for subnet in subnets
        if len(subnet.segments) > 1
    )

    for left, right in combinations(subnets, 2):
        if not _overlaps(left.network, right.network):
            continue
        if left.vrf is not None and right.vrf is not None and left.vrf[0] != right.vrf[0]:
            continue
        if not (left.segments or right.segments) and left.vrf is None and right.vrf is None:
            # Two hand-written prefixes neither of which can be placed in a VRF:
            # nothing here proves they are even in the same routing domain, and
            # neither was allocated, so this check has nothing to say.
            continue
        findings.append(
            Finding(
                message=(
                    f"{left.label} and {right.label} overlap. Two gateways for one address range in one routing "
                    "domain answer for each other's hosts."
                ),
                object_id=right.prefix_id,
                object_type=KIND_PREFIX,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Rule 3: VIP blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VipBlock:
    app_id: str
    app_name: str
    block_id: str
    network: Network
    cluster_name: str | None
    pools: tuple[Network, ...]


def vip_blocks(parsed: AllocationConsistencyCheckQuery) -> list[VipBlock]:
    blocks: list[VipBlock] = []
    for app in _edges_of(parsed.service_fabric_app):
        block = _node_of(app.vip_block)
        if block is None:
            continue
        network = _network(_value(block.prefix))
        if network is None:
            continue
        cluster = _node_of(app.cluster)
        pools = (
            tuple(pool for node in _edges_of(cluster.vip_pools) if (pool := _network(_value(node.prefix))) is not None)
            if cluster is not None
            else ()
        )
        blocks.append(
            VipBlock(
                app_id=app.id,
                app_name=_value(app.name) or app.id,
                block_id=block.id,
                network=network,
                cluster_name=(_value(cluster.name) or cluster.id) if cluster is not None else None,
                pools=pools,
            )
        )
    return sorted(blocks, key=lambda block: (block.app_name, block.app_id))


def check_vip_blocks(parsed: AllocationConsistencyCheckQuery) -> list[Finding]:
    """Rule 3: every VIP block inside its cluster's pools, and no two overlapping."""
    findings: list[Finding] = []
    blocks = vip_blocks(parsed)

    for block in blocks:
        inside = any(
            block.network.version == pool.version and block.network.subnet_of(pool)  # type: ignore[arg-type]
            for pool in block.pools
        )
        if inside:
            continue
        pools = ", ".join(str(pool) for pool in block.pools) or "none"
        findings.append(
            Finding(
                message=(
                    f"{KIND_APP} {block.app_name!r} holds VIP block {block.network}, which is not inside any VIP "
                    f"pool of cluster {block.cluster_name!r} (pools: {pools}). The leaves accept only those "
                    "supernets, so the cluster would advertise a block the fabric refuses."
                ),
                object_id=block.app_id,
                object_type=KIND_APP,
            )
        )

    for left, right in combinations(blocks, 2):
        if not _overlaps(left.network, right.network):
            continue
        findings.append(
            Finding(
                message=(
                    f"{KIND_APP} {left.app_name!r} (VIP block {left.network}) and {KIND_APP} "
                    f"{right.app_name!r} (VIP block {right.network}) overlap, so two LoadBalancers can be "
                    "handed the same address."
                ),
                object_id=right.app_id,
                object_type=KIND_APP,
            )
        )

    return findings


def collect_findings(parsed: AllocationConsistencyCheckQuery) -> list[Finding]:
    return (
        check_fabric_vlan_ids(parsed)
        + check_vlan_reference(parsed)
        + check_segment_subnets(parsed)
        + check_vip_blocks(parsed)
    )


class AllocationConsistencyCheck(InfrahubCheck):
    """Refuse a proposed change that allocates the same number or range twice."""

    query = "allocation_consistency_check"

    def validate(self, data: dict) -> None:  # type: ignore[override]
        """Emit every finding. Any log_error blocks the merge."""
        parsed = AllocationConsistencyCheckQuery(**data)
        findings = collect_findings(parsed)

        for finding in findings:
            self.log_error(
                message=finding.message,
                object_id=finding.object_id,
                object_type=finding.object_type,
            )

        if not findings:
            # Says what was examined: success over an empty collection is not
            # evidence, as peering_consistency_check documents at length.
            self.log_info(
                message=(
                    f"Allocations are consistent: {len(service_vlans(parsed))} network-service VLAN(s), "
                    f"{len(tenant_subnets(parsed))} tenant subnet(s) and {len(vip_blocks(parsed))} VIP block(s)"
                )
            )
