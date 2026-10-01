from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GenerateMonitoringCollectorQuery(BaseModel):
    target: "GenerateMonitoringCollectorQueryTarget"


class GenerateMonitoringCollectorQueryTarget(BaseModel):
    edges: list["GenerateMonitoringCollectorQueryTargetEdges"]


class GenerateMonitoringCollectorQueryTargetEdges(BaseModel):
    node: Optional["GenerateMonitoringCollectorQueryTargetEdgesNode"]


class GenerateMonitoringCollectorQueryTargetEdgesNode(BaseModel):
    id: str
    name: Optional["GenerateMonitoringCollectorQueryTargetEdgesNodeName"]


class GenerateMonitoringCollectorQueryTargetEdgesNodeName(BaseModel):
    value: Optional[str]


GenerateMonitoringCollectorQuery.model_rebuild()
GenerateMonitoringCollectorQueryTarget.model_rebuild()
GenerateMonitoringCollectorQueryTargetEdges.model_rebuild()
GenerateMonitoringCollectorQueryTargetEdgesNode.model_rebuild()
