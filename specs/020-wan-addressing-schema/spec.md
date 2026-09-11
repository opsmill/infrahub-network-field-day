# Schema Design Specification: Making the WAN's Addressing Real

> **This is a schema design spec.** The implementing agent MUST use the `infrahub-managing-schemas` skill to build and validate all schema definitions.

**Feature Branch**: `020-wan-addressing-schema`
**Created**: 2026-09-11
**Status**: Draft
**Input**: "Tackle the next item needed to get to the end goal."

## Why this cycle exists

The end goal is fixed by cycle 010's opening request: *"ensure that we can contain all of the
information that is in the lab: the ISP, the branches, and the firewall,"* and then render it.
The fabric renders through AVD. Crossplane renders through cycles 011 and 017. The WAN does
not render at all, and cycle 019 — the most recent — names its own successor in its first
line of Out of Scope: *"Rendering FRR configuration for the ISP, CE and branch routers from
these services."* That is the next deliverable, and `../lab/wan/rendered/*/frr.conf` is a
six-file golden oracle waiting for it.

**That transform cannot be written yet, and this cycle is why.** Walking the six rendered
configs line by line against the graph turns up one class of failure over and over: the
addresses the configs are made of are not in the model. `objects/33_nfd41_wan.yml` records
the provider side of acme's circuit like this:

```yaml
- side: a
  name: isp-pe1-eth2
  description: "Provider side, isp-pe1 eth2, 10.51.10.1/30"
```

The interface is a string, the address is prose inside a sentence, and neither is queryable.
Cycle 010 already forbade exactly this — assumption 4, *"Free-text CIDRs are the failure mode
this model exists to remove"*, and SC-008, *"No new node restates a prefix or an address as
text where an IPAM object exists for it."* The rule was written; the WAN seed broke it,
because at the time nothing read those fields and nothing caught it. A renderer reads them.

### What the rendered configs need, and what the graph has

| The configs need | Today |
| --- | --- |
| Router IDs — `10.50.0.1`, `10.50.0.2`, `10.52.0.2`, `10.60.10.1`, `10.60.20.1`, `10.70.255.1` | Nothing |
| Announced loopbacks — `network 10.50.0.1/32` | No interface, no address |
| PE↔CE circuit addresses — `10.51.10.1/.2`, `10.51.20.1/.2`, `10.51.11.1/.2` | Prose in endpoint descriptions; the `/30` prefixes exist |
| The iBGP pair `10.50.255.1/.2` and the transit pair `10.52.0.1/.2` | Prefixes only |
| Interfaces `eth1`/`eth2`/`eth3` on the WAN routers | None exist |
| The provider's AS 65500 and the internet's AS 64500 | 65500 is prose in a provider description |
| eBGP sessions PE↔CE, the pe1↔pe2 iBGP, the pe2↔internet transit | No session objects; `WanSite.bgp_session` is empty |
| The acme-dr static route inside `CUST_ACME` | `WanSite.static_routes` is empty |
| Site ASNs, LAN prefixes, DC service prefixes, customer aggregate, tenant cloud subnets, the internet-access flag | **All present and correct** |

The right-hand column splits cleanly in two. Most rows are *missing object data* — interfaces,
addresses, ASNs, sessions — and seeding those is the cycle after this one. A short tail are
rows with **nowhere to put the data at all**, and those are schema. This cycle is that tail,
and nothing else.

Five gaps, each traceable to a line in a rendered config:

1. A circuit end cannot name the interface that terminates it, so `10.51.10.1` has no
   structural home even once the interface exists.
2. `WanInternetPeering` has a `peer_asn` but no session, so `neighbor 10.52.0.2 remote-as
   64500` on isp-pe2 is unrepresentable.
3. Nothing carries a router ID, so `bgp router-id` has no source.
4. Nothing distinguishes a loopback from any other virtual interface, so `network
   10.50.0.1/32` cannot be derived. *(Phase 0 found this one already solved — see FR-020.)*
5. `WanSite.bgp_session` is cardinality one, but a PE↔CE session is two `RoutingBGPNeighbor`
   objects — one per device — and the site needs both.

Keeping this cycle to those five is deliberate. Everything else the WAN render needs is either
already modelled or is object data, and the repository's rule is one artifact type per cycle.

## Schema Files

All schema definitions live in `schemas/*.yml`. Each file must start with:

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"
```

Two files are touched. `schemas/wan/wan.yml` owns `WanSite` and `WanInternetPeering` and is
edited directly. `DcimCircuitEndpoint` and `DcimInterface` are **adopted marketplace kinds** —
`objects/33_nfd41_wan.yml` records the adoption, and `schemas/MARKETPLACE.md` governs it — so
they are extended through an `extensions:` block in a file this repository owns, never by
editing the vendored definition. The device-side `router_id` follows the established pattern in
`schemas/dcim_extensions.yml`.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A circuit end names its interface and its address (Priority: P1)

An engineer opens acme's HQ circuit in Infrahub and follows the A side to `isp-pe1`'s `eth2`,
and from that interface to the IP address `10.51.10.1/30`. Nothing is read out of a description
sentence. The Z side resolves the same way to `cust-acme-ce` `eth1` and `10.51.10.2/30`, which
is the pair that becomes `neighbor 10.51.10.2` on the PE and `neighbor 10.51.10.1` on the CE.

**Why this priority**: It is the largest gap and the one that unblocks the most rendered lines
— every PE↔CE neighbor statement on isp-pe1 and both customer edges. It is also the direct
remedy for the SC-008 violation, so it repays a debt as well as enabling a feature.

**Independent Test**: Load the schema and create a circuit endpoint that points at an interface
carrying an IP address; traverse endpoint → interface → address in one GraphQL query. Valuable
on its own even if the remaining stories are dropped, because the circuit model stops lying.

**Acceptance Scenarios**:

1. **Given** a `DcimCircuitEndpoint` and an `InterfacePhysical` on the same device, **When** the
   endpoint's interface relationship is set, **Then** the endpoint resolves to the interface and
   through it to every `IpamIPAddress` on that interface.
2. **Given** the schema is loaded, **When** an endpoint is created with no interface, **Then** it
   is accepted, because the branch's private fibre and any not-yet-cabled circuit must remain
   expressible.
3. **Given** the extension is applied, **When** the adopted circuit schema file is compared
   against its upstream form, **Then** it is unchanged.

---

### User Story 2 - Every BGP session in the WAN has a home (Priority: P2)

Each session the six configs emit can be found from the object that justifies it: a site's two
sessions from the `WanSite`, the transit session from the `WanInternetPeering`. A reviewer
asking "where does `neighbor 10.52.0.2 remote-as 64500` come from?" lands on the internet
peering, not on a device with no explanation attached.

**Why this priority**: Second because the session objects are worth little until the addresses
in story 1 exist for them to point at, and because a session is reachable from its device
regardless — this story is about making it reachable from the *intent*, which is what the
renderer walks.

**Independent Test**: Load the schema, attach two `RoutingBGPNeighbor` objects to one `WanSite`
and one to a `WanInternetPeering`, and query each from the service side.

**Acceptance Scenarios**:

1. **Given** a `WanSite` with a BGP attachment, **When** both the provider-side and
   customer-side neighbor objects are attached, **Then** both are returned from the site.
2. **Given** a `WanSite` with `attachment_kind: static`, **When** no session is attached,
   **Then** the site is valid, because acme's DR site runs no protocol at all.
3. **Given** a `WanInternetPeering`, **When** its session is attached, **Then** it resolves from
   the peering, and the peering's `peer_asn` and its session's remote AS describe the same
   neighbor.

---

### User Story 3 - A router knows its own ID, and a loopback says it is one (Priority: P3)

`isp-pe1` names the address that is its router ID, and its `10.50.0.1/32` loopback is
identifiable as a loopback rather than as an unlabelled virtual interface. A CE whose router ID
is its LAN-side address expresses that just as directly.

**Why this priority**: Smallest of the three and the most mechanical, but without it two lines
of every single rendered config — `bgp router-id` and the announced `network x/32` — have to be
guessed by the renderer from naming conventions, which is precisely the kind of inference this
model exists to delete.

**Independent Test**: Load the schema, set a device's router ID to an existing address object,
and create a virtual interface with the loopback role.

**Acceptance Scenarios**:

1. **Given** a device and an `IpamIPAddress`, **When** the address is set as the device's router
   ID, **Then** it resolves from the device, and the address need not sit on a loopback — a
   customer edge's router ID is its LAN address.
2. **Given** the interface role choices, **When** a virtual interface is created as a loopback,
   **Then** `loopback` is an accepted role.
3. **Given** an existing fabric device, **When** the schema is loaded, **Then** the device is
   unaffected, because the router ID is optional and AVD continues to derive its own.

---

### Edge Cases

- A circuit endpoint with no interface — the branch's private fibre into `border-leaf1` is not a
  purchased circuit and has no provider side; the relationship must stay optional.
- An interface that terminates no circuit — `eth3` on `isp-pe2` faces the internet router, and
  the transit link may or may not be modelled as a circuit.
- An interface carrying several addresses, or none — `ip_addresses` is already cardinality many
  and optional, and this cycle must not narrow it.
- A statically attached site with zero BGP sessions, and a BGP site with exactly two. Both are
  valid; a cardinality of one can express neither.
- A device with no router ID — every fabric device, which derives its own through AVD.
- Two sites of one tenant, each with its own sessions, which must not collide in a uniqueness
  constraint.
- An address that is a router ID *and* sits on an interface. It is one `IpamIPAddress` reached
  two ways, not two objects; nothing may force a copy.
- The adopted circuit schema being re-synced from the marketplace, which must not silently drop
  this repository's additions.

## Requirements *(mandatory)*

### Functional Requirements

#### Relationships

- **FR-001**: `DcimCircuitEndpoint` MUST gain an optional, cardinality-one relationship to the
  terminating interface, so a circuit end resolves to a real interface and through it to real
  addresses.
- **FR-002**: FR-001 MUST be delivered through an `extensions:` block in a file this repository
  owns; the adopted circuit schema file MUST NOT be edited.
- **FR-003**: The FR-001 peer MUST be the `DcimInterface` generic rather than a concrete
  interface kind, so both physical and virtual terminations are expressible.
- **FR-004**: `WanInternetPeering` MUST gain an optional, cardinality-one relationship to its
  BGP session, so the transit neighbor is reachable from the peering that justifies it.
- **FR-005**: `WanSite` MUST be able to reference **both** ends of its attachment's BGP session,
  provider-side and customer-side. The existing cardinality-one `bgp_session` cannot, and MUST
  be widened to many rather than duplicated into a second relationship.
- **FR-006**: FR-005 MUST remain optional, so a statically attached site with no protocol stays
  valid.
- **FR-007**: A device MUST be able to name the `IpamIPAddress` that is its BGP router ID,
  through an optional, cardinality-one relationship.
- **FR-008**: FR-007 MUST NOT require the address to sit on a loopback, because two of the six
  routers use a LAN-side address as their router ID.
- **FR-009**: Every new relationship MUST carry an explicit `identifier`, and any bidirectional
  pair MUST use the same identifier string on both sides.
- **FR-010**: Every new relationship `peer` MUST use the full kind, namespace included.
- **FR-011**: Every new relationship name MUST be snake_case.
- **FR-012**: No new relationship may be mandatory. Every one of them describes data that does
  not exist yet for any object in the graph, and a mandatory relationship would make the
  current seed unloadable.

#### Attributes

- **FR-020**: ~~The interface `role` dropdown MUST gain a `loopback` choice.~~ **Withdrawn by
  Phase 0 research (R1): already satisfied.** `schemas/dcim_extensions.yml` re-declares
  `DcimInterface.role` and its list already contains `loopback` and `vtep_loopback`. The
  specification read the base definition in `schemas/base/dcim.yml` and stopped there; the
  extension overrides it. Nothing to build.
- **FR-021**: Withdrawn with FR-020, for the same reason.
- **FR-022**: No existing attribute may be removed or made mandatory.

#### Display & Identification

- **FR-030**: Every new relationship MUST set an `order_weight` consistent with the file it
  lands in — 900-999 for primary relationships, 1000+ for secondary.
- **FR-031**: New relationships MUST NOT change any node's `display_label`,
  `human_friendly_id`, or `order_by`.

#### Migration

- **FR-040**: The FR-005 widening MUST be verified to affect no instance data before it is
  made. No `WanSite` currently has a session, which MUST be confirmed rather than assumed.
- **FR-043**: `tests/unit/test_wan_schema_contract.py` asserts the current cardinality-one
  `bgp_session` and MUST be updated alongside FR-005. The contract test is the mechanism that
  would otherwise catch this change as a regression, so it is updated deliberately and in the
  same commit, never loosened to stop failing.
- **FR-041**: Loading the changed schema against the existing seed MUST succeed with no
  migration step and no data loss.
- **FR-042**: `src/solution_arista_avd/protocols.py` MUST be regenerated, and the type check
  MUST pass against it.

### Key Entities

- **DcimCircuitEndpoint** *(adopted, extended)*: one end of an attachment circuit. Gains the
  interface that terminates it; keeps its side, name, status and location.
- **DcimInterface** *(adopted, extended)*: gains a `loopback` role choice. Already carries
  `ip_addresses`, which is the whole reason FR-001 is enough on its own.
- **WanSite**: one location of a tenant. Its single BGP session becomes many, because a session
  between two devices is two objects.
- **WanInternetPeering**: the provider's transit peering. Gains the session that realizes the
  `peer_asn` it already declares.
- **DcimDevice** *(extended)*: gains an optional router ID naming an existing `IpamIPAddress`.
- **RoutingBGPNeighbor**, **IpamIPAddress**, **InterfacePhysical**, **InterfaceVirtual**,
  **RoutingAsn**, **RoutingVrfStaticRoute** *(unchanged)*: already sufficient. They are listed
  because confirming they need no change is a result of this cycle, not an omission from it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run infrahubctl schema check schemas/` passes with zero validation errors.
- **SC-002**: Loading the changed schema over the existing seed succeeds, and every object in
  `objects/` still loads afterwards.
- **SC-003**: A single GraphQL query walks circuit → endpoint → interface → IP address and
  returns an address object, on a fixture built from the new relationships.
- **SC-004**: A `WanSite` accepts two BGP sessions and zero BGP sessions; both are valid.
- **SC-005**: Every one of the five gaps listed in "Why this cycle exists" has a modelled
  destination, and each destination is traceable to the rendered-config line that demands it.
  Four are built this cycle; the fifth, the loopback role, was already modelled — see FR-020.
- **SC-006**: Re-running the full inventory of the six rendered configs against the schema
  leaves **no remaining row whose obstacle is schema**. Every outstanding row is object data.
  This is the criterion that says the next cycle can start.
- **SC-007**: `uv run infrahubctl protocols` regenerates cleanly and `uv run mypy
  --show-error-codes src/solution_arista_avd` passes.
- **SC-008**: The WAN schema contract test asserts the widened relationship, and `uv run invoke
  test` and `uv run invoke lint` both pass. It is the only existing test that changes.
- **SC-009**: The adopted circuit schema file is byte-identical to its pre-cycle state.

## Assumptions

1. **The FRR render is the goal this serves, and it is two cycles away.** Schema here, object
   data next, the transform after that. The repository's constitution and the speckit routing
   extension both hold to one artifact type per cycle, and cycles 010 → 019 followed the same
   chain for the service layer. Collapsing them would be faster to write and much harder to
   review.
2. **Byte-for-byte parity against `../lab/wan/rendered/` is the eventual acceptance test.** The
   lab's templates are already Jinja2, so a port can reproduce them exactly, comments included.
   This cycle is scoped by what that target needs, which is why the inventory table is the
   spec's backbone rather than an appendix.
3. **Router ID is explicit, not derived.** A renderer could infer it from a loopback, but two of
   the six routers use a LAN address instead, so inference would be wrong a third of the time
   and silently so.
4. **`WanSite.site_asn` stays a Number.** It duplicates what a `RoutingAsn` object would hold,
   and converting it is a defensible cleanup — but it is seeded, correct, and read by nothing
   yet, so changing it here would be churn in a cycle that is otherwise purely additive.
5. **The provider's own AS needs no schema.** `RoutingAsn.devices` already exists, so AS 65500
   and AS 64500 are object data.
6. **Interfaces on the WAN routers are `InterfacePhysical` and `InterfaceVirtual`.** Both
   already inherit `InterfaceLayer3` and therefore `ip_addresses`; no new interface kind is
   needed for a router that is not an EOS switch.

## Out of Scope

- **Seeding any of it.** The interfaces, addresses, ASNs, BGP sessions and static routes this
  schema makes expressible are the next cycle. This one writes YAML under `schemas/` and
  nothing under `objects/`.
- **The FRR transform, its query, its templates and its artifact definition.** Two cycles out.
- **Correcting the prose addresses in `objects/33_nfd41_wan.yml`.** They become redundant once
  the real objects exist, and removing them belongs with the cycle that replaces them.
- **Converting `WanSite.site_asn` to a `RoutingAsn` relationship.** See assumption 4.
- **Junos firewall rendering.** A separate branch of the same end goal, with its own oracle in
  `../lab/configs/fw/vsrx/junos.conf`, and independent of everything here.
- **`ServiceAppAccess` and the `AppAccess` transform.** Still blocked on having no oracle, as
  cycles 013 and 017 both recorded.
- **Any change to the AVD pipeline, the fabric generators, or the EOS rendering path.** The
  `router_id` relationship is optional precisely so AVD is untouched.
- **A group for the WAN routers.** The artifact target the transform will need is object data,
  and it belongs with the transform.
