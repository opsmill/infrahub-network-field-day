"""The DNS Zone Configuration transform (specs/037-lab-dns-service).

What the resolver answers is derived from Infrahub, so what is asserted here is
the derivation: which names become records, which are skipped and said so, and
the three things the renderer refuses rather than renders.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import yaml

from transforms.dns_zone_config import (
    DnsZoneConfig,
    DnsZoneConfigError,
    Record,
    render_corefile,
    render_zone,
    select_records,
    serial_for,
)

ZONE = "int.otternet.lab"
APPS: dict[str, tuple[str | None, bool]] = {
    "otternet-dns": ("active", True),
    "otter-shop": ("active", True),
    "old-shop": ("decommissioning", True),
    "internal": ("active", False),
}


def _named(*pairs: tuple[str, str]) -> list[tuple[str, str]]:
    return [(f"{label}.{ZONE}", f"{address}/32") for label, address in pairs]


def test_a_live_application_becomes_one_record() -> None:
    records, notes = select_records(
        ZONE, _named(("otternet-dns", "10.112.240.96"), ("otter-shop", "10.112.240.16")), APPS
    )
    assert records == [Record("otter-shop", "10.112.240.16"), Record("otternet-dns", "10.112.240.96")]
    assert notes == []


def test_a_withdrawn_or_unexposed_application_is_skipped_and_said_so() -> None:
    records, notes = select_records(
        ZONE, _named(("otternet-dns", "10.112.240.96"), ("old-shop", "10.112.240.32"), ("internal", "10.0.0.1")), APPS
    )
    assert [r.label for r in records] == ["otternet-dns"]
    assert any("old-shop" in n and "decommissioning" in n for n in notes)
    assert any("internal" in n and "not exposed" in n for n in notes)


def test_a_name_outside_the_zone_is_not_this_resolvers() -> None:
    records, _ = select_records(
        ZONE, [("a.other.lab", "10.0.0.9/32"), *_named(("otternet-dns", "10.112.240.96"))], APPS
    )
    assert [r.label for r in records] == ["otternet-dns"]


def test_a_hand_made_record_with_no_application_is_kept() -> None:
    records, _ = select_records(ZONE, _named(("otternet-dns", "10.112.240.96"), ("printer", "10.0.0.5")), APPS)
    assert Record("printer", "10.0.0.5") in records


def test_two_addresses_for_one_name_are_refused() -> None:
    with pytest.raises(DnsZoneConfigError, match="two addresses"):
        select_records(ZONE, _named(("otter-shop", "10.112.240.16"), ("otter-shop", "10.112.240.17")), APPS)


def test_an_empty_zone_is_refused() -> None:
    with pytest.raises(DnsZoneConfigError, match="empty zone"):
        render_zone(ZONE, "otternet-dns", [], [])


def test_a_resolver_with_no_name_of_its_own_is_refused() -> None:
    with pytest.raises(DnsZoneConfigError, match="NS record"):
        render_zone(ZONE, "otternet-dns", [Record("otter-shop", "10.112.240.16")], [])


def test_the_serial_changes_with_the_records_and_only_with_them() -> None:
    a = [Record("otternet-dns", "10.112.240.96")]
    b = [*a, Record("otter-shop", "10.112.240.16")]
    assert serial_for(a) == serial_for(list(a))
    assert serial_for(a) != serial_for(b)
    assert render_zone(ZONE, "otternet-dns", a, []) == render_zone(ZONE, "otternet-dns", list(a), [])


def test_the_zone_file_has_the_soa_the_ns_and_one_a_record_each() -> None:
    zone = render_zone(
        ZONE, "otternet-dns", [Record("otter-shop", "10.112.240.16"), Record("otternet-dns", "10.112.240.96")], []
    )
    lines = zone.splitlines()
    assert lines[0] == f"$ORIGIN {ZONE}."
    assert lines[2].startswith(f"@ IN SOA otternet-dns.{ZONE}. hostmaster.{ZONE}.")
    assert lines[3] == f"@ IN NS otternet-dns.{ZONE}."
    assert "otter-shop IN A 10.112.240.16" in lines
    assert "otternet-dns IN A 10.112.240.96" in lines


def test_the_corefile_serves_the_zone_from_the_file_and_refuses_everything_else() -> None:
    corefile = render_corefile(ZONE)
    assert f"{ZONE}:53 {{" in corefile
    assert f"file /etc/coredns/{ZONE}.db" in corefile
    assert "reload 10s" in corefile
    assert "rcode REFUSED" in corefile
    # the chart's probes need both
    assert "health" in corefile
    assert "ready" in corefile
    assert "forward" not in corefile


def _data(zone: str | None = ZONE, namespace: str | None = "otternet-dns", **extra: Any) -> dict[str, Any]:
    def value(v: Any) -> dict[str, Any]:
        return {"value": v}

    return {
        "target": {
            "edges": [
                {
                    "node": {
                        "id": "r1",
                        "name": value("otternet-dns"),
                        "dns_zone": value(zone),
                        "namespace_name": value(namespace),
                    }
                }
            ]
        },
        "records": {
            "edges": [
                {"node": {"id": "a1", "address": value("10.112.240.96/32"), "fqdn": value(f"otternet-dns.{ZONE}")}},
                {"node": {"id": "a2", "address": value("10.112.240.16/32"), "fqdn": value(f"otter-shop.{ZONE}")}},
            ]
        },
        "apps": {
            "edges": [
                {
                    "node": {
                        "id": "r1",
                        "name": value("otternet-dns"),
                        "status": value("active"),
                        "exposed": value(True),
                    }
                },
                {"node": {"id": "s1", "name": value("otter-shop"), "status": value("active"), "exposed": value(True)}},
            ]
        },
        **extra,
    }


def _render(data: dict[str, Any]) -> str:
    return asyncio.run(DnsZoneConfig.__new__(DnsZoneConfig).transform(data))


def test_the_artifact_is_one_configmap_with_the_corefile_and_the_zone() -> None:
    manifest = yaml.safe_load(_render(_data()))
    assert manifest["kind"] == "ConfigMap"
    assert manifest["metadata"]["name"] == "lab-dns"
    assert manifest["metadata"]["namespace"] == "otternet-dns"
    assert set(manifest["data"]) == {"Corefile", f"{ZONE}.db"}
    assert "otter-shop IN A 10.112.240.16" in manifest["data"][f"{ZONE}.db"]


def test_a_render_with_nothing_changed_is_byte_identical() -> None:
    assert _render(_data()) == _render(_data())


def test_an_application_with_no_dns_zone_is_not_a_resolver() -> None:
    with pytest.raises(DnsZoneConfigError, match="not a resolver"):
        _render(_data(zone=None))


def test_a_resolver_with_no_namespace_is_refused() -> None:
    with pytest.raises(DnsZoneConfigError, match="namespace_name"):
        _render(_data(namespace=None))
