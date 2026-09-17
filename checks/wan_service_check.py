"""WAN service consistency check.

The WAN service layer names technical objects rather than creating them, which
is why no generator sits beneath it. The cost of that design is that **every one
of its references is unverified**: a service can name another tenant's circuit,
another tenant's VRF, or a zone governing a different routing domain, and the
model loads, the FRR configuration renders, and nothing errors.

This is the WAN's equivalent of `zone-advertisement` on the fabric leg, and it
guards the lab's central claim. `schemas/service/wan_services.yml` says the
isolation is *structural* -- no VRF imports another's route targets anywhere, so
there is no east-west path to filter in the first place -- and that claim is only
true while the services are wired correctly. Nothing checked that they were.

FOUR RULES, and every one describes a failure that is silent today.

* **A circuit that belongs to another tenant.** `ServiceL3vpn.circuits` IS the
  routing domain: two sites reach each other because both circuits are in the
  list, not because anything was leaked. A foreign circuit therefore joins two
  tenants' routing directly, which is exactly what cycle 019's FR-005 warns
  about and what the whole provider-edge design exists to prevent.

* **Two L3VPNs sharing a provider-edge VRF.** The same collapse by a different
  route: one VRF carrying two tenants' prefixes is one routing table, whatever
  the two services claim.

* **A tenant cloud whose zone governs a different VRF.** The firewall is the
  only way into a cloud, and `generate-app-access` derives a grant's destination
  zone by matching the application's VRF against `SecurityZone.vrf`. If a
  cloud's zone names a different VRF than the cloud lives in, the policy being
  written is for somewhere else -- and grants land in the wrong zone with no
  error anywhere.

* **Two clouds sharing a VRF or a zone.** The datacentre-side collapse, and the
  one that most looks like tidy reuse when it is written.

WHY A DECOMMISSIONED SERVICE IS STILL JUDGED. Everywhere except
`generate-network-segment`, `status` is inert: nothing withdraws on
`decommissioned`, so a decommissioned `ServiceL3vpn` still assembles the
provider edge's import policy. Skipping it here would excuse a live
misconfiguration because of a label. See the service-layer section of AGENTS.md.

GLOBAL, with no `targets`. "Two services claim one VRF" has no natural group to
iterate, exactly like `peering-consistency` and `zone-advertisement` beside it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from infrahub_sdk.checks import InfrahubCheck

from .wan_service_check_query import WanServiceCheckQuery

KIND_L3VPN = "ServiceL3vpn"
KIND_CLOUD = "ServiceTenantCloud"


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
    if relationship is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def _name_of(relationship: Any) -> str | None:
    node = _node_of(relationship)
    return None if node is None else _value(node.name)


def check_circuit_membership(parsed: WanServiceCheckQuery) -> list[Finding]:
    """Rule 1: every member circuit belongs to the L3VPN's own tenant."""
    findings: list[Finding] = []

    for vpn in _edges_of(parsed.service_l_3_vpn):
        tenant = _node_of(vpn.tenant)
        if tenant is None:
            # Mandatory in the schema. A service without one is a different
            # defect, and attributing it here would name the wrong thing.
            continue

        for circuit in _edges_of(vpn.circuits):
            owner = _node_of(circuit.tenant)
            if owner is None or owner.id == tenant.id:
                continue
            findings.append(
                Finding(
                    message=(
                        f"L3VPN {_value(vpn.name)!r} belongs to {_value(tenant.name)!r} but carries circuit "
                        f"{_value(circuit.circuit_id)!r}, which belongs to {_value(owner.name)!r}. Membership "
                        "of this list is the routing domain, so the two tenants would reach each other "
                        "directly across the provider edge."
                    ),
                    object_id=vpn.id,
                    object_type=KIND_L3VPN,
                )
            )

    return findings


def _shared(pairs: list[tuple[str, str, str, str]]) -> dict[str, list[tuple[str, str, str]]]:
    """Group ``(peer_id, peer_name, service_id, service_name)`` by peer id."""
    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for peer_id, peer_name, service_id, service_name in pairs:
        grouped[peer_id].append((peer_name, service_id, service_name))
    return {peer: entries for peer, entries in grouped.items() if len(entries) > 1}


def check_exclusive_vrfs(parsed: WanServiceCheckQuery) -> list[Finding]:
    """Rule 2: no provider-edge VRF carries two L3VPNs."""
    findings: list[Finding] = []

    pairs = [
        (vrf.id, _value(vrf.name) or vrf.id, vpn.id, _value(vpn.name) or vpn.id)
        for vpn in _edges_of(parsed.service_l_3_vpn)
        if (vrf := _node_of(vpn.vrf)) is not None
    ]

    for _, entries in sorted(_shared(pairs).items()):
        vrf_name = entries[0][0]
        names = ", ".join(sorted(repr(name) for _, _, name in entries))
        findings.extend(
            Finding(
                message=(
                    f"Provider-edge VRF {vrf_name!r} is claimed by {len(entries)} L3VPNs ({names}). "
                    "One VRF carrying two tenants' prefixes is one routing table, whatever the "
                    "services claim."
                ),
                object_id=service_id,
                object_type=KIND_L3VPN,
            )
            for _, service_id, _ in entries
        )

    return findings


def check_cloud_zone_matches_vrf(parsed: WanServiceCheckQuery) -> list[Finding]:
    """Rule 3: a cloud's firewall zone governs the VRF the cloud lives in."""
    findings: list[Finding] = []

    for cloud in _edges_of(parsed.service_tenant_cloud):
        vrf = _node_of(cloud.vrf)
        zone = _node_of(cloud.zone)
        if vrf is None or zone is None:
            continue

        zone_vrf = _node_of(zone.vrf)
        if zone_vrf is None:
            # A zone with no VRF cannot be matched to an application either, so
            # it is a defect -- but it is the zone's, not this service's.
            continue
        if zone_vrf.id == vrf.id:
            continue

        findings.append(
            Finding(
                message=(
                    f"Tenant cloud {_value(cloud.name)!r} lives in VRF {_value(vrf.name)!r} but names zone "
                    f"{_value(zone.name)!r}, which governs {_value(zone_vrf.name)!r}. The firewall is the only "
                    "way in, and generate-app-access matches an application's VRF against the zone's -- so "
                    "grants for this cloud would be written into a policy for somewhere else."
                ),
                object_id=cloud.id,
                object_type=KIND_CLOUD,
            )
        )

    return findings


def check_exclusive_clouds(parsed: WanServiceCheckQuery) -> list[Finding]:
    """Rule 4: no VRF and no zone is shared between two tenant clouds."""
    findings: list[Finding] = []

    for label, accessor in (("VRF", "vrf"), ("firewall zone", "zone")):
        pairs = [
            (peer.id, _value(peer.name) or peer.id, cloud.id, _value(cloud.name) or cloud.id)
            for cloud in _edges_of(parsed.service_tenant_cloud)
            if (peer := _node_of(getattr(cloud, accessor, None))) is not None
        ]
        for _, entries in sorted(_shared(pairs).items()):
            peer_name = entries[0][0]
            names = ", ".join(sorted(repr(name) for _, _, name in entries))
            findings.extend(
                Finding(
                    message=(
                        f"{label.capitalize()} {peer_name!r} is shared by {len(entries)} tenant clouds "
                        f"({names}). The lab's isolation is structural -- sharing one collapses two "
                        "tenants into a single domain."
                    ),
                    object_id=service_id,
                    object_type=KIND_CLOUD,
                )
                for _, service_id, _ in entries
            )

    return findings


def collect_findings(parsed: WanServiceCheckQuery) -> list[Finding]:
    return (
        check_circuit_membership(parsed)
        + check_exclusive_vrfs(parsed)
        + check_cloud_zone_matches_vrf(parsed)
        + check_exclusive_clouds(parsed)
    )


class WanServiceConsistencyCheck(InfrahubCheck):
    """Refuse a proposed change that would join two tenants."""

    query = "wan_service_check"

    def validate(self, data: dict) -> None:  # type: ignore[override]
        """Emit every finding. Any log_error blocks the merge."""
        parsed = WanServiceCheckQuery(**data)
        findings = collect_findings(parsed)

        for finding in findings:
            self.log_error(
                message=finding.message,
                object_id=finding.object_id,
                object_type=finding.object_type,
            )

        if not findings:
            # Says what was examined rather than merely that nothing was wrong.
            # A check reporting success over an empty collection manufactures
            # confidence, which peering_consistency_check documents at length.
            vpns = len(_edges_of(parsed.service_l_3_vpn))
            clouds = len(_edges_of(parsed.service_tenant_cloud))
            circuits = sum(len(_edges_of(vpn.circuits)) for vpn in _edges_of(parsed.service_l_3_vpn))
            self.log_info(
                message=(
                    f"WAN services are consistent: {vpns} L3VPN(s) over {circuits} circuit(s) "
                    f"and {clouds} tenant cloud(s)"
                )
            )
