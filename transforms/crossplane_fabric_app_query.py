from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CrossplaneFabricAppQuery(BaseModel):
    target: "CrossplaneFabricAppQueryTarget"


class CrossplaneFabricAppQueryTarget(BaseModel):
    edges: list["CrossplaneFabricAppQueryTargetEdges"]


class CrossplaneFabricAppQueryTargetEdges(BaseModel):
    node: Optional["CrossplaneFabricAppQueryTargetEdgesNode"]


class CrossplaneFabricAppQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["CrossplaneFabricAppQueryTargetEdgesNodeName"]
    namespace_name: Optional["CrossplaneFabricAppQueryTargetEdgesNodeNamespaceName"]
    exposed: Optional["CrossplaneFabricAppQueryTargetEdgesNodeExposed"]
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
    values_file: "CrossplaneFabricAppQueryTargetEdgesNodeValuesFile"


class CrossplaneFabricAppQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeNamespaceName(BaseModel):
    value: Optional[str]


class CrossplaneFabricAppQueryTargetEdgesNodeExposed(BaseModel):
    value: Optional[bool]


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
CrossplaneFabricAppQueryTargetEdgesNodeValuesFile.model_rebuild()
CrossplaneFabricAppQueryTargetEdgesNodeValuesFileNode.model_rebuild()
