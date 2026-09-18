"""The perimeter firewall's static routes, checked against three sources.

Eight routes transcribed from ``../lab/configs/fw/vsrx/junos.conf`` onto
``fw1``. Cycle 024 widened ``RoutingStaticRoute.device`` so a
``SecurityFirewall`` could own one; cycle 025 put the device's real forwarding
decisions in the graph; cycle 026 renders them.

THREE SOURCES, AND WHY IT IS THREE RATHER THAN ONE:

* the device file -- exact transcription, checked BOTH WAYS
* ``fw1``'s interface addresses -- every next hop must be on a connected
  subnet
* the security address book -- every destination must be something the
  firewall has policy for

The second one is the one that earns its place. **A comparison against the
device file cannot catch a typo in the device file**, because the device file
is what it compares to. Interface addresses are an independent witness: a next
hop off a connected subnet is accepted by Junos and then silently never
installs.

TWO CLAUSES THAT EXIST BECAUSE OF EARLIER MISTAKES:

* ``test_the_oracle_parser_reads_all_eight`` -- the stanza is column-aligned
  by hand with variable-width runs of spaces, and a single-space assumption
  reads six of eight lines. The equivalent bug overstated cycle 023's gap by
  six corrections and was believed for a while; the parser was the thing that
  was wrong.
* the comparison runs in BOTH directions, as separate assertions. Cycle 023
  deleted fourteen lines of correct data after a one-way read concluded
  something was absent when the search was at fault.

WHAT IS DELIBERATELY NOT ASSERTED: the converse of the address-book check.
Five book entries correctly have no route of their own -- ``acme-hq``,
``acme-dr`` and ``globex-hq`` sit inside ``10.60.0.0/16``; ``access-portal``
(``10.112.240.33/32``) sits inside ``10.112.0.0/16``; and ``fabric-infra`` is
never a destination at all, appearing six times as a rule ``source_address``
in the anti-spoofing rules. "Every address-book prefix has a route" would fail
on all five.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[2]

ROUTES = REPO_ROOT / "objects/32b_otternet_fw_static_routes.yml"
SECURITY = REPO_ROOT / "objects/32_otternet_security.yml"
ORACLE = Path("../lab/configs/fw/vsrx/junos.conf")

FIREWALL = "fw1"
EXPECTED_ROUTE_COUNT = 8

# Only these four fields. `vrf` is absent on purpose: the schema default
# "default" IS the master routing instance, which is where these routes live,
# and the live schema carries a `[device, prefix]` uniqueness constraint
# derived from the HFID in addition to the declared one that names `vrf`.
# `gateway`, `interface`, `distance` and `tag` are unset because the device
# sets none of them -- inventing one would make cycle 026 render configuration
# the firewall does not have.
ALLOWED_FIELDS = {"prefix", "next_hop", "route_name", "device"}

# next_hop -> the fw1 interface whose /30 it falls in.
EXPECTED_NEXT_HOP_INTERFACES = {
    "10.250.110.1": "ge-0/0/0",
    "10.250.210.1": "ge-0/0/1",
    "10.250.150.1": "ge-0/0/2",
    "10.250.170.1": "ge-0/0/3",
    "10.250.10.1": "ge-0/0/4",
    "10.250.20.1": "ge-0/0/5",
}

EXPECTED_ADDRESS_BOOK_NAMES = {
    "k8s-nodes",
    "k8s-pods",
    "k8s-services",
    "app-hosts",
    "wan-customers",
    "branch-users",
    "acme-cloud",
    "globex-cloud",
}


# -- sources ---------------------------------------------------------------


def _oracle_lines() -> list[str]:
    if not ORACLE.is_file():
        pytest.skip("lab repo not checked out alongside this one")
    return ORACLE.read_text(encoding="utf-8").splitlines()


def _parse_oracle() -> dict[str, tuple[str, str]]:
    """The device file's `routing-options { static { ... } }` block.

    The line shape is NOT fixed-width. Junos was hand-aligned here, so the run
    of spaces between the prefix and ``next-hop``, and between the ``;`` and
    the comment, both vary:

        route 10.110.0.0/24 next-hop 10.250.110.1;   /* k8s nodes */
        route 10.60.0.0/16  next-hop 10.250.150.1;   /* WAN customer supernet */
        route 10.220.10.0/24 next-hop 10.250.10.1;  /* acme cloud instances */

    ``\\s+`` throughout, never a literal single space.
    """
    lines = _oracle_lines()
    start = next(i for i, line in enumerate(lines) if line.startswith("routing-options {"))
    end = next(i for i, line in enumerate(lines[start:], start) if line == "}")

    pattern = re.compile(r"^\s*route\s+(\S+)\s+next-hop\s+(\S+);\s*/\*\s*(.*?)\s*\*/\s*$")
    routes: dict[str, tuple[str, str]] = {}
    for line in lines[start : end + 1]:
        match = pattern.match(line)
        if match:
            routes[match.group(1)] = (match.group(2), match.group(3))
    return routes


def _route_file() -> dict[str, Any]:
    return yaml.safe_load(ROUTES.read_text(encoding="utf-8"))


def _route_entries() -> list[dict[str, Any]]:
    return list(_route_file()["spec"]["data"])


def _routes_by_prefix() -> dict[str, tuple[str, str]]:
    return {e["prefix"]: (e["next_hop"], e["route_name"]) for e in _route_entries()}


def _security_docs() -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(SECURITY.read_text(encoding="utf-8")) if d]


def _firewall_interface_networks() -> dict[str, ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """`fw1`'s own ports and the networks they are numbered on."""
    networks = {}
    for doc in _security_docs():
        if doc.get("spec", {}).get("kind") != "SecurityFirewallInterface":
            continue
        for interface in doc["spec"]["data"]:
            for address in interface.get("ip_addresses", {}).get("data", []):
                networks[interface["name"]] = ipaddress.ip_interface(address["address"]).network
    return networks


def _address_book() -> dict[str, str]:
    """Prefix -> address name, for every book entry carrying an `ip_prefix`."""
    book = {}
    for doc in _security_docs():
        for item in doc.get("spec", {}).get("data", []):
            if isinstance(item, dict) and "ip_prefix" in item:
                book[item["ip_prefix"][0]] = item["name"]
    return book


# -- C4: the parser, pinned before anything relies on it -------------------


def test_the_oracle_parser_reads_all_eight() -> None:
    """The clause that exists because this parser is what went wrong before.

    A `route (\\S+) next-hop` pattern assuming single spaces reads six of the
    eight lines and silently drops the two whose prefix is shorter.
    """
    assert len(_parse_oracle()) == EXPECTED_ROUTE_COUNT


def test_the_oracle_parser_handles_the_variable_column_alignment() -> None:
    """Specifically the two lines a naive parser drops.

    `10.60.0.0/16` and `10.70.0.0/24` are padded with two spaces before
    `next-hop` rather than one, to hold the column.
    """
    parsed = _parse_oracle()
    assert parsed["10.60.0.0/16"] == ("10.250.150.1", "WAN customer supernet")
    assert parsed["10.70.0.0/24"] == ("10.250.170.1", "branch office LAN")


# -- C1, C2: file shape ----------------------------------------------------


def test_the_file_is_a_well_formed_object_document() -> None:
    document = _route_file()
    assert document["apiVersion"] == "infrahub.app/v1"
    assert document["kind"] == "Object"
    assert document["spec"]["kind"] == "RoutingStaticRoute"
    assert isinstance(document["spec"]["data"], list)


def test_there_are_eight_routes_and_all_are_on_the_firewall() -> None:
    entries = _route_entries()
    assert len(entries) == EXPECTED_ROUTE_COUNT
    assert {e["device"] for e in entries} == {FIREWALL}


def test_the_device_reference_is_a_plain_scalar() -> None:
    """Pinned so a well-meaning "fix" to an inline block fails loudly.

    ``device`` peers ``DcimGenericDevice``, and the reflex for a generic peer
    is an inline ``kind:``/``data:`` block -- which is what cycle 023 needed
    for the polymorphic address book. It is unnecessary here because
    ``DcimGenericDevice`` defines ``human_friendly_id: [name__value]``, so the
    scalar resolves. Verified by loading, not by reading.
    """
    for entry in _route_entries():
        assert isinstance(entry["device"], str), (
            "device must stay a scalar HFID; DcimGenericDevice has an HFID so no inline concrete-kind block is needed"
        )


# -- C3: the comparison, both ways, as separate assertions -----------------


def test_every_route_in_the_device_file_is_in_the_object_file() -> None:
    missing = sorted(set(_parse_oracle()) - set(_routes_by_prefix()))
    assert not missing, f"the device file has routes the model does not: {missing}"


def test_every_route_in_the_object_file_is_in_the_device_file() -> None:
    """The direction that catches an invented route.

    Stated separately from its opposite because cycle 023 ran the check one
    way, concluded data was absent when the search was at fault, and deleted
    fourteen correct lines.
    """
    invented = sorted(set(_routes_by_prefix()) - set(_parse_oracle()))
    assert not invented, f"the model has routes the device does not: {invented}"


def test_next_hop_and_comment_match_the_device_file_exactly() -> None:
    oracle = _parse_oracle()
    routes = _routes_by_prefix()
    mismatched = {p: (oracle[p], routes[p]) for p in oracle if p in routes and oracle[p] != routes[p]}
    assert not mismatched, f"value mismatches (device, model): {mismatched}"


# -- C5: only the intended fields ------------------------------------------


def test_no_route_sets_a_field_the_device_does_not() -> None:
    """`vrf`, `gateway`, `interface`, `distance` and `tag` stay unset.

    An invented `distance` or `interface` is not a transcription: cycle 026
    would render it as configuration the firewall does not have.
    """
    for entry in _route_entries():
        extra = set(entry) - ALLOWED_FIELDS
        assert not extra, f"{entry['prefix']}: unexpected field(s) {sorted(extra)}"


# -- C6: the independent witness -------------------------------------------


def test_every_next_hop_is_on_a_connected_subnet() -> None:
    """The check the device file cannot provide.

    Comparing the routes to `junos.conf` cannot catch a typo in `junos.conf`.
    `fw1`'s interface addresses are a separate source, so a next hop that is
    not on a connected /30 fails here and nowhere else. On the device such a
    route is accepted and never installs.
    """
    networks = _firewall_interface_networks()
    assert networks, "no fw1 interface addresses found; the source moved"

    for prefix, (next_hop, _) in sorted(_routes_by_prefix().items()):
        landed = [name for name, network in networks.items() if ipaddress.ip_address(next_hop) in network]
        assert landed, f"{prefix}: next hop {next_hop} is on no connected subnet of {FIREWALL}"
        assert landed == [EXPECTED_NEXT_HOP_INTERFACES[next_hop]]


# -- C7: destinations are things the firewall has policy for ---------------


def test_every_destination_is_an_address_book_prefix() -> None:
    """The firewall routes to precisely the prefixes it filters.

    The CONVERSE is false and is deliberately not asserted -- see the module
    docstring. Five book entries correctly have no route.
    """
    book = _address_book()
    named = {book[p] for p in _routes_by_prefix() if p in book}
    unknown = sorted(p for p in _routes_by_prefix() if p not in book)

    assert not unknown, f"destinations with no address-book entry: {unknown}"
    assert named == EXPECTED_ADDRESS_BOOK_NAMES


def test_the_address_book_entries_without_a_route_are_the_expected_five() -> None:
    """Pinned so the converse is never quietly added.

    Three sit inside the `10.60.0.0/16` route, one host sits inside the
    `10.112.0.0/16` route, and `fabric-infra` is only ever a rule source.
    """
    unrouted = sorted(set(_address_book()) - set(_routes_by_prefix()))
    assert unrouted == [
        "10.41.0.0/16",  # fabric-infra -- source of the anti-spoofing rules, never a destination
        "10.60.10.0/24",  # acme-hq     -- inside the wan-customers route
        "10.60.11.0/24",  # acme-dr     -- inside the wan-customers route
        "10.60.20.0/24",  # globex-hq   -- inside the wan-customers route
    ]


# -- C8: load order --------------------------------------------------------


def test_the_file_loads_after_the_one_that_defines_the_firewall() -> None:
    """`fw1` is created in 31_; the routes reference it, so they must follow."""
    devices = "31_otternet_offfabric_devices.yml"
    assert (REPO_ROOT / "objects" / devices).is_file()
    assert ROUTES.name > devices
