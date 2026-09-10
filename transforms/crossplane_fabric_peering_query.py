from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CrossplaneFabricPeeringQuery(BaseModel):
    target: "CrossplaneFabricPeeringQueryTarget"


class CrossplaneFabricPeeringQueryTarget(BaseModel):
    edges: list["CrossplaneFabricPeeringQueryTargetEdges"]


class CrossplaneFabricPeeringQueryTargetEdges(BaseModel):
    node: Optional["CrossplaneFabricPeeringQueryTargetEdgesNode"]


class CrossplaneFabricPeeringQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeName"]
    status: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeStatus"]
    communities: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeCommunities"]
    advertisement_selector: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeAdvertisementSelector"]
    cluster: "CrossplaneFabricPeeringQueryTargetEdgesNodeCluster"
    peerings: "CrossplaneFabricPeeringQueryTargetEdgesNodePeerings"


class CrossplaneFabricPeeringQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class CrossplaneFabricPeeringQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class CrossplaneFabricPeeringQueryTargetEdgesNodeCommunities(BaseModel):
    value: Optional[Any]


class CrossplaneFabricPeeringQueryTargetEdgesNodeAdvertisementSelector(BaseModel):
    value: Optional[Any]


class CrossplaneFabricPeeringQueryTargetEdgesNodeCluster(BaseModel):
    node: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNode"]


class CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNode(BaseModel):
    id: str
    name: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeName"]
    local_asn: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeLocalAsn"]
    bgp_auth_secret_name: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeBgpAuthSecretName"]
    bgp_timers: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeBgpTimers"]
    pod_cidr_communities: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodePodCidrCommunities"]
    node_selector: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeNodeSelector"]
    advertisement_selector: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeAdvertisementSelector"]


class CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeName(BaseModel):
    value: Optional[str]


class CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeLocalAsn(BaseModel):
    value: Optional[Any]


class CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeBgpAuthSecretName(BaseModel):
    value: Optional[str]


class CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeBgpTimers(BaseModel):
    value: Optional[Any]


class CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodePodCidrCommunities(BaseModel):
    value: Optional[Any]


class CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeNodeSelector(BaseModel):
    value: Optional[Any]


class CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNodeAdvertisementSelector(BaseModel):
    value: Optional[Any]


class CrossplaneFabricPeeringQueryTargetEdgesNodePeerings(BaseModel):
    edges: list["CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdges"]


class CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdges(BaseModel):
    node: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNode"]


class CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNode(BaseModel):
    id: str
    name: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodeName"]
    peer_asn: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAsn"]
    enabled: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodeEnabled"]
    peer_address: "CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAddress"


class CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodeName(BaseModel):
    value: Optional[str]


class CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAsn(BaseModel):
    value: Optional[Any]


class CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodeEnabled(BaseModel):
    value: Optional[bool]


class CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAddress(BaseModel):
    node: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAddressNode"]


class CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAddressNode(BaseModel):
    address: Optional["CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAddressNodeAddress"]


class CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAddressNodeAddress(BaseModel):
    value: Optional[str]


CrossplaneFabricPeeringQuery.model_rebuild()
CrossplaneFabricPeeringQueryTarget.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdges.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdgesNode.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdgesNodeCluster.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdgesNodeClusterNode.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdgesNodePeerings.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdges.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNode.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAddress.model_rebuild()
CrossplaneFabricPeeringQueryTargetEdgesNodePeeringsEdgesNodePeerAddressNode.model_rebuild()
