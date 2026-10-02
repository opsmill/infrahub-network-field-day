from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CrossplaneFabricAppQuery(BaseModel):
    target: "CrossplaneFabricAppQueryTarget"
    monitoring_profile: "CrossplaneFabricAppQueryMonitoringProfile" = Field(
        alias="MonitoringProfile"
    )


class CrossplaneFabricAppQueryTarget(BaseModel):
    edges: list["CrossplaneFabricAppQueryTargetEdges"]


class CrossplaneFabricAppQueryTargetEdges(BaseModel):
    node: Optional["CrossplaneFabricAppQueryTargetEdgesNode"]


class CrossplaneFabricAppQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["CrossplaneFabricAppQueryTargetEdgesNodeName"]
    status: Optional["CrossplaneFabricAppQueryTargetEdgesNodeStatus"]
    namespace_name: Optional["CrossplaneFabricAppQueryTargetEdgesNodeNamespaceName"]
    exposed: Optional["CrossplaneFabricAppQueryTargetEdgesNodeExposed"]
    sso_provider: Optional["CrossplaneFabricAppQueryTargetEdgesNodeSsoProvider"]
    chart_repository: Optional["CrossplaneFabricAppQueryTargetEdgesNodeChartRepository"]
    chart_name: Optional["CrossplaneFabricAppQueryTargetEdgesNodeChartName"]
    chart_version: Optional["CrossplaneFabricAppQueryTargetEdgesNodeChartVersion"]
    chart_values: Optional["CrossplaneFabricAppQueryTargetEdgesNodeChartValues"]
    service_selector: Optional["CrossplaneFabricAppQueryTargetEdgesNodeServiceSelector"]
    communities: Optional["CrossplaneFabricAppQueryTargetEdgesNodeCommunities"]
    workload_selector: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodeWorkloadSelector"
    ]
    policy_default_deny: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodePolicyDefaultDeny"
    ]
    policy_allow_dns: Optional["CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowDns"]
    policy_allow_intra_namespace: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowIntraNamespace"
    ]
    policy_allow_egress_api_server: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowEgressApiServer"
    ]
    policy_allow_egress_internet: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowEgressInternet"
    ]
    policy_allow_ports: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowPorts"
    ]
    vrf: "CrossplaneFabricAppQueryTargetEdgesNodeVrf"
    vip_block: "CrossplaneFabricAppQueryTargetEdgesNodeVipBlock"
    allowed_source_prefixes: (
        "CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixes"
    )
    advertised_services: "CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServices"
    values_file: "CrossplaneFabricAppQueryTargetEdgesNodeValuesFile"


class CrossplaneFabricAppQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeNamespaceName(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeExposed(BaseModel):
    value: Optional[bool]


class CrossplaneFabricAppQueryTargetEdgesNodeSsoProvider(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeChartRepository(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeChartName(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeChartVersion(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeChartValues(BaseModel):
    value: Optional[Any]


class CrossplaneFabricAppQueryTargetEdgesNodeServiceSelector(BaseModel):
    value: Optional[Any]


class CrossplaneFabricAppQueryTargetEdgesNodeCommunities(BaseModel):
    value: Optional[Any]


class CrossplaneFabricAppQueryTargetEdgesNodeWorkloadSelector(BaseModel):
    value: Optional[Any]


class CrossplaneFabricAppQueryTargetEdgesNodePolicyDefaultDeny(BaseModel):
    value: Optional[bool]


class CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowDns(BaseModel):
    value: Optional[bool]


class CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowIntraNamespace(BaseModel):
    value: Optional[bool]


class CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowEgressApiServer(BaseModel):
    value: Optional[bool]


class CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowEgressInternet(BaseModel):
    value: Optional[bool]


class CrossplaneFabricAppQueryTargetEdgesNodePolicyAllowPorts(BaseModel):
    value: Optional[Any]


class CrossplaneFabricAppQueryTargetEdgesNodeVrf(BaseModel):
    node: Optional["CrossplaneFabricAppQueryTargetEdgesNodeVrfNode"]


class CrossplaneFabricAppQueryTargetEdgesNodeVrfNode(BaseModel):
    id: str
    name: Optional["CrossplaneFabricAppQueryTargetEdgesNodeVrfNodeName"]


class CrossplaneFabricAppQueryTargetEdgesNodeVrfNodeName(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeVipBlock(BaseModel):
    node: Optional["CrossplaneFabricAppQueryTargetEdgesNodeVipBlockNode"]


class CrossplaneFabricAppQueryTargetEdgesNodeVipBlockNode(BaseModel):
    id: str
    prefix: Optional["CrossplaneFabricAppQueryTargetEdgesNodeVipBlockNodePrefix"]


class CrossplaneFabricAppQueryTargetEdgesNodeVipBlockNodePrefix(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixes(BaseModel):
    edges: list["CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixesEdges"]


class CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixesEdges(BaseModel):
    node: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixesEdgesNode"
    ]


class CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixesEdgesNode(BaseModel):
    id: str
    prefix: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixesEdgesNodePrefix"
    ]


class CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixesEdgesNodePrefix(
    BaseModel
):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServices(BaseModel):
    edges: list["CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdges"]


class CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdges(BaseModel):
    node: Optional["CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNode"]


class CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNode(BaseModel):
    id: str
    port: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodePort"
    ]
    ip_protocol: (
        "CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodeIpProtocol"
    )


class CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodePort(BaseModel):
    value: Optional[Any]


class CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodeIpProtocol(
    BaseModel
):
    node: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodeIpProtocolNode"
    ]


class CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodeIpProtocolNode(
    BaseModel
):
    id: str
    name: Optional[
        "CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodeIpProtocolNodeName"
    ]


class CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodeIpProtocolNodeName(
    BaseModel
):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeValuesFile(BaseModel):
    node: Optional["CrossplaneFabricAppQueryTargetEdgesNodeValuesFileNode"]


class CrossplaneFabricAppQueryTargetEdgesNodeValuesFileNode(BaseModel):
    id: str
    file_name: Optional["CrossplaneFabricAppQueryTargetEdgesNodeValuesFileNodeFileName"]
    checksum: Optional["CrossplaneFabricAppQueryTargetEdgesNodeValuesFileNodeChecksum"]


class CrossplaneFabricAppQueryTargetEdgesNodeValuesFileNodeFileName(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeValuesFileNodeChecksum(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryMonitoringProfile(BaseModel):
    edges: list["CrossplaneFabricAppQueryMonitoringProfileEdges"]


class CrossplaneFabricAppQueryMonitoringProfileEdges(BaseModel):
    node: Optional["CrossplaneFabricAppQueryMonitoringProfileEdgesNode"]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNode(BaseModel):
    id: str
    name: Optional["CrossplaneFabricAppQueryMonitoringProfileEdgesNodeName"]
    enabled: Optional["CrossplaneFabricAppQueryMonitoringProfileEdgesNodeEnabled"]
    service_kind: Optional[
        "CrossplaneFabricAppQueryMonitoringProfileEdgesNodeServiceKind"
    ]
    measurements: "CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurements"
    collector: "CrossplaneFabricAppQueryMonitoringProfileEdgesNodeCollector"


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeName(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeEnabled(BaseModel):
    value: Optional[bool]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeServiceKind(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurements(BaseModel):
    edges: list["CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurementsEdges"]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurementsEdges(BaseModel):
    node: Optional[
        "CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurementsEdgesNode"
    ]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurementsEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurementsEdgesNodeName"
    ]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurementsEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeCollector(BaseModel):
    node: Optional["CrossplaneFabricAppQueryMonitoringProfileEdgesNodeCollectorNode"]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeCollectorNode(BaseModel):
    id: str
    namespace_name: Optional[
        "CrossplaneFabricAppQueryMonitoringProfileEdgesNodeCollectorNodeNamespaceName"
    ]


class CrossplaneFabricAppQueryMonitoringProfileEdgesNodeCollectorNodeNamespaceName(
    BaseModel
):
    value: Optional[str]


CrossplaneFabricAppQuery.model_rebuild()
CrossplaneFabricAppQueryTarget.model_rebuild()
CrossplaneFabricAppQueryTargetEdges.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNode.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeVrf.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeVrfNode.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeVipBlock.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeVipBlockNode.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixes.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixesEdges.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeAllowedSourcePrefixesEdgesNode.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServices.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdges.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNode.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodeIpProtocol.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeAdvertisedServicesEdgesNodeIpProtocolNode.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeValuesFile.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeValuesFileNode.model_rebuild()
CrossplaneFabricAppQueryMonitoringProfile.model_rebuild()
CrossplaneFabricAppQueryMonitoringProfileEdges.model_rebuild()
CrossplaneFabricAppQueryMonitoringProfileEdgesNode.model_rebuild()
CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurements.model_rebuild()
CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurementsEdges.model_rebuild()
CrossplaneFabricAppQueryMonitoringProfileEdgesNodeMeasurementsEdgesNode.model_rebuild()
CrossplaneFabricAppQueryMonitoringProfileEdgesNodeCollector.model_rebuild()
CrossplaneFabricAppQueryMonitoringProfileEdgesNodeCollectorNode.model_rebuild()
