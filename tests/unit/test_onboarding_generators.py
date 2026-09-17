"""Unit tests for the two onboarding generators.

Fixtures built from the lab's real shapes: four EVPN tenants at VNI bases
11000, 12000, 13000 and 15000 -- note the gap at 14000 -- and the racks and
machines `objects/25_nfd41_racks.yml` and `objects/28_nfd41_endpoints.yml`
declare.

**The claim most of this file exists to protect is the VNI derivation.** Every
tenant's L2VLAN VNIs are allocated upward from its base, so two tenants whose
bases are close share VNIs and the fabric bridges them together. Nothing errors
on that path, which is why the spacing is asserted rather than assumed -- and
why `mac_vrf_vni_base` is not drawn from a `CoreNumberPool`, which would hand
out consecutive integers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pytest

from generators.generate_server_placement import (
    ServerPlacementGenerator,
)
from generators.generate_server_placement import (
    adopted_id as placement_adopted_id,
)
from generators.generate_server_placement import validate_model as validate_placement
from generators.generate_server_placement_query import GenerateServerPlacementQuery
from generators.generate_tenant_onboarding import (
    VNI_SPACING,
    TenantOnboardingGenerator,
    evpn_tenant_name,
    next_vni_base,
    taken_bases,
)
from generators.generate_tenant_onboarding import validate_model as validate_onboarding
from generators.generate_tenant_onboarding_query import GenerateTenantOnboardingQuery

LAB_BASES = {"TENANT_K8S": 11000, "TENANT_APP": 12000, "TENANT_CLOUD": 13000, "TENANT_EXTERNAL": 15000}


def _wrap(value: Any) -> dict[str, Any]:
    return {"value": value}


def _rel(node_id: str | None, name: str | None = None, **extra: Any) -> dict[str, Any]:
    if node_id is None:
        return {"node": None}
    node: dict[str, Any] = {"id": node_id}
    if name is not None:
        node["name"] = _wrap(name)
    node.update(extra)
    return {"node": node}


# ---------------------------------------------------------------------------
# Tenant onboarding
# ---------------------------------------------------------------------------


def _tenants(bases: dict[str, int] | None = None) -> dict[str, Any]:
    entries = LAB_BASES if bases is None else bases
    return {
        "edges": [
            {"node": {"id": f"evpn-{name}", "name": _wrap(name), "mac_vrf_vni_base": _wrap(base)}}
            for name, base in entries.items()
        ]
    }


def _onboarding(
    *,
    organization: str | None = "platform",
    status: str = "provisioning",
    base: int | None = None,
    built: tuple[str, str, int] | None = None,
    fabric: bool = True,
) -> dict[str, Any]:
    return {
        "node": {
            "id": "onb-1",
            "name": _wrap("onboard-platform"),
            "description": _wrap("platform tenant"),
            "status": _wrap(status),
            "mac_vrf_vni_base": _wrap(base),
            "organization": _rel("org-platform", organization) if organization else {"node": None},
            "fabric": _rel("fabric-nfd41", "NFD41_FABRIC") if fabric else {"node": None},
            "evpn_tenant": (
                {"node": {"id": built[0], "name": _wrap(built[1]), "mac_vrf_vni_base": _wrap(built[2])}}
                if built
                else {"node": None}
            ),
        }
    }


def _onboarding_query(
    onboarding: dict[str, Any] | None = None, tenants: dict[str, Any] | None = None
) -> GenerateTenantOnboardingQuery:
    return GenerateTenantOnboardingQuery(
        target={"edges": [onboarding if onboarding is not None else _onboarding()]},
        EvpnTenant=tenants if tenants is not None else _tenants(),
    )


def test_the_next_base_fills_the_gap_the_lab_leaves() -> None:
    """14000 is free between TENANT_CLOUD and TENANT_EXTERNAL.

    Filling it rather than appending at 16000 is what stops the numbering
    drifting upward forever as tenants come and go.
    """
    assert next_vni_base(set(LAB_BASES.values())) == 14000


def test_the_first_tenant_starts_at_the_floor() -> None:
    assert next_vni_base(set()) == 11000


def test_consecutive_derivations_are_spaced_not_adjacent() -> None:
    """THE FAILURE A NUMBER POOL WOULD CAUSE.

    A CoreNumberPool would hand out 16000 and 16001, and the two tenants' VNI
    ranges would overlap completely while every object looked correct.
    """
    taken = set(LAB_BASES.values())
    first = next_vni_base(taken)
    second = next_vni_base(taken | {first})
    assert second - first >= VNI_SPACING


def test_bases_are_read_from_the_graph() -> None:
    assert taken_bases(_onboarding_query()) == set(LAB_BASES.values())


def test_a_tenant_with_no_base_is_ignored_rather_than_counted_as_zero() -> None:
    parsed = _onboarding_query(
        tenants={"edges": [{"node": {"id": "t", "name": _wrap("T"), "mac_vrf_vni_base": _wrap(None)}}]}
    )
    assert taken_bases(parsed) == set()


@pytest.mark.parametrize(
    ("organization", "expected"),
    [("acme", "TENANT_ACME"), ("platform-team", "TENANT_PLATFORM_TEAM"), ("globex", "TENANT_GLOBEX")],
)
def test_the_evpn_tenant_name_matches_the_labs_convention(organization: str, expected: str) -> None:
    """Every VRF and route target in this lab already references names of this
    shape, so a generated tenant has to look like the hand-written ones."""
    assert evpn_tenant_name(organization) == expected


def test_a_stated_base_is_honoured() -> None:
    assert validate_onboarding(_onboarding_query(_onboarding(base=20000))).vni_base == 20000


def test_a_rebuild_keeps_the_base_it_already_has() -> None:
    """Re-deriving could move it, and every VNI beneath it with it."""
    context = validate_onboarding(_onboarding_query(_onboarding(built=("evpn-x", "TENANT_PLATFORM", 14000))))
    assert context.vni_base == 14000


def test_a_name_collision_with_a_lab_tenant_is_refused() -> None:
    """A request for `k8s` would upsert onto TENANT_K8S and then delete it on
    decommissioning."""
    with pytest.raises(ValueError, match="adopt"):
        validate_onboarding(_onboarding_query(_onboarding(organization="k8s")))


@pytest.mark.parametrize("missing", ["organization", "fabric"])
def test_an_incomplete_request_is_refused(missing: str) -> None:
    kwargs: dict[str, Any] = {"organization": None} if missing == "organization" else {"fabric": False}
    with pytest.raises(ValueError, match=missing):
        validate_onboarding(_onboarding_query(_onboarding(**kwargs)))


# ---------------------------------------------------------------------------
# Server placement
# ---------------------------------------------------------------------------


def _placement(
    *,
    hostname: str | None = "host-new",
    status: str = "provisioning",
    rack: bool = True,
    template: bool = True,
    built: tuple[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "node": {
            "id": "plc-1",
            "name": _wrap("place-host-new"),
            "description": _wrap("a new workload host"),
            "status": _wrap(status),
            "hostname": _wrap(hostname),
            "server_role": _wrap("compute"),
            "rack": _rel("rack-app", "APP_LEAFS") if rack else {"node": None},
            "template": (
                {
                    "node": {
                        "__typename": "CoreObjectTemplate",
                        "id": "tpl-workload",
                        "template_name": _wrap("nfd41-workload-host"),
                    }
                }
                if template
                else {"node": None}
            ),
            "tenant": _rel("org-acme", "acme"),
            "server": _rel(built[0], built[1]) if built else {"node": None},
        }
    }


def _servers(*names: str) -> dict[str, Any]:
    return {"edges": [{"node": {"id": f"srv-{n}", "name": _wrap(n)}} for n in names]}


def _placement_query(
    placement: dict[str, Any] | None = None, servers: dict[str, Any] | None = None
) -> GenerateServerPlacementQuery:
    return GenerateServerPlacementQuery(
        target={"edges": [placement if placement is not None else _placement()]},
        ComputePhysicalServer=servers if servers is not None else _servers("k8s-node1", "k8s-node2", "host-a"),
    )


def test_a_complete_placement_validates() -> None:
    context = validate_placement(_placement_query())
    assert context.hostname == "host-new"
    assert context.rack_id == "rack-app"
    assert context.template_id == "tpl-workload"


def test_a_placement_with_no_rack_is_refused() -> None:
    """generate-server-cabling finds leaves in the server's RACK, so a machine
    without one is cabled to nothing and reports success."""
    with pytest.raises(ValueError, match="cabled to nothing"):
        validate_placement(_placement_query(_placement(rack=False)))


def test_a_placement_with_no_template_is_refused() -> None:
    """The template supplies the interfaces, and cabling cables interfaces. A
    machine without one makes the cabling generator log "has no interfaces" and
    return, which reads exactly like a broken generator."""
    with pytest.raises(ValueError, match="nothing to cable"):
        validate_placement(_placement_query(_placement(template=False)))


def test_a_hostname_collision_with_a_running_machine_is_refused() -> None:
    """Upserting onto k8s-node1 would hand this request ownership of a running
    Kubernetes node, and decommissioning it would delete the node."""
    with pytest.raises(ValueError, match="another hostname"):
        validate_placement(_placement_query(_placement(hostname="k8s-node1")))


def test_our_own_earlier_machine_is_adopted_rather_than_refused() -> None:
    """It must be written AGAIN every run: returning its id without touching it
    leaves it outside the tracking group, and delete_unused_nodes then removes
    the machine the service still points at."""

    @dataclass
    class _Wrapped:
        value: Any

    @dataclass
    class _Existing:
        id: str
        name: Any

    existing = [_Existing("srv-mine", _Wrapped("host-new"))]
    assert placement_adopted_id(existing, "host-new", "srv-mine") == "srv-mine"


# ---------------------------------------------------------------------------
# generate() -- claims about calls
# ---------------------------------------------------------------------------


@dataclass
class _Attr:
    value: Any = None


class _Node:
    def __init__(self, node_id: str, **attrs: Any) -> None:
        self.id = node_id
        self.saves: list[dict[str, Any]] = []
        self.status = _Attr("provisioning")
        self.mac_vrf_vni_base = _Attr(None)
        self.evpn_tenant: Any = "unset"
        self.server: Any = "unset"
        for k, v in attrs.items():
            setattr(self, k, _Attr(v))

    async def save(self, **kwargs: Any) -> None:
        self.saves.append(kwargs)


@dataclass
class _Client:
    created: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    deleted: list[tuple[str, str]] = field(default_factory=list)
    nodes: dict[str, _Node] = field(default_factory=dict)

    async def create(self, kind: str, data: dict[str, Any]) -> Any:
        self.created.append((kind, data))
        return _Node(f"new-{kind}")

    async def get(self, kind: str, id: str, **_kwargs: Any) -> Any:  # noqa: A002
        return self.nodes.setdefault(id, _Node(id))

    async def delete(self, kind: str, id: str) -> None:  # noqa: A002
        self.deleted.append((kind, id))


def _gen(cls: Any, client: _Client) -> Any:
    generator = cls.__new__(cls)
    generator._client = client
    generator._init_client = client
    generator.logger = logging.getLogger("test")
    return generator


@pytest.mark.asyncio
async def test_onboarding_creates_the_evpn_tenant_with_the_derived_base() -> None:
    client = _Client()
    await _gen(TenantOnboardingGenerator, client).generate(_onboarding_query().model_dump(by_alias=True))

    kind, data = client.created[0]
    assert kind == "EvpnTenant"
    assert data["name"] == "TENANT_PLATFORM"
    assert data["mac_vrf_vni_base"] == 14000


@pytest.mark.asyncio
async def test_placement_joins_the_group_the_cabling_generator_targets() -> None:
    """Without this the machine is created and never cabled, and nothing says
    so."""
    client = _Client()
    await _gen(ServerPlacementGenerator, client).generate(_placement_query().model_dump(by_alias=True))

    kind, data = client.created[0]
    assert kind == "ComputePhysicalServer"
    assert data["member_of_groups"] == ["servers"]
    assert data["object_template"] == "tpl-workload"


@pytest.mark.asyncio
async def test_placement_passes_the_template_on_every_run_not_only_creation() -> None:
    """An upsert omitting it would leave a re-created machine bare."""
    client = _Client()
    parsed = _placement_query(_placement(built=("srv-mine", "host-new")), servers=_servers("host-new"))
    # The recorded machine is ours, so this is the adoption path.
    parsed.target.edges[0].node.server.node.id = "srv-host-new"  # type: ignore[union-attr]
    await _gen(ServerPlacementGenerator, client).generate(parsed.model_dump(by_alias=True))

    _, data = client.created[0]
    assert data["object_template"] == "tpl-workload"


@pytest.mark.asyncio
async def test_decommissioning_a_placement_deletes_the_machine_it_made() -> None:
    client = _Client()
    parsed = _placement_query(_placement(status="decommissioning", built=("srv-mine", "host-new")))
    await _gen(ServerPlacementGenerator, client).generate(parsed.model_dump(by_alias=True))

    assert client.deleted == [("ComputePhysicalServer", "srv-mine")]


@pytest.mark.asyncio
async def test_decommissioning_a_placement_that_built_nothing_deletes_nothing() -> None:
    client = _Client()
    parsed = _placement_query(_placement(status="decommissioned"))
    await _gen(ServerPlacementGenerator, client).generate(parsed.model_dump(by_alias=True))

    assert client.deleted == []
