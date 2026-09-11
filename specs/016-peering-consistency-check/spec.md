# Check Specification: Peering Consistency

> **Workflow type**: Infrahub Check (proposed-change validation)
> **Skill**: Use the `infrahub-managing-checks` skill to implement this specification.

**Feature Branch**: `016-peering-consistency-check`
**Created**: 2026-09-11
**Status**: Draft
**Input**: "Please tackle the outstanding items" — the check cycle, ranked next after 015.

## Why this cycle exists

Cycles 010 through 015 built a model whose entire purpose is to stop the two ends of a BGP
session drifting apart. 012 made `peer_asn` derived; 014 modelled the SVIs; 015 made
`peer_address` derived. Every one of those cycles measured itself against the same artifact
checksum.

**None of it fails a proposed change.** The generator corrects drift when it runs, but nothing
stops someone editing a session by hand, opening a proposed change, and merging it. The
correction happens after the fact, if it happens at all. A check is the thing that refuses the
merge.

## What this check can and cannot compare

The obvious rule — "does the cluster's view agree with what AVD renders onto the leaf?" —
**is not implementable on this instance**, and that was verified before this spec was written
rather than discovered during implementation:

| Candidate source of the fabric's own view | Objects present |
| --- | --- |
| `RoutingBGPNeighbor` | **0** on every branch |
| `AvdStructuredConfigFile` | **0** |
| `AvdHostvarFile` | **0** |
| `AvdArtifact` | **0** |

The AVD generator chain has never run here, so there is no rendered state to compare against.
A check written against it would pass vacuously, which is worse than no check: it would report
success while validating nothing.

What **is** present and comparable is the graph itself, including `EvpnSviNode` (16 objects) —
the fabric's own record of which address sits on which device's SVI, and the duplication cycle
014 flagged and deliberately did not fix.

So this check validates the model against itself. Every rule below is pure graph.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A hand-edited session fails the merge (Priority: P1) 🎯 MVP

Someone edits a `ClusterFabricPeering` by hand — changes an ASN, repoints an address — and
opens a proposed change. The check fails it, naming the object and both values.

**Why this priority**: This is the gap. The generator corrects drift on its next run; the
check is what prevents the drift being merged in the first place.

**Independent Test**: Change a session's `peer_asn` away from its device's `RoutingAsn` and
run the check.

**Acceptance Scenarios**:

1. **Given** a session whose `peer_asn` differs from its peer device's `RoutingAsn`, **When** the check runs, **Then** it logs an error naming the session, the recorded value and the device's value
2. **Given** a session whose `peer_address` is not the address on its peer device's peering SVI, **When** the check runs, **Then** it logs an error naming both
3. **Given** a model the generator produced, **When** the check runs, **Then** it passes with no errors
4. **Given** a failing session, **When** the check runs, **Then** it reports **every** failing session rather than stopping at the first

---

### User Story 2 - Structural impossibilities are caught (Priority: P2)

Two services claiming one cluster, or a session pointing at a device the cluster is not cabled
to, are states the generator would never produce but object data can express.

**Why this priority**: P2 because they are less likely than a hand-edited value, but they are
exactly the states that make a generator run destructive — 012's evidence recorded that two
services on one cluster would fight over the same objects on every run.

**Acceptance Scenarios**:

1. **Given** two `ServiceFabricPeering` objects referencing one cluster, **When** the check runs, **Then** it logs an error naming both
2. **Given** a session whose `peer_device` is not reachable from any of the cluster's cabled nodes, **When** the check runs, **Then** it logs an error naming the session and the device
3. **Given** a session pointing at a device that is not a fabric leaf, **When** the check runs, **Then** it logs an error

---

### User Story 3 - The SVI duplication is surfaced (Priority: P2)

Cycle 014 introduced a second record of each peering address: the SVI's `ip_addresses`, and
`EvpnSviNode.ip_address`, which the fabric already had. They agree today and nothing enforces
it.

**Why this priority**: P2 because it is a latent inconsistency rather than an active one. It is
in scope because cycle 014 explicitly flagged it as the cost of not making a schema change, and
a check is the cheaper half of that trade.

**Acceptance Scenarios**:

1. **Given** an `EvpnSviNode` whose `ip_address` differs from the address on the corresponding SVI, **When** the check runs, **Then** it logs an error naming the device and both values
2. **Given** an `EvpnSviNode` with no corresponding SVI, **When** the check runs, **Then** it reports informationally rather than failing, because not every SVI node is a peering SVI

---

### Edge Cases

- **No peering services at all.** The check must pass, not fail on an empty result.
- **A cluster with no `local_asn`.** Already caught by the generator; the check should not duplicate a guard that blocks generation anyway.
- **A session whose peer device has no peering SVI.** The generator refuses to create it; an existing one is drift.
- **A device carrying several `EvpnSviNode` records.** Matching must be on device *and* VLAN, not device alone.
- **A proposed change that deletes a session.** Absence is not drift.

## Requirements *(mandatory)*

### Functional Requirements

**Check class**:

- **FR-001**: The check MUST inherit `infrahub_sdk.checks.InfrahubCheck` and implement `validate(self, data: dict) -> None`
- **FR-002**: The check MUST be **global** — no `targets` — so it runs on every proposed change. The inconsistencies it catches are not scoped to one fabric
- **FR-003**: The check MUST consume its query response through generated typed models, per Principle III
- **FR-004**: Failures MUST use `log_error`; advisory findings MUST use `log_info`, since the SDK has no `log_warning`
- **FR-005**: Every `log_error` MUST carry `object_id` and `object_type`, so the failure is attributable in the proposed-change UI
- **FR-006**: The check MUST report every violation it finds, never stopping at the first

**Rules**:

- **FR-007**: A session's `peer_asn` MUST equal its peer device's `RoutingAsn`
- **FR-008**: A session's `peer_address` MUST be the address on its peer device's `peering`-role SVI
- **FR-009**: A cluster MUST be referenced by at most one `ServiceFabricPeering`
- **FR-010**: A session's `peer_device` MUST be a device the cluster's nodes are cabled to
- **FR-011**: A session's `peer_device` MUST have a fabric-leaf role
- **FR-012**: An `EvpnSviNode.ip_address` MUST agree with the address on the matching SVI, matched on device and VLAN

**Registration**:

- **FR-013**: The query and the check MUST be registered in `.infrahub.yml`, with the check's `query` attribute matching the registered query name exactly
- **FR-014**: The check MUST NOT duplicate a guard the generator already enforces at write time, except where object data can bypass it

### Key Entities

- **`ClusterFabricPeering`**: the object being validated.
- **`DcimDevice`**: supplies the authoritative `RoutingAsn` and the peering SVI.
- **`InterfaceVirtual`**: the peering SVI, matched by `role`.
- **`EvpnSviNode`**: the fabric's second record of the same address.
- **`ServiceFabricPeering`**: counted per cluster for FR-009.

### Key Files

| File | Purpose |
| --- | --- |
| `checks/peering_consistency_check.gql` | The query |
| `checks/peering_consistency_check_query.py` | Generated typed models |
| `checks/peering_consistency_check.py` | The check class |
| `.infrahub.yml` | Query and check definition |
| `tests/unit/test_peering_consistency_check.py` | Unit coverage |

## Success Criteria *(mandatory)*

- **SC-001**: A model the generator produced passes with zero errors
- **SC-002**: A session whose `peer_asn` is edited by hand fails, naming the session and both values
- **SC-003**: A session whose `peer_address` is repointed fails, naming both
- **SC-004**: Two services on one cluster fail
- **SC-005**: A session pointing at an uncabled or non-leaf device fails
- **SC-006**: An `EvpnSviNode` disagreeing with its SVI fails
- **SC-007**: Several simultaneous violations are all reported in one run
- **SC-008**: An empty model passes rather than erroring
- **SC-009**: Every error carries an object id and type
- **SC-010**: All unit tests and the repository's linters pass

## Assumptions

1. **The check validates the model against itself**, because the fabric's rendered view does not exist on this instance — verified, not assumed.
2. **Global rather than targeted.** These inconsistencies are not scoped to a fabric, and a global check needs no group.
3. **The generator remains the corrector**; the check is the gate. They overlap deliberately.
4. **`EvpnSviNode` matching is on device and VLAN.** A device may carry several.

## Out of Scope

- Comparing against AVD structured config or `RoutingBGPNeighbor`. Both are empty; a check against them would pass vacuously. If the AVD chain is ever run here, that becomes its own cycle and is the most valuable remaining rule.
- Fixing the `EvpnSviNode` duplication. This surfaces it; collapsing it is a schema change.
- Checks for the other five service kinds, which have no objects.
- The FabricApp and AppAccess transforms.
