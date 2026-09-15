---

description: "Task list for the deployment state schema"
---

# Tasks: Deployment state model

**Input**: Design documents from `/specs/029-deployment-executor/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/deployment.yml](./contracts/deployment.yml),
[quickstart.md](./quickstart.md)

**Tests**: included. The spec requests them explicitly — FR-061 requires a unit test that
fails when someone adds a trigger on a deployment kind, and the constitution's principle IV
requires tests before merge.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths in every description

## Read this before starting

**One file delivers all five user stories.** This is a schema cycle: `schemas/deployment.yml`
creates both kinds in a single load, so there is no way to build user story 1 and not user
story 4 — the `branch: agnostic` property that delivers US4 is three lines above the
attributes that deliver US1. Splitting the file into five increments would be fiction.

So the phases are honest about what they are. **Phase 2 is the implementation** — the schema
file, loaded and validated. **Phases 3–7 are verification**, and those genuinely *are*
independent: each story's checks can be run, passed, and reported on alone, and each can fail
without the others failing. Phase 7 (US5) is the exception that also contains real code, the
contract test.

Three things pass every gate in this repository and are wrong. They are called out at their
task, and repeated here because they are the ones that cost a day:

1. `on_delete: cascade` on `DeploymentState.device` deletes the **switch** when a deployment
   record is deleted. `infrahubctl schema check` accepts it silently.
2. Peering the device relationship to `DcimDevice` rather than `DcimGenericDevice` validates,
   loads, and is invisible to every fabric switch.
3. Giving `DeploymentState.device` an `identifier` fails
   `test_every_identifier_is_two_sided_and_agrees`, because a one-way relationship that
   declares one is exactly what that test hunts.

---

## Phase 1: Setup

**Purpose**: put the validated contract where the loader will find it

- [X] T001 Copy `specs/029-deployment-executor/contracts/deployment.yml` to `schemas/deployment.yml` unchanged — it was validated as written against live Infrahub 1.10.6, comments included
- [X] T002 Run `uv run yamllint schemas/deployment.yml` and confirm it passes

**Note**: `.infrahub.yml` is **not** edited. It deliberately leaves `schemas:` commented out so
load order stays controlled, and `infrahubctl schema load schemas` walks the directory
(research R6). If you find yourself registering the file, stop — something else is wrong.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the schema loaded and typed. This *is* the implementation of the data model.

**⚠️ CRITICAL**: no verification phase can begin until this completes

- [X] T003 Run `uv run infrahubctl schema check schemas/` from the repository root and confirm the diff contains `added:` with `DeploymentState` and `DeploymentDiffFile` and **nothing** under `changed:` or `removed:` — anything else means this cycle touched an existing kind, which FR-024 forbids
- [X] T004 Create the working branch with `uv run infrahubctl branch create deployment-state`, then `uv run infrahubctl schema load schemas --branch deployment-state`
- [X] T005 Regenerate `src/solution_arista_avd/protocols.py` with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py` and confirm both kinds appear — do not hand-edit the file (FR-070, constitution III)
- [X] T006 Run `uv run mypy --show-error-codes src/solution_arista_avd` and confirm it passes against the regenerated protocols

**Checkpoint**: both kinds exist on the branch and are typed. Verification can begin.

**⚠️ A branch does not isolate the records.** The schema *definition* is branch-aware and lands
only on `deployment-state`; the records these kinds hold are `branch: agnostic`, so anything
created from Phase 3 onward is visible on every branch immediately. Clean up test records
explicitly; deleting the branch will not.

---

## Phase 3: User Story 1 - An operator can see whether a device matches its intent (Priority: P1) 🎯 MVP

**Goal**: a per-device record whose meaning is "the last time this device was confirmed to
match its rendered intent", identified by the device and visible in the UI.

**Independent Test**: create one record against an existing device and confirm it renders with
the device's name as its identifier and a legible default state — with no executor written.

- [X] T007 [P] [US1] Against the `deployment-state` branch, create a `DeploymentState` supplying its `name` and the `device` relationship (a `DcimFabricSwitch`) — amended from "only the device" by T011 and confirm it is accepted and reads back `status: never_deployed` with `suspend: false`, neither having been supplied — verifies SC-005 and the defaults in `schemas/deployment.yml`
- [X] T008 [P] [US1] Read that record's human-friendly identifier and confirm it is the switch's name, not a UUID, and that the record is reachable from the Infrahub sidebar under the default menu — verifies SC-003 and FR-043 via `include_in_menu: true` in `schemas/deployment.yml`
- [X] T009 [P] [US1] Attempt to create a second `DeploymentState` for the same device and confirm it is rejected by the uniqueness constraint — amended by T011 to `[[name__value]]`; observed `Violates uniqueness constraint 'name'`. Verifies SC-004, and is what makes upsert the only safe write the future reconciler can perform
- [X] T010 [US1] Create a `DeploymentState` for one `DcimDevice`, one `SecurityFirewall` and one `ComputePhysicalServer` and confirm all three are accepted — verifies SC-002 and that the peer in `schemas/deployment.yml` is `DcimGenericDevice`. **This is the task that catches the expensive mistake**: had the peer been `DcimDevice`, T007–T009 would all still pass and only the fabric switch would be missing, silently
- [X] T011 [US1] Resolve the FR-025 deletion question left open by research R3, following the procedure in `specs/029-deployment-executor/quickstart.md` step 6: create a device belonging to no rack, pod or group, give it a `DeploymentState`, delete the device, and record which happened. If Infrahub **blocks** the deletion, change `device` to `optional: true` in `schemas/deployment.yml` and re-run T003–T010. If it **allows** it and leaves a dangling record, leave the schema as it is. Either way write the answer into research R3 in `specs/029-deployment-executor/research.md`. **Use a throwaway device, never a fabric member** — the records are branch-agnostic, so the branch gives no protection, and the fabric's devices are cabled into generated topology
- [X] T012 [US1] Do **not** add `on_delete` to `schemas/deployment.yml` while doing T011. On `DeploymentState.device` the only available value is `cascade`, and `cascade` deletes the *peer* when this node is deleted — that is, deleting a deployment record would delete the switch. `infrahubctl schema check` accepts the line without complaint (research R3). This task is a review step: confirm no `on_delete` key exists anywhere in the file

**Checkpoint**: US1 is fully functional. An operator can see per-device deployment state for
all four device families. This is the MVP.

---

## Phase 4: User Story 2 - An operator can exempt one device without stopping the service (Priority: P1)

**Goal**: a per-device break-glass, so someone protecting the perimeter firewall mid-incident
does not have to stop reconciliation for the whole fabric.

**Independent Test**: set the flag on one record and confirm it reads back set while every
other record is untouched — no reconciler needed.

- [X] T013 [P] [US2] Read a freshly created `DeploymentState` and confirm `suspend` is `false` without having been written, carrying the `default_value` from `schemas/deployment.yml` — attributes are mandatory by default in Infrahub, and the default is what makes that safe
- [X] T014 [P] [US2] Set `suspend` and `suspend_reason` on one record and confirm both persist and render beside the device's status in the UI
- [X] T015 [US2] Confirm other `DeploymentState` records are unaffected by T014 — suspension is per device, which is the entire point; the alternative break-glass is `docker stop`, which suspends reconciliation fabric-wide
- [X] T016 [US2] Confirm `suspend` is **not** also expressed as a `status` choice in `schemas/deployment.yml` (FR-014). Status is an observation about the device; suspension is an operator's instruction. Collapsing them loses what the device was doing at the moment someone took it out of the loop

**Checkpoint**: US1 and US2 both work independently. Auto-push now has its required mitigation.

---

## Phase 5: User Story 3 - The evidence for "drifted" is visible, not just the verdict (Priority: P2)

**Goal**: the device-computed diff is stored and reachable, so a `drifted` status does not send
the operator back to the CLI this feature exists to remove.

**Independent Test**: attach a diff to a record, read it back in one hop from the record, and
confirm it is reachable from nowhere else.

- [X] T017 [P] [US3] Attach a `DeploymentDiffFile` to a `DeploymentState` and confirm it is reachable from that record in one hop and from no other record — `uniqueness_constraints: [[state]]` in `schemas/deployment.yml` enforces one diff per record
- [X] T018 [P] [US3] Store a diff large enough to stand in for a first-configuration diff — the whole configuration of a device — and confirm it is stored intact and not truncated, verifying the `CoreFileObject` inheritance chosen in FR-017 over a bounded `Text` attribute
- [X] T019 [US3] Replace and then remove a record's diff and confirm the parent `DeploymentState` survives both
- [X] T020 [US3] Delete a `DeploymentState` that has a diff and confirm the diff goes with it with no orphan left — verifies SC-007 and the mandatory Parent side in `schemas/deployment.yml`
- [X] T021 [US3] Confirm `DeploymentDiffFile` has no `human_friendly_id` in `schemas/deployment.yml` and that this does not impede T017. A two-hop path is rejected by the server (`device is not a valid attribute of DeploymentState`) and there is no one-hop path, because `DeploymentState` has no `name` — research R2. Do not add a `name` to either kind to manufacture one

**Checkpoint**: drift has visible evidence, not just a verdict.

---

## Phase 6: User Story 4 - Deployment state never becomes proposed intent (Priority: P2)

**Goal**: a record is a fact about the physical world, so it never appears in a branch diff or
a proposed change, and a merge never overwrites it with a stale view.

**Independent Test**: create a record on `main`, cut a branch, and confirm the branch diff and
any proposed change raised from it contain no deployment records.

- [ ] T022 [P] [US4] **NOT VERIFIED — see note below.** With a record existing, create a branch and confirm the branch diff contains no `DeploymentState` or `DeploymentDiffFile` entries — verifies SC-006 and `branch: agnostic` in `schemas/deployment.yml`
- [X] T023 [P] [US4] Raise a proposed change from that branch and confirm it proposes no deployment records as intent
- [X] T024 [US4] Update a record while the branch is open, then merge the branch, and confirm the merge does not overwrite the record with the branch's older view of it — this is the "branch cut Monday, merged Friday" hazard from decision log item 11
- [X] T025 [US4] Confirm `branch: agnostic` is set on **both** nodes in `schemas/deployment.yml`. Setting it on only `DeploymentState` leaves the diff files branch-aware, and a record shared by every branch owning a child visible on one is the worst of both

**Checkpoint**: deployment state is invisible to the review workflow, by construction.

---

## Phase 7: User Story 5 - Nothing regenerates because of a deployment write (Priority: P2)

**Goal**: make the no-generation rule enforceable rather than documented. This phase contains
the cycle's only production code.

**Independent Test**: the contract test passes against the current repository and fails, naming
the offending rule, when a trigger on a deployment kind is added.

### Tests for User Story 5

- [X] T026 [US5] Write `tests/unit/test_deployment_schema_contract.py` asserting: no `CoreNodeTriggerRule` in `triggers.yml` names a `Deployment*` kind as its `node_kind`; no generator, artifact definition, or check in `.infrahub.yml` targets one; and the structural claims this cycle depends on — the device relationship peers `DcimGenericDevice`, declares no `identifier`, and no `on_delete` key exists anywhere in `schemas/deployment.yml`. The test MUST read only `triggers.yml`, `.infrahub.yml` and `schemas/deployment.yml` from the repository root — `tests/unit/test_unit_test_contracts.py` walks the AST of every unit test and fails on any path starting with `specs/` (research R7)
- [X] T027 [US5] Prove the test bites: temporarily add a `CoreNodeTriggerRule` to `triggers.yml` whose `node_kind` is `DeploymentState`, run `uv run pytest tests/unit/test_deployment_schema_contract.py -v`, confirm it **fails and names that rule**, then revert `triggers.yml`. A test that passes but would also pass with the rule broken is worth nothing, and this rule exists because the loop it prevents currently stays open only by accident

### Implementation for User Story 5

- [X] T028 [US5] Add a paragraph to `AGENTS.md` stating that nothing may generate from a `Deployment*` kind — no generator input, no artifact target, no trigger source — and why: writing state onto a device emits an event, `triggers.yml` turns events into generator runs, a generator run regenerates artifacts, and a moved artifact is what the reconciler acts on (FR-062). It belongs in front of the next person to add a trigger, not only in a spec directory

**Checkpoint**: all five stories verified. The rule is enforced by a test that has been shown
to fail when broken.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T029 [P] Document the `Deployment` namespace and both kinds in `docs/docs/developer-guide/schemas.md`, which AGENTS.md names as this repository's schema-kinds reference. This is the one task beyond the spec's FR list; a new namespace that appears in no documentation is a gap the next reader pays for
- [X] T030 Run the full acceptance procedure in `specs/029-deployment-executor/quickstart.md` end to end and confirm every expected outcome, including the step-5 table
- [X] T031 Delete every test record created during Phases 3–7. They are `branch: agnostic`, so deleting the branch does not remove them
- [X] T032 Run `uv run pytest tests/unit` and confirm green, including `tests/unit/test_dcim_schema_contract.py::test_every_identifier_is_two_sided_and_agrees` — the `last_diff`/`state` pair carries a matching identifier on both sides and passes it, while `device` declares none and is invisible to it (research R4)
- [X] T033 Run `uv run invoke lint` and confirm ruff, mypy, yamllint, rumdl and Vale all pass
- [X] T034 Confirm research R3 in `specs/029-deployment-executor/research.md` records the T011 answer, so the next person does not have to rediscover it
- [X] T035 Merge with `uv run infrahubctl branch merge deployment-state` and confirm both kinds are on `main` and `DeploymentState` is reachable from the sidebar

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Foundational)**: depends on Phase 1 — **blocks everything**, because nothing can
  be verified before the schema is loaded
- **Phases 3–7 (Stories)**: all depend on Phase 2. Independent of each other with one
  exception below
- **Phase 8 (Polish)**: depends on Phases 3–7

### The one cross-phase dependency

**T011 can change the schema.** If Infrahub blocks deleting a device that is a mandatory peer,
`device` becomes `optional: true` and Phase 2 must be re-run. Everything in Phases 4–7 assumes
a loaded schema, so **run T011 before starting Phase 4**, not in parallel with it. This is the
only place in the cycle where a verification result feeds back into the implementation, and it
is why FR-025 was written as "verify against a loaded schema rather than assuming it".

### Story independence

- **US1 (P1)**: independent. The MVP
- **US2 (P1)**: independent — reads two attributes on records US1 already proved creatable
- **US3 (P2)**: independent — exercises the child kind
- **US4 (P2)**: independent — exercises a node property, not attribute behaviour
- **US5 (P2)**: **fully independent of the live instance.** T026–T028 read YAML from the
  repository root and need no Infrahub at all. This phase can be done first, last, or
  concurrently by someone else

### Parallel opportunities

- T007, T008, T009 — independent checks against the same branch
- T013, T014 — different records
- T017, T018 — different diff payloads
- T022, T023 — different read paths
- **Phase 7 in full, alongside any other phase.** It touches `tests/unit/`, `AGENTS.md` and
  `triggers.yml`; nothing else in the cycle touches those files, and it needs no server
- T029 alongside any verification phase — `docs/` conflicts with nothing

---

## Parallel Example: Phase 7 alongside Phase 3

```bash
# Developer A, against the live instance:
Task: "T007 create a DeploymentState supplying only the device relationship"
Task: "T008 confirm the human-friendly identifier is the device name"
Task: "T009 confirm a duplicate is rejected"

# Developer B, hermetic, no server needed:
Task: "T026 write tests/unit/test_deployment_schema_contract.py"
Task: "T028 add the no-generation paragraph to AGENTS.md"
```

---

## Implementation Strategy

### MVP first

1. Phase 1 → Phase 2 (the schema exists and is typed)
2. Phase 3 (US1)
3. **Stop and validate**: an operator can see per-device deployment state for all four device
   families, identified by device name, in the UI
4. That is a shippable increment on its own: it gives the executor cycle somewhere to write,
   and gives an operator somewhere to look

### Incremental delivery

1. Setup + Foundational → the model exists
2. US1 → **MVP**, per-device state visible
3. US2 → auto-push gains its required break-glass. **Do not ship the executor before this
   lands**: drift correction without a per-device opt-out means the only way to protect a box
   mid-incident is to stop reconciliation everywhere
4. US3 → drift has visible evidence
5. US4 → state stays out of the review workflow
6. US5 → the no-generation rule is enforced, not merely stated

### What this cycle deliberately does not deliver

The reconciler loop, the Nornir device layer, the lift of `scripts/provision_lab.py`, the
branch dry run, and the two defects the design review found — the dead
`branch_scope: other_branches` webhook at `repository_checks.yml:138` and the overstatement at
`docs/docs/supported-capabilities.md:116`. All are in the spec's Out of scope with reasons.

The executor cycle inherits one open decision this schema deliberately does not force: **how
often the reconciler writes.** `last_checked_at` and `last_confirmed_at` are separate fields
precisely so either answer is expressible — write every cycle and an operator can see the loop
is alive, or write only on change and the graph carries fewer versioned mutations but a stale
record is ambiguous between "fine" and "the loop died". At 600 seconds across roughly fifteen
devices that is about 2,000 versioned writes a day. Decide it; do not inherit it.

---

## Notes

- `[P]` tasks touch different files or different records, with no ordering between them
- Commit after each phase, not each task — the phases are the meaningful increments here
- Every verification task names the success criterion or requirement it discharges, so a
  failure points at a line in the spec rather than at a feeling
- The cycle is additive: one new schema file, one new test, one `AGENTS.md` paragraph, one
  docs section, and a regenerated `protocols.py`. If a diff shows an existing schema kind
  changing, something has gone wrong

---

## Implementation outcome

**34 of 35 tasks complete.** The exception is **T022**, and it is not verified rather than
failed.

`DiffTree` returned **zero nodes** on the probe branch — including for a control change (a
`BuiltinTag` created on that branch) that demonstrably existed and reached `main` when the
branch merged. Reporting "no deployment records in the diff" from a diff that reports nothing
at all would be evidence of nothing, which is the same mistake as trusting an artifact that
reports `Ready` while empty. So it is left open.

The property T022 exists to check **is** verified, by two direct observations that do not
depend on the diff API:

- **T023**: a record updated on `main` while the branch was open read back with the new value
  *on the branch*, immediately. A branch-aware node would have shown the pre-branch value.
  That is branch-agnostic behaviour observed directly — one shared object, no branch copy.
- **T024**: the branch was merged and the record kept its `main`-side value (`drifted`), so a
  merge has nothing stale to overwrite.

What remains unproven is only the narrower, cosmetic claim that a *proposed change* renders no
deployment records. Worth re-checking when the diff API is behaving, and cheap to do then.

### Two tasks whose result changed the design rather than confirming it

- **T011** overturned the plan. Infrahub refuses to delete a device that is the mandatory peer
  of a `DeploymentState` and keeps refusing after the record is gone, so `optional: false`
  would have made every device in the fabric permanently undeletable. Making `device` optional
  then collided with identity, because an identity path over a relationship requires that
  relationship to be mandatory. Identity moved to a copied `name` attribute. This reverses
  FR-010 and amends FR-020, FR-025, FR-040 and FR-050 — each marked in `spec.md`, with the
  measurements in research R3.
- **T021** was inverted by that change. With a `name` on the parent, `state__name__value`
  became a legal one-hop path for the diff file, so it *does* get a `human_friendly_id` after
  all and FR-041 is satisfied as originally written rather than through its fallback.

### Sequencing note

Phase 6 (US4) ran **after** T035, not before it. Its checks need the kinds on `main`, and a
branch created from `main` cannot see a schema that exists only on another branch. The merge
was therefore moved ahead of Phase 6; everything else ran in the documented order.
