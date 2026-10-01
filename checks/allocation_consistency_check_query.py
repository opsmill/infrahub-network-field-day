from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AllocationConsistencyCheckQuery(BaseModel):
    evpn_tenant: "AllocationConsistencyCheckQueryEvpnTenant" = Field(alias="EvpnTenant")
    evpn_svi: "AllocationConsistencyCheckQueryEvpnSvi" = Field(alias="EvpnSvi")
    service_network_segment: "AllocationConsistencyCheckQueryServiceNetworkSegment" = (
        Field(alias="ServiceNetworkSegment")
    )
    ipam_prefix: "AllocationConsistencyCheckQueryIpamPrefix" = Field(alias="IpamPrefix")
    core_ip_prefix_pool: "AllocationConsistencyCheckQueryCoreIpPrefixPool" = Field(
        alias="CoreIPPrefixPool"
    )
    service_fabric_app: "AllocationConsistencyCheckQueryServiceFabricApp" = Field(
        alias="ServiceFabricApp"
    )


class AllocationConsistencyCheckQueryEvpnTenant(BaseModel):
    edges: list["AllocationConsistencyCheckQueryEvpnTenantEdges"]


class AllocationConsistencyCheckQueryEvpnTenantEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnTenantEdgesNode"]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNode(BaseModel):
    id: str
    name: Optional["AllocationConsistencyCheckQueryEvpnTenantEdgesNodeName"]
    mac_vrf_vni_base: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeMacVrfVniBase"
    ]
    fabrics: "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabrics"
    vrfs: "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeVrfs"
    l_2_vlans: "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2Vlans" = Field(
        alias="l2vlans"
    )


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeMacVrfVniBase(BaseModel):
    value: Optional[Any]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabrics(BaseModel):
    edges: list["AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabricsEdges"]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabricsEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabricsEdgesNode"]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabricsEdgesNode(BaseModel):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabricsEdgesNodeName"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabricsEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeVrfs(BaseModel):
    edges: list["AllocationConsistencyCheckQueryEvpnTenantEdgesNodeVrfsEdges"]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeVrfsEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnTenantEdgesNodeVrfsEdgesNode"]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeVrfsEdgesNode(BaseModel):
    id: str


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2Vlans(BaseModel):
    edges: list["AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdges"]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNode"]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNode(BaseModel):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeName"
    ]
    vlan_id: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanId"
    ]
    vni_override: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVniOverride"
    ]
    vlan: "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlan"
    rack_tags: (
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTags"
    )
    avd_tags: (
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTags"
    )


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVniOverride(
    BaseModel
):
    value: Optional[Any]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlan(BaseModel):
    node: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanNode"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanNode(
    BaseModel
):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanNodeName"
    ]
    vlan_id: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanNodeVlanId"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanNodeName(
    BaseModel
):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanNodeVlanId(
    BaseModel
):
    value: Optional[Any]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTags(
    BaseModel
):
    edges: list[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTagsEdges"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTagsEdges(
    BaseModel
):
    node: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTagsEdgesNode"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTagsEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTagsEdgesNodeName"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTagsEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTags(
    BaseModel
):
    edges: list[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTagsEdges"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTagsEdges(
    BaseModel
):
    node: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTagsEdgesNode"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTagsEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTagsEdgesNodeName"
    ]


class AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTagsEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnSvi(BaseModel):
    edges: list["AllocationConsistencyCheckQueryEvpnSviEdges"]


class AllocationConsistencyCheckQueryEvpnSviEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNode"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNode(BaseModel):
    id: str
    name: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeName"]
    svi_id: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeSviId"]
    ip_address_virtual: Optional[
        "AllocationConsistencyCheckQueryEvpnSviEdgesNodeIpAddressVirtual"
    ]
    ip_virtual_router_addresses: Optional[
        "AllocationConsistencyCheckQueryEvpnSviEdgesNodeIpVirtualRouterAddresses"
    ]
    vrf: "AllocationConsistencyCheckQueryEvpnSviEdgesNodeVrf"
    vlan: "AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlan"
    rack_tags: "AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTags"
    avd_tags: "AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTags"


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeSviId(BaseModel):
    value: Optional[Any]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeIpAddressVirtual(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeIpVirtualRouterAddresses(
    BaseModel
):
    value: Optional[Any]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeVrf(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeVrfNode"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeVrfNode(BaseModel):
    id: str
    name: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeVrfNodeName"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeVrfNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlan(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlanNode"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlanNode(BaseModel):
    id: str
    name: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlanNodeName"]
    vlan_id: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlanNodeVlanId"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlanNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlanNodeVlanId(BaseModel):
    value: Optional[Any]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTags(BaseModel):
    edges: list["AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTagsEdges"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTagsEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTagsEdgesNode"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTagsEdgesNode(BaseModel):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTagsEdgesNodeName"
    ]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTagsEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTags(BaseModel):
    edges: list["AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTagsEdges"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTagsEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTagsEdgesNode"]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTagsEdgesNode(BaseModel):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTagsEdgesNodeName"
    ]


class AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTagsEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryServiceNetworkSegment(BaseModel):
    edges: list["AllocationConsistencyCheckQueryServiceNetworkSegmentEdges"]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNode"]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNode(BaseModel):
    id: str
    name: Optional["AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeName"]
    status: Optional[
        "AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeStatus"
    ]
    vrf: "AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeVrf"
    subnet: "AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeSubnet"


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeStatus(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeVrf(BaseModel):
    node: Optional[
        "AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeVrfNode"
    ]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeVrfNode(BaseModel):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeVrfNodeName"
    ]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeVrfNodeName(
    BaseModel
):
    value: Optional[str]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeSubnet(BaseModel):
    node: Optional[
        "AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeSubnetNode"
    ]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeSubnetNode(
    BaseModel
):
    id: str
    prefix: Optional[
        "AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeSubnetNodePrefix"
    ]


class AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeSubnetNodePrefix(
    BaseModel
):
    value: Optional[str]


class AllocationConsistencyCheckQueryIpamPrefix(BaseModel):
    edges: list["AllocationConsistencyCheckQueryIpamPrefixEdges"]


class AllocationConsistencyCheckQueryIpamPrefixEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryIpamPrefixEdgesNode"]


class AllocationConsistencyCheckQueryIpamPrefixEdgesNode(BaseModel):
    id: str
    prefix: Optional["AllocationConsistencyCheckQueryIpamPrefixEdgesNodePrefix"]
    role: Optional["AllocationConsistencyCheckQueryIpamPrefixEdgesNodeRole"]
    vrf: "AllocationConsistencyCheckQueryIpamPrefixEdgesNodeVrf"


class AllocationConsistencyCheckQueryIpamPrefixEdgesNodePrefix(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryIpamPrefixEdgesNodeRole(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryIpamPrefixEdgesNodeVrf(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryIpamPrefixEdgesNodeVrfNode"]


class AllocationConsistencyCheckQueryIpamPrefixEdgesNodeVrfNode(BaseModel):
    id: str
    name: Optional["AllocationConsistencyCheckQueryIpamPrefixEdgesNodeVrfNodeName"]


class AllocationConsistencyCheckQueryIpamPrefixEdgesNodeVrfNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryCoreIpPrefixPool(BaseModel):
    edges: list["AllocationConsistencyCheckQueryCoreIpPrefixPoolEdges"]


class AllocationConsistencyCheckQueryCoreIpPrefixPoolEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNode"]


class AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNode(BaseModel):
    id: str
    name: Optional["AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeName"]
    resources: "AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeResources"


class AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeResources(BaseModel):
    edges: Optional[
        list["AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeResourcesEdges"]
    ]


class AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeResourcesEdges(BaseModel):
    node: Optional[
        "AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNode"
    ]


class AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNode(
    BaseModel
):
    typename__: Literal[
        "BuiltinIPPrefix", "InternalIPPrefixAvailable", "IpamPrefix"
    ] = Field(alias="__typename")
    id: Optional[str]


class AllocationConsistencyCheckQueryServiceFabricApp(BaseModel):
    edges: list["AllocationConsistencyCheckQueryServiceFabricAppEdges"]


class AllocationConsistencyCheckQueryServiceFabricAppEdges(BaseModel):
    node: Optional["AllocationConsistencyCheckQueryServiceFabricAppEdgesNode"]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNode(BaseModel):
    id: str
    name: Optional["AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeName"]
    status: Optional["AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeStatus"]
    exposed: Optional["AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeExposed"]
    vip_block_managed: Optional[
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlockManaged"
    ]
    vip_block: "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlock"
    cluster: "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeCluster"


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeName(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeStatus(BaseModel):
    value: Optional[str]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeExposed(BaseModel):
    value: Optional[bool]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlockManaged(
    BaseModel
):
    value: Optional[bool]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlock(BaseModel):
    node: Optional[
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlockNode"
    ]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlockNode(BaseModel):
    id: str
    prefix: Optional[
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlockNodePrefix"
    ]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlockNodePrefix(
    BaseModel
):
    value: Optional[str]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeCluster(BaseModel):
    node: Optional[
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNode"
    ]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNode(BaseModel):
    id: str
    name: Optional[
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeName"
    ]
    vip_pools: (
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPools"
    )


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeName(
    BaseModel
):
    value: Optional[str]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPools(
    BaseModel
):
    edges: list[
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPoolsEdges"
    ]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPoolsEdges(
    BaseModel
):
    node: Optional[
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPoolsEdgesNode"
    ]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPoolsEdgesNode(
    BaseModel
):
    id: str
    prefix: Optional[
        "AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPoolsEdgesNodePrefix"
    ]


class AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPoolsEdgesNodePrefix(
    BaseModel
):
    value: Optional[str]


AllocationConsistencyCheckQuery.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenant.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabrics.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabricsEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeFabricsEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeVrfs.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeVrfsEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2Vlans.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlan.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeVlanNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTags.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTagsEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeRackTagsEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTags.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTagsEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnTenantEdgesNodeL2VlansEdgesNodeAvdTagsEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnSvi.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeVrf.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeVrfNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlan.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeVlanNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTags.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTagsEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeRackTagsEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTags.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTagsEdges.model_rebuild()
AllocationConsistencyCheckQueryEvpnSviEdgesNodeAvdTagsEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryServiceNetworkSegment.model_rebuild()
AllocationConsistencyCheckQueryServiceNetworkSegmentEdges.model_rebuild()
AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeVrf.model_rebuild()
AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeVrfNode.model_rebuild()
AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeSubnet.model_rebuild()
AllocationConsistencyCheckQueryServiceNetworkSegmentEdgesNodeSubnetNode.model_rebuild()
AllocationConsistencyCheckQueryIpamPrefix.model_rebuild()
AllocationConsistencyCheckQueryIpamPrefixEdges.model_rebuild()
AllocationConsistencyCheckQueryIpamPrefixEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryIpamPrefixEdgesNodeVrf.model_rebuild()
AllocationConsistencyCheckQueryIpamPrefixEdgesNodeVrfNode.model_rebuild()
AllocationConsistencyCheckQueryCoreIpPrefixPool.model_rebuild()
AllocationConsistencyCheckQueryCoreIpPrefixPoolEdges.model_rebuild()
AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeResources.model_rebuild()
AllocationConsistencyCheckQueryCoreIpPrefixPoolEdgesNodeResourcesEdges.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricApp.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdges.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdgesNode.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlock.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeVipBlockNode.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeCluster.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNode.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPools.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPoolsEdges.model_rebuild()
AllocationConsistencyCheckQueryServiceFabricAppEdgesNodeClusterNodeVipPoolsEdgesNode.model_rebuild()
