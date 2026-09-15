# Schema Design Specification: Deployment state model

> **This is a schema design spec.** The implementing agent MUST use the `infrahub-managing-schemas` skill to build and validate all schema definitions.

**Feature Branch**: `029-deployment-executor`
**Created**: 2026-09-15
**Status**: Draft
**Input**: User description: "specs/029-deployment-executor/grilling-decision-log.md"

## Why this cycle is schema-only

The decision log describes a reconciler: a loop that compares every device against its
rendered intent and pushes when they differ. Its single most consequential conclusion is
item 9 — **state lives in Infrahub**, and the executor is stateless. Everything else in the
design rests on that: cold start stops being a fabric-wide config event, partial failure is
recorded per device by construction, and an operator looks for "did my merge reach the
fabric?" in the UI they already use.

That makes the data model the first thing that has to exist, and the spec-driven workflow
takes one artifact type per cycle. This spec covers **only** the Infrahub schema. The
reconciler loop, the Nornir device layer, the lift of `scripts/provision_lab.py` into a
module, and the cleanup sweep are later cycles and are listed under
[Out of scope](#out-of-scope).

## Schema Files

All schema definitions live in `schemas/*.yml`. Each file must start with:

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"
```

This feature adds one file, `schemas/deployment.yml`. It adds nothing to an existing
schema file and extends no existing node — see FR-024.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator can see whether a device matches its intent (Priority: P1)

A network engineer merges a proposed change and wants to know whether the fabric now
reflects it. Today the only answer is to run `uv run invoke provision` and read its output,
which is a claim about what the command did, not about what the devices are. This story
introduces a per-device record whose meaning is **"the last time this device was confirmed
to match its rendered intent"** — decision log item 12, the "confirmed, not sent"
distinction.

**Why this priority**: it is the whole reason state moved into Infrahub. Without it there is
no place an operator looks, and the executor is back to being a SQLite file in a container.
Every other story in this spec hangs off this node.

**Independent Test**: load `schemas/deployment.yml` into a branch, create one record against
an existing device by hand, and confirm it renders in the UI with the device name as its
identifier. Delivers operator-visible deployment state with no executor written at all.

**Acceptance Scenarios**:

1. **Given** no deployment schema exists, **When** `schemas/deployment.yml` is loaded,
   **Then** `DeploymentState` appears in Infrahub with its attributes and its relationship
   to a device.
2. **Given** the node exists, **When** a record is created against a `DcimFabricSwitch`,
   **Then** its human-friendly identifier reads as that switch's name and its status defaults
   to `never_deployed`.
3. **Given** a record exists for a device, **When** a second record is created for the same
   device, **Then** the uniqueness constraint rejects it.
4. **Given** a record for a `DcimFabricSwitch`, **When** a record is created for a
   `DcimDevice`, a `SecurityFirewall` and a `ComputePhysicalServer`, **Then** all four are
   accepted, because the relationship peers the generic and not one device kind.

---

### User Story 2 - An operator can exempt one device without stopping the service (Priority: P1)

Decision log item 15 settled that drift is corrected automatically and without asking. The
mitigation it required in the same breath is a per-device break-glass: someone who has added
an emergency rule to the perimeter firewall at 3am needs the reconciler to leave that box
alone, and `docker stop` suspends reconciliation for the entire fabric.

**Why this priority**: it is not a convenience. Auto-correction without a per-device opt-out
means the only way to protect a device mid-incident is to disable deployment everywhere,
which is the wrong trade in exactly the situation it arises. P1 alongside story 1 because
auto-push must not ship without it.

**Independent Test**: set the suspend flag on one record and confirm it reads back as set
while every other record is untouched. Testable with no reconciler present; the reconciler's
obligation to honour it is asserted in its own cycle.

**Acceptance Scenarios**:

1. **Given** a record with suspension unset, **When** it is read, **Then** the flag is
   `false` without having been written — it carries a default.
2. **Given** a record, **When** an operator sets suspension and records a reason, **Then**
   both persist and are visible in the UI next to the device's status.
3. **Given** one suspended record, **When** other records are read, **Then** they are
   unaffected — suspension is per device, not global.

---

### User Story 3 - The evidence for "drifted" is visible, not just the verdict (Priority: P2)

All three device families compute the diff themselves — `show session-config diffs` inside
the configuration session `push_eos` already opens, `show | compare` between the
`load replace` and the `commit` that `push_junos` already does, and `frr-reload.py --test`.
That output is the evidence. A status of `drifted` with no way to see *what* drifted sends
the operator back to the CLI, which is the workflow this feature exists to remove.

**Why this priority**: the status alone is actionable enough to ship, so this is not P1. But
storing the device-computed diff is what makes the record a claim about the network rather
than about the executor, and it is what the branch dry run (item 12) renders.

**Independent Test**: attach a diff to a record, read it back, and confirm it is reachable
from the device's deployment record in one hop.

**Acceptance Scenarios**:

1. **Given** a deployment record, **When** a diff is attached, **Then** it is reachable from
   that record and from nowhere else.
2. **Given** a record with a diff, **When** a later comparison finds the device in sync,
   **Then** the diff can be replaced or removed without deleting the record.
3. **Given** a deployment record is deleted, **When** its diff is looked for, **Then** it is
   gone with it rather than orphaned.

---

### User Story 4 - Deployment state never becomes proposed intent (Priority: P2)

Decision log item 11: deployment state is a fact about the physical world, not about a
branch. Modelled branch-aware, a branch created Monday and merged Friday carries Monday's
deployment state into `main`, and every proposed change displays deployment records as
though someone were proposing them.

**Why this priority**: it is a modelling property rather than a user-visible feature, but
getting it wrong is expensive to undo once records exist, so it is settled here rather than
discovered later.

**Independent Test**: create a record on `main`, create a branch, and confirm the branch
diff and any proposed change raised from it contain no deployment records.

**Acceptance Scenarios**:

1. **Given** a record exists, **When** a branch is created and a proposed change raised,
   **Then** the proposed change shows no deployment records as proposed changes.
2. **Given** a record is updated while a branch is open, **When** that branch is merged,
   **Then** the merge does not overwrite the record with the branch's older view of it.

---

### User Story 5 - Nothing regenerates because of a deployment write (Priority: P2)

Decision log item 10 is the loop this design has to not close. Writing state onto a device
emits an event; `triggers.yml` turns node events into generator runs; a generator run
regenerates artifacts; a moved artifact is what the reconciler acts on. Today the loop stays
open only because no trigger happens to watch a switch — **by accident, not by design**.

**Why this priority**: the separate kind is what makes the rule enforceable, and the kind is
being created now. The enforcement is cheap to add at the same time and expensive to
retrofit after someone has added the trigger this prevents.

**Independent Test**: a unit test over `triggers.yml` fails if any trigger rule names a
deployment kind. Runs in `tests/unit`, hermetic, no Infrahub instance needed.

**Acceptance Scenarios**:

1. **Given** the current `triggers.yml`, **When** the test runs, **Then** it passes.
2. **Given** someone adds a trigger rule whose `node_kind` is a deployment kind, **When**
   the test runs, **Then** it fails and names the offending rule.

---

### Edge Cases

- **A device is deleted while it has a deployment record.** The relationship to the device is
  mandatory, so the record must not be what blocks the deletion, and it must not survive as an
  orphan pointing at nothing. FR-025 settles the behaviour.
- **Two records for the same device.** Prevented by the uniqueness constraint (FR-050); the
  reconciler must upsert on the device relationship rather than create.
- **A record for a device the reconciler has never reached.** The status default
  (`never_deployed`) has to be distinguishable from "checked and found to match", because the
  two lead to opposite actions. This is the cold-start hazard from item 8 stated as a data
  requirement.
- **A record whose confirmation timestamp is old but whose status is `in_sync`.** Means the
  reconciler has stopped running. The model must let an operator tell that apart from a
  device that is genuinely fine, which is why a checked timestamp and a confirmed timestamp
  are separate fields.
- **The diff file exists but its parent record does not.** Prevented by the Parent
  relationship being mandatory; deleting the record removes the diff.
- **A diff that is enormous** — a device that has never been configured produces a diff the
  size of its whole configuration. The field kind has to tolerate that rather than truncating
  silently.
- **Suspension set on a device with no deployment record yet.** There is nothing to set it
  on. The reconciler must create the record before it can be exempted, which is an ordering
  constraint on the executor cycle, not on this schema.
- **`generate_profile` left at its default.** Profiles on an observed-state kind are
  meaningless — a profile supplies default values for intent, and nothing here is intent.
  FR-006 turns them off explicitly.

## Requirements *(mandatory)*

### Functional Requirements

#### Nodes & Generics

- **FR-001**: Schema MUST define `DeploymentState` and `DeploymentDiffFile` as concrete
  nodes under the `Deployment` namespace, in a new file `schemas/deployment.yml`.
- **FR-002**: The schema MUST NOT define any generic. Both nodes are concrete, and
  `DeploymentDiffFile` takes its file behaviour from the built-in `CoreFileObject` rather than
  from a new local generic.
- **FR-003**: `DeploymentDiffFile` MUST inherit from `CoreFileObject` via `inherit_from`,
  matching the `AvdHostvarFile` and `AvdStructuredConfigFile` precedent in
  `schemas/objects/objects.yml`.
- **FR-004**: All node names MUST be PascalCase (pattern: `^[A-Z][a-zA-Z0-9]+$`, 2-32 chars).
- **FR-005**: The `Deployment` namespace MUST satisfy `^[A-Z][a-z0-9]+$`, 3-32 chars.
- **FR-006**: Both nodes MUST set `generate_profile: false`. Neither node holds intent, so a
  profile supplying default values for it has no meaning.
- **FR-007**: Both nodes MUST set `branch: agnostic`, so a record is one fact shared by every
  branch rather than a per-branch opinion. This is what delivers User Story 4: agnostic nodes
  do not appear in branch diffs or proposed changes, and a branch merge cannot overwrite a
  record with a stale view of it.

#### Attributes

- **FR-010**: ~~`DeploymentState` MUST NOT define a `name` attribute.~~ **Reversed during
  implementation.** `DeploymentState` MUST define a `name` attribute of kind Text with
  `unique: true`, holding the name of the device it describes. The original requirement — that
  identity come from the `device` relationship — is not implementable: Infrahub requires any
  relationship used in `human_friendly_id` or `uniqueness_constraints` to be mandatory, and a
  mandatory `device` makes any device that has ever held a record permanently undeletable,
  which would violate FR-025 for every device in the fabric. See research R3 for the
  measurement. The reconciler MUST own this field and refresh it from the device each cycle,
  which is the answer to the drift objection that motivated the original wording.
- **FR-011**: `DeploymentState` MUST define these attributes:

  | Attribute | Kind | Optional | Default | Purpose |
  | --- | --- | --- | --- | --- |
  | `status` | Dropdown | no | `never_deployed` | The device's standing against its intent |
  | `last_confirmed_at` | DateTime | yes | — | Last time the device was **confirmed to match** |
  | `last_checked_at` | DateTime | yes | — | Last time a comparison ran, match or not |
  | `last_attempt_at` | DateTime | yes | — | Last time a push was attempted |
  | `last_error` | TextArea | yes | — | Failure detail from the last unsuccessful cycle |
  | `suspend` | Boolean | no | `false` | Per-device break-glass; the reconciler skips it |
  | `suspend_reason` | Text | yes | — | Why, and by whom — free text |

- **FR-012**: `status` MUST define `choices` with at least: `never_deployed`, `in_sync`,
  `pending`, `drifted`, `failed`. Each choice MUST carry a `name`; labels and colours are
  expected but not required.
- **FR-013**: `status` and `suspend` MUST be mandatory with a `default_value`, so a record
  created by the reconciler with only a device relationship is already in a legible state.
- **FR-014**: `suspend` MUST NOT be expressed as a `status` choice. Suspension is an
  operator's instruction; status is an observation about the device. Collapsing them loses
  what the device was doing when it was suspended.
- **FR-015**: `last_error` MUST be `TextArea` rather than `Text`, because device and library
  errors are multi-line.
- **FR-016**: All attribute names MUST be snake_case (`^[a-z0-9\_]+$`, 3-64 chars) and all
  kinds MUST be valid Infrahub attribute kinds. The deprecated `String` kind MUST NOT be used.
- **FR-017**: `DeploymentDiffFile` MUST hold the diff as file content through
  `CoreFileObject` rather than as a bounded `Text` attribute, so a first-configuration diff
  the size of a whole device configuration is stored intact.

#### Relationships

- **FR-020**: `DeploymentState` MUST relate to `DcimGenericDevice` — **not** to `DcimDevice`
  and **not** to `DcimFabricSwitch` — with `cardinality: one`, `kind: Attribute`, and
  **`optional: true`** (amended from `optional: false`; see FR-010 and research R3 — mandatory
  makes the device permanently undeletable). The four device kinds are siblings; a relationship naming `DcimDevice`
  would be invisible to every fabric switch, and all four families are deployed by this
  feature.
- **FR-021**: The relationship to the device MUST be declared one-sided, with no reverse
  relationship added to `DcimGenericDevice` and no `identifier`, following the
  `AvdArtifact.device` precedent. A reverse side would put a deployment relationship on the
  device kinds themselves, which is the surface User Story 5 exists to keep clear.
- **FR-022**: `DeploymentState` MUST relate to `DeploymentDiffFile` with `kind: Component`,
  `cardinality: one`, `optional: true`, and `DeploymentDiffFile` MUST relate back with
  `kind: Parent`, `cardinality: one`, `optional: false`. Both sides MUST carry the same
  `identifier`.
- **FR-023**: All relationship `peer` values MUST use the full kind (namespace + name) and all
  relationship names MUST be snake_case.
- **FR-024**: The schema MUST NOT use an `extensions` block. Nothing in this feature modifies
  an existing node, and the one-sided device relationship is what makes that possible.
- **FR-025**: Deleting a device MUST NOT be blocked by the existence of its deployment record.
  **Verified and delivered** by `optional: true` on the device relationship: with it, the
  delete succeeds. `on_delete` is eliminated — its only value, `cascade`, would delete the
  *switch* when a record is deleted (research R3).

  The second half of the original wording — "MUST NOT leave that record behind pointing at a
  device that no longer exists" — **is not delivered by the schema and cannot be**. A deleted
  device leaves its record with an unresolvable peer. Sweeping those records is a stated
  obligation of the executor cycle, not a property of this model.

#### Display & Identification

- **FR-040**: `DeploymentState` MUST define `human_friendly_id` as `["name__value"]` (amended
  from `["device__name__value"]`, which is not implementable — research R3). The record is
  still identified by the device's name; the name is carried on the record rather than
  traversed to.
- **FR-041**: `DeploymentState` MUST define a `display_label` that renders the device name.
  `DeploymentDiffFile` MUST define a `human_friendly_id` that resolves through its parent
  record to the device. **Satisfied as written**: `state__name__value`. The two-hop path
  `state__device__name__value` was tried first and rejected by the server; the fallback clause
  became unnecessary once FR-010 was reversed (research R2, R3).
- **FR-042**: Attributes MUST use `order_weight` following the project convention — 900-999
  primary relationships, 1000-1099 identifiers, 1100-1499 secondary, 1500-1999 tertiary,
  2000+ metadata. Status and the timestamps are the primary reading of the node and MUST sort
  above the suspension fields.
- **FR-043**: `DeploymentState` MUST be reachable in the Infrahub UI, because User Story 1 is
  the point of the feature. Menu placement is a `menus/` change and belongs to a separate
  cycle; this cycle MUST NOT leave the node unreachable in the meantime.
- **FR-044**: `DeploymentDiffFile` MUST set `include_in_menu: false`. It is read through its
  parent record, matching `AvdHostvarFile`.

#### Uniqueness Constraints

- **FR-050**: `DeploymentState` MUST enforce one record per device. **Amended**: the
  constraint is `[[name__value]]`, not `[[device]]` — Infrahub rejects a uniqueness constraint
  over an optional relationship (`cannot use device relationship, relationship must be
  mandatory`), and FR-025 requires the relationship to be optional. Because `name` is the
  device's name, uniqueness on it is uniqueness per device **provided the reconciler keeps the
  two in step**, which FR-010 makes its responsibility. This is a genuine weakening: the graph
  now enforces one record per *name* rather than one per device object.
- **FR-051**: `DeploymentDiffFile` MUST define `uniqueness_constraints: [[state]]` — one diff
  per record, mirroring `AvdHostvarFile`'s `[["artifact"]]`.
- **FR-052**: Uniqueness constraints MUST use the `__value` suffix for attribute references
  and bare names for relationship references.

#### The no-generation rule

- **FR-060**: Nothing MUST generate from a deployment kind. No generator, trigger rule, or
  artifact definition may take a `Deployment*` node as an input, a target, or a trigger
  source.
- **FR-061**: A unit test under `tests/unit` MUST fail when any `CoreNodeTriggerRule` in
  `triggers.yml` names a deployment kind as its `node_kind`, or when any generator or artifact
  definition in `.infrahub.yml` targets one. The rule in FR-060 is worth nothing if the only
  thing holding it is this document.
- **FR-062**: The rule MUST also be stated in `AGENTS.md`, so it is in front of the next
  person to add a trigger rather than only in a spec directory.

#### Regeneration and validation

- **FR-070**: `src/solution_arista_avd/protocols.py` MUST be regenerated after the schema
  loads, per the constitution's schema-first workflow. It MUST NOT be hand-edited.
- **FR-071**: `uv run infrahubctl schema check schemas/` MUST pass before the schema is
  loaded into any branch.

### Key Entities

- **DeploymentState**: one record per device, holding that device's standing against its
  rendered intent. Carries the device's name (its identity — see FR-010), a status, the timestamp of the last confirmed match, the timestamp
  of the last comparison, the last attempt and its error, and a per-device suspension flag with
  a reason. Relates to exactly one `DcimGenericDevice` and optionally owns one diff. It is the
  `AvdArtifact` of this design: the small parent node that the heavier file hangs off.
- **DeploymentDiffFile**: the device-computed difference between the device and its intent,
  from the most recent comparison that found one. Inherits `CoreFileObject`, so the content is
  a file rather than a bounded attribute. Owned by exactly one `DeploymentState`. It is the
  `AvdHostvarFile` of this design.

## Assumptions

- **`Deployment` is a new namespace, and that is the right call.** The kind spans all four
  device families, so `Avd` would be wrong (it would claim FRR routers and the firewall are
  AVD-rendered) and `Dcim` would be wrong (this is not inventory). The repository already adds
  namespaces beyond the base set — `Service` is one — so a new one is conventional here rather
  than exceptional.
- **`branch: agnostic` is the mechanism behind "main-only".** The decision log says deploys
  happen only on `main` and a branch dry run writes no state. Branch-agnostic nodes deliver
  exactly that shape: one copy of the fact, invisible in proposed changes, unaffected by a
  merge. If schema validation rejects an agnostic node relating to branch-aware devices, the
  implementing cycle escalates rather than silently falling back to branch-aware.
- **The executor's own configuration is not modelled here.** Poll interval, the 60-second
  floor, and the every-fourth-cycle firewall multiple are service configuration, not device
  state. They belong to the executor cycle. If they later want to be operator-editable in the
  UI, that is a further schema cycle and a separate node.
- **Deployment state is per device, not per artifact.** Settled in the decision log: a device
  either matches or it does not. Artifact-level state is what item 7 rejected for stranding
  partial failures.
- **The reconciler upserts on the device relationship.** This spec fixes the uniqueness
  constraint that makes that the only safe option; the reconciler's obligation to use it is
  asserted in its own cycle.
- **How often the reconciler writes is left open, and the schema supports either answer.**
  Decision log item 10 raises the write-volume hazard: Infrahub versions every mutation, so a
  heartbeat per cycle is a standing cost. Splitting `last_checked_at` from `last_confirmed_at`
  means the executor cycle can choose to write every cycle (an operator can then see the
  reconciler is alive) or only when something changes (fewer versioned writes, but a stale
  record is ambiguous between "fine" and "the loop died"). Both readings are reasonable and
  the schema does not force one. **This is the decision the executor cycle must make
  explicitly rather than inherit** — at 600 seconds across roughly fifteen devices it is about
  2,000 versioned writes a day, which is the number to hold that choice against.

## Out of scope

Everything below is from the decision log and is deliberately **not** in this cycle:

- The reconciler loop itself — the 600-second default, the 60-second floor, the
  every-fourth-cycle firewall check, and the per-cycle cleanup sweep for abandoned EOS
  configuration sessions and Junos locks.
- Lifting `scripts/provision_lab.py` into an importable module, and the tests against
  `_assert_eos_lifeline`, `_assert_junos_scope` and `_eos_config_lines` that the lift is the
  moment to add.
- The Nornir device layer and the `nornir-infrahub` inventory over `DcimGenericDevice`.
- The branch dry run.
- The two defects the review found — the dead `branch_scope: other_branches` webhook at
  `repository_checks.yml:138`, and the overstatement at
  `docs/docs/supported-capabilities.md:116`. Both are real, both are independent of this
  schema, and both should be fixed on their own rather than folded in here.
- The decision log's open items: ordering against Vidra, credentials and blast radius, where
  the executor lives, and where an alert goes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run infrahubctl schema check schemas/` passes with zero validation errors.
- **SC-002**: After loading, a deployment record can be created against a device of each of
  the four kinds — `DcimFabricSwitch`, `DcimDevice`, `SecurityFirewall`,
  `ComputePhysicalServer` — and all four succeed.
- **SC-003**: A record's human-friendly identifier reads as the device's name, and the record
  is reachable in the UI without knowing its UUID.
- **SC-004**: Creating a second record for a device that already has one is rejected.
- **SC-005**: A record created with only a device relationship reads back as
  `never_deployed` and not suspended, without either value having been supplied.
- **SC-006**: A branch created after a record exists shows no deployment records in its diff,
  and a proposed change raised from that branch proposes none.
- **SC-007**: Deleting a deployment record removes its diff; no orphaned diff remains.
- **SC-008**: The unit test from FR-061 passes against the current repository and fails when a
  trigger rule naming a deployment kind is added to `triggers.yml`.
- **SC-009**: `uv run invoke lint` and `uv run pytest tests/unit` both pass, and
  `src/solution_arista_avd/protocols.py` regenerates with the two new kinds present and no
  hand edits.
- **SC-010**: An operator asked "has this device been confirmed to match since the last
  merge?" can answer it from the Infrahub UI alone, without a shell.

## Next cycles

The routing hook detected more than one Infrahub artifact type in this feature. Schema is
first because everything else depends on the data model. After this cycle completes, re-run
the specify command for:

1. **Menu** — placing `DeploymentState` in the sidebar (FR-043's permanent home).
2. **Check** — if the no-generation rule (FR-060) should also be enforced as a proposed-change
   check rather than only as a unit test.

The reconciler service, the Nornir layer and the `provision_lab.py` lift are not Infrahub
artifact types and do not route through this extension; they are ordinary feature work in a
later cycle.
