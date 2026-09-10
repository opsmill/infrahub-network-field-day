from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class GenerateFabricPeeringQuery(BaseModel):
    target: "GenerateFabricPeeringQueryTarget"


class GenerateFabricPeeringQueryTarget(BaseModel):
    edges: list["GenerateFabricPeeringQueryTargetEdges"]


class GenerateFabricPeeringQueryTargetEdges(BaseModel):
    node: Optional["GenerateFabricPeeringQueryTargetEdgesNode"]


class GenerateFabricPeeringQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateFabricPeeringQueryTargetEdgesNodeName"]
    cluster: "GenerateFabricPeeringQueryTargetEdgesNodeCluster"


class GenerateFabricPeeringQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeCluster(BaseModel):
    node: Optional["GenerateFabricPeeringQueryTargetEdgesNodeClusterNode"]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNode(BaseModel):
    id: str
    name: Optional["GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeName"]
    local_asn: Optional["GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeLocalAsn"]
    fabric_peerings: (
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeerings"
    )
    nodes: "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodes"


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeName(BaseModel):
    value: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeLocalAsn(BaseModel):
    value: Optional[Any]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeerings(BaseModel):
    edges: list[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdges"
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdges(
    BaseModel
):
    node: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNode"
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNode(
    BaseModel
):
    id: str
    name: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodeName"
    ]
    peer_asn: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAsn"
    ]
    enabled: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodeEnabled"
    ]
    peer_device: "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerDevice"
    peer_address: "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAddress"


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodeName(
    BaseModel
):
    value: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAsn(
    BaseModel
):
    value: Optional[Any]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodeEnabled(
    BaseModel
):
    value: Optional[bool]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerDevice(
    BaseModel
):
    node: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerDeviceNode"
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]
    display_label: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAddress(
    BaseModel
):
    node: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAddressNode"
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAddressNode(
    BaseModel
):
    id: str
    address: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAddressNodeAddress"
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAddressNodeAddress(
    BaseModel
):
    value: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodes(BaseModel):
    edges: Optional[
        list["GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdges"]
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputeGenericUnit",
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServer",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputeGenericUnit(
    BaseModel
):
    typename__: Literal["ComputeGenericUnit", "VirtualizationVirtualMachine"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServer(
    BaseModel
):
    typename__: Literal["ComputePhysicalServer"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerName"
    ]
    interfaces: "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfaces"


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerName(
    BaseModel
):
    value: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfaces(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdges"
        ]
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeDcimInterface",
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeDcimInterface(
    BaseModel
):
    typename__: Literal[
        "DcimInterface", "InterfaceLag", "InterfaceVirtual", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    connector: "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnector"


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnector(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeDcimConnector",
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLink",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeDcimConnector(
    BaseModel
):
    typename__: Literal["DcimConnector"] = Field(alias="__typename")


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLink(
    BaseModel
):
    typename__: Literal["NetworkLink"] = Field(alias="__typename")
    id: str
    connected_endpoints: "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpoints"


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpoints(
    BaseModel
):
    edges: Optional[
        list[
            "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdges"
        ]
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeDcimEndpoint",
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeDcimEndpoint(
    BaseModel
):
    typename__: Literal[
        "DcimCircuitEndpoint", "DcimEndpoint", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    device: "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDevice"


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice",
                "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDevice",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDevice(
    BaseModel
):
    typename__: Literal["DcimDevice"] = Field(alias="__typename")
    id: str
    name: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceName"
    ]
    role: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceRole"
    ]
    asn: "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceAsn"


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceName(
    BaseModel
):
    value: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceRole(
    BaseModel
):
    value: Optional[str]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceAsn(
    BaseModel
):
    node: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceAsnNode"
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceAsnNode(
    BaseModel
):
    id: str
    asn: Optional[
        "GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceAsnNodeAsn"
    ]


class GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceAsnNodeAsn(
    BaseModel
):
    value: Optional[Any]


GenerateFabricPeeringQuery.model_rebuild()
GenerateFabricPeeringQueryTarget.model_rebuild()
GenerateFabricPeeringQueryTargetEdges.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNode.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeCluster.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNode.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeerings.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdges.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNode.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerDevice.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAddress.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeFabricPeeringsEdgesNodePeerAddressNode.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodes.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdges.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServer.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfaces.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdges.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysical.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnector.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLink.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpoints.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdges.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysical.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDevice.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDevice.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceAsn.model_rebuild()
GenerateFabricPeeringQueryTargetEdgesNodeClusterNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimDeviceAsnNode.model_rebuild()
