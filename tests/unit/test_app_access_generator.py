"""Unit tests for the application access grant generator.

Fixtures rather than a live server, and the fixtures are built from the real
shapes in ``objects/32_nfd41_security.yml`` -- six zones, one
``nfd41-perimeter`` policy, the four service objects the firewall declares, and
the address book's ``book_index`` values 10 to 130. Fixtures invented from
scratch would pass while missing the two cases that actually matter: adopting
``junos-https`` for port 443, and leaving the pinned address-book order alone.

The derivation is a set of module-level pure functions over the parsed query
response, so most of what follows runs without a client at all. The tests that
exercise ``generate()`` use a recording fake, because "wrote nothing" is a claim
about calls rather than about state.

The last section asserts the seed data instead, and it is the one that guards
something the rest cannot see: ``tests/unit/test_junos_config.py`` holds the
rendered artifact byte-for-byte, but it reads a captured fixture, so approving
the seeded grant would break the real artifact without failing that test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from generators.generate_app_access import (
    BOOK_INDEX_FLOOR,
    RULE_INDEX_FLOOR,
    AppAccessGenerator,
    GrantContext,
    derive_destination_zone,
    derive_policy,
    derive_tcp_protocol,
    index_address_book,
    index_tcp_services,
    is_approved,
    normalise_ports,
    validate_model,
)
from generators.generate_app_access_query import GenerateAppAccessQuery

# ---------------------------------------------------------------------------
# The lab, as loaded. Changing any of these means the lab changed, not the
# generator.
# ---------------------------------------------------------------------------

GRANT = "branch-to-nfd41-demo"
APP = "nfd41-demo"
VIP_ID = "ip-10.112.240.10"

# Zone name -> the IpamVRF it hands off to. SecurityZone.vrf is how the
# destination zone is derived; the firewall's /30 handoff interfaces contain no
# VIP, so containment cannot be used (research R2).
ZONE_VRFS = {
    "k8s-prod": "vrf-K8S_PROD",
    "app-prod": "vrf-APP_PROD",
    "acme-cloud": "vrf-TENANT_ACME",
    "globex-cloud": "vrf-TENANT_GLOBEX",
    "branch": "vrf-BRANCH",
    "wan": "vrf-WAN",
}

# The firewall's own applications stanza. A grant for 80 or 443 must adopt
# these rather than declare a second application for the same port.
FIREWALL_SERVICES = [
    ("junos-http", 80, "tcp"),
    ("junos-https", 443, "tcp"),
    ("junos-ping", 0, "icmp"),
    ("any", 0, "tcp"),
]

# The address book's pinned order, asserted byte-for-byte by
# tests/unit/test_junos_config.py. Nothing generated may land inside it.
HAND_WRITTEN_BOOK_INDEXES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 130]

# The hand-written rules occupy only these three indexes, in every zone pair,
# with the anti-spoofing deny first.
BASELINE_RULE_INDEXES = (10, 20, 30)


# A sentinel, because `None` and `[]` are both meaningful values here: they are
# the empty-ports case the generator must reject rather than read as "all".
_UNSET = object()


def _grant(
    *,
    approved: bool = True,
    ports: Any = _UNSET,
    app_vrf: str | None = "vrf-K8S_PROD",
    source_zone: str | None = "branch",
    vip_id: str | None = VIP_ID,
    granted_rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    """One ServiceAppAccess as GraphQL returns it.

    Note the shape of an absent relationship: ``{"node": None}``, never a bare
    ``None``. That is what Infrahub returns and what the generated models
    enforce.
    """
    resolved_ports = [8080] if ports is _UNSET else ports
    return {
        "node": {
            "id": f"grant-{GRANT}",
            "name": {"value": GRANT},
            "status": {"value": "provisioning"},
            "approved": {"value": approved},
            "requester": {"value": "branch-office-user"},
            "justification": {"value": "verify reachability"},
            "ports": {"value": resolved_ports},
            "application": {
                "node": {
                    "id": f"app-{APP}",
                    "name": {"value": APP},
                    "vrf": ({"node": {"id": app_vrf, "name": {"value": "K8S_PROD"}}} if app_vrf else {"node": None}),
                }
            },
            "source_zone": (
                {"node": {"id": f"zone-{source_zone}", "name": {"value": source_zone}}}
                if source_zone
                else {"node": None}
            ),
            "source_address": (
                {
                    "node": {
                        "__typename": "SecurityIPAMIPPrefix",
                        "id": "addr-branch-users",
                        "display_label": "branch-users",
                    }
                }
            ),
            "destination_vip": (
                {"node": {"id": vip_id, "address": {"value": "10.112.240.10/32"}}} if vip_id else {"node": None}
            ),
            "granted_rules": {
                "edges": [{"node": {"id": rid, "name": {"value": rid}}} for rid in (granted_rule_ids or [])]
            },
        }
    }


def _address_book(*, vip_entry_for: str | None = None, ours: bool = False) -> dict[str, Any]:
    """The book. ``vip_entry_for`` adds an entry already wrapping that address.

    ``access-portal`` is the hand-written instance of exactly that shape, which
    is why adoption is keyed on the wrapped address rather than on a name.
    """
    edges = [
        {
            "node": {
                "__typename": "SecurityIPAMIPPrefix",
                "id": f"addr-book-{index}",
                "name": {"value": f"entry-{index}"},
                "book_index": {"value": index},
            }
        }
        for index in HAND_WRITTEN_BOOK_INDEXES
    ]
    # `any` is a Junos keyword: referenced by rules, declared in no book, and
    # carrying no book_index. It must survive index_address_book untouched.
    edges.extend(
        [
            {
                "node": {
                    "__typename": "SecurityPrefix",
                    "id": "addr-any",
                    "name": {"value": "any"},
                    "book_index": {"value": None},
                }
            },
            {
                "node": {
                    "__typename": "SecurityIPAMIPAddress",
                    "id": "addr-access-portal",
                    "name": {"value": "access-portal"},
                    "book_index": {"value": 40},
                    "ip_address": {"node": {"id": "ip-10.112.240.33"}},
                }
            },
        ]
    )
    if vip_entry_for is not None:
        edges.append(
            {
                "node": {
                    "__typename": "SecurityIPAMIPAddress",
                    "id": "addr-existing-vip",
                    "name": {"value": "hand-written-vip"},
                    "book_index": {"value": 120},
                    "ip_address": {"node": {"id": vip_entry_for}},
                }
            }
        )
    if ours:
        # What an earlier run of THIS generator left behind.
        edges.append(
            {
                "node": {
                    "__typename": "SecurityIPAMIPAddress",
                    "id": "addr-ours-from-run-1",
                    "name": {"value": f"svc-{GRANT}-vip"},
                    "book_index": {"value": BOOK_INDEX_FLOOR + 3},
                    "ip_address": {"node": {"id": VIP_ID}},
                }
            }
        )
    return {"edges": edges}


def _query(
    *,
    zones: dict[str, str] | None = None,
    policy_targets: int = 1,
    protocols: tuple[str, ...] = ("tcp", "icmp"),
    **grant_kwargs: Any,
) -> GenerateAppAccessQuery:
    """The whole parsed response, with the lab's real context by default."""
    zones = ZONE_VRFS if zones is None else zones
    vip_entry_for = grant_kwargs.pop("existing_vip_entry_for", None)
    from_previous_run = grant_kwargs.pop("from_previous_run", False)
    services = list(FIREWALL_SERVICES)
    if from_previous_run:
        services.append((f"svc-{GRANT}-tcp-8080", 8080, "tcp"))

    policies = [
        {
            "node": {
                "id": f"policy-{n}",
                "name": {"value": "nfd41-perimeter" if n == 0 else f"other-{n}"},
                "device_target": {"node": {"id": "dev-fw1", "display_label": "fw1"}},
            }
        }
        for n in range(policy_targets)
    ]

    return GenerateAppAccessQuery(
        target={"edges": [_grant(**grant_kwargs)]},
        SecurityPolicy={"edges": policies},
        SecurityZone={
            "edges": [
                {"node": {"id": f"zone-{name}", "name": {"value": name}, "vrf": {"node": {"id": vrf}}}}
                for name, vrf in zones.items()
            ]
        },
        SecurityService={
            "edges": [
                {
                    "node": {
                        "id": f"svc-{name}",
                        "name": {"value": name},
                        "port": {"value": port},
                        "ip_protocol": {"node": {"id": f"proto-{proto}", "name": {"value": proto}}},
                    }
                }
                for name, port, proto in services
            ]
        },
        SecurityIPProtocol={"edges": [{"node": {"id": f"proto-{p}", "name": {"value": p}}} for p in protocols]},
        SecurityGenericAddress=_address_book(vip_entry_for=vip_entry_for, ours=from_previous_run),
    )


# ---------------------------------------------------------------------------
# US1 -- the approval gate and port validation
# ---------------------------------------------------------------------------


def test_an_unapproved_grant_is_not_approved() -> None:
    parsed = _query(approved=False)
    assert is_approved(parsed.target.edges[0].node) is False


def test_an_approved_grant_is_approved() -> None:
    parsed = _query(approved=True)
    assert is_approved(parsed.target.edges[0].node) is True


def test_empty_ports_is_rejected_and_never_read_as_all() -> None:
    """The worst defect this generator could have.

    An empty list must raise. Reading it as "all ports" would turn a request
    for one application into a permit-everything rule, and the lab's own
    FirewallAccess CRD makes the same choice with minItems: 1.
    """
    for empty in ([], None):
        parsed = _query(ports=empty)
        with pytest.raises(ValueError, match="empty list is rejected"):
            normalise_ports(parsed.target.edges[0].node)


def test_ports_are_sorted_deduplicated_and_range_checked() -> None:
    parsed = _query(ports=[443, 80, 443])
    assert normalise_ports(parsed.target.edges[0].node) == [80, 443]

    for bad in ([0], [65536], [-1]):
        with pytest.raises(ValueError, match="outside 1-65535"):
            normalise_ports(_query(ports=bad).target.edges[0].node)

    with pytest.raises(ValueError, match="not a number"):
        normalise_ports(_query(ports=["http"]).target.edges[0].node)


# ---------------------------------------------------------------------------
# US1 -- destination zone derivation (research R2)
# ---------------------------------------------------------------------------


def test_destination_zone_comes_from_the_applications_vrf() -> None:
    parsed = _query()
    grant = parsed.target.edges[0].node
    assert derive_destination_zone(parsed, grant) == "zone-k8s-prod"


def test_destination_zone_raises_when_the_application_has_no_vrf() -> None:
    parsed = _query(app_vrf=None)
    with pytest.raises(ValueError, match="has no VRF"):
        derive_destination_zone(parsed, parsed.target.edges[0].node)


def test_destination_zone_raises_when_no_zone_hands_off_to_that_vrf() -> None:
    """Must raise, not fall back to a default zone."""
    parsed = _query(zones={"wan": "vrf-WAN"})
    with pytest.raises(ValueError, match="0 security zones"):
        derive_destination_zone(parsed, parsed.target.edges[0].node)


def test_destination_zone_raises_when_two_zones_share_the_vrf() -> None:
    """Ambiguity is an error, never a first-match."""
    parsed = _query(zones={"k8s-prod": "vrf-K8S_PROD", "k8s-dr": "vrf-K8S_PROD"})
    with pytest.raises(ValueError, match="2 security zones"):
        derive_destination_zone(parsed, parsed.target.edges[0].node)


def test_an_intrazone_grant_is_refused() -> None:
    """Source and destination resolving to one zone is not modelled here."""
    parsed = _query(source_zone="k8s-prod")
    with pytest.raises(ValueError, match="intrazone"):
        validate_model(parsed)


# ---------------------------------------------------------------------------
# US1 -- policy and protocol derivation
# ---------------------------------------------------------------------------


def test_policy_is_the_one_targeting_a_device() -> None:
    parsed = _query()
    assert derive_policy(parsed, GRANT) == "policy-0"


def test_policy_raises_when_more_than_one_targets_a_device() -> None:
    parsed = _query(policy_targets=2)
    with pytest.raises(ValueError, match="2 security policies"):
        derive_policy(parsed, GRANT)


def test_policy_raises_when_none_targets_a_device() -> None:
    parsed = _query(policy_targets=0)
    with pytest.raises(ValueError, match="0 security policies"):
        derive_policy(parsed, GRANT)


def test_tcp_protocol_is_resolved_and_its_absence_raises() -> None:
    assert derive_tcp_protocol(_query(), GRANT) == "proto-tcp"
    with pytest.raises(ValueError, match="SecurityIPProtocol"):
        derive_tcp_protocol(_query(protocols=("icmp",)), GRANT)


# ---------------------------------------------------------------------------
# US1 -- deterministic allocation (research R1, R4)
# ---------------------------------------------------------------------------


def _context(parsed: GenerateAppAccessQuery) -> GrantContext:
    return validate_model(parsed)


def test_rule_index_sits_above_the_hand_written_baseline() -> None:
    """Generated permits must evaluate AFTER the anti-spoofing deny.

    Junos is first-match within a zone pair. A generated permit below index 10
    would shadow `deny-spoofed-infra` and turn every grant into a potential
    bypass for a spoofed fabric-infra source.
    """
    index = _context(_query()).rule_index
    assert index >= RULE_INDEX_FLOOR
    assert index not in BASELINE_RULE_INDEXES


def test_book_index_sits_clear_of_the_pinned_address_book() -> None:
    book_index = _context(_query()).book_index
    assert book_index >= BOOK_INDEX_FLOOR
    assert book_index not in HAND_WRITTEN_BOOK_INDEXES


def test_allocation_is_stable_across_calls() -> None:
    """Not Python's hash(): it is randomised per process, so a generator using
    it would allocate a different index every run and the tracking context
    would churn."""
    first, second = _context(_query()), _context(_query())
    assert first.rule_index == second.rule_index
    assert first.book_index == second.book_index


def test_book_index_steps_past_a_value_already_taken() -> None:
    taken = _context(_query())
    crowded = GrantContext(**{**taken.__dict__, "taken_book_indexes": frozenset({taken.book_index})})
    assert crowded.book_index == taken.book_index + 1


def test_generated_names_derive_from_the_grant_name() -> None:
    context = _context(_query())
    assert context.rule_name == f"svc-{GRANT}"
    assert context.vip_entry_name == f"svc-{GRANT}-vip"
    assert context.service_name(8080) == f"svc-{GRANT}-tcp-8080"


# ---------------------------------------------------------------------------
# US2 -- adoption, which is what makes revocation safe
# ---------------------------------------------------------------------------


def test_existing_tcp_services_are_indexed_by_port_not_by_name() -> None:
    """A grant for 443 must find junos-https.

    Creating `svc-<grant>-tcp-443` beside it would declare a second Junos
    application for the same port, and the rendered configuration would stop
    reading like the hand-written rules next to it.
    """
    services = index_tcp_services(_query())
    assert services[80].id == "svc-junos-http"
    assert services[443].id == "svc-junos-https"
    assert services[443].name == "junos-https"


def test_icmp_services_are_never_offered_for_adoption() -> None:
    """`ports` is a list of TCP ports; junos-ping stays hand-written."""
    services = index_tcp_services(_query())
    assert "svc-junos-ping" not in {existing.id for existing in services.values()}


def test_the_address_book_is_indexed_by_the_address_it_wraps() -> None:
    by_address, taken = index_address_book(_query())
    assert by_address["ip-10.112.240.33"].id == "addr-access-portal"
    assert by_address["ip-10.112.240.33"].name == "access-portal"
    assert set(HAND_WRITTEN_BOOK_INDEXES) <= taken


def test_an_entry_without_a_book_index_is_not_counted_as_taken() -> None:
    """`any` is a keyword: referenced by rules, declared in no book."""
    _, taken = index_address_book(_query())
    assert None not in taken


def test_an_existing_entry_for_the_vip_is_adopted_rather_than_duplicated() -> None:
    context = _context(_query(existing_vip_entry_for=VIP_ID))
    assert context.existing_vip_entry is not None
    assert context.existing_vip_entry.id == "addr-existing-vip"
    assert not context.existing_vip_entry.is_ours(context.vip_entry_name), (
        "a hand-written entry is foreign and must never be rewritten"
    )


def test_no_existing_entry_means_one_will_be_created() -> None:
    assert _context(_query()).existing_vip_entry is None


# ---------------------------------------------------------------------------
# The whole validated context
# ---------------------------------------------------------------------------


def test_validate_model_resolves_everything_before_any_write() -> None:
    context = _context(_query(ports=[8080, 443]))
    assert context.grant_name == GRANT
    assert context.ports == [443, 8080]
    assert context.policy_id == "policy-0"
    assert context.destination_zone_id == "zone-k8s-prod"
    assert context.source_zone_id == "zone-branch"
    assert context.vip_id == VIP_ID
    assert context.tcp_protocol_id == "proto-tcp"


def test_validate_model_raises_when_the_grant_is_missing() -> None:
    parsed = GenerateAppAccessQuery(
        target={"edges": []},
        SecurityPolicy={"edges": []},
        SecurityZone={"edges": []},
        SecurityService={"edges": []},
        SecurityIPProtocol={"edges": []},
        SecurityGenericAddress={"edges": []},
    )
    with pytest.raises(ValueError, match="no ServiceAppAccess matched"):
        validate_model(parsed)


def test_validate_model_raises_when_the_destination_vip_is_gone() -> None:
    with pytest.raises(ValueError, match="no destination_vip"):
        validate_model(_query(vip_id=None))


# ---------------------------------------------------------------------------
# generate() -- the claims that are about calls rather than about state
# ---------------------------------------------------------------------------


@dataclass
class _RecordingAttribute:
    value: Any = None


class _RecordingRelationship:
    """A RelationshipManager is not a list: it is fetched, then add/remove'd."""

    def __init__(self) -> None:
        self.peer_ids: list[str] = []
        self.fetched = False

    async def fetch(self) -> None:
        self.fetched = True

    def add(self, peer_id: str) -> None:
        self.peer_ids.append(peer_id)

    def remove(self, peer_id: str) -> None:
        self.peer_ids.remove(peer_id)


class _RecordingNode:
    def __init__(self, node_id: str) -> None:
        self.id = node_id
        self.saves: list[dict[str, Any]] = []
        self.status = _RecordingAttribute("provisioning")
        self.granted_rules = _RecordingRelationship()

    async def save(self, **kwargs: Any) -> None:
        self.saves.append(kwargs)


class _RecordingClient:
    """Enough client to prove what was and was not written."""

    def __init__(self) -> None:
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.fetched: list[str] = []
        self.deleted: list[tuple[str, str]] = []
        self.nodes: dict[str, _RecordingNode] = {}

    async def create(self, kind: str, data: dict[str, Any]) -> Any:
        self.created.append((kind, data))
        return _RecordingNode(f"new-{kind}-{len(self.created)}")

    async def get(self, kind: str, id: str) -> Any:  # noqa: A002
        self.fetched.append(f"{kind}:{id}")
        return self.nodes.setdefault(id, _RecordingNode(id))

    async def delete(self, kind: str, id: str) -> None:  # noqa: A002
        self.deleted.append((kind, id))


def _generator(client: _RecordingClient) -> AppAccessGenerator:
    generator = AppAccessGenerator.__new__(AppAccessGenerator)
    generator._client = client  # type: ignore[attr-defined]
    import logging

    generator.logger = logging.getLogger("test")
    return generator


@pytest.mark.asyncio
async def test_an_unapproved_grant_writes_absolutely_nothing() -> None:
    """Zero writes, not merely the absence of a rule.

    This is the seeded grant's state, so it is also the default outcome on a
    fresh bootstrap -- and it reads exactly like a broken generator, which is
    why the positive case below has to be proven beside it.
    """
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=False)

    await generator.generate(parsed.model_dump(by_alias=True))

    assert client.created == []
    assert client.fetched == []


@pytest.mark.asyncio
async def test_an_approved_grant_creates_the_entry_services_and_rule() -> None:
    """The non-empty result that makes the empty one above evidence."""
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=True, ports=[8080])

    await generator.generate(parsed.model_dump(by_alias=True))

    kinds = [kind for kind, _ in client.created]
    assert kinds == ["SecurityIPAMIPAddress", "SecurityService", "SecurityPolicyRule"]

    rule = next(data for kind, data in client.created if kind == "SecurityPolicyRule")
    assert rule["managed_by_service"] is True
    assert rule["action"] == "permit"
    assert rule["index"] >= RULE_INDEX_FLOOR
    assert rule["source_zone"] == "zone-branch"
    assert rule["destination_zone"] == "zone-k8s-prod"

    entry = next(data for kind, data in client.created if kind == "SecurityIPAMIPAddress")
    assert entry["book_index"] >= BOOK_INDEX_FLOOR, "an entry without one is skipped by the renderer"


@pytest.mark.asyncio
async def test_port_443_adopts_junos_https_instead_of_creating_a_duplicate() -> None:
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=True, ports=[443])

    await generator.generate(parsed.model_dump(by_alias=True))

    assert [kind for kind, _ in client.created] == ["SecurityIPAMIPAddress", "SecurityPolicyRule"]
    rule = next(data for kind, data in client.created if kind == "SecurityPolicyRule")
    assert rule["destination_services"] == ["svc-junos-https"]


@pytest.mark.asyncio
async def test_revoking_a_grant_withdraws_what_an_earlier_run_created() -> None:
    """Revocation is explicit, because tracking does not cover it.

    `InfrahubGroupContext.update_group` opens with ``if not members: return``,
    so a run that touches nothing prunes nothing. Relying on it left a revoked
    grant's rule, address entry and service object in place on a live branch.
    """
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=False, from_previous_run=True, granted_rule_ids=[f"svc-{GRANT}"])
    # granted_rules carries the rule's own name, which is how it is recognised.
    parsed.target.edges[0].node.granted_rules.edges[0].node.name.value = f"svc-{GRANT}"

    await generator.generate(parsed.model_dump(by_alias=True))

    assert client.created == []
    deleted_kinds = {kind for kind, _ in client.deleted}
    assert deleted_kinds == {"SecurityPolicyRule", "SecurityIPAMIPAddress", "SecurityService"}


@pytest.mark.asyncio
async def test_revocation_never_deletes_a_referenced_object() -> None:
    """`junos-https` is not named `svc-<grant>-tcp-443`, so it is never a
    candidate. Deleting it would break the baseline rules that share the port.
    """
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=False, from_previous_run=True)

    await generator.generate(parsed.model_dump(by_alias=True))

    assert "svc-junos-https" not in {node_id for _, node_id in client.deleted}
    assert "addr-access-portal" not in {node_id for _, node_id in client.deleted}


@pytest.mark.asyncio
async def test_revoking_a_grant_that_built_nothing_deletes_nothing() -> None:
    """The seeded grant's state: unapproved and never approved."""
    client = _RecordingClient()
    generator = _generator(client)

    await generator.generate(_query(approved=False).model_dump(by_alias=True))

    assert client.created == []
    assert client.deleted == []


@pytest.mark.asyncio
async def test_an_adopted_service_is_never_marked_as_service_managed() -> None:
    """The guard that keeps junos-https alive when a grant using it is revoked.

    `managed_by_service` is what the tracking context's ownership ultimately
    reflects: an object this generator created is its to remove, and an adopted
    one is not. If adoption ever became an upsert, revoking a grant that used
    port 443 would take `junos-https` with it and the baseline rules that
    reference it would break.
    """
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=True, ports=[443])

    await generator.generate(parsed.model_dump(by_alias=True))

    for kind, data in client.created:
        if kind != "SecurityPolicyRule":
            assert "managed_by_service" not in data, f"{kind} is not a rule and must not claim ownership"
    assert not any(kind == "SecurityService" for kind, _ in client.created)


@pytest.mark.asyncio
async def test_an_adopted_address_entry_keeps_its_name_and_book_index() -> None:
    """Adoption fetches and modifies; it never renames or re-indexes.

    Re-indexing an adopted entry would move it inside the address book, and the
    book's order is pinned byte-for-byte by tests/unit/test_junos_config.py.
    """
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=True, ports=[8080], existing_vip_entry_for=VIP_ID)

    await generator.generate(parsed.model_dump(by_alias=True))

    assert not any(kind == "SecurityIPAMIPAddress" for kind, _ in client.created)
    rule = next(data for kind, data in client.created if kind == "SecurityPolicyRule")
    assert rule["destination_address"] == ["addr-existing-vip"]


@pytest.mark.asyncio
async def test_narrowing_the_ports_narrows_what_the_run_touches() -> None:
    """Three ports down to one leaves two service objects untouched.

    Untouched is what the tracking context acts on: the two the generator no
    longer creates are the two it deletes.
    """
    wide = _RecordingClient()
    await _generator(wide).generate(_query(approved=True, ports=[8080, 9090, 9091]).model_dump(by_alias=True))
    narrow = _RecordingClient()
    await _generator(narrow).generate(_query(approved=True, ports=[8080]).model_dump(by_alias=True))

    wide_services = [d["name"] for k, d in wide.created if k == "SecurityService"]
    narrow_services = [d["name"] for k, d in narrow.created if k == "SecurityService"]
    assert wide_services == [f"svc-{GRANT}-tcp-8080", f"svc-{GRANT}-tcp-9090", f"svc-{GRANT}-tcp-9091"]
    assert narrow_services == [f"svc-{GRANT}-tcp-8080"]


@pytest.mark.asyncio
async def test_a_second_run_rewrites_the_objects_the_first_run_created() -> None:
    """The regression test for a bug a live run found and no fake could.

    On the second run the address entry and the service object already exist,
    so the obvious implementation returns their ids and touches nothing. That
    leaves them out of the run's tracking group, `delete_unused_nodes=True`
    deletes them, and the rule -- which IS rewritten -- survives pointing at an
    address the book no longer declares. Measured against a live branch: the
    second run removed `svc-<grant>-vip` and `svc-<grant>-tcp-8080` and left the
    rule referencing both.

    So an object this generator owns must be written every single run. The test
    asserts the write, not the absence of a duplicate.
    """
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=True, ports=[8080], from_previous_run=True)

    await generator.generate(parsed.model_dump(by_alias=True))

    written = [kind for kind, _ in client.created]
    assert "SecurityIPAMIPAddress" in written, "our own address entry must be rewritten, not skipped"
    assert "SecurityService" in written, "our own service object must be rewritten, not skipped"


@pytest.mark.asyncio
async def test_a_foreign_object_is_still_only_referenced_on_a_second_run() -> None:
    """The other half: rewriting everything would be just as wrong.

    `junos-https` belongs to the hand-written baseline. Writing it would pull it
    into the tracking group, and revoking this grant would then delete an object
    the baseline rules still reference.
    """
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=True, ports=[443], from_previous_run=True)

    await generator.generate(parsed.model_dump(by_alias=True))

    assert not any(kind == "SecurityService" for kind, _ in client.created)
    rule = next(data for kind, data in client.created if kind == "SecurityPolicyRule")
    assert rule["destination_services"] == ["svc-junos-https"]


@pytest.mark.asyncio
async def test_a_second_run_produces_byte_identical_payloads() -> None:
    """Idempotence, as far as a fake client can prove it.

    Every name and every allocated index must be identical, because that is
    what makes `save(allow_upsert=True)` a no-op on the second run rather than
    a second object. A moving index would also churn the tracking group.
    """
    first, second = _RecordingClient(), _RecordingClient()
    payload = _query(approved=True, ports=[8080]).model_dump(by_alias=True)

    await _generator(first).generate(payload)
    await _generator(second).generate(payload)

    assert first.created == second.created


@pytest.mark.asyncio
async def test_the_grant_is_saved_without_joining_the_tracking_group() -> None:
    """`update_group_context=False` is not optional.

    The grant is this generator's *target*, not something it owns. Letting it
    join the tracking group would make it a deletion candidate on any later run
    that did not touch it -- the generator would delete the service it exists
    to serve.
    """
    client = _RecordingClient()
    await _generator(client).generate(_query(approved=True, ports=[8080]).model_dump(by_alias=True))

    grant = client.nodes[f"grant-{GRANT}"]
    assert grant.saves, "the grant should have been saved at least once"
    assert all(save.get("update_group_context") is False for save in grant.saves)


@pytest.mark.asyncio
async def test_a_validation_failure_records_error_and_raises() -> None:
    """`error` is distinct from `provisioning` on purpose: both leave no
    technical objects behind, and "tried and failed" is otherwise
    indistinguishable from "not built yet"."""
    client = _RecordingClient()
    generator = _generator(client)
    parsed = _query(approved=True, ports=[])

    with pytest.raises(ValueError, match="empty list is rejected"):
        await generator.generate(parsed.model_dump(by_alias=True))

    assert client.created == []
    assert client.fetched == [f"ServiceAppAccess:grant-{GRANT}"]


# ---------------------------------------------------------------------------
# The seed data, which is the only thing keeping the rendered artifact stable
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[2]
GRANTS_FILE = REPO_ROOT / "objects/38_nfd41_access_grants.yml"
GROUPS_FILE = REPO_ROOT / "objects/00_groups.yml"


def _documents(path: Path) -> list[dict[str, Any]]:
    return [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]


def _seeded_grants() -> list[dict[str, Any]]:
    for document in _documents(GRANTS_FILE):
        spec = document.get("spec", {})
        if spec.get("kind") == "ServiceAppAccess":
            return spec.get("data", [])
    return []


def test_the_seeded_grant_is_unapproved() -> None:
    """The load-bearing property of the seed data, asserted rather than assumed.

    tests/unit/test_junos_config.py holds the rendered artifact byte-for-byte
    against ../lab/configs/fw/vsrx/junos.conf -- but it reads a captured
    fixture, so it cannot notice a change made here. Approving the seeded grant
    would add a rule and an address-book entry to the default data set, and the
    device file those assertions are measured against has no such rule, so
    there would be nothing true to update them to.

    If this test fails, do not flip it back without also deciding what
    test_junos_config.py should now assert.
    """
    grants = _seeded_grants()
    assert grants, "ServiceAppAccess has no seed object; the generator would never run"
    for grant in grants:
        assert grant["approved"] is False, (
            f"seeded grant {grant['name']!r} is approved; it will change the rendered Junos artifact"
        )


def test_the_seeded_grant_joins_the_generator_target_group() -> None:
    """A grant outside the group is a grant the generator never sees."""
    for grant in _seeded_grants():
        assert "service_app_accesses" in grant.get("member_of_groups", [])


def test_the_target_group_is_declared() -> None:
    for document in _documents(GROUPS_FILE):
        spec = document.get("spec", {})
        if spec.get("kind") == "CoreStandardGroup":
            names = {row["name"] for row in spec.get("data", [])}
            assert "service_app_accesses" in names
            return
    pytest.fail("objects/00_groups.yml declares no CoreStandardGroup document")


def test_the_seeded_grant_names_the_ports_its_application_serves() -> None:
    """A grant naming a port the application does not serve is permitted by the
    firewall and refused by the cluster's network policy, which reads as a
    firewall fault."""
    app_services = REPO_ROOT / "objects/36_nfd41_app_services.yml"
    apps = {
        row["name"]: row
        for document in _documents(app_services)
        if document.get("spec", {}).get("kind") == "ServiceFabricApp"
        for row in document["spec"]["data"]
    }

    for grant in _seeded_grants():
        application = apps[grant["application"]]
        served = {int(entry["port"]) for entry in application.get("policy_allow_ports", [])}
        assert set(grant["ports"]) <= served, f"grant {grant['name']!r} asks for ports its application does not serve"


# ---------------------------------------------------------------------------
# The rule reaches the rendered configuration (US3)
# ---------------------------------------------------------------------------

JUNOS_FIXTURE = REPO_ROOT / "tests/unit/fixtures/junos/fw1.json"


def _render_with_generated_objects() -> list[str]:
    """Render fw1's configuration with one generated grant present.

    No transform change was needed for this to work: `junos_config.gql` queries
    `SecurityGenericAddress` and `SecurityPolicy` unfiltered, so a generated
    object is rendered the moment it exists. This test is what turns that from
    a claim into evidence.
    """
    import asyncio
    import json

    from transforms.junos_config import JunosConfig

    data = json.loads(JUNOS_FIXTURE.read_text(encoding="utf-8"))

    # Exactly what _upsert_vip_entry writes: a book entry above every
    # hand-written index, wrapping the grant's VIP.
    data["SecurityGenericAddress"]["edges"].append(
        {
            "node": {
                "__typename": "SecurityIPAMIPAddress",
                "name": {"value": f"svc-{GRANT}-vip"},
                "description": {"value": "generated"},
                "book_index": {"value": BOOK_INDEX_FLOOR + 7},
                "ip_address": {"node": {"address": {"value": "10.112.240.10/32"}}},
            }
        }
    )
    data["SecurityGenericService"]["edges"].append(
        {"node": {"__typename": "SecurityService", "name": {"value": f"svc-{GRANT}-tcp-8080"}}}
    )
    # And what _upsert_rule writes, into the branch -> k8s-prod pair.
    data["SecurityPolicy"]["edges"][0]["node"]["rules"]["edges"].append(
        {
            "node": {
                "name": {"value": f"svc-{GRANT}"},
                "index": {"value": RULE_INDEX_FLOOR + 7},
                "action": {"value": "permit"},
                "log": {"value": True},
                "log_session_close": {"value": True},
                "source_zone": {"node": {"name": {"value": "branch"}}},
                "destination_zone": {"node": {"name": {"value": "k8s-prod"}}},
                "source_address": {
                    "edges": [{"node": {"__typename": "SecurityIPAMIPPrefix", "display_label": "branch-users"}}]
                },
                "destination_address": {
                    "edges": [{"node": {"__typename": "SecurityIPAMIPAddress", "display_label": f"svc-{GRANT}-vip"}}]
                },
                "source_groups": {"edges": []},
                "destination_groups": {"edges": []},
                "source_services": {"edges": []},
                "destination_services": {
                    "edges": [{"node": {"__typename": "SecurityService", "display_label": f"svc-{GRANT}-tcp-8080"}}]
                },
                "source_service_groups": {"edges": []},
                "destination_service_groups": {"edges": []},
            }
        }
    )

    transform = JunosConfig.__new__(JunosConfig)
    transform.root_directory = str(REPO_ROOT)
    return asyncio.run(transform.transform(data)).splitlines()


def test_a_generated_rule_renders_into_its_zone_pair() -> None:
    rendered = _render_with_generated_objects()
    assert any(f"policy svc-{GRANT} {{" in line for line in rendered)
    assert any(f"svc-{GRANT}-vip" in line for line in rendered)


def test_a_generated_rule_renders_after_the_baseline_in_its_pair() -> None:
    """Junos is first-match: the anti-spoofing deny must still come first.

    This is the assertion behind the index floor. If a generated permit ever
    sorted above `deny-spoofed-infra`, a grant would become a bypass for a
    spoofed fabric-infra source, and nothing else in the suite would notice.
    """
    rendered = _render_with_generated_objects()
    pair_start = next(i for i, line in enumerate(rendered) if "from-zone branch to-zone k8s-prod" in line)
    tail = rendered[pair_start:]

    deny = next(i for i, line in enumerate(tail) if "policy deny-spoofed-infra {" in line)
    generated = next(i for i, line in enumerate(tail) if f"policy svc-{GRANT} {{" in line)
    assert deny < generated


def test_a_generated_address_entry_renders_after_every_hand_written_one() -> None:
    """The address book's order is pinned; the floor of 1000 is what keeps it."""
    rendered = _render_with_generated_objects()
    generated = next(i for i, line in enumerate(rendered) if f"svc-{GRANT}-vip" in line)
    for name in ("k8s-nodes", "branch-users", "globex-cloud"):
        hand_written = next(i for i, line in enumerate(rendered) if f"address {name} " in line)
        assert hand_written < generated
