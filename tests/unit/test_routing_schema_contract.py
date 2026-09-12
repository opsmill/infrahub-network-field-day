"""Contract tests for the device-level static route.

`schemas/routing/routing.yml` had no contract test until cycle 024, and the
gap mattered more than its size suggests. Ten `*_schema_contract.py` modules
exist and none read this file; the only module that mentioned
``RoutingStaticRoute`` mocks ``client.create``, so it asserts the shape of a
call and never touches the schema at all.

The consequence, measured rather than supposed: the full suite passed with
``RoutingStaticRoute.device`` peering the wrong kind. 998 green tests were not
evidence that the relationship was right, because nothing was looking.

WHAT THIS PINS, AND WHY EACH CLAUSE EARNS ITS PLACE:

* **The peer is the device GENERIC.** ``SecurityFirewall`` inherits
  ``DcimGenericDevice`` but not ``DcimDevice``, so a concrete peer silently
  excludes the perimeter firewall -- which is the whole reason cycle 023 could
  not render the firewall's ``routing-options`` stanza. Narrowing it back
  re-breaks that without any error.
* **Both ends share one identifier.** Mismatched identifiers do not fail. They
  produce two one-way relationships that each look correct in isolation, which
  is the specific trap the Infrahub identifier rule warns about.
* **`DcimDevice` must NOT re-declare `static_routes`.** It keeps the
  relationship by inheriting the generic. Declaring it in both places is two
  declarations of one identifier.
* **`RoutingVrfStaticRoute` is a different kind.** VRF-scoped, reached through
  ``WanSite``, and read by ``transforms/frr_config.py``. The two are easy to
  confuse and a tidy-up that merged them would break the WAN render.
* **The uniqueness constraint is load-bearing beyond display.** The
  `backfill-structured-config` generator saves with ``allow_upsert=True``,
  which resolves against ``[device, prefix__value, vrf__value]``. Changing it
  breaks generator idempotence, not a label.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parents[2]

ROUTING_SCHEMA = "schemas/routing/routing.yml"
VRF_SERVICES_SCHEMA = "schemas/routing/vrf_services.yml"

STATIC_ROUTE_IDENTIFIER = "device__static_route"

# The four that stay on DcimDevice. Nothing in this cycle asks a firewall to
# hold a BGP peer group, so only `static_routes` moves to the generic.
DCIM_DEVICE_ROUTING_RELATIONSHIPS = (
    "bgp_peer_groups",
    "bgp_neighbors",
    "prefix_lists",
    "route_maps",
)


def _load_yaml(path: str) -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _node(schema: dict[str, Any], namespace: str, name: str) -> dict[str, Any]:
    for node in schema.get("nodes", []):
        if node.get("namespace") == namespace and node.get("name") == name:
            return node
    raise AssertionError(f"{namespace}{name} node not found")


def _extension_node(schema: dict[str, Any], kind: str) -> dict[str, Any] | None:
    for node in schema.get("extensions", {}).get("nodes", []):
        if node.get("kind") == kind:
            return node
    return None


def _relationship(owner: dict[str, Any], name: str) -> dict[str, Any] | None:
    for relationship in owner.get("relationships", []):
        if relationship.get("name") == name:
            return relationship
    return None


# -- C1: the forward relationship ------------------------------------------


def test_static_route_device_peers_the_device_generic() -> None:
    """The clause the whole cycle turns on.

    ``DcimDevice`` would pass every other assertion in this file and still
    leave the firewall unable to own a route.
    """
    schema = _load_yaml(ROUTING_SCHEMA)
    device = _relationship(_node(schema, "Routing", "StaticRoute"), "device")

    assert device is not None, "RoutingStaticRoute must declare a `device` relationship"
    assert device["peer"] == "DcimGenericDevice", (
        "peer must be the generic: SecurityFirewall inherits DcimGenericDevice "
        "but not DcimDevice, so a concrete peer excludes the perimeter firewall"
    )


def test_static_route_device_stays_mandatory_and_singular() -> None:
    """A route with no device, or with several, is not a route."""
    schema = _load_yaml(ROUTING_SCHEMA)
    device = _relationship(_node(schema, "Routing", "StaticRoute"), "device")
    assert device is not None

    assert device["kind"] == "Attribute"
    assert device["cardinality"] == "one"
    assert device["optional"] is False
    assert device["identifier"] == STATIC_ROUTE_IDENTIFIER


# -- C2, C3: the reverse relationship and the shared identifier -------------


def test_device_generic_declares_static_routes() -> None:
    schema = _load_yaml(ROUTING_SCHEMA)
    generic = _extension_node(schema, "DcimGenericDevice")

    assert generic is not None, "the reverse side must live on DcimGenericDevice, matching the forward peer"
    static_routes = _relationship(generic, "static_routes")
    assert static_routes is not None

    assert static_routes["peer"] == "RoutingStaticRoute"
    assert static_routes["kind"] == "Generic"
    assert static_routes["cardinality"] == "many"
    assert static_routes["optional"] is True


def test_both_ends_of_the_relationship_share_one_identifier() -> None:
    """Stated separately because the failure is silent.

    Mismatched identifiers do not raise. They create two one-way
    relationships, each of which looks right on its own.
    """
    schema = _load_yaml(ROUTING_SCHEMA)
    forward = _relationship(_node(schema, "Routing", "StaticRoute"), "device")
    generic = _extension_node(schema, "DcimGenericDevice")
    assert forward is not None and generic is not None
    reverse = _relationship(generic, "static_routes")
    assert reverse is not None

    assert forward["identifier"] == reverse["identifier"] == STATIC_ROUTE_IDENTIFIER


# -- C4: DcimDevice keeps the relationship by inheritance, not declaration --


def test_dcim_device_does_not_also_declare_static_routes() -> None:
    schema = _load_yaml(ROUTING_SCHEMA)
    dcim_device = _extension_node(schema, "DcimDevice")
    assert dcim_device is not None

    assert _relationship(dcim_device, "static_routes") is None, (
        "DcimDevice inherits static_routes from DcimGenericDevice; declaring it "
        "here as well is two declarations of one identifier"
    )


def test_the_move_did_not_take_its_neighbours_with_it() -> None:
    """Only `static_routes` moves. The other four stay."""
    schema = _load_yaml(ROUTING_SCHEMA)
    dcim_device = _extension_node(schema, "DcimDevice")
    assert dcim_device is not None

    for name in DCIM_DEVICE_ROUTING_RELATIONSHIPS:
        assert _relationship(dcim_device, name) is not None, f"{name} belongs on DcimDevice and must not have moved"


def test_only_the_static_route_peers_the_device_generic() -> None:
    """The blast-radius clause, and it exists because the mistake was made.

    While implementing cycle 024 a careless ``sed`` widened every
    ``peer: DcimDevice`` in this file, flipping five unrelated relationships
    along with the intended one. Nothing objected: ``infrahubctl schema
    check`` reported all 38 files valid, and the unit suite reported only the
    failures that were already expected.

    Widening a peer is not a neutral act -- it changes which kinds may be
    referenced -- so each of these five is pinned to the concrete kind until
    some cycle argues otherwise for that specific relationship.
    """
    schema = _load_yaml(ROUTING_SCHEMA)

    peers = {
        (node["namespace"] + node["name"], relationship["name"]): relationship["peer"]
        for node in schema.get("nodes", [])
        for relationship in node.get("relationships", [])
        if relationship.get("peer", "").startswith("Dcim")
    }

    assert peers == {
        ("RoutingBGPPeerGroup", "device"): "DcimDevice",
        ("RoutingBGPNeighbor", "device"): "DcimDevice",
        ("RoutingAsn", "devices"): "DcimDevice",
        ("RoutingPrefixList", "device"): "DcimDevice",
        ("RoutingRouteMap", "device"): "DcimDevice",
        ("RoutingStaticRoute", "device"): "DcimGenericDevice",
    }


# -- C5: the VRF-scoped kind is a different kind ---------------------------


def test_vrf_static_route_is_untouched() -> None:
    """`frr_config` reads this one through WanSite. They are not the same kind."""
    schema = _load_yaml(VRF_SERVICES_SCHEMA)
    node = _node(schema, "Routing", "VrfStaticRoute")

    vrf = _relationship(node, "vrf")
    assert vrf is not None
    assert vrf["identifier"] == "vrf__static_routes"

    devices = _relationship(node, "devices")
    assert devices is not None
    assert devices["identifier"] == "device__vrf_static_routes", (
        f"the VRF-scoped kind keeps its own identifier, distinct from {STATIC_ROUTE_IDENTIFIER}"
    )


# -- C6: display and uniqueness survive the widening -----------------------


def test_display_and_uniqueness_are_unchanged() -> None:
    """`human_friendly_id` reads through the relationship to `name`.

    ``DcimGenericDevice`` carries `name`, so the HFID keeps resolving. The
    uniqueness constraint matters beyond display: the backfill generator's
    ``allow_upsert=True`` resolves against it.
    """
    schema = _load_yaml(ROUTING_SCHEMA)
    node = _node(schema, "Routing", "StaticRoute")

    assert node["human_friendly_id"] == ["device__name__value", "prefix__value"]
    assert node["display_label"] == "prefix__value"
    assert node["uniqueness_constraints"] == [["device", "prefix__value", "vrf__value"]]


def test_route_name_exists_to_carry_the_devices_own_comment() -> None:
    """Cycle 025 needs somewhere to put each route's ``/* ... */`` text.

    Pinned here so the attribute is not tidied away before the cycle that
    reads it lands.
    """
    schema = _load_yaml(ROUTING_SCHEMA)
    node = _node(schema, "Routing", "StaticRoute")

    route_name = next((a for a in node["attributes"] if a["name"] == "route_name"), None)
    assert route_name is not None
    assert route_name["kind"] == "Text"
    assert route_name["optional"] is True
