from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class JunosConfigQuery(BaseModel):
    target: "JunosConfigQueryTarget"
    security_zone: "JunosConfigQuerySecurityZone" = Field(alias="SecurityZone")
    security_generic_address: "JunosConfigQuerySecurityGenericAddress" = Field(
        alias="SecurityGenericAddress"
    )
    security_address_group: "JunosConfigQuerySecurityAddressGroup" = Field(
        alias="SecurityAddressGroup"
    )
    security_generic_service: "JunosConfigQuerySecurityGenericService" = Field(
        alias="SecurityGenericService"
    )
    security_policy: "JunosConfigQuerySecurityPolicy" = Field(alias="SecurityPolicy")


class JunosConfigQueryTarget(BaseModel):
    edges: list["JunosConfigQueryTargetEdges"]


class JunosConfigQueryTargetEdges(BaseModel):
    node: Optional["JunosConfigQueryTargetEdgesNode"]


class JunosConfigQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["JunosConfigQueryTargetEdgesNodeName"]
    description: Optional["JunosConfigQueryTargetEdgesNodeDescription"]
    tcp_mss: Optional["JunosConfigQueryTargetEdgesNodeTcpMss"]
    static_routes: "JunosConfigQueryTargetEdgesNodeStaticRoutes"
    interfaces: "JunosConfigQueryTargetEdgesNodeInterfaces"


class JunosConfigQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class JunosConfigQueryTargetEdgesNodeDescription(BaseModel):
    value: Optional[str]


class JunosConfigQueryTargetEdgesNodeTcpMss(BaseModel):
    value: Optional[Any]


class JunosConfigQueryTargetEdgesNodeStaticRoutes(BaseModel):
    edges: list["JunosConfigQueryTargetEdgesNodeStaticRoutesEdges"]


class JunosConfigQueryTargetEdgesNodeStaticRoutesEdges(BaseModel):
    node: Optional["JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNode"]


class JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNode(BaseModel):
    prefix: Optional["JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNodePrefix"]
    next_hop: Optional["JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNodeNextHop"]
    route_name: Optional[
        "JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNodeRouteName"
    ]


class JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNodePrefix(BaseModel):
    value: Optional[str]


class JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNodeNextHop(BaseModel):
    value: Optional[str]


class JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNodeRouteName(BaseModel):
    value: Optional[str]


class JunosConfigQueryTargetEdgesNodeInterfaces(BaseModel):
    edges: Optional[list["JunosConfigQueryTargetEdgesNodeInterfacesEdges"]]


class JunosConfigQueryTargetEdgesNodeInterfacesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeDcimInterface",
                "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterface",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeDcimInterface(BaseModel):
    typename__: Literal[
        "DcimInterface", "InterfaceLag", "InterfacePhysical", "InterfaceVirtual"
    ] = Field(alias="__typename")


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterface(
    BaseModel
):
    typename__: Literal["SecurityFirewallInterface"] = Field(alias="__typename")
    name: Optional[
        "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceName"
    ]
    description: Optional[
        "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceDescription"
    ]
    mtu: Optional[
        "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceMtu"
    ]
    security_zone: "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceSecurityZone"
    ip_addresses: "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddresses"


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceName(
    BaseModel
):
    value: Optional[str]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceDescription(
    BaseModel
):
    value: Optional[str]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceMtu(
    BaseModel
):
    value: Optional[Any]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceSecurityZone(
    BaseModel
):
    node: Optional[
        "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceSecurityZoneNode"
    ]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceSecurityZoneNode(
    BaseModel
):
    name: Optional[
        "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceSecurityZoneNodeName"
    ]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceSecurityZoneNodeName(
    BaseModel
):
    value: Optional[str]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddresses(
    BaseModel
):
    edges: list[
        "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddressesEdges"
    ]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddressesEdges(
    BaseModel
):
    node: Optional[
        "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddressesEdgesNode"
    ]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddressesEdgesNode(
    BaseModel
):
    address: Optional[
        "JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddressesEdgesNodeAddress"
    ]


class JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddressesEdgesNodeAddress(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityZone(BaseModel):
    edges: list["JunosConfigQuerySecurityZoneEdges"]


class JunosConfigQuerySecurityZoneEdges(BaseModel):
    node: Optional["JunosConfigQuerySecurityZoneEdgesNode"]


class JunosConfigQuerySecurityZoneEdgesNode(BaseModel):
    name: Optional["JunosConfigQuerySecurityZoneEdgesNodeName"]
    trust_level: Optional["JunosConfigQuerySecurityZoneEdgesNodeTrustLevel"]
    interfaces: "JunosConfigQuerySecurityZoneEdgesNodeInterfaces"


class JunosConfigQuerySecurityZoneEdgesNodeName(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityZoneEdgesNodeTrustLevel(BaseModel):
    value: Optional[Any]


class JunosConfigQuerySecurityZoneEdgesNodeInterfaces(BaseModel):
    edges: list["JunosConfigQuerySecurityZoneEdgesNodeInterfacesEdges"]


class JunosConfigQuerySecurityZoneEdgesNodeInterfacesEdges(BaseModel):
    node: Optional["JunosConfigQuerySecurityZoneEdgesNodeInterfacesEdgesNode"]


class JunosConfigQuerySecurityZoneEdgesNodeInterfacesEdgesNode(BaseModel):
    name: Optional["JunosConfigQuerySecurityZoneEdgesNodeInterfacesEdgesNodeName"]


class JunosConfigQuerySecurityZoneEdgesNodeInterfacesEdgesNodeName(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddress(BaseModel):
    edges: list["JunosConfigQuerySecurityGenericAddressEdges"]


class JunosConfigQuerySecurityGenericAddressEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityGenericAddress",
                "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddress",
                "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefix",
                "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityGenericAddress(BaseModel):
    typename__: Literal[
        "SecurityFQDN", "SecurityGenericAddress", "SecurityIPAddress", "SecurityIPRange"
    ] = Field(alias="__typename")


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddress(BaseModel):
    typename__: Literal["SecurityIPAMIPAddress"] = Field(alias="__typename")
    name: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressName"
    ]
    description: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressDescription"
    ]
    book_index: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressBookIndex"
    ]
    ip_address: (
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddress"
    )


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressName(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressDescription(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressBookIndex(
    BaseModel
):
    value: Optional[Any]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddress(
    BaseModel
):
    node: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddressNode"
    ]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddressNode(
    BaseModel
):
    address: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddressNodeAddress"
    ]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddressNodeAddress(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefix(BaseModel):
    typename__: Literal["SecurityIPAMIPPrefix"] = Field(alias="__typename")
    name: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixName"
    ]
    description: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixDescription"
    ]
    book_index: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixBookIndex"
    ]
    ip_prefix: (
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefix"
    )


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixName(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixDescription(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixBookIndex(
    BaseModel
):
    value: Optional[Any]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefix(
    BaseModel
):
    node: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefixNode"
    ]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefixNode(
    BaseModel
):
    prefix: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefixNodePrefix"
    ]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefixNodePrefix(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefix(BaseModel):
    typename__: Literal["SecurityPrefix"] = Field(alias="__typename")
    name: Optional["JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefixName"]
    description: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefixDescription"
    ]
    book_index: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefixBookIndex"
    ]
    prefix: Optional[
        "JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefixPrefix"
    ]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefixName(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefixDescription(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefixBookIndex(BaseModel):
    value: Optional[Any]


class JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefixPrefix(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityAddressGroup(BaseModel):
    edges: list["JunosConfigQuerySecurityAddressGroupEdges"]


class JunosConfigQuerySecurityAddressGroupEdges(BaseModel):
    node: Optional["JunosConfigQuerySecurityAddressGroupEdgesNode"]


class JunosConfigQuerySecurityAddressGroupEdgesNode(BaseModel):
    name: Optional["JunosConfigQuerySecurityAddressGroupEdgesNodeName"]
    description: Optional["JunosConfigQuerySecurityAddressGroupEdgesNodeDescription"]
    addresses: "JunosConfigQuerySecurityAddressGroupEdgesNodeAddresses"


class JunosConfigQuerySecurityAddressGroupEdgesNodeName(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityAddressGroupEdgesNodeDescription(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityAddressGroupEdgesNodeAddresses(BaseModel):
    edges: Optional[list["JunosConfigQuerySecurityAddressGroupEdgesNodeAddressesEdges"]]


class JunosConfigQuerySecurityAddressGroupEdgesNodeAddressesEdges(BaseModel):
    node: Optional["JunosConfigQuerySecurityAddressGroupEdgesNodeAddressesEdgesNode"]


class JunosConfigQuerySecurityAddressGroupEdgesNodeAddressesEdgesNode(BaseModel):
    typename__: Literal[
        "SecurityFQDN",
        "SecurityGenericAddress",
        "SecurityIPAMIPAddress",
        "SecurityIPAMIPPrefix",
        "SecurityIPAddress",
        "SecurityIPRange",
        "SecurityPrefix",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class JunosConfigQuerySecurityGenericService(BaseModel):
    edges: list["JunosConfigQuerySecurityGenericServiceEdges"]


class JunosConfigQuerySecurityGenericServiceEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityGenericService",
                "JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityIPProtocol",
                "JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityService",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityGenericService(BaseModel):
    typename__: Literal["SecurityGenericService", "SecurityServiceRange"] = Field(
        alias="__typename"
    )


class JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityIPProtocol(BaseModel):
    typename__: Literal["SecurityIPProtocol"] = Field(alias="__typename")
    name: Optional[
        "JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityIPProtocolName"
    ]


class JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityIPProtocolName(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityService(BaseModel):
    typename__: Literal["SecurityService"] = Field(alias="__typename")
    name: Optional["JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityServiceName"]


class JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityServiceName(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityPolicy(BaseModel):
    edges: list["JunosConfigQuerySecurityPolicyEdges"]


class JunosConfigQuerySecurityPolicyEdges(BaseModel):
    node: Optional["JunosConfigQuerySecurityPolicyEdgesNode"]


class JunosConfigQuerySecurityPolicyEdgesNode(BaseModel):
    name: Optional["JunosConfigQuerySecurityPolicyEdgesNodeName"]
    device_target: "JunosConfigQuerySecurityPolicyEdgesNodeDeviceTarget"
    rules: "JunosConfigQuerySecurityPolicyEdgesNodeRules"


class JunosConfigQuerySecurityPolicyEdgesNodeName(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeDeviceTarget(BaseModel):
    node: Optional["JunosConfigQuerySecurityPolicyEdgesNodeDeviceTargetNode"]


class JunosConfigQuerySecurityPolicyEdgesNodeDeviceTargetNode(BaseModel):
    display_label: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRules(BaseModel):
    edges: list["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdges"]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdges(BaseModel):
    node: Optional["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNode"]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNode(BaseModel):
    name: Optional["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeName"]
    index: Optional["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeIndex"]
    action: Optional["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeAction"]
    log: Optional["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeLog"]
    log_session_close: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeLogSessionClose"
    ]
    source_zone: "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceZone"
    destination_zone: (
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationZone"
    )
    source_address: "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddress"
    destination_address: (
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddress"
    )
    source_groups: "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceGroups"
    destination_groups: (
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationGroups"
    )
    source_services: (
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceServices"
    )
    destination_services: (
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationServices"
    )


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeName(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeIndex(BaseModel):
    value: Optional[Any]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeAction(BaseModel):
    value: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeLog(BaseModel):
    value: Optional[bool]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeLogSessionClose(BaseModel):
    value: Optional[bool]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceZone(BaseModel):
    node: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceZoneNode"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceZoneNode(BaseModel):
    name: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceZoneNodeName"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceZoneNodeName(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationZone(BaseModel):
    node: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationZoneNode"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationZoneNode(
    BaseModel
):
    name: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationZoneNodeName"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationZoneNodeName(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddress(BaseModel):
    edges: Optional[
        list["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdges"]
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdgesNodeSecurityGenericAddress",
                "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdgesNodeSecurityPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdgesNodeSecurityGenericAddress(
    BaseModel
):
    typename__: Literal[
        "SecurityFQDN",
        "SecurityGenericAddress",
        "SecurityIPAMIPAddress",
        "SecurityIPAMIPPrefix",
        "SecurityIPAddress",
        "SecurityIPRange",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdgesNodeSecurityPrefix(
    BaseModel
):
    typename__: Literal["SecurityPrefix"] = Field(alias="__typename")
    display_label: Optional[str]
    name: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdgesNodeSecurityPrefixName"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdgesNodeSecurityPrefixName(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddress(
    BaseModel
):
    edges: Optional[
        list[
            "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdges"
        ]
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdgesNodeSecurityGenericAddress",
                "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdgesNodeSecurityPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdgesNodeSecurityGenericAddress(
    BaseModel
):
    typename__: Literal[
        "SecurityFQDN",
        "SecurityGenericAddress",
        "SecurityIPAMIPAddress",
        "SecurityIPAMIPPrefix",
        "SecurityIPAddress",
        "SecurityIPRange",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdgesNodeSecurityPrefix(
    BaseModel
):
    typename__: Literal["SecurityPrefix"] = Field(alias="__typename")
    display_label: Optional[str]
    name: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdgesNodeSecurityPrefixName"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdgesNodeSecurityPrefixName(
    BaseModel
):
    value: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceGroups(BaseModel):
    edges: Optional[
        list["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceGroupsEdges"]
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceGroupsEdges(BaseModel):
    node: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceGroupsEdgesNode"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceGroupsEdgesNode(
    BaseModel
):
    typename__: Literal["SecurityAddressGroup", "SecurityGenericAddressGroup"] = Field(
        alias="__typename"
    )
    display_label: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationGroups(BaseModel):
    edges: Optional[
        list[
            "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationGroupsEdges"
        ]
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationGroupsEdges(
    BaseModel
):
    node: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationGroupsEdgesNode"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationGroupsEdgesNode(
    BaseModel
):
    typename__: Literal["SecurityAddressGroup", "SecurityGenericAddressGroup"] = Field(
        alias="__typename"
    )
    display_label: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceServices(BaseModel):
    edges: Optional[
        list["JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceServicesEdges"]
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceServicesEdges(
    BaseModel
):
    node: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceServicesEdgesNode"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceServicesEdgesNode(
    BaseModel
):
    typename__: Literal[
        "SecurityGenericService",
        "SecurityIPProtocol",
        "SecurityService",
        "SecurityServiceRange",
    ] = Field(alias="__typename")
    display_label: Optional[str]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationServices(
    BaseModel
):
    edges: Optional[
        list[
            "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationServicesEdges"
        ]
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationServicesEdges(
    BaseModel
):
    node: Optional[
        "JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationServicesEdgesNode"
    ]


class JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationServicesEdgesNode(
    BaseModel
):
    typename__: Literal[
        "SecurityGenericService",
        "SecurityIPProtocol",
        "SecurityService",
        "SecurityServiceRange",
    ] = Field(alias="__typename")
    display_label: Optional[str]


JunosConfigQuery.model_rebuild()
JunosConfigQueryTarget.model_rebuild()
JunosConfigQueryTargetEdges.model_rebuild()
JunosConfigQueryTargetEdgesNode.model_rebuild()
JunosConfigQueryTargetEdgesNodeStaticRoutes.model_rebuild()
JunosConfigQueryTargetEdgesNodeStaticRoutesEdges.model_rebuild()
JunosConfigQueryTargetEdgesNodeStaticRoutesEdgesNode.model_rebuild()
JunosConfigQueryTargetEdgesNodeInterfaces.model_rebuild()
JunosConfigQueryTargetEdgesNodeInterfacesEdges.model_rebuild()
JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterface.model_rebuild()
JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceSecurityZone.model_rebuild()
JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceSecurityZoneNode.model_rebuild()
JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddresses.model_rebuild()
JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddressesEdges.model_rebuild()
JunosConfigQueryTargetEdgesNodeInterfacesEdgesNodeSecurityFirewallInterfaceIpAddressesEdgesNode.model_rebuild()
JunosConfigQuerySecurityZone.model_rebuild()
JunosConfigQuerySecurityZoneEdges.model_rebuild()
JunosConfigQuerySecurityZoneEdgesNode.model_rebuild()
JunosConfigQuerySecurityZoneEdgesNodeInterfaces.model_rebuild()
JunosConfigQuerySecurityZoneEdgesNodeInterfacesEdges.model_rebuild()
JunosConfigQuerySecurityZoneEdgesNodeInterfacesEdgesNode.model_rebuild()
JunosConfigQuerySecurityGenericAddress.model_rebuild()
JunosConfigQuerySecurityGenericAddressEdges.model_rebuild()
JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddress.model_rebuild()
JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddress.model_rebuild()
JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPAddressIpAddressNode.model_rebuild()
JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefix.model_rebuild()
JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefix.model_rebuild()
JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityIPAMIPPrefixIpPrefixNode.model_rebuild()
JunosConfigQuerySecurityGenericAddressEdgesNodeSecurityPrefix.model_rebuild()
JunosConfigQuerySecurityAddressGroup.model_rebuild()
JunosConfigQuerySecurityAddressGroupEdges.model_rebuild()
JunosConfigQuerySecurityAddressGroupEdgesNode.model_rebuild()
JunosConfigQuerySecurityAddressGroupEdgesNodeAddresses.model_rebuild()
JunosConfigQuerySecurityAddressGroupEdgesNodeAddressesEdges.model_rebuild()
JunosConfigQuerySecurityGenericService.model_rebuild()
JunosConfigQuerySecurityGenericServiceEdges.model_rebuild()
JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityIPProtocol.model_rebuild()
JunosConfigQuerySecurityGenericServiceEdgesNodeSecurityService.model_rebuild()
JunosConfigQuerySecurityPolicy.model_rebuild()
JunosConfigQuerySecurityPolicyEdges.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNode.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeDeviceTarget.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRules.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdges.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNode.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceZone.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceZoneNode.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationZone.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationZoneNode.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddress.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdges.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceAddressEdgesNodeSecurityPrefix.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddress.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdges.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationAddressEdgesNodeSecurityPrefix.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceGroups.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceGroupsEdges.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationGroups.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationGroupsEdges.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceServices.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeSourceServicesEdges.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationServices.model_rebuild()
JunosConfigQuerySecurityPolicyEdgesNodeRulesEdgesNodeDestinationServicesEdges.model_rebuild()
