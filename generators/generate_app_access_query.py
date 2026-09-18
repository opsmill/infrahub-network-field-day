from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class GenerateAppAccessQuery(BaseModel):
    target: "GenerateAppAccessQueryTarget"
    service_app_access: "GenerateAppAccessQueryServiceAppAccess" = Field(
        alias="ServiceAppAccess"
    )
    security_policy: "GenerateAppAccessQuerySecurityPolicy" = Field(
        alias="SecurityPolicy"
    )
    security_zone: "GenerateAppAccessQuerySecurityZone" = Field(alias="SecurityZone")
    security_service: "GenerateAppAccessQuerySecurityService" = Field(
        alias="SecurityService"
    )
    security_ip_protocol: "GenerateAppAccessQuerySecurityIpProtocol" = Field(
        alias="SecurityIPProtocol"
    )
    security_generic_address: "GenerateAppAccessQuerySecurityGenericAddress" = Field(
        alias="SecurityGenericAddress"
    )


class GenerateAppAccessQueryTarget(BaseModel):
    edges: list["GenerateAppAccessQueryTargetEdges"]


class GenerateAppAccessQueryTargetEdges(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNode"]


class GenerateAppAccessQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryTargetEdgesNodeName"]
    status: Optional["GenerateAppAccessQueryTargetEdgesNodeStatus"]
    requester: Optional["GenerateAppAccessQueryTargetEdgesNodeRequester"]
    justification: Optional["GenerateAppAccessQueryTargetEdgesNodeJustification"]
    ports: Optional["GenerateAppAccessQueryTargetEdgesNodePorts"]
    application: "GenerateAppAccessQueryTargetEdgesNodeApplication"
    source_site: "GenerateAppAccessQueryTargetEdgesNodeSourceSite"
    source_zone: "GenerateAppAccessQueryTargetEdgesNodeSourceZone"
    source_address: "GenerateAppAccessQueryTargetEdgesNodeSourceAddress"
    destination_vip: "GenerateAppAccessQueryTargetEdgesNodeDestinationVip"
    granted_source_prefixes: (
        "GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixes"
    )
    granted_rules: "GenerateAppAccessQueryTargetEdgesNodeGrantedRules"


class GenerateAppAccessQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeRequester(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeJustification(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodePorts(BaseModel):
    value: Optional[Any]


class GenerateAppAccessQueryTargetEdgesNodeApplication(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeApplicationNode"]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryTargetEdgesNodeApplicationNodeName"]
    manifests: Optional["GenerateAppAccessQueryTargetEdgesNodeApplicationNodeManifests"]
    manifests_file: "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeManifestsFile"
    service_selector: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeServiceSelector"
    ]
    allowed_source_prefixes: (
        "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixes"
    )
    vip_block: "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVipBlock"
    vrf: "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrf"


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeManifests(BaseModel):
    value: Optional[Any]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeManifestsFile(BaseModel):
    node: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeManifestsFileNode"
    ]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeManifestsFileNode(BaseModel):
    id: str


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeServiceSelector(BaseModel):
    value: Optional[Any]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixes(
    BaseModel
):
    edges: list[
        "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixesEdges"
    ]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixesEdges(
    BaseModel
):
    node: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixesEdgesNode"
    ]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixesEdgesNode(
    BaseModel
):
    id: str
    prefix: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixesEdgesNodePrefix"
    ]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixesEdgesNodePrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVipBlock(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVipBlockNode"]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVipBlockNode(BaseModel):
    id: str
    prefix: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVipBlockNodePrefix"
    ]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVipBlockNodePrefix(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrf(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNode"]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNodeName"]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceSite(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeSourceSiteNode"]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeName"]
    security_zone: "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZone"
    security_source_address: (
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddress"
    )


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZone(BaseModel):
    node: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNode"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNode(BaseModel):
    id: str
    name: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeName"
    ]
    dc_advertised_prefix_list: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeDcAdvertisedPrefixList"
    ]
    advertising_device: "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDevice"


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeDcAdvertisedPrefixList(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDevice(
    BaseModel
):
    node: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDeviceNode"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDeviceNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDeviceNodeName"
    ]
    avd_custom_hostvars: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDeviceNodeAvdCustomHostvars"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDeviceNodeAvdCustomHostvars(
    BaseModel
):
    value: Optional[Any]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddress(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityGenericAddress",
                "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityGenericAddress(
    BaseModel
):
    typename__: Literal[
        "SecurityFQDN",
        "SecurityGenericAddress",
        "SecurityIPAMIPAddress",
        "SecurityIPAddress",
        "SecurityIPRange",
        "SecurityPrefix",
    ] = Field(alias="__typename")
    id: Optional[str]
    display_label: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefix(
    BaseModel
):
    typename__: Literal["SecurityIPAMIPPrefix"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    ip_prefix: "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefixIpPrefix"


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefixIpPrefix(
    BaseModel
):
    node: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefixIpPrefixNode"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefixIpPrefixNode(
    BaseModel
):
    id: str
    prefix: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefixIpPrefixNodePrefix"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefixIpPrefixNodePrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceZone(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeSourceZoneNode"]


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeName"]
    dc_advertised_prefix_list: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeDcAdvertisedPrefixList"
    ]
    advertising_device: (
        "GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDevice"
    )


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeDcAdvertisedPrefixList(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDevice(BaseModel):
    node: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDeviceNode"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDeviceNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDeviceNodeName"
    ]
    avd_custom_hostvars: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDeviceNodeAvdCustomHostvars"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDeviceNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDeviceNodeAvdCustomHostvars(
    BaseModel
):
    value: Optional[Any]


class GenerateAppAccessQueryTargetEdgesNodeSourceAddress(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityGenericAddress",
                "GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityGenericAddress(
    BaseModel
):
    typename__: Literal[
        "SecurityFQDN",
        "SecurityGenericAddress",
        "SecurityIPAMIPAddress",
        "SecurityIPAddress",
        "SecurityIPRange",
        "SecurityPrefix",
    ] = Field(alias="__typename")
    id: Optional[str]
    display_label: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefix(
    BaseModel
):
    typename__: Literal["SecurityIPAMIPPrefix"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    ip_prefix: "GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefixIpPrefix"


class GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefixIpPrefix(
    BaseModel
):
    node: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefixIpPrefixNode"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefixIpPrefixNode(
    BaseModel
):
    id: str
    prefix: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefixIpPrefixNodePrefix"
    ]


class GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefixIpPrefixNodePrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeDestinationVip(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeDestinationVipNode"]


class GenerateAppAccessQueryTargetEdgesNodeDestinationVipNode(BaseModel):
    id: str
    address: Optional["GenerateAppAccessQueryTargetEdgesNodeDestinationVipNodeAddress"]


class GenerateAppAccessQueryTargetEdgesNodeDestinationVipNodeAddress(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixes(BaseModel):
    edges: list["GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixesEdges"]


class GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixesEdges(BaseModel):
    node: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixesEdgesNode"
    ]


class GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixesEdgesNode(BaseModel):
    id: str
    prefix: Optional[
        "GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixesEdgesNodePrefix"
    ]


class GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixesEdgesNodePrefix(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeGrantedRules(BaseModel):
    edges: list["GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdges"]


class GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdges(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdgesNode"]


class GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdgesNodeName"]


class GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryServiceAppAccess(BaseModel):
    edges: list["GenerateAppAccessQueryServiceAppAccessEdges"]


class GenerateAppAccessQueryServiceAppAccessEdges(BaseModel):
    node: Optional["GenerateAppAccessQueryServiceAppAccessEdgesNode"]


class GenerateAppAccessQueryServiceAppAccessEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryServiceAppAccessEdgesNodeName"]
    status: Optional["GenerateAppAccessQueryServiceAppAccessEdgesNodeStatus"]
    application: "GenerateAppAccessQueryServiceAppAccessEdgesNodeApplication"
    granted_source_prefixes: (
        "GenerateAppAccessQueryServiceAppAccessEdgesNodeGrantedSourcePrefixes"
    )


class GenerateAppAccessQueryServiceAppAccessEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryServiceAppAccessEdgesNodeStatus(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryServiceAppAccessEdgesNodeApplication(BaseModel):
    node: Optional["GenerateAppAccessQueryServiceAppAccessEdgesNodeApplicationNode"]


class GenerateAppAccessQueryServiceAppAccessEdgesNodeApplicationNode(BaseModel):
    id: str


class GenerateAppAccessQueryServiceAppAccessEdgesNodeGrantedSourcePrefixes(BaseModel):
    edges: list[
        "GenerateAppAccessQueryServiceAppAccessEdgesNodeGrantedSourcePrefixesEdges"
    ]


class GenerateAppAccessQueryServiceAppAccessEdgesNodeGrantedSourcePrefixesEdges(
    BaseModel
):
    node: Optional[
        "GenerateAppAccessQueryServiceAppAccessEdgesNodeGrantedSourcePrefixesEdgesNode"
    ]


class GenerateAppAccessQueryServiceAppAccessEdgesNodeGrantedSourcePrefixesEdgesNode(
    BaseModel
):
    id: str


class GenerateAppAccessQuerySecurityPolicy(BaseModel):
    edges: list["GenerateAppAccessQuerySecurityPolicyEdges"]


class GenerateAppAccessQuerySecurityPolicyEdges(BaseModel):
    node: Optional["GenerateAppAccessQuerySecurityPolicyEdgesNode"]


class GenerateAppAccessQuerySecurityPolicyEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQuerySecurityPolicyEdgesNodeName"]
    device_target: "GenerateAppAccessQuerySecurityPolicyEdgesNodeDeviceTarget"


class GenerateAppAccessQuerySecurityPolicyEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQuerySecurityPolicyEdgesNodeDeviceTarget(BaseModel):
    node: Optional["GenerateAppAccessQuerySecurityPolicyEdgesNodeDeviceTargetNode"]


class GenerateAppAccessQuerySecurityPolicyEdgesNodeDeviceTargetNode(BaseModel):
    id: str
    display_label: Optional[str]


class GenerateAppAccessQuerySecurityZone(BaseModel):
    edges: list["GenerateAppAccessQuerySecurityZoneEdges"]


class GenerateAppAccessQuerySecurityZoneEdges(BaseModel):
    node: Optional["GenerateAppAccessQuerySecurityZoneEdgesNode"]


class GenerateAppAccessQuerySecurityZoneEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQuerySecurityZoneEdgesNodeName"]
    vrf: "GenerateAppAccessQuerySecurityZoneEdgesNodeVrf"


class GenerateAppAccessQuerySecurityZoneEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQuerySecurityZoneEdgesNodeVrf(BaseModel):
    node: Optional["GenerateAppAccessQuerySecurityZoneEdgesNodeVrfNode"]


class GenerateAppAccessQuerySecurityZoneEdgesNodeVrfNode(BaseModel):
    id: str


class GenerateAppAccessQuerySecurityService(BaseModel):
    edges: list["GenerateAppAccessQuerySecurityServiceEdges"]


class GenerateAppAccessQuerySecurityServiceEdges(BaseModel):
    node: Optional["GenerateAppAccessQuerySecurityServiceEdgesNode"]


class GenerateAppAccessQuerySecurityServiceEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQuerySecurityServiceEdgesNodeName"]
    port: Optional["GenerateAppAccessQuerySecurityServiceEdgesNodePort"]
    ip_protocol: "GenerateAppAccessQuerySecurityServiceEdgesNodeIpProtocol"


class GenerateAppAccessQuerySecurityServiceEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQuerySecurityServiceEdgesNodePort(BaseModel):
    value: Optional[Any]


class GenerateAppAccessQuerySecurityServiceEdgesNodeIpProtocol(BaseModel):
    node: Optional["GenerateAppAccessQuerySecurityServiceEdgesNodeIpProtocolNode"]


class GenerateAppAccessQuerySecurityServiceEdgesNodeIpProtocolNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQuerySecurityServiceEdgesNodeIpProtocolNodeName"]


class GenerateAppAccessQuerySecurityServiceEdgesNodeIpProtocolNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQuerySecurityIpProtocol(BaseModel):
    edges: list["GenerateAppAccessQuerySecurityIpProtocolEdges"]


class GenerateAppAccessQuerySecurityIpProtocolEdges(BaseModel):
    node: Optional["GenerateAppAccessQuerySecurityIpProtocolEdgesNode"]


class GenerateAppAccessQuerySecurityIpProtocolEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQuerySecurityIpProtocolEdgesNodeName"]


class GenerateAppAccessQuerySecurityIpProtocolEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQuerySecurityGenericAddress(BaseModel):
    edges: list["GenerateAppAccessQuerySecurityGenericAddressEdges"]


class GenerateAppAccessQuerySecurityGenericAddressEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityGenericAddress",
                "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddress",
                "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefix",
                "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAddress",
                "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityGenericAddress(
    BaseModel
):
    typename__: Literal["SecurityFQDN", "SecurityGenericAddress", "SecurityIPRange"] = (
        Field(alias="__typename")
    )
    id: Optional[str]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddress(
    BaseModel
):
    typename__: Literal["SecurityIPAMIPAddress"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressName"
    ]
    book_index: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressBookIndex"
    ]
    ip_address: "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddress"


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressName(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressBookIndex(
    BaseModel
):
    value: Optional[Any]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddress(
    BaseModel
):
    node: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddressNode"
    ]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddressNode(
    BaseModel
):
    id: str


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefix(
    BaseModel
):
    typename__: Literal["SecurityIPAMIPPrefix"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixName"
    ]
    book_index: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixBookIndex"
    ]
    ip_prefix: "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefix"


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixName(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixBookIndex(
    BaseModel
):
    value: Optional[Any]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefix(
    BaseModel
):
    node: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefixNode"
    ]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefixNode(
    BaseModel
):
    id: str


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAddress(BaseModel):
    typename__: Literal["SecurityIPAddress"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAddressName"
    ]
    book_index: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAddressBookIndex"
    ]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAddressName(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAddressBookIndex(
    BaseModel
):
    value: Optional[Any]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityPrefix(BaseModel):
    typename__: Literal["SecurityPrefix"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityPrefixName"
    ]
    book_index: Optional[
        "GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityPrefixBookIndex"
    ]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityPrefixName(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityPrefixBookIndex(
    BaseModel
):
    value: Optional[Any]


GenerateAppAccessQuery.model_rebuild()
GenerateAppAccessQueryTarget.model_rebuild()
GenerateAppAccessQueryTargetEdges.model_rebuild()
GenerateAppAccessQueryTargetEdgesNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplication.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeManifestsFile.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixes.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixesEdges.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeAllowedSourcePrefixesEdgesNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVipBlock.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVipBlockNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrf.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSite.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZone.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDevice.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecurityZoneNodeAdvertisingDeviceNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddress.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefix.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefixIpPrefix.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceSiteNodeSecuritySourceAddressNodeSecurityIPAMIPPrefixIpPrefixNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceZone.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceZoneNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDevice.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeAdvertisingDeviceNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceAddress.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefix.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefixIpPrefix.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceAddressNodeSecurityIPAMIPPrefixIpPrefixNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeDestinationVip.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeDestinationVipNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixes.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixesEdges.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedSourcePrefixesEdgesNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedRules.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdges.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdgesNode.model_rebuild()
GenerateAppAccessQueryServiceAppAccess.model_rebuild()
GenerateAppAccessQueryServiceAppAccessEdges.model_rebuild()
GenerateAppAccessQueryServiceAppAccessEdgesNode.model_rebuild()
GenerateAppAccessQueryServiceAppAccessEdgesNodeApplication.model_rebuild()
GenerateAppAccessQueryServiceAppAccessEdgesNodeGrantedSourcePrefixes.model_rebuild()
GenerateAppAccessQueryServiceAppAccessEdgesNodeGrantedSourcePrefixesEdges.model_rebuild()
GenerateAppAccessQuerySecurityPolicy.model_rebuild()
GenerateAppAccessQuerySecurityPolicyEdges.model_rebuild()
GenerateAppAccessQuerySecurityPolicyEdgesNode.model_rebuild()
GenerateAppAccessQuerySecurityPolicyEdgesNodeDeviceTarget.model_rebuild()
GenerateAppAccessQuerySecurityZone.model_rebuild()
GenerateAppAccessQuerySecurityZoneEdges.model_rebuild()
GenerateAppAccessQuerySecurityZoneEdgesNode.model_rebuild()
GenerateAppAccessQuerySecurityZoneEdgesNodeVrf.model_rebuild()
GenerateAppAccessQuerySecurityService.model_rebuild()
GenerateAppAccessQuerySecurityServiceEdges.model_rebuild()
GenerateAppAccessQuerySecurityServiceEdgesNode.model_rebuild()
GenerateAppAccessQuerySecurityServiceEdgesNodeIpProtocol.model_rebuild()
GenerateAppAccessQuerySecurityServiceEdgesNodeIpProtocolNode.model_rebuild()
GenerateAppAccessQuerySecurityIpProtocol.model_rebuild()
GenerateAppAccessQuerySecurityIpProtocolEdges.model_rebuild()
GenerateAppAccessQuerySecurityIpProtocolEdgesNode.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddress.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddressEdges.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddress.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddress.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefix.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefix.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAddress.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityPrefix.model_rebuild()
