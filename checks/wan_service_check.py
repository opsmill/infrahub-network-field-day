"""WAN service consistency check.

The WAN service layer names technical objects rather than creating them, which
is why no generator sits beneath it. The cost of that design is that **every one
of its references is unverified**: a service can name another tenant's circuit,
another tenant's VRF, or a zone governing a different routing domain, and the
model loads, the SR Linux configuration renders, and nothing errors.

This is the WAN's equivalent of `zone-advertisement` on the fabric leg, and it
guards the lab's central claim. `schemas/service/wan_services.yml` says the
isolation is *structural* -- no VRF imports another's route targets anywhere, so
there is no east-west path to filter in the first place -- and that claim is only
true while the services are wired correctly. Nothing checked that they were.

SIX RULES, and every one describes a failure that is otherwise silent. The
first four guard isolation:

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

TWO MORE, added when a portal request turned out to merge as a no-op.
`srl_config` rendered `acme` and `globex` by name and skipped every other
tenant, so an L3VPN for a third tenant merged green and reached no router. The
renderer now takes any tenant; these say what a tenant still needs to be
rendered, so the proposed change goes red naming it:

* **A live L3VPN that cannot be put on a port** (rule 5): no provider-edge VRF,
  no live tenant cloud, no `WanSite` at all, or a site that cannot be attached
  -- a BGP site without sessions on both a provider edge and an `srl_routers`
  customer edge, a static site whose next hop nobody owns, an attachment no
  provider-edge port is on, a LAN outside the customer aggregate the fabric and
  the firewall accept, a name SR Linux cannot carry.

* **A service that renders only through a live L3VPN, without one** (rule 6):
  a tenant cloud whose tenant has none, and live L3VPNs that disagree on (or all omit) the
  shared DC service range.

These two judge LIVE services only. Rules 1-4 refuse to let a label excuse a
misconfiguration; rules 5-6 ask whether a request will render, and a withdrawn
one deliberately will not.

WHY A DECOMMISSIONED SERVICE IS STILL JUDGED. Everywhere except
`generate-network-segment`, `status` is inert: nothing withdraws on
`decommissioned`, so a decommissioned `ServiceL3vpn` still assembles the
provider edge's import policy. Skipping it here would excuse a live
misconfiguration because of a label. See the service-layer section of AGENTS.md.

GLOBAL, with no `targets`. "Two services claim one VRF" has no natural group to
iterate, exactly like `peering-consistency` and `zone-advertisement` beside it.
"""

from __future__ import annotations

import ipaddress
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from infrahub_sdk.checks import InfrahubCheck

from .wan_service_check_query import WanServiceCheckQuery

KIND_L3VPN = "ServiceL3vpn"
KIND_CLOUD = "ServiceTenantCloud"

# transforms/srl_config.py's two constants, restated rather than imported: a
# check is loaded by Infrahub's check runner on its own, and a cross-package
# import from it is one more thing that can fail at sync time with a message
# naming neither file. tests/unit/test_wan_service_check.py holds them equal.
DECOMMISSIONED_STATUSES = frozenset({"decommissioning", "decommissioned"})
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


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


# ---------------------------------------------------------------------------
# Rules 5 and 6 -- would srl_config render this request at all?
# ---------------------------------------------------------------------------


def _live(node: Any) -> bool:
    """`srl_config._live`, exactly: a decommissioned service renders as absent.

    Rules 1-4 judge decommissioned services too, because a label must not
    excuse a misconfiguration. These two do not: they ask whether a request
    WILL render, and a withdrawn one deliberately will not.
    """
    status = _value(getattr(node, "status", None))
    return status not in DECOMMISSIONED_STATUSES


def _strip_mask(address: str) -> str:
    return address.split("/", 1)[0]


def _interface_addresses(device: Any) -> list[str]:
    addresses: list[str] = []
    for interface in _edges_of(device.interfaces):
        addresses.extend(_value(a.address) for a in _edges_of(getattr(interface, "ip_addresses", None)))
    return [a for a in addresses if a]


def _address_owners(parsed: WanServiceCheckQuery) -> dict[str, str]:
    """Bare address -> owning device, as srl_config resolves a static site's CE."""
    owners: dict[str, str] = {}
    for address in _edges_of(parsed.ipam_ip_address):
        interface = _node_of(address.interface)
        device = _node_of(getattr(interface, "device", None)) if interface is not None else None
        if device is not None and _value(address.address):
            owners[_strip_mask(_value(address.address))] = _value(device.name)
    return owners


def _on_a_port(attachment: str, ports: list[str]) -> bool:
    ip = ipaddress.ip_address(attachment)
    return any(ip in ipaddress.ip_interface(port).network for port in ports)


def _within(prefix: str, aggregate: str) -> bool:
    inner, outer = ipaddress.ip_network(prefix), ipaddress.ip_network(aggregate)
    return inner.version == outer.version and inner.network_address in outer and inner.prefixlen >= outer.prefixlen


def _l3vpn_finding(vpn: Any, message: str) -> Finding:
    return Finding(message=message, object_id=vpn.id, object_type=KIND_L3VPN)


def _site_prerequisites(
    tenant: str,
    site: Any,
    *,
    pe_ports: list[str],
    devices: dict[str, Any],
    owners: dict[str, str],
    aggregate: str | None,
) -> list[str]:
    """Every reason one site of a live tenant cannot be rendered onto a port."""
    name = _value(site.name)
    label = f"site {tenant}/{name}"
    missing: list[str] = []
    if not SAFE_NAME.match(name or ""):
        missing.append(f"{label}: the name cannot be spliced into an SR Linux peer-group or policy name")

    lan = _value(_node_of(site.lan_prefix).prefix) if _node_of(site.lan_prefix) else None
    if aggregate and lan and not _within(lan, aggregate):
        missing.append(
            f"{label}: LAN {lan} lies outside the customer aggregate {aggregate}, which is all border-leaf1 "
            "accepts from the WAN and all fw1 routes back -- the route would reach the provider and stop there"
        )

    attachment: str | None = None
    if _value(site.attachment_kind) == "bgp":
        sessions = _edges_of(site.bgp_sessions)
        by_role = {_value(_node_of(s.device).role): s for s in sessions if _node_of(s.device) is not None}
        pe_side, ce_side = by_role.get("isp_edge"), by_role.get("customer_edge")
        if _value(site.site_asn) is None:
            missing.append(f"{label}: no site_asn, so its peer group on the provider edge has no peer-as")
        if pe_side is None or ce_side is None:
            missing.append(
                f"{label}: a BGP site needs a session on the provider edge AND one on a customer edge "
                "(device role customer_edge); it has "
                + (", ".join(sorted(f"{_value(_node_of(s.device).name)}" for s in sessions)) or "none")
            )
        else:
            attachment = _value(ce_side.peer_address)
            ce_name = _value(_node_of(ce_side.device).name)
            ce = devices.get(ce_name)
            if ce is None or not _edges_of(ce.member_of_groups):
                missing.append(
                    f"{label}: customer edge {ce_name!r} is not in the `srl_routers` group, so no "
                    "configuration is rendered for it and the session never comes up"
                )
            elif _node_of(ce.router_id) is None:
                missing.append(f"{label}: customer edge {ce_name!r} has no router id")
    else:
        route = next(iter(_edges_of(site.static_routes)), None)
        if route is None:
            missing.append(f"{label}: a static site needs a static route toward its CE, and has none")
        else:
            attachment = _strip_mask(_value(route.next_hop))
            if attachment not in owners:
                missing.append(
                    f"{label}: no device owns the static route's next hop {attachment}, so there is no CE to name"
                )

    if attachment and not _on_a_port(attachment, pe_ports):
        missing.append(
            f"{label}: no provider-edge interface has an address on the subnet of {attachment}, so the "
            "site has no port to put in the tenant's VRF"
        )
    return missing


def check_l3vpn_renderable(parsed: WanServiceCheckQuery) -> list[Finding]:
    """Rule 5: a live L3VPN has everything srl_config needs to put it on a port.

    The renderer once rendered two tenants by NAME and skipped every other one
    without a word, so an L3VPN requested through the portal for a third tenant
    merged green and changed nothing. The renderer now takes any tenant; what it
    cannot take is a tenant the lab has no attachment for, and that is reported
    here -- in the proposed change, naming the missing prerequisite -- instead
    of at render time or not at all.
    """
    findings: list[Finding] = []
    owners = _address_owners(parsed)
    devices = {_value(d.name): d for d in _edges_of(parsed.dcim_device)}
    pe_ports = [a for d in devices.values() if _value(d.role) == "isp_edge" for a in _interface_addresses(d)]
    peering = next(iter(_edges_of(parsed.wan_internet_peering)), None)
    aggregate_node = _node_of(peering.customer_aggregate) if peering is not None else None
    aggregate = _value(aggregate_node.prefix) if aggregate_node is not None else None

    sites: dict[str, list[Any]] = defaultdict(list)
    for site in _edges_of(parsed.wan_site):
        if (owner := _name_of(site.tenant)) is not None:
            sites[owner].append(site)
    clouds = {_name_of(c.tenant) for c in _edges_of(parsed.service_tenant_cloud) if _live(c)}

    live: dict[str, list[Any]] = defaultdict(list)
    for vpn in _edges_of(parsed.service_l_3_vpn):
        if _live(vpn) and (tenant := _name_of(vpn.tenant)) is not None:
            live[tenant].append(vpn)

    for tenant, vpns in sorted(live.items()):
        if len(vpns) > 1:
            names = ", ".join(sorted(repr(_value(v.name)) for v in vpns))
            findings.extend(
                _l3vpn_finding(
                    vpn,
                    f"Tenant {tenant!r} has {len(vpns)} live L3VPNs ({names}). The provider edge carries one "
                    "per tenant, and srl_config refuses to render either rather than let one replace the other.",
                )
                for vpn in vpns
            )
            continue

        vpn = vpns[0]
        missing: list[str] = []
        if not SAFE_NAME.match(tenant):
            missing.append(f"the tenant name {tenant!r} cannot be spliced into an SR Linux policy name")
        vrf = _node_of(vpn.vrf)
        if vrf is None:
            missing.append("no provider-edge VRF (`vrf`), so there is no network instance to put its sites in")
        elif not SAFE_NAME.match(_value(vrf.name) or ""):
            missing.append(f"VRF {_value(vrf.name)!r} cannot be an SR Linux network-instance name")
        if tenant not in clouds:
            missing.append(
                f"no live ServiceTenantCloud for {tenant!r}, so its import policy has no cloud subnet and "
                "srl_config refuses the provider edge"
            )
        if not sites.get(tenant):
            missing.append(
                f"no WanSite for {tenant!r}: the lab has no attachment circuit, CE or provider-edge port for "
                "this tenant, so its VRF would render with nothing in it. Model the site (and its circuit, "
                "CE and PE port) first"
            )
        for site in sorted(sites.get(tenant, []), key=lambda s: _value(s.name) or ""):
            missing.extend(
                _site_prerequisites(
                    tenant, site, pe_ports=pe_ports, devices=devices, owners=owners, aggregate=aggregate
                )
            )

        findings.extend(
            _l3vpn_finding(vpn, f"L3VPN {_value(vpn.name)!r} cannot be rendered onto the WAN: {reason}.")
            for reason in missing
        )

    return findings


def check_dependents_renderable(parsed: WanServiceCheckQuery) -> list[Finding]:
    """Rule 6: services that render only THROUGH a live L3VPN, and the shared range.

    A tenant cloud reaches the WAN only as part of its tenant's L3VPN.
    Without a live one it renders nowhere, and nothing
    else reads them -- the same merged no-op rule 5 exists to catch.
    """
    findings: list[Finding] = []
    live_vpns = [v for v in _edges_of(parsed.service_l_3_vpn) if _live(v)]
    live_tenants = {_name_of(v.tenant) for v in live_vpns}

    for cloud in _edges_of(parsed.service_tenant_cloud):
        tenant = _name_of(cloud.tenant)
        if _live(cloud) and tenant not in live_tenants:
            findings.append(
                Finding(
                    message=(
                        f"Tenant cloud {_value(cloud.name)!r} for {tenant!r} renders nowhere: srl_config reads a "
                        "cloud only through its tenant's L3VPN, and that tenant has no live ServiceL3vpn."
                    ),
                    object_id=cloud.id,
                    object_type=KIND_CLOUD,
                )
            )

    declared = {
        vpn.id: frozenset(_value(p.prefix) for p in _edges_of(vpn.dc_service_prefixes))
        for vpn in live_vpns
        if _edges_of(vpn.dc_service_prefixes)
    }
    if live_vpns and not declared:
        findings.extend(
            _l3vpn_finding(
                vpn,
                f"L3VPN {_value(vpn.name)!r}: no live L3VPN states dc_service_prefixes, so the shared DC "
                "range every tenant imports has no source and srl_config refuses the provider edge.",
            )
            for vpn in live_vpns
        )
    elif len(set(declared.values())) > 1:
        findings.extend(
            _l3vpn_finding(
                vpn,
                f"L3VPN {_value(vpn.name)!r} states DC service prefixes {', '.join(sorted(declared[vpn.id]))}, "
                "which differ from another live L3VPN's. The range is shared -- it is in every tenant's "
                "import policy -- so srl_config refuses to pick one.",
            )
            for vpn in live_vpns
            if vpn.id in declared
        )

    return findings


def collect_findings(parsed: WanServiceCheckQuery) -> list[Finding]:
    return (
        check_circuit_membership(parsed)
        + check_exclusive_vrfs(parsed)
        + check_cloud_zone_matches_vrf(parsed)
        + check_exclusive_clouds(parsed)
        + check_l3vpn_renderable(parsed)
        + check_dependents_renderable(parsed)
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
            sites = len(_edges_of(parsed.wan_site))
            self.log_info(
                message=(
                    f"WAN services are consistent and renderable: {vpns} L3VPN(s) over {circuits} circuit(s), "
                    f"{clouds} tenant cloud(s) and {sites} WAN site(s)"
                )
            )
