from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ZoneAdvertisementCheckQuery(BaseModel):
    security_zone: "ZoneAdvertisementCheckQuerySecurityZone" = Field(
        alias="SecurityZone"
    )
    network_fabric: "ZoneAdvertisementCheckQueryNetworkFabric" = Field(
        alias="NetworkFabric"
    )
    service_app_access: "ZoneAdvertisementCheckQueryServiceAppAccess" = Field(
        alias="ServiceAppAccess"
    )


class ZoneAdvertisementCheckQuerySecurityZone(BaseModel):
    edges: list["ZoneAdvertisementCheckQuerySecurityZoneEdges"]


class ZoneAdvertisementCheckQuerySecurityZoneEdges(BaseModel):
    node: Optional["ZoneAdvertisementCheckQuerySecurityZoneEdgesNode"]


class ZoneAdvertisementCheckQuerySecurityZoneEdgesNode(BaseModel):
    id: str
    name: Optional["ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeName"]
    dc_advertised_prefix_list: Optional[
        "ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeDcAdvertisedPrefixList"
    ]
    advertising_device: (
        "ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDevice"
    )


class ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeName(BaseModel):
    value: Optional[str]


class ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeDcAdvertisedPrefixList(BaseModel):
    value: Optional[str]


class ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDevice(BaseModel):
    node: Optional[
        "ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDeviceNode"
    ]


class ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDeviceNode(BaseModel):
    id: str
    name: Optional[
        "ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDeviceNodeName"
    ]
    avd_custom_hostvars: Optional[
        "ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDeviceNodeAvdCustomHostvars"
    ]


class ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDeviceNodeAvdCustomHostvars(
    BaseModel
):
    value: Optional[Any]


class ZoneAdvertisementCheckQueryNetworkFabric(BaseModel):
    edges: list["ZoneAdvertisementCheckQueryNetworkFabricEdges"]


class ZoneAdvertisementCheckQueryNetworkFabricEdges(BaseModel):
    node: Optional["ZoneAdvertisementCheckQueryNetworkFabricEdgesNode"]


class ZoneAdvertisementCheckQueryNetworkFabricEdgesNode(BaseModel):
    id: str
    name: Optional["ZoneAdvertisementCheckQueryNetworkFabricEdgesNodeName"]
    avd_custom_hostvars: Optional[
        "ZoneAdvertisementCheckQueryNetworkFabricEdgesNodeAvdCustomHostvars"
    ]


class ZoneAdvertisementCheckQueryNetworkFabricEdgesNodeName(BaseModel):
    value: Optional[str]


class ZoneAdvertisementCheckQueryNetworkFabricEdgesNodeAvdCustomHostvars(BaseModel):
    value: Optional[Any]


class ZoneAdvertisementCheckQueryServiceAppAccess(BaseModel):
    edges: list["ZoneAdvertisementCheckQueryServiceAppAccessEdges"]


class ZoneAdvertisementCheckQueryServiceAppAccessEdges(BaseModel):
    node: Optional["ZoneAdvertisementCheckQueryServiceAppAccessEdgesNode"]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNode(BaseModel):
    id: str
    name: Optional["ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeName"]
    approved: Optional["ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApproved"]
    destination_vip: (
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeDestinationVip"
    )
    application: "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplication"
    source_zone: "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeSourceZone"


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeName(BaseModel):
    value: Optional[str]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApproved(BaseModel):
    value: Optional[bool]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeDestinationVip(BaseModel):
    node: Optional[
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeDestinationVipNode"
    ]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeDestinationVipNode(BaseModel):
    id: str
    address: Optional[
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeDestinationVipNodeAddress"
    ]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeDestinationVipNodeAddress(
    BaseModel
):
    value: Optional[str]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplication(BaseModel):
    node: Optional[
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNode"
    ]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNode(BaseModel):
    id: str
    name: Optional[
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeName"
    ]
    exposed: Optional[
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeExposed"
    ]
    vip_block: (
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeVipBlock"
    )


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeName(
    BaseModel
):
    value: Optional[str]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeExposed(
    BaseModel
):
    value: Optional[bool]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeVipBlock(
    BaseModel
):
    node: Optional[
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeVipBlockNode"
    ]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeVipBlockNode(
    BaseModel
):
    id: str
    prefix: Optional[
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeVipBlockNodePrefix"
    ]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeVipBlockNodePrefix(
    BaseModel
):
    value: Optional[str]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeSourceZone(BaseModel):
    node: Optional["ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeSourceZoneNode"]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeSourceZoneNode(BaseModel):
    id: str
    name: Optional[
        "ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeSourceZoneNodeName"
    ]


class ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeSourceZoneNodeName(BaseModel):
    value: Optional[str]


ZoneAdvertisementCheckQuery.model_rebuild()
ZoneAdvertisementCheckQuerySecurityZone.model_rebuild()
ZoneAdvertisementCheckQuerySecurityZoneEdges.model_rebuild()
ZoneAdvertisementCheckQuerySecurityZoneEdgesNode.model_rebuild()
ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDevice.model_rebuild()
ZoneAdvertisementCheckQuerySecurityZoneEdgesNodeAdvertisingDeviceNode.model_rebuild()
ZoneAdvertisementCheckQueryNetworkFabric.model_rebuild()
ZoneAdvertisementCheckQueryNetworkFabricEdges.model_rebuild()
ZoneAdvertisementCheckQueryNetworkFabricEdgesNode.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccess.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdges.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNode.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeDestinationVip.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeDestinationVipNode.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplication.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNode.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeVipBlock.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeApplicationNodeVipBlockNode.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeSourceZone.model_rebuild()
ZoneAdvertisementCheckQueryServiceAppAccessEdgesNodeSourceZoneNode.model_rebuild()
