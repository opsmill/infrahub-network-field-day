from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GenerateDnsRecordQuery(BaseModel):
    target: "GenerateDnsRecordQueryTarget"
    resolver: "GenerateDnsRecordQueryResolver"


class GenerateDnsRecordQueryTarget(BaseModel):
    edges: list["GenerateDnsRecordQueryTargetEdges"]


class GenerateDnsRecordQueryTargetEdges(BaseModel):
    node: Optional["GenerateDnsRecordQueryTargetEdgesNode"]


class GenerateDnsRecordQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateDnsRecordQueryTargetEdgesNodeName"]
    status: Optional["GenerateDnsRecordQueryTargetEdgesNodeStatus"]
    exposed: Optional["GenerateDnsRecordQueryTargetEdgesNodeExposed"]
    vip_block: "GenerateDnsRecordQueryTargetEdgesNodeVipBlock"


class GenerateDnsRecordQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateDnsRecordQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class GenerateDnsRecordQueryTargetEdgesNodeExposed(BaseModel):
    value: Optional[bool]


class GenerateDnsRecordQueryTargetEdgesNodeVipBlock(BaseModel):
    node: Optional["GenerateDnsRecordQueryTargetEdgesNodeVipBlockNode"]


class GenerateDnsRecordQueryTargetEdgesNodeVipBlockNode(BaseModel):
    id: str
    prefix: Optional["GenerateDnsRecordQueryTargetEdgesNodeVipBlockNodePrefix"]


class GenerateDnsRecordQueryTargetEdgesNodeVipBlockNodePrefix(BaseModel):
    value: Optional[str]


class GenerateDnsRecordQueryResolver(BaseModel):
    edges: list["GenerateDnsRecordQueryResolverEdges"]


class GenerateDnsRecordQueryResolverEdges(BaseModel):
    node: Optional["GenerateDnsRecordQueryResolverEdgesNode"]


class GenerateDnsRecordQueryResolverEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateDnsRecordQueryResolverEdgesNodeName"]
    dns_zone: Optional["GenerateDnsRecordQueryResolverEdgesNodeDnsZone"]


class GenerateDnsRecordQueryResolverEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateDnsRecordQueryResolverEdgesNodeDnsZone(BaseModel):
    value: Optional[str]


GenerateDnsRecordQuery.model_rebuild()
GenerateDnsRecordQueryTarget.model_rebuild()
GenerateDnsRecordQueryTargetEdges.model_rebuild()
GenerateDnsRecordQueryTargetEdgesNode.model_rebuild()
GenerateDnsRecordQueryTargetEdgesNodeVipBlock.model_rebuild()
GenerateDnsRecordQueryTargetEdgesNodeVipBlockNode.model_rebuild()
GenerateDnsRecordQueryResolver.model_rebuild()
GenerateDnsRecordQueryResolverEdges.model_rebuild()
GenerateDnsRecordQueryResolverEdgesNode.model_rebuild()
