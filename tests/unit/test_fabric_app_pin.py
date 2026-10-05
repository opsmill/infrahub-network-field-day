"""Pinning an application from its catalogue entry (specs/035-application-catalogue).

`generate-fabric-app` copies a catalogue entry onto a requested application ONCE.
The claims that matter are the negatives, because each of them fails quietly:

- a later catalogue edit must not move a running application;
- an application with no entry must be left exactly as it was;
- one on its way out must not be pinned;
- the run after a pin must write nothing, or the event rules loop;
- `vip_block_size`, which the rules watch, must never be written.

The SDK is replaced by small doubles. What they cannot prove is live behaviour
(a file node created inside a generator on a branch), which is a lab-phase check.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import pytest

from generators.generate_fabric_app import FabricAppGenerator
from tests.unit.test_fabric_app_generator import _app, _query, _RecordingClient
from tests.unit.test_fabric_app_generator import _generator as base_generator


@dataclass
class _Attr:
    value: Any = None


class _Peers:
    """A cardinality-many relationship: ids, and `add` by id."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = list(ids)
        self.fetched = False

    @property
    def peer_ids(self) -> list[str]:
        """Not an answer until fetched, as with the SDK's uninitialised manager."""
        assert self.fetched, "peer_ids read on a cardinality-many relationship that was never fetched"
        return self._ids

    async def fetch(self) -> None:
        self.fetched = True

    def add(self, peer_id: str) -> None:
        self._ids.append(peer_id)


class _One:
    """A cardinality-one relationship, fetched on demand."""

    def __init__(self, peer: Any = None) -> None:
        self.peer = peer
        self.id = None if peer is None else peer.id
        self.fetched = False

    async def fetch(self) -> None:
        self.fetched = True


class _File:
    def __init__(self, content: bytes | None = None) -> None:
        self.id = "file-1"
        self.content = content
        self.name: str | None = None
        self.saves = 0

    def upload_from_bytes(self, content: bytes, name: str) -> None:
        self.content = content
        self.name = name

    async def save(self, **_: Any) -> None:
        self.saves += 1

    async def download_file(self) -> bytes:
        assert self.content is not None
        return self.content


class _Entry:
    def __init__(self, **overrides: Any) -> None:
        self.id = "entry-whoami"
        self.name = _Attr("whoami")
        self.chart_repository = _Attr("https://cowboysysop.github.io/charts/")
        self.chart_name = _Attr("whoami")
        self.chart_version = _Attr("6.0.0")
        self.default_values = _Attr("replicaCount: 1\n")
        self.default_service_selector = _Attr(["otternet.lab/advertise=true"])
        self.default_policy_allow_egress_api_server = _Attr(False)
        self.default_advertised_services = _Peers(["svc-junos-http"])
        for key, value in overrides.items():
            setattr(self, key, value)


class _Service:
    def __init__(self, entry: _Entry | None, **overrides: Any) -> None:
        self.id = "app-1"
        self.name = _Attr("my-app")
        self.status = _Attr("provisioning")
        self.chart_repository = _Attr("https://example.invalid/typed")
        self.chart_name = _Attr("typed")
        self.chart_version = _Attr("0.0.1")
        self.service_selector = _Attr([])
        self.policy_allow_egress_api_server = _Attr(False)
        self.advertised_services = _Peers([])
        self.definition_pinned = _Attr(False)
        self.vip_block_size = _Attr(28)
        self.definition = _One(entry)
        self.values_file = _One(None)
        self.saves: list[dict[str, Any]] = []
        for key, value in overrides.items():
            setattr(self, key, value)

    async def save(self, **kwargs: Any) -> None:
        self.saves.append(
            {
                **kwargs,
                "chart": (self.chart_repository.value, self.chart_name.value, self.chart_version.value),
                "pinned": self.definition_pinned.value,
                "block_size": self.vip_block_size.value,
            }
        )


@dataclass
class _Client:
    service: _Service
    created: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    files: list[_File] = field(default_factory=list)
    events: list[str] = field(default_factory=list)

    async def get(self, kind: str, id: str | None = None, **_: Any) -> Any:  # noqa: A002
        assert kind == "ServiceFabricApp"
        return self.service

    async def create(self, kind: str, data: dict[str, Any]) -> _File:
        assert kind == "ServiceFabricAppValuesFile"
        self.created.append((kind, data))
        self.events.append("create-file")
        file = _File()
        original = file.save

        async def save(**kwargs: Any) -> None:
            self.events.append("save-file")
            await original(**kwargs)

        file.save = save  # type: ignore[method-assign]
        self.files.append(file)
        return file


def _generator(client: Any) -> FabricAppGenerator:
    generator = FabricAppGenerator.__new__(FabricAppGenerator)
    generator._client = client  # type: ignore[attr-defined]
    generator._init_client = client  # type: ignore[attr-defined]
    generator.logger = logging.getLogger("test")
    generator.branch = "a-review-branch"
    return generator


@pytest.mark.asyncio
async def test_an_unpinned_application_is_pinned_from_its_entry() -> None:
    service = _Service(_Entry())
    client = _Client(service)

    await _generator(client)._pin_definition("app-1")

    assert (service.chart_repository.value, service.chart_name.value, service.chart_version.value) == (
        "https://cowboysysop.github.io/charts/",
        "whoami",
        "6.0.0",
    )
    assert service.definition_pinned.value is True
    assert service.service_selector.value == ["otternet.lab/advertise=true"]
    assert service.advertised_services.peer_ids == ["svc-junos-http"]
    assert len(service.saves) == 1, "the chart fields and the marker are ONE save"
    assert service.saves[0]["pinned"] is True
    assert service.saves[0]["chart"][2] == "6.0.0"


@pytest.mark.asyncio
async def test_an_entry_that_needs_the_api_server_turns_the_namespace_egress_on() -> None:
    service = _Service(_Entry(default_policy_allow_egress_api_server=_Attr(True)))

    await _generator(_Client(service))._pin_definition("app-1")

    assert service.policy_allow_egress_api_server.value is True
    assert len(service.saves) == 1, "the egress setting rides on the same single save"


@pytest.mark.asyncio
async def test_an_entry_that_does_not_need_it_leaves_the_egress_alone() -> None:
    asked = _Service(_Entry(), policy_allow_egress_api_server=_Attr(True))
    plain = _Service(_Entry())

    await _generator(_Client(asked))._pin_definition("app-1")
    await _generator(_Client(plain))._pin_definition("app-1")

    assert asked.policy_allow_egress_api_server.value is True, "a request's own setting is never turned off"
    assert plain.policy_allow_egress_api_server.value is False


@pytest.mark.asyncio
async def test_the_values_file_is_created_from_the_entrys_text() -> None:
    client = _Client(_Service(_Entry(default_values=_Attr("service:\n  type: LoadBalancer\n"))))

    await _generator(client)._pin_definition("app-1")

    assert client.created == [("ServiceFabricAppValuesFile", {"app": "app-1"})]
    (file,) = client.files
    assert file.content == b"service:\n  type: LoadBalancer\n"
    assert file.name == "values.yaml"
    assert file.saves == 1


@pytest.mark.asyncio
async def test_the_file_is_written_before_the_marker_so_a_failure_is_retried() -> None:
    """The marker is the commit point. A pin recorded as done with no file would
    never be repeated."""
    service = _Service(_Entry())
    client = _Client(service)

    await _generator(client)._pin_definition("app-1")

    assert client.events == ["create-file", "save-file"]
    assert service.definition_pinned.value is True


@pytest.mark.asyncio
async def test_an_application_with_no_entry_is_left_exactly_as_it_was() -> None:
    service = _Service(None)
    client = _Client(service)

    await _generator(client)._pin_definition("app-1")

    assert service.saves == []
    assert client.created == []
    assert service.chart_name.value == "typed"
    assert service.definition_pinned.value is False


@pytest.mark.asyncio
async def test_a_pinned_application_ignores_a_changed_entry() -> None:
    """THE POINT OF PINNING: editing the catalogue upgrades nothing."""
    service = _Service(
        _Entry(chart_version=_Attr("7.0.0"), default_values=_Attr("replicaCount: 9\n")),
        definition_pinned=_Attr(True),
        chart_version=_Attr("6.0.0"),
    )
    client = _Client(service)

    await _generator(client)._pin_definition("app-1")

    assert service.saves == []
    assert client.created == []
    assert service.chart_version.value == "6.0.0"
    assert service.definition.fetched is False, "a pinned application does not even read the entry"


@pytest.mark.asyncio
async def test_a_second_run_after_a_pin_writes_nothing() -> None:
    """The run the status write-back triggers must be a no-op, or the rules loop."""
    service = _Service(_Entry())
    client = _Client(service)
    generator = _generator(client)

    await generator._pin_definition("app-1")
    saves, created = len(service.saves), len(client.created)
    await generator._pin_definition("app-1")

    assert (len(service.saves), len(client.created)) == (saves, created)


@pytest.mark.asyncio
async def test_an_entry_with_no_values_pins_without_a_file_and_is_not_repinned() -> None:
    service = _Service(_Entry(default_values=_Attr(None)))
    client = _Client(service)
    generator = _generator(client)

    await generator._pin_definition("app-1")

    assert client.created == []
    assert service.definition_pinned.value is True
    saves = len(service.saves)
    await generator._pin_definition("app-1")
    assert len(service.saves) == saves


@pytest.mark.asyncio
async def test_typed_chart_fields_that_disagree_with_the_entry_are_overwritten_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = _Service(_Entry())
    client = _Client(service)

    with caplog.at_level(logging.WARNING, logger="test"):
        await _generator(client)._pin_definition("app-1")

    assert service.chart_name.value == "whoami"
    assert "chart_name" in caplog.text
    assert "the catalogue entry decides" in caplog.text


@pytest.mark.asyncio
async def test_a_requests_own_selector_and_services_are_kept() -> None:
    service = _Service(_Entry(), service_selector=_Attr(["team=mine"]), advertised_services=_Peers(["svc-https"]))

    await _generator(_Client(service))._pin_definition("app-1")

    assert service.service_selector.value == ["team=mine"]
    assert service.advertised_services.peer_ids == ["svc-https"]


@pytest.mark.asyncio
async def test_the_block_size_is_never_written() -> None:
    """It is a watched input: writing it back would feed the run into the next."""
    service = _Service(_Entry())

    await _generator(_Client(service))._pin_definition("app-1")

    assert service.vip_block_size.value == 28
    assert {save["block_size"] for save in service.saves} == {28}


@pytest.mark.asyncio
async def test_an_existing_values_file_with_the_same_content_is_not_rewritten() -> None:
    content = b"replicaCount: 1\n"
    existing = _File(content)
    service = _Service(_Entry(default_values=_Attr(content.decode())), values_file=_One(existing))
    client = _Client(service)

    await _generator(client)._pin_definition("app-1")

    assert existing.saves == 0
    assert client.created == []
    assert hashlib.sha256(existing.content or b"").hexdigest() == hashlib.sha256(content).hexdigest()


# ---- generate() calls it, at the right moments -----------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "pinned"),
    [("provisioning", True), ("active", True), ("error", True), ("decommissioning", False), ("decommissioned", False)],
)
async def test_generate_pins_unless_the_application_is_being_withdrawn(status: str, pinned: bool) -> None:
    client = _RecordingClient(node_status=status)
    generator = base_generator(client)
    calls: list[str] = []

    async def spy(app_id: str) -> None:
        calls.append(app_id)

    generator._pin_definition = spy  # type: ignore[method-assign]
    await generator.generate(_query(app=_app(status=status, exposed=False)).model_dump(by_alias=True))

    assert (calls == ["app-1"]) is pinned


@pytest.mark.asyncio
async def test_a_failed_pin_marks_the_application_error_and_raises() -> None:
    client = _RecordingClient()
    generator = base_generator(client)

    async def boom(_: str) -> None:
        msg = "entry unreadable"
        raise RuntimeError(msg)

    generator._pin_definition = boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="unreadable"):
        await generator.generate(_query(app=_app(status="provisioning")).model_dump(by_alias=True))

    assert client.nodes["app-1"].status.value == "error"
    assert client.allocations == []
