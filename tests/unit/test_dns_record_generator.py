"""generate-dns-record names an application, and takes the name away (specs/037-lab-dns-service).

The generator writes `fqdn` on an address and nothing else, so the properties
asserted are about what it will and will not touch: it never moves a name that
already has an address, it creates an address only when none exists and marks
it, and it deletes only what it marked.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from generators.generate_dns_record import (
    CREATED_MARK,
    DnsRecordGenerator,
    first_address,
    has_name,
)

ZONE = "int.otternet.lab"


def test_the_first_address_of_the_block_is_the_name() -> None:
    assert first_address("10.112.240.16/28") == "10.112.240.16/32"
    assert first_address("10.112.240.0/28") == "10.112.240.0/32"


@pytest.mark.parametrize(
    ("status", "exposed", "prefix", "label", "expected"),
    [
        ("active", True, "10.112.240.16/28", "otter-shop", True),
        ("provisioning", True, "10.112.240.16/28", "otter-shop", True),
        ("decommissioning", True, "10.112.240.16/28", "otter-shop", False),
        ("decommissioned", True, "10.112.240.16/28", "otter-shop", False),
        ("active", False, "10.112.240.16/28", "otter-shop", False),
        ("active", True, None, "otter-shop", False),
        ("active", True, "10.112.240.16/28", "Not_A_Label", False),
    ],
)
def test_an_application_has_a_name_only_when_live_exposed_with_a_block(
    status: str, exposed: bool, prefix: str | None, label: str, expected: bool
) -> None:
    assert has_name(status=status, exposed=exposed, prefix=prefix, label=label) is expected


@dataclass
class _Attr:
    value: Any


class _Address:
    _next_id = 0

    def __init__(self, address: str, fqdn: str | None = None, description: str | None = None) -> None:
        _Address._next_id += 1
        self.id = f"id-{_Address._next_id:04d}"
        self.address = _Attr(address)
        self.fqdn = _Attr(fqdn)
        self.description = _Attr(description)
        self.saved = 0
        self.deleted = False

    async def save(self, **_kwargs: Any) -> None:
        self.saved += 1

    async def delete(self) -> None:
        self.deleted = True


class _Client:
    address = "http://infrahub:8000"

    def __init__(self, held: list[_Address]) -> None:
        self.held = held
        self.created: list[_Address] = []

    async def filters(self, kind: Any, **filters: Any) -> list[_Address]:
        name = getattr(kind, "__name__", kind)
        if name == "IpamIPAddress":
            if "fqdn__value" in filters:
                return [a for a in self.held if a.fqdn.value == filters["fqdn__value"]]
            return [a for a in self.held if a.address.value == filters["address__value"]]
        return []  # CoreArtifact: none yet

    async def get(self, kind: str, **_filters: Any) -> Any:
        return SimpleNamespace(id="def-1")

    async def create(self, _kind: Any, **data: Any) -> _Address:
        self.create_args = data
        node = _Address(data["address"], data["fqdn"], data["description"])
        self.created.append(node)
        self.held.append(node)
        return node

    async def _post(self, url: str, payload: dict[str, Any]) -> Any:
        return SimpleNamespace(raise_for_status=lambda: None)


def _data(
    *, status: str = "active", exposed: bool = True, prefix: str | None = "10.112.240.16/28", zone: str | None = ZONE
) -> dict[str, Any]:
    def v(x: Any) -> dict[str, Any]:
        return {"value": x}

    block = {"node": {"id": "p1", "prefix": v(prefix)}} if prefix else {"node": None}
    resolvers = [{"node": {"id": "r1", "name": v("otternet-dns"), "dns_zone": v(zone)}}] if zone else []
    return {
        "target": {
            "edges": [
                {
                    "node": {
                        "id": "a1",
                        "name": v("otter-shop"),
                        "status": v(status),
                        "exposed": v(exposed),
                        "vip_block": block,
                    }
                }
            ]
        },
        "resolver": {"edges": resolvers},
    }


def _run(held: list[_Address], data: dict[str, Any]) -> _Client:
    generator = DnsRecordGenerator.__new__(DnsRecordGenerator)
    client = _Client(held)
    generator.client = client
    generator._init_client = client
    generator.branch = "feature-x"
    quiet = lambda *_a, **_k: None  # noqa: E731
    generator.logger = SimpleNamespace(info=quiet, warning=quiet)
    asyncio.run(generator.generate(data))
    return client


def test_a_live_application_gets_a_marked_address_carrying_its_name() -> None:
    client = _run([], _data())
    assert [(a.address.value, a.fqdn.value) for a in client.created] == [("10.112.240.16/32", f"otter-shop.{ZONE}")]
    assert str(client.created[0].description.value).startswith(CREATED_MARK)


def test_running_twice_changes_nothing_the_second_time() -> None:
    held: list[_Address] = []
    _run(held, _data())
    second = _run(held, _data())
    assert second.created == []
    assert len(held) == 1


def test_an_existing_address_without_a_name_is_named_not_duplicated() -> None:
    existing = _Address("10.112.240.16/32", None, "someone else made this")
    client = _run([existing], _data())
    assert client.created == []
    assert existing.fqdn.value == f"otter-shop.{ZONE}"
    assert existing.description.value == "someone else made this"


def test_a_name_that_already_has_an_address_is_never_moved() -> None:
    seeded = _Address("10.112.240.17/32", f"otter-shop.{ZONE}", "hand seeded")
    client = _run([seeded], _data())
    assert client.created == []
    assert seeded.address.value == "10.112.240.17/32"


def test_withdrawal_deletes_only_what_it_created() -> None:
    mine = _Address("10.112.240.16/32", f"otter-shop.{ZONE}", f"{CREATED_MARK} otter-shop")
    _run([mine], _data(status="decommissioning"))
    assert mine.deleted


def test_withdrawal_only_clears_the_name_on_an_address_it_did_not_create() -> None:
    theirs = _Address("10.112.240.16/32", f"otter-shop.{ZONE}", "a firewall entry points here")
    _run([theirs], _data(status="decommissioning"))
    assert not theirs.deleted
    assert theirs.fqdn.value is None


def test_an_unexposed_application_loses_its_name() -> None:
    mine = _Address("10.112.240.16/32", f"otter-shop.{ZONE}", f"{CREATED_MARK} otter-shop")
    _run([mine], _data(exposed=False))
    assert mine.deleted


def test_an_application_with_no_block_yet_gets_no_name_and_no_error() -> None:
    client = _run([], _data(prefix=None))
    assert client.created == []


def test_with_no_resolver_nothing_is_written() -> None:
    client = _run([], _data(zone=None))
    assert client.created == []


def test_two_resolvers_are_refused() -> None:
    data = _data()
    data["resolver"]["edges"].append({"node": {"id": "r2", "name": {"value": "other"}, "dns_zone": {"value": "x.lab"}}})
    with pytest.raises(ValueError, match="one resolver"):
        _run([], data)


def test_the_create_names_the_namespace_so_a_racing_upsert_finds_the_first() -> None:
    client = _run([], _data())
    assert client.create_args["ip_namespace"] == {"hfid": ["default"]}


def test_two_racing_runs_that_both_created_the_address_leave_one() -> None:
    first = _Address("10.112.240.16/32", f"otter-shop.{ZONE}", f"{CREATED_MARK} otter-shop")
    second = _Address("10.112.240.16/32", f"otter-shop.{ZONE}", f"{CREATED_MARK} otter-shop")
    _run([second, first], _data())
    survivors = [a for a in (first, second) if not a.deleted]
    assert [a.id for a in survivors] == [min(first.id, second.id)]


def test_a_duplicate_is_never_deleted_unless_this_generator_created_it() -> None:
    seeded = _Address("10.112.240.17/32", f"otter-shop.{ZONE}", "hand seeded")
    created = _Address("10.112.240.16/32", f"otter-shop.{ZONE}", f"{CREATED_MARK} otter-shop")
    _run([seeded, created], _data())
    assert not seeded.deleted
