from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field


class FabricPoolCheckQuery(BaseModel):
    network_fabric: "FabricPoolCheckQueryNetworkFabric" = Field(alias="NetworkFabric")
    network_pod: "FabricPoolCheckQueryNetworkPod" = Field(alias="NetworkPod")
    network_link: "FabricPoolCheckQueryNetworkLink" = Field(alias="NetworkLink")


class FabricPoolCheckQueryNetworkFabric(BaseModel):
    edges: list["FabricPoolCheckQueryNetworkFabricEdges"]


class FabricPoolCheckQueryNetworkFabricEdges(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkFabricEdgesNode"]


class FabricPoolCheckQueryNetworkFabricEdgesNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeName"]
    underlay_routing_protocol: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeUnderlayRoutingProtocol"
    ]
    overlay_routing_protocol: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeOverlayRoutingProtocol"
    ]
    fabric_ip_pools: "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPools"
    mgmt_pool: "FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPool"
    loopback_pool: "FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPool"
    vtep_pool: "FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPool"
    uplink_pool: "FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPool"
    dci_pool: "FabricPoolCheckQueryNetworkFabricEdgesNodeDciPool"


class FabricPoolCheckQueryNetworkFabricEdgesNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeUnderlayRoutingProtocol(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeOverlayRoutingProtocol(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPools(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdges"]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreResourcePool",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPool",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPool",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreResourcePool(
    BaseModel
):
    typename__: Literal["CoreNumberPool", "CoreResourcePool"] = Field(
        alias="__typename"
    )
    id: Optional[str]
    display_label: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPool(
    BaseModel
):
    typename__: Literal["CoreIPAddressPool"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    name: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolName"
    ]
    resources: "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResources"


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPool(
    BaseModel
):
    typename__: Literal["CoreIPPrefixPool"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    name: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolName"
    ]
    resources: "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources"


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPool(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNode"]


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeName"]
    resources: "FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResources"


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResources(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdges"]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPool(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNode"]


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeName"]
    resources: "FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResources"


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResources(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdges"]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPool(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNode"]


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeName"]
    resources: "FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResources"


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResources(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdges"]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPool(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNode"]


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeName"]
    resources: "FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResources"


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResources(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdges"]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPool(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNode"]


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeName"]
    resources: "FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResources"


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResources(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdges"]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPod(BaseModel):
    edges: list["FabricPoolCheckQueryNetworkPodEdges"]


class FabricPoolCheckQueryNetworkPodEdges(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkPodEdgesNode"]


class FabricPoolCheckQueryNetworkPodEdgesNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkPodEdgesNodeName"]
    parent: "FabricPoolCheckQueryNetworkPodEdgesNodeParent"
    pod_ip_pools: "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPools"
    mlag_peer_pool: "FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPool"
    mlag_l_3_pool: "FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3Pool" = Field(
        alias="mlag_l3_pool"
    )
    racks: "FabricPoolCheckQueryNetworkPodEdgesNodeRacks"


class FabricPoolCheckQueryNetworkPodEdgesNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParent(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkBuildingBlock",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabric",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkBuildingBlock(BaseModel):
    typename__: Literal["NetworkBuildingBlock", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabric(BaseModel):
    typename__: Literal["NetworkFabric"] = Field(alias="__typename")
    id: str
    name: Optional["FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricName"]
    underlay_routing_protocol: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUnderlayRoutingProtocol"
    ]
    fabric_ip_pools: (
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPools"
    )
    mgmt_pool: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPool"
    loopback_pool: (
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPool"
    )
    vtep_pool: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPool"
    uplink_pool: (
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPool"
    )
    dci_pool: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPool"


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUnderlayRoutingProtocol(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPools(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreResourcePool",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreResourcePool(
    BaseModel
):
    typename__: Literal["CoreNumberPool", "CoreResourcePool"] = Field(
        alias="__typename"
    )
    id: Optional[str]
    display_label: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool(
    BaseModel
):
    typename__: Literal["CoreIPAddressPool"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool(
    BaseModel
):
    typename__: Literal["CoreIPPrefixPool"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPool(BaseModel):
    node: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNode"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPool(
    BaseModel
):
    node: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNode"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPool(BaseModel):
    node: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNode"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPool(
    BaseModel
):
    node: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNode"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPool(BaseModel):
    node: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNode"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNode(
    BaseModel
):
    id: str
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPools(BaseModel):
    edges: Optional[list["FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdges"]]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreResourcePool",
                "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPool",
                "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPool",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreResourcePool(
    BaseModel
):
    typename__: Literal["CoreNumberPool", "CoreResourcePool"] = Field(
        alias="__typename"
    )
    id: Optional[str]
    display_label: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPool(
    BaseModel
):
    typename__: Literal["CoreIPAddressPool"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources"


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPool(
    BaseModel
):
    typename__: Literal["CoreIPPrefixPool"] = Field(alias="__typename")
    id: str
    display_label: Optional[str]
    name: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolName"
    ]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources"


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolName(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges"
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPool(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNode"]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeName"]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResources(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdges"]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3Pool(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNode"]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNode(BaseModel):
    id: str
    name: Optional["FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeName"]
    resources: "FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResources"


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeName(BaseModel):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResources(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdges"]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeBuiltinIPPrefix",
                "FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    prefix: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeIpamPrefixRole"
    ]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class FabricPoolCheckQueryNetworkPodEdgesNodeRacks(BaseModel):
    edges: list["FabricPoolCheckQueryNetworkPodEdgesNodeRacksEdges"]


class FabricPoolCheckQueryNetworkPodEdgesNodeRacksEdges(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkPodEdgesNodeRacksEdgesNode"]


class FabricPoolCheckQueryNetworkPodEdgesNodeRacksEdgesNode(BaseModel):
    id: str
    mlag: Optional["FabricPoolCheckQueryNetworkPodEdgesNodeRacksEdgesNodeMlag"]


class FabricPoolCheckQueryNetworkPodEdgesNodeRacksEdgesNodeMlag(BaseModel):
    value: Optional[bool]


class FabricPoolCheckQueryNetworkLink(BaseModel):
    edges: list["FabricPoolCheckQueryNetworkLinkEdges"]


class FabricPoolCheckQueryNetworkLinkEdges(BaseModel):
    node: Optional["FabricPoolCheckQueryNetworkLinkEdgesNode"]


class FabricPoolCheckQueryNetworkLinkEdgesNode(BaseModel):
    id: str
    connected_endpoints: "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpoints"


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpoints(BaseModel):
    edges: Optional[
        list["FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdges"]
    ]


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeDcimEndpoint",
                "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeDcimEndpoint(
    BaseModel
):
    typename__: Literal[
        "DcimCircuitEndpoint", "DcimEndpoint", "SecurityFirewallInterface"
    ] = Field(alias="__typename")


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical(
    BaseModel
):
    typename__: Literal["InterfacePhysical"] = Field(alias="__typename")
    device: "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice"


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice",
                "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimGenericDevice(
    BaseModel
):
    typename__: Literal[
        "ComputePhysicalServer", "DcimDevice", "DcimGenericDevice", "SecurityFirewall"
    ] = Field(alias="__typename")
    id: Optional[str]


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch(
    BaseModel
):
    typename__: Literal["DcimFabricSwitch"] = Field(alias="__typename")
    id: str
    pod: "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPod"


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPod(
    BaseModel
):
    node: Optional[
        "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNode"
    ]


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNode(
    BaseModel
):
    parent: "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParent"


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParent(
    BaseModel
):
    node: Optional[
        "FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNode"
    ]


class FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParentNode(
    BaseModel
):
    typename__: Literal["NetworkBuildingBlock", "NetworkFabric", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]


FabricPoolCheckQuery.model_rebuild()
FabricPoolCheckQueryNetworkFabric.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNode.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPools.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPool.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResources.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPool.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPool.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeMgmtPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPool.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeLoopbackPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPool.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeVtepPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPool.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeUplinkPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeDciPool.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkFabricEdgesNodeDciPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPod.model_rebuild()
FabricPoolCheckQueryNetworkPodEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNode.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParent.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabric.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPools.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricUplinkPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeParentNodeNetworkFabricDciPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPools.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNode.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagPeerPoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3Pool.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNode.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResources.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeMlagL3PoolNodeResourcesEdgesNodeIpamPrefix.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeRacks.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeRacksEdges.model_rebuild()
FabricPoolCheckQueryNetworkPodEdgesNodeRacksEdgesNode.model_rebuild()
FabricPoolCheckQueryNetworkLink.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdges.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNode.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpoints.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdges.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysical.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDevice.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitch.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPod.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNode.model_rebuild()
FabricPoolCheckQueryNetworkLinkEdgesNodeConnectedEndpointsEdgesNodeInterfacePhysicalDeviceNodeDcimFabricSwitchPodNodeParent.model_rebuild()
