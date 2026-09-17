from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class GenerateNetworkSegmentQuery(BaseModel):
    target: "GenerateNetworkSegmentQueryTarget"
    existing_vlan: "GenerateNetworkSegmentQueryExistingVlan"
    existing_svi: "GenerateNetworkSegmentQueryExistingSvi"
    core_ip_prefix_pool: "GenerateNetworkSegmentQueryCoreIpPrefixPool" = Field(
        alias="CoreIPPrefixPool"
    )
    core_number_pool: "GenerateNetworkSegmentQueryCoreNumberPool" = Field(
        alias="CoreNumberPool"
    )
    ipam_l_2_domain: "GenerateNetworkSegmentQueryIpamL2Domain" = Field(
        alias="IpamL2Domain"
    )


class GenerateNetworkSegmentQueryTarget(BaseModel):
    edges: list["GenerateNetworkSegmentQueryTargetEdges"]


class GenerateNetworkSegmentQueryTargetEdges(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNode"]


class GenerateNetworkSegmentQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeName"]
    description: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeDescription"]
    status: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeStatus"]
    vlan_id: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeVlanId"]
    prefix_length: Optional["GenerateNetworkSegmentQueryTargetEdgesNodePrefixLength"]
    tenant: "GenerateNetworkSegmentQueryTargetEdgesNodeTenant"
    vrf: "GenerateNetworkSegmentQueryTargetEdgesNodeVrf"
    fabric: "GenerateNetworkSegmentQueryTargetEdgesNodeFabric"
    avd_tags: "GenerateNetworkSegmentQueryTargetEdgesNodeAvdTags"
    subnet_pool: "GenerateNetworkSegmentQueryTargetEdgesNodeSubnetPool"
    vlan_pool: "GenerateNetworkSegmentQueryTargetEdgesNodeVlanPool"
    subnet: "GenerateNetworkSegmentQueryTargetEdgesNodeSubnet"
    vlan: "GenerateNetworkSegmentQueryTargetEdgesNodeVlan"
    svi: "GenerateNetworkSegmentQueryTargetEdgesNodeSvi"


class GenerateNetworkSegmentQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeDescription(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeVlanId(BaseModel):
    value: Optional[Any]


class GenerateNetworkSegmentQueryTargetEdgesNodePrefixLength(BaseModel):
    value: Optional[Any]


class GenerateNetworkSegmentQueryTargetEdgesNodeTenant(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeTenantNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeTenantNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeTenantNodeName"]


class GenerateNetworkSegmentQueryTargetEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeVrf(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeVrfNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeVrfNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeVrfNodeName"]


class GenerateNetworkSegmentQueryTargetEdgesNodeVrfNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeFabric(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeFabricNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeFabricNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeFabricNodeName"]


class GenerateNetworkSegmentQueryTargetEdgesNodeFabricNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeAvdTags(BaseModel):
    edges: list["GenerateNetworkSegmentQueryTargetEdgesNodeAvdTagsEdges"]


class GenerateNetworkSegmentQueryTargetEdgesNodeAvdTagsEdges(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeAvdTagsEdgesNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeAvdTagsEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeAvdTagsEdgesNodeName"]


class GenerateNetworkSegmentQueryTargetEdgesNodeAvdTagsEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeSubnetPool(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeSubnetPoolNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeSubnetPoolNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeSubnetPoolNodeName"]


class GenerateNetworkSegmentQueryTargetEdgesNodeSubnetPoolNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeVlanPool(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeVlanPoolNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeVlanPoolNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeVlanPoolNodeName"]


class GenerateNetworkSegmentQueryTargetEdgesNodeVlanPoolNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeSubnet(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeSubnetNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeSubnetNode(BaseModel):
    id: str
    prefix: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeSubnetNodePrefix"]


class GenerateNetworkSegmentQueryTargetEdgesNodeSubnetNodePrefix(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeVlan(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeVlanNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeVlanNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeVlanNodeName"]
    vlan_id: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeVlanNodeVlanId"]


class GenerateNetworkSegmentQueryTargetEdgesNodeVlanNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeVlanNodeVlanId(BaseModel):
    value: Optional[Any]


class GenerateNetworkSegmentQueryTargetEdgesNodeSvi(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeSviNode"]


class GenerateNetworkSegmentQueryTargetEdgesNodeSviNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeSviNodeName"]
    svi_id: Optional["GenerateNetworkSegmentQueryTargetEdgesNodeSviNodeSviId"]


class GenerateNetworkSegmentQueryTargetEdgesNodeSviNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryTargetEdgesNodeSviNodeSviId(BaseModel):
    value: Optional[Any]


class GenerateNetworkSegmentQueryExistingVlan(BaseModel):
    edges: list["GenerateNetworkSegmentQueryExistingVlanEdges"]


class GenerateNetworkSegmentQueryExistingVlanEdges(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryExistingVlanEdgesNode"]


class GenerateNetworkSegmentQueryExistingVlanEdgesNode(BaseModel):
    id: str
    vlan_id: Optional["GenerateNetworkSegmentQueryExistingVlanEdgesNodeVlanId"]


class GenerateNetworkSegmentQueryExistingVlanEdgesNodeVlanId(BaseModel):
    value: Optional[Any]


class GenerateNetworkSegmentQueryExistingSvi(BaseModel):
    edges: list["GenerateNetworkSegmentQueryExistingSviEdges"]


class GenerateNetworkSegmentQueryExistingSviEdges(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryExistingSviEdgesNode"]


class GenerateNetworkSegmentQueryExistingSviEdgesNode(BaseModel):
    id: str
    svi_id: Optional["GenerateNetworkSegmentQueryExistingSviEdgesNodeSviId"]


class GenerateNetworkSegmentQueryExistingSviEdgesNodeSviId(BaseModel):
    value: Optional[Any]


class GenerateNetworkSegmentQueryCoreIpPrefixPool(BaseModel):
    edges: list["GenerateNetworkSegmentQueryCoreIpPrefixPoolEdges"]


class GenerateNetworkSegmentQueryCoreIpPrefixPoolEdges(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNode"]


class GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeName"]
    resources: "GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResources"


class GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResources(BaseModel):
    edges: Optional[
        list["GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdges"]
    ]


class GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNodeBuiltinIPPrefix",
                "GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    id: str
    role: Optional[
        "GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class GenerateNetworkSegmentQueryCoreNumberPool(BaseModel):
    edges: list["GenerateNetworkSegmentQueryCoreNumberPoolEdges"]


class GenerateNetworkSegmentQueryCoreNumberPoolEdges(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryCoreNumberPoolEdgesNode"]


class GenerateNetworkSegmentQueryCoreNumberPoolEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryCoreNumberPoolEdgesNodeName"]
    node: Optional["GenerateNetworkSegmentQueryCoreNumberPoolEdgesNodeNode"]
    node_attribute: Optional[
        "GenerateNetworkSegmentQueryCoreNumberPoolEdgesNodeNodeAttribute"
    ]


class GenerateNetworkSegmentQueryCoreNumberPoolEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryCoreNumberPoolEdgesNodeNode(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryCoreNumberPoolEdgesNodeNodeAttribute(BaseModel):
    value: Optional[str]


class GenerateNetworkSegmentQueryIpamL2Domain(BaseModel):
    edges: list["GenerateNetworkSegmentQueryIpamL2DomainEdges"]


class GenerateNetworkSegmentQueryIpamL2DomainEdges(BaseModel):
    node: Optional["GenerateNetworkSegmentQueryIpamL2DomainEdgesNode"]


class GenerateNetworkSegmentQueryIpamL2DomainEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateNetworkSegmentQueryIpamL2DomainEdgesNodeName"]


class GenerateNetworkSegmentQueryIpamL2DomainEdgesNodeName(BaseModel):
    value: Optional[str]


GenerateNetworkSegmentQuery.model_rebuild()
GenerateNetworkSegmentQueryTarget.model_rebuild()
GenerateNetworkSegmentQueryTargetEdges.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeTenant.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeTenantNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeVrf.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeVrfNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeFabric.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeFabricNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeAvdTags.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeAvdTagsEdges.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeAvdTagsEdgesNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeSubnetPool.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeSubnetPoolNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeVlanPool.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeVlanPoolNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeSubnet.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeSubnetNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeVlan.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeVlanNode.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeSvi.model_rebuild()
GenerateNetworkSegmentQueryTargetEdgesNodeSviNode.model_rebuild()
GenerateNetworkSegmentQueryExistingVlan.model_rebuild()
GenerateNetworkSegmentQueryExistingVlanEdges.model_rebuild()
GenerateNetworkSegmentQueryExistingVlanEdgesNode.model_rebuild()
GenerateNetworkSegmentQueryExistingSvi.model_rebuild()
GenerateNetworkSegmentQueryExistingSviEdges.model_rebuild()
GenerateNetworkSegmentQueryExistingSviEdgesNode.model_rebuild()
GenerateNetworkSegmentQueryCoreIpPrefixPool.model_rebuild()
GenerateNetworkSegmentQueryCoreIpPrefixPoolEdges.model_rebuild()
GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNode.model_rebuild()
GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResources.model_rebuild()
GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdges.model_rebuild()
GenerateNetworkSegmentQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
GenerateNetworkSegmentQueryCoreNumberPool.model_rebuild()
GenerateNetworkSegmentQueryCoreNumberPoolEdges.model_rebuild()
GenerateNetworkSegmentQueryCoreNumberPoolEdgesNode.model_rebuild()
GenerateNetworkSegmentQueryIpamL2Domain.model_rebuild()
GenerateNetworkSegmentQueryIpamL2DomainEdges.model_rebuild()
GenerateNetworkSegmentQueryIpamL2DomainEdgesNode.model_rebuild()
