"""generate-monitoring-collector asks for a render and changes nothing (cycle 034).

Its whole job is one POST: re-render the collector's configuration artifact on
the generator's own branch. Two properties make that safe to run in every
proposed change and after every merge, and both are asserted here:

* **No node is written.** A generator that created or updated something would
  emit an event, and this one runs on every change to the lab -- which is how a
  quiet freshness hook becomes a loop.
* **`?branch=` is on the request, and `nodes` names the artifact.** Without the
  branch the endpoint regenerates against `main`; with the collector's id in
  `nodes` it regenerates nothing at all. Both were measured on
  `generate-app-access`, and both return 200.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from generators.generate_monitoring_collector import COLLECTOR_ARTIFACT, MonitoringCollectorGenerator


class _Response:
    def raise_for_status(self) -> None:
        return None


class _Client:
    address = "http://infrahub:8000"

    def __init__(self, artifacts: list[str]) -> None:
        self.artifacts = artifacts
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.writes = 0

    async def get(self, kind: str, **_filters: Any) -> Any:
        assert kind == "CoreArtifactDefinition"
        return SimpleNamespace(id="def-1")

    async def filters(self, kind: str, **filters: Any) -> list[Any]:
        assert kind == "CoreArtifact"
        assert filters["name__value"] == COLLECTOR_ARTIFACT
        assert filters["object__ids"] == ["collector-1"]
        return [SimpleNamespace(id=a) for a in self.artifacts]

    async def _post(self, url: str, payload: dict[str, Any]) -> _Response:
        self.posts.append((url, payload))
        return _Response()

    def create(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover - must never be called
        self.writes += 1
        raise AssertionError("generate-monitoring-collector must not create nodes")


def _quiet(*_args: object, **_kwargs: object) -> None:
    return None


def _run(artifacts: list[str], branch: str = "feature-x") -> _Client:
    generator = MonitoringCollectorGenerator.__new__(MonitoringCollectorGenerator)
    client = _Client(artifacts)
    generator._init_client = client
    generator.branch = branch
    generator.logger = SimpleNamespace(info=_quiet, warning=_quiet)
    data = {"target": {"edges": [{"node": {"id": "collector-1", "name": {"value": "otternet-telegraf"}}}]}}
    asyncio.run(generator.generate(data))
    return client


def test_one_render_is_requested_on_the_generators_own_branch_naming_the_artifact() -> None:
    client = _run(["artifact-9"])
    assert client.posts == [
        ("http://infrahub:8000/api/artifact/generate/def-1?branch=feature-x", {"nodes": ["artifact-9"]})
    ]
    assert client.writes == 0


def test_before_the_first_render_every_member_is_asked_for() -> None:
    client = _run([])
    assert client.posts[0][1] == {"nodes": []}


def test_running_twice_requests_the_same_render_and_writes_nothing() -> None:
    first, second = _run(["artifact-9"]), _run(["artifact-9"])
    assert first.posts == second.posts
    assert first.writes == second.writes == 0
