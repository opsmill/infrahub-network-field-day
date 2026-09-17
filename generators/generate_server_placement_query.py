from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GenerateServerPlacementQuery(BaseModel):
    target: "GenerateServerPlacementQueryTarget"
    compute_physical_server: "GenerateServerPlacementQueryComputePhysicalServer" = (
        Field(alias="ComputePhysicalServer")
    )


class GenerateServerPlacementQueryTarget(BaseModel):
    edges: list["GenerateServerPlacementQueryTargetEdges"]


class GenerateServerPlacementQueryTargetEdges(BaseModel):
    node: Optional["GenerateServerPlacementQueryTargetEdgesNode"]


class GenerateServerPlacementQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateServerPlacementQueryTargetEdgesNodeName"]
    description: Optional["GenerateServerPlacementQueryTargetEdgesNodeDescription"]
    status: Optional["GenerateServerPlacementQueryTargetEdgesNodeStatus"]
    hostname: Optional["GenerateServerPlacementQueryTargetEdgesNodeHostname"]
    server_role: Optional["GenerateServerPlacementQueryTargetEdgesNodeServerRole"]
    rack: "GenerateServerPlacementQueryTargetEdgesNodeRack"
    template: "GenerateServerPlacementQueryTargetEdgesNodeTemplate"
    tenant: "GenerateServerPlacementQueryTargetEdgesNodeTenant"
    server: "GenerateServerPlacementQueryTargetEdgesNodeServer"


class GenerateServerPlacementQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryTargetEdgesNodeDescription(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryTargetEdgesNodeHostname(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryTargetEdgesNodeServerRole(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryTargetEdgesNodeRack(BaseModel):
    node: Optional["GenerateServerPlacementQueryTargetEdgesNodeRackNode"]


class GenerateServerPlacementQueryTargetEdgesNodeRackNode(BaseModel):
    id: str
    name: Optional["GenerateServerPlacementQueryTargetEdgesNodeRackNodeName"]


class GenerateServerPlacementQueryTargetEdgesNodeRackNodeName(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryTargetEdgesNodeTemplate(BaseModel):
    node: Optional["GenerateServerPlacementQueryTargetEdgesNodeTemplateNode"]


class GenerateServerPlacementQueryTargetEdgesNodeTemplateNode(BaseModel):
    typename__: Literal[
        "CoreObjectTemplate",
        "TemplateComputePhysicalServer",
        "TemplateDcimFabricSwitch",
    ] = Field(alias="__typename")
    id: Optional[str]
    template_name: Optional[
        "GenerateServerPlacementQueryTargetEdgesNodeTemplateNodeTemplateName"
    ]


class GenerateServerPlacementQueryTargetEdgesNodeTemplateNodeTemplateName(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryTargetEdgesNodeTenant(BaseModel):
    node: Optional["GenerateServerPlacementQueryTargetEdgesNodeTenantNode"]


class GenerateServerPlacementQueryTargetEdgesNodeTenantNode(BaseModel):
    id: str
    name: Optional["GenerateServerPlacementQueryTargetEdgesNodeTenantNodeName"]


class GenerateServerPlacementQueryTargetEdgesNodeTenantNodeName(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryTargetEdgesNodeServer(BaseModel):
    node: Optional["GenerateServerPlacementQueryTargetEdgesNodeServerNode"]


class GenerateServerPlacementQueryTargetEdgesNodeServerNode(BaseModel):
    id: str
    name: Optional["GenerateServerPlacementQueryTargetEdgesNodeServerNodeName"]


class GenerateServerPlacementQueryTargetEdgesNodeServerNodeName(BaseModel):
    value: Optional[str]


class GenerateServerPlacementQueryComputePhysicalServer(BaseModel):
    edges: list["GenerateServerPlacementQueryComputePhysicalServerEdges"]


class GenerateServerPlacementQueryComputePhysicalServerEdges(BaseModel):
    node: Optional["GenerateServerPlacementQueryComputePhysicalServerEdgesNode"]


class GenerateServerPlacementQueryComputePhysicalServerEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateServerPlacementQueryComputePhysicalServerEdgesNodeName"]


class GenerateServerPlacementQueryComputePhysicalServerEdgesNodeName(BaseModel):
    value: Optional[str]


GenerateServerPlacementQuery.model_rebuild()
GenerateServerPlacementQueryTarget.model_rebuild()
GenerateServerPlacementQueryTargetEdges.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNode.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNodeRack.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNodeRackNode.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNodeTemplate.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNodeTemplateNode.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNodeTenant.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNodeTenantNode.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNodeServer.model_rebuild()
GenerateServerPlacementQueryTargetEdgesNodeServerNode.model_rebuild()
GenerateServerPlacementQueryComputePhysicalServer.model_rebuild()
GenerateServerPlacementQueryComputePhysicalServerEdges.model_rebuild()
GenerateServerPlacementQueryComputePhysicalServerEdgesNode.model_rebuild()
