from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class PeeringConsistencyCheckQuery(BaseModel):
    service_fabric_peering: "PeeringConsistencyCheckQueryServiceFabricPeering" = Field(
        alias="ServiceFabricPeering"
    )
    cluster_fabric_peering: "PeeringConsistencyCheckQueryClusterFabricPeering" = Field(
        alias="ClusterFabricPeering"
    )
    interface_virtual: "PeeringConsistencyCheckQueryInterfaceVirtual" = Field(
        alias="InterfaceVirtual"
    )
    evpn_svi_node: "PeeringConsistencyCheckQueryEvpnSviNode" = Field(
        alias="EvpnSviNode"
    )
    cluster_kubernetes: "PeeringConsistencyCheckQueryClusterKubernetes" = Field(
        alias="ClusterKubernetes"
    )


class PeeringConsistencyCheckQueryServiceFabricPeering(BaseModel):
    edges: list["PeeringConsistencyCheckQueryServiceFabricPeeringEdges"]


class PeeringConsistencyCheckQueryServiceFabricPeeringEdges(BaseModel):
    node: Optional["PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNode"]


class PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNode(BaseModel):
    id: str
    name: Optional["PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeName"]
    cluster: "PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeCluster"


class PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeName(BaseModel):
    value: Optional[str]


class PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeCluster(BaseModel):
    node: Optional[
        "PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeClusterNode"
    ]


class PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeClusterNode(BaseModel):
    id: str
    name: Optional[
        "PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeClusterNodeName"
    ]


class PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeClusterNodeName(
    BaseModel
):
    value: Optional[str]


class PeeringConsistencyCheckQueryClusterFabricPeering(BaseModel):
    edges: list["PeeringConsistencyCheckQueryClusterFabricPeeringEdges"]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdges(BaseModel):
    node: Optional["PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNode"]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNode(BaseModel):
    id: str
    name: Optional["PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeName"]
    peer_asn: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAsn"
    ]
    cluster: "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeCluster"
    peer_device: "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDevice"
    peer_address: "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAddress"


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeName(BaseModel):
    value: Optional[str]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAsn(BaseModel):
    value: Optional[Any]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeCluster(BaseModel):
    node: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeClusterNode"
    ]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeClusterNode(BaseModel):
    id: str
    name: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeClusterNodeName"
    ]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeClusterNodeName(
    BaseModel
):
    value: Optional[str]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDevice(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimGenericDevice",
                "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDevice",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimGenericDevice(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]
    display_label: Optional[str]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDevice(
    BaseModel
):
    typename__: Literal["DcimDevice"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    name: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceName"
    ]
    role: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceRole"
    ]
    asn: "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceAsn"


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceName(
    BaseModel
):
    value: Optional[str]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceRole(
    BaseModel
):
    value: Optional[str]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceAsn(
    BaseModel
):
    node: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceAsnNode"
    ]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceAsnNode(
    BaseModel
):
    id: str
    asn: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceAsnNodeAsn"
    ]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceAsnNodeAsn(
    BaseModel
):
    value: Optional[Any]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAddress(BaseModel):
    node: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAddressNode"
    ]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAddressNode(
    BaseModel
):
    id: str
    address: Optional[
        "PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAddressNodeAddress"
    ]


class PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAddressNodeAddress(
    BaseModel
):
    value: Optional[str]


class PeeringConsistencyCheckQueryInterfaceVirtual(BaseModel):
    edges: list["PeeringConsistencyCheckQueryInterfaceVirtualEdges"]


class PeeringConsistencyCheckQueryInterfaceVirtualEdges(BaseModel):
    node: Optional["PeeringConsistencyCheckQueryInterfaceVirtualEdgesNode"]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNode(BaseModel):
    id: str
    name: Optional["PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeName"]
    role: Optional["PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeRole"]
    dot_1_q_id: Optional[
        "PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeDot1QId"
    ] = Field(alias="dot1q_id")
    device: "PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeDevice"
    ip_addresses: "PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddresses"


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeName(BaseModel):
    value: Optional[str]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeRole(BaseModel):
    value: Optional[str]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeDot1QId(BaseModel):
    value: Optional[Any]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeDevice(BaseModel):
    node: Optional["PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeDeviceNode"]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeDeviceNode(BaseModel):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]
    display_label: Optional[str]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddresses(BaseModel):
    edges: list["PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddressesEdges"]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddressesEdges(BaseModel):
    node: Optional[
        "PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddressesEdgesNode"
    ]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddressesEdgesNode(
    BaseModel
):
    id: str
    address: Optional[
        "PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddressesEdgesNodeAddress"
    ]


class PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddressesEdgesNodeAddress(
    BaseModel
):
    value: Optional[str]


class PeeringConsistencyCheckQueryEvpnSviNode(BaseModel):
    edges: list["PeeringConsistencyCheckQueryEvpnSviNodeEdges"]


class PeeringConsistencyCheckQueryEvpnSviNodeEdges(BaseModel):
    node: Optional["PeeringConsistencyCheckQueryEvpnSviNodeEdgesNode"]


class PeeringConsistencyCheckQueryEvpnSviNodeEdgesNode(BaseModel):
    id: str
    ip_address: Optional["PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeIpAddress"]
    device: "PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeDevice"
    svi: "PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeSvi"


class PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeIpAddress(BaseModel):
    value: Optional[str]


class PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeDevice(BaseModel):
    node: Optional["PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeDeviceNode"]


class PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeDeviceNode(BaseModel):
    id: str
    display_label: Optional[str]


class PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeSvi(BaseModel):
    node: Optional["PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeSviNode"]


class PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeSviNode(BaseModel):
    id: str
    svi_id: Optional["PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeSviNodeSviId"]


class PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeSviNodeSviId(BaseModel):
    value: Optional[Any]


class PeeringConsistencyCheckQueryClusterKubernetes(BaseModel):
    edges: list["PeeringConsistencyCheckQueryClusterKubernetesEdges"]


class PeeringConsistencyCheckQueryClusterKubernetesEdges(BaseModel):
    node: Optional["PeeringConsistencyCheckQueryClusterKubernetesEdgesNode"]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNode(BaseModel):
    id: str
    name: Optional["PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeName"]
    nodes: "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodes"


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeName(BaseModel):
    value: Optional[str]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodes(BaseModel):
    edges: Optional[
        list["PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdges"]
    ]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputeGenericUnit",
                "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServer",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputeGenericUnit(
    BaseModel
):
    typename__: Literal["ComputeGenericUnit", "VirtualizationVirtualMachine"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServer(
    BaseModel
):
    typename__: Literal["ComputePhysicalServer"] = Field(alias="__typename")
    id: str
    interfaces: "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfaces"


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfaces(
    BaseModel
):
    edges: Optional[
        list[
            "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdges"
        ]
    ]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeDcimInterface",
                "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeDcimInterface(
    BaseModel
):
    typename__: Literal[
        "DcimInterface", "InterfaceLag", "InterfaceVirtual", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    connector: "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnector"


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnector(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeDcimConnector",
                "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLink",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeDcimConnector(
    BaseModel
):
    typename__: Literal["DcimConnector"] = Field(alias="__typename")


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLink(
    BaseModel
):
    typename__: Literal["NetworkLink"] = Field(alias="__typename")
    id: str
    connected_endpoints: "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpoints"


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpoints(
    BaseModel
):
    edges: Optional[
        list[
            "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdges"
        ]
    ]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeDcimEndpoint",
                "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeDcimEndpoint(
    BaseModel
):
    typename__: Literal[
        "DcimCircuitEndpoint", "DcimEndpoint", "SecurityFirewallInterface"
    ] = Field(alias="__typename")
    id: Optional[str]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    id: str
    device: "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDevice"


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        "PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNode"
    ]


class PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNode(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]


PeeringConsistencyCheckQuery.model_rebuild()
PeeringConsistencyCheckQueryServiceFabricPeering.model_rebuild()
PeeringConsistencyCheckQueryServiceFabricPeeringEdges.model_rebuild()
PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNode.model_rebuild()
PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeCluster.model_rebuild()
PeeringConsistencyCheckQueryServiceFabricPeeringEdgesNodeClusterNode.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeering.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdges.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNode.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeCluster.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodeClusterNode.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDevice.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDevice.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceAsn.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerDeviceNodeDcimDeviceAsnNode.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAddress.model_rebuild()
PeeringConsistencyCheckQueryClusterFabricPeeringEdgesNodePeerAddressNode.model_rebuild()
PeeringConsistencyCheckQueryInterfaceVirtual.model_rebuild()
PeeringConsistencyCheckQueryInterfaceVirtualEdges.model_rebuild()
PeeringConsistencyCheckQueryInterfaceVirtualEdgesNode.model_rebuild()
PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeDevice.model_rebuild()
PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddresses.model_rebuild()
PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddressesEdges.model_rebuild()
PeeringConsistencyCheckQueryInterfaceVirtualEdgesNodeIpAddressesEdgesNode.model_rebuild()
PeeringConsistencyCheckQueryEvpnSviNode.model_rebuild()
PeeringConsistencyCheckQueryEvpnSviNodeEdges.model_rebuild()
PeeringConsistencyCheckQueryEvpnSviNodeEdgesNode.model_rebuild()
PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeDevice.model_rebuild()
PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeSvi.model_rebuild()
PeeringConsistencyCheckQueryEvpnSviNodeEdgesNodeSviNode.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetes.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdges.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNode.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodes.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdges.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServer.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfaces.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdges.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysical.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnector.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLink.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpoints.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdges.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysical.model_rebuild()
PeeringConsistencyCheckQueryClusterKubernetesEdgesNodeNodesEdgesNodeComputePhysicalServerInterfacesEdgesNodeInterfacePhysicalConnectorNodeNetworkLinkConnectedEndpointsEdgesNodeInterfacePhysicalDevice.model_rebuild()
