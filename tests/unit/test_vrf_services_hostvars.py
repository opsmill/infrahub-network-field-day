"""Unit tests for the VRF-scoped service hostvars.

Cover the AVD structures the OTTERNET design depends on and that the reference
design previously could not express as inputs: per-node SVI addresses with a
VARP gateway, VRF static routes, VRF BGP peers, and routed L3 handoffs.

These deliberately model the relationship shape the SDK actually returns from
``client.filters`` -- a peer id with nothing hydrated -- because that is where
the first implementation broke: reading ``RelatedNode.peer`` resolves through
the client's local store and raises for a peer that was never fetched, which
surfaced only inside a full testcontainer run.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from generators.generate_avd_device_hostvar import GenerateAVDDeviceHostvar


def _attr(value: object) -> SimpleNamespace:
    return SimpleNamespace(value=value)


class _RaisingPeer:
    """A relationship whose ``peer`` raises, as the SDK's does when unfetched."""

    def __init__(self, peer_id: str) -> None:
        self.id = peer_id

    @property
    def peer(self) -> object:  # pragma: no cover - accessing it is the bug
        raise AssertionError("peer must not be read; it resolves through the local store")

    @property
    def node(self) -> None:
        return None


def _many(*peer_ids: str) -> SimpleNamespace:
    return SimpleNamespace(fetch=AsyncMock(), peers=[_RaisingPeer(peer_id) for peer_id in peer_ids])


def _generator(devices: dict[str, str]) -> GenerateAVDDeviceHostvar:
    """A generator whose client resolves device ids to names, and nothing else."""
    gen = GenerateAVDDeviceHostvar.__new__(GenerateAVDDeviceHostvar)
    gen.client = AsyncMock()

    async def get(*, kind: str, id: str, **_: Any) -> SimpleNamespace:  # noqa: A002
        assert kind == "DcimFabricSwitch"
        return SimpleNamespace(name=_attr(devices[id]))

    gen.client.get = AsyncMock(side_effect=get)
    return gen


def _filters_returning(rows: dict[str, list[object]]) -> AsyncMock:
    async def filters(*, kind: str, **_: Any) -> list[object]:
        return rows.get(kind, [])

    return AsyncMock(side_effect=filters)


# ------------------------------------------------------------------ SVI nodes
@pytest.mark.anyio
async def test_svi_emits_varp_gateway_and_per_node_addresses() -> None:
    """A VARP SVI carries the shared gateway plus each leaf's own address.

    Cilium peers BGP from the k3s nodes, so each leaf needs an unambiguous
    address of its own; an anycast-only SVI cannot give it one.
    """
    svi = SimpleNamespace(
        id="svi-1",
        svi_id=_attr(110),
        name=_attr("K8S_NODES"),
        enabled=_attr(True),
        description=_attr("k3s node network"),
        ip_address_virtual=_attr(None),
        ip_virtual_router_addresses=_attr(["10.110.0.1"]),
        nodes=None,
        rack_tags=None,
        avd_tags=None,
    )
    svi_nodes = [
        SimpleNamespace(ip_address=_attr("10.110.0.3/24"), device=_RaisingPeer("dev-2")),
        SimpleNamespace(ip_address=_attr("10.110.0.2/24"), device=_RaisingPeer("dev-1")),
    ]

    gen = _generator({"dev-1": "k8s-leaf1", "dev-2": "k8s-leaf2"})
    gen.client.filters = _filters_returning({"EvpnSvi": [svi], "EvpnSviNode": svi_nodes})

    svis = await gen._build_svis_hostvars(SimpleNamespace(id="vrf-1", svis=None))

    assert svis == [
        {
            "id": 110,
            "name": "K8S_NODES",
            "enabled": True,
            "description": "k3s node network",
            "ip_virtual_router_addresses": ["10.110.0.1"],
            # Sorted by node so a re-run produces identical hostvars.
            "nodes": [
                {"node": "k8s-leaf1", "ip_address": "10.110.0.2/24"},
                {"node": "k8s-leaf2", "ip_address": "10.110.0.3/24"},
            ],
        }
    ]


# --------------------------------------------------------------- static routes
@pytest.mark.anyio
async def test_static_route_is_scoped_to_its_originating_devices() -> None:
    """A tenant default route names only the device that originates it."""
    route = SimpleNamespace(
        prefix=_attr("0.0.0.0/0"),
        next_hop=_attr("10.250.110.2/32"),
        description=_attr("Default via the firewall's k8s-prod zone"),
        devices=_many("dev-border"),
    )
    gen = _generator({"dev-border": "border-leaf1"})
    gen.client.filters = _filters_returning({"RoutingVrfStaticRoute": [route]})

    routes = await gen._build_vrf_static_routes(SimpleNamespace(id="vrf-1", static_routes=None))

    assert routes == [
        {
            # The next hop is a single host, so the /32 the IPHost attribute
            # stores is stripped -- AVD wants a bare address.
            "prefix": "0.0.0.0/0",
            "next_hop": "10.250.110.2",
            "nodes": ["border-leaf1"],
        }
    ]
    # AVD's static-route model has no `description` key and rejects one, which
    # fails the whole device's input validation. The object keeps it for humans.
    assert "description" not in routes[0]


@pytest.mark.anyio
async def test_static_route_with_no_devices_is_dropped() -> None:
    """A route that names no device is skipped rather than emitted fabric-wide.

    Originating a tenant default on every leaf would black-hole traffic on the
    ones with no path to the next hop.
    """
    route = SimpleNamespace(
        prefix=_attr("0.0.0.0/0"),
        next_hop=_attr("10.250.110.2"),
        description=_attr(None),
        devices=SimpleNamespace(fetch=AsyncMock(), peers=[]),
    )
    gen = _generator({})
    gen.client.filters = _filters_returning({"RoutingVrfStaticRoute": [route]})

    assert await gen._build_vrf_static_routes(SimpleNamespace(id="vrf-1", static_routes=None)) == []


# ------------------------------------------------------------------ BGP peers
@pytest.mark.anyio
async def test_bgp_peer_carries_policy_and_both_pair_members() -> None:
    """A workload peer lands on both MLAG members with its full policy."""
    peer = SimpleNamespace(
        ip_address=_attr("10.110.0.11/32"),
        remote_asn=_attr(65401),
        description=_attr("k8s-node1-cilium"),
        cleartext_password=_attr("Otternet-Cilium"),
        send_community=_attr("all"),
        next_hop_self=_attr(True),
        maximum_routes=_attr(100),
        route_map_in=_attr("RM-CILIUM-IN"),
        route_map_out=_attr("RM-FABRIC-TO-CILIUM"),
        devices=_many("dev-1", "dev-2"),
    )
    gen = _generator({"dev-1": "k8s-leaf1", "dev-2": "k8s-leaf2"})
    gen.client.filters = _filters_returning({"RoutingVrfBgpPeer": [peer]})

    peers = await gen._build_vrf_bgp_peers(SimpleNamespace(id="vrf-1", bgp_peers=None))

    assert peers == [
        {
            "ip_address": "10.110.0.11",
            # PyAVD expects a stringified ASN.
            "remote_as": "65401",
            "nodes": ["k8s-leaf1", "k8s-leaf2"],
            "description": "k8s-node1-cilium",
            "cleartext_password": "Otternet-Cilium",
            "send_community": "all",
            "next_hop_self": True,
            "maximum_routes": 100,
            "route_map_in": "RM-CILIUM-IN",
            "route_map_out": "RM-FABRIC-TO-CILIUM",
        }
    ]


@pytest.mark.anyio
async def test_bgp_peer_keeps_a_deliberate_false() -> None:
    """`next_hop_self: false` is a decision, not an unset field."""
    peer = SimpleNamespace(
        ip_address=_attr("10.250.50.2"),
        remote_asn=_attr(65500),
        description=_attr("isp-pe2"),
        cleartext_password=_attr(None),
        send_community=_attr("all"),
        next_hop_self=_attr(False),
        maximum_routes=_attr(1000),
        route_map_in=_attr("RM-WAN-IN"),
        route_map_out=_attr("RM-DC-TO-EXTERNAL"),
        devices=_many("dev-border"),
    )
    gen = _generator({"dev-border": "border-leaf1"})
    gen.client.filters = _filters_returning({"RoutingVrfBgpPeer": [peer]})

    peers = await gen._build_vrf_bgp_peers(SimpleNamespace(id="vrf-1", bgp_peers=None))

    assert peers[0]["next_hop_self"] is False
    assert "cleartext_password" not in peers[0]


# -------------------------------------------------------------- L3 interfaces
@pytest.mark.anyio
async def test_l3_interface_emits_avd_parallel_lists_with_acl_bindings() -> None:
    """One Infrahub object becomes one single-element AVD `l3_interfaces` entry."""
    l3_interface = SimpleNamespace(
        interface_name=_attr("Ethernet10"),
        ip_address=_attr("10.250.110.1/30"),
        description=_attr("FW1_ge-0/0/0_ZONE-K8S-PROD"),
        enabled=_attr(True),
        ipv4_acl_in=_attr("ACL-FROM-FIREWALL"),
        ipv4_acl_out=_attr("ACL-K8S-ANTISPOOF"),
        device=_RaisingPeer("dev-border"),
    )
    gen = _generator({"dev-border": "border-leaf1"})
    gen.client.filters = _filters_returning({"RoutingVrfL3Interface": [l3_interface]})

    interfaces = await gen._build_vrf_l3_interfaces(SimpleNamespace(id="vrf-1", l3_interfaces=None))

    assert interfaces == [
        {
            "interfaces": ["Ethernet10"],
            "nodes": ["border-leaf1"],
            # The mask is kept here, unlike a static route's next hop.
            "ip_addresses": ["10.250.110.1/30"],
            "description": "FW1_ge-0/0/0_ZONE-K8S-PROD",
            "enabled": True,
            "ipv4_acl_in": "ACL-FROM-FIREWALL",
            "ipv4_acl_out": "ACL-K8S-ANTISPOOF",
        }
    ]


@pytest.mark.anyio
async def test_l3_interfaces_are_ordered_by_device_then_interface() -> None:
    """Deterministic order, so a re-run produces byte-identical hostvars."""
    rows = [
        SimpleNamespace(
            interface_name=_attr(name),
            ip_address=_attr(address),
            description=_attr(None),
            enabled=_attr(True),
            ipv4_acl_in=_attr(None),
            ipv4_acl_out=_attr(None),
            device=_RaisingPeer("dev-border"),
        )
        for name, address in (("Ethernet14", "10.250.150.1/30"), ("Ethernet12", "10.250.50.1/30"))
    ]
    gen = _generator({"dev-border": "border-leaf1"})
    gen.client.filters = _filters_returning({"RoutingVrfL3Interface": rows})

    interfaces = await gen._build_vrf_l3_interfaces(SimpleNamespace(id="vrf-1", l3_interfaces=None))

    assert [entry["interfaces"][0] for entry in interfaces] == ["Ethernet12", "Ethernet14"]


# ----------------------------------------------------------------- VRF fields
@pytest.mark.anyio
async def test_vrf_attributes_reach_the_tenant_payload() -> None:
    """The AVD VRF inputs the design needs are all emitted."""
    vrf = SimpleNamespace(
        id="vrf-1",
        name=_attr("K8S_PROD"),
        vrf_id=_attr(110),
        vrf_vni=_attr(110),
        description=_attr("Kubernetes production"),
        enable_mlag_ibgp_peering_vrfs=_attr(True),
        redistribute_connected=_attr(True),
        redistribute_static=_attr(True),
        vtep_diagnostic_loopback=_attr(None),
        vtep_diagnostic_loopback_ip_range=_attr(None),
        svis=None,
        static_routes=None,
        bgp_peers=None,
        l3_interfaces=None,
    )
    tenant = SimpleNamespace(
        id="tenant-1",
        name=_attr("TENANT_K8S"),
        mac_vrf_vni_base=_attr(11000),
        vrfs=None,
        l2vlans=None,
    )

    gen = _generator({})
    gen.client.filters = _filters_returning({"EvpnTenant": [tenant], "IpamVRF": [vrf]})

    tenants = await gen._build_tenants_hostvars("fabric-1")

    assert tenants == [
        {
            "name": "TENANT_K8S",
            "mac_vrf_vni_base": 11000,
            "vrfs": [
                {
                    "name": "K8S_PROD",
                    "vrf_id": 110,
                    "vrf_vni": 110,
                    "description": "Kubernetes production",
                    "enable_mlag_ibgp_peering_vrfs": True,
                    "redistribute_connected": True,
                    "redistribute_static": True,
                }
            ],
        }
    ]
