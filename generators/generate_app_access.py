"""Turn an approved application access grant into the firewall objects for it.

`ServiceAppAccess` was the one service kind that produced nothing: a schema, a
menu entry and six contract tests, but no generator, no transform and no
artifact. This is the generator that makes it act.

An approved grant becomes three things -- an address-book entry for the
destination VIP, a service object per permitted port, and the `permit` rule
joining them -- and those render into the firewall's existing Junos artifact
with no change downstream. `transforms/junos_config.gql` queries
`SecurityGenericAddress` and `SecurityPolicy` unfiltered, so a generated object
is picked up the moment it exists.

FIVE THINGS THAT LOOK ARBITRARY AND ARE NOT.

* **The index floor of 100.** Junos evaluates policies first-match *within* a
  zone pair, so `index` is semantic. The hand-written baseline puts an
  anti-spoofing `deny` at index 10 in every pair and its permits at 20 and 30.
  A generated permit at 100+ therefore evaluates *after* the deny, and a grant
  can never open a hole for a spoofed `fabric-infra` source. Allocating below
  the baseline would invert that and make every grant a potential bypass.

* **The `book_index` floor of 1000.** `transforms/junos_config.py::_addresses`
  renders the address book in `book_index` order and **skips any entry whose
  index is null** -- such an entry is referenced by a rule and never declared,
  and the configuration does not load. Hand-written entries occupy 10 to 130,
  so a floor of 1000 leaves the order `tests/unit/test_junos_config.py` pins
  completely untouched. Both floors are presentational rather than semantic;
  what matters is that they are deterministic, because the tracking context
  churns on any value that moves between runs.

* **An object is either ours or foreign, and the two are handled opposite
  ways.** The firewall already declares `junos-http` (80) and `junos-https`
  (443), so a grant for 443 *references* the existing object rather than
  declaring a second application for the same port. A referenced object is
  never written, never renamed and never marked `managed_by_service`, so it
  never joins the tracking group and survives the grant's revocation.

  An object this generator created on an EARLIER run is the opposite case: it
  must be written **again, every run**. This is the trap, and it is invisible
  to a unit test with a fake client. Returning an existing id without touching
  the node leaves it out of this run's tracking group, and
  `delete_unused_nodes=True` then deletes it -- while the rule referencing it
  is rewritten and survives. The result is an address referenced by a rule and
  declared nowhere, which is precisely what stops the configuration loading.
  Measured: the second run deleted `svc-<grant>-vip` and `svc-<grant>-tcp-8080`
  and left the rule pointing at both. `Existing.is_ours` is the distinction.

* **The destination zone comes from the VRF, not from the firewall's
  interfaces.** `ServiceFabricApp.vrf` and `SecurityZone.vrf` both peer
  `IpamVRF`, and the zone is the one whose VRF matches the application's.
  Deriving it from "the interface whose subnet contains the VIP" cannot work:
  the handoff interfaces are /30 point-to-points (10.250.110.2/30 and friends)
  and contain no service VIP, so containment matches nothing and every grant
  raises.

* **An unapproved grant is a silent no-op, deliberately.** `approved` is the
  gate, and an unapproved request has to be inert rather than merely hidden.
  The cost is that "ran successfully and created nothing" is the normal
  outcome, which is indistinguishable from a broken generator unless you check
  the flag first. The seeded grant in `objects/38_nfd41_access_grants.yml` is
  unapproved for exactly this reason -- it keeps the rendered artifact
  byte-identical while leaving the demo one field-flip away.

Validation runs to completion before the first write. The tracking context
deletes previously-managed objects this run did not touch, so a *partial* write
followed by a successful exit is the one path by which this generator can
delete a real rule. A raised exception is safe by comparison: the SDK's
`__aexit__` updates the group only when `exc_type is None`, so a failed run
prunes nothing.

WHAT THE TRACKING CONTEXT DOES **NOT** COVER, and assuming otherwise was a bug
this cycle had to fix: `InfrahubGroupContext.update_group` opens with
``if not members: return``. A run that touches nothing therefore prunes nothing.
That is fine for *narrowing* a grant -- the run still writes a rule, so the
dropped service objects fall out of a non-empty member set -- and wrong for
*revoking* one, where the run writes nothing at all. Un-approving a grant left
its rule, its address entry and its service object exactly where they were.
`_withdraw` deletes them explicitly, by generated name, which is also what keeps
a referenced object like `junos-https` out of the deletion set.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import blake2b
from operator import itemgetter
from typing import Any
from urllib.parse import quote

from infrahub_sdk.generator import InfrahubGenerator

from .generate_app_access_query import (
    GenerateAppAccessQuery,
    GenerateAppAccessQueryTargetEdgesNode,
)

# Readable alias for the verbose generated class, following
# generators/generate_fabric_peering.py. The deeper ones are reached through
# attribute access rather than named, because their generated names run past
# 200 characters.
GrantNode = GenerateAppAccessQueryTargetEdgesNode

# See the module docstring. Both are deterministic and both sit clear of every
# hand-written value, which is what keeps the pinned orderings intact.
RULE_INDEX_FLOOR = 100
BOOK_INDEX_FLOOR = 1000
# Hand-written prefix-list sequences are 10 and 20, and they live at fabric
# scope. A generated sequence sits far above them and at DEVICE scope, where
# `_merge_lists` composes the two by `name` then by `sequence` rather than
# replacing the baseline.
PREFIX_SEQUENCE_FLOOR = 1000

# Wide enough that two grants colliding is negligible at any realistic number
# of them. A collision would not change what the firewall permits -- generated
# permits have disjoint destinations, so their relative order carries no
# meaning -- but it would make the rendered artifact's ordering unstable, and
# the reconciler would then see a difference on every cycle.
ALLOCATION_SPAN = 1_000_000

# Only TCP is generated. `ports` is a list of TCP ports; ICMP is not
# requestable through a grant, and the firewall's `junos-ping` stays
# hand-written.
TCP = "tcp"

# The artifact_name from .infrahub.yml, which is what artifact_generate
# looks the artifact up by. A mismatch here fails at run time, not load time.
FIREWALL_ARTIFACT = "Junos Configuration"

# The one key inside DcimFabricSwitch.avd_custom_hostvars this generator
# writes. The attribute is a shared JSON blob, so every write is a
# read-modify-write that preserves everything else in it.
PREFIX_LISTS_KEY = "custom_structured_configuration_prefix_lists"

MIN_PORT = 1
MAX_PORT = 65535


def _value(wrapper: Any) -> Any:
    """Unwrap an Infrahub ``{"value": ...}`` wrapper, tolerating absence."""
    return wrapper.value if wrapper is not None else None


def _node_of(relationship: Any) -> Any:
    """Unwrap a cardinality-one relationship, tolerating absence."""
    return relationship.node if relationship is not None else None


def _edges_of(relationship: Any) -> list[Any]:
    """Unwrap a cardinality-many relationship into its nodes, skipping nulls."""
    if relationship is None:
        return []
    return [edge.node for edge in relationship.edges if edge.node is not None]


def _stable_offset(seed: str, floor: int) -> int:
    """A deterministic number at or above ``floor``, derived from ``seed``.

    Deliberately not ``hash()``: Python randomises string hashing per process
    unless PYTHONHASHSEED is fixed, so a generator using it would allocate a
    different index on every run and the tracking context would churn.
    """
    digest = blake2b(seed.encode("utf-8"), digest_size=8).digest()
    return floor + int.from_bytes(digest, "big") % ALLOCATION_SPAN


@dataclass(frozen=True)
class Advertisement:
    """Where a grant's VIP must be advertised from, when anywhere.

    The fabric leg of a grant. A `ServiceAppAccess` names all three domains of
    this lab -- the application (Kubernetes), the source zone (Junos) and the
    destination VIP (the fabric) -- and until cycle 032 the third had nowhere to
    write, because nothing connected a zone to the policy governing
    advertisement toward it.

    `None` is a legitimate result: four of the six zones carry neither field
    because the DC advertises nothing toward them, and a grant from one of those
    gets its firewall rule and no advertisement.
    """

    device_id: str
    device_name: str
    prefix_list: str
    hostvars: dict[str, Any]


def derive_advertisement(grant: GrantNode) -> Advertisement | None:
    """The fabric side of the grant's source zone, or None if it has none."""
    zone = _node_of(grant.source_zone)
    if zone is None:
        return None

    prefix_list_value = _value(getattr(zone, "dc_advertised_prefix_list", None))
    device = _node_of(getattr(zone, "advertising_device", None))
    name = _value(zone.name)

    if prefix_list_value is None and device is None:
        return None

    # Half-modelled. The schema permits it and the lab has none; a zone with one
    # half is a mistake rather than a state to act on, and acting on it would
    # either write into an unnamed list or name a list on no device.
    if prefix_list_value is None or device is None:
        missing = "advertising_device" if device is None else "dc_advertised_prefix_list"
        msg = (
            f"zone {name!r} carries one half of its advertisement policy and not the other "
            f"({missing} is unset); the fabric leg cannot be derived"
        )
        raise ValueError(msg)

    raw = _value(getattr(device, "avd_custom_hostvars", None))
    hostvars = deepcopy(raw) if isinstance(raw, dict) else {}

    return Advertisement(
        device_id=device.id,
        device_name=_value(device.name),
        prefix_list=prefix_list_value,
        hostvars=hostvars,
    )


def advertisement_entry(hostvars: dict[str, Any], prefix_list: str, sequence: int, action: str) -> dict[str, Any]:
    """``hostvars`` with one sequence added to one prefix list.

    Merged rather than replaced, at every level. The attribute is shared, the
    list may already carry another grant's sequence, and `_merge_lists` in
    `generate_avd_device_hostvar.py` composes this device-scope entry with the
    fabric-scope baseline by `name` and then by `sequence` -- so this adds to
    `PL-DC-ADVERTISED-BRANCH` rather than replacing what the fabric declares.
    """
    merged = deepcopy(hostvars)
    lists = merged.setdefault(PREFIX_LISTS_KEY, [])

    entry = next((item for item in lists if item.get("name") == prefix_list), None)
    if entry is None:
        entry = {"name": prefix_list, "sequence_numbers": []}
        lists.append(entry)

    sequences = [item for item in entry.get("sequence_numbers", []) if item.get("sequence") != sequence]
    sequences.append({"sequence": sequence, "action": action})
    entry["sequence_numbers"] = sorted(sequences, key=itemgetter("sequence"))
    return merged


def advertisement_removed(hostvars: dict[str, Any], prefix_list: str, sequence: int) -> dict[str, Any]:
    """``hostvars`` with one sequence removed, pruning what it empties.

    An emptied list and an emptied key are both removed, so a device that has
    never carried anything else comes back to `{}` rather than to a husk of
    nested empties that renders an empty prefix list onto the switch.
    """
    merged = deepcopy(hostvars)
    lists = merged.get(PREFIX_LISTS_KEY)
    if not isinstance(lists, list):
        return merged

    for entry in list(lists):
        if entry.get("name") != prefix_list:
            continue
        entry["sequence_numbers"] = [
            item for item in entry.get("sequence_numbers", []) if item.get("sequence") != sequence
        ]
        if not entry["sequence_numbers"]:
            lists.remove(entry)

    if not lists:
        merged.pop(PREFIX_LISTS_KEY, None)
    return merged


@dataclass(frozen=True)
class Existing:
    """An object already in the graph that this run could reference.

    The name is what separates the two cases, and getting them the same way
    round is the difference between a working generator and one that deletes
    the objects its own rule points at.

    **Ours** -- the name matches what this grant generates. It was created by an
    earlier run of this generator, and it MUST be written again every run.
    Returning its id without touching it leaves it out of this run's tracking
    group, and `delete_unused_nodes=True` then deletes it while the rule that
    references it survives. That produces an address referenced and never
    declared, which is exactly what stops the configuration loading.

    **Foreign** -- anything else, `junos-https` being the case that matters. It
    must be referenced and never written, so it never joins the tracking group
    and is never a deletion candidate when this grant is revoked.
    """

    id: str
    name: str | None

    def is_ours(self, generated_name: str) -> bool:
        return self.name == generated_name


@dataclass(frozen=True)
class GrantContext:
    """Everything a validated grant needs, resolved before the first write."""

    grant: GrantNode
    grant_name: str
    ports: list[int]
    policy_id: str
    destination_zone_id: str
    source_zone_id: str
    source_address_id: str
    vip_id: str
    vip_address: str | None
    firewall_id: str | None
    tcp_protocol_id: str
    application_name: str | None
    requester: str | None
    existing_vip_entry: Existing | None
    """An address-book entry already wrapping this VIP, if one exists."""
    taken_book_indexes: frozenset[int] = field(default_factory=frozenset)
    services_by_port: dict[int, Existing] = field(default_factory=dict)
    """Existing TCP service objects, keyed by port. Referenced, never duplicated."""

    @property
    def rule_name(self) -> str:
        return f"svc-{self.grant_name}"

    @property
    def vip_entry_name(self) -> str:
        return f"svc-{self.grant_name}-vip"

    def service_name(self, port: int) -> str:
        return f"svc-{self.grant_name}-{TCP}-{port}"

    @property
    def rule_index(self) -> int:
        return _stable_offset(self.grant_name, RULE_INDEX_FLOOR)

    @property
    def prefix_sequence(self) -> int:
        """The sequence this grant occupies in the advertised prefix list."""
        return _stable_offset(self.grant_name, PREFIX_SEQUENCE_FLOOR)

    @property
    def book_index(self) -> int:
        """Clear of the hand-written book, and clear of anything already taken.

        The floor alone guarantees the first, because hand-written entries stop
        at 130. The loop guarantees the second, which the floor cannot: two
        generated entries could in principle land on the same number.
        """
        candidate = _stable_offset(self.vip_entry_name, BOOK_INDEX_FLOOR)
        while candidate in self.taken_book_indexes:
            candidate += 1
        return candidate


def is_approved(grant: GrantNode) -> bool:
    """V1. The gate: nothing is materialized while this is false."""
    return bool(_value(grant.approved))


def normalise_ports(grant: GrantNode) -> list[int]:
    """V2, V3. The permitted TCP ports, sorted, validated, de-duplicated.

    An EMPTY list is rejected rather than read as "all ports". That is the
    worst defect this generator could have, and the lab's own `FirewallAccess`
    CRD makes the same choice with ``minItems: 1``.
    """
    raw = _value(grant.ports)
    name = _value(grant.name)

    if not raw:
        msg = (
            f"grant {name!r} permits no ports; an empty list is rejected rather than "
            "read as 'all ports', which is what a permit-everything rule would mean"
        )
        raise ValueError(msg)

    ports: set[int] = set()
    for entry in raw:
        try:
            port = int(entry)
        except (TypeError, ValueError):
            msg = f"grant {name!r} names a port that is not a number: {entry!r}"
            raise ValueError(msg) from None
        if not MIN_PORT <= port <= MAX_PORT:
            msg = f"grant {name!r} names port {port}, outside {MIN_PORT}-{MAX_PORT}"
            raise ValueError(msg)
        ports.add(port)

    return sorted(ports)


def derive_firewall(parsed: GenerateAppAccessQuery) -> str | None:
    """The device the policy is applied to, so its artifact can be re-rendered."""
    for edge in parsed.security_policy.edges:
        node = edge.node
        target = _node_of(node.device_target) if node is not None else None
        if target is not None:
            return target.id
    return None


def derive_policy(parsed: GenerateAppAccessQuery, grant_name: str) -> str:
    """V6. The policy the rule joins.

    ``SecurityPolicyRule.policy`` is mandatory and cardinality one, and the
    grant does not name a policy. Exactly one has to target the firewall; the
    lab has one, ``nfd41-perimeter``.
    """
    policies = [edge.node for edge in parsed.security_policy.edges if edge.node is not None]
    targeted = [policy for policy in policies if _node_of(policy.device_target) is not None]

    if len(targeted) != 1:
        found = ", ".join(sorted(_value(policy.name) or "?" for policy in targeted)) or "none"
        msg = (
            f"grant {grant_name!r} cannot be placed: {len(targeted)} security policies target a "
            f"device ({found}); a rule joins exactly one policy and the grant does not name it"
        )
        raise ValueError(msg)

    return targeted[0].id


def derive_destination_zone(parsed: GenerateAppAccessQuery, grant: GrantNode) -> str:
    """V4, V5. The zone the application sits in, reached through its VRF.

    ``ServiceFabricApp.vrf`` and ``SecurityZone.vrf`` both peer ``IpamVRF``,
    and `SecurityZone.vrf` exists to record precisely this pairing -- its
    schema comment calls it "the thing that makes the firewall unavoidable
    rather than decorative".

    Both relationships are optional in the schema, so all three failures below
    are reachable with a model that loads cleanly.
    """
    name = _value(grant.name)
    application = _node_of(grant.application)
    if application is None:
        msg = f"grant {name!r} names no application; the destination zone cannot be derived"
        raise ValueError(msg)

    app_name = _value(application.name)
    vrf = _node_of(application.vrf)
    if vrf is None:
        msg = (
            f"application {app_name!r} has no VRF; the destination zone is derived from the "
            "VRF a zone hands off to, so there is nothing to match"
        )
        raise ValueError(msg)

    zones = [edge.node for edge in parsed.security_zone.edges if edge.node is not None]
    matching = [zone for zone in zones if getattr(_node_of(zone.vrf), "id", None) == vrf.id]

    if len(matching) != 1:
        found = ", ".join(sorted(_value(zone.name) or "?" for zone in matching)) or "none"
        msg = (
            f"application {app_name!r} is in VRF {_value(vrf.name)!r}, which {len(matching)} "
            f"security zones hand off to ({found}); the destination zone is ambiguous"
        )
        raise ValueError(msg)

    return matching[0].id


def derive_tcp_protocol(parsed: GenerateAppAccessQuery, grant_name: str) -> str:
    """The ``tcp`` SecurityIPProtocol every generated service object needs."""
    for edge in parsed.security_ip_protocol.edges:
        if edge.node is not None and _value(edge.node.name) == TCP:
            return edge.node.id

    msg = (
        f"grant {grant_name!r} needs the {TCP!r} SecurityIPProtocol to build a service "
        "object, and the firewall model declares none"
    )
    raise ValueError(msg)


def index_address_book(
    parsed: GenerateAppAccessQuery,
) -> tuple[dict[str, Existing], frozenset[int]]:
    """Existing book entries by the IPAM address they wrap, and indexes in use.

    Keyed on the wrapped address rather than on a name, so an entry someone
    wrote by hand -- ``access-portal`` is exactly this shape -- is referenced
    instead of being duplicated under a generated name.

    The name comes back too, because it is the only thing distinguishing an
    entry this generator created on an earlier run from one it must not touch.
    See `Existing` for why that distinction is load bearing.
    """
    by_address: dict[str, Existing] = {}
    taken: set[int] = set()

    for edge in parsed.security_generic_address.edges:
        node = edge.node
        if node is None:
            continue

        book_index = _value(getattr(node, "book_index", None))
        if book_index is not None:
            taken.add(int(book_index))

        wrapped = _node_of(getattr(node, "ip_address", None))
        if wrapped is not None:
            by_address[wrapped.id] = Existing(id=node.id, name=_value(getattr(node, "name", None)))

    return by_address, frozenset(taken)


def index_tcp_services(parsed: GenerateAppAccessQuery) -> dict[int, Existing]:
    """Existing TCP service objects by port.

    Adoption is keyed on ``(protocol, port)`` and never on a name. The
    firewall declares ``junos-http`` and ``junos-https``; a grant for 80 or 443
    must reference those rather than declare a second application for the same
    port, or the rendered configuration stops reading like the hand-written
    rules beside it.
    """
    by_port: dict[int, Existing] = {}

    for edge in parsed.security_service.edges:
        node = edge.node
        if node is None:
            continue
        protocol = _node_of(node.ip_protocol)
        if protocol is None or _value(protocol.name) != TCP:
            continue
        port = _value(node.port)
        if port is None:
            continue
        by_port[int(port)] = Existing(id=node.id, name=_value(node.name))

    return by_port


def validate_model(parsed: GenerateAppAccessQuery) -> GrantContext:
    """Resolve and check everything before a single object is written.

    Raises:
        ValueError: naming the object and the field, for each of V2 to V8 in
            the feature's data model. V1 -- approval -- is checked by the
            caller, because an unapproved grant is a no-op rather than a
            failure.
    """
    grant = parsed.target.edges[0].node if parsed.target.edges else None
    if grant is None:
        msg = "no ServiceAppAccess matched the requested name"
        raise ValueError(msg)

    name = _value(grant.name)
    ports = normalise_ports(grant)
    policy_id = derive_policy(parsed, name)
    destination_zone_id = derive_destination_zone(parsed, grant)

    # V7. All three are mandatory in the schema, so a null here means the
    # query returned a grant whose peer was deleted out from under it.
    source_zone = _node_of(grant.source_zone)
    source_address = _node_of(grant.source_address)
    vip = _node_of(grant.destination_vip)
    for label, node in (
        ("source_zone", source_zone),
        ("source_address", source_address),
        ("destination_vip", vip),
    ):
        if node is None:
            msg = f"grant {name!r} has no {label}; the rule cannot be built"
            raise ValueError(msg)

    # V8. A grant whose source and destination resolve to the same zone is an
    # intrazone policy, which this firewall's model does not express.
    if source_zone.id == destination_zone_id:
        msg = (
            f"grant {name!r} resolves to an intrazone rule: its source zone and its "
            "application's zone are the same, and an intrazone policy is not modelled here"
        )
        raise ValueError(msg)

    entries_by_address, taken = index_address_book(parsed)
    application = _node_of(grant.application)

    return GrantContext(
        grant=grant,
        grant_name=name,
        ports=ports,
        policy_id=policy_id,
        destination_zone_id=destination_zone_id,
        source_zone_id=source_zone.id,
        source_address_id=source_address.id,
        vip_id=vip.id,
        vip_address=_value(vip.address),
        firewall_id=derive_firewall(parsed),
        tcp_protocol_id=derive_tcp_protocol(parsed, name),
        application_name=_value(application.name) if application else None,
        requester=_value(grant.requester),
        existing_vip_entry=entries_by_address.get(vip.id),
        taken_book_indexes=taken,
        services_by_port=index_tcp_services(parsed),
    )


class AppAccessGenerator(InfrahubGenerator):
    """Materialize an approved access grant as firewall objects."""

    async def generate(self, data: dict) -> None:
        """Build the rule an approved grant asks for, or do nothing."""
        parsed = GenerateAppAccessQuery(**data)

        grant = parsed.target.edges[0].node if parsed.target.edges else None
        if grant is None:
            msg = "no ServiceAppAccess matched the requested name"
            raise ValueError(msg)

        # V1, before anything else. An unapproved grant materializes nothing --
        # and withdraws anything an earlier approved run left behind.
        if not is_approved(grant):
            await self._withdraw(parsed, grant)
            return

        try:
            context = validate_model(parsed)
        except ValueError:
            await self._set_status(grant.id, "error")
            raise

        vip_entry_id = await self._upsert_vip_entry(context)
        service_ids = await self._upsert_services(context)
        rule_id = await self._upsert_rule(context, vip_entry_id, service_ids)

        await self._link_granted_rules(context, [rule_id])
        await self._set_status(grant.id, "active")
        await self._advertise(context, derive_advertisement(grant))
        await self._rerender_firewall(context.firewall_id)

    async def _upsert_vip_entry(self, context: GrantContext) -> str:
        """The address-book entry for the destination VIP.

        A **foreign** entry already wrapping this address -- `access-portal` is
        the hand-written case -- is referenced and never written, so it never
        joins the tracking group and is never deleted when the grant is
        revoked.

        An entry this generator created on an earlier run is written **again**,
        every run. Skipping it because "it already exists" is what leaves it out
        of this run's tracking group, and `delete_unused_nodes=True` then
        deletes it while the rule referencing it survives.
        """
        existing = context.existing_vip_entry
        if existing is not None and not existing.is_ours(context.vip_entry_name):
            self.logger.info("Referencing the existing address-book entry for the destination VIP")
            return existing.id

        entry = await self.client.create(
            kind="SecurityIPAMIPAddress",
            data={
                "name": context.vip_entry_name,
                "description": (f"{context.application_name} VIP, granted to {context.requester}"),
                "ip_address": context.vip_id,
                # Without this the entry is referenced by the rule and never
                # declared in the book, and the configuration does not load.
                "book_index": context.book_index,
            },
        )
        await entry.save(allow_upsert=True)
        self.logger.info("Wrote address-book entry %s", context.vip_entry_name)
        return entry.id

    async def _upsert_services(self, context: GrantContext) -> list[str]:
        """One service object per permitted port.

        Same split as the address entry: the firewall's own `junos-http` and
        `junos-https` are referenced and never written, and anything this grant
        generated is written again every run so it stays in the tracking group.
        """
        service_ids: list[str] = []

        for port in context.ports:
            existing = context.services_by_port.get(port)
            if existing is not None and not existing.is_ours(context.service_name(port)):
                self.logger.info("Referencing the existing service object for tcp/%s", port)
                service_ids.append(existing.id)
                continue

            service = await self.client.create(
                kind="SecurityService",
                data={
                    "name": context.service_name(port),
                    "description": f"tcp/{port}, granted by {context.grant_name}",
                    "port": port,
                    "ip_protocol": context.tcp_protocol_id,
                },
            )
            await service.save(allow_upsert=True)
            self.logger.info("Wrote service object for tcp/%s", port)
            service_ids.append(service.id)

        return service_ids

    async def _upsert_rule(self, context: GrantContext, vip_entry_id: str, service_ids: list[str]) -> str:
        """The permit rule itself.

        ``log`` and ``log_session_close`` are both true because a grant is an
        audited exception to the baseline, which is the distinction
        `schemas/security_extensions.yml` records as behaviour rather than
        formatting.
        """
        rule = await self.client.create(
            kind="SecurityPolicyRule",
            data={
                "name": context.rule_name,
                "index": context.rule_index,
                "action": "permit",
                "log": True,
                "log_session_close": True,
                # The guard that makes this safe against a hand-maintained
                # firewall. Set only on what this generator creates.
                "managed_by_service": True,
                "policy": context.policy_id,
                "source_zone": context.source_zone_id,
                "destination_zone": context.destination_zone_id,
                "source_address": [context.source_address_id],
                "destination_address": [vip_entry_id],
                "destination_services": service_ids,
            },
        )
        await rule.save(allow_upsert=True)
        self.logger.info("Created rule %s at index %s", context.rule_name, context.rule_index)
        return rule.id

    async def _link_granted_rules(self, context: GrantContext, rule_ids: list[str]) -> None:
        """Point the grant at the rules this run produced.

        ``update_group_context=False`` is not optional. The grant is this
        generator's *target*, not something it owns; letting it join the
        tracking group would make it a deletion candidate on any later run that
        did not touch it.
        """
        grant = await self.client.get(kind="ServiceAppAccess", id=context.grant.id)

        # A RelationshipManager is not a list: it must be fetched before its
        # members can be edited, and it is edited through add/remove rather
        # than assignment.
        granted = grant.granted_rules  # type: ignore[attr-defined]
        await granted.fetch()

        current = set(granted.peer_ids)
        wanted = set(rule_ids)
        for missing in sorted(wanted - current):
            granted.add(missing)
        for stale in sorted(current - wanted):
            granted.remove(stale)

        if wanted != current:
            await grant.save(update_group_context=False)
            self.logger.info("Linked %s rule(s) to the grant", len(wanted))

    async def _withdraw(self, parsed: GenerateAppAccessQuery, grant: GrantNode) -> None:
        """Remove what an earlier approved run created for this grant.

        THE TRACKING CONTEXT DOES NOT COVER THIS, and assuming it did was a
        real bug. `InfrahubGroupContext.update_group` opens with
        ``if not members: return`` -- so a run that touches nothing prunes
        nothing. Tracking handles *narrowing* a grant, where the run still
        writes a rule and the dropped service objects fall out of a non-empty
        member set. It does not handle *revoking* one, where the run writes
        nothing at all. Measured on a live branch: un-approving a grant left its
        rule, its address-book entry and its service object exactly where they
        were.

        Deletion is by the deterministic generated name and nothing else, so a
        referenced object is never a candidate: `junos-https` is not named
        ``svc-<grant>-tcp-443`` and survives, as does a hand-written address
        entry that happened to wrap the same VIP.

        Order matters -- the rule references the address entry and the service
        objects, so it goes first.
        """
        name = _value(grant.name)
        rule_name = f"svc-{name}"
        vip_entry_name = f"{rule_name}-vip"
        service_prefix = f"{rule_name}-{TCP}-"

        removed = 0
        for rule in _edges_of(grant.granted_rules):
            if _value(rule.name) != rule_name:
                continue
            await self.client.delete(kind="SecurityPolicyRule", id=rule.id)
            removed += 1

        for edge in parsed.security_generic_address.edges:
            node = edge.node
            if node is not None and _value(getattr(node, "name", None)) == vip_entry_name:
                await self.client.delete(kind="SecurityIPAMIPAddress", id=node.id)
                removed += 1

        for edge in parsed.security_service.edges:
            node = edge.node
            if node is not None and (_value(node.name) or "").startswith(service_prefix):
                await self.client.delete(kind="SecurityService", id=node.id)
                removed += 1

        if removed:
            self.logger.info("Grant %r is not approved; withdrew %s object(s)", name, removed)
            # Back to "ordered, not built". Leaving it `active` would claim a
            # rule that no longer exists.
            await self._set_status(grant.id, "provisioning")
            await self._withdraw_advertisement(name, derive_advertisement(grant))
            await self._rerender_firewall(derive_firewall(parsed))
        else:
            self.logger.info("Grant %r is not approved; nothing to materialize", name)

    async def _advertise(self, context: GrantContext, advertisement: Advertisement | None) -> None:
        """Make the grant's VIP routable from its source zone.

        The third leg. Without it the firewall permits a session to somewhere
        the border leaf never re-advertises: permitted and unroutable, which
        `schemas/service/access_services.yml` warns about on `destination_vip`.

        **The write does not reach a switch on its own.** It lands in the
        device's `avd_custom_hostvars`, which `generate-avd-device-hostvar`
        reads -- and that generator is registered `execute_after_merge: false`
        deliberately, because the AVD chain is expensive and is run explicitly.
        So the model is correct immediately and the switch follows on the next
        `invoke avd`, exactly as it does for any other fabric change.

        DEVICE SCOPE, not fabric scope. `_merge_lists` composes the two by
        `name` and then by `sequence`, so this adds a sequence to
        `PL-DC-ADVERTISED-BRANCH` rather than replacing what the fabric
        declares. Writing at fabric scope would put a per-grant value into the
        attribute carrying the hand-authored baseline for every device.
        """
        if advertisement is None:
            self.logger.info(
                "Zone advertises nothing from the DC, so %r is permitted but not made routable",
                context.grant_name,
            )
            return
        if context.vip_address is None:
            self.logger.warning("The destination VIP carries no address; nothing to advertise")
            return

        merged = advertisement_entry(
            advertisement.hostvars,
            advertisement.prefix_list,
            context.prefix_sequence,
            f"permit {context.vip_address}",
        )
        await self._write_hostvars(advertisement, merged)
        self.logger.info(
            "Advertised %s from %s via %s (seq %s); run `invoke avd` to reach the switch",
            context.vip_address,
            advertisement.device_name,
            advertisement.prefix_list,
            context.prefix_sequence,
        )

    async def _withdraw_advertisement(self, grant_name: str, advertisement: Advertisement | None) -> None:
        """Stop advertising a revoked grant's VIP.

        Keyed on this grant's own sequence, so another grant's entry in the same
        prefix list survives -- the device-scope list is shared between grants
        the way the address book is.
        """
        if advertisement is None:
            return

        sequence = _stable_offset(grant_name, PREFIX_SEQUENCE_FLOOR)
        merged = advertisement_removed(advertisement.hostvars, advertisement.prefix_list, sequence)
        if merged == advertisement.hostvars:
            return

        await self._write_hostvars(advertisement, merged)
        self.logger.info(
            "Withdrew the advertisement from %s; run `invoke avd` to reach the switch",
            advertisement.device_name,
        )

    async def _write_hostvars(self, advertisement: Advertisement, hostvars: dict[str, Any]) -> None:
        """Save the device's custom hostvars.

        Through the NON-tracking client, and never with group context. The
        switch is not this generator's to own: adding it to the tracking group
        would make it a deletion candidate on any later run that did not touch
        it, and this generator would eventually delete a leaf.
        """
        device = await self._init_client.get(kind="DcimFabricSwitch", id=advertisement.device_id)
        device.avd_custom_hostvars.value = hostvars  # type: ignore[union-attr]
        await device.save(update_group_context=False)

    async def _rerender_firewall(self, firewall_id: str | None) -> None:
        """Ask for the firewall's artifact to be re-rendered.

        WITHOUT THIS THE RULE NEVER REACHES THE DEVICE. An artifact is
        regenerated when its *target* changes, and the target here is the
        firewall -- a new `SecurityPolicyRule` is not a change to `fw1`. So the
        objects appear, the rendered artifact keeps its old checksum, and the
        reconciler compares the device against stale output and reports no
        difference. Measured: the generator ran on merge, and three and a half
        minutes later the artifact checksum had not moved.

        Infrahub's trigger rules cannot close this -- `CoreGeneratorAction` and
        `CoreGroupAction` are the only actions, and neither renders an artifact
        -- so the generator that changed the configuration asks for the
        re-render itself.

        Best effort, and deliberately so. The objects are already written and
        correct by this point; raising here would skip the tracking context's
        `update_group`, leaving this run's objects outside the group they should
        own. A failed request is recoverable by regenerating the artifact, so it
        is logged loudly rather than thrown.

        Uses the NON-tracking client: the firewall is not this generator's to
        own, and fetching it through the tracking client risks making it a
        deletion candidate.
        """
        if firewall_id is None:
            self.logger.warning(
                "No firewall resolved, so %r was not re-rendered; the rule will not reach a device "
                "until the artifact is regenerated",
                FIREWALL_ARTIFACT,
            )
            return

        try:
            # NOT `firewall.artifact_generate(...)`, WHICH IS A NO-OP ON A BRANCH.
            #
            # The SDK helper posts to `/api/artifact/generate/{id}` with no
            # `branch` parameter, and that endpoint regenerates against `main`
            # when none is given. On a branch the objects were therefore written,
            # this method logged that it had asked for a re-render, and the
            # branch's artifact kept its old checksum -- so a proposed change
            # showed the new rule as data and no configuration diff at all.
            # Measured: identical checksums on `main` and the branch after the
            # generator ran, and the rule appearing the moment the same endpoint
            # was called with `?branch=`.
            #
            # That is the very failure this method exists to prevent, and a
            # branch is where AGENTS.md says this work should happen -- so the
            # helper was hiding the bug in the place it mattered most.
            branch = self.branch_name
            # `nodes` NAMES THE ARTIFACT, NOT ITS TARGET, and passing the
            # firewall's id instead is accepted and silently regenerates
            # nothing -- the endpoint matches it against no artifact and
            # returns 200. Measured, and it looks exactly like the missing
            # branch does.
            artifact = await self._init_client.get(
                kind="CoreArtifact",
                name__value=FIREWALL_ARTIFACT,
                object__ids=[firewall_id],
                branch=branch,
            )
            definition = await self._init_client.get(
                kind="CoreArtifactDefinition",
                artifact_name__value=FIREWALL_ARTIFACT,
                branch=branch,
            )
            url = f"{self._init_client.address}/api/artifact/generate/{definition.id}"
            if branch:
                url = f"{url}?branch={quote(branch, safe='')}"
            # `_post` is private, and is what the SDK's own `generate()` uses;
            # there is no public call that takes a branch.
            response = await self._init_client._post(url, payload={"nodes": [artifact.id]})  # noqa: SLF001
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - see the docstring; never fatal here
            self.logger.warning(
                "Could not re-render %r (%s). The objects are correct; regenerate the artifact "
                "or the reconciler will keep comparing against stale output",
                FIREWALL_ARTIFACT,
                exc,
            )
            return

        self.logger.info("Requested a re-render of %r", FIREWALL_ARTIFACT)

    async def _set_status(self, grant_id: str, status: str) -> None:
        """Record the outcome on the grant.

        ``error`` is distinct from ``provisioning`` on purpose: both leave no
        technical objects behind, and "tried to build and failed" is otherwise
        indistinguishable from "not built yet".
        """
        grant = await self.client.get(kind="ServiceAppAccess", id=grant_id)
        if _value(grant.status) == status:  # type: ignore[attr-defined]
            return
        grant.status.value = status  # type: ignore[union-attr]
        await grant.save(update_group_context=False)
        self.logger.info("Grant status set to %s", status)
