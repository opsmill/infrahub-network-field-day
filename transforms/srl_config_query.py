from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class SrlConfigQuery(BaseModel):
    target: "SrlConfigQueryTarget"
    dcim_device: "SrlConfigQueryDcimDevice" = Field(alias="DcimDevice")
    wan_site: "SrlConfigQueryWanSite" = Field(alias="WanSite")
    service_l_3_vpn: "SrlConfigQueryServiceL3Vpn" = Field(alias="ServiceL3vpn")
    service_tenant_cloud: "SrlConfigQueryServiceTenantCloud" = Field(
        alias="ServiceTenantCloud"
    )
    network_local_user: "SrlConfigQueryNetworkLocalUser" = Field(
        alias="NetworkLocalUser"
    )
    wan_internet_peering: "SrlConfigQueryWanInternetPeering" = Field(
        alias="WanInternetPeering"
    )
    ipam_ip_address: "SrlConfigQueryIpamIpAddress" = Field(alias="IpamIPAddress")


class SrlConfigQueryTarget(BaseModel):
    edges: list["SrlConfigQueryTargetEdges"]


class SrlConfigQueryTargetEdges(BaseModel):
    node: Optional["SrlConfigQueryTargetEdgesNode"]


class SrlConfigQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["SrlConfigQueryTargetEdgesNodeName"]
    role: Optional["SrlConfigQueryTargetEdgesNodeRole"]
    description: Optional["SrlConfigQueryTargetEdgesNodeDescription"]
    router_id: "SrlConfigQueryTargetEdgesNodeRouterId"
    asn: "SrlConfigQueryTargetEdgesNodeAsn"
    bgp_neighbors: "SrlConfigQueryTargetEdgesNodeBgpNeighbors"
    interfaces: "SrlConfigQueryTargetEdgesNodeInterfaces"


class SrlConfigQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeRole(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeDescription(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeRouterId(BaseModel):
    node: Optional["SrlConfigQueryTargetEdgesNodeRouterIdNode"]


class SrlConfigQueryTargetEdgesNodeRouterIdNode(BaseModel):
    address: Optional["SrlConfigQueryTargetEdgesNodeRouterIdNodeAddress"]


class SrlConfigQueryTargetEdgesNodeRouterIdNodeAddress(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeAsn(BaseModel):
    node: Optional["SrlConfigQueryTargetEdgesNodeAsnNode"]


class SrlConfigQueryTargetEdgesNodeAsnNode(BaseModel):
    asn: Optional["SrlConfigQueryTargetEdgesNodeAsnNodeAsn"]


class SrlConfigQueryTargetEdgesNodeAsnNodeAsn(BaseModel):
    value: Optional[Any]


class SrlConfigQueryTargetEdgesNodeBgpNeighbors(BaseModel):
    edges: list["SrlConfigQueryTargetEdgesNodeBgpNeighborsEdges"]


class SrlConfigQueryTargetEdgesNodeBgpNeighborsEdges(BaseModel):
    node: Optional["SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNode"]


class SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNode(BaseModel):
    peer_address: Optional[
        "SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodePeerAddress"
    ]
    remote_as: Optional["SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodeRemoteAs"]
    description: Optional[
        "SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodeDescription"
    ]


class SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodePeerAddress(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodeRemoteAs(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodeDescription(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeInterfaces(BaseModel):
    edges: Optional[list["SrlConfigQueryTargetEdgesNodeInterfacesEdges"]]


class SrlConfigQueryTargetEdgesNodeInterfacesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeDcimInterface",
                "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysical",
                "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtual",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeDcimInterface(BaseModel):
    typename__: Literal[
        "DcimInterface", "InterfaceLag", "SecurityFirewallInterface"
    ] = Field(alias="__typename")


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysical(BaseModel):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    name: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalName"
    ]
    role: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalRole"
    ]
    mtu: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalMtu"
    ]
    l_2_mode: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalL2Mode"
    ] = Field(alias="l2_mode")
    ip_addresses: (
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddresses"
    )


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalName(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalRole(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalMtu(BaseModel):
    value: Optional[Any]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalL2Mode(
    BaseModel
):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddresses(
    BaseModel
):
    edges: list[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdges"
    ]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdges(
    BaseModel
):
    node: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNode"
    ]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNode(
    BaseModel
):
    address: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNodeAddress"
    ]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNodeAddress(
    BaseModel
):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtual(BaseModel):
    typename__: Literal["InterfaceVirtual"] = Field(alias="__typename")
    name: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualName"
    ]
    role: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualRole"
    ]
    mtu: Optional["SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualMtu"]
    l_2_mode: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualL2Mode"
    ] = Field(alias="l2_mode")
    ip_addresses: (
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddresses"
    )


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualName(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualRole(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualMtu(BaseModel):
    value: Optional[Any]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualL2Mode(BaseModel):
    value: Optional[str]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddresses(
    BaseModel
):
    edges: list[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdges"
    ]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdges(
    BaseModel
):
    node: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNode"
    ]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNode(
    BaseModel
):
    address: Optional[
        "SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNodeAddress"
    ]


class SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNodeAddress(
    BaseModel
):
    value: Optional[str]


class SrlConfigQueryDcimDevice(BaseModel):
    edges: list["SrlConfigQueryDcimDeviceEdges"]


class SrlConfigQueryDcimDeviceEdges(BaseModel):
    node: Optional["SrlConfigQueryDcimDeviceEdgesNode"]


class SrlConfigQueryDcimDeviceEdgesNode(BaseModel):
    name: Optional["SrlConfigQueryDcimDeviceEdgesNodeName"]
    role: Optional["SrlConfigQueryDcimDeviceEdgesNodeRole"]
    router_id: "SrlConfigQueryDcimDeviceEdgesNodeRouterId"
    asn: "SrlConfigQueryDcimDeviceEdgesNodeAsn"
    bgp_neighbors: "SrlConfigQueryDcimDeviceEdgesNodeBgpNeighbors"


class SrlConfigQueryDcimDeviceEdgesNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryDcimDeviceEdgesNodeRole(BaseModel):
    value: Optional[str]


class SrlConfigQueryDcimDeviceEdgesNodeRouterId(BaseModel):
    node: Optional["SrlConfigQueryDcimDeviceEdgesNodeRouterIdNode"]


class SrlConfigQueryDcimDeviceEdgesNodeRouterIdNode(BaseModel):
    address: Optional["SrlConfigQueryDcimDeviceEdgesNodeRouterIdNodeAddress"]


class SrlConfigQueryDcimDeviceEdgesNodeRouterIdNodeAddress(BaseModel):
    value: Optional[str]


class SrlConfigQueryDcimDeviceEdgesNodeAsn(BaseModel):
    node: Optional["SrlConfigQueryDcimDeviceEdgesNodeAsnNode"]


class SrlConfigQueryDcimDeviceEdgesNodeAsnNode(BaseModel):
    asn: Optional["SrlConfigQueryDcimDeviceEdgesNodeAsnNodeAsn"]


class SrlConfigQueryDcimDeviceEdgesNodeAsnNodeAsn(BaseModel):
    value: Optional[Any]


class SrlConfigQueryDcimDeviceEdgesNodeBgpNeighbors(BaseModel):
    edges: list["SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdges"]


class SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdges(BaseModel):
    node: Optional["SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNode"]


class SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNode(BaseModel):
    peer_address: Optional[
        "SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodePeerAddress"
    ]
    remote_as: Optional[
        "SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodeRemoteAs"
    ]
    description: Optional[
        "SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodeDescription"
    ]


class SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodePeerAddress(BaseModel):
    value: Optional[str]


class SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodeRemoteAs(BaseModel):
    value: Optional[str]


class SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodeDescription(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSite(BaseModel):
    edges: list["SrlConfigQueryWanSiteEdges"]


class SrlConfigQueryWanSiteEdges(BaseModel):
    node: Optional["SrlConfigQueryWanSiteEdgesNode"]


class SrlConfigQueryWanSiteEdgesNode(BaseModel):
    name: Optional["SrlConfigQueryWanSiteEdgesNodeName"]
    attachment_kind: Optional["SrlConfigQueryWanSiteEdgesNodeAttachmentKind"]
    site_asn: Optional["SrlConfigQueryWanSiteEdgesNodeSiteAsn"]
    tenant: "SrlConfigQueryWanSiteEdgesNodeTenant"
    lan_prefix: "SrlConfigQueryWanSiteEdgesNodeLanPrefix"
    bgp_sessions: "SrlConfigQueryWanSiteEdgesNodeBgpSessions"
    static_routes: "SrlConfigQueryWanSiteEdgesNodeStaticRoutes"


class SrlConfigQueryWanSiteEdgesNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeAttachmentKind(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeSiteAsn(BaseModel):
    value: Optional[Any]


class SrlConfigQueryWanSiteEdgesNodeTenant(BaseModel):
    node: Optional["SrlConfigQueryWanSiteEdgesNodeTenantNode"]


class SrlConfigQueryWanSiteEdgesNodeTenantNode(BaseModel):
    name: Optional["SrlConfigQueryWanSiteEdgesNodeTenantNodeName"]


class SrlConfigQueryWanSiteEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeLanPrefix(BaseModel):
    node: Optional["SrlConfigQueryWanSiteEdgesNodeLanPrefixNode"]


class SrlConfigQueryWanSiteEdgesNodeLanPrefixNode(BaseModel):
    prefix: Optional["SrlConfigQueryWanSiteEdgesNodeLanPrefixNodePrefix"]


class SrlConfigQueryWanSiteEdgesNodeLanPrefixNodePrefix(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeBgpSessions(BaseModel):
    edges: list["SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdges"]


class SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdges(BaseModel):
    node: Optional["SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode"]


class SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode(BaseModel):
    peer_address: Optional[
        "SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodePeerAddress"
    ]
    remote_as: Optional["SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeRemoteAs"]
    device: "SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice"


class SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodePeerAddress(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeRemoteAs(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice(BaseModel):
    node: Optional["SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode"]


class SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode(BaseModel):
    name: Optional["SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeName"]
    role: Optional["SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeRole"]


class SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeRole(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeStaticRoutes(BaseModel):
    edges: list["SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdges"]


class SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdges(BaseModel):
    node: Optional["SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNode"]


class SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNode(BaseModel):
    prefix: Optional["SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNodePrefix"]
    next_hop: Optional["SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNodeNextHop"]


class SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNodePrefix(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNodeNextHop(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceL3Vpn(BaseModel):
    edges: list["SrlConfigQueryServiceL3VpnEdges"]


class SrlConfigQueryServiceL3VpnEdges(BaseModel):
    node: Optional["SrlConfigQueryServiceL3VpnEdgesNode"]


class SrlConfigQueryServiceL3VpnEdgesNode(BaseModel):
    name: Optional["SrlConfigQueryServiceL3VpnEdgesNodeName"]
    status: Optional["SrlConfigQueryServiceL3VpnEdgesNodeStatus"]
    tenant: "SrlConfigQueryServiceL3VpnEdgesNodeTenant"
    vrf: "SrlConfigQueryServiceL3VpnEdgesNodeVrf"
    dc_service_prefixes: "SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixes"


class SrlConfigQueryServiceL3VpnEdgesNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceL3VpnEdgesNodeStatus(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceL3VpnEdgesNodeTenant(BaseModel):
    node: Optional["SrlConfigQueryServiceL3VpnEdgesNodeTenantNode"]


class SrlConfigQueryServiceL3VpnEdgesNodeTenantNode(BaseModel):
    name: Optional["SrlConfigQueryServiceL3VpnEdgesNodeTenantNodeName"]


class SrlConfigQueryServiceL3VpnEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceL3VpnEdgesNodeVrf(BaseModel):
    node: Optional["SrlConfigQueryServiceL3VpnEdgesNodeVrfNode"]


class SrlConfigQueryServiceL3VpnEdgesNodeVrfNode(BaseModel):
    name: Optional["SrlConfigQueryServiceL3VpnEdgesNodeVrfNodeName"]


class SrlConfigQueryServiceL3VpnEdgesNodeVrfNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixes(BaseModel):
    edges: list["SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges"]


class SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges(BaseModel):
    node: Optional["SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode"]


class SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode(BaseModel):
    prefix: Optional[
        "SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNodePrefix"
    ]


class SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNodePrefix(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceTenantCloud(BaseModel):
    edges: list["SrlConfigQueryServiceTenantCloudEdges"]


class SrlConfigQueryServiceTenantCloudEdges(BaseModel):
    node: Optional["SrlConfigQueryServiceTenantCloudEdgesNode"]


class SrlConfigQueryServiceTenantCloudEdgesNode(BaseModel):
    name: Optional["SrlConfigQueryServiceTenantCloudEdgesNodeName"]
    status: Optional["SrlConfigQueryServiceTenantCloudEdgesNodeStatus"]
    tenant: "SrlConfigQueryServiceTenantCloudEdgesNodeTenant"
    prefix: "SrlConfigQueryServiceTenantCloudEdgesNodePrefix"


class SrlConfigQueryServiceTenantCloudEdgesNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceTenantCloudEdgesNodeStatus(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceTenantCloudEdgesNodeTenant(BaseModel):
    node: Optional["SrlConfigQueryServiceTenantCloudEdgesNodeTenantNode"]


class SrlConfigQueryServiceTenantCloudEdgesNodeTenantNode(BaseModel):
    name: Optional["SrlConfigQueryServiceTenantCloudEdgesNodeTenantNodeName"]


class SrlConfigQueryServiceTenantCloudEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryServiceTenantCloudEdgesNodePrefix(BaseModel):
    node: Optional["SrlConfigQueryServiceTenantCloudEdgesNodePrefixNode"]


class SrlConfigQueryServiceTenantCloudEdgesNodePrefixNode(BaseModel):
    prefix: Optional["SrlConfigQueryServiceTenantCloudEdgesNodePrefixNodePrefix"]


class SrlConfigQueryServiceTenantCloudEdgesNodePrefixNodePrefix(BaseModel):
    value: Optional[str]


class SrlConfigQueryNetworkLocalUser(BaseModel):
    edges: list["SrlConfigQueryNetworkLocalUserEdges"]


class SrlConfigQueryNetworkLocalUserEdges(BaseModel):
    node: Optional["SrlConfigQueryNetworkLocalUserEdgesNode"]


class SrlConfigQueryNetworkLocalUserEdgesNode(BaseModel):
    name: Optional["SrlConfigQueryNetworkLocalUserEdgesNodeName"]
    password_type: Optional["SrlConfigQueryNetworkLocalUserEdgesNodePasswordType"]
    password: Optional["SrlConfigQueryNetworkLocalUserEdgesNodePassword"]


class SrlConfigQueryNetworkLocalUserEdgesNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryNetworkLocalUserEdgesNodePasswordType(BaseModel):
    value: Optional[str]


class SrlConfigQueryNetworkLocalUserEdgesNodePassword(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanInternetPeering(BaseModel):
    edges: list["SrlConfigQueryWanInternetPeeringEdges"]


class SrlConfigQueryWanInternetPeeringEdges(BaseModel):
    node: Optional["SrlConfigQueryWanInternetPeeringEdgesNode"]


class SrlConfigQueryWanInternetPeeringEdgesNode(BaseModel):
    name: Optional["SrlConfigQueryWanInternetPeeringEdgesNodeName"]
    peer_asn: Optional["SrlConfigQueryWanInternetPeeringEdgesNodePeerAsn"]
    customer_aggregate: "SrlConfigQueryWanInternetPeeringEdgesNodeCustomerAggregate"
    internet_prefixes: "SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixes"


class SrlConfigQueryWanInternetPeeringEdgesNodeName(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanInternetPeeringEdgesNodePeerAsn(BaseModel):
    value: Optional[Any]


class SrlConfigQueryWanInternetPeeringEdgesNodeCustomerAggregate(BaseModel):
    node: Optional["SrlConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNode"]


class SrlConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNode(BaseModel):
    prefix: Optional[
        "SrlConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNodePrefix"
    ]


class SrlConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNodePrefix(BaseModel):
    value: Optional[str]


class SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixes(BaseModel):
    edges: list["SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdges"]


class SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdges(BaseModel):
    node: Optional["SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNode"]


class SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNode(BaseModel):
    prefix: Optional[
        "SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNodePrefix"
    ]


class SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNodePrefix(
    BaseModel
):
    value: Optional[str]


class SrlConfigQueryIpamIpAddress(BaseModel):
    edges: list["SrlConfigQueryIpamIpAddressEdges"]


class SrlConfigQueryIpamIpAddressEdges(BaseModel):
    node: Optional["SrlConfigQueryIpamIpAddressEdgesNode"]


class SrlConfigQueryIpamIpAddressEdgesNode(BaseModel):
    address: Optional["SrlConfigQueryIpamIpAddressEdgesNodeAddress"]
    interface: "SrlConfigQueryIpamIpAddressEdgesNodeInterface"


class SrlConfigQueryIpamIpAddressEdgesNodeAddress(BaseModel):
    value: Optional[str]


class SrlConfigQueryIpamIpAddressEdgesNodeInterface(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceLayer3",
                "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical",
                "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceLayer3(BaseModel):
    typename__: Literal["InterfaceLag", "InterfaceLayer3"] = Field(alias="__typename")


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical(BaseModel):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    name: Optional[
        "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalName"
    ]
    role: Optional[
        "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalRole"
    ]
    device: "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice"


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalName(BaseModel):
    value: Optional[str]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalRole(BaseModel):
    value: Optional[str]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode"
    ]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer",
        "DcimDevice",
        "DcimFabricSwitch",
        "DcimGenericDevice",
        "SecurityFirewall",
    ] = Field(alias="__typename")
    name: Optional[
        "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNodeName"
    ]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual(BaseModel):
    typename__: Literal["InterfaceVirtual"] = Field(alias="__typename")
    name: Optional[
        "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualName"
    ]
    role: Optional[
        "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualRole"
    ]
    device: "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice"


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualName(BaseModel):
    value: Optional[str]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualRole(BaseModel):
    value: Optional[str]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice(
    BaseModel
):
    node: Optional[
        "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode"
    ]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer",
        "DcimDevice",
        "DcimFabricSwitch",
        "DcimGenericDevice",
        "SecurityFirewall",
    ] = Field(alias="__typename")
    name: Optional[
        "SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNodeName"
    ]


class SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNodeName(
    BaseModel
):
    value: Optional[str]


SrlConfigQuery.model_rebuild()
SrlConfigQueryTarget.model_rebuild()
SrlConfigQueryTargetEdges.model_rebuild()
SrlConfigQueryTargetEdgesNode.model_rebuild()
SrlConfigQueryTargetEdgesNodeRouterId.model_rebuild()
SrlConfigQueryTargetEdgesNodeRouterIdNode.model_rebuild()
SrlConfigQueryTargetEdgesNodeAsn.model_rebuild()
SrlConfigQueryTargetEdgesNodeAsnNode.model_rebuild()
SrlConfigQueryTargetEdgesNodeBgpNeighbors.model_rebuild()
SrlConfigQueryTargetEdgesNodeBgpNeighborsEdges.model_rebuild()
SrlConfigQueryTargetEdgesNodeBgpNeighborsEdgesNode.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfaces.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdges.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysical.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddresses.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdges.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNode.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtual.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddresses.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdges.model_rebuild()
SrlConfigQueryTargetEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNode.model_rebuild()
SrlConfigQueryDcimDevice.model_rebuild()
SrlConfigQueryDcimDeviceEdges.model_rebuild()
SrlConfigQueryDcimDeviceEdgesNode.model_rebuild()
SrlConfigQueryDcimDeviceEdgesNodeRouterId.model_rebuild()
SrlConfigQueryDcimDeviceEdgesNodeRouterIdNode.model_rebuild()
SrlConfigQueryDcimDeviceEdgesNodeAsn.model_rebuild()
SrlConfigQueryDcimDeviceEdgesNodeAsnNode.model_rebuild()
SrlConfigQueryDcimDeviceEdgesNodeBgpNeighbors.model_rebuild()
SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdges.model_rebuild()
SrlConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNode.model_rebuild()
SrlConfigQueryWanSite.model_rebuild()
SrlConfigQueryWanSiteEdges.model_rebuild()
SrlConfigQueryWanSiteEdgesNode.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeTenant.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeTenantNode.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeLanPrefix.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeLanPrefixNode.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeBgpSessions.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdges.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeStaticRoutes.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdges.model_rebuild()
SrlConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNode.model_rebuild()
SrlConfigQueryServiceL3Vpn.model_rebuild()
SrlConfigQueryServiceL3VpnEdges.model_rebuild()
SrlConfigQueryServiceL3VpnEdgesNode.model_rebuild()
SrlConfigQueryServiceL3VpnEdgesNodeTenant.model_rebuild()
SrlConfigQueryServiceL3VpnEdgesNodeTenantNode.model_rebuild()
SrlConfigQueryServiceL3VpnEdgesNodeVrf.model_rebuild()
SrlConfigQueryServiceL3VpnEdgesNodeVrfNode.model_rebuild()
SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixes.model_rebuild()
SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges.model_rebuild()
SrlConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode.model_rebuild()
SrlConfigQueryServiceTenantCloud.model_rebuild()
SrlConfigQueryServiceTenantCloudEdges.model_rebuild()
SrlConfigQueryServiceTenantCloudEdgesNode.model_rebuild()
SrlConfigQueryServiceTenantCloudEdgesNodeTenant.model_rebuild()
SrlConfigQueryServiceTenantCloudEdgesNodeTenantNode.model_rebuild()
SrlConfigQueryServiceTenantCloudEdgesNodePrefix.model_rebuild()
SrlConfigQueryServiceTenantCloudEdgesNodePrefixNode.model_rebuild()
SrlConfigQueryNetworkLocalUser.model_rebuild()
SrlConfigQueryNetworkLocalUserEdges.model_rebuild()
SrlConfigQueryNetworkLocalUserEdgesNode.model_rebuild()
SrlConfigQueryWanInternetPeering.model_rebuild()
SrlConfigQueryWanInternetPeeringEdges.model_rebuild()
SrlConfigQueryWanInternetPeeringEdgesNode.model_rebuild()
SrlConfigQueryWanInternetPeeringEdgesNodeCustomerAggregate.model_rebuild()
SrlConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNode.model_rebuild()
SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixes.model_rebuild()
SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdges.model_rebuild()
SrlConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNode.model_rebuild()
SrlConfigQueryIpamIpAddress.model_rebuild()
SrlConfigQueryIpamIpAddressEdges.model_rebuild()
SrlConfigQueryIpamIpAddressEdgesNode.model_rebuild()
SrlConfigQueryIpamIpAddressEdgesNodeInterface.model_rebuild()
SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical.model_rebuild()
SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice.model_rebuild()
SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode.model_rebuild()
SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual.model_rebuild()
SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice.model_rebuild()
SrlConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode.model_rebuild()
