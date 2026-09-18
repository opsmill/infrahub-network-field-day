"""Contract tests for the OTTERNET seed data.

These check the invariants that are easy to break from a distance and expensive
to discover: they surface as a generator failure deep inside a testcontainer run
rather than as a bad diff.
"""

from __future__ import annotations

import itertools
import operator
from pathlib import Path
from typing import Any

import yaml

OBJECTS_DIR = Path(__file__).parent.parent.parent / "objects"

# The AS numbers the deployed OTTERNET lab is running: 65100 on both spines and one
# per leaf rack. They are created as objects rather than pool-allocated.
OTTERNET_PINNED_ASNS = {65100, 65101, 65102, 65103}


def _load_objects(kind: str) -> list[tuple[Path, dict[str, Any]]]:
    """Every seed object of ``kind``, with the file it came from."""
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(OBJECTS_DIR.glob("*.yml")):
        for doc in yaml.safe_load_all(path.read_text()):
            if doc and doc.get("spec", {}).get("kind") == kind:
                found.extend((path, entry) for entry in doc["spec"]["data"])
    return found


def _asn_pools() -> list[tuple[str, int, int]]:
    return [
        (entry["name"], entry["start_range"], entry["end_range"])
        for _, entry in _load_objects("CoreNumberPool")
        if entry.get("node") == "RoutingAsn"
    ]


def test_asn_pool_ranges_are_disjoint() -> None:
    """No two fabrics may draw AS numbers from overlapping ranges.

    ``RoutingAsn.asn`` is unique instance-wide, so two pools that overlap work
    right up until both fabrics generate -- then whichever runs second trips the
    uniqueness constraint and its whole pod generator fails.
    """
    pools = sorted(_asn_pools(), key=operator.itemgetter(1))
    overlaps = [
        f"{earlier[0]} ({earlier[1]}-{earlier[2]}) overlaps {later[0]} ({later[1]}-{later[2]})"
        for earlier, later in itertools.pairwise(pools)
        if later[1] <= earlier[2]
    ]
    assert not overlaps, "overlapping ASN pools:\n  " + "\n  ".join(overlaps)


def test_pinned_otternet_asns_are_outside_every_pool() -> None:
    """The lab's AS numbers must not also be allocatable from a pool.

    They already exist as objects, so a pool that can hand them out will fail on
    its first allocation from that part of the range.
    """
    clashes = [
        f"{name} ({start}-{end}) can allocate {sorted(OTTERNET_PINNED_ASNS & set(range(start, end + 1)))}"
        for name, start, end in _asn_pools()
        if OTTERNET_PINNED_ASNS & set(range(start, end + 1))
    ]
    assert not clashes, "pools overlap the pinned OTTERNET ASNs:\n  " + "\n  ".join(clashes)


def test_otternet_pinned_asns_are_seeded() -> None:
    """Every AS number the fabric needs exists as a RoutingAsn object."""
    seeded = {entry["asn"] for _, entry in _load_objects("RoutingAsn")}
    assert seeded >= OTTERNET_PINNED_ASNS, f"missing RoutingAsn objects: {sorted(OTTERNET_PINNED_ASNS - seeded)}"


# How the pod and rack generators name what they create. Mirrored from
# generators/generate_pod.py and generators/generate_rack.py.
SPINE_NAME = "spine-{pod}-{index}"
LEAF_NAME = "leaf-{pod}-{rack_index}-{index}"


def _pod() -> dict[str, Any]:
    fabric = next(entry for _, entry in _load_objects("NetworkFabric") if entry["name"] == "OTTERNET_FABRIC")
    return fabric["children"]["data"][0]


def test_seeded_switch_names_match_what_the_generators_produce() -> None:
    """The pinned devices must be named exactly as the generators would name them.

    The pod and rack generators upsert devices *by name*. A seeded name that does
    not match leaves these objects orphaned and a second set of devices created
    alongside them -- which renders as a fabric of switches with no uplinks, plus
    a duplicate set with no pinned identity.
    """
    pod = _pod()["name"]
    expected = {SPINE_NAME.format(pod=pod, index=index) for index in (1, 2)}
    for _, rack in _load_objects("LocationRack"):
        quantity = rack["device_designs"]["data"][0]["device_quantity"]
        expected |= {
            LEAF_NAME.format(pod=pod, rack_index=rack["index"], index=index) for index in range(1, quantity + 1)
        }

    seeded = {entry["name"] for path, entry in _load_objects("DcimFabricSwitch") if path.name.startswith("26_otternet")}
    assert seeded == expected


def test_no_rack_or_pod_overrides_the_default_naming() -> None:
    """Naming is left to the generators; the lab is deployed to match.

    A `device_name_template` here would have to agree with every seeded device
    name, so the two could drift apart silently. Leaving it unset removes that
    failure mode.
    """
    overrides = [
        entry["name"]
        for entry in (*(rack for _, rack in _load_objects("LocationRack")), _pod())
        if entry.get("device_name_template")
    ]
    assert not overrides, f"unexpected device_name_template on: {sorted(overrides)}"


def test_spine_uplink_ports_follow_rack_order() -> None:
    """Rack index decides which spine port a rack's leaves land on.

    The generators allocate spine downlinks in rack order, so the indices fix the
    point-to-point addressing and every spine interface description. Reordering
    the racks rewrites the spines' configuration.
    """
    racks = sorted((entry for _, entry in _load_objects("LocationRack")), key=operator.itemgetter("index"))
    assert [rack["name"] for rack in racks] == ["K8S_LEAFS", "APP_LEAFS", "BORDER_LEAFS"]
    assert [rack["index"] for rack in racks] == [1, 2, 3]


def test_otternet_mlag_domains_are_named_after_their_racks() -> None:
    """The MLAG domain ID is the rack name, and reaches the switch as `domain-id`.

    The rack generator derives the domain ID from the rack name, and the hostvar
    generator uses it as the AVD node-group name; the deployed switches are
    configured with `mlag configuration domain-id K8S_LEAFS`.
    """
    domains = {entry["domain_id"] for _, entry in _load_objects("MlagDomain")}
    racks = {entry["name"] for _, entry in _load_objects("LocationRack") if entry.get("mlag") is True}
    assert racks >= domains, f"MLAG domains with no matching rack: {sorted(domains - racks)}"
    assert domains >= {"K8S_LEAFS", "APP_LEAFS"}


def test_new_object_kinds_are_reachable_from_the_ui_menu() -> None:
    """The VRF services and per-node SVI addresses appear in the navigation.

    They carry the fabric's service-insertion design and its workload BGP
    policy, so they are exactly the objects someone reviewing the fabric needs
    to find. A kind with no menu entry is only reachable by GraphQL.
    """
    menu = yaml.safe_load((OBJECTS_DIR.parent / "menus" / "menu.yml").read_text())

    def kinds(items: list[dict[str, Any]]) -> set[str]:
        found: set[str] = set()
        for item in items:
            if item.get("kind"):
                found.add(item["kind"])
            found |= kinds(item.get("children", {}).get("data", []))
        return found

    menu_kinds = kinds(menu["spec"]["data"])
    expected = {
        "RoutingVrfStaticRoute",
        "RoutingVrfBgpPeer",
        "RoutingVrfL3Interface",
        "EvpnSviNode",
    }
    assert menu_kinds >= expected, f"kinds missing from the menu: {sorted(expected - menu_kinds)}"
