# Schema Design Specification: Zone Advertisement Policy

> **This is a schema design spec.** The implementing agent MUST use the `infrahub-managing-schemas` skill to build and validate all schema definitions.

**Feature Branch**: `032-zone-advertisement-policy`
**Created**: 2026-09-16
**Status**: Draft
**Input**: Connect a `SecurityZone` to the prefix list that governs what the DC advertises toward it, so an access grant can make its destination VIP routable as well as permitted — closing the fabric leg of the fabric/Kubernetes/Junos service.

## Why this cycle exists

Cycle 031 built the Junos leg of an access grant: an approved `ServiceAppAccess` now creates the firewall rule permitting the session. That made `ServiceAppAccess` the one service that names all three domains of this lab — and revealed that only two of them act.

| Leg | What the grant names | Acts today |
| --- | --- | --- |
| **Kubernetes** | `application` → `ServiceFabricApp`: namespace, chart, VIP block, network policy | **Yes** — Crossplane and Vidra |
| **Junos** | `source_zone` + `source_address` → the firewall rule | **Yes** — cycle 031 |
| **Fabric** | `destination_vip` — must be re-advertised into the source's VRF | **No** |

The gap is written into the schema already, on `destination_vip` in `schemas/service/access_services.yml`:

> *"Must sit inside the range the border leaf re-advertises to the source, or the grant is permitted by the firewall and still unroutable."*

### What that costs today, concretely

`border-leaf1` advertises toward the branch through `RM-DC-TO-BRANCH`, which matches `PL-DC-ADVERTISED-BRANCH`:

```text
ip prefix-list PL-DC-ADVERTISED-BRANCH
   seq 10 permit 10.112.240.0/24 le 32      <- every application VIP
   seq 20 permit 10.110.0.0/24              <- the k8s node subnet
```

A blanket `/24`. **Every application VIP is already routable from the branch**, and the firewall is the only thing deciding which one a branch user reaches. So revoking a grant removes permission and leaves reachability: the route stays, the session is refused at the perimeter rather than never having a path. Defence in depth is one layer thinner than the model implies, and nothing says so.

Closing the leg means a grant becomes the single thing making all three true — and withdrawing all three.

### The modelling gap this cycle fills

A grant knows its source zone. **Nothing connects a `SecurityZone` to the policy governing what the DC advertises toward it.** Two facts are missing and both live only as strings inside a JSON attribute:

- *which prefix list* governs advertisement toward this zone (`PL-DC-ADVERTISED-BRANCH`)
- *which device* carries it (`border-leaf1`)

`SecurityZone` today carries `name`, `description`, `trust_level` and `vrf`. The firewall side of a zone is modelled — `SecurityFirewallInterface.security_zone` — and the fabric side is not.

### The constraint that shapes the whole design

**There are zero `RoutingPrefixList` objects in the graph.** Verified against `main`. The fabric's entire BGP policy — every prefix list and route map — lives inside `NetworkFabric.avd_custom_hostvars`, a JSON attribute, as `custom_structured_configuration_prefix_lists`. That is AVD's documented escape hatch for inputs this data model does not model, and `generate_avd_device_hostvar.py` merges it into the AVD inputs at fabric, pod and device scope.

So there is no object for a zone to point *at*. This cycle therefore models the **reference**, not the policy: a zone records the name of the list governing advertisement toward it and the device carrying it, and the reference is made *detectable* rather than merely trusted. Migrating the fabric's BGP policy out of the JSON blob into first-class routing objects is a much larger cycle and is out of scope — see Assumptions.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A zone knows what the DC advertises toward it (Priority: P1)

A `SecurityZone` records the name of the prefix list that governs what the datacentre advertises in its direction, so a generator can find that list without inferring it from a naming convention.

**Why this priority**: it is the whole blocker. Without it a grant generator has to guess `PL-DC-ADVERTISED-<ZONE-UPPER>`, and this repository has explicitly rejected that shape of inference once already — research R2 of cycle 031 discarded a derivation that "happens to be right today". Everything else in this chain waits on this one fact.

**Independent Test**: `infrahubctl schema check schemas/` passes; each of the six zones shows the field in the UI; a single query returns every zone with its advertisement policy and nothing else needs to be consulted.

**Acceptance Scenarios**:

1. **Given** a zone the DC advertises toward, **When** it is read, **Then** the name of the governing prefix list is available on the zone itself
2. **Given** a zone the DC advertises nothing toward, **When** it is read, **Then** the field is empty and that is a valid state, not an error — an internal zone need have no external advertisement
3. **Given** the six zones loaded from `objects/32_nfd41_security.yml`, **When** the schema is loaded, **Then** every one of them still loads, because the new field is optional
4. **Given** a client that knows only the zone kind, **When** it queries for advertisement policy, **Then** it gets the answer without reading `NetworkFabric.avd_custom_hostvars`

---

### User Story 2 - A zone knows which device carries that policy (Priority: P2)

A `SecurityZone` records the fabric device whose configuration carries the advertisement policy, so a generator writes at device scope rather than fabric scope.

**Why this priority**: it is what makes the eventual write *safe* rather than merely possible. `avd_custom_hostvars` exists at fabric, pod and device scope and the generator merges them in that order. Writing a per-grant entry at fabric scope would put a service-owned value into the same attribute that carries the hand-authored baseline for every device; writing at device scope leaves that baseline untouched and lets the merge compose the two. P2 rather than P1 because a generator could hardcode the border leaf and still work — badly, and only for this lab.

**Independent Test**: schema check passes; each zone that has an advertisement policy also resolves to exactly one device; deleting that device does not silently orphan the zone.

**Acceptance Scenarios**:

1. **Given** a zone with an advertisement policy, **When** it is read, **Then** the device carrying that policy is reachable from the zone in one hop
2. **Given** that device, **When** it is read, **Then** the zones whose policy it carries are reachable from it, so "what does this leaf advertise, and to whom" is answerable from either end
3. **Given** a zone whose carrying device is deleted, **When** the zone is read, **Then** it is still readable and the missing device is detectable — deleting a switch must not delete a security zone
4. **Given** a zone with no advertisement policy, **When** it is read, **Then** it needs no carrying device either

---

### User Story 3 - A policy that does not exist is detectable (Priority: P3)

Because the prefix list is named rather than referenced, a zone can name a list no device actually defines. The model must make that mismatch findable by a query rather than discoverable only when a generated route never appears.

**Why this priority**: it is the honest cost of modelling a reference into a JSON blob, and naming the cost is what makes the choice defensible. It is P3 because the detection itself — a check — is a separate cycle and a separate artifact type; what this cycle owes is a model that *can* be checked.

**Independent Test**: given a zone naming a list absent from every device's merged AVD inputs, a query can return that zone. No check is built in this cycle.

**Acceptance Scenarios**:

1. **Given** a zone naming a prefix list, **When** the fabric's custom hostvars are read, **Then** the two can be compared without parsing free text
2. **Given** a zone naming a list that no device defines, **When** the comparison runs, **Then** the zone is identifiable as misconfigured
3. **Given** a zone whose named list exists, **When** the comparison runs, **Then** it is not reported

---

### Edge Cases

- Two zones name the same prefix list. Is that legitimate (one list serving several zones) or a modelling error?
- A zone names a prefix list that exists on a *different* device from the one recorded as carrying it.
- The carrying device is not a `border_leaf` — for example a spine, which advertises nothing externally.
- The prefix list name is changed in `avd_custom_hostvars` and the zone still names the old one; nothing fails, and the advertisement quietly stops being governed by anything the zone knows about.
- A zone has a carrying device but no prefix-list name, or a name but no device. Is either half alone meaningful?
- The fabric's BGP policy is later migrated to first-class routing objects, and the name attribute becomes a duplicate of a relationship.
- A second fabric is added with its own border leaf and its own zones of the same names.
- `SecurityZone` is an upstream kind; the attribute has to be added by extension without changing the upstream contract more than necessary.

## Requirements *(mandatory)*

### Functional Requirements

#### Nodes & Generics

- **FR-001**: The schema MUST extend the existing `SecurityZone` kind rather than introducing a parallel one, so every zone gains the fields and none has to opt in
- **FR-002**: The extension MUST live in `schemas/security_extensions.yml`, which is where this repository already adds `trust_level`, `vrf`, `book_index` and `log_session_close` to upstream security kinds
- **FR-003**: No new node or generic is required. If implementation finds one is, that is a signal the design drifted toward migrating the policy rather than referencing it — stop and re-scope

#### Advertisement policy (User Story 1)

- **FR-010**: `SecurityZone` MUST carry the name of the prefix list governing what the datacentre advertises toward that zone
- **FR-011**: The field MUST be optional, because a zone the DC advertises nothing toward is valid and because six zones already exist without it
- **FR-012**: The field MUST be a plain scalar, not a relationship, because there is no object to point at — every prefix list in this fabric exists only inside `NetworkFabric.avd_custom_hostvars`
- **FR-013**: The field's description MUST record that it is a soft reference into custom AVD hostvars, and that nothing enforces the name resolves. An undocumented soft reference is how the next reader mistakes it for a validated one

#### Carrying device (User Story 2)

- **FR-020**: `SecurityZone` MUST relate to the fabric device whose configuration carries that prefix list, with cardinality one and optional
- **FR-021**: The relationship MUST peer a device kind that a border leaf satisfies. It MUST NOT peer `DcimDevice`, which in this repository is the WAN's FRR routers and does not include fabric switches
- **FR-022**: The relationship MUST be navigable from the device as well as the zone, with matching `identifier` values on both sides
- **FR-023**: The relationship MUST NOT cascade on delete. Deleting a switch must never delete a security zone
- **FR-024**: Both halves MUST be independently optional, so a partially-modelled zone loads and is detectable rather than unloadable

#### Detectability (User Story 3)

- **FR-030**: The prefix-list name and the carrying device MUST both be queryable in one request alongside the zone, so a later check can compare them against the device's merged AVD inputs without a second traversal
- **FR-031**: No check is built in this cycle. The requirement is that the model permits one

#### Display & Identification

- **FR-040**: New fields MUST use `order_weight` following the repository convention, and MUST sort after the zone's existing `name`, `description`, `trust_level` and `vrf` rather than displacing them
- **FR-041**: Attribute and relationship names MUST be snake_case (`^[a-z0-9_]+$`, 3–64 chars); the relationship `peer` MUST use the full kind

#### Migration

- **FR-050**: New fields on `SecurityZone` MUST be optional or carry a `default_value`, because six zone objects already exist and a mandatory field with no default makes them unloadable
- **FR-051**: `infrahubctl schema check schemas/` MUST pass, and every file under `objects/` MUST continue to load. Where seed data must be updated to populate the new fields, that update is part of this cycle
- **FR-052**: `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py` MUST be re-run, because the generated protocols are a schema artifact

#### Contract tests

- **FR-060**: A unit test MUST assert both fields exist on `SecurityZone`, are optional, and that the relationship does not cascade on delete
- **FR-061**: A unit test MUST assert the relationship's peer is a kind that includes fabric switches, so a later refactor cannot repoint it at `DcimDevice` and silently match nothing
- **FR-062**: A unit test MUST assert that the zones seeded in `objects/32_nfd41_security.yml` populate both fields wherever the fabric actually advertises toward them, so the model and the lab do not drift

### Key Entities

- **`SecurityZone`** *(existing, extended)*: a perimeter zone. Already carries `name`, `description`, `trust_level` and a `vrf` pairing that records the fabric VRF on the other side of its handoff. Gains the name of the prefix list governing DC advertisement toward it, and the fabric device carrying that policy. The firewall side of a zone was already modelled; this adds the fabric side.
- **`DcimFabricSwitch`** *(existing, extended by the inverse relationship)*: the EOS switches. A border leaf gains the ability to answer "which zones' advertisement policy do I carry".
- **`NetworkFabric.avd_custom_hostvars`** *(existing, unchanged)*: the JSON attribute holding every prefix list and route map as AVD custom structured configuration. This cycle points at it by name and does not migrate it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `infrahubctl schema check schemas/` passes with zero errors, and `infrahubctl schema load schemas` succeeds against a branch
- **SC-002**: Every zone that the datacentre advertises toward resolves, in one query, to the prefix list governing that advertisement and the device carrying it
- **SC-003**: All six seeded zones load unchanged, or the seed update is made in this cycle
- **SC-004**: Every file under `objects/` loads without error after the change
- **SC-005**: Deleting a fabric switch leaves every security zone intact and readable
- **SC-006**: A zone naming a non-existent prefix list is identifiable by comparing two queried values, with no free-text parsing
- **SC-007**: `uv run pytest tests/unit` passes, including the new contract tests, and `uv run invoke lint` is clean
- **SC-008**: `uv run invoke bootstrap --fresh` completes and `scripts/verify_bootstrap.sh` passes all sixteen assertions

## Assumptions

- **The policy is referenced by name, not migrated into objects.** Every prefix list and route map in this fabric lives inside `NetworkFabric.avd_custom_hostvars`, which is AVD's documented channel for inputs this model does not model. Moving that policy into `RoutingPrefixList` objects — which today number zero — would be a large migration touching every device's rendered configuration, and it would fight a design the repository chose deliberately. This cycle records the reference and makes it checkable. If the policy is migrated later, the name attribute becomes redundant and is removed then.
- **A soft reference is acceptable here because it is made detectable.** The repository rejected naming-convention *inference* in cycle 031 (research R2). This is different: the name is authored data, not derived, and User Story 3 requires the mismatch to be findable. An authored name that a check validates is not the same as a name a generator guesses.
- **One device per zone.** Each zone in this lab hands off to exactly one border leaf. A zone advertised by two devices would need cardinality many; nothing in the lab requires it, and widening later is additive.
- **The write mechanism is settled and out of scope.** `generate_avd_device_hostvar.py` merges custom hostvars at fabric, pod and device scope, and `_merge_lists` merges by identity — two prefix lists sharing a `name` merge field by field, and their `sequence_numbers` merge by `sequence`. So a device-scope entry appends to the fabric-scope list rather than replacing it. That is what makes the generator cycle viable; it is not built here.
- **Sequence numbering for generated entries** follows the precedent set in cycle 031 — a floor well clear of hand-written values. Not decided here.

## Out of Scope

- **The generator.** Extending `generate-app-access` to write and withdraw the VIP entry is the next cycle. This one only makes it possible to find where to write.
- **The check.** Detecting a zone that names a non-existent prefix list is a third cycle and a different artifact type. User Story 3 requires only that the model permit it.
- **Migrating BGP policy into routing objects.** `RoutingPrefixList` and `RoutingRouteMap` remain AVD *output*, written by `backfill_structured_config`. Nothing in this cycle makes them inputs.
- **Narrowing `PL-DC-ADVERTISED-BRANCH` from its blanket `/24`.** That is a behaviour change to the lab's baseline and belongs with the generator that replaces it with per-grant entries, not with the schema that describes it.
- **`ServiceFabricApp` VIP-block allocation** and the **WAN service redesign**, both of which the user has asked for and both of which follow this chain.
- **`DeploymentState` and `DeploymentDiffFile`.** Nothing here reads, writes or triggers from them.
