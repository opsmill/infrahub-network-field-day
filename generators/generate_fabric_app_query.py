from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class GenerateFabricAppQuery(BaseModel):
    target: "GenerateFabricAppQueryTarget"
    core_ip_prefix_pool: "GenerateFabricAppQueryCoreIpPrefixPool" = Field(
        alias="CoreIPPrefixPool"
    )


class GenerateFabricAppQueryTarget(BaseModel):
    edges: list["GenerateFabricAppQueryTargetEdges"]


class GenerateFabricAppQueryTargetEdges(BaseModel):
    node: Optional["GenerateFabricAppQueryTargetEdgesNode"]


class GenerateFabricAppQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateFabricAppQueryTargetEdgesNodeName"]
    status: Optional["GenerateFabricAppQueryTargetEdgesNodeStatus"]
    exposed: Optional["GenerateFabricAppQueryTargetEdgesNodeExposed"]
    vip_block_size: Optional["GenerateFabricAppQueryTargetEdgesNodeVipBlockSize"]
    vip_block_managed: Optional["GenerateFabricAppQueryTargetEdgesNodeVipBlockManaged"]
    vip_block: "GenerateFabricAppQueryTargetEdgesNodeVipBlock"
    cluster: "GenerateFabricAppQueryTargetEdgesNodeCluster"


class GenerateFabricAppQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateFabricAppQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class GenerateFabricAppQueryTargetEdgesNodeExposed(BaseModel):
    value: Optional[bool]


class GenerateFabricAppQueryTargetEdgesNodeVipBlockSize(BaseModel):
    value: Optional[Any]


class GenerateFabricAppQueryTargetEdgesNodeVipBlockManaged(BaseModel):
    value: Optional[bool]


class GenerateFabricAppQueryTargetEdgesNodeVipBlock(BaseModel):
    node: Optional["GenerateFabricAppQueryTargetEdgesNodeVipBlockNode"]


class GenerateFabricAppQueryTargetEdgesNodeVipBlockNode(BaseModel):
    id: str
    prefix: Optional["GenerateFabricAppQueryTargetEdgesNodeVipBlockNodePrefix"]


class GenerateFabricAppQueryTargetEdgesNodeVipBlockNodePrefix(BaseModel):
    value: Optional[str]


class GenerateFabricAppQueryTargetEdgesNodeCluster(BaseModel):
    node: Optional["GenerateFabricAppQueryTargetEdgesNodeClusterNode"]


class GenerateFabricAppQueryTargetEdgesNodeClusterNode(BaseModel):
    id: str
    name: Optional["GenerateFabricAppQueryTargetEdgesNodeClusterNodeName"]
    vip_pools: "GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPools"


class GenerateFabricAppQueryTargetEdgesNodeClusterNodeName(BaseModel):
    value: Optional[str]


class GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPools(BaseModel):
    edges: list["GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPoolsEdges"]


class GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPoolsEdges(BaseModel):
    node: Optional["GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPoolsEdgesNode"]


class GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPoolsEdgesNode(BaseModel):
    id: str
    prefix: Optional[
        "GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPoolsEdgesNodePrefix"
    ]


class GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPoolsEdgesNodePrefix(
    BaseModel
):
    value: Optional[str]


class GenerateFabricAppQueryCoreIpPrefixPool(BaseModel):
    edges: list["GenerateFabricAppQueryCoreIpPrefixPoolEdges"]


class GenerateFabricAppQueryCoreIpPrefixPoolEdges(BaseModel):
    node: Optional["GenerateFabricAppQueryCoreIpPrefixPoolEdgesNode"]


class GenerateFabricAppQueryCoreIpPrefixPoolEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeName"]
    resources: "GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeResources"


class GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeResources(BaseModel):
    edges: Optional[
        list["GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeResourcesEdges"]
    ]


class GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeResourcesEdges(BaseModel):
    node: Optional["GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNode"]


class GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeResourcesEdgesNode(BaseModel):
    typename__: Literal[
        "BuiltinIPPrefix", "InternalIPPrefixAvailable", "IpamPrefix"
    ] = Field(alias="__typename")
    id: Optional[str]


GenerateFabricAppQuery.model_rebuild()
GenerateFabricAppQueryTarget.model_rebuild()
GenerateFabricAppQueryTargetEdges.model_rebuild()
GenerateFabricAppQueryTargetEdgesNode.model_rebuild()
GenerateFabricAppQueryTargetEdgesNodeVipBlock.model_rebuild()
GenerateFabricAppQueryTargetEdgesNodeVipBlockNode.model_rebuild()
GenerateFabricAppQueryTargetEdgesNodeCluster.model_rebuild()
GenerateFabricAppQueryTargetEdgesNodeClusterNode.model_rebuild()
GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPools.model_rebuild()
GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPoolsEdges.model_rebuild()
GenerateFabricAppQueryTargetEdgesNodeClusterNodeVipPoolsEdgesNode.model_rebuild()
GenerateFabricAppQueryCoreIpPrefixPool.model_rebuild()
GenerateFabricAppQueryCoreIpPrefixPoolEdges.model_rebuild()
GenerateFabricAppQueryCoreIpPrefixPoolEdgesNode.model_rebuild()
GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeResources.model_rebuild()
GenerateFabricAppQueryCoreIpPrefixPoolEdgesNodeResourcesEdges.model_rebuild()
