from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field


class AvdAntaCatalogQuery(BaseModel):
    target: "AvdAntaCatalogQueryTarget"
    dcim_fabric_switch: "AvdAntaCatalogQueryDcimFabricSwitch" = Field(
        alias="DcimFabricSwitch"
    )


class AvdAntaCatalogQueryTarget(BaseModel):
    edges: list["AvdAntaCatalogQueryTargetEdges"]


class AvdAntaCatalogQueryTargetEdges(BaseModel):
    node: Optional["AvdAntaCatalogQueryTargetEdgesNode"]


class AvdAntaCatalogQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["AvdAntaCatalogQueryTargetEdgesNodeName"]
    pod: "AvdAntaCatalogQueryTargetEdgesNodePod"


class AvdAntaCatalogQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


class AvdAntaCatalogQueryTargetEdgesNodePod(BaseModel):
    node: Optional["AvdAntaCatalogQueryTargetEdgesNodePodNode"]


class AvdAntaCatalogQueryTargetEdgesNodePodNode(BaseModel):
    id: str
    parent: "AvdAntaCatalogQueryTargetEdgesNodePodNodeParent"


class AvdAntaCatalogQueryTargetEdgesNodePodNodeParent(BaseModel):
    node: Optional[
        Annotated[
            Union[
                "AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkBuildingBlock",
                "AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkFabric",
            ],
            Field(discriminator="typename__"),
        ]
    ]


class AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkBuildingBlock(
    BaseModel
):
    typename__: Literal["NetworkBuildingBlock", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkFabric(BaseModel):
    typename__: Literal["NetworkFabric"] = Field(alias="__typename")
    id: str
    name: Optional[
        "AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkFabricName"
    ]
    anta_enabled: Optional[
        "AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkFabricAntaEnabled"
    ]


class AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkFabricName(BaseModel):
    value: Optional[str]


class AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkFabricAntaEnabled(
    BaseModel
):
    value: Optional[bool]


class AvdAntaCatalogQueryDcimFabricSwitch(BaseModel):
    edges: list["AvdAntaCatalogQueryDcimFabricSwitchEdges"]


class AvdAntaCatalogQueryDcimFabricSwitchEdges(BaseModel):
    node: Optional["AvdAntaCatalogQueryDcimFabricSwitchEdgesNode"]


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNode(BaseModel):
    id: str
    name: Optional["AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeName"]
    pod: "AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePod"
    avd_artifact: "AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifact"


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeName(BaseModel):
    value: Optional[str]


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePod(BaseModel):
    node: Optional["AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePodNode"]


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePodNode(BaseModel):
    id: str
    parent: "AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePodNodeParent"


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePodNodeParent(BaseModel):
    node: Optional["AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePodNodeParentNode"]


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePodNodeParentNode(BaseModel):
    typename__: Literal["NetworkBuildingBlock", "NetworkFabric", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifact(BaseModel):
    node: Optional["AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifactNode"]


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifactNode(BaseModel):
    id: str
    structured_config_file: "AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile"


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile(
    BaseModel
):
    node: Optional[
        "AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode"
    ]


class AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode(
    BaseModel
):
    id: str


AvdAntaCatalogQuery.model_rebuild()
AvdAntaCatalogQueryTarget.model_rebuild()
AvdAntaCatalogQueryTargetEdges.model_rebuild()
AvdAntaCatalogQueryTargetEdgesNode.model_rebuild()
AvdAntaCatalogQueryTargetEdgesNodePod.model_rebuild()
AvdAntaCatalogQueryTargetEdgesNodePodNode.model_rebuild()
AvdAntaCatalogQueryTargetEdgesNodePodNodeParent.model_rebuild()
AvdAntaCatalogQueryTargetEdgesNodePodNodeParentNodeNetworkFabric.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitch.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitchEdges.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitchEdgesNode.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePod.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePodNode.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitchEdgesNodePodNodeParent.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifact.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifactNode.model_rebuild()
AvdAntaCatalogQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile.model_rebuild()
