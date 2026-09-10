"""Contract tests for the NFD41 seed data.

These check the invariants that are easy to break from a distance and expensive
to discover: they surface as a generator failure deep inside a testcontainer run
rather than as a bad diff.
"""

from __future__ import annotations

import itertools
import operator
from pathlib import Path
from typing import Any

import pytest
import yaml

OBJECTS_DIR = Path(__file__).parent.parent.parent / "objects"

# The AS numbers the deployed NFD41 lab is running: 65100 on both spines and one
# per leaf rack. They are created as objects rather than pool-allocated.
NFD41_PINNED_ASNS = {65100, 65101, 65102, 65103}


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


def test_pinned_nfd41_asns_are_outside_every_pool() -> None:
    """The lab's AS numbers must not also be allocatable from a pool.

    They already exist as objects, so a pool that can hand them out will fail on
    its first allocation from that part of the range.
    """
    clashes = [
        f"{name} ({start}-{end}) can allocate {sorted(NFD41_PINNED_ASNS & set(range(start, end + 1)))}"
        for name, start, end in _asn_pools()
        if NFD41_PINNED_ASNS & set(range(start, end + 1))
    ]
    assert not clashes, "pools overlap the pinned NFD41 ASNs:\n  " + "\n  ".join(clashes)


def test_nfd41_pinned_asns_are_seeded() -> None:
    """Every AS number the fabric needs exists as a RoutingAsn object."""
    seeded = {entry["asn"] for _, entry in _load_objects("RoutingAsn")}
    assert seeded >= NFD41_PINNED_ASNS, f"missing RoutingAsn objects: {sorted(NFD41_PINNED_ASNS - seeded)}"


def test_nfd41_devices_are_named_for_the_deployed_lab() -> None:
    """The seven switches carry the hostnames containerlab gives them.

    The rendered configuration contains these names, and so does every
    neighbour's configuration, so a rename is a fabric-wide change.
    """
    devices = {entry["name"] for path, entry in _load_objects("DcimDevice") if path.name.startswith("26_nfd41")}
    assert devices == {
        "spine1",
        "spine2",
        "k8s-leaf1",
        "k8s-leaf2",
        "app-leaf1",
        "app-leaf2",
        "border-leaf1",
    }


@pytest.mark.parametrize(
    ("rack", "template", "expected"),
    [
        ("K8S_LEAFS", "k8s-leaf{index}", ["k8s-leaf1", "k8s-leaf2"]),
        ("APP_LEAFS", "app-leaf{index}", ["app-leaf1", "app-leaf2"]),
        ("BORDER_LEAFS", "border-leaf{index}", ["border-leaf1"]),
    ],
)
def test_rack_name_templates_produce_the_seeded_hostnames(rack: str, template: str, expected: list[str]) -> None:
    """A rack's name template must render exactly the hostnames that are seeded.

    If it does not, the rack generator creates a second set of devices under its
    own names and leaves the seeded ones uncabled -- which renders as a fabric
    of switches with no uplinks.
    """
    racks = {entry["name"]: entry for _, entry in _load_objects("LocationRack")}
    assert racks[rack]["device_name_template"] == template
    quantity = racks[rack]["device_designs"]["data"][0]["device_quantity"]
    assert [template.format(index=index) for index in range(1, quantity + 1)] == expected


def test_nfd41_mlag_domains_are_named_after_their_racks() -> None:
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
