# Implementation Plan: Zone Advertisement Policy

**Branch**: `032-zone-advertisement-policy` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/032-zone-advertisement-policy/spec.md`

## Summary

Two fields on `SecurityZone`, added by extension: the name of the prefix list governing what the datacentre advertises toward that zone, and the fabric switch that applies it. Two of the six zones get values; four legitimately stay empty.

That is the whole change. It exists because a `ServiceAppAccess` grant already names all three domains of this lab and only two of them act — the fabric leg has nowhere to write, because nothing connects a zone to the policy governing advertisement toward it.

Phase 0 found that **both plausible derivations of the carrying device fail**: no device carries the `border_leaf` role (all five leaves are `leaf`), and `IpamVRF` has no relationship to any `Dcim` kind. The fact is unrecoverable from the graph, which is what makes a modelled relationship necessary rather than convenient. See [research.md](./research.md) R4.

## Technical Context

**Language/Version**: n/a — YAML schema. Tests are Python >=3.11,<3.14.

**Primary Dependencies**: Infrahub 1.10.6; `infrahubctl` for check, load and protocol generation.

**Storage**: Infrahub graph (Neo4j). Two fields on an existing kind; no new node or generic.

**Testing**: pytest. New contract tests; `tests/unit/test_junos_config.py` and the service-layer contract tests must keep passing.

**Target Platform**: Infrahub schema, loaded by `infrahubctl schema load schemas`.

**Project Type**: Infrahub repository artifact — schema, per the `infrahub-speckit` routing for this cycle.

**Performance Goals**: n/a.

**Constraints**:
- `SecurityZone` is an upstream marketplace kind; changes go in `schemas/security_extensions.yml` so `schemas/security/security.yml` keeps diffing cleanly against a later `marketplace get`
- Six zone objects already exist, so both fields must be optional (FR-050)
- The relationship must peer `DcimFabricSwitch`; `DcimDevice` would match nothing and fail silently
- `src/solution_arista_avd/protocols.py` is generated and must be regenerated, never hand-edited

**Scale/Scope**: one schema file, one object file, one new test module. Six existing files unchanged.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
| --- | --- | --- |
| **I. Schema-Driven Architecture** | Schema before the code that reads it; extensions for upstream nodes; regenerate protocols | **PASS.** This cycle *is* the schema, and it precedes the generator cycle that consumes it — which is why it exists as its own cycle rather than being folded into that work. Both fields are added through the `extensions:` block, which `schemas/security_extensions.yml` already uses for `trust_level`, `vrf`, `book_index` and `log_session_close`. Protocol regeneration is T-tracked. |
| **II. Idempotent Operations** | Generators idempotent; repeated-run validation defined | **N/A.** No generator changes. `infrahubctl schema load` is idempotent by construction, and re-loading the seed objects upserts. |
| **III. Type Safety** | Typed models; mypy `disallow_untyped_defs` | **PASS.** No production Python. Regenerated protocols carry the new fields; the new test module is typed. |
| **IV. Test-Required Quality** | Tests exist; all linters pass | **PASS.** Contract tests are FR-060 to FR-062. The third is the interesting one — it holds the model against the lab rather than only against itself. |
| **V. Convention-Based Structure** | Naming conventions; numbered object files | **PASS.** Attribute and relationship names are snake_case; the seed change edits the existing `objects/32_nfd41_security.yml` rather than adding a file, because the zones are already defined there. |

**Deployment-state rule** (`AGENTS.md`): nothing here reads, writes, targets or triggers from `DeploymentState` or `DeploymentDiffFile`.

**Service-layer dependency rule**: unaffected. This is a technical-layer change; no service kind is named.

**Upstream-contract note**: `SecurityZone` gains two fields it does not have upstream. That is the fourth such addition in this file and follows the pattern its header documents. Recorded in Complexity Tracking for visibility, not as a violation.

**Post-Phase 1 re-check**: PASS. The design adds no node, no generic, no dependency and no file outside the conventions above.

## Project Structure

### Documentation (this feature)

```text
specs/032-zone-advertisement-policy/
├── plan.md              # This file
├── spec.md
├── research.md          # Phase 0 — R1..R6
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── checklists/
│   └── requirements.md
├── contracts/
│   ├── schema-fields.md     # The two fields, exactly
│   └── seed-values.md       # Which zones get what, and why four stay empty
└── tasks.md             # /speckit-tasks output — NOT created here
```

### Source Code (repository root)

```text
schemas/
└── security_extensions.yml      # + advertising_device, + dc_advertised_prefix_list

src/solution_arista_avd/
└── protocols.py                 # REGENERATED, never hand-edited

objects/
└── 32_nfd41_security.yml        # branch and wan zones gain values

tests/unit/
└── test_zone_advertisement_contract.py   # new
```

**Structure Decision**: no new files under `schemas/`. The extension lands in `security_extensions.yml`, which exists for exactly this — adding to adopted marketplace kinds without editing them. Seed values edit the zone rows already in `objects/32_nfd41_security.yml` rather than introducing a numbered file, because a separate file would define the same zones twice and load order would decide which won.

## Phase Outputs

| Phase | Artifact | Content |
| --- | --- | --- |
| 0 | [research.md](./research.md) | R1 peer kind, R2 what "carrying device" means, R3 the attribute's name, R4 why no derivation works, R5 the seed values, R6 placement |
| 1 | [data-model.md](./data-model.md) | The two fields, their properties, what is deliberately absent, and the soft reference's failure modes |
| 1 | [contracts/schema-fields.md](./contracts/schema-fields.md) | The exact field definitions and the traps in each |
| 1 | [contracts/seed-values.md](./contracts/seed-values.md) | Zone-by-zone values and the evidence for each |
| 1 | [quickstart.md](./quickstart.md) | Check, load, verify, and the one query the next cycle depends on |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Two more local additions to the upstream `SecurityZone` contract | The fabric side of a zone is not modelled upstream, and the grant generator cannot find where to write without it | Deriving the device by role or by VRF — both verified impossible against the live instance (research R4). Deriving the prefix-list name by convention was rejected in cycle 031 for inference, and this cycle stores it as authored data instead. |
| A `Text` attribute holding a name that resolves into a JSON blob, with nothing enforcing it resolves | Zero `RoutingPrefixList` objects exist; the fabric's whole BGP policy lives in `NetworkFabric.avd_custom_hostvars`, which is AVD's documented channel for un-modelled inputs | Migrating that policy into first-class routing objects first — a large migration touching every rendered device configuration, and it fights a deliberate design choice. Recorded in the spec's Assumptions with the condition for revisiting. User Story 3 requires the mismatch be detectable, which is what makes the soft reference defensible rather than merely convenient. |
