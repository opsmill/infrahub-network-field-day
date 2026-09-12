# Schema Design Specification: Device-Level Static Routes for the Perimeter Firewall

**Feature Branch**: `024-firewall-static-routes`
**Created**: 2026-09-12
**Status**: Draft
**Artifact type**: Schema (first of three — see [Next cycles](#next-cycles))

## Summary

Cycle 023 rendered 573 of the perimeter firewall's 677 configuration lines and enumerated the
104 it left out. The largest recoverable piece of that gap is `routing-options { static { … } }`
— twelve lines, eight routes — excluded because the firewall has nowhere to keep them.

This cycle gives it somewhere. It is a schema cycle only: no seed data and no rendering, both of
which follow.

## Schema Files

```text
schemas/routing/routing.yml          # EDIT — widen RoutingStaticRoute.device to the device generic
```

One file, and it is **not** marketplace-adopted. `schemas/MARKETPLACE.md` lists four adopted
files — `security/security.yml`, `cluster/cluster.yml`, `circuit/circuit.yml` and
`tenancy/tenancy.yml` — and `routing/routing.yml` is not among them. So this is an ordinary edit
to the repository's own schema rather than an `*_extensions.yml` addition.

## What was believed, and what is true

Cycle 023 recorded that `routing-options` "needs a device-level static route the schema does not
have", and `AGENTS.md` repeats it. Checked against the repository, that is wrong in a way that
makes this cycle smaller and worth correcting in the same change:

| Claim in the 023 record | What the repository actually holds |
| --- | --- |
| No device-level static route kind exists | `RoutingStaticRoute` exists in `schemas/routing/routing.yml`, with `prefix`, `next_hop`, `interface`, `distance`, `tag`, `route_name` and `vrf` |
| A new kind must be designed | No new kind. One relationship peer is too narrow |
| `routing.yml` would need extending from outside | `routing.yml` is the repository's own file, not adopted |

The real blocker is a single relationship: `RoutingStaticRoute.device` is mandatory and peers
`DcimDevice`. `fw1` is a `SecurityFirewall`, which inherits
`DcimGenericDevice`, `DcimPhysicalDevice`, `CoreArtifactTarget` and `SecurityPolicyAssignment` —
but **not** `DcimDevice`. So no static route can name the firewall as its device.

`DcimDevice` itself inherits `DcimGenericDevice`, and so does `ComputePhysicalServer`. Widening
the peer to the generic therefore keeps every existing use working and admits the firewall.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A firewall can own a static route (Priority: P1)

A network engineer records the firewall's eight forwarding decisions in Infrahub as first-class
objects, the same way the fabric's routes and the WAN's VRF routes are already recorded, rather
than leaving them readable only in a file on the device.

**Why this priority**: it is the whole cycle. Nothing else here is independently useful.

**Independent Test**: create a `RoutingStaticRoute` whose `device` is `fw1` and confirm it is
accepted; confirm the same object is rejected when `device` is omitted.

**Acceptance Scenarios**:

1. **Given** the schema is loaded, **When** a static route names `fw1` (a `SecurityFirewall`) as
   its device, **Then** it is created successfully.
2. **Given** the schema is loaded, **When** a static route names an existing `DcimDevice` as its
   device, **Then** it is still created successfully — the widening takes nothing away.
3. **Given** the schema is loaded, **When** a static route is created with no device, **Then** it
   is rejected, because a route with no device has no meaning.
4. **Given** two static routes on `fw1`, **When** they carry the same `prefix` and `vrf`,
   **Then** the second is rejected by the existing uniqueness constraint.

### User Story 2 - The firewall's routes are reachable from the firewall (Priority: P2)

Whoever reads `fw1` in the UI or in a query sees its static routes on it, without having to
search the static-route list for ones that happen to point back.

**Why this priority**: the reverse relationship is what makes the data navigable and what a
renderer will traverse next cycle. It is separable from US1 — the forward direction alone would
technically store the data — but a one-directional model would be a trap for cycle 026.

**Independent Test**: query `fw1` and read its `static_routes`; confirm the same relationship
still resolves from a `DcimDevice`.

**Acceptance Scenarios**:

1. **Given** a static route on `fw1`, **When** `fw1` is queried, **Then** the route appears in
   its `static_routes`.
2. **Given** an existing fabric device, **When** it is queried, **Then** its `static_routes`
   relationship resolves exactly as before.

### User Story 3 - The record stops misleading the next cycle (Priority: P3)

Whoever plans the follow-on work reads an accurate description of what the schema holds.

**Why this priority**: it is documentation, so it cannot break anything — but the incorrect
sentence in `AGENTS.md` is what would otherwise cause cycle 025 to be planned as a new-kind
design rather than a seeding exercise.

**Independent Test**: `AGENTS.md` and the cycle-023 exclusion note describe the gap as a
relationship-peer limitation, now closed, rather than a missing kind.

**Acceptance Scenarios**:

1. **Given** the schema change is made, **When** `AGENTS.md`'s `junos_config` section is read,
   **Then** it states that `routing-options` is pending seed data and rendering, not a missing
   schema kind.

### Edge Cases

- **A server acquires the ability to hold static routes.** `DcimGenericDevice` is also inherited
  by `ComputePhysicalServer`, so widening the peer admits servers too. This is accepted rather
  than prevented: it is the normal consequence of using a generic, nothing seeds such a route,
  and narrowing it back would need a peer that names two kinds, which the schema language does
  not offer.
- **Eleven existing routes name a `DcimDevice`.** Widening a peer to a generic the current peer
  already inherits is a widening, not a retype, so those references stay valid — verified by
  loading the change on a branch that held all eleven, not assumed.
- **The reverse relationship currently sits on `DcimDevice`.** If the forward side moves to the
  generic and the reverse side does not, the two ends of `device__static_route` disagree about
  their peer. Both ends move or neither does.
- **`human_friendly_id` reads `device__name__value`.** `DcimGenericDevice` carries `name`, so the
  HFID and the `[device, prefix__value, vrf__value]` uniqueness constraint keep working.
- **`vrf` defaults to `"default"`.** The firewall's eight routes are all in the master routing
  instance, which is what that default means, so no route needs to set it.

## Requirements *(mandatory)*

### Functional Requirements

#### Nodes & Generics

- **FR-001**: No new node or generic is defined. `RoutingStaticRoute` already models everything
  the eight routes need.
- **FR-002**: `SecurityFirewall` MUST NOT be modified. It is part of the adopted
  `security/security.yml`, one of the four files this repository keeps byte-identical to its
  marketplace copy.

#### Attributes

- **FR-003**: No attribute is added, removed or retyped. In particular the per-route comment the
  device file carries is satisfied by the existing `route_name` attribute, which is optional and
  documented as "Route Description".

#### Relationships

- **FR-004**: `RoutingStaticRoute.device` MUST peer `DcimGenericDevice` instead of `DcimDevice`.
- **FR-005**: `RoutingStaticRoute.device` MUST remain `cardinality: one`, `optional: false` and
  `kind: Attribute`. A route with no device is meaningless and must stay rejected.
- **FR-006**: The reverse relationship `static_routes` MUST move from the `DcimDevice` extension
  block to `DcimGenericDevice`, so both ends of `device__static_route` name the same peer.
- **FR-007**: The identifier `device__static_route` MUST be unchanged on both ends.
- **FR-008**: `RoutingVrfStaticRoute` MUST NOT be changed. It is a different kind for a different
  purpose — VRF-scoped routes reached through `WanSite.static_routes` — and the firewall's routes
  are device-level and in the master instance.

#### Display & Identification

- **FR-009**: `human_friendly_id` (`device__name__value`, `prefix__value`) and `display_label`
  (`prefix__value`) MUST be unchanged.

#### Uniqueness Constraints

- **FR-010**: The constraint `[device, prefix__value, vrf__value]` MUST be unchanged, and MUST
  still reject a duplicate prefix on the same device and VRF once the peer is a generic.

#### Migration

- **FR-011**: The change MUST be applied by editing the existing relationship rather than by
  adding a second one and marking the first `state: absent`. A widening to a generic the current
  peer inherits does not need the three-step migration that a retype would.
- **FR-012**: Regenerated artefacts MUST be regenerated, not hand-edited:
  `src/solution_arista_avd/protocols.py` and `schema.graphql`.
- **FR-013**: The schema MUST be loaded and checked on a branch before `main`.

### Key Entities

- **RoutingStaticRoute** — an existing node: a destination `prefix`, a `next_hop` or `interface`,
  an optional `distance`, `tag` and `route_name`, a `vrf` defaulting to `"default"`, and exactly
  one owning device. Unique per device, prefix and VRF.
- **DcimGenericDevice** — the existing generic that `DcimDevice`, `SecurityFirewall` and
  `ComputePhysicalServer` all inherit. Carries `name`, which the static route's HFID reads.
- **SecurityFirewall** — `fw1`'s kind, from the adopted security schema. Modified by nothing here;
  it gains the relationship by inheritance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `infrahubctl schema check schemas/` passes with zero validation errors.
- **SC-002**: A `RoutingStaticRoute` whose device is `fw1` loads successfully; before this change
  the same object is rejected. Both directions are demonstrated, so the criterion measures the
  change rather than the end state.
- **SC-003**: Every existing consumer of the kind still works. Specifically: the
  `backfill-structured-config` generator still creates and **upserts** static routes, whose
  `allow_upsert=True` depends on the uniqueness constraint that names `device`; and
  `transforms/frr_config.gql` renders all six FRR configurations byte-for-byte as before. The
  full unit suite stays green at its current count of 998.
- **SC-010**: `tests/unit/test_routing_schema_contract.py` exists and pins the peer, the
  cardinality, the mandatory flag and the shared identifier. Without it the suite passes whether
  the peer is right or wrong — see [research.md](./research.md) R7 — so this criterion is what
  makes SC-001 and SC-008 mean anything.
- **SC-004**: `fw1` exposes a `static_routes` relationship, and so does an existing fabric device.
- **SC-005**: A second route with the same prefix and VRF on the same device is rejected.
- **SC-006**: A route created with no device is rejected.
- **SC-007**: `schemas/security/security.yml` is byte-identical to the marketplace copy after the
  change, verified by the diff command in `schemas/MARKETPLACE.md`.
- **SC-008**: `protocols.py` and `schema.graphql` are regenerated, and `RoutingStaticRoute`'s
  device peer reads as the generic in both.
- **SC-009**: `AGENTS.md` no longer states that the schema lacks a device-level static route.

## Assumptions

1. **Widening the peer is preferred to adding a firewall-specific relationship.** The alternative
   — leaving `RoutingStaticRoute.device` on `DcimDevice` and adding a separate
   `SecurityFirewall.static_routes` — would need a second identifier, would make `device`
   ambiguous, and would give the next renderer two places to look. One generic peer is the
   smaller change and the one the schema language is shaped for.
2. **`RoutingStaticRoute` holds live data, and no data migration is needed anyway.**
   *(Corrected after Phase 0 — the first draft of this assumption claimed the kind was unused.)*
   `objects/` seeds none, but the `backfill-structured-config` generator creates them from AVD
   structured configs: eleven exist on `main`, on fabric spines and leaves. A widening keeps
   every existing `DcimDevice` reference valid, which [research.md](./research.md) R5
   demonstrates by loading the change on a live branch with those eleven objects present rather
   than by arguing it. The WAN's static routes are a different kind, `RoutingVrfStaticRoute`
   reached through `WanSite`, which this cycle does not touch.
3. **The eight routes are all in the master routing instance.** The device file's
   `routing-options { static { … } }` sits outside any `routing-instances` block, which is what
   `vrf: "default"` already means.
4. **`route_name` is the right home for the per-route comment.** Every one of the eight routes
   carries a `/* … */` comment that explains what the prefix is for, and those comments are most
   of the teaching value of the stanza — the same argument cycle 022 made for the FRR templates.

## Scope

**In scope**: one relationship peer, its reverse side, the regenerated artefacts, the tests that
prove the widening took nothing away, and the corrected sentence in `AGENTS.md`.

**Out of scope**, deliberately:

- **Seeding the eight routes.** Cycle 025.
- **Rendering `routing-options`.** Cycle 026, and it carries a known difficulty — see below.
- **The `system` stanza.** Permanently excluded; it holds two credential hashes that must never
  enter the model.
- **The `flow` block.** Seven lines, still unmodelled, and not addressed here.
- **`RoutingVrfStaticRoute` and the WAN.** Untouched.

## Next cycles

This feature is three cycles, which is the same shape as 020 → 021 → 022 for the WAN:

| Cycle | Artifact | Content |
| --- | --- | --- |
| 024 (this one) | Schema | One relationship peer |
| 025 | Objects | The eight routes on `fw1`, transcribed from the device file |
| 026 | Transform | The `routing-options` stanza; the artifact goes 573 → 585 of 677 lines and the documented exclusion list shrinks from 104 to 92 |

Folding 025 into this cycle is possible — cycle 023 did exactly that on request, and recorded the
deviation rather than leaving it implicit. It is not proposed here, because unlike 023 the seed
work is not blocked-on-discovery: it is straightforward transcription that can wait for a schema
that is already proven.

### A difficulty cycle 026 will meet, found while measuring this one

The stanza's twelve lines are **column-aligned by hand, and inconsistently**. Measured from the
file:

```text
route 10.110.0.0/24 next-hop 10.250.110.1;   /* k8s nodes */
route 10.60.0.0/16  next-hop 10.250.150.1;   /* WAN customer supernet */
route 10.220.10.0/24 next-hop 10.250.10.1;  /* acme cloud instances */
```

The prefix field is padded to a minimum width of 13, which puts `next-hop` at column 28 for six
of the eight routes and column 29 for the two whose prefix is one character longer. The comment
then begins at column 53 for those six and at column **52** for the other two. No single
derivation produces all eight lines: two of them are simply misaligned by one column in the
source.

That is recorded now, while the evidence is in hand, because it is the same family of problem as
cycle 023's three ordering questions and it will decide a success criterion in 026 — byte-for-byte
on ten of twelve lines with the deviation enumerated, or a relaxed comparison. It does **not**
affect this cycle: no attribute here stores presentation.

## Dependencies

None outstanding. Cycles 020–023 are merged and pushed. This cycle stands alone and is a
prerequisite for 025 and 026.
