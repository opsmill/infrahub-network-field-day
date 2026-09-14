from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class PodGeneratorQuery(BaseModel):
    network_pod: "PodGeneratorQueryNetworkPod" = Field(alias="NetworkPod")


class PodGeneratorQueryNetworkPod(BaseModel):
    edges: list["PodGeneratorQueryNetworkPodEdges"]


class PodGeneratorQueryNetworkPodEdges(BaseModel):
    node: Optional["PodGeneratorQueryNetworkPodEdgesNode"]


class PodGeneratorQueryNetworkPodEdgesNode(BaseModel):
    id: str
    name: Optional["PodGeneratorQueryNetworkPodEdgesNodeName"]
    checksum: Optional["PodGeneratorQueryNetworkPodEdgesNodeChecksum"]
    index: Optional["PodGeneratorQueryNetworkPodEdgesNodeIndex"]
    role: Optional["PodGeneratorQueryNetworkPodEdgesNodeRole"]
    device_designs: "PodGeneratorQueryNetworkPodEdgesNodeDeviceDesigns"
    pod_ip_pools: "PodGeneratorQueryNetworkPodEdgesNodePodIpPools"
    parent: "PodGeneratorQueryNetworkPodEdgesNodeParent"


class PodGeneratorQueryNetworkPodEdgesNodeName(BaseModel):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeChecksum(BaseModel):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeIndex(BaseModel):
    value: Optional[Any]


class PodGeneratorQueryNetworkPodEdgesNodeRole(BaseModel):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeDeviceDesigns(BaseModel):
    edges: list["PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdges"]


class PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdges(BaseModel):
    node: Optional["PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNode"]


class PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNode(BaseModel):
    role: Optional["PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeRole"]
    device_quantity: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeDeviceQuantity"
    ]
    device_template: (
        "PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeDeviceTemplate"
    )


class PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeRole(BaseModel):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeDeviceQuantity(
    BaseModel
):
    value: Optional[Any]


class PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeDeviceTemplate(
    BaseModel
):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeDeviceTemplateNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeDeviceTemplateNode(
    BaseModel
):
    typename__: Literal[
        "CoreObjectTemplate",
        "TemplateComputePhysicalServer",
        "TemplateDcimFabricSwitch",
    ] = Field(alias="__typename")
    id: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPools(BaseModel):
    edges: Optional[list["PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdges"]]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdges(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreResourcePool",
                "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPool",
                "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPool",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreResourcePool(
    BaseModel
):
    typename__: Literal["CoreNumberPool", "CoreResourcePool"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPool(
    BaseModel
):
    typename__: Literal["CoreIPAddressPool"] = Field(alias="__typename")
    id: str
    resources: "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources"


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges"
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix",
                "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    id: str
    prefix: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPool(
    BaseModel
):
    typename__: Literal["CoreIPPrefixPool"] = Field(alias="__typename")
    id: str
    resources: "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources"


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges"
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix",
                "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    id: str
    prefix: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParent(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkBuildingBlock",
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabric",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkBuildingBlock(BaseModel):
    typename__: Literal["NetworkBuildingBlock", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]
    name: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkBuildingBlockName"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkBuildingBlockName(BaseModel):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabric(BaseModel):
    typename__: Literal["NetworkFabric"] = Field(alias="__typename")
    id: str
    name: Optional["PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricName"]
    underlay_routing_protocol: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricUnderlayRoutingProtocol"
    ]
    fabric_interface_sorting_method: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricInterfaceSortingMethod"
    ]
    spine_interface_sorting_method: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricSpineInterfaceSortingMethod"
    ]
    device_designs: (
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesigns"
    )
    asn_pool: "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricAsnPool"
    node_id_pool: (
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricNodeIdPool"
    )
    mgmt_pool: "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPool"
    fabric_ip_pools: (
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPools"
    )
    vtep_pool: "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPool"
    loopback_pool: (
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPool"
    )


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricName(BaseModel):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricUnderlayRoutingProtocol(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricInterfaceSortingMethod(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricSpineInterfaceSortingMethod(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesigns(
    BaseModel
):
    edges: list[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdges"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdges(
    BaseModel
):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNode(
    BaseModel
):
    role: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeRole"
    ]
    device_quantity: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeDeviceQuantity"
    ]
    device_template: "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeDeviceTemplate"


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeRole(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeDeviceQuantity(
    BaseModel
):
    value: Optional[Any]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeDeviceTemplate(
    BaseModel
):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeDeviceTemplateNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeDeviceTemplateNode(
    BaseModel
):
    typename__: Literal[
        "CoreObjectTemplate",
        "TemplateComputePhysicalServer",
        "TemplateDcimFabricSwitch",
    ] = Field(alias="__typename")
    id: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricAsnPool(BaseModel):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricAsnPoolNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricAsnPoolNode(BaseModel):
    id: str


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricNodeIdPool(BaseModel):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricNodeIdPoolNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricNodeIdPoolNode(
    BaseModel
):
    id: str


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPool(BaseModel):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPoolNode(
    BaseModel
):
    id: str


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPools(
    BaseModel
):
    edges: Optional[
        list[
            "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdges"
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreResourcePool",
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool",
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreResourcePool(
    BaseModel
):
    typename__: Literal["CoreNumberPool", "CoreResourcePool"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool(
    BaseModel
):
    typename__: Literal["CoreIPAddressPool"] = Field(alias="__typename")
    id: str
    resources: "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources"


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges"
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix",
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    id: str
    prefix: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool(
    BaseModel
):
    typename__: Literal["CoreIPPrefixPool"] = Field(alias="__typename")
    id: str
    resources: "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources"


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources(
    BaseModel
):
    edges: Optional[
        list[
            "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges"
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges(
    BaseModel
):
    node: Optional[
        Annotated[
            Union[
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix",
                "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeBuiltinIPPrefix(
    BaseModel
):
    typename__: Literal["BuiltinIPPrefix", "InternalIPPrefixAvailable"] = Field(
        alias="__typename"
    )


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix(
    BaseModel
):
    typename__: Literal["IpamPrefix"] = Field(alias="__typename")
    id: str
    prefix: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix"
    ]
    role: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixPrefix(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefixRole(
    BaseModel
):
    value: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPool(BaseModel):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNode(
    BaseModel
):
    id: str
    resources: "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResources"


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResources(
    BaseModel
):
    edges: Optional[
        list[
            "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdges"
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdges(
    BaseModel
):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdgesNode(
    BaseModel
):
    typename__: Literal[
        "BuiltinIPPrefix", "InternalIPPrefixAvailable", "IpamPrefix"
    ] = Field(alias="__typename")
    id: Optional[str]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPool(
    BaseModel
):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNode(
    BaseModel
):
    id: str
    resources: "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResources"


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResources(
    BaseModel
):
    edges: Optional[
        list[
            "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdges"
        ]
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdges(
    BaseModel
):
    node: Optional[
        "PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNode"
    ]


class PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdgesNode(
    BaseModel
):
    typename__: Literal[
        "BuiltinIPPrefix", "InternalIPPrefixAvailable", "IpamPrefix"
    ] = Field(alias="__typename")
    id: Optional[str]


PodGeneratorQuery.model_rebuild()
PodGeneratorQueryNetworkPod.model_rebuild()
PodGeneratorQueryNetworkPodEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNode.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeDeviceDesigns.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNode.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeDeviceDesignsEdgesNodeDeviceTemplate.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPools.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResources.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResources.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodePodIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParent.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkBuildingBlock.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabric.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesigns.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNode.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricDeviceDesignsEdgesNodeDeviceTemplate.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricAsnPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricNodeIdPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricMgmtPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPools.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResources.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPAddressPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResources.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricFabricIpPoolsEdgesNodeCoreIPPrefixPoolResourcesEdgesNodeIpamPrefix.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNode.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResources.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricVtepPoolNodeResourcesEdges.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPool.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNode.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResources.model_rebuild()
PodGeneratorQueryNetworkPodEdgesNodeParentNodeNetworkFabricLoopbackPoolNodeResourcesEdges.model_rebuild()
