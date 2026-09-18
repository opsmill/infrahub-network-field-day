"""Unit tests for the network segment generator.

Fixtures rather than a live server, built from the real shapes in
``objects/21_otternet_pools.yml`` and ``objects/24_otternet_tenants.yml``: one prefix
pool whose supernet carries ``tenant_host``, one number pool allocating
``IpamVLAN.vlan_id``, and one ``OTTERNET-L2Domain``. Invented fixtures would pass
while missing what the defaults are actually resolved from.

**The claim most of this file exists to hold is that a segment lands
somewhere.** Measured on a branch before any of this was written: an SVI with no
tags rendered on zero switches, and the same SVI tagged ``k8s`` rendered on
exactly the two K8S leaves -- because AVD matches ``svis[].tags`` against a
node group's ``filter.tags``, and `EvpnSvi.rack_tags` contributes the rack's
NAME, which matches nothing. Nothing errors on the way through, so the only
place that failure can be caught is here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pytest

from generators.generate_network_segment import (
    NetworkSegmentGenerator,
    adopted_id,
    gateway_address,
    is_withdrawn,
    resolve_l2domain,
    resolve_subnet_pool,
    resolve_vlan_pool,
    validate_model,
)
from generators.generate_network_segment_query import GenerateNetworkSegmentQuery

SEGMENT_NAME = "PLATFORM_HOSTS"
SUBNET_POOL_ID = "pool-subnet"
VLAN_POOL_ID = "pool-vlan"
L2DOMAIN_ID = "l2-otternet"
VRF_ID = "vrf-k8s-prod"
TAG_K8S = "tag-k8s"


def _wrap(value: Any) -> dict[str, Any] | None:
    return {"value": value}


def _named(node_id: str, name: str) -> dict[str, Any]:
    return {"node": {"id": node_id, "name": _wrap(name)}}


def _segment(
    *,
    status: str = "provisioning",
    vlan_id: int | None = None,
    prefix_length: int | None = 24,
    avd_tags: list[str] | None = None,
    subnet_pool: str | None = None,
    vlan_pool: str | None = None,
    subnet: tuple[str, str] | None = None,
    vlan: tuple[str, int] | None = None,
    svi: str | None = None,
    vrf: str | None = VRF_ID,
) -> dict[str, Any]:
    tags = [TAG_K8S] if avd_tags is None else avd_tags
    return {
        "node": {
            "id": "seg-1",
            "name": _wrap(SEGMENT_NAME),
            "description": _wrap("platform hosts"),
            "status": _wrap(status),
            "vlan_id": _wrap(vlan_id),
            "prefix_length": _wrap(prefix_length),
            "tenant": _named("tenant-platform", "PLATFORM"),
            "vrf": _named(vrf, "K8S_PROD") if vrf else {"node": None},
            "fabric": _named("fabric-otternet", "OTTERNET_FABRIC"),
            "avd_tags": {"edges": [{"node": {"id": tag, "name": _wrap(tag.removeprefix("tag-"))}} for tag in tags]},
            "subnet_pool": _named(subnet_pool, "named-subnet-pool") if subnet_pool else {"node": None},
            "vlan_pool": _named(vlan_pool, "named-vlan-pool") if vlan_pool else {"node": None},
            "subnet": ({"node": {"id": subnet[0], "prefix": _wrap(subnet[1])}} if subnet else {"node": None}),
            "vlan": (
                {"node": {"id": vlan[0], "name": _wrap(SEGMENT_NAME), "vlan_id": _wrap(vlan[1])}}
                if vlan
                else {"node": None}
            ),
            "svi": (
                {"node": {"id": svi, "name": _wrap(SEGMENT_NAME), "svi_id": _wrap(500)}} if svi else {"node": None}
            ),
        }
    }


def _prefix_pools(*, role: str = "tenant_host", extra_with_role: bool = False) -> dict[str, Any]:
    """The lab's four prefix pools. Only the supernet carries ``tenant_host``."""
    pools = [
        ("pool-loopback", "OTTERNET-Loopback-Pool", "loopback"),
        (SUBNET_POOL_ID, "OTTERNET-Segment-Subnet-Pool", role),
        ("pool-uplink", "OTTERNET-Uplink-Pool", "fabric_point_to_point"),
        ("pool-vtep", "OTTERNET-VTEP-Pool", "loopback-vtep"),
    ]
    if extra_with_role:
        pools.append(("pool-second", "Second-Segment-Pool", "tenant_host"))
    return {
        "edges": [
            {
                "node": {
                    "id": pool_id,
                    "name": _wrap(name),
                    "resources": {
                        "edges": [{"node": {"__typename": "IpamPrefix", "id": f"pfx-{pool_id}", "role": _wrap(value)}}]
                    },
                }
            }
            for pool_id, name, value in pools
        ]
    }


def _number_pools(*, node: str = "IpamVLAN") -> dict[str, Any]:
    pools = [
        ("pool-asn", "OTTERNET-ASN-Pool", "RoutingAsn", "asn"),
        ("pool-nodeid", "OTTERNET-NodeID-Pool", "DcimFabricSwitch", "node_id"),
        (VLAN_POOL_ID, "OTTERNET-Segment-VLAN-Pool", node, "vlan_id"),
    ]
    return {
        "edges": [
            {
                "node": {
                    "id": pool_id,
                    "name": _wrap(name),
                    "node": _wrap(kind),
                    "node_attribute": _wrap(attribute),
                }
            }
            for pool_id, name, kind, attribute in pools
        ]
    }


def _query(
    *,
    segment: dict[str, Any] | None = None,
    prefix_pools: dict[str, Any] | None = None,
    number_pools: dict[str, Any] | None = None,
    l2domains: list[str] | None = None,
    existing_vlan: list[dict[str, Any]] | None = None,
    existing_svi: list[dict[str, Any]] | None = None,
) -> GenerateNetworkSegmentQuery:
    domains = [L2DOMAIN_ID] if l2domains is None else l2domains
    return GenerateNetworkSegmentQuery(
        target={"edges": [segment if segment is not None else _segment()]},
        existing_vlan={"edges": existing_vlan or []},
        existing_svi={"edges": existing_svi or []},
        CoreIPPrefixPool=prefix_pools if prefix_pools is not None else _prefix_pools(),
        CoreNumberPool=number_pools if number_pools is not None else _number_pools(),
        IpamL2Domain={"edges": [{"node": {"id": d, "name": _wrap("OTTERNET-L2Domain")}} for d in domains]},
    )


# ---------------------------------------------------------------------------
# Resolving the defaults, which is what a request deliberately does not state
# ---------------------------------------------------------------------------


def test_the_subnet_pool_is_found_by_role_not_by_name() -> None:
    """A hard-coded pool name would tie this generator to one lab's object
    files. `tenant_host` is a statement about what the pool is for."""
    parsed = _query()
    assert resolve_subnet_pool(parsed, parsed.target.edges[0].node) == SUBNET_POOL_ID


def test_a_named_subnet_pool_beats_the_default() -> None:
    parsed = _query(segment=_segment(subnet_pool="pool-explicit"))
    assert resolve_subnet_pool(parsed, parsed.target.edges[0].node) == "pool-explicit"


def test_no_pool_carrying_the_role_is_refused_with_the_remedy() -> None:
    """The message has to name the way out. "No pool found" sends the reader to
    the pool file; the fix is usually on the segment."""
    parsed = _query(prefix_pools=_prefix_pools(role="loopback"))
    with pytest.raises(ValueError, match="subnet_pool"):
        resolve_subnet_pool(parsed, parsed.target.edges[0].node)


def test_two_pools_carrying_the_role_are_refused_rather_than_guessed() -> None:
    parsed = _query(prefix_pools=_prefix_pools(extra_with_role=True))
    with pytest.raises(ValueError, match="found 2"):
        resolve_subnet_pool(parsed, parsed.target.edges[0].node)


def test_the_vlan_pool_is_the_one_allocating_vlan_ids() -> None:
    """Identified by what it allocates, so the ASN and node-id pools beside it
    are never candidates however they are named."""
    parsed = _query()
    assert resolve_vlan_pool(parsed, parsed.target.edges[0].node) == VLAN_POOL_ID


def test_a_pool_allocating_another_kind_is_not_the_vlan_pool() -> None:
    parsed = _query(number_pools=_number_pools(node="IpamVRF"))
    with pytest.raises(ValueError, match="vlan_pool"):
        resolve_vlan_pool(parsed, parsed.target.edges[0].node)


def test_several_l2_domains_are_refused_rather_than_picked() -> None:
    """`IpamVLAN.l2domain` is mandatory and the request names none, so one
    domain is resolvable and two are a question only the schema can answer."""
    with pytest.raises(ValueError, match="IpamL2Domain"):
        resolve_l2domain(_query(l2domains=["a", "b"]))


# ---------------------------------------------------------------------------
# The failure that renders nothing and reports nothing
# ---------------------------------------------------------------------------


def test_a_segment_with_no_avd_tags_is_refused() -> None:
    """The regression test for the measured defect.

    An SVI whose tags match no node group's filter renders on no switch. The
    artifact is produced, reports Ready, and simply lacks the interface -- so
    the request has to be refused here or the failure is invisible.
    """
    with pytest.raises(ValueError, match="render on no switch"):
        validate_model(_query(segment=_segment(avd_tags=[])))


def test_a_segment_with_a_tag_validates() -> None:
    context = validate_model(_query())
    assert context.avd_tag_ids == [TAG_K8S]
    assert context.subnet_pool_id == SUBNET_POOL_ID
    assert context.vlan_pool_id == VLAN_POOL_ID
    assert context.l2domain_id == L2DOMAIN_ID


def test_a_segment_with_no_vrf_is_refused() -> None:
    with pytest.raises(ValueError, match="no VRF"):
        validate_model(_query(segment=_segment(vrf=None)))


# ---------------------------------------------------------------------------
# Adoption versus collision
# ---------------------------------------------------------------------------


def test_nothing_carrying_the_name_is_the_normal_first_run() -> None:
    assert adopted_id([], None) is None


def test_an_object_the_service_records_is_our_own_earlier_output() -> None:
    """It must be written AGAIN every run. Returning its id without touching it
    leaves it outside this run's tracking group, and `delete_unused_nodes`
    then deletes it -- the bug `generate-app-access` shipped once."""

    @dataclass
    class _Node:
        id: str

    assert adopted_id([_Node("vlan-1")], "vlan-1") == "vlan-1"


def test_an_object_the_service_does_not_record_is_a_collision() -> None:
    """A segment named K8S_NODES must not quietly take ownership of the lab's
    hand-written VLAN -- because decommissioning it would then delete it."""

    @dataclass
    class _Node:
        id: str

    with pytest.raises(ValueError, match="adopt"):
        adopted_id([_Node("vlan-handwritten")], None)


# ---------------------------------------------------------------------------
# The gateway
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        ("10.230.0.0/24", "10.230.0.1/24"),
        ("10.230.4.0/22", "10.230.4.1/22"),
        ("10.230.0.0/30", "10.230.0.1/30"),
    ],
)
def test_the_gateway_is_the_first_usable_address(prefix: str, expected: str) -> None:
    """What every hand-written segment in this lab uses, and what
    `EvpnSvi.ip_address_virtual` expects -- host notation, not a bare address."""
    assert gateway_address(prefix) == expected


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
        self.status = _RecordingAttribute("provisioning")
        self.subnet: Any = None
        self.vlan: Any = None
        self.svi: Any = None
        for key, value in attributes.items():
            setattr(self, key, _RecordingAttribute(value))

    async def save(self, **kwargs: Any) -> None:
        self.saves.append(kwargs)


@dataclass
class _RecordingClient:
    """Enough client to prove what was and was not written."""

    created: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    deleted: list[tuple[str, str]] = field(default_factory=list)
    allocations: list[dict[str, Any]] = field(default_factory=list)
    nodes: dict[str, _RecordingNode] = field(default_factory=dict)
    allocated_prefix: str = "10.230.0.0/24"
    allocated_vlan: int = 500

    async def create(self, kind: str, data: dict[str, Any]) -> Any:
        self.created.append((kind, data))
        number = data.get("vlan_id")
        if isinstance(number, dict) or kind != "IpamVLAN":
            number = self.allocated_vlan
        return _RecordingNode(f"new-{kind}-{len(self.created)}", vlan_id=number)

    async def get(self, kind: str, id: str) -> Any:  # noqa: A002
        return self.nodes.setdefault(id, _RecordingNode(id))

    async def delete(self, kind: str, id: str) -> None:  # noqa: A002
        self.deleted.append((kind, id))

    async def allocate_next_ip_prefix(self, **kwargs: Any) -> Any:
        self.allocations.append(kwargs)
        return _RecordingNode("new-prefix", prefix=self.allocated_prefix)


def _generator(client: _RecordingClient) -> NetworkSegmentGenerator:
    generator = NetworkSegmentGenerator.__new__(NetworkSegmentGenerator)
    generator._client = client  # type: ignore[attr-defined]
    generator._init_client = client  # type: ignore[attr-defined]
    generator.logger = logging.getLogger("test")
    return generator


@pytest.mark.asyncio
async def test_a_request_builds_a_subnet_a_vlan_and_a_gateway() -> None:
    client = _RecordingClient()
    await _generator(client).generate(_query().model_dump(by_alias=True))

    assert [kind for kind, _ in client.created] == ["IpamVLAN", "EvpnSvi"]
    assert len(client.allocations) == 1


@pytest.mark.asyncio
async def test_the_allocation_is_keyed_on_the_id_so_a_rename_keeps_its_subnet() -> None:
    """Keyed on the name, a rename would allocate a second subnet and orphan
    the first while the service went on reporting active."""
    client = _RecordingClient()
    await _generator(client).generate(_query().model_dump(by_alias=True))

    assert client.allocations[0]["identifier"] == "segment-seg-1"


@pytest.mark.asyncio
async def test_the_svi_carries_the_tags_and_the_gateway() -> None:
    client = _RecordingClient()
    await _generator(client).generate(_query().model_dump(by_alias=True))

    _, svi = next((kind, data) for kind, data in client.created if kind == "EvpnSvi")
    assert svi["avd_tags"] == [TAG_K8S]
    assert svi["ip_address_virtual"] == "10.230.0.1/24"
    # The uniqueness constraint is [vrf, svi_id], so two segments in one VRF
    # cannot share a VLAN id and the constraint says so rather than this
    # generator having to remember.
    assert svi["svi_id"] == 500


@pytest.mark.asyncio
async def test_a_stated_vlan_id_is_honoured_rather_than_allocated() -> None:
    client = _RecordingClient()
    await _generator(client).generate(_query(segment=_segment(vlan_id=777)).model_dump(by_alias=True))

    _, vlan = next((kind, data) for kind, data in client.created if kind == "IpamVLAN")
    assert vlan["vlan_id"] == 777


@pytest.mark.asyncio
async def test_a_rerun_reuses_its_vlan_rather_than_asking_the_pool_again() -> None:
    """`from_pool` on a re-run would ask for a second number for a VLAN that
    already has one."""
    client = _RecordingClient()
    segment = _segment(subnet=("pfx-1", "10.230.0.0/24"), vlan=("vlan-1", 500), svi="svi-1")
    parsed = _query(
        segment=segment,
        existing_vlan=[{"node": {"id": "vlan-1", "vlan_id": _wrap(500)}}],
        existing_svi=[{"node": {"id": "svi-1", "svi_id": _wrap(500)}}],
    )
    await _generator(client).generate(parsed.model_dump(by_alias=True))

    _, vlan = next((kind, data) for kind, data in client.created if kind == "IpamVLAN")
    assert vlan["vlan_id"] == 500
    assert vlan["id"] == "vlan-1"
    # And no second subnet: the recorded one is reused.
    assert client.allocations == []


@pytest.mark.asyncio
async def test_a_rerun_writes_its_own_objects_again() -> None:
    """Not an optimisation to skip. An object left out of this run's tracking
    group is deleted by `delete_unused_nodes` while the service still points at
    it."""
    client = _RecordingClient()
    parsed = _query(
        segment=_segment(subnet=("pfx-1", "10.230.0.0/24"), vlan=("vlan-1", 500), svi="svi-1"),
        existing_vlan=[{"node": {"id": "vlan-1", "vlan_id": _wrap(500)}}],
        existing_svi=[{"node": {"id": "svi-1", "svi_id": _wrap(500)}}],
    )
    await _generator(client).generate(parsed.model_dump(by_alias=True))

    assert [kind for kind, _ in client.created] == ["IpamVLAN", "EvpnSvi"]


@pytest.mark.asyncio
async def test_a_collision_refuses_before_anything_is_written() -> None:
    """A VLAN wearing the requested name that the service does not record."""
    client = _RecordingClient()
    parsed = _query(existing_vlan=[{"node": {"id": "vlan-handwritten", "vlan_id": _wrap(110)}}])

    with pytest.raises(ValueError, match="adopt"):
        await _generator(client).generate(parsed.model_dump(by_alias=True))

    assert [kind for kind, _ in client.created] == []


# ---------------------------------------------------------------------------
# Withdrawal, which the tracking context does not cover
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["decommissioning", "decommissioned"])
def test_the_two_statuses_that_mean_take_it_away(status: str) -> None:
    parsed = _query(segment=_segment(status=status))
    assert is_withdrawn(parsed.target.edges[0].node)


@pytest.mark.parametrize("status", ["provisioning", "active", "error"])
def test_every_other_status_builds(status: str) -> None:
    """`error` included: a failed run that is corrected must rebuild rather
    than needing its status reset by hand."""
    parsed = _query(segment=_segment(status=status))
    assert not is_withdrawn(parsed.target.edges[0].node)


@pytest.mark.asyncio
async def test_decommissioning_deletes_in_reference_order() -> None:
    """The SVI points at the VLAN and the VLAN at the prefix, so the order is
    fixed. Deleting the prefix last is also what returns the subnet to its
    pool."""
    client = _RecordingClient()
    segment = _segment(
        status="decommissioning",
        subnet=("pfx-1", "10.230.0.0/24"),
        vlan=("vlan-1", 500),
        svi="svi-1",
    )
    await _generator(client).generate(_query(segment=segment).model_dump(by_alias=True))

    assert client.deleted == [("EvpnSvi", "svi-1"), ("IpamVLAN", "vlan-1"), ("IpamPrefix", "pfx-1")]
    assert client.created == []


@pytest.mark.asyncio
async def test_decommissioning_deletes_only_what_the_service_records() -> None:
    """An object that merely shares the name was refused at build time and is
    not this generator's to remove."""
    client = _RecordingClient()
    parsed = _query(
        segment=_segment(status="decommissioning"),
        existing_vlan=[{"node": {"id": "vlan-handwritten", "vlan_id": _wrap(110)}}],
        existing_svi=[{"node": {"id": "svi-handwritten", "svi_id": _wrap(110)}}],
    )
    await _generator(client).generate(parsed.model_dump(by_alias=True))

    assert client.deleted == []
