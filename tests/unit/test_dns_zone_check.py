"""The DNS zone consistency check (specs/037-lab-dns-service)."""

from __future__ import annotations

from typing import Any

from checks.dns_zone_check import collect_findings
from checks.dns_zone_check_query import DnsZoneCheckQuery

ZONE = "int.otternet.lab"


def _v(x: Any) -> dict[str, Any]:
    return {"value": x}


def _app(name: str, prefix: str | None, zone: str | None = None) -> dict[str, Any]:
    block = {"node": {"id": f"p-{name}", "prefix": _v(prefix)}} if prefix else {"node": None}
    return {
        "node": {
            "id": name,
            "name": _v(name),
            "status": _v("active"),
            "exposed": _v(True),
            "dns_zone": _v(zone),
            "vip_block": block,
        }
    }


def _address(address: str, fqdn: str) -> dict[str, Any]:
    return {"node": {"id": address, "address": _v(address), "fqdn": _v(fqdn)}}


def _parse(apps: list[dict[str, Any]], addresses: list[dict[str, Any]]) -> DnsZoneCheckQuery:
    return DnsZoneCheckQuery(ServiceFabricApp={"edges": apps}, IpamIPAddress={"edges": addresses})


def test_one_resolver_and_names_inside_their_blocks_pass() -> None:
    parsed = _parse(
        [_app("otternet-dns", "10.112.240.96/28", ZONE), _app("otter-shop", "10.112.240.16/28")],
        [_address("10.112.240.96/32", f"otternet-dns.{ZONE}"), _address("10.112.240.16/32", f"otter-shop.{ZONE}")],
    )
    assert collect_findings(parsed) == []


def test_two_resolvers_are_both_reported() -> None:
    parsed = _parse([_app("a", None, ZONE), _app("b", None, "other.lab")], [])
    findings = collect_findings(parsed)
    assert len(findings) == 2
    assert all("one resolver" in f.message for f in findings)


def test_a_name_outside_its_applications_block_is_reported() -> None:
    parsed = _parse(
        [_app("otternet-dns", "10.112.240.96/28", ZONE), _app("otter-shop", "10.112.240.16/28")],
        [_address("10.112.240.200/32", f"otter-shop.{ZONE}")],
    )
    findings = collect_findings(parsed)
    assert len(findings) == 1
    assert "outside application otter-shop" in findings[0].message


def test_a_hand_made_name_with_no_application_is_not_this_checks_business() -> None:
    parsed = _parse([_app("otternet-dns", "10.112.240.96/28", ZONE)], [_address("10.0.0.5/32", f"printer.{ZONE}")])
    assert collect_findings(parsed) == []
