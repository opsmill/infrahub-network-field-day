from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class GenerateAppAccessQuery(BaseModel):
    target: "GenerateAppAccessQueryTarget"
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
    approved: Optional["GenerateAppAccessQueryTargetEdgesNodeApproved"]
    requester: Optional["GenerateAppAccessQueryTargetEdgesNodeRequester"]
    justification: Optional["GenerateAppAccessQueryTargetEdgesNodeJustification"]
    ports: Optional["GenerateAppAccessQueryTargetEdgesNodePorts"]
    application: "GenerateAppAccessQueryTargetEdgesNodeApplication"
    source_zone: "GenerateAppAccessQueryTargetEdgesNodeSourceZone"
    source_address: "GenerateAppAccessQueryTargetEdgesNodeSourceAddress"
    destination_vip: "GenerateAppAccessQueryTargetEdgesNodeDestinationVip"
    granted_rules: "GenerateAppAccessQueryTargetEdgesNodeGrantedRules"


class GenerateAppAccessQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeStatus(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeApproved(BaseModel):
    value: Optional[bool]


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
    vrf: "GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrf"


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrf(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNode"]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNodeName"]


class GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceZone(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeSourceZoneNode"]


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNode(BaseModel):
    id: str
    name: Optional["GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeName"]


class GenerateAppAccessQueryTargetEdgesNodeSourceZoneNodeName(BaseModel):
    value: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeSourceAddress(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeSourceAddressNode"]


class GenerateAppAccessQueryTargetEdgesNodeSourceAddressNode(BaseModel):
    typename__: Literal[
        "SecurityFQDN",
        "SecurityGenericAddress",
        "SecurityIPAMIPAddress",
        "SecurityIPAMIPPrefix",
        "SecurityIPAddress",
        "SecurityIPRange",
        "SecurityPrefix",
    ] = Field(alias="__typename")
    id: Optional[str]
    display_label: Optional[str]


class GenerateAppAccessQueryTargetEdgesNodeDestinationVip(BaseModel):
    node: Optional["GenerateAppAccessQueryTargetEdgesNodeDestinationVipNode"]


class GenerateAppAccessQueryTargetEdgesNodeDestinationVipNode(BaseModel):
    id: str
    address: Optional["GenerateAppAccessQueryTargetEdgesNodeDestinationVipNodeAddress"]


class GenerateAppAccessQueryTargetEdgesNodeDestinationVipNodeAddress(BaseModel):
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


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixName(
    BaseModel
):
    value: Optional[str]


class GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixBookIndex(
    BaseModel
):
    value: Optional[Any]


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
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrf.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeApplicationNodeVrfNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceZone.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceZoneNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeSourceAddress.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeDestinationVip.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeDestinationVipNode.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedRules.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdges.model_rebuild()
GenerateAppAccessQueryTargetEdgesNodeGrantedRulesEdgesNode.model_rebuild()
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
GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityIPAddress.model_rebuild()
GenerateAppAccessQuerySecurityGenericAddressEdgesNodeSecurityPrefix.model_rebuild()
