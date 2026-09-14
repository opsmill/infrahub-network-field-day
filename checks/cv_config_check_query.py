from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CVConfigCheckQuery(BaseModel):
    network_fabric: "CVConfigCheckQueryNetworkFabric" = Field(alias="NetworkFabric")
    dcim_fabric_switch: "CVConfigCheckQueryDcimFabricSwitch" = Field(
        alias="DcimFabricSwitch"
    )


class CVConfigCheckQueryNetworkFabric(BaseModel):
    edges: list["CVConfigCheckQueryNetworkFabricEdges"]


class CVConfigCheckQueryNetworkFabricEdges(BaseModel):
    node: Optional["CVConfigCheckQueryNetworkFabricEdgesNode"]


class CVConfigCheckQueryNetworkFabricEdgesNode(BaseModel):
    id: str
    name: Optional["CVConfigCheckQueryNetworkFabricEdgesNodeName"]
    cloudvision_managed: Optional[
        "CVConfigCheckQueryNetworkFabricEdgesNodeCloudvisionManaged"
    ]


class CVConfigCheckQueryNetworkFabricEdgesNodeName(BaseModel):
    value: Optional[str]


class CVConfigCheckQueryNetworkFabricEdgesNodeCloudvisionManaged(BaseModel):
    value: Optional[bool]


class CVConfigCheckQueryDcimFabricSwitch(BaseModel):
    edges: list["CVConfigCheckQueryDcimFabricSwitchEdges"]


class CVConfigCheckQueryDcimFabricSwitchEdges(BaseModel):
    node: Optional["CVConfigCheckQueryDcimFabricSwitchEdgesNode"]


class CVConfigCheckQueryDcimFabricSwitchEdgesNode(BaseModel):
    id: str
    name: Optional["CVConfigCheckQueryDcimFabricSwitchEdgesNodeName"]
    serial: Optional["CVConfigCheckQueryDcimFabricSwitchEdgesNodeSerial"]
    pod: "CVConfigCheckQueryDcimFabricSwitchEdgesNodePod"
    avd_artifact: "CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifact"


class CVConfigCheckQueryDcimFabricSwitchEdgesNodeName(BaseModel):
    value: Optional[str]


class CVConfigCheckQueryDcimFabricSwitchEdgesNodeSerial(BaseModel):
    value: Optional[str]


class CVConfigCheckQueryDcimFabricSwitchEdgesNodePod(BaseModel):
    node: Optional["CVConfigCheckQueryDcimFabricSwitchEdgesNodePodNode"]


class CVConfigCheckQueryDcimFabricSwitchEdgesNodePodNode(BaseModel):
    id: str
    parent: "CVConfigCheckQueryDcimFabricSwitchEdgesNodePodNodeParent"


class CVConfigCheckQueryDcimFabricSwitchEdgesNodePodNodeParent(BaseModel):
    node: Optional["CVConfigCheckQueryDcimFabricSwitchEdgesNodePodNodeParentNode"]


class CVConfigCheckQueryDcimFabricSwitchEdgesNodePodNodeParentNode(BaseModel):
    typename__: Literal["NetworkBuildingBlock", "NetworkFabric", "NetworkPod"] = Field(
        alias="__typename"
    )
    id: Optional[str]


class CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifact(BaseModel):
    node: Optional["CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifactNode"]


class CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifactNode(BaseModel):
    id: str
    structured_config_file: (
        "CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile"
    )


class CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile(
    BaseModel
):
    node: Optional[
        "CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode"
    ]


class CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode(
    BaseModel
):
    id: str


CVConfigCheckQuery.model_rebuild()
CVConfigCheckQueryNetworkFabric.model_rebuild()
CVConfigCheckQueryNetworkFabricEdges.model_rebuild()
CVConfigCheckQueryNetworkFabricEdgesNode.model_rebuild()
CVConfigCheckQueryDcimFabricSwitch.model_rebuild()
CVConfigCheckQueryDcimFabricSwitchEdges.model_rebuild()
CVConfigCheckQueryDcimFabricSwitchEdgesNode.model_rebuild()
CVConfigCheckQueryDcimFabricSwitchEdgesNodePod.model_rebuild()
CVConfigCheckQueryDcimFabricSwitchEdgesNodePodNode.model_rebuild()
CVConfigCheckQueryDcimFabricSwitchEdgesNodePodNodeParent.model_rebuild()
CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifact.model_rebuild()
CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifactNode.model_rebuild()
CVConfigCheckQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile.model_rebuild()
