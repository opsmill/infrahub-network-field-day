from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AvdFabricDevicesQuery(BaseModel):
    network_fabric: "AvdFabricDevicesQueryNetworkFabric" = Field(alias="NetworkFabric")
    dcim_fabric_switch: "AvdFabricDevicesQueryDcimFabricSwitch" = Field(
        alias="DcimFabricSwitch"
    )


class AvdFabricDevicesQueryNetworkFabric(BaseModel):
    edges: list["AvdFabricDevicesQueryNetworkFabricEdges"]


class AvdFabricDevicesQueryNetworkFabricEdges(BaseModel):
    node: Optional["AvdFabricDevicesQueryNetworkFabricEdgesNode"]


class AvdFabricDevicesQueryNetworkFabricEdgesNode(BaseModel):
    id: str
    name: Optional["AvdFabricDevicesQueryNetworkFabricEdgesNodeName"]


class AvdFabricDevicesQueryNetworkFabricEdgesNodeName(BaseModel):
    value: Optional[str]


class AvdFabricDevicesQueryDcimFabricSwitch(BaseModel):
    edges: list["AvdFabricDevicesQueryDcimFabricSwitchEdges"]


class AvdFabricDevicesQueryDcimFabricSwitchEdges(BaseModel):
    node: Optional["AvdFabricDevicesQueryDcimFabricSwitchEdgesNode"]


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNode(BaseModel):
    id: str
    name: Optional["AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeName"]
    pod: "AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePod"
    avd_artifact: "AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifact"


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeName(BaseModel):
    value: Optional[str]


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePod(BaseModel):
    node: Optional["AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePodNode"]


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePodNode(BaseModel):
    id: str
    parent: "AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePodNodeParent"


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePodNodeParent(BaseModel):
    node: Optional["AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePodNodeParentNode"]


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePodNodeParentNode(BaseModel):
    typename__: Literal["NetworkBuildingBlock", "NetworkFabric", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifact(BaseModel):
    node: Optional["AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNode"]


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNode(BaseModel):
    id: str
    hostvar_file: (
        "AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeHostvarFile"
    )
    structured_config_file: "AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile"


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeHostvarFile(
    BaseModel
):
    node: Optional[
        "AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeHostvarFileNode"
    ]


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeHostvarFileNode(
    BaseModel
):
    id: str


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile(
    BaseModel
):
    node: Optional[
        "AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode"
    ]


class AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode(
    BaseModel
):
    id: str


AvdFabricDevicesQuery.model_rebuild()
AvdFabricDevicesQueryNetworkFabric.model_rebuild()
AvdFabricDevicesQueryNetworkFabricEdges.model_rebuild()
AvdFabricDevicesQueryNetworkFabricEdgesNode.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitch.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdges.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdgesNode.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePod.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePodNode.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdgesNodePodNodeParent.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifact.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNode.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeHostvarFile.model_rebuild()
AvdFabricDevicesQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile.model_rebuild()
