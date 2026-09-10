"""Contract tests for the k8s leaves' Vlan110 peering SVIs.

These hold the contract in `specs/014-k8s-leaf-peering-svi/contracts/object-contract.md`
in place. They parse the seed YAML, so they run without an Infrahub instance and
catch a bad edit at review time rather than at load time -- which for this data
matters more than usual, because the failure mode is silent: several plausible
edits leave the objects loading cleanly while quietly destroying the traversal
that makes `peer_address` derivable.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import yaml

OBJECTS_DIR = Path(__file__).parent.parent.parent / "objects"

# The two switches the Cilium sessions actually peer with. The lab models the
# same hardware a second time as `k8s-leaf1`/`k8s-leaf2` (their containerlab
# hostnames); those duplicates are NOT valid peer targets, because
# ClusterFabricPeering.peer_device points at the names below.
K8S_LEAVES = {"leaf-nfd41-pod1-1-1", "leaf-nfd41-pod1-1-2"}

# The network the Cilium nodes and both leaves share.
PEERING_PREFIX = ipaddress.ip_network("10.110.0.0/24")

# The MLAG pair's shared virtual-router address. Present on BOTH leaves, so it
# can never identify a single BGP neighbour.
VARP_GATEWAY = ipaddress.ip_address("10.110.0.1")

SVI_NAME = "Vlan110"


def _load_objects(kind: str) -> list[tuple[Path, dict[str, Any]]]:
    """Every seed object of ``kind``, with the file it came from."""
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(OBJECTS_DIR.glob("*.yml")):
        for doc in yaml.safe_load_all(path.read_text()):
            if doc and doc.get("spec", {}).get("kind") == kind:
                found.extend((path, entry) for entry in doc["spec"]["data"])
    return found


def _peering_svis() -> list[tuple[Path, dict[str, Any]]]:
    return [(path, entry) for path, entry in _load_objects("InterfaceVirtual") if entry.get("name") == SVI_NAME]


def _svi_addresses(entry: dict[str, Any]) -> list[str]:
    """The addresses an SVI attaches, as plain strings.

    ``ip_addresses`` is a list of human-friendly ids, each of which is itself a
    list ``[address, ip_namespace]`` because ``IpamIPAddress`` has a two-element
    HFID.
    """
    return [ref[0] if isinstance(ref, list) else ref for ref in entry.get("ip_addresses", [])]


def test_one_peering_svi_per_k8s_leaf() -> None:
    """Exactly two peering SVIs exist, one on each k8s leaf.

    A third would mean the derivation has more than one candidate interface on
    some device; a missing one would leave that leaf's session underivable.
    """
    devices = [entry["device"] for _, entry in _peering_svis()]
    assert sorted(devices) == sorted(K8S_LEAVES), (
        f"peering SVIs are on {sorted(devices)}, expected {sorted(K8S_LEAVES)}"
    )


def test_each_peering_svi_carries_exactly_one_address() -> None:
    """One address per SVI, so "the address on this interface" is unambiguous."""
    for _, entry in _peering_svis():
        addresses = _svi_addresses(entry)
        assert len(addresses) == 1, f"{entry['device']} {SVI_NAME} carries {addresses}, expected exactly one"


def test_the_two_peering_addresses_are_distinct() -> None:
    """Each leaf needs an address of its own to be a distinguishable neighbour."""
    addresses = [address for _, entry in _peering_svis() for address in _svi_addresses(entry)]
    assert len(set(addresses)) == len(addresses), f"peering addresses are not distinct: {addresses}"


def test_peering_svi_addresses_match_the_declared_peer_addresses() -> None:
    """The address derivable from a device equals the one its session declares.

    This is the check that makes the follow-up cycle a refactor rather than a
    change: once a generator sets `peer_address` from this traversal, no value
    moves. If this fails, the two halves of the model disagree and whichever the
    generator wins with is the one that reaches a live cluster.
    """
    by_device = {entry["device"]: _svi_addresses(entry)[0] for _, entry in _peering_svis()}
    for _, session in _load_objects("ClusterFabricPeering"):
        device = session["peer_device"]
        declared = session["peer_address"][0]
        assert device in by_device, f"session {session['name']} peers {device}, which has no {SVI_NAME}"
        assert by_device[device] == declared, (
            f"session {session['name']}: declared peer_address {declared} "
            f"but {device}'s {SVI_NAME} carries {by_device[device]}"
        )


def test_peering_svis_never_carry_the_varp_gateway() -> None:
    """The shared virtual-router address must not be attachable to one leaf.

    10.110.0.1 lives on `EvpnSvi.ip_virtual_router_addresses` as intent and is
    present on both leaves. Attaching it to an interface would not make the
    derivation *wrong* -- it would make it ambiguous, which is far harder to
    notice, because BGP would come up against whichever leaf answered first.
    """
    for _, entry in _peering_svis():
        for address in _svi_addresses(entry):
            assert ipaddress.ip_interface(address).ip != VARP_GATEWAY, (
                f"{entry['device']} {SVI_NAME} carries the shared VARP gateway {address}"
            )


def test_the_varp_gateway_is_not_seeded_as_an_address_object() -> None:
    """Nothing may attach 10.110.0.1 later, because the object does not exist."""
    seeded = {ipaddress.ip_interface(entry["address"]).ip for _, entry in _load_objects("IpamIPAddress")}
    assert VARP_GATEWAY not in seeded, f"{VARP_GATEWAY} is seeded as an IpamIPAddress and could be attached"


def test_exactly_one_seeded_address_per_leaf_inside_the_peering_prefix() -> None:
    """The derivation "the address this device owns in the node prefix" is single-valued.

    A second interface on the same leaf with an address in 10.110.0.0/24 would
    give the follow-up generator two candidates and no rule for choosing.
    """
    per_device: dict[str, list[str]] = {}
    for _, entry in _load_objects("InterfaceVirtual"):
        for address in _svi_addresses(entry):
            if ipaddress.ip_interface(address).ip in PEERING_PREFIX:
                per_device.setdefault(entry["device"], []).append(address)

    assert set(per_device) == K8S_LEAVES, f"addresses in {PEERING_PREFIX} are on {sorted(per_device)}"
    for device, addresses in per_device.items():
        assert len(addresses) == 1, f"{device} owns {addresses} inside {PEERING_PREFIX}; the derivation is ambiguous"


def test_peering_svis_use_ip_addresses_not_ip_address() -> None:
    """Guards the one substitution that would silently undo this whole cycle.

    ``InterfaceVirtual`` has two relationships to ``IpamIPAddress``:

    * ``ip_addresses`` (identifier ``interfacelayer3__ipamipaddress``) -- the
      only one with a reverse side, so it is the only one that populates
      ``IpamIPAddress.interface`` and makes the address reachable from a device.
    * ``ip_address`` (identifier ``interface__ip_address``) -- no counterpart on
      the address node at all.

    Swapping to ``ip_address`` loads cleanly, shows an address on the interface
    in the UI, and leaves ``IpamIPAddress.interface`` null -- reproducing exactly
    the defect this cycle removed, while looking like it works.
    """
    for path, entry in _peering_svis():
        assert entry.get("ip_addresses"), f"{path.name}: {entry['device']} {SVI_NAME} sets no ip_addresses"
        assert "ip_address" not in entry, (
            f"{path.name}: {entry['device']} {SVI_NAME} sets `ip_address`, which has no reverse "
            "relationship; use `ip_addresses` or the address stays unreachable from the device"
        )


def test_peering_svis_target_the_devices_the_sessions_name() -> None:
    """Never the k8s-leaf* containerlab duplicates of the same hardware."""
    peers = {session["peer_device"] for _, session in _load_objects("ClusterFabricPeering")}
    for _, entry in _peering_svis():
        assert entry["device"] in peers, (
            f"{SVI_NAME} is on {entry['device']}, which no ClusterFabricPeering names as a peer "
            f"(sessions peer {sorted(peers)})"
        )


def test_peering_svis_load_after_the_addresses_they_reference() -> None:
    """File order is the dependency order; the loader resolves against what exists.

    Asserted from the filenames rather than trusted, so a renumbering that would
    fail at load time fails here instead.
    """
    svi_files = {path.name for path, _ in _peering_svis()}
    address_files = {
        path.name
        for path, entry in _load_objects("IpamIPAddress")
        if ipaddress.ip_interface(entry["address"]).ip in PEERING_PREFIX
    }
    assert svi_files and address_files
    assert min(svi_files) > max(address_files), (
        f"{sorted(svi_files)} must sort after {sorted(address_files)}, which declares the peering addresses"
    )
