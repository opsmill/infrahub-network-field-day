# Implementation Plan: Application File Attachments

**Branch**: `013-app-file-attachments` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-app-file-attachments/spec.md`

## Summary

Add two file-attachment kinds to the service layer so an application's deployment payload —
Helm values and raw Kubernetes manifests — is stored as a file with its own checksum rather
than as a JSON attribute. This exists so cycle 014 can render a `FabricApp` manifest from a
payload that `infrahubctl object load` is currently unable to seed at all.

The design follows this repository's existing `CoreFileObject` pattern exactly:
`AvdHostvarFile` and `AvdStructuredConfigFile` are each a separate kind, cardinality one from
their parent, unique on that parent. Two kinds rather than one kind with a role discriminator
— see [research.md](./research.md) R1.

No code. One schema file changes, plus regenerated protocols and contract tests.

## Technical Context

**Language/Version**: N/A — schema YAML. Tests are Python 3.11–3.13

**Primary Dependencies**: Infrahub 1.10.6's `CoreFileObject` interface. No new dependency

**Storage**: Infrahub graph plus its object storage, which is where file content lives

**Testing**: pytest contract tests reading the YAML directly, following `tests/unit/test_service_layer_schema_contract.py`

**Target Platform**: Infrahub 1.10.6

**Project Type**: Infrahub reference-design repository — schema change under `schemas/service/`

**Performance Goals**: None. A payload of a few hundred kilobytes is the realistic upper bound

**Constraints**: Strictly additive. The `crossplane_fabric_peering` artifact checksum `0d800c9d5005b5fdb6b371bb5627d143` must not move, and cycle 012's generator must be untouched

**Scale/Scope**: 2 new node kinds, 2 new relationships on one existing node, 1 schema file, 1 test module extended

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Initial | Post-Design |
| --- | --- | --- | --- |
| **I. Schema-Driven Architecture** | Model before code | ✅ PASS — this cycle *is* the schema step, deliberately separated from the transform that consumes it, which is what the principle asks for | ✅ PASS |
| **II. Idempotent Operations** | Upserts, natural keys, repeated-run validation | ✅ PASS — no generator or mutation here. The relevant property is that re-uploading identical content leaves the checksum unchanged, which `save_file_if_changed` already implements and SC-003 verifies | ✅ PASS |
| **III. Type Safety** | Typed models, regenerated protocols, mypy | ✅ PASS — `protocols.py` is regenerated, never hand-edited | ✅ PASS |
| **IV. Test-Required Quality** | Unit tests; all linters; `$infrahub-run-integration-tests` | ⚠️ CONDITIONAL — contract tests are planned; the five linters pass. The mandated skill is **not installed**, the same exception as cycles 010–012 | ⚠️ CONDITIONAL |
| **V. Convention-Based Structure** | Established naming and layout | ✅ PASS — follows `AvdHostvarFile` field for field (R1), in the service domain's existing file | ✅ PASS |

One conditional gate, unchanged from the three preceding cycles and recorded in Complexity
Tracking. Principle II is genuinely satisfied here rather than waived: this cycle adds no
mutating code.

## Project Structure

### Documentation (this feature)

```text
specs/013-app-file-attachments/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── schema-kinds.md
├── checklists/requirements.md
└── spec.md
```

### Source Code (repository root)

```text
schemas/service/
└── kubernetes_services.yml      # MODIFIED — 2 new kinds, 2 new relationships

src/solution_arista_avd/
└── protocols.py                 # REGENERATED — never hand-edited

tests/unit/
└── test_service_layer_schema_contract.py   # EXTENDED
```

**Structure Decision**: The new kinds live in `schemas/service/kubernetes_services.yml`
alongside `ServiceFabricApp` itself, rather than in `schemas/objects/objects.yml` where the
AVD file kinds live. `objects.yml` is the AVD artifact domain; these belong to the service
layer that owns them, and 010 established one file per service domain.

## Complexity Tracking

> Constitution Check violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **Principle IV** — `$infrahub-run-integration-tests` cannot be run; not installed | Mandated for every Infrahub change | Same decision and evidence set as cycles 010, 011 and 012: contract tests over the YAML, a live `schema load` on a branch, and the artifact-checksum regression check. For a purely additive schema change the checksum check is the strongest available evidence that nothing downstream moved |

## Phase 0 — Research

See [research.md](./research.md). Six decisions. The two that shape the schema:

- **R1 — two kinds, not one with a role.** The repository's own `CoreFileObject` usage is one
  kind per file role, each cardinality one and unique on its parent. That makes the role
  implicit in the kind, removes a dropdown, and makes the relationship names self-documenting
  (`values_file`, `manifests_file`).
- **R2 — the attachment wins over the attribute.** FR-011 required the precedence rule to be
  unambiguous and stated but deliberately did not choose. The attachment wins, because it is
  the only one of the two that can hold the payloads this cycle exists to enable.

## Phase 1 — Design

Design artifacts:

- [data-model.md](./data-model.md)
- [contracts/schema-kinds.md](./contracts/schema-kinds.md)
- [quickstart.md](./quickstart.md)

The shape:

```text
ServiceFabricApp
├── values_file    ──Component(one)──► ServiceFabricAppValuesFile    ──► CoreFileObject
└── manifests_file ──Component(one)──► ServiceFabricAppManifestsFile ──► CoreFileObject
```

Each file kind carries nothing of its own beyond the parent relationship: `file_name`,
`file_size`, `file_type`, `checksum` and `storage_id` all arrive from `CoreFileObject`.
