from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DnsZoneCheckQuery(BaseModel):
    service_fabric_app: "DnsZoneCheckQueryServiceFabricApp" = Field(
        alias="ServiceFabricApp"
    )
    ipam_ip_address: "DnsZoneCheckQueryIpamIpAddress" = Field(alias="IpamIPAddress")


class DnsZoneCheckQueryServiceFabricApp(BaseModel):
    edges: list["DnsZoneCheckQueryServiceFabricAppEdges"]


class DnsZoneCheckQueryServiceFabricAppEdges(BaseModel):
    node: Optional["DnsZoneCheckQueryServiceFabricAppEdgesNode"]


class DnsZoneCheckQueryServiceFabricAppEdgesNode(BaseModel):
    id: str
    name: Optional["DnsZoneCheckQueryServiceFabricAppEdgesNodeName"]
    status: Optional["DnsZoneCheckQueryServiceFabricAppEdgesNodeStatus"]
    exposed: Optional["DnsZoneCheckQueryServiceFabricAppEdgesNodeExposed"]
    dns_zone: Optional["DnsZoneCheckQueryServiceFabricAppEdgesNodeDnsZone"]
    vip_block: "DnsZoneCheckQueryServiceFabricAppEdgesNodeVipBlock"


class DnsZoneCheckQueryServiceFabricAppEdgesNodeName(BaseModel):
    value: Optional[str]


class DnsZoneCheckQueryServiceFabricAppEdgesNodeStatus(BaseModel):
    value: Optional[str]


class DnsZoneCheckQueryServiceFabricAppEdgesNodeExposed(BaseModel):
    value: Optional[bool]


class DnsZoneCheckQueryServiceFabricAppEdgesNodeDnsZone(BaseModel):
    value: Optional[str]


class DnsZoneCheckQueryServiceFabricAppEdgesNodeVipBlock(BaseModel):
    node: Optional["DnsZoneCheckQueryServiceFabricAppEdgesNodeVipBlockNode"]


class DnsZoneCheckQueryServiceFabricAppEdgesNodeVipBlockNode(BaseModel):
    id: str
    prefix: Optional["DnsZoneCheckQueryServiceFabricAppEdgesNodeVipBlockNodePrefix"]


class DnsZoneCheckQueryServiceFabricAppEdgesNodeVipBlockNodePrefix(BaseModel):
    value: Optional[str]


class DnsZoneCheckQueryIpamIpAddress(BaseModel):
    edges: list["DnsZoneCheckQueryIpamIpAddressEdges"]


class DnsZoneCheckQueryIpamIpAddressEdges(BaseModel):
    node: Optional["DnsZoneCheckQueryIpamIpAddressEdgesNode"]


class DnsZoneCheckQueryIpamIpAddressEdgesNode(BaseModel):
    id: str
    address: Optional["DnsZoneCheckQueryIpamIpAddressEdgesNodeAddress"]
    fqdn: Optional["DnsZoneCheckQueryIpamIpAddressEdgesNodeFqdn"]


class DnsZoneCheckQueryIpamIpAddressEdgesNodeAddress(BaseModel):
    value: Optional[str]


class DnsZoneCheckQueryIpamIpAddressEdgesNodeFqdn(BaseModel):
    value: Optional[str]


DnsZoneCheckQuery.model_rebuild()
DnsZoneCheckQueryServiceFabricApp.model_rebuild()
DnsZoneCheckQueryServiceFabricAppEdges.model_rebuild()
DnsZoneCheckQueryServiceFabricAppEdgesNode.model_rebuild()
DnsZoneCheckQueryServiceFabricAppEdgesNodeVipBlock.model_rebuild()
DnsZoneCheckQueryServiceFabricAppEdgesNodeVipBlockNode.model_rebuild()
DnsZoneCheckQueryIpamIpAddress.model_rebuild()
DnsZoneCheckQueryIpamIpAddressEdges.model_rebuild()
DnsZoneCheckQueryIpamIpAddressEdgesNode.model_rebuild()
