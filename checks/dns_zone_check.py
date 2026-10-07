"""DNS zone consistency check (specs/037-lab-dns-service).

Two statements about the whole graph, neither of which a schema constraint can
make:

* **At most one application is the resolver.** A lab has one zone and one
  resolver; two applications carrying a ``dns_zone`` would each be asked for
  their own artifact and the names would belong to whichever rendered last.
* **A name points inside its own application's block.** An address named
  ``<app>.<zone>`` that lies outside ``<app>``'s VIP block is a name that sends
  users somewhere the application is not -- loaded and merged cleanly, and
  wrong. A name with no such application (somebody's hand-made record) is not
  this check's business.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any

from infrahub_sdk.checks import InfrahubCheck

from .dns_zone_check_query import DnsZoneCheckQuery


@dataclass(frozen=True)
class Finding:
    """One violation, with what the UI needs to attribute it."""

    message: str
    object_id: str
    object_type: str


def _value(wrapper: Any) -> Any:
    return wrapper.value if wrapper is not None else None


def collect_findings(parsed: DnsZoneCheckQuery) -> list[Finding]:
    """Every violation of the two rules."""
    apps = [edge.node for edge in parsed.service_fabric_app.edges if edge.node is not None]
    findings: list[Finding] = []

    resolvers = [app for app in apps if _value(app.dns_zone)]
    if len(resolvers) > 1:
        names = ", ".join(sorted(str(_value(app.name)) for app in resolvers))
        findings.extend(
            Finding(
                message=f"{_value(app.name)!r} has a dns_zone, but so do {names}; a lab has one resolver",
                object_id=app.id,
                object_type="ServiceFabricApp",
            )
            for app in resolvers
        )

    zones = {str(_value(app.dns_zone)) for app in resolvers}
    blocks = {
        str(_value(app.name)): ipaddress.ip_network(str(_value(app.vip_block.node.prefix)), strict=False)
        for app in apps
        if app.vip_block is not None and app.vip_block.node is not None and _value(app.vip_block.node.prefix)
    }
    for edge in parsed.ipam_ip_address.edges:
        node = edge.node
        if node is None:
            continue
        fqdn = str(_value(node.fqdn))
        for zone in zones:
            suffix = f".{zone}"
            if not fqdn.endswith(suffix):
                continue
            label = fqdn[: -len(suffix)]
            block = blocks.get(label)
            address = ipaddress.ip_interface(str(_value(node.address))).ip
            if block is not None and address not in block:
                findings.append(
                    Finding(
                        message=(
                            f"{fqdn} points at {address}, which is outside application {label}'s VIP block "
                            f"{block}; the name would send users where the application is not"
                        ),
                        object_id=node.id,
                        object_type="IpamIPAddress",
                    )
                )
    return findings


class DnsZoneConsistencyCheck(InfrahubCheck):
    """Refuse a proposed change whose DNS names contradict the model."""

    query = "dns_zone_check"

    def validate(self, data: dict) -> None:  # type: ignore[override]
        """Emit every finding. Any log_error blocks the merge."""
        findings = collect_findings(DnsZoneCheckQuery(**data))
        for finding in findings:
            self.log_error(message=finding.message, object_id=finding.object_id, object_type=finding.object_type)
        if not findings:
            self.log_info(
                message="DNS names are consistent: one resolver, and every name inside its application's block"
            )
