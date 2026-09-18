"""Turn an application access grant into the firewall objects that permit it.

`ServiceAppAccess` was the one service kind that produced nothing: a schema, a
menu entry and six contract tests, but no generator, no transform and no
artifact. This is the generator that makes it act.

A grant becomes three things -- an address-book entry for the
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

* **A grant is gated by its BRANCH, not by a field.** There was an `approved`
  Boolean here, and it was a second gate in front of one the workflow already
  has: a request is made on a branch and reaches no device until its proposed
  change merges. Two gates can only disagree, and the branch is the better
  record -- it has a reviewer, a diff and a history. Because the generators run
  on the branch, that reviewer sees the rule, the service objects and the
  re-rendered firewall configuration before deciding, which the Boolean never
  showed them.

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

import yaml
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
    """The fabric side of the grant's source zone, or None if it has none.

    The zone may be DERIVED from `source_site`, so this has to look in the same
    two places `validate_model` does. Reading only `source_zone` would give a
    site-based grant its firewall rule and silently no advertisement -- the
    permitted-but-unroutable outcome the model exists to prevent.
    """
    site = _node_of(grant.source_site)
    zone = _node_of(grant.source_zone) or (_node_of(getattr(site, "security_zone", None)) if site else None)
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
    vip_is_block: bool = False
    """True when the destination is the application's `vip_block` rather than a
    single VIP the requester named. The address-book entry is then a prefix."""
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


WITHDRAWN_STATUSES = frozenset({"decommissioning", "decommissioned"})


def is_withdrawn(grant: GrantNode) -> bool:
    """Whether this grant should hold any firewall objects at all.

    REPLACES THE `approved` GATE, which was a second gate in front of one the
    workflow already has: a grant is requested on a branch and reaches no device
    until its proposed change merges. Two gates can only disagree -- approved
    but unmerged changed nothing, and merged but unapproved left an object on
    main doing nothing and saying nothing about why.

    `decommissioning` counts as gone rather than going, which is what every
    other service kind here means by it: the alternative is a window in which
    the intent is withdrawn and the firewall still permits the session.
    """
    return _value(grant.status) in WITHDRAWN_STATUSES


def advertised_service_ports(manifests: Any, service_selector: Any = None) -> list[int]:
    """The TCP ports the application's ADVERTISED Services answer on.

    THIS IS THE PORT A FIREWALL RULE NEEDS, and it is not the one the
    application's network policy names. `policy_allow_ports` was read here for
    two cycles and is the CiliumNetworkPolicy's ingress port, applied to the
    PODS: 8080 for nfd41-demo, whose Service maps ``port: 80`` to
    ``targetPort: 8080``. The firewall's destination is the VIP, so the derived
    rule permitted 8080, the VIP answered only on 80, and the grant was
    rendered, merged, pushed and confirmed while reaching nothing. Deriving
    from the Service closes that by construction -- the same object decides
    both the VIP's port and the rule's.

    ONLY ADVERTISED SERVICES COUNT. A `ClusterIP` Service has no VIP and is
    unreachable from the branch, so its ports must never widen a rule;
    nfd41-demo's `backend` is exactly that, on 8080, and including it would
    have reintroduced the wrong port by another route. A Service qualifies when
    it is `type: LoadBalancer` or carries the application's `service_selector`
    labels, which is what gives it an address in the first place.

    Non-TCP entries are skipped: a rule here is TCP, and widening it to UDP
    because a Service mentions one is a different permission.
    """
    wanted = _selector_labels(service_selector)
    ports: list[int] = []
    for document in manifests or []:
        if not isinstance(document, dict) or document.get("kind") != "Service":
            continue
        spec = document.get("spec")
        if not isinstance(spec, dict):
            continue
        labels = ((document.get("metadata") or {}).get("labels")) or {}
        advertised = spec.get("type") == "LoadBalancer" or (
            bool(wanted) and all(str(labels.get(k)) == v for k, v in wanted.items())
        )
        if not advertised:
            continue
        for entry in spec.get("ports") or []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("protocol", "TCP")).upper() != "TCP":
                continue
            try:
                ports.append(int(entry["port"]))
            except (KeyError, TypeError, ValueError):
                continue
    return ports


def _selector_labels(service_selector: Any) -> dict[str, str]:
    """``["nfd41.lab/advertise=true"]`` as ``{"nfd41.lab/advertise": "true"}``.

    Takes the UNWRAPPED list, like `manifests` beside it, so both arguments to
    `advertised_service_ports` are plain data and the function is testable
    without building query models.
    """
    labels: dict[str, str] = {}
    for item in service_selector or []:
        text = str(item)
        if "=" not in text:
            continue
        key, _, value = text.partition("=")
        labels[key.strip()] = value.strip()
    return labels


def normalise_ports(grant: GrantNode, derived: list[int] | None = None) -> list[int]:
    """V2, V3. The permitted TCP ports, sorted, validated, de-duplicated.

    A grant that names NO ports takes the ports its application's ADVERTISED
    SERVICES answer on, because the application already knows what it serves
    and the requester mostly does not. `derived` is that list, computed by
    `advertised_service_ports` from the manifests.

    Naming ports explicitly still works, and is how you ask for a SUBSET.

    An EMPTY result is rejected rather than read as "all ports". That is the
    worst defect this generator could have, and the lab's own `FirewallAccess`
    CRD makes the same choice with ``minItems: 1``.

    IT REFUSES RATHER THAN GUESSING when nothing can be derived, and that is a
    deliberate change of behaviour. The previous fallback -- the application's
    `policy_allow_ports` -- is always populated and always plausible, so a
    wrong port was never once reported as wrong: the rule rendered, merged,
    pushed and confirmed, and the only symptom was a healthy app nobody could
    reach. A request that stops with a message naming the application costs a
    minute; the silent version cost an afternoon.
    """
    raw = _value(grant.ports) or derived
    name = _value(grant.name)

    if not raw:
        msg = (
            f"grant {name!r} names no ports and no advertised Service was found on its "
            "application to derive them from; name the ports explicitly, or give the "
            "application a LoadBalancer Service in its manifests. An empty list is "
            "rejected rather than read as 'all ports', which is what a "
            "permit-everything rule would mean"
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

        # Both shapes: an entry wrapping a host address, and one wrapping a
        # prefix. A derived destination is a `vip_block`, so indexing only
        # `ip_address` would miss the entry an earlier run created and write a
        # second one beside it every time.
        for field_name in ("ip_address", "ip_prefix"):
            wrapped = _node_of(getattr(node, field_name, None))
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


def validate_model(parsed: GenerateAppAccessQuery, derived_ports: list[int] | None = None) -> GrantContext:
    """Resolve and check everything before a single object is written.

    Raises:
        ValueError: naming the object and the field, for each of V2 to V8 in
            the feature's data model. V1 -- approval -- is checked by the
            caller, because a withdrawn grant is a no-op rather than a
            failure.
    """
    grant = parsed.target.edges[0].node if parsed.target.edges else None
    if grant is None:
        msg = "no ServiceAppAccess matched the requested name"
        raise ValueError(msg)

    name = _value(grant.name)
    # The application's advertised Services are the fallback for ports it did
    # not name; `generate` resolves them, because the manifests may be an
    # attachment that has to be downloaded.
    ports = normalise_ports(grant, derived_ports)
    policy_id = derive_policy(parsed, name)
    destination_zone_id = derive_destination_zone(parsed, grant)

    # V7. All three are mandatory in the schema, so a null here means the
    # query returned a grant whose peer was deleted out from under it.
    # THE SOURCE, named or derived from where the requester sits. A person
    # knows their site far better than they know which security zone it is, so
    # a grant may name a `source_site` and take both from it. Naming the zone
    # or the address directly WINS, which is how the platform team asks for a
    # source that is not somebody's desk.
    site = _node_of(grant.source_site)
    source_zone = _node_of(grant.source_zone) or (_node_of(getattr(site, "security_zone", None)) if site else None)
    source_address = _node_of(grant.source_address) or (
        _node_of(getattr(site, "security_source_address", None)) if site else None
    )
    for label, node in (
        ("source_zone", source_zone),
        ("source_address", source_address),
    ):
        if node is None:
            hint = (
                f" and its site {_value(site.name)!r} maps to none"
                if site is not None
                else " and it names no source_site to derive one from"
            )
            msg = f"grant {name!r} has no {label}{hint}; the rule cannot be built"
            raise ValueError(msg)

    # THE DESTINATION, named or derived. A requester cannot honestly know the
    # VIP -- Cilium assigns it to a LoadBalancer service at runtime -- so a
    # grant naming none permits to the application's own `vip_block`, the set of
    # addresses it can ever be advertised on.
    application_node = _node_of(grant.application)
    vip = _node_of(grant.destination_vip)
    vip_is_block = False
    if vip is None:
        vip = _node_of(getattr(application_node, "vip_block", None)) if application_node else None
        vip_is_block = vip is not None
    if vip is None:
        msg = (
            f"grant {name!r} names no destination_vip and its application has no "
            "vip_block; there is no address to permit"
        )
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

    return GrantContext(
        grant=grant,
        grant_name=name,
        ports=ports,
        policy_id=policy_id,
        destination_zone_id=destination_zone_id,
        source_zone_id=source_zone.id,
        source_address_id=source_address.id,
        vip_id=vip.id,
        vip_address=_value(vip.prefix) if vip_is_block else _value(vip.address),
        vip_is_block=vip_is_block,
        firewall_id=derive_firewall(parsed),
        tcp_protocol_id=derive_tcp_protocol(parsed, name),
        application_name=_value(application_node.name) if application_node else None,
        requester=_value(grant.requester),
        existing_vip_entry=entries_by_address.get(vip.id),
        taken_book_indexes=taken,
        services_by_port=index_tcp_services(parsed),
    )


class AppAccessGenerator(InfrahubGenerator):
    """Materialize an access grant as firewall objects."""

    async def generate(self, data: dict) -> None:
        """Build the rule this grant asks for, or withdraw what it had."""
        parsed = GenerateAppAccessQuery(**data)

        grant = parsed.target.edges[0].node if parsed.target.edges else None
        if grant is None:
            msg = "no ServiceAppAccess matched the requested name"
            raise ValueError(msg)

        # Withdrawal first. `decommissioning` counts as gone rather than going,
        # and it removes anything an earlier run left behind.
        if is_withdrawn(grant):
            await self._withdraw(parsed, grant)
            return

        try:
            derived_ports = await self._advertised_ports(_node_of(grant.application))
            context = validate_model(parsed, derived_ports)
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

    async def _advertised_ports(self, application: Any) -> list[int]:
        """The ports this application's advertised Services answer on.

        The manifests are a `CoreFileObject` attachment far more often than an
        inline attribute -- nfd41-demo's are -- and the query returns the
        file's METADATA only, its content living in object storage. So the node
        is re-fetched by id and `download_file()` called on it, which is the
        same two-step `crossplane_fabric_app._payload` does for the same
        reason: `download_file` is a method on an SDK node, not on the
        generated query model.

        A failure here returns nothing rather than raising, and
        `normalise_ports` then refuses with a message naming the grant. An
        unreadable payload must not be indistinguishable from an application
        that genuinely advertises nothing, but neither should it abort a grant
        that names its own ports.
        """
        if application is None:
            return []

        manifests = _value(getattr(application, "manifests", None))
        stub = _node_of(getattr(application, "manifests_file", None))
        if stub is not None:
            try:
                file_node = await self._init_client.get(kind="ServiceFabricAppManifestsFile", id=stub.id)
                content = await file_node.download_file()
                text = content.decode() if isinstance(content, bytes) else content
                manifests = yaml.safe_load(text)
            except Exception:  # noqa: BLE001 - see the docstring: refuse, do not abort
                return []

        if isinstance(manifests, str):
            try:
                manifests = yaml.safe_load(manifests)
            except yaml.YAMLError:
                return []
        if not isinstance(manifests, list):
            return []

        return advertised_service_ports(manifests, _value(getattr(application, "service_selector", None)))

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

        # A DERIVED destination is the application's `vip_block`, which is a
        # prefix rather than a host -- so it needs the prefix-shaped address
        # kind and the prefix-shaped field. Wrapping a prefix id in
        # `SecurityIPAMIPAddress.ip_address` is refused by the schema.
        kind = "SecurityIPAMIPPrefix" if context.vip_is_block else "SecurityIPAMIPAddress"
        peer_field = "ip_prefix" if context.vip_is_block else "ip_address"
        described = "VIP block" if context.vip_is_block else "VIP"

        entry = await self.client.create(
            kind=kind,
            data={
                "name": context.vip_entry_name,
                "description": (f"{context.application_name} {described}, granted to {context.requester}"),
                peer_field: context.vip_id,
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
        """Remove what an earlier run created for this grant.

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
                # THE KIND COMES FROM THE NODE, because `_upsert_vip_entry`
                # chooses between two of them: a derived destination is the
                # application's `vip_block`, which is a prefix, so the entry is
                # a `SecurityIPAMIPPrefix` rather than a `SecurityIPAMIPAddress`.
                # Hard-coding the host kind here made withdrawal fail for every
                # grant that took the derived path -- the common one -- with
                # `exists, but it is a SecurityIPAMIPPrefix`, leaving the entry
                # declared in the address book and referenced by nothing.
                await self.client.delete(kind=node.typename__, id=node.id)
                removed += 1

        for edge in parsed.security_service.edges:
            node = edge.node
            if node is not None and (_value(node.name) or "").startswith(service_prefix):
                await self.client.delete(kind="SecurityService", id=node.id)
                removed += 1

        if removed:
            self.logger.info("Grant %r is withdrawn; removed %s object(s)", name, removed)
            # `decommissioned` -- "withdrawn" -- and NOT `provisioning`, which
            # is what this wrote while `approved` was the gate. Status was an
            # independent label then, so "ordered, not built" was a fair
            # description of an un-approved grant. Now status IS the gate, and
            # writing a non-withdrawn value here erases the very signal that
            # caused the withdrawal: the next run reads `provisioning`, decides
            # the grant is live, and rebuilds the rule it just deleted. Measured
            # on a live branch -- two consecutive runs went withdraw, rebuild,
            # leaving the grant `active` and the firewall permitting a session
            # somebody had revoked.
            #
            # `decommissioned` is terminal and is in WITHDRAWN_STATUSES, so the
            # second run is a no-op and the generator is idempotent again. It
            # mirrors the build path's `provisioning` -> `active`.
            await self._set_status(grant.id, "decommissioned")
            await self._withdraw_advertisement(name, derive_advertisement(grant))
            await self._rerender_firewall(derive_firewall(parsed))
        else:
            self.logger.info("Grant %r is withdrawn; nothing to remove", name)

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
