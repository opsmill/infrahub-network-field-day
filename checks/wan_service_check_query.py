from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class WanServiceCheckQuery(BaseModel):
    service_l_3_vpn: "WanServiceCheckQueryServiceL3Vpn" = Field(alias="ServiceL3vpn")
    service_tenant_cloud: "WanServiceCheckQueryServiceTenantCloud" = Field(
        alias="ServiceTenantCloud"
    )
    wan_site: "WanServiceCheckQueryWanSite" = Field(alias="WanSite")
    dcim_device: "WanServiceCheckQueryDcimDevice" = Field(alias="DcimDevice")
    wan_internet_peering: "WanServiceCheckQueryWanInternetPeering" = Field(
        alias="WanInternetPeering"
    )
    ipam_ip_address: "WanServiceCheckQueryIpamIpAddress" = Field(alias="IpamIPAddress")


class WanServiceCheckQueryServiceL3Vpn(BaseModel):
    edges: list["WanServiceCheckQueryServiceL3VpnEdges"]


class WanServiceCheckQueryServiceL3VpnEdges(BaseModel):
    node: Optional["WanServiceCheckQueryServiceL3VpnEdgesNode"]


class WanServiceCheckQueryServiceL3VpnEdgesNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryServiceL3VpnEdgesNodeName"]
    status: Optional["WanServiceCheckQueryServiceL3VpnEdgesNodeStatus"]
    tenant: "WanServiceCheckQueryServiceL3VpnEdgesNodeTenant"
    vrf: "WanServiceCheckQueryServiceL3VpnEdgesNodeVrf"
    dc_service_prefixes: "WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixes"
    circuits: "WanServiceCheckQueryServiceL3VpnEdgesNodeCircuits"


class WanServiceCheckQueryServiceL3VpnEdgesNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceL3VpnEdgesNodeStatus(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceL3VpnEdgesNodeTenant(BaseModel):
    node: Optional["WanServiceCheckQueryServiceL3VpnEdgesNodeTenantNode"]


class WanServiceCheckQueryServiceL3VpnEdgesNodeTenantNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryServiceL3VpnEdgesNodeTenantNodeName"]


class WanServiceCheckQueryServiceL3VpnEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceL3VpnEdgesNodeVrf(BaseModel):
    node: Optional["WanServiceCheckQueryServiceL3VpnEdgesNodeVrfNode"]


class WanServiceCheckQueryServiceL3VpnEdgesNodeVrfNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryServiceL3VpnEdgesNodeVrfNodeName"]


class WanServiceCheckQueryServiceL3VpnEdgesNodeVrfNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixes(BaseModel):
    edges: list["WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges"]


class WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges(BaseModel):
    node: Optional[
        "WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode"
    ]


class WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode(BaseModel):
    prefix: Optional[
        "WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNodePrefix"
    ]


class WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNodePrefix(
    BaseModel
):
    value: Optional[str]


class WanServiceCheckQueryServiceL3VpnEdgesNodeCircuits(BaseModel):
    edges: list["WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdges"]


class WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdges(BaseModel):
    node: Optional["WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNode"]


class WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNode(BaseModel):
    id: str
    circuit_id: Optional[
        "WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeCircuitId"
    ]
    tenant: "WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeTenant"


class WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeCircuitId(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeTenant(BaseModel):
    node: Optional[
        "WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeTenantNode"
    ]


class WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeTenantNode(BaseModel):
    id: str
    name: Optional[
        "WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeTenantNodeName"
    ]


class WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeTenantNodeName(
    BaseModel
):
    value: Optional[str]


class WanServiceCheckQueryServiceTenantCloud(BaseModel):
    edges: list["WanServiceCheckQueryServiceTenantCloudEdges"]


class WanServiceCheckQueryServiceTenantCloudEdges(BaseModel):
    node: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNode"]


class WanServiceCheckQueryServiceTenantCloudEdgesNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeName"]
    status: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeStatus"]
    tenant: "WanServiceCheckQueryServiceTenantCloudEdgesNodeTenant"
    vrf: "WanServiceCheckQueryServiceTenantCloudEdgesNodeVrf"
    zone: "WanServiceCheckQueryServiceTenantCloudEdgesNodeZone"
    prefix: "WanServiceCheckQueryServiceTenantCloudEdgesNodePrefix"


class WanServiceCheckQueryServiceTenantCloudEdgesNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeStatus(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeTenant(BaseModel):
    node: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeTenantNode"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeTenantNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeTenantNodeName"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeVrf(BaseModel):
    node: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeVrfNode"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeVrfNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeVrfNodeName"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeVrfNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeZone(BaseModel):
    node: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNode"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeName"]
    vrf: "WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeVrf"


class WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeVrf(BaseModel):
    node: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeVrfNode"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeVrfNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeVrfNodeName"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeVrfNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryServiceTenantCloudEdgesNodePrefix(BaseModel):
    node: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodePrefixNode"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodePrefixNode(BaseModel):
    id: str
    prefix: Optional["WanServiceCheckQueryServiceTenantCloudEdgesNodePrefixNodePrefix"]


class WanServiceCheckQueryServiceTenantCloudEdgesNodePrefixNodePrefix(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanSite(BaseModel):
    edges: list["WanServiceCheckQueryWanSiteEdges"]


class WanServiceCheckQueryWanSiteEdges(BaseModel):
    node: Optional["WanServiceCheckQueryWanSiteEdgesNode"]


class WanServiceCheckQueryWanSiteEdgesNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryWanSiteEdgesNodeName"]
    attachment_kind: Optional["WanServiceCheckQueryWanSiteEdgesNodeAttachmentKind"]
    site_asn: Optional["WanServiceCheckQueryWanSiteEdgesNodeSiteAsn"]
    tenant: "WanServiceCheckQueryWanSiteEdgesNodeTenant"
    lan_prefix: "WanServiceCheckQueryWanSiteEdgesNodeLanPrefix"
    bgp_sessions: "WanServiceCheckQueryWanSiteEdgesNodeBgpSessions"
    static_routes: "WanServiceCheckQueryWanSiteEdgesNodeStaticRoutes"


class WanServiceCheckQueryWanSiteEdgesNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanSiteEdgesNodeAttachmentKind(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanSiteEdgesNodeSiteAsn(BaseModel):
    value: Optional[Any]


class WanServiceCheckQueryWanSiteEdgesNodeTenant(BaseModel):
    node: Optional["WanServiceCheckQueryWanSiteEdgesNodeTenantNode"]


class WanServiceCheckQueryWanSiteEdgesNodeTenantNode(BaseModel):
    id: str
    name: Optional["WanServiceCheckQueryWanSiteEdgesNodeTenantNodeName"]


class WanServiceCheckQueryWanSiteEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanSiteEdgesNodeLanPrefix(BaseModel):
    node: Optional["WanServiceCheckQueryWanSiteEdgesNodeLanPrefixNode"]


class WanServiceCheckQueryWanSiteEdgesNodeLanPrefixNode(BaseModel):
    prefix: Optional["WanServiceCheckQueryWanSiteEdgesNodeLanPrefixNodePrefix"]


class WanServiceCheckQueryWanSiteEdgesNodeLanPrefixNodePrefix(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanSiteEdgesNodeBgpSessions(BaseModel):
    edges: list["WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdges"]


class WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdges(BaseModel):
    node: Optional["WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNode"]


class WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNode(BaseModel):
    peer_address: Optional[
        "WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodePeerAddress"
    ]
    device: "WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice"


class WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodePeerAddress(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice(BaseModel):
    node: Optional["WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode"]


class WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode(BaseModel):
    name: Optional[
        "WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeName"
    ]
    role: Optional[
        "WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeRole"
    ]


class WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeRole(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanSiteEdgesNodeStaticRoutes(BaseModel):
    edges: list["WanServiceCheckQueryWanSiteEdgesNodeStaticRoutesEdges"]


class WanServiceCheckQueryWanSiteEdgesNodeStaticRoutesEdges(BaseModel):
    node: Optional["WanServiceCheckQueryWanSiteEdgesNodeStaticRoutesEdgesNode"]


class WanServiceCheckQueryWanSiteEdgesNodeStaticRoutesEdgesNode(BaseModel):
    next_hop: Optional[
        "WanServiceCheckQueryWanSiteEdgesNodeStaticRoutesEdgesNodeNextHop"
    ]


class WanServiceCheckQueryWanSiteEdgesNodeStaticRoutesEdgesNodeNextHop(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryDcimDevice(BaseModel):
    edges: list["WanServiceCheckQueryDcimDeviceEdges"]


class WanServiceCheckQueryDcimDeviceEdges(BaseModel):
    node: Optional["WanServiceCheckQueryDcimDeviceEdgesNode"]


class WanServiceCheckQueryDcimDeviceEdgesNode(BaseModel):
    name: Optional["WanServiceCheckQueryDcimDeviceEdgesNodeName"]
    role: Optional["WanServiceCheckQueryDcimDeviceEdgesNodeRole"]
    router_id: "WanServiceCheckQueryDcimDeviceEdgesNodeRouterId"
    member_of_groups: "WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroups"
    interfaces: "WanServiceCheckQueryDcimDeviceEdgesNodeInterfaces"


class WanServiceCheckQueryDcimDeviceEdgesNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryDcimDeviceEdgesNodeRole(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryDcimDeviceEdgesNodeRouterId(BaseModel):
    node: Optional["WanServiceCheckQueryDcimDeviceEdgesNodeRouterIdNode"]


class WanServiceCheckQueryDcimDeviceEdgesNodeRouterIdNode(BaseModel):
    address: Optional["WanServiceCheckQueryDcimDeviceEdgesNodeRouterIdNodeAddress"]


class WanServiceCheckQueryDcimDeviceEdgesNodeRouterIdNodeAddress(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroups(BaseModel):
    edges: Optional[list["WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroupsEdges"]]


class WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroupsEdges(BaseModel):
    node: Optional["WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroupsEdgesNode"]


class WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroupsEdgesNode(BaseModel):
    typename__: Literal[
        "CoreAccountGroup",
        "CoreGeneratorAwareGroup",
        "CoreGeneratorGroup",
        "CoreGraphQLQueryGroup",
        "CoreGroup",
        "CoreRepositoryGroup",
        "CoreStandardGroup",
    ] = Field(alias="__typename")
    name: Optional["WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroupsEdgesNodeName"]


class WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroupsEdgesNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfaces(BaseModel):
    edges: Optional[list["WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdges"]]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeDcimInterface",
                "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysical",
                "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtual",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeDcimInterface(
    BaseModel
):
    typename__: Literal[
        "DcimInterface", "InterfaceLag", "SecurityFirewallInterface"
    ] = Field(alias="__typename")


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    name: Optional[
        "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalName"
    ]
    ip_addresses: "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddresses"


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalName(
    BaseModel
):
    value: Optional[str]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddresses(
    BaseModel
):
    edges: list[
        "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdges"
    ]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdges(
    BaseModel
):
    node: Optional[
        "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNode"
    ]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNode(
    BaseModel
):
    address: Optional[
        "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNodeAddress"
    ]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNodeAddress(
    BaseModel
):
    value: Optional[str]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtual(
    BaseModel
):
    typename__: Literal["InterfaceVirtual"] = Field(alias="__typename")
    name: Optional[
        "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualName"
    ]
    ip_addresses: "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddresses"


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualName(
    BaseModel
):
    value: Optional[str]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddresses(
    BaseModel
):
    edges: list[
        "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdges"
    ]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdges(
    BaseModel
):
    node: Optional[
        "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNode"
    ]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNode(
    BaseModel
):
    address: Optional[
        "WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNodeAddress"
    ]


class WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNodeAddress(
    BaseModel
):
    value: Optional[str]


class WanServiceCheckQueryWanInternetPeering(BaseModel):
    edges: list["WanServiceCheckQueryWanInternetPeeringEdges"]


class WanServiceCheckQueryWanInternetPeeringEdges(BaseModel):
    node: Optional["WanServiceCheckQueryWanInternetPeeringEdgesNode"]


class WanServiceCheckQueryWanInternetPeeringEdgesNode(BaseModel):
    name: Optional["WanServiceCheckQueryWanInternetPeeringEdgesNodeName"]
    customer_aggregate: (
        "WanServiceCheckQueryWanInternetPeeringEdgesNodeCustomerAggregate"
    )


class WanServiceCheckQueryWanInternetPeeringEdgesNodeName(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryWanInternetPeeringEdgesNodeCustomerAggregate(BaseModel):
    node: Optional[
        "WanServiceCheckQueryWanInternetPeeringEdgesNodeCustomerAggregateNode"
    ]


class WanServiceCheckQueryWanInternetPeeringEdgesNodeCustomerAggregateNode(BaseModel):
    prefix: Optional[
        "WanServiceCheckQueryWanInternetPeeringEdgesNodeCustomerAggregateNodePrefix"
    ]


class WanServiceCheckQueryWanInternetPeeringEdgesNodeCustomerAggregateNodePrefix(
    BaseModel
):
    value: Optional[str]


class WanServiceCheckQueryIpamIpAddress(BaseModel):
    edges: list["WanServiceCheckQueryIpamIpAddressEdges"]


class WanServiceCheckQueryIpamIpAddressEdges(BaseModel):
    node: Optional["WanServiceCheckQueryIpamIpAddressEdgesNode"]


class WanServiceCheckQueryIpamIpAddressEdgesNode(BaseModel):
    address: Optional["WanServiceCheckQueryIpamIpAddressEdgesNodeAddress"]
    interface: "WanServiceCheckQueryIpamIpAddressEdgesNodeInterface"


class WanServiceCheckQueryIpamIpAddressEdgesNodeAddress(BaseModel):
    value: Optional[str]


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterface(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceLayer3",
                "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical",
                "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceLayer3(BaseModel):
    typename__: Literal["InterfaceLag", "InterfaceLayer3"] = Field(alias="__typename")


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    device: (
        "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice"
    )


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode"
    ]


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode(
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
        "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNodeName"
    ]


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual(
    BaseModel
):
    typename__: Literal["InterfaceVirtual"] = Field(alias="__typename")
    device: (
        "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice"
    )


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice(
    BaseModel
):
    node: Optional[
        "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode"
    ]


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode(
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
        "WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNodeName"
    ]


class WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNodeName(
    BaseModel
):
    value: Optional[str]


WanServiceCheckQuery.model_rebuild()
WanServiceCheckQueryServiceL3Vpn.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdges.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNode.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeTenant.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeTenantNode.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeVrf.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeVrfNode.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixes.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeCircuits.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdges.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNode.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeTenant.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeCircuitsEdgesNodeTenantNode.model_rebuild()
WanServiceCheckQueryServiceTenantCloud.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdges.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNode.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodeTenant.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodeTenantNode.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodeVrf.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodeVrfNode.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodeZone.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNode.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeVrf.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodeZoneNodeVrfNode.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodePrefix.model_rebuild()
WanServiceCheckQueryServiceTenantCloudEdgesNodePrefixNode.model_rebuild()
WanServiceCheckQueryWanSite.model_rebuild()
WanServiceCheckQueryWanSiteEdges.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNode.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeTenant.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeTenantNode.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeLanPrefix.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeLanPrefixNode.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeBgpSessions.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdges.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNode.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeStaticRoutes.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeStaticRoutesEdges.model_rebuild()
WanServiceCheckQueryWanSiteEdgesNodeStaticRoutesEdgesNode.model_rebuild()
WanServiceCheckQueryDcimDevice.model_rebuild()
WanServiceCheckQueryDcimDeviceEdges.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNode.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeRouterId.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeRouterIdNode.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroups.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroupsEdges.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeMemberOfGroupsEdgesNode.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfaces.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdges.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysical.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddresses.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdges.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfacePhysicalIpAddressesEdgesNode.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtual.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddresses.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdges.model_rebuild()
WanServiceCheckQueryDcimDeviceEdgesNodeInterfacesEdgesNodeInterfaceVirtualIpAddressesEdgesNode.model_rebuild()
WanServiceCheckQueryWanInternetPeering.model_rebuild()
WanServiceCheckQueryWanInternetPeeringEdges.model_rebuild()
WanServiceCheckQueryWanInternetPeeringEdgesNode.model_rebuild()
WanServiceCheckQueryWanInternetPeeringEdgesNodeCustomerAggregate.model_rebuild()
WanServiceCheckQueryWanInternetPeeringEdgesNodeCustomerAggregateNode.model_rebuild()
WanServiceCheckQueryIpamIpAddress.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdges.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdgesNode.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdgesNodeInterface.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice.model_rebuild()
WanServiceCheckQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode.model_rebuild()
