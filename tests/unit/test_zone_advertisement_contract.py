"""Contract tests for the zone advertisement policy.

Against the YAML files rather than a live server, so they run in CI without an
instance — the same choice `tests/unit/test_fw_static_route_objects.py` makes.

Two of these tests are worth more than the rest and both are negative:

* `test_the_advertising_device_peers_the_fabric_switch_kind` — `DcimDevice` in
  this repository is the WAN's FRR routers. A relationship peered there would
  pass `infrahubctl schema check`, load cleanly, and resolve to nothing, and the
  failure would surface a cycle later as "the generator never finds a device".
* `test_the_tenant_cloud_zones_advertise_nothing` — populating `acme-cloud`
  would look more complete and would invert the field's meaning. Those prefixes
  sit *inside* `PL-DC-ADVERTISED`: they are the subject of an advertisement
  toward `wan`, not the destination of one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[2]
SECURITY_EXTENSIONS = REPO_ROOT / "schemas/security_extensions.yml"
SECURITY_OBJECTS = REPO_ROOT / "objects/32_nfd41_security.yml"

# The lab, as configured. Each value is evidence from
# lab/avd/intended/configs/border-leaf1.cfg, not a preference.
BORDER_LEAF = "leaf-nfd41-pod1-3-1"
ADVERTISING_ZONES = {
    "branch": "PL-DC-ADVERTISED-BRANCH",
    "wan": "PL-DC-ADVERTISED",
}
# The DC advertises nothing toward these. k8s-prod and app-prod *are* the DC;
# the two tenant clouds are the subject of an advertisement toward `wan`.
SILENT_ZONES = ("k8s-prod", "app-prod", "acme-cloud", "globex-cloud")

IDENTIFIER = "security_zone__advertising_device"


def _extension(kind: str) -> dict[str, Any]:
    """The extensions entry for one kind in security_extensions.yml."""
    document = yaml.safe_load(SECURITY_EXTENSIONS.read_text(encoding="utf-8"))
    for node in document.get("extensions", {}).get("nodes", []):
        if node.get("kind") == kind:
            return node
    pytest.fail(f"schemas/security_extensions.yml extends no {kind!r}")


def _field(kind: str, section: str, name: str) -> dict[str, Any]:
    for entry in _extension(kind).get(section, []) or []:
        if entry.get("name") == name:
            return entry
    pytest.fail(f"{kind} has no {section[:-1]} named {name!r}")


def _zones() -> dict[str, dict[str, Any]]:
    for document in yaml.safe_load_all(SECURITY_OBJECTS.read_text(encoding="utf-8")):
        if document and document.get("spec", {}).get("kind") == "SecurityZone":
            return {row["name"]: row for row in document["spec"]["data"]}
    pytest.fail("objects/32_nfd41_security.yml declares no SecurityZone document")


# ---------------------------------------------------------------------------
# US1 — the prefix list's name
# ---------------------------------------------------------------------------


def test_the_prefix_list_attribute_exists_and_is_text() -> None:
    attribute = _field("SecurityZone", "attributes", "dc_advertised_prefix_list")
    assert attribute["kind"] == "Text"


def test_the_prefix_list_attribute_is_optional() -> None:
    """The load-bearing half.

    Attributes default to `optional: false`, unlike relationships. Four of the
    six zones supply no value, so a mandatory attribute makes them unloadable.
    """
    attribute = _field("SecurityZone", "attributes", "dc_advertised_prefix_list")
    assert attribute.get("optional") is True


def test_the_prefix_list_attribute_admits_it_is_a_soft_reference() -> None:
    """FR-013. Nothing enforces the name resolves, and an undocumented soft
    reference is how the next reader mistakes it for a validated one."""
    attribute = _field("SecurityZone", "attributes", "dc_advertised_prefix_list")
    description = (attribute.get("description") or "").lower()
    assert "soft reference" in description
    assert "enforce" in description


def test_the_advertising_zones_name_the_right_prefix_lists() -> None:
    zones = _zones()
    for zone, prefix_list in ADVERTISING_ZONES.items():
        assert zones[zone]["dc_advertised_prefix_list"] == prefix_list


def test_the_tenant_cloud_zones_advertise_nothing() -> None:
    """The negative half, and the one that matters.

    `acme-cloud` and `globex-cloud` look like candidates and are not. Their
    prefixes appear inside PL-DC-ADVERTISED, which is what the DC tells the WAN
    — they are the subject of that advertisement, not its destination.
    Recording it against them would tell a later generator to add branch VIPs to
    a tenant's list.
    """
    zones = _zones()
    for zone in SILENT_ZONES:
        assert "dc_advertised_prefix_list" not in zones[zone], (
            f"{zone} names a prefix list; the DC advertises nothing toward it"
        )


# ---------------------------------------------------------------------------
# US2 — the carrying device
# ---------------------------------------------------------------------------


def test_the_advertising_device_relationship_exists_and_is_singular() -> None:
    """Cardinality is the trap.

    Relationships default to `many`, the opposite way round from attributes,
    which default to mandatory. Omitting it here would let a zone claim several
    advertising devices and give the next cycle no single place to write.
    """
    relationship = _field("SecurityZone", "relationships", "advertising_device")
    assert relationship["cardinality"] == "one"
    assert relationship.get("optional") is True


def test_the_advertising_device_peers_the_fabric_switch_kind() -> None:
    """FR-061, and the most valuable assertion in this cycle.

    `DcimDevice` in this repository is the WAN's FRR routers. A relationship
    peered there passes `infrahubctl schema check`, loads cleanly, renders no
    error and resolves to nothing -- AGENTS.md says so outright: "A query naming
    `DcimDevice` does not see a fabric switch and reports nothing." The failure
    would surface a cycle later as "the generator never finds a device".

    `DcimGenericDevice` would resolve but admits the firewall and the compute
    nodes, neither of which carries `avd_custom_hostvars` -- so a zone could
    point somewhere the next cycle's write has nowhere to land.
    """
    relationship = _field("SecurityZone", "relationships", "advertising_device")
    assert relationship["peer"] == "DcimFabricSwitch"


def test_the_advertising_device_does_not_cascade_on_delete() -> None:
    """`on_delete` has one useful value, `cascade`, and it deletes the *peer*.

    Here that would mean deleting a switch deletes a security zone.
    `infrahubctl schema check` accepts the line without complaint, so nothing
    but this test stands between that and a silently destructive schema.
    """
    relationship = _field("SecurityZone", "relationships", "advertising_device")
    assert "on_delete" not in relationship


def test_both_sides_of_the_link_share_one_identifier() -> None:
    """Mismatched identifiers produce two independent relationships that each
    look correct and never connect."""
    zone_side = _field("SecurityZone", "relationships", "advertising_device")
    switch_side = _field("DcimFabricSwitch", "relationships", "advertised_zones")
    assert zone_side["identifier"] == IDENTIFIER
    assert switch_side["identifier"] == IDENTIFIER
    assert switch_side["peer"] == "SecurityZone"
    assert switch_side["cardinality"] == "many"


def test_only_the_advertising_zones_name_a_device() -> None:
    zones = _zones()
    for zone in ADVERTISING_ZONES:
        assert zones[zone]["advertising_device"] == BORDER_LEAF
    for zone in SILENT_ZONES:
        assert "advertising_device" not in zones[zone]


# ---------------------------------------------------------------------------
# US3 — the two halves are usable together
# ---------------------------------------------------------------------------


def test_no_zone_is_half_modelled() -> None:
    """The schema permits a zone with one half and not the other (G3 in the
    data model). This asserts the lab has none, which is the difference between
    a tolerated state and an accidental one.
    """
    for name, zone in _zones().items():
        has_list = "dc_advertised_prefix_list" in zone
        has_device = "advertising_device" in zone
        assert has_list == has_device, f"{name} carries one half of the policy and not the other"
