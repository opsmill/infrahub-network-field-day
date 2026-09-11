"""Peering consistency check.

Cycles 010 through 015 built a model whose whole purpose is to stop the two ends
of a BGP session drifting apart, and each measured itself against the same
artifact checksum. None of them refuses a merge. The generator corrects drift
when it runs; nothing stops someone editing a session by hand, opening a
proposed change, and merging it.

This is the gate. Six rules, every one of them a comparison within the graph.

**What it deliberately does not check.** The most valuable rule for this project
would be "does the cluster's view agree with what AVD renders onto the leaf?"
That is not implementable here: ``RoutingBGPNeighbor``,
``AvdStructuredConfigFile``, ``AvdHostvarFile`` and ``AvdArtifact`` all hold
zero objects on every branch, because the AVD generator chain has never run on
this instance. A check written against them would iterate an empty collection
and report success -- a vacuous pass, which is worse than no check because it
manufactures confidence. Running the AVD chain is the precondition, and that
rule is then a cycle of its own.

Overlap with the generator is deliberate rather than redundant: the generator
asserts the derived values *when it runs*, and object data can set them at any
time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrahub_sdk.checks import InfrahubCheck

from .peering_consistency_check_query import PeeringConsistencyCheckQuery

# Roles a cluster node may legitimately be cabled to, matching the generator's
# own filter so the check and the generator cannot disagree about what a fabric
# peer is.
FABRIC_ROLES = frozenset({"leaf", "border_leaf", "l2leaf"})
PEERING_INTERFACE_ROLE = "peering"

# Kind names used for error attribution. The query selects `__typename`, but the
# code generator drops it on concrete nodes -- it only emits a discriminator
# where a union needs one -- so the kind is named here rather than read back.
KIND_SESSION = "ClusterFabricPeering"
KIND_SERVICE = "ServiceFabricPeering"
KIND_SVI_NODE = "EvpnSviNode"


@dataclass(frozen=True)
class Finding:
    """One violation, with everything needed to attribute it in the UI."""

    message: str
    object_id: str
    object_type: str
    is_error: bool = True
    """False for advisory findings. The SDK has no log_warning, so this is the
    difference between blocking a merge and leaving a note."""


def _value(wrapper: Any) -> Any:
    return wrapper.value if wrapper is not None else None


def _node_of(relationship: Any) -> Any:
    return relationship.node if relationship is not None else None


def _edges_of(relationship: Any) -> list[Any]:
    if relationship is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def _svis_by_device(parsed: PeeringConsistencyCheckQuery) -> dict[str, list[Any]]:
    """Every virtual interface, indexed by the device it belongs to."""
    index: dict[str, list[Any]] = {}
    for svi in _edges_of(parsed.interface_virtual):
        device = _node_of(svi.device)
        if device is not None:
            index.setdefault(device.id, []).append(svi)
    return index


def _peering_address(svis: list[Any]) -> str | None:
    """The address on the device's peering SVI, or None if not exactly one."""
    candidates = [svi for svi in svis if _value(svi.role) == PEERING_INTERFACE_ROLE]
    if len(candidates) != 1:
        return None
    addresses = _edges_of(candidates[0].ip_addresses)
    if len(addresses) != 1:
        return None
    return _value(addresses[0].address)


def check_asn_matches_device(parsed: PeeringConsistencyCheckQuery) -> list[Finding]:
    """C-1. The peer device's RoutingAsn is authoritative."""
    findings: list[Finding] = []
    for session in _edges_of(parsed.cluster_fabric_peering):
        device = _node_of(session.peer_device)
        if device is None:
            continue
        asn_node = _node_of(getattr(device, "asn", None))
        authoritative = _value(getattr(asn_node, "asn", None)) if asn_node else None
        recorded = _value(session.peer_asn)
        if authoritative is not None and recorded != authoritative:
            findings.append(
                Finding(
                    message=(
                        f"session {_value(session.name)!r} records peer_asn {recorded} but its peer device "
                        f"{device.display_label} has RoutingAsn {authoritative}; the device is authoritative"
                    ),
                    object_id=session.id,
                    object_type=KIND_SESSION,
                )
            )
    return findings


def check_address_matches_svi(parsed: PeeringConsistencyCheckQuery) -> list[Finding]:
    """C-2. The address must be the one on the peer device's peering SVI."""
    findings: list[Finding] = []
    svis = _svis_by_device(parsed)
    for session in _edges_of(parsed.cluster_fabric_peering):
        device = _node_of(session.peer_device)
        if device is None:
            continue
        expected = _peering_address(svis.get(device.id, []))
        recorded_node = _node_of(session.peer_address)
        recorded = _value(getattr(recorded_node, "address", None)) if recorded_node else None
        if expected is not None and recorded != expected:
            findings.append(
                Finding(
                    message=(
                        f"session {_value(session.name)!r} records peer_address {recorded} but the peering SVI on "
                        f"{device.display_label} carries {expected}"
                    ),
                    object_id=session.id,
                    object_type=KIND_SESSION,
                )
            )
    return findings


def check_one_service_per_cluster(parsed: PeeringConsistencyCheckQuery) -> list[Finding]:
    """C-3. Two services claiming one cluster would fight over the same
    objects on every generator run."""
    by_cluster: dict[str, list[Any]] = {}
    for service in _edges_of(parsed.service_fabric_peering):
        cluster = _node_of(service.cluster)
        if cluster is not None:
            by_cluster.setdefault(cluster.id, []).append(service)

    findings: list[Finding] = []
    for services in by_cluster.values():
        if len(services) < 2:
            continue
        names = ", ".join(sorted(str(_value(s.name)) for s in services))
        findings.extend(
            Finding(
                message=(
                    f"cluster {_value(_node_of(service.cluster).name)!r} is claimed by "
                    f"{len(services)} peering services ({names}); each generator run would fight over "
                    "the same sessions"
                ),
                object_id=service.id,
                object_type=KIND_SERVICE,
            )
            for service in services
        )
    return findings


def _cabled_devices_by_cluster(parsed: PeeringConsistencyCheckQuery) -> dict[str, set[str]]:
    """The devices each cluster's nodes are cabled to, excluding the near end."""
    index: dict[str, set[str]] = {}
    for cluster in _edges_of(parsed.cluster_kubernetes):
        reachable: set[str] = set()
        for node in _edges_of(cluster.nodes):
            for interface in _edges_of(getattr(node, "interfaces", None)):
                link = _node_of(getattr(interface, "connector", None))
                if link is None:
                    continue
                for endpoint in _edges_of(getattr(link, "connected_endpoints", None)):
                    if endpoint.id == interface.id:
                        continue
                    device = _node_of(getattr(endpoint, "device", None))
                    if device is not None:
                        reachable.add(device.id)
        index[cluster.id] = reachable
    return index


def check_peer_is_cabled(parsed: PeeringConsistencyCheckQuery) -> list[Finding]:
    """C-4. A session to a device the cluster cannot reach is not a session."""
    findings: list[Finding] = []
    cabled = _cabled_devices_by_cluster(parsed)
    for session in _edges_of(parsed.cluster_fabric_peering):
        cluster = _node_of(session.cluster)
        device = _node_of(session.peer_device)
        if cluster is None or device is None:
            continue
        reachable = cabled.get(cluster.id)
        if reachable is None or device.id in reachable:
            continue
        findings.append(
            Finding(
                message=(
                    f"session {_value(session.name)!r} peers with {device.display_label}, which none of cluster "
                    f"{_value(cluster.name)!r}'s nodes are cabled to"
                ),
                object_id=session.id,
                object_type=KIND_SESSION,
            )
        )
    return findings


def check_peer_role(parsed: PeeringConsistencyCheckQuery) -> list[Finding]:
    """C-5. The peer must be a fabric leaf, not an out-of-band switch."""
    findings: list[Finding] = []
    for session in _edges_of(parsed.cluster_fabric_peering):
        device = _node_of(session.peer_device)
        if device is None:
            continue
        role = _value(getattr(device, "role", None))
        if role is None or role in FABRIC_ROLES:
            continue
        findings.append(
            Finding(
                message=(
                    f"session {_value(session.name)!r} peers with {device.display_label}, whose role is {role!r} "
                    f"and not one of {sorted(FABRIC_ROLES)}"
                ),
                object_id=session.id,
                object_type=KIND_SESSION,
            )
        )
    return findings


def check_svi_node_agreement(parsed: PeeringConsistencyCheckQuery) -> list[Finding]:
    """C-6 and C-7. The fabric's second record of the same address.

    Cycle 014 modelled the peering SVIs and flagged that `EvpnSviNode` already
    recorded the same (device, address) pairing, leaving the fabric with two
    copies and nothing enforcing agreement. This enforces it.

    Matched on device **and** VLAN: a device carries several SVI nodes, so
    matching on device alone would compare a peering SVI against an unrelated
    tenant SVI and report a difference that is not drift.
    """
    findings: list[Finding] = []
    by_device_vlan: dict[tuple[str, Any], list[str]] = {}
    for svi in _edges_of(parsed.interface_virtual):
        device = _node_of(svi.device)
        vlan = _value(svi.dot_1_q_id)
        if device is None or vlan is None:
            continue
        addresses = [_value(a.address) for a in _edges_of(svi.ip_addresses)]
        by_device_vlan[device.id, vlan] = [a for a in addresses if a]

    for svi_node in _edges_of(parsed.evpn_svi_node):
        device = _node_of(svi_node.device)
        svi = _node_of(svi_node.svi)
        recorded = _value(svi_node.ip_address)
        if device is None or svi is None or recorded is None:
            continue
        vlan = _value(svi.svi_id)
        addresses = by_device_vlan.get((device.id, vlan))

        if addresses is None:
            findings.append(
                Finding(
                    message=(
                        f"EvpnSviNode on {device.display_label} for VLAN {vlan} records {recorded} but no matching "
                        "virtual interface exists; not every SVI node is a peering SVI, so this is advisory"
                    ),
                    object_id=svi_node.id,
                    object_type=KIND_SVI_NODE,
                    is_error=False,
                )
            )
            continue

        if recorded not in addresses:
            findings.append(
                Finding(
                    message=(
                        f"EvpnSviNode on {device.display_label} for VLAN {vlan} records {recorded} but the matching "
                        f"virtual interface carries {addresses}; the fabric holds two disagreeing copies"
                    ),
                    object_id=svi_node.id,
                    object_type=KIND_SVI_NODE,
                )
            )
    return findings


def collect_findings(parsed: PeeringConsistencyCheckQuery) -> list[Finding]:
    """Every rule, accumulated. Never returns early.

    A check that stops at the first failure forces a merge-fix-merge cycle for
    each independent problem.
    """
    findings: list[Finding] = []
    for rule in (
        check_asn_matches_device,
        check_address_matches_svi,
        check_one_service_per_cluster,
        check_peer_is_cabled,
        check_peer_role,
        check_svi_node_agreement,
    ):
        findings.extend(rule(parsed))
    return findings


class PeeringConsistencyCheck(InfrahubCheck):
    """Refuse a proposed change whose peering model contradicts itself."""

    query = "peering_consistency_check"

    def validate(self, data: dict) -> None:  # type: ignore[override]
        """Emit every finding. Any log_error blocks the merge."""
        parsed = PeeringConsistencyCheckQuery(**data)
        findings = collect_findings(parsed)

        for finding in findings:
            if finding.is_error:
                self.log_error(
                    message=finding.message,
                    object_id=finding.object_id,
                    object_type=finding.object_type,
                )
            else:
                self.log_info(message=f"ADVISORY: {finding.message}")

        if not any(f.is_error for f in findings):
            self.log_info(message="Peering model is self-consistent across all six rules")
