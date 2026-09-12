from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class FrrConfigQuery(BaseModel):
    target: "FrrConfigQueryTarget"
    dcim_device: "FrrConfigQueryDcimDevice" = Field(alias="DcimDevice")
    wan_site: "FrrConfigQueryWanSite" = Field(alias="WanSite")
    service_l_3_vpn: "FrrConfigQueryServiceL3Vpn" = Field(alias="ServiceL3vpn")
    service_tenant_cloud: "FrrConfigQueryServiceTenantCloud" = Field(
        alias="ServiceTenantCloud"
    )
    service_internet_access: "FrrConfigQueryServiceInternetAccess" = Field(
        alias="ServiceInternetAccess"
    )
    wan_internet_peering: "FrrConfigQueryWanInternetPeering" = Field(
        alias="WanInternetPeering"
    )
    ipam_ip_address: "FrrConfigQueryIpamIpAddress" = Field(alias="IpamIPAddress")


class FrrConfigQueryTarget(BaseModel):
    edges: list["FrrConfigQueryTargetEdges"]


class FrrConfigQueryTargetEdges(BaseModel):
    node: Optional["FrrConfigQueryTargetEdgesNode"]


class FrrConfigQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["FrrConfigQueryTargetEdgesNodeName"]
    role: Optional["FrrConfigQueryTargetEdgesNodeRole"]
    description: Optional["FrrConfigQueryTargetEdgesNodeDescription"]
    router_id: "FrrConfigQueryTargetEdgesNodeRouterId"
    asn: "FrrConfigQueryTargetEdgesNodeAsn"
    bgp_neighbors: "FrrConfigQueryTargetEdgesNodeBgpNeighbors"


class FrrConfigQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryTargetEdgesNodeRole(BaseModel):
    value: Optional[str]


class FrrConfigQueryTargetEdgesNodeDescription(BaseModel):
    value: Optional[str]


class FrrConfigQueryTargetEdgesNodeRouterId(BaseModel):
    node: Optional["FrrConfigQueryTargetEdgesNodeRouterIdNode"]


class FrrConfigQueryTargetEdgesNodeRouterIdNode(BaseModel):
    address: Optional["FrrConfigQueryTargetEdgesNodeRouterIdNodeAddress"]


class FrrConfigQueryTargetEdgesNodeRouterIdNodeAddress(BaseModel):
    value: Optional[str]


class FrrConfigQueryTargetEdgesNodeAsn(BaseModel):
    node: Optional["FrrConfigQueryTargetEdgesNodeAsnNode"]


class FrrConfigQueryTargetEdgesNodeAsnNode(BaseModel):
    asn: Optional["FrrConfigQueryTargetEdgesNodeAsnNodeAsn"]


class FrrConfigQueryTargetEdgesNodeAsnNodeAsn(BaseModel):
    value: Optional[Any]


class FrrConfigQueryTargetEdgesNodeBgpNeighbors(BaseModel):
    edges: list["FrrConfigQueryTargetEdgesNodeBgpNeighborsEdges"]


class FrrConfigQueryTargetEdgesNodeBgpNeighborsEdges(BaseModel):
    node: Optional["FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNode"]


class FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNode(BaseModel):
    peer_address: Optional[
        "FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodePeerAddress"
    ]
    remote_as: Optional["FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodeRemoteAs"]
    description: Optional[
        "FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodeDescription"
    ]


class FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodePeerAddress(BaseModel):
    value: Optional[str]


class FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodeRemoteAs(BaseModel):
    value: Optional[str]


class FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNodeDescription(BaseModel):
    value: Optional[str]


class FrrConfigQueryDcimDevice(BaseModel):
    edges: list["FrrConfigQueryDcimDeviceEdges"]


class FrrConfigQueryDcimDeviceEdges(BaseModel):
    node: Optional["FrrConfigQueryDcimDeviceEdgesNode"]


class FrrConfigQueryDcimDeviceEdgesNode(BaseModel):
    name: Optional["FrrConfigQueryDcimDeviceEdgesNodeName"]
    role: Optional["FrrConfigQueryDcimDeviceEdgesNodeRole"]
    router_id: "FrrConfigQueryDcimDeviceEdgesNodeRouterId"
    asn: "FrrConfigQueryDcimDeviceEdgesNodeAsn"
    bgp_neighbors: "FrrConfigQueryDcimDeviceEdgesNodeBgpNeighbors"


class FrrConfigQueryDcimDeviceEdgesNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryDcimDeviceEdgesNodeRole(BaseModel):
    value: Optional[str]


class FrrConfigQueryDcimDeviceEdgesNodeRouterId(BaseModel):
    node: Optional["FrrConfigQueryDcimDeviceEdgesNodeRouterIdNode"]


class FrrConfigQueryDcimDeviceEdgesNodeRouterIdNode(BaseModel):
    address: Optional["FrrConfigQueryDcimDeviceEdgesNodeRouterIdNodeAddress"]


class FrrConfigQueryDcimDeviceEdgesNodeRouterIdNodeAddress(BaseModel):
    value: Optional[str]


class FrrConfigQueryDcimDeviceEdgesNodeAsn(BaseModel):
    node: Optional["FrrConfigQueryDcimDeviceEdgesNodeAsnNode"]


class FrrConfigQueryDcimDeviceEdgesNodeAsnNode(BaseModel):
    asn: Optional["FrrConfigQueryDcimDeviceEdgesNodeAsnNodeAsn"]


class FrrConfigQueryDcimDeviceEdgesNodeAsnNodeAsn(BaseModel):
    value: Optional[Any]


class FrrConfigQueryDcimDeviceEdgesNodeBgpNeighbors(BaseModel):
    edges: list["FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdges"]


class FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdges(BaseModel):
    node: Optional["FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNode"]


class FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNode(BaseModel):
    peer_address: Optional[
        "FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodePeerAddress"
    ]
    remote_as: Optional[
        "FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodeRemoteAs"
    ]
    description: Optional[
        "FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodeDescription"
    ]


class FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodePeerAddress(BaseModel):
    value: Optional[str]


class FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodeRemoteAs(BaseModel):
    value: Optional[str]


class FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNodeDescription(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSite(BaseModel):
    edges: list["FrrConfigQueryWanSiteEdges"]


class FrrConfigQueryWanSiteEdges(BaseModel):
    node: Optional["FrrConfigQueryWanSiteEdgesNode"]


class FrrConfigQueryWanSiteEdgesNode(BaseModel):
    name: Optional["FrrConfigQueryWanSiteEdgesNodeName"]
    attachment_kind: Optional["FrrConfigQueryWanSiteEdgesNodeAttachmentKind"]
    site_asn: Optional["FrrConfigQueryWanSiteEdgesNodeSiteAsn"]
    tenant: "FrrConfigQueryWanSiteEdgesNodeTenant"
    lan_prefix: "FrrConfigQueryWanSiteEdgesNodeLanPrefix"
    bgp_sessions: "FrrConfigQueryWanSiteEdgesNodeBgpSessions"
    static_routes: "FrrConfigQueryWanSiteEdgesNodeStaticRoutes"


class FrrConfigQueryWanSiteEdgesNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeAttachmentKind(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeSiteAsn(BaseModel):
    value: Optional[Any]


class FrrConfigQueryWanSiteEdgesNodeTenant(BaseModel):
    node: Optional["FrrConfigQueryWanSiteEdgesNodeTenantNode"]


class FrrConfigQueryWanSiteEdgesNodeTenantNode(BaseModel):
    name: Optional["FrrConfigQueryWanSiteEdgesNodeTenantNodeName"]


class FrrConfigQueryWanSiteEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeLanPrefix(BaseModel):
    node: Optional["FrrConfigQueryWanSiteEdgesNodeLanPrefixNode"]


class FrrConfigQueryWanSiteEdgesNodeLanPrefixNode(BaseModel):
    prefix: Optional["FrrConfigQueryWanSiteEdgesNodeLanPrefixNodePrefix"]


class FrrConfigQueryWanSiteEdgesNodeLanPrefixNodePrefix(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeBgpSessions(BaseModel):
    edges: list["FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdges"]


class FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdges(BaseModel):
    node: Optional["FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode"]


class FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode(BaseModel):
    peer_address: Optional[
        "FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodePeerAddress"
    ]
    remote_as: Optional["FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeRemoteAs"]
    device: "FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice"


class FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodePeerAddress(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeRemoteAs(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice(BaseModel):
    node: Optional["FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode"]


class FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode(BaseModel):
    name: Optional["FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeName"]
    role: Optional["FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeRole"]


class FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNodeRole(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeStaticRoutes(BaseModel):
    edges: list["FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdges"]


class FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdges(BaseModel):
    node: Optional["FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNode"]


class FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNode(BaseModel):
    prefix: Optional["FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNodePrefix"]
    next_hop: Optional["FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNodeNextHop"]


class FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNodePrefix(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNodeNextHop(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceL3Vpn(BaseModel):
    edges: list["FrrConfigQueryServiceL3VpnEdges"]


class FrrConfigQueryServiceL3VpnEdges(BaseModel):
    node: Optional["FrrConfigQueryServiceL3VpnEdgesNode"]


class FrrConfigQueryServiceL3VpnEdgesNode(BaseModel):
    name: Optional["FrrConfigQueryServiceL3VpnEdgesNodeName"]
    tenant: "FrrConfigQueryServiceL3VpnEdgesNodeTenant"
    vrf: "FrrConfigQueryServiceL3VpnEdgesNodeVrf"
    dc_service_prefixes: "FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixes"


class FrrConfigQueryServiceL3VpnEdgesNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceL3VpnEdgesNodeTenant(BaseModel):
    node: Optional["FrrConfigQueryServiceL3VpnEdgesNodeTenantNode"]


class FrrConfigQueryServiceL3VpnEdgesNodeTenantNode(BaseModel):
    name: Optional["FrrConfigQueryServiceL3VpnEdgesNodeTenantNodeName"]


class FrrConfigQueryServiceL3VpnEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceL3VpnEdgesNodeVrf(BaseModel):
    node: Optional["FrrConfigQueryServiceL3VpnEdgesNodeVrfNode"]


class FrrConfigQueryServiceL3VpnEdgesNodeVrfNode(BaseModel):
    name: Optional["FrrConfigQueryServiceL3VpnEdgesNodeVrfNodeName"]


class FrrConfigQueryServiceL3VpnEdgesNodeVrfNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixes(BaseModel):
    edges: list["FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges"]


class FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges(BaseModel):
    node: Optional["FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode"]


class FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode(BaseModel):
    prefix: Optional[
        "FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNodePrefix"
    ]


class FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNodePrefix(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceTenantCloud(BaseModel):
    edges: list["FrrConfigQueryServiceTenantCloudEdges"]


class FrrConfigQueryServiceTenantCloudEdges(BaseModel):
    node: Optional["FrrConfigQueryServiceTenantCloudEdgesNode"]


class FrrConfigQueryServiceTenantCloudEdgesNode(BaseModel):
    name: Optional["FrrConfigQueryServiceTenantCloudEdgesNodeName"]
    tenant: "FrrConfigQueryServiceTenantCloudEdgesNodeTenant"
    prefix: "FrrConfigQueryServiceTenantCloudEdgesNodePrefix"


class FrrConfigQueryServiceTenantCloudEdgesNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceTenantCloudEdgesNodeTenant(BaseModel):
    node: Optional["FrrConfigQueryServiceTenantCloudEdgesNodeTenantNode"]


class FrrConfigQueryServiceTenantCloudEdgesNodeTenantNode(BaseModel):
    name: Optional["FrrConfigQueryServiceTenantCloudEdgesNodeTenantNodeName"]


class FrrConfigQueryServiceTenantCloudEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceTenantCloudEdgesNodePrefix(BaseModel):
    node: Optional["FrrConfigQueryServiceTenantCloudEdgesNodePrefixNode"]


class FrrConfigQueryServiceTenantCloudEdgesNodePrefixNode(BaseModel):
    prefix: Optional["FrrConfigQueryServiceTenantCloudEdgesNodePrefixNodePrefix"]


class FrrConfigQueryServiceTenantCloudEdgesNodePrefixNodePrefix(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceInternetAccess(BaseModel):
    edges: list["FrrConfigQueryServiceInternetAccessEdges"]


class FrrConfigQueryServiceInternetAccessEdges(BaseModel):
    node: Optional["FrrConfigQueryServiceInternetAccessEdgesNode"]


class FrrConfigQueryServiceInternetAccessEdgesNode(BaseModel):
    name: Optional["FrrConfigQueryServiceInternetAccessEdgesNodeName"]
    l_3_vpn: "FrrConfigQueryServiceInternetAccessEdgesNodeL3Vpn" = Field(alias="l3vpn")


class FrrConfigQueryServiceInternetAccessEdgesNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryServiceInternetAccessEdgesNodeL3Vpn(BaseModel):
    node: Optional["FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNode"]


class FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNode(BaseModel):
    tenant: "FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNodeTenant"


class FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNodeTenant(BaseModel):
    node: Optional["FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNodeTenantNode"]


class FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNodeTenantNode(BaseModel):
    name: Optional[
        "FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNodeTenantNodeName"
    ]


class FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNodeTenantNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanInternetPeering(BaseModel):
    edges: list["FrrConfigQueryWanInternetPeeringEdges"]


class FrrConfigQueryWanInternetPeeringEdges(BaseModel):
    node: Optional["FrrConfigQueryWanInternetPeeringEdgesNode"]


class FrrConfigQueryWanInternetPeeringEdgesNode(BaseModel):
    name: Optional["FrrConfigQueryWanInternetPeeringEdgesNodeName"]
    peer_asn: Optional["FrrConfigQueryWanInternetPeeringEdgesNodePeerAsn"]
    customer_aggregate: "FrrConfigQueryWanInternetPeeringEdgesNodeCustomerAggregate"
    internet_prefixes: "FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixes"


class FrrConfigQueryWanInternetPeeringEdgesNodeName(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanInternetPeeringEdgesNodePeerAsn(BaseModel):
    value: Optional[Any]


class FrrConfigQueryWanInternetPeeringEdgesNodeCustomerAggregate(BaseModel):
    node: Optional["FrrConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNode"]


class FrrConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNode(BaseModel):
    prefix: Optional[
        "FrrConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNodePrefix"
    ]


class FrrConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNodePrefix(BaseModel):
    value: Optional[str]


class FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixes(BaseModel):
    edges: list["FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdges"]


class FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdges(BaseModel):
    node: Optional["FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNode"]


class FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNode(BaseModel):
    prefix: Optional[
        "FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNodePrefix"
    ]


class FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNodePrefix(
    BaseModel
):
    value: Optional[str]


class FrrConfigQueryIpamIpAddress(BaseModel):
    edges: list["FrrConfigQueryIpamIpAddressEdges"]


class FrrConfigQueryIpamIpAddressEdges(BaseModel):
    node: Optional["FrrConfigQueryIpamIpAddressEdgesNode"]


class FrrConfigQueryIpamIpAddressEdgesNode(BaseModel):
    address: Optional["FrrConfigQueryIpamIpAddressEdgesNodeAddress"]
    interface: "FrrConfigQueryIpamIpAddressEdgesNodeInterface"


class FrrConfigQueryIpamIpAddressEdgesNodeAddress(BaseModel):
    value: Optional[str]


class FrrConfigQueryIpamIpAddressEdgesNodeInterface(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceLayer3",
                "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical",
                "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceLayer3(BaseModel):
    typename__: Literal["InterfaceLag", "InterfaceLayer3"] = Field(alias="__typename")


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical(BaseModel):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    name: Optional[
        "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalName"
    ]
    role: Optional[
        "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalRole"
    ]
    device: "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice"


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalName(BaseModel):
    value: Optional[str]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalRole(BaseModel):
    value: Optional[str]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode"
    ]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    name: Optional[
        "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNodeName"
    ]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual(BaseModel):
    typename__: Literal["InterfaceVirtual"] = Field(alias="__typename")
    name: Optional[
        "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualName"
    ]
    role: Optional[
        "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualRole"
    ]
    device: "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice"


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualName(BaseModel):
    value: Optional[str]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualRole(BaseModel):
    value: Optional[str]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice(
    BaseModel
):
    node: Optional[
        "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode"
    ]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    name: Optional[
        "FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNodeName"
    ]


class FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNodeName(
    BaseModel
):
    value: Optional[str]


FrrConfigQuery.model_rebuild()
FrrConfigQueryTarget.model_rebuild()
FrrConfigQueryTargetEdges.model_rebuild()
FrrConfigQueryTargetEdgesNode.model_rebuild()
FrrConfigQueryTargetEdgesNodeRouterId.model_rebuild()
FrrConfigQueryTargetEdgesNodeRouterIdNode.model_rebuild()
FrrConfigQueryTargetEdgesNodeAsn.model_rebuild()
FrrConfigQueryTargetEdgesNodeAsnNode.model_rebuild()
FrrConfigQueryTargetEdgesNodeBgpNeighbors.model_rebuild()
FrrConfigQueryTargetEdgesNodeBgpNeighborsEdges.model_rebuild()
FrrConfigQueryTargetEdgesNodeBgpNeighborsEdgesNode.model_rebuild()
FrrConfigQueryDcimDevice.model_rebuild()
FrrConfigQueryDcimDeviceEdges.model_rebuild()
FrrConfigQueryDcimDeviceEdgesNode.model_rebuild()
FrrConfigQueryDcimDeviceEdgesNodeRouterId.model_rebuild()
FrrConfigQueryDcimDeviceEdgesNodeRouterIdNode.model_rebuild()
FrrConfigQueryDcimDeviceEdgesNodeAsn.model_rebuild()
FrrConfigQueryDcimDeviceEdgesNodeAsnNode.model_rebuild()
FrrConfigQueryDcimDeviceEdgesNodeBgpNeighbors.model_rebuild()
FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdges.model_rebuild()
FrrConfigQueryDcimDeviceEdgesNodeBgpNeighborsEdgesNode.model_rebuild()
FrrConfigQueryWanSite.model_rebuild()
FrrConfigQueryWanSiteEdges.model_rebuild()
FrrConfigQueryWanSiteEdgesNode.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeTenant.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeTenantNode.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeLanPrefix.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeLanPrefixNode.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeBgpSessions.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdges.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNode.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDevice.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeBgpSessionsEdgesNodeDeviceNode.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeStaticRoutes.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdges.model_rebuild()
FrrConfigQueryWanSiteEdgesNodeStaticRoutesEdgesNode.model_rebuild()
FrrConfigQueryServiceL3Vpn.model_rebuild()
FrrConfigQueryServiceL3VpnEdges.model_rebuild()
FrrConfigQueryServiceL3VpnEdgesNode.model_rebuild()
FrrConfigQueryServiceL3VpnEdgesNodeTenant.model_rebuild()
FrrConfigQueryServiceL3VpnEdgesNodeTenantNode.model_rebuild()
FrrConfigQueryServiceL3VpnEdgesNodeVrf.model_rebuild()
FrrConfigQueryServiceL3VpnEdgesNodeVrfNode.model_rebuild()
FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixes.model_rebuild()
FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdges.model_rebuild()
FrrConfigQueryServiceL3VpnEdgesNodeDcServicePrefixesEdgesNode.model_rebuild()
FrrConfigQueryServiceTenantCloud.model_rebuild()
FrrConfigQueryServiceTenantCloudEdges.model_rebuild()
FrrConfigQueryServiceTenantCloudEdgesNode.model_rebuild()
FrrConfigQueryServiceTenantCloudEdgesNodeTenant.model_rebuild()
FrrConfigQueryServiceTenantCloudEdgesNodeTenantNode.model_rebuild()
FrrConfigQueryServiceTenantCloudEdgesNodePrefix.model_rebuild()
FrrConfigQueryServiceTenantCloudEdgesNodePrefixNode.model_rebuild()
FrrConfigQueryServiceInternetAccess.model_rebuild()
FrrConfigQueryServiceInternetAccessEdges.model_rebuild()
FrrConfigQueryServiceInternetAccessEdgesNode.model_rebuild()
FrrConfigQueryServiceInternetAccessEdgesNodeL3Vpn.model_rebuild()
FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNode.model_rebuild()
FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNodeTenant.model_rebuild()
FrrConfigQueryServiceInternetAccessEdgesNodeL3VpnNodeTenantNode.model_rebuild()
FrrConfigQueryWanInternetPeering.model_rebuild()
FrrConfigQueryWanInternetPeeringEdges.model_rebuild()
FrrConfigQueryWanInternetPeeringEdgesNode.model_rebuild()
FrrConfigQueryWanInternetPeeringEdgesNodeCustomerAggregate.model_rebuild()
FrrConfigQueryWanInternetPeeringEdgesNodeCustomerAggregateNode.model_rebuild()
FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixes.model_rebuild()
FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdges.model_rebuild()
FrrConfigQueryWanInternetPeeringEdgesNodeInternetPrefixesEdgesNode.model_rebuild()
FrrConfigQueryIpamIpAddress.model_rebuild()
FrrConfigQueryIpamIpAddressEdges.model_rebuild()
FrrConfigQueryIpamIpAddressEdgesNode.model_rebuild()
FrrConfigQueryIpamIpAddressEdgesNodeInterface.model_rebuild()
FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysical.model_rebuild()
FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDevice.model_rebuild()
FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfacePhysicalDeviceNode.model_rebuild()
FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtual.model_rebuild()
FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDevice.model_rebuild()
FrrConfigQueryIpamIpAddressEdgesNodeInterfaceNodeInterfaceVirtualDeviceNode.model_rebuild()
