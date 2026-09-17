from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class WanServiceCheckQuery(BaseModel):
    service_l_3_vpn: "WanServiceCheckQueryServiceL3Vpn" = Field(alias="ServiceL3vpn")
    service_tenant_cloud: "WanServiceCheckQueryServiceTenantCloud" = Field(
        alias="ServiceTenantCloud"
    )


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


WanServiceCheckQuery.model_rebuild()
WanServiceCheckQueryServiceL3Vpn.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdges.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNode.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeTenant.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeTenantNode.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeVrf.model_rebuild()
WanServiceCheckQueryServiceL3VpnEdgesNodeVrfNode.model_rebuild()
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
