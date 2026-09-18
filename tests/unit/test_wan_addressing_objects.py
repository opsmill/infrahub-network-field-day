"""Seed-data tests for the WAN's addressing (objects/31a, and the links in 33).

The object files are a hand transcription of `../lab/wan/tenants.yml`, so the
assertions worth having are the ones that catch a slip against it. They compare
**both directions**: an address invented here fails as loudly as one omitted,
which a one-directional check would miss entirely.

Three guards are not about transcription at all:

* no endpoint description may contain an address. That prose is the debt cycle
  021 repays, and re-introducing it would restore two sources of truth for one
  address.
* every inline ``data:`` block under a cardinality-one relationship must be a
  mapping. A list raises ``AttributeError: 'list' object has no attribute
  'items'`` from inside the SDK, naming neither file nor field, so it is worth
  catching in pytest instead.
* ``31a`` must sort between ``31`` and ``33``. Interfaces hang off the devices
  in 31 and are named by the circuits in 33, so a rename that breaks the
  ordering breaks the load.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ADDRESSING_FILE = Path("objects/31a_otternet_wan_addressing.yml")
WAN_FILE = Path("objects/33_otternet_wan.yml")
SERVICES_FILE = Path("objects/37_otternet_wan_services.yml")
LAB_TENANTS = Path("../lab/wan/tenants.yml")

IPV4 = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

# The branch router's switch ports. Bridged into br-branch so the branch
# desktop, host and Guacamole gateway can reach each other; they carry no
# addresses and appear in no FRR config. Spec assumption 3.
BRANCH_ACCESS_PORTS = {"eth2", "eth3", "eth4"}


def _docs(path: Path) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _data(path: Path, kind: str) -> list[dict[str, Any]]:
    for doc in _docs(path):
        if doc.get("spec", {}).get("kind") == kind:
            return doc["spec"]["data"]
    pytest.fail(f"no {kind} block in {path}")


def _lab() -> dict[str, Any]:
    if not LAB_TENANTS.is_file():
        pytest.skip("lab repo not checked out alongside this one")
    return yaml.safe_load(LAB_TENANTS.read_text(encoding="utf-8"))


def _lab_interfaces() -> set[tuple[str, str]]:
    """Every (device, interface) the lab expects, minus the bridged ports."""
    lab = _lab()
    isp, branch = lab["isp"], lab["branch"]
    found: set[tuple[str, str]] = set()

    for key in ("edge", "core"):
        entry = isp[key]
        node = entry["node"]
        found.add((node, "lo"))
        found.add((node, entry["core"]["interface"]))
        if "dc" in entry:
            found.add((node, entry["dc"]["interface"]))

    peering = isp["internet"]["peering"]
    router = isp["internet"]["router"]
    found.add((peering["node"], peering["interface"]))
    found.add((router, peering["router_interface"]))
    found.add((router, isp["internet"]["lan_interface"]))

    for tenant in lab["tenants"]:
        for site in tenant["sites"]:
            found.add((site["pe"]["node"], site["pe"]["interface"]))
            found.add((site["ce"]["node"], site["ce"]["wan_interface"]))
            found.add((site["ce"]["node"], site["ce"]["lan_interface"]))

    router_entry = branch["router"]
    node = router_entry["node"]
    found.add((node, "lo"))
    found.add((node, router_entry["dc_interface"]))
    found.add((node, router_entry["lan_bridge"]))
    return found


def _lab_addresses() -> set[str]:
    lab = _lab()
    isp, branch = lab["isp"], lab["branch"]
    found: set[str] = set()

    for key in ("edge", "core"):
        entry = isp[key]
        found.add(f"{entry['loopback']}/32")
        found.add(entry["core"]["address"])
        if "dc" in entry:
            found.add(entry["dc"]["address"])

    peering = isp["internet"]["peering"]
    found.add(peering["address"])
    found.add(f"{peering['peer']}/30")
    found.add(isp["internet"]["lan_address"])

    for tenant in lab["tenants"]:
        for site in tenant["sites"]:
            found.add(site["pe"]["address"])
            found.add(site["ce"]["wan_address"])
            found.add(site["ce"]["lan_address"])

    found.add(f"{branch['loopback']}/32")
    found.add(branch["router"]["dc_address"])
    found.add(branch["router"]["lan_address"])
    return found


def _seeded_interfaces() -> set[tuple[str, str]]:
    found = set()
    for kind in ("InterfacePhysical", "InterfaceVirtual"):
        found |= {(i["device"], i["name"]) for i in _data(ADDRESSING_FILE, kind)}
    return found


# ---------------------------------------------------------------------------
# Transcription parity -- both directions
# ---------------------------------------------------------------------------


def test_every_seeded_interface_exists_in_the_lab() -> None:
    """Nothing is invented."""
    assert _seeded_interfaces() <= _lab_interfaces()


def test_every_lab_interface_is_seeded() -> None:
    """Nothing is missed, except the bridged branch ports (assumption 3)."""
    missing = _lab_interfaces() - _seeded_interfaces()

    assert missing == set(), f"interfaces in the lab but not seeded: {sorted(missing)}"


def test_the_bridged_branch_ports_are_deliberately_absent() -> None:
    """They carry no address and appear in no FRR config -- plumbing, not intent."""
    seeded = _seeded_interfaces()

    assert not {("branch-rtr", port) for port in BRANCH_ACCESS_PORTS} & seeded


def test_address_transcription_matches_the_lab_in_both_directions() -> None:
    seeded = {a["address"] for a in _data(ADDRESSING_FILE, "IpamIPAddress")}

    assert seeded == _lab_addresses()


def test_every_address_sits_on_a_seeded_interface() -> None:
    """An address whose interface does not exist would fail at load time."""
    interfaces = _seeded_interfaces()

    for entry in _data(ADDRESSING_FILE, "IpamIPAddress"):
        inline = entry["interface"]["data"]
        assert (inline["device"], inline["name"]) in interfaces


def test_interfaces_carry_the_labs_mtu() -> None:
    lab_mtu = _lab()["mtu"]

    for entry in _data(ADDRESSING_FILE, "InterfacePhysical"):
        assert entry["mtu"] == lab_mtu


def test_loopbacks_are_virtual_and_flagged() -> None:
    """So an announced /32 is identifiable without inferring it from a name."""
    loopbacks = _data(ADDRESSING_FILE, "InterfaceVirtual")

    assert {entry["device"] for entry in loopbacks} == {"isp-pe1", "isp-pe2", "branch-rtr"}
    assert all(entry["role"] == "loopback" for entry in loopbacks)


def test_the_static_sites_ce_still_has_interfaces() -> None:
    """cust-acme-dr-ce speaks no protocol, but its eth1 is the static route's next hop."""
    seeded = _seeded_interfaces()

    assert ("cust-acme-dr-ce", "eth1") in seeded
    assert ("cust-acme-dr-ce", "eth2") in seeded


# ---------------------------------------------------------------------------
# The debt this cycle repays
# ---------------------------------------------------------------------------


def test_no_endpoint_description_restates_an_address() -> None:
    """The regression guard for cycle 010's SC-008.

    Relationship references to IpamPrefix and IpamIPAddress are fine -- those
    are objects. What may never come back is an address written as prose inside
    a sentence, which is how objects/33 used to record both ends of a circuit.
    """
    offenders = []
    for circuit in _data(WAN_FILE, "DcimCircuit"):
        for endpoint in circuit.get("endpoints", {}).get("data", []):
            description = endpoint.get("description", "")
            if IPV4.search(description):
                offenders.append((endpoint.get("name"), description))

    assert offenders == [], f"addresses restated as prose: {offenders}"


def test_every_circuit_endpoint_names_its_interface() -> None:
    endpoints = [
        endpoint
        for circuit in _data(WAN_FILE, "DcimCircuit")
        for endpoint in circuit.get("endpoints", {}).get("data", [])
    ]

    assert len(endpoints) == 8
    for endpoint in endpoints:
        device, name = endpoint["interface"]
        assert (device, name) in _seeded_interfaces()


# ---------------------------------------------------------------------------
# Guards on the load itself
# ---------------------------------------------------------------------------


def _inline_blocks(node: Any) -> list[dict[str, Any]]:
    """Every inline relationship block -- a mapping carrying `kind` and `data`."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if "kind" in node and "data" in node:
            found.append(node)
        for value in node.values():
            found += _inline_blocks(value)
    elif isinstance(node, list):
        for item in node:
            found += _inline_blocks(item)
    return found


@pytest.mark.parametrize("path", [ADDRESSING_FILE, WAN_FILE, SERVICES_FILE])
def test_cardinality_one_inline_blocks_are_mappings(path: Path) -> None:
    """A list here raises AttributeError from inside the SDK, naming nothing.

    Only the top-level `spec` block takes a list of objects; an inline block for
    a cardinality-one relationship takes a mapping. The distinction is invisible
    in the YAML until the load fails, so it is asserted here instead.
    """
    for doc in _docs(path):
        spec = doc.get("spec", {})
        for block in _inline_blocks(spec.get("data", [])):
            if block["kind"] in {"LocationSite", "InterfacePhysical", "InterfaceVirtual"}:
                assert isinstance(block["data"], dict), (
                    f"{path}: inline {block['kind']} block uses a list; cardinality-one relationships take a mapping"
                )


def test_the_addressing_file_sorts_between_the_devices_and_the_circuits() -> None:
    """Interfaces hang off file 31's devices and are named by file 33's circuits."""
    names = sorted(
        [
            "31_otternet_offfabric_devices.yml",
            ADDRESSING_FILE.name,
            "32_otternet_security.yml",
            WAN_FILE.name,
        ]
    )

    assert names.index(ADDRESSING_FILE.name) == 1


# ---------------------------------------------------------------------------
# ASNs, sessions and the static route
# ---------------------------------------------------------------------------


def _lab_asns() -> dict[int, set[str]]:
    lab = _lab()
    isp, branch = lab["isp"], lab["branch"]
    found: dict[int, set[str]] = {
        isp["asn"]: {isp["edge"]["node"], isp["core"]["node"]},
        isp["internet"]["asn"]: {isp["internet"]["router"]},
        branch["asn"]: {branch["router"]["node"]},
    }
    for tenant in lab["tenants"]:
        for site in tenant["sites"]:
            if site["kind"] == "bgp":
                found.setdefault(site["asn"], set()).add(site["ce"]["node"])
    return found


def test_asn_transcription_matches_the_lab() -> None:
    seeded = {entry["asn"]: set(entry["devices"]) for entry in _data(ADDRESSING_FILE, "RoutingAsn")}

    assert seeded == _lab_asns()


def test_both_ends_of_every_session_are_seeded() -> None:
    """Ten neighbours: five sessions, each two device-scoped objects."""
    seeded = {(entry["device"], entry["peer_address"]) for entry in _data(ADDRESSING_FILE, "RoutingBGPNeighbor")}

    assert len(seeded) == 10
    for near, far in (
        (("isp-pe1", "10.50.255.2"), ("isp-pe2", "10.50.255.1")),
        (("isp-pe1", "10.51.10.2"), ("cust-acme-ce", "10.51.10.1")),
        (("isp-pe1", "10.51.20.2"), ("cust-globex-ce", "10.51.20.1")),
        (("isp-pe2", "10.52.0.2"), ("internet-rtr", "10.52.0.1")),
    ):
        assert near in seeded and far in seeded


def test_remote_as_is_written_as_text() -> None:
    """The attribute is Text; an int would load but compare wrongly later."""
    for entry in _data(ADDRESSING_FILE, "RoutingBGPNeighbor"):
        assert isinstance(entry["remote_as"], str)


def test_the_static_site_has_a_route_and_no_sessions() -> None:
    """acme/dr is the reason WanSite.bgp_sessions is optional."""
    sites = {(s["tenant"], s["name"]): s for s in _data(WAN_FILE, "WanSite")}
    dr = sites["acme", "dr"]

    assert "bgp_sessions" not in dr
    assert dr["static_routes"] == [["CUST_ACME", "10.60.11.0/24", "10.51.11.2/32"]]
    assert dr["attachment_kind"] == "static"


def test_every_bgp_site_names_its_sessions() -> None:
    """Both ends where both are ours; one where the far end is a fabric device.

    The branch peers with border-leaf1 over a private fibre, so only the branch
    side belongs to the WAN -- the fabric side is already modelled in
    objects/27_otternet_vrf_services.yml.
    """
    sites = {(s["tenant"], s["name"]): s for s in _data(WAN_FILE, "WanSite")}
    expected = {
        ("acme", "hq"): 2,
        ("globex", "hq"): 2,
        ("branch", "office"): 1,
    }

    for key, count in expected.items():
        assert len(sites[key]["bgp_sessions"]) == count, key


def test_the_internet_peering_names_both_transit_ends() -> None:
    peering = _data(WAN_FILE, "WanInternetPeering")[0]

    assert peering["bgp_sessions"] == [["isp-pe2", "10.52.0.2"], ["internet-rtr", "10.52.0.1"]]


def test_the_static_route_matches_the_lab() -> None:
    lab = _lab()
    acme = next(t for t in lab["tenants"] if t["name"] == "acme")
    dr = next(s for s in acme["sites"] if s["kind"] == "static")
    route = _data(ADDRESSING_FILE, "RoutingVrfStaticRoute")[0]

    assert route["prefix"] == dr["lan"]
    assert route["next_hop"] == dr["ce"]["wan_address"].split("/")[0]
    # The site reference must use the /32 form IPHost normalises to.
    site = next(x for x in _data(WAN_FILE, "WanSite") if x["name"] == "dr")
    assert site["static_routes"][0][2].endswith("/32")
    assert route["vrf"] == acme["vrf"]
    assert route["devices"] == [dr["pe"]["node"]]


def test_the_pe_vrfs_are_defined_in_exactly_one_file() -> None:
    """Cycle 021 moved them out of the service layer; a copy left behind would
    give one VRF two definitions and reintroduce the drift this cycle removes.
    """
    defined_in = [
        path.name
        for path in (ADDRESSING_FILE, SERVICES_FILE)
        for doc in _docs(path)
        if doc.get("spec", {}).get("kind") == "IpamVRF"
    ]

    assert defined_in == [ADDRESSING_FILE.name]


# ---------------------------------------------------------------------------
# Router IDs
# ---------------------------------------------------------------------------


def _lab_router_ids() -> dict[str, str]:
    lab = _lab()
    isp, branch = lab["isp"], lab["branch"]
    found = {
        isp["edge"]["node"]: f"{isp['edge']['loopback']}/32",
        isp["core"]["node"]: f"{isp['core']['loopback']}/32",
        branch["router"]["node"]: f"{branch['loopback']}/32",
        isp["internet"]["router"]: f"{isp['internet']['peering']['peer']}/30",
    }
    for tenant in lab["tenants"]:
        for site in tenant["sites"]:
            if site["kind"] == "bgp":
                found[site["ce"]["node"]] = site["ce"]["lan_address"]
    return found


def test_router_ids_match_the_lab() -> None:
    seeded = {d["name"]: d["router_id"][0] for d in _data(ADDRESSING_FILE, "DcimDevice")}

    assert seeded == _lab_router_ids()


def test_the_static_sites_ce_has_no_router_id() -> None:
    """It runs no routing protocol, so there is nothing to identify it as."""
    seeded = {d["name"] for d in _data(ADDRESSING_FILE, "DcimDevice")}

    assert "cust-acme-dr-ce" not in seeded


def test_half_the_router_ids_are_not_loopbacks() -> None:
    """The reason router_id is explicit rather than derived.

    Deriving it from a loopback interface would be wrong for these three, and a
    mismatched router-id still forms a session -- so the error would be silent.
    """
    loopback_addresses = {
        a["address"] for a in _data(ADDRESSING_FILE, "IpamIPAddress") if a["interface"]["data"]["name"] == "lo"
    }
    seeded = {d["name"]: d["router_id"][0] for d in _data(ADDRESSING_FILE, "DcimDevice")}
    not_loopbacks = {name for name, addr in seeded.items() if addr not in loopback_addresses}

    assert not_loopbacks == {"cust-acme-ce", "cust-globex-ce", "internet-rtr"}


def test_every_router_id_is_an_address_this_file_seeds() -> None:
    """One object reached two ways -- via its interface and via the device --
    never a second copy, which the address uniqueness constraint would reject.
    """
    addresses = {a["address"] for a in _data(ADDRESSING_FILE, "IpamIPAddress")}

    for device in _data(ADDRESSING_FILE, "DcimDevice"):
        assert device["router_id"][0] in addresses


def test_dc_service_prefixes_are_the_shared_range_not_a_tenant_subnet() -> None:
    """Cycle 019 transcription fix, caught by cycle 021's SC-009 walk.

    The lab's `isp.dc_service_prefixes` is one shared range -- "what EVERY
    tenant may reach in the datacentre, regardless of what they buy" -- and it
    is the same for both tenants. 019 seeded each tenant's own cloud subnet
    instead, which is a different concept that already lives on
    ServiceTenantCloud.prefix. Rendered, the error would put the wrong network
    in isp-pe1's PL-DC-SERVICES and duplicate the cloud subnet.
    """
    expected = _lab()["isp"]["dc_service_prefixes"]

    for l3vpn in _data(SERVICES_FILE, "ServiceL3vpn"):
        assert [ref[0] for ref in l3vpn["dc_service_prefixes"]] == expected
