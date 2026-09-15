# Implementation Plan: Deployment state model

**Branch**: `029-deployment-executor` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/029-deployment-executor/spec.md`

## Summary

Add two nodes in a new `Deployment` namespace — `DeploymentState` (one per device) and
`DeploymentDiffFile` (its `CoreFileObject` child) — in one new file `schemas/deployment.yml`.
They give the deployment executor described in
[grilling-decision-log.md](./grilling-decision-log.md) somewhere to record **the last time
each device was confirmed to match its rendered intent**, in the source of truth rather than
in a SQLite file inside a container.

The design is settled; Phase 0 was about which parts of it Infrahub 1.10.6 actually accepts.
The schema in [contracts/deployment.yml](./contracts/deployment.yml) has been checked against
the live instance and validates. Three findings changed the plan:

1. **`branch: agnostic` works** with a mandatory relationship to a branch-aware
   `DcimGenericDevice`. The spec said escalate if not; no escalation needed.
2. **A two-hop `human_friendly_id` is rejected** (`device is not a valid attribute of
   DeploymentState`). At plan time this meant the diff file got none; implementation later
   made a one-hop path available. See the note below.
3. **`on_delete` is off the table, and its obvious use is dangerous.** On
   `DeploymentState.device`, `cascade` deletes the *peer* — deleting a deployment record would
   delete the switch — and `infrahubctl schema check` accepts the line without complaint.

**What implementation then changed.** The FR-025 verification task (T011) did not confirm the
plan; it overturned part of it. Infrahub refuses to delete a device that is the mandatory peer
of a `DeploymentState`, and **keeps refusing after the record is deleted**, naming a record
that no longer exists — so `optional: false` would have made every device in the fabric
permanently undeletable. Making `device` optional then collided with identity: Infrahub
requires any relationship used in `human_friendly_id` or `uniqueness_constraints` to be
mandatory. The resolution moves identity onto a copied `name` attribute, which reverses FR-010
and amends FR-020, FR-040 and FR-050. Research R3 carries the measurements; the spec marks each
amended requirement in place. One knock-on: with a `name` on the parent, the diff file's
`human_friendly_id` became expressible one-hop after all, so FR-041 is satisfied as originally
written rather than through its fallback.

Scope is the schema only. The reconciler loop, the Nornir layer and the `provision_lab.py`
lift are later cycles, listed in the spec's Out of scope.

## Technical Context

**Language/Version**: Python 3.12.13 (project constraint >=3.11,<3.14). No Python is written
this cycle except one unit test.

**Primary Dependencies**: Infrahub 1.10.6 (live instance verified), `infrahub-sdk` 1.22.0.
No new dependency.

**Storage**: Infrahub graph (Neo4j). The new kinds are `branch: agnostic`, so a record is one
fact shared by every branch.

**Testing**: pytest, `tests/unit`. One new hermetic test file reading `triggers.yml` and
`.infrahub.yml`; no Infrahub instance required to run it.

**Target Platform**: Infrahub schema, loaded with `infrahubctl schema load schemas`.

**Project Type**: Infrahub schema artifact (routed by `infrahub-speckit`; skill
`infrahub-managing-schemas` loaded for both specify and plan).

**Performance Goals**: not applicable to this cycle. The write-volume question the schema
enables — whether the reconciler writes a timestamp every cycle or only on change, roughly
2,000 versioned writes a day at 600s across ~15 devices — is explicitly deferred to the
executor cycle and recorded in the spec's assumptions so it is decided rather than inherited.

**Constraints**: additive only. No existing node, generic, or `.infrahub.yml` entry is
modified; the Phase 0 schema check confirms the diff contains `added:` and nothing else.

**Scale/Scope**: one new schema file (~170 lines with comments), one new test file, one
`AGENTS.md` paragraph, one regenerated `protocols.py`.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1.*

| Principle | Status | Evidence |
| --- | --- | --- |
| **I. Schema-Driven Architecture** | **Pass** | This cycle *is* the schema, and it precedes the code that will use it — the executor cycle cannot start before the model exists. `Deployment` is a new namespace; the constitution permits namespaces beyond the base list ("other approved project namespaces") and the repository already adds them (`Service`). Justified in the spec's Assumptions: the kind spans all four device families, so `Avd` would falsely claim FRR and Junos boxes are AVD-rendered and `Dcim` would imply inventory. Protocol regeneration is required by FR-070 and is step 4 of the quickstart. |
| **II. Idempotent Operations** | **Pass (not engaged)** | No generator is added or changed. The constraint this cycle contributes to idempotence is `uniqueness_constraints: [[name__value]]`, which makes upsert-on-name the only safe write the future reconciler can perform — and, because `name` is the device's name, one record per device only so long as the reconciler keeps the two in step. `$infrahub-test-generator-idempotence` is not applicable — there is no generator. |
| **III. Type Safety** | **Pass** | `protocols.py` regenerated, not hand-edited (FR-070). mypy in the quickstart gate. No GraphQL query is added, so no `*_query.py` is needed. |
| **IV. Test-Required Quality** | **Pass, with one documented exception** | A new `tests/unit/test_deployment_schema_contract.py` covers FR-060/061 and the schema's structural claims. All linters run via `uv run invoke lint`. **Exception**: `$infrahub-run-integration-tests` is nominally required for every Infrahub change. The change here is a YAML schema file with no Python consumer yet — nothing in the integration suite can exercise it, because the code that will read these kinds is a later cycle. The substitute is stronger than a no-op integration run and is already done: the schema was validated against a live Infrahub 1.10.6, and the quickstart's step 5 is a concrete live-instance acceptance procedure. Recorded in Complexity Tracking. |
| **V. Convention-Based Structure** | **Pass** | `schemas/deployment.yml` matches the flat-file convention (`schemas/dcim_extensions.yml`, `schemas/device_design.yml`). Test named for the contract tests it sits beside. Node/attribute/relationship naming validated by `schema check`. |

**Post-Phase-1 re-check**: unchanged.

**Post-implementation re-check**: still passing, with one line worth noting against principle
I. The shipped model keeps identity on an attribute rather than on the relationship, which is
weaker modelling than the spec intended — the graph enforces one record per *name*, not one
per device object. That is not a schema-first violation (the schema is still authoritative and
was defined before any consumer), but it does hand the reconciler an obligation the graph used
to be asked to carry, and it is written into FR-010 and FR-050 rather than left implicit.

## Project Structure

### Documentation (this feature)

```text
specs/029-deployment-executor/
├── grilling-decision-log.md   # Input: the adversarial design review
├── spec.md                    # Schema design specification
├── plan.md                    # This file
├── research.md                # Phase 0: seven findings, all from the live instance
├── data-model.md              # Phase 1: entities, transitions, validation rules
├── quickstart.md              # Phase 1: runnable validation procedure
├── contracts/
│   └── deployment.yml         # Phase 1: the schema file, validated as written
├── checklists/
│   └── requirements.md        # Spec quality checklist
└── tasks.md                   # Phase 2 (/speckit-tasks — not created here)
```

### Source code (repository root)

```text
schemas/
└── deployment.yml                          # NEW — copied from contracts/, the only schema change

src/solution_arista_avd/
└── protocols.py                            # REGENERATED — gains the two kinds

tests/unit/
└── test_deployment_schema_contract.py      # NEW — FR-060/061 plus structural claims

AGENTS.md                                   # MODIFIED — one paragraph stating the no-generation rule
```

**Structure Decision**: additive, four files, no existing schema touched. `schemas/` is flat
at the top level for cross-cutting files and subdivided by domain (`avd/`, `security/`,
`service/`) for grouped ones. A single file at the top level matches `device_design.yml` and
`management.yml`. It is not placed under a new `schemas/deployment/` directory because one
file does not need one, and it is not folded into `schemas/objects/objects.yml` — whose
`AvdArtifact` shape it borrows — because that file is AVD artifact storage and these kinds
are not AVD-specific.

`.infrahub.yml` is **not** modified: it deliberately leaves `schemas:` commented out so load
order stays controlled, and `infrahubctl schema load schemas` walks the directory (research
R6).

## What the implementing cycle must not do

Three specific things, each of which passes every automated gate in this repository:

1. **Add `on_delete: cascade` to `DeploymentState.device`.** It reads like cleanup and it
   deletes switches. Research R3.
2. **Peer the device relationship to `DcimDevice`.** It validates, loads, and is invisible to
   every fabric switch. The quickstart's step-5 row 4 exists to catch it.
3. **Give `DeploymentState.device` an `identifier`.** A one-way relationship that declares one
   fails `test_every_identifier_is_two_sided_and_agrees`; declaring none is the documented
   arrangement `AvdArtifact.device` uses. Research R4.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| No `$infrahub-run-integration-tests` evidence (constitution IV) | The change is a schema YAML file with no Python consumer until a later cycle. The integration suite has nothing to exercise. | Writing an integration test now would mean writing the reconciler now, which is a different cycle and the thing the spec deliberately scoped out. The substitute — validation against a live Infrahub 1.10.6 plus the quickstart's live acceptance procedure — tests the actual artifact rather than a stub around it. |
| New `Deployment` namespace (constitution I names a conventional list) | The kind spans `DcimFabricSwitch`, `DcimDevice`, `SecurityFirewall` and `ComputePhysicalServer`. | `Avd` would claim FRR routers and the firewall are AVD-rendered — they are not, and `get_avd_type` raises for their roles. `Dcim` would imply inventory rather than observed state. The repository already adds namespaces past the base set (`Service`), so this is conventional here. |

## Phase 2 preview (not executed by this command)

`/speckit-tasks` will break this into roughly: place the schema file; check and load on a
branch; regenerate protocols and run mypy; write the contract test and prove it fails when the
rule is broken; run the quickstart's step-5 acceptance table; answer the FR-025 deletion
question and write the answer into research R3; add the `AGENTS.md` paragraph; full lint and
unit gate; merge.

The follow-up specify cycles the routing hook flagged remain: **Menu** (flip
`include_in_menu` to `false` and add the curated entry) and possibly **Check** (whether the
no-generation rule also wants a proposed-change check). The executor itself is not an Infrahub
artifact type and does not route through this extension.
