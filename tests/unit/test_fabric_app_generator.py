"""Unit tests for the fabric application generator.

Fixtures built from the real shapes in `objects/34_nfd41_cluster.yml` and
`objects/36_nfd41_app_services.yml`: one cluster whose `vip_pools` is
`10.112.240.0/24`, one pool drawing from it, and `nfd41-demo` holding the
hand-written `10.112.240.0/28`.

**The claim this file exists to protect is that the seeded application does not
move.** Its block is declared in `objects/29_nfd41_offfabric_prefixes.yml`, the
`zone-advertisement` check measures grant VIPs against it, and the rendered
Crossplane manifest is delivered into a live cluster. A generator that
reallocated it, or withdrew it on decommissioning, would break all three -- so
"already has a block" and "did not allocate this block" are the two paths with
the most tests behind them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pytest

from generators.generate_fabric_app import (
    FabricAppGenerator,
    resolve_vip_pool,
    validate_model,
    wants_a_block,
)
from generators.generate_fabric_app_query import GenerateFabricAppQuery

APP_NAME = "nfd41-demo"
POOL_ID = "pool-vip"
SUPERNET_ID = "pfx-10-112-240-0-24"
SEEDED_BLOCK_ID = "pfx-10-112-240-0-28"
SEEDED_BLOCK = "10.112.240.0/28"


def _wrap(value: Any) -> dict[str, Any]:
    return {"value": value}


def _app(
    *,
    exposed: bool = True,
    status: str = "active",
    block: tuple[str, str] | None = None,
    managed: bool = False,
    size: int | None = 28,
    supernets: list[str] | None = None,
    cluster: bool = True,
) -> dict[str, Any]:
    pools = [SUPERNET_ID] if supernets is None else supernets
    return {
        "node": {
            "id": "app-1",
            "name": _wrap(APP_NAME),
            "status": _wrap(status),
            "exposed": _wrap(exposed),
            "vip_block_size": _wrap(size),
            "vip_block_managed": _wrap(managed),
            "vip_block": ({"node": {"id": block[0], "prefix": _wrap(block[1])}} if block else {"node": None}),
            "cluster": (
                {
                    "node": {
                        "id": "cluster-nfd41",
                        "name": _wrap("nfd41"),
                        "vip_pools": {
                            "edges": [
                                {"node": {"__typename": "IpamPrefix", "id": pid, "prefix": _wrap("10.112.240.0/24")}}
                                for pid in pools
                            ]
                        },
                    }
                }
                if cluster
                else {"node": None}
            ),
        }
    }


def _pools(*, drawing_from: list[str] | None = None, extra: int = 0) -> dict[str, Any]:
    """The lab's prefix pools. Only one draws from the cluster's VIP supernet."""
    resources = [SUPERNET_ID] if drawing_from is None else drawing_from
    entries: list[dict[str, Any]] = [
        {"id": "pool-loopback", "name": "NFD41-Loopback-Pool", "resources": ["pfx-loopback"]},
        {"id": POOL_ID, "name": "NFD41-VIP-Pool", "resources": resources},
        {"id": "pool-segment", "name": "NFD41-Segment-Subnet-Pool", "resources": ["pfx-segment"]},
    ]
    entries.extend({"id": f"pool-extra-{n}", "name": f"Extra-{n}", "resources": [SUPERNET_ID]} for n in range(extra))
    return {
        "edges": [
            {
                "node": {
                    "id": entry["id"],
                    "name": _wrap(entry["name"]),
                    "resources": {
                        "edges": [{"node": {"__typename": "IpamPrefix", "id": rid}} for rid in entry["resources"]]
                    },
                }
            }
            for entry in entries
        ]
    }


def _query(app: dict[str, Any] | None = None, pools: dict[str, Any] | None = None) -> GenerateFabricAppQuery:
    return GenerateFabricAppQuery(
        target={"edges": [app if app is not None else _app()]},
        CoreIPPrefixPool=pools if pools is not None else _pools(),
    )


# ---------------------------------------------------------------------------
# Finding the pool
# ---------------------------------------------------------------------------


def test_the_pool_is_found_through_the_cluster() -> None:
    """Not by name and not by role. A cluster's `vip_pools` are the only
    supernets the leaves' inbound route policy permits, so the pool that draws
    from them is the only one that can produce a routable block."""
    parsed = _query()
    assert resolve_vip_pool(parsed, parsed.target.edges[0].node) == POOL_ID


def test_no_pool_over_the_clusters_supernet_is_refused() -> None:
    parsed = _query(pools=_pools(drawing_from=["pfx-something-else"]))
    with pytest.raises(ValueError, match="found none"):
        resolve_vip_pool(parsed, parsed.target.edges[0].node)


def test_two_pools_over_the_same_supernet_are_refused_rather_than_guessed() -> None:
    """They would allocate against each other, and the generator must not pick."""
    parsed = _query(pools=_pools(extra=1))
    with pytest.raises(ValueError, match="found 2"):
        resolve_vip_pool(parsed, parsed.target.edges[0].node)


def test_a_cluster_with_no_vip_pools_is_refused_with_the_remedy() -> None:
    parsed = _query(app=_app(supernets=[]))
    with pytest.raises(ValueError, match="add one to the cluster"):
        resolve_vip_pool(parsed, parsed.target.edges[0].node)


def test_an_application_with_no_cluster_is_refused() -> None:
    parsed = _query(app=_app(cluster=False))
    with pytest.raises(ValueError, match="names no cluster"):
        validate_model(parsed)


# ---------------------------------------------------------------------------
# Who should hold a block
# ---------------------------------------------------------------------------


def test_an_exposed_active_application_wants_one() -> None:
    assert wants_a_block(_query().target.edges[0].node)


def test_an_unexposed_application_does_not() -> None:
    """The schema says an unexposed application gets no pool, no VIP and no
    advertisement. Holding a block would keep addresses out of the pool for
    something that cannot receive traffic."""
    assert not wants_a_block(_query(app=_app(exposed=False)).target.edges[0].node)


@pytest.mark.parametrize("status", ["decommissioning", "decommissioned"])
def test_a_decommissioned_application_does_not(status: str) -> None:
    assert not wants_a_block(_query(app=_app(status=status)).target.edges[0].node)


@pytest.mark.parametrize("status", ["provisioning", "active", "error"])
def test_every_other_status_still_wants_one(status: str) -> None:
    """`error` included: a failed run that is corrected must rebuild rather than
    needing its status reset by hand."""
    assert wants_a_block(_query(app=_app(status=status)).target.edges[0].node)


# ---------------------------------------------------------------------------
# generate() -- claims about calls rather than about state
# ---------------------------------------------------------------------------


@dataclass
class _RecordingAttribute:
    value: Any = None


class _RecordingNode:
    def __init__(self, node_id: str, **attributes: Any) -> None:
        self.id = node_id
        self.saves: list[dict[str, Any]] = []
        self.vip_block: Any = "unset"
        self.vip_block_managed = _RecordingAttribute(False)
        self.artifacts: list[str] = []
        for key, value in attributes.items():
            setattr(self, key, _RecordingAttribute(value))

    async def save(self, **kwargs: Any) -> None:
        # Recorded as a snapshot, so a test can tell what was true AT each save
        # rather than only at the end.
        self.saves.append({**kwargs, "vip_block": self.vip_block, "managed": self.vip_block_managed.value})

    async def artifact_generate(self, name: str) -> None:
        self.artifacts.append(name)


@dataclass
class _RecordingClient:
    allocations: list[dict[str, Any]] = field(default_factory=list)
    deleted: list[tuple[str, str]] = field(default_factory=list)
    nodes: dict[str, _RecordingNode] = field(default_factory=dict)
    allocated_prefix: str = "10.112.240.16/28"

    async def get(self, kind: str, id: str) -> Any:  # noqa: A002
        return self.nodes.setdefault(id, _RecordingNode(id))

    async def delete(self, kind: str, id: str) -> None:  # noqa: A002
        self.deleted.append((kind, id))

    async def allocate_next_ip_prefix(self, **kwargs: Any) -> Any:
        self.allocations.append(kwargs)
        return _RecordingNode("new-block", prefix=self.allocated_prefix)


def _generator(client: _RecordingClient) -> FabricAppGenerator:
    generator = FabricAppGenerator.__new__(FabricAppGenerator)
    generator._client = client  # type: ignore[attr-defined]
    generator._init_client = client  # type: ignore[attr-defined]
    generator.logger = logging.getLogger("test")
    return generator


@pytest.mark.asyncio
async def test_an_exposed_application_with_no_block_gets_one() -> None:
    client = _RecordingClient()
    await _generator(client).generate(_query(app=_app()).model_dump(by_alias=True))

    assert len(client.allocations) == 1
    assert client.allocations[0]["prefix_length"] == 28
    assert client.allocations[0]["data"]["role"] == "vip_pool"


@pytest.mark.asyncio
async def test_the_allocation_is_keyed_on_the_id_so_a_rename_keeps_its_block() -> None:
    client = _RecordingClient()
    await _generator(client).generate(_query(app=_app()).model_dump(by_alias=True))

    assert client.allocations[0]["identifier"] == "fabric-app-app-1"


@pytest.mark.asyncio
async def test_the_ownership_flag_is_written_with_the_block_not_after_it() -> None:
    """Two saves would leave a window in which the block exists and nothing
    records who owns it -- and a withdrawal landing in that window would decline
    to remove a block this generator had in fact allocated, leaking it."""
    client = _RecordingClient()
    await _generator(client).generate(_query(app=_app()).model_dump(by_alias=True))

    service = client.nodes["app-1"]
    assert len(service.saves) == 1
    assert service.saves[0]["vip_block"] == "new-block"
    assert service.saves[0]["managed"] is True


@pytest.mark.asyncio
async def test_an_application_that_already_has_a_block_keeps_it() -> None:
    """THE SEEDED APPLICATION'S PATH.

    nfd41-demo names 10.112.240.0/28, declared in objects/ and delivered into a
    live cluster. Reallocating it would move a manifest that is already applied.
    """
    client = _RecordingClient()
    parsed = _query(app=_app(block=(SEEDED_BLOCK_ID, SEEDED_BLOCK)))

    await _generator(client).generate(parsed.model_dump(by_alias=True))

    assert client.allocations == []
    assert client.deleted == []
    assert client.nodes == {}


@pytest.mark.asyncio
async def test_an_unexposed_application_loses_a_block_the_generator_allocated() -> None:
    client = _RecordingClient()
    parsed = _query(app=_app(exposed=False, block=("pfx-ours", "10.112.240.16/28"), managed=True))

    await _generator(client).generate(parsed.model_dump(by_alias=True))

    assert client.deleted == [("IpamPrefix", "pfx-ours")]


@pytest.mark.asyncio
async def test_withdrawal_clears_the_reference_before_deleting_the_prefix() -> None:
    """Deleting first leaves the service pointing at a prefix that no longer
    exists for as long as the second write takes, and a failure in between would
    leave it permanently."""
    client = _RecordingClient()
    parsed = _query(app=_app(exposed=False, block=("pfx-ours", "10.112.240.16/28"), managed=True))

    await _generator(client).generate(parsed.model_dump(by_alias=True))

    service = client.nodes["app-1"]
    assert service.saves[0]["vip_block"] is None
    assert service.saves[0]["managed"] is False
    assert client.deleted


@pytest.mark.asyncio
async def test_a_hand_written_block_survives_decommissioning() -> None:
    """THE REASON `vip_block_managed` EXISTS.

    nfd41-demo's block is declared in objects/29_nfd41_offfabric_prefixes.yml.
    Deleting it would remove an object the seed data owns and break the next
    `invoke load`.
    """
    client = _RecordingClient()
    parsed = _query(app=_app(status="decommissioned", block=(SEEDED_BLOCK_ID, SEEDED_BLOCK), managed=False))

    await _generator(client).generate(parsed.model_dump(by_alias=True))

    assert client.deleted == []
    assert client.nodes == {}


@pytest.mark.asyncio
async def test_withdrawing_from_an_application_with_no_block_does_nothing() -> None:
    client = _RecordingClient()
    parsed = _query(app=_app(exposed=False))

    await _generator(client).generate(parsed.model_dump(by_alias=True))

    assert client.deleted == []
    assert client.allocations == []


@pytest.mark.asyncio
async def test_the_manifest_is_rerendered_after_an_allocation() -> None:
    """The block only reaches the cluster through the artifact."""
    client = _RecordingClient()
    await _generator(client).generate(_query(app=_app()).model_dump(by_alias=True))

    assert client.nodes["app-1"].artifacts == ["Crossplane FabricApp"]
