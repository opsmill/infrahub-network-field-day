from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AvdDeviceConfigQuery(BaseModel):
    dcim_fabric_switch: "AvdDeviceConfigQueryDcimFabricSwitch" = Field(
        alias="DcimFabricSwitch"
    )


class AvdDeviceConfigQueryDcimFabricSwitch(BaseModel):
    edges: list["AvdDeviceConfigQueryDcimFabricSwitchEdges"]


class AvdDeviceConfigQueryDcimFabricSwitchEdges(BaseModel):
    node: Optional["AvdDeviceConfigQueryDcimFabricSwitchEdgesNode"]


class AvdDeviceConfigQueryDcimFabricSwitchEdgesNode(BaseModel):
    id: str
    name: Optional["AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeName"]
    avd_artifact: "AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifact"


class AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeName(BaseModel):
    value: Optional[str]


class AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifact(BaseModel):
    node: Optional["AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNode"]


class AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNode(BaseModel):
    id: str
    structured_config_file: "AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile"


class AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile(
    BaseModel
):
    node: Optional[
        "AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode"
    ]


class AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode(
    BaseModel
):
    id: str
    checksum: Optional[
        "AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNodeChecksum"
    ]


class AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNodeChecksum(
    BaseModel
):
    value: Optional[str]


AvdDeviceConfigQuery.model_rebuild()
AvdDeviceConfigQueryDcimFabricSwitch.model_rebuild()
AvdDeviceConfigQueryDcimFabricSwitchEdges.model_rebuild()
AvdDeviceConfigQueryDcimFabricSwitchEdgesNode.model_rebuild()
AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifact.model_rebuild()
AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNode.model_rebuild()
AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFile.model_rebuild()
AvdDeviceConfigQueryDcimFabricSwitchEdgesNodeAvdArtifactNodeStructuredConfigFileNode.model_rebuild()
