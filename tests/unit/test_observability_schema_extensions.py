"""Contract tests for the schema extensions observability needs (cycle 034).

* **Every device kind can be observed, and none becomes pushable.** Only
  ``DcimFabricSwitch`` had an address; the FRR routers and the firewall were
  reached by container name and the k3s nodes not at all. A collector running
  in a pod cannot resolve a container name, so the other three kinds gain a
  ``telemetry_address``. It is NOT called ``mgmt_ip``: that name means "push
  over eAPI" to the reconciler and cycle 027 holds it on switches alone. Each
  declares its own identifier, because one identifier shared by several
  one-way relationships reads to Infrahub as one relationship.
* **SNMP is optional.** Absent, ``junos_config`` renders no ``snmp`` stanza,
  which is what keeps the artifact byte-identical to the device file until the
  stanza is deliberately added to both.
* **SSO is declared, never inferred.** ``sso_provider`` defaults to ``none`` so
  every existing application renders exactly as it did.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

SCHEMAS = Path(__file__).parents[2] / "schemas"


def _extension(kind: str) -> dict[str, Any]:
    """Merge every ``extensions`` entry for ``kind`` across ``schemas/``."""
    merged: dict[str, list[dict[str, Any]]] = {"attributes": [], "relationships": []}
    for path in sorted(SCHEMAS.rglob("*.yml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if not isinstance(document, dict):
                continue
            for entry in document.get("extensions", {}).get("nodes", []):
                if entry.get("kind") == kind:
                    merged["attributes"] += entry.get("attributes", [])
                    merged["relationships"] += entry.get("relationships", [])
    return merged


def _named(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [i for i in items if i["name"] == name]
    assert len(matches) == 1, f"expected exactly one {name}, found {len(matches)}"
    return matches[0]


def test_every_non_switch_device_kind_has_an_optional_telemetry_address() -> None:
    identifiers = []
    for kind in ("DcimDevice", "SecurityFirewall", "ComputePhysicalServer"):
        assert not [r for r in _extension(kind)["relationships"] if r["name"] == "mgmt_ip"], (
            f"{kind} must not gain mgmt_ip: the reconciler reads that name as an eAPI address"
        )
        rel = _named(_extension(kind)["relationships"], "telemetry_address")
        assert rel["peer"] == "IpamIPAddress", kind
        assert rel.get("cardinality") == "one", kind
        assert rel.get("optional") is True, kind
        identifiers.append(rel["identifier"])
    assert len(set(identifiers)) == len(identifiers), identifiers


def test_firewall_snmp_is_optional() -> None:
    firewall = _extension("SecurityFirewall")
    community = _named(firewall["attributes"], "snmp_community")
    assert community["kind"] == "Text"
    assert community.get("optional") is True
    clients = _named(firewall["relationships"], "snmp_clients")
    assert clients["peer"] == "IpamPrefix"
    assert clients.get("cardinality") == "one"
    assert clients.get("optional") is True


def test_sso_provider_is_declared_and_defaults_to_none() -> None:
    nodes = {}
    for document in yaml.safe_load_all((SCHEMAS / "service" / "kubernetes_services.yml").read_text(encoding="utf-8")):
        for node in (document or {}).get("nodes", []):
            nodes[f"{node['namespace']}{node['name']}"] = node
    sso = _named(nodes["ServiceFabricApp"]["attributes"], "sso_provider")
    assert sso["kind"] == "Dropdown"
    assert [c["name"] for c in sso["choices"]] == ["none", "dex"]
    assert sso.get("default_value") == "none"
