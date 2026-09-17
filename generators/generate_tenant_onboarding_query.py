from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class GenerateTenantOnboardingQuery(BaseModel):
    target: "GenerateTenantOnboardingQueryTarget"
    evpn_tenant: "GenerateTenantOnboardingQueryEvpnTenant" = Field(alias="EvpnTenant")


class GenerateTenantOnboardingQueryTarget(BaseModel):
    edges: list["GenerateTenantOnboardingQueryTargetEdges"]


class GenerateTenantOnboardingQueryTargetEdges(BaseModel):
    node: Optional["GenerateTenantOnboardingQueryTargetEdgesNode"]


class GenerateTenantOnboardingQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeName"]
    description: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeDescription"]
    status: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeStatus"]
    mac_vrf_vni_base: Optional[
        "GenerateTenantOnboardingQueryTargetEdgesNodeMacVrfVniBase"
    ]
    organization: "GenerateTenantOnboardingQueryTargetEdgesNodeOrganization"
    fabric: "GenerateTenantOnboardingQueryTargetEdgesNodeFabric"
    evpn_tenant: "GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenant"


class GenerateTenantOnboardingQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateTenantOnboardingQueryTargetEdgesNodeDescription(BaseModel):
    value: Optional[str]


class GenerateTenantOnboardingQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class GenerateTenantOnboardingQueryTargetEdgesNodeMacVrfVniBase(BaseModel):
    value: Optional[Any]


class GenerateTenantOnboardingQueryTargetEdgesNodeOrganization(BaseModel):
    node: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeOrganizationNode"]


class GenerateTenantOnboardingQueryTargetEdgesNodeOrganizationNode(BaseModel):
    id: str
    name: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeOrganizationNodeName"]


class GenerateTenantOnboardingQueryTargetEdgesNodeOrganizationNodeName(BaseModel):
    value: Optional[str]


class GenerateTenantOnboardingQueryTargetEdgesNodeFabric(BaseModel):
    node: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeFabricNode"]


class GenerateTenantOnboardingQueryTargetEdgesNodeFabricNode(BaseModel):
    id: str
    name: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeFabricNodeName"]


class GenerateTenantOnboardingQueryTargetEdgesNodeFabricNodeName(BaseModel):
    value: Optional[str]


class GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenant(BaseModel):
    node: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenantNode"]


class GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenantNode(BaseModel):
    id: str
    name: Optional["GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenantNodeName"]
    mac_vrf_vni_base: Optional[
        "GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenantNodeMacVrfVniBase"
    ]


class GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenantNodeName(BaseModel):
    value: Optional[str]


class GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenantNodeMacVrfVniBase(
    BaseModel
):
    value: Optional[Any]


class GenerateTenantOnboardingQueryEvpnTenant(BaseModel):
    edges: list["GenerateTenantOnboardingQueryEvpnTenantEdges"]


class GenerateTenantOnboardingQueryEvpnTenantEdges(BaseModel):
    node: Optional["GenerateTenantOnboardingQueryEvpnTenantEdgesNode"]


class GenerateTenantOnboardingQueryEvpnTenantEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateTenantOnboardingQueryEvpnTenantEdgesNodeName"]
    mac_vrf_vni_base: Optional[
        "GenerateTenantOnboardingQueryEvpnTenantEdgesNodeMacVrfVniBase"
    ]


class GenerateTenantOnboardingQueryEvpnTenantEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateTenantOnboardingQueryEvpnTenantEdgesNodeMacVrfVniBase(BaseModel):
    value: Optional[Any]


GenerateTenantOnboardingQuery.model_rebuild()
GenerateTenantOnboardingQueryTarget.model_rebuild()
GenerateTenantOnboardingQueryTargetEdges.model_rebuild()
GenerateTenantOnboardingQueryTargetEdgesNode.model_rebuild()
GenerateTenantOnboardingQueryTargetEdgesNodeOrganization.model_rebuild()
GenerateTenantOnboardingQueryTargetEdgesNodeOrganizationNode.model_rebuild()
GenerateTenantOnboardingQueryTargetEdgesNodeFabric.model_rebuild()
GenerateTenantOnboardingQueryTargetEdgesNodeFabricNode.model_rebuild()
GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenant.model_rebuild()
GenerateTenantOnboardingQueryTargetEdgesNodeEvpnTenantNode.model_rebuild()
GenerateTenantOnboardingQueryEvpnTenant.model_rebuild()
GenerateTenantOnboardingQueryEvpnTenantEdges.model_rebuild()
GenerateTenantOnboardingQueryEvpnTenantEdgesNode.model_rebuild()
