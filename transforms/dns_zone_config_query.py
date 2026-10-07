from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DnsZoneConfigQuery(BaseModel):
    target: "DnsZoneConfigQueryTarget"
    records: "DnsZoneConfigQueryRecords"
    apps: "DnsZoneConfigQueryApps"


class DnsZoneConfigQueryTarget(BaseModel):
    edges: list["DnsZoneConfigQueryTargetEdges"]


class DnsZoneConfigQueryTargetEdges(BaseModel):
    node: Optional["DnsZoneConfigQueryTargetEdgesNode"]


class DnsZoneConfigQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["DnsZoneConfigQueryTargetEdgesNodeName"]
    dns_zone: Optional["DnsZoneConfigQueryTargetEdgesNodeDnsZone"]
    namespace_name: Optional["DnsZoneConfigQueryTargetEdgesNodeNamespaceName"]


class DnsZoneConfigQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class DnsZoneConfigQueryTargetEdgesNodeDnsZone(BaseModel):
    value: Optional[str]


class DnsZoneConfigQueryTargetEdgesNodeNamespaceName(BaseModel):
    value: Optional[str]


class DnsZoneConfigQueryRecords(BaseModel):
    edges: list["DnsZoneConfigQueryRecordsEdges"]


class DnsZoneConfigQueryRecordsEdges(BaseModel):
    node: Optional["DnsZoneConfigQueryRecordsEdgesNode"]


class DnsZoneConfigQueryRecordsEdgesNode(BaseModel):
    id: str
    address: Optional["DnsZoneConfigQueryRecordsEdgesNodeAddress"]
    fqdn: Optional["DnsZoneConfigQueryRecordsEdgesNodeFqdn"]


class DnsZoneConfigQueryRecordsEdgesNodeAddress(BaseModel):
    value: Optional[str]


class DnsZoneConfigQueryRecordsEdgesNodeFqdn(BaseModel):
    value: Optional[str]


class DnsZoneConfigQueryApps(BaseModel):
    edges: list["DnsZoneConfigQueryAppsEdges"]


class DnsZoneConfigQueryAppsEdges(BaseModel):
    node: Optional["DnsZoneConfigQueryAppsEdgesNode"]


class DnsZoneConfigQueryAppsEdgesNode(BaseModel):
    id: str
    name: Optional["DnsZoneConfigQueryAppsEdgesNodeName"]
    status: Optional["DnsZoneConfigQueryAppsEdgesNodeStatus"]
    exposed: Optional["DnsZoneConfigQueryAppsEdgesNodeExposed"]


class DnsZoneConfigQueryAppsEdgesNodeName(BaseModel):
    value: Optional[str]


class DnsZoneConfigQueryAppsEdgesNodeStatus(BaseModel):
    value: Optional[str]


class DnsZoneConfigQueryAppsEdgesNodeExposed(BaseModel):
    value: Optional[bool]


DnsZoneConfigQuery.model_rebuild()
DnsZoneConfigQueryTarget.model_rebuild()
DnsZoneConfigQueryTargetEdges.model_rebuild()
DnsZoneConfigQueryTargetEdgesNode.model_rebuild()
DnsZoneConfigQueryRecords.model_rebuild()
DnsZoneConfigQueryRecordsEdges.model_rebuild()
DnsZoneConfigQueryRecordsEdgesNode.model_rebuild()
DnsZoneConfigQueryApps.model_rebuild()
DnsZoneConfigQueryAppsEdges.model_rebuild()
DnsZoneConfigQueryAppsEdgesNode.model_rebuild()
