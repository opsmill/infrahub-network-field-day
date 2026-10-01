"""Unit tests for the per-section builders `_build_hostvars` is assembled from.

The hostvars are serialized with `json.dumps` and checksummed, and the checksum is
what decides whether the file is re-uploaded. So these tests pin KEY ORDER as well
as content: a builder that emitted the same keys in a different order would move
every switch's checksum while changing nothing AVD can see.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from generators.generate_avd_device_hostvar import (
    GenerateAVDDeviceHostvar,
    _remote_server_device,  # noqa: PLC2701 - focused unit coverage for the endpoint filter
)

G = GenerateAVDDeviceHostvar


def _attr(value: object) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _edges(*nodes: object) -> SimpleNamespace:
    return SimpleNamespace(edges=[SimpleNamespace(node=n) for n in nodes])


def _hostvars_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "hostname": "leaf1",
        "role": "leaf",
        "bgp_asn": 65101,
        "node_id": 1,
        "loopback_ip": "10.0.0.1",
        "loopback_ipv4_pool": None,
        "vtep_loopback_ip": None,
        "vtep_loopback_ipv4_pool": None,
        "mgmt_ip": None,
        "fabric_name": "FAB",
        "mgmt_gateway": "172.20.0.1",
        "virtual_router_mac": None,
        "underlay_routing_protocol": "ebgp",
        "overlay_routing_protocol": "ebgp",
        "p2p_uplinks_mtu": None,
        "spanning_tree_mode": None,
        "spanning_tree_priorities": {},
        "bgp_passwords": {"evpn_overlay": "pw", "underlay": None, "mlag": None},
        "management": {"dns_servers": [{"ip_address": "1.1.1.1"}]},
        "pools": {},
        "uplinks": {"uplink_interfaces": [], "uplink_switches": [], "uplink_switch_interfaces": []},
        "rack_info": {"name": None, "mlag": None, "leaf_names": [], "avd_tags": []},
        "mlag_info": {"domain_id": None, "bgp_asn": None, "virtual_router_mac": None, "peer_names": []},
        "tenants_data": [],
        "connected_endpoints": [],
    }
    kwargs.update(overrides)
    return kwargs


# --- node config ---------------------------------------------------------------


def test_node_identity_key_order_and_mlag_leaf_omits_bgp_as() -> None:
    node = G._build_node_identity(
        hostname="ss1",
        role="super_spine",
        node_id=3,
        bgp_asn=65000,
        is_mlag_leaf=False,
        loopback_ip="10.0.0.1",
        loopback_ipv4_pool="10.0.0.0/24",
        vtep_loopback_ip=None,
        vtep_loopback_ipv4_pool=None,
        mgmt_ip="172.20.0.9/24",
        evpn_gateway=None,
    )
    assert list(node) == ["name", "id", "evpn_role", "bgp_as", "loopback_ipv4_address", "loopback_ipv4_pool", "mgmt_ip"]
    assert node["evpn_role"] == "server"
    assert node["bgp_as"] == "65000"

    mlag = G._build_node_identity(
        hostname="leaf1",
        role="leaf",
        node_id=None,
        bgp_asn=65101,
        is_mlag_leaf=True,
        loopback_ip=None,
        loopback_ipv4_pool="ignored-without-address",
        vtep_loopback_ip=None,
        vtep_loopback_ipv4_pool=None,
        mgmt_ip=None,
        evpn_gateway=None,
    )
    assert mlag == {"name": "leaf1"}


def test_node_identity_vtep_pool_only_for_leaf_family() -> None:
    common: dict[str, Any] = {
        "hostname": "x",
        "node_id": None,
        "bgp_asn": None,
        "is_mlag_leaf": False,
        "loopback_ip": None,
        "loopback_ipv4_pool": None,
        "vtep_loopback_ip": "10.1.0.1",
        "vtep_loopback_ipv4_pool": "10.1.0.0/24",
        "mgmt_ip": None,
        "evpn_gateway": None,
    }
    assert "vtep_loopback_ipv4_pool" in G._build_node_identity(role="leaf", **common)
    assert "vtep_loopback_ipv4_pool" not in G._build_node_identity(role="spine", **common)


def test_node_underlay_pools_then_uplinks_and_reservation() -> None:
    node = G._build_node_underlay(
        pools={"mlag_peer_ipv4_pool": "10.3.0.0/24", "uplink_ipv4_pool": "10.2.0.0/16"},
        uplinks={
            "uplink_interfaces": ["Ethernet1"],
            "uplink_switches": ["spine1"],
            "uplink_switch_interfaces": ["Ethernet3"],
        },
        uplink_pool_reservation={"max_uplink_switches": 2, "max_parallel_uplinks": None},
    )
    assert list(node) == [
        "mlag_peer_ipv4_pool",
        "uplink_interfaces",
        "uplink_switches",
        "uplink_switch_interfaces",
        "uplink_ipv4_pool",
        "max_uplink_switches",
    ]


def test_node_underlay_without_uplinks_ignores_uplink_pool() -> None:
    node = G._build_node_underlay(
        pools={"uplink_ipv4_pool": "10.2.0.0/16"},
        uplinks={"uplink_interfaces": [], "uplink_switches": [], "uplink_switch_interfaces": []},
        uplink_pool_reservation={"max_uplink_switches": 2, "max_parallel_uplinks": 2},
    )
    assert node == {}


def test_node_mlag_and_svi_gates() -> None:
    mlag_info = {"domain_id": "D1", "mlag_peer_interfaces": ["Ethernet47"]}
    node = G._build_node_mlag_and_svi(
        role="leaf", renders_mlag=True, mlag_info=mlag_info, virtual_router_mac="00:1c:73:00:00:01", has_tenants=True
    )
    assert list(node) == ["mlag_interfaces", "virtual_router_mac_address"]
    # A spine carries no SVIs, so it never gets the node-level MAC; no tenants, no MAC either.
    assert "virtual_router_mac_address" not in G._build_node_mlag_and_svi(
        role="spine", renders_mlag=False, mlag_info=mlag_info, virtual_router_mac="m", has_tenants=True
    )
    assert (
        G._build_node_mlag_and_svi(
            role="leaf", renders_mlag=True, mlag_info={"domain_id": None}, virtual_router_mac="m", has_tenants=False
        )
        == {}
    )


# --- top-level sections --------------------------------------------------------


def test_fabric_settings_order_and_sentinel_underlay() -> None:
    settings = G._build_fabric_settings(
        mgmt_gateway="gw",
        virtual_router_mac="mac",
        underlay_routing_protocol="ebgp",
        overlay_routing_protocol="ebgp",
        evpn_vlan_aware_bundles=True,
        p2p_uplinks_mtu=0,
        spanning_tree_mode="mstp",
    )
    assert list(settings) == [
        "mgmt_gateway",
        "virtual_router_mac_address",
        "underlay_routing_protocol",
        "overlay_routing_protocol",
        "evpn_vlan_aware_bundles",
        "p2p_uplinks_mtu",
        "spanning_tree_settings",
    ]
    # p2p_uplinks_mtu=0 is a value, not an absence.
    assert settings["p2p_uplinks_mtu"] == 0
    none_underlay = G._build_fabric_settings(
        mgmt_gateway=None,
        virtual_router_mac=None,
        underlay_routing_protocol="none",
        overlay_routing_protocol=None,
        evpn_vlan_aware_bundles=False,
        p2p_uplinks_mtu=None,
        spanning_tree_mode=None,
    )
    assert none_underlay == {}


def test_node_type_defaults_keeps_a_zero_priority() -> None:
    assert G._build_node_type_defaults(role="spine", spanning_tree_priorities={"spine": 0}) == {
        "spanning_tree_priority": 0
    }
    assert G._build_node_type_defaults(role="leaf", spanning_tree_priorities={"spine": 0}) == {}


def test_bgp_peer_groups_omitted_when_no_password() -> None:
    assert G._build_bgp_peer_groups({"evpn_overlay": None, "underlay": None, "mlag": None}) == {}
    groups = G._build_bgp_peer_groups({"evpn_overlay": "a", "underlay": "b", "mlag": "c"})
    assert list(groups["bgp_peer_groups"]) == ["evpn_overlay_peers", "ipv4_underlay_peers", "mlag_ipv4_underlay_peer"]


def test_management_hostvars_lifts_first_server_vrf() -> None:
    result = G._build_management_hostvars(
        {
            "dns_servers": [{"ip_address": "1.1.1.1"}],
            "ntp_servers": [{"name": "a", "server_vrf": "MGMT", "iburst": True}, {"name": "b", "server_vrf": "X"}],
            "ntp_set_first_server_as_preferred": True,
            "local_users": [{"name": "admin"}],
        }
    )
    assert list(result) == ["dns_settings", "ntp_settings", "aaa_settings"]
    assert result["ntp_settings"] == {
        "servers": [{"name": "a", "iburst": True}, {"name": "b"}],
        "server_vrf": "MGMT",
        "set_first_ntp_server_as_preferred": True,
    }


def test_services_hostvars_order() -> None:
    result = G._build_services_hostvars(
        tenants_data=[{"name": "T"}], connected_endpoints=[{"name": "s", "adapters": []}], dci_l3_edge_p2p_links=[{}]
    )
    assert list(result) == ["tenants", "servers", "l3_edge"]
    assert G._build_services_hostvars(tenants_data=[], connected_endpoints=[], dci_l3_edge_p2p_links=None) == {}


# --- node groups ---------------------------------------------------------------


def test_node_groups_mlag_pair_and_missing_asn() -> None:
    mlag_info = {"domain_id": "D1", "bgp_asn": 65101, "virtual_router_mac": None, "peer_names": ["leaf2"]}
    rack_info: Any = {"name": "R1", "mlag": True, "leaf_names": ["leaf1", "leaf2", "leaf3"], "avd_tags": []}
    groups = G._build_node_groups(
        hostname="leaf1",
        renders_mlag=True,
        is_leaf_family=True,
        rack_info=rack_info,
        mlag_info=mlag_info,
        virtual_router_mac="fabric-mac",
    )
    assert groups == [
        {
            "group": "D1",
            "nodes": [{"name": "leaf1"}, {"name": "leaf2"}],
            "mlag_domain_id": "D1",
            "bgp_as": "65101",
            "virtual_router_mac_address": "fabric-mac",
        }
    ]

    with pytest.raises(ValueError, match="has no BGP ASN"):
        G._build_node_groups(
            hostname="leaf1",
            renders_mlag=True,
            is_leaf_family=True,
            rack_info=rack_info,
            mlag_info={**mlag_info, "bgp_asn": None},
            virtual_router_mac=None,
        )


def test_node_groups_rack_and_none() -> None:
    rack_info: Any = {"name": "R1", "mlag": False, "leaf_names": ["leaf3"], "avd_tags": []}
    no_mlag = {"domain_id": None, "bgp_asn": None, "virtual_router_mac": None, "peer_names": []}
    groups = G._build_node_groups(
        hostname="leaf1",
        renders_mlag=True,
        is_leaf_family=True,
        rack_info=rack_info,
        mlag_info=no_mlag,
        virtual_router_mac=None,
    )
    assert groups == [{"group": "R1", "nodes": [{"name": "leaf1"}, {"name": "leaf3"}], "mlag": False}]
    # No rack name, or a device that renders no MLAG constructs: no group at all.
    assert not G._build_node_groups(
        hostname="leaf1",
        renders_mlag=True,
        is_leaf_family=True,
        rack_info={**rack_info, "name": None},
        mlag_info=no_mlag,
        virtual_router_mac=None,
    )
    assert not G._build_node_groups(
        hostname="spine1",
        renders_mlag=False,
        is_leaf_family=False,
        rack_info=rack_info,
        mlag_info=no_mlag,
        virtual_router_mac=None,
    )


# --- assembly order ------------------------------------------------------------


def test_build_hostvars_places_node_type_after_management_without_defaults() -> None:
    hostvars = G._build_hostvars(**_hostvars_kwargs())
    assert list(hostvars) == [
        "type",
        "fabric_name",
        "mgmt_gateway",
        "underlay_routing_protocol",
        "overlay_routing_protocol",
        "bgp_peer_groups",
        "dns_settings",
        "l3leaf",
    ]
    assert list(hostvars["l3leaf"]) == ["nodes"]


def test_build_hostvars_places_node_type_before_bgp_with_defaults() -> None:
    hostvars = G._build_hostvars(
        **_hostvars_kwargs(
            spanning_tree_priorities={"leaf": 4096},
            rack_info={"name": "R1", "mlag": None, "leaf_names": [], "avd_tags": []},
            tenants_data=[{"name": "T"}],
        )
    )
    assert list(hostvars) == [
        "type",
        "fabric_name",
        "mgmt_gateway",
        "underlay_routing_protocol",
        "overlay_routing_protocol",
        "l3leaf",
        "bgp_peer_groups",
        "dns_settings",
        "tenants",
    ]
    assert list(hostvars["l3leaf"]) == ["defaults", "nodes", "node_groups"]


def test_build_hostvars_custom_keys_lead_and_generated_values_win() -> None:
    hostvars = G._build_hostvars(**_hostvars_kwargs(custom_hostvars={"zz_first": 1, "fabric_name": "OVERRIDE"}))
    assert next(iter(hostvars)) == "zz_first"
    assert hostvars["fabric_name"] == "FAB"


# --- management extraction ------------------------------------------------------


def test_extract_management_settings_sections() -> None:
    fabric = SimpleNamespace(
        dns_servers=_edges(SimpleNamespace(ip_address=_attr("10.0.0.53/32"), vrf=_attr("MGMT")), None),
        ntp_servers=_edges(SimpleNamespace(name=_attr(None)), SimpleNamespace(name=_attr("ntp1"), iburst=_attr(True))),
        ntp_set_first_server_as_preferred=_attr(True),
        local_users=_edges(
            SimpleNamespace(name=_attr("a"), password_type=_attr("sha512"), password=_attr("$6$h")),
            SimpleNamespace(name=_attr("b"), password_type=_attr("plain"), password=_attr("secret")),
        ),
    )
    result = G._extract_management_settings(fabric)
    assert list(result) == ["dns_servers", "ntp_servers", "ntp_set_first_server_as_preferred", "local_users"]
    assert result["dns_servers"] == [{"ip_address": "10.0.0.53", "vrf": "MGMT"}]
    assert result["ntp_servers"] == [{"name": "ntp1", "iburst": True}]
    assert result["local_users"] == [
        {"name": "a", "privilege": 15, "role": "network-admin", "sha512_password": "$6$h"},
        # A non-sha512 password is never emitted.
        {"name": "b", "privilege": 15, "role": "network-admin", "no_password": True},
    ]
    assert G._extract_management_settings(SimpleNamespace()) == {}


# --- generate() helpers ----------------------------------------------------------


def test_extract_spanning_tree_priorities_and_bgp_passwords() -> None:
    fabric = SimpleNamespace(
        spanning_tree_priorities=_edges(
            None,
            SimpleNamespace(role=_attr("spine"), priority=_attr(0)),
            SimpleNamespace(role=_attr("leaf"), priority=_attr(None)),
        ),
        bgp_evpn_overlay_password=_attr("o"),
        bgp_underlay_password=_attr("u"),
        bgp_mlag_password=None,
    )
    assert G._extract_spanning_tree_priorities(fabric) == {"spine": 0}
    assert G._extract_bgp_passwords(fabric, is_l2leaf=False) == {"evpn_overlay": "o", "underlay": "u", "mlag": None}
    assert G._extract_bgp_passwords(fabric, is_l2leaf=True) == {"evpn_overlay": None, "underlay": None, "mlag": None}


def test_raw_fabric_digs_out_the_fabric_node() -> None:
    raw = {"DcimFabricSwitch": {"edges": [{"node": {"pod": {"node": {"parent": {"node": {"id": "f"}}}}}}]}}
    assert G._raw_fabric(raw) == {"id": "f"}
    assert G._raw_fabric({}) is None
    assert G._raw_fabric(object()) is None


def test_remote_server_device_filters() -> None:
    server = SimpleNamespace(name=_attr("srv1"), role=None, typename__="ComputePhysicalServer")
    local = SimpleNamespace(id="local")
    remote = SimpleNamespace(id="remote", device=SimpleNamespace(node=server))
    assert _remote_server_device(remote, local, skip_l2leaf_endpoints=True) is server
    assert _remote_server_device(None, local, skip_l2leaf_endpoints=True) is None
    # The local interface is one of the link's endpoints.
    assert (
        _remote_server_device(SimpleNamespace(id="local", device=remote.device), local, skip_l2leaf_endpoints=True)
        is None
    )

    # Only physical servers are endpoints, whatever the skip flag says.
    switch = SimpleNamespace(name=_attr("sw"), role=_attr("l2leaf"), typename__="DcimFabricSwitch")
    to_switch = SimpleNamespace(id="r", device=SimpleNamespace(node=switch))
    assert _remote_server_device(to_switch, local, skip_l2leaf_endpoints=False) is None

    # An l2leaf-role remote is dropped only when the caller asks for it.
    l2leaf_server = SimpleNamespace(name=_attr("s2"), role=_attr("l2leaf"), typename__="ComputePhysicalServer")
    to_l2leaf = SimpleNamespace(id="r2", device=SimpleNamespace(node=l2leaf_server))
    assert _remote_server_device(to_l2leaf, local, skip_l2leaf_endpoints=True) is None
    assert _remote_server_device(to_l2leaf, local, skip_l2leaf_endpoints=False) is l2leaf_server
