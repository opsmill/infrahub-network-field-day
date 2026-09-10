# Implementation Plan: Service-Layer Fabric Peering Generator

**Branch**: `012-service-layer-generator` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-service-layer-generator/spec.md`

## Summary

Replace the two hand-written `ClusterFabricPeering` rows in `objects/34_nfd41_cluster.yml`
with a generator that derives them from the graph. An operator orders one
`ServiceFabricPeering`; the generator walks the cluster's nodes through their cabling to the
fabric devices they attach to, reads each device's BGP AS from the fabric model, and upserts
one session per distinct device.

The approach is deliberately conservative. Both clarifications were answered to preserve
existing values, so the first run is a **pure adoption**: the two existing sessions are
matched on their `(cluster, peer_device)` uniqueness constraint, their `name` and
`peer_address` are carried through untouched, and only `peer_asn` changes from a typed-in
number to one derived from `DcimDevice.asn`. Cycle 011's recorded artifact checksum is the
regression oracle — if it moves, the refactor changed what reaches the cluster and is wrong.

## Technical Context

**Language/Version**: Python 3.11–3.13 (`requires-python = ">=3.11, <3.14"`)

**Primary Dependencies**: `infrahub-sdk` (`InfrahubGenerator`, tracking-enabled `self.client`); no new dependency

**Storage**: Infrahub graph (1.10.6). No files written at runtime

**Testing**: pytest unit tests with fixture query responses; live double-run against a feature branch; artifact checksum comparison

**Target Platform**: Infrahub task-worker (generators execute server-side) and `infrahubctl generator` locally

**Project Type**: Infrahub reference-design repository — generator added under `generators/`

**Performance Goals**: One query round trip per service. The lab's cluster is 3 nodes → 2 sessions; the design must not issue a query per node or per peer

**Constraints**: The rendered Crossplane artifact must stay byte-identical (SC-004). The generator must not delete technical objects it did not create (FR-022), which is not the default behaviour of the tracking context

**Scale/Scope**: 1 GraphQL query, 1 generated query model, 1 generator class, 1 `.infrahub.yml` registration pair, 1 unit-test module, and a subtraction from one object file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Initial | Post-Design |
| --- | --- | --- | --- |
| **I. Schema-Driven Architecture** | Schema is the source of truth; model before code | ✅ PASS — no schema change. Every kind this cycle touches was published by 010 and is already loaded. FR-027's limitation exists *because* the schema does not connect the peering address to a device, and the fix is explicitly deferred to a schema cycle rather than worked around in code | ✅ PASS |
| **II. Idempotent Operations** | `allow_upsert=True`, natural-key dedup, repeated-run validation, `$infrahub-test-generator-idempotence` | ⚠️ CONDITIONAL — the mechanics are satisfiable and central to the design (see R3, R4). The mandated skill is **not installed**; see Complexity Tracking | ⚠️ CONDITIONAL — unchanged, with a stronger alternative than a generic idempotence check: cycle 011's artifact checksum |
| **III. Type Safety** | Typed models, no raw dict access, mypy clean | ✅ PASS — `.gql` plus generated `*_query.py`, consumed through Pydantic models, matching every existing generator and transform | ✅ PASS |
| **IV. Test-Required Quality** | Unit tests for changed behaviour; all linters; `$infrahub-run-integration-tests` | ⚠️ CONDITIONAL — unit coverage planned (R7); the five linters pass. The mandated skill is **not installed**; same exception as cycles 010 and 011 | ⚠️ CONDITIONAL |
| **V. Convention-Based Structure** | Established naming and layout | ✅ PASS — `generate_<entity>.py` with a co-located `.gql` and generated `*_query.py`, per AGENTS.md and all seven existing generators (R8) | ✅ PASS |

**Two conditional gates, both from missing validation skills, both recorded in Complexity
Tracking.** Neither is a design compromise; the mechanics each principle demands are met.

## Project Structure

### Documentation (this feature)

```text
specs/012-service-layer-generator/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── generator-contract.md
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── spec.md
```

### Source Code (repository root)

```text
generators/
├── generate_fabric_peering.py          # NEW — the generator class
├── generate_fabric_peering.gql         # NEW — one-round-trip query
├── generate_fabric_peering_query.py    # NEW — generated, never hand-edited
├── generate_fabric.py                  # existing, unchanged
├── generate_rack.py                    # existing, unchanged
└── ...

objects/
└── 34_nfd41_cluster.yml                # MODIFIED — loses 2 hand-written sessions

tests/unit/
└── test_generate_fabric_peering.py     # NEW

.infrahub.yml                           # MODIFIED — query + generator_definition
```

**Structure Decision**: The repository co-locates each generator's `.gql` and generated
`*_query.py` beside its `.py`, which overrides the skill's suggested `queries/` layout.
AGENTS.md states this explicitly ("GraphQL queries MUST be stored in `.gql` files co-located
with their Python consumers") and all seven existing generators comply. See R8 for the name.

## Complexity Tracking

> Constitution Check violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **Principle II** — `$infrahub-test-generator-idempotence` cannot be run; not installed in this environment | The constitution mandates it for generator changes when live validation is permitted | Skipping repeated-run validation was rejected. **Alternative plan**: (a) unit tests asserting the derivation is a pure function of the query response; (b) a live double-run via `infrahubctl generator` with an object-state snapshot compared before and after; (c) the decisive one — regenerate cycle 011's artifact after each run and require the checksum to be unchanged. (c) is *stronger* than a generic idempotence check, because it validates the observable output an operator consumes, not just object counts |
| **Principle IV** — `$infrahub-run-integration-tests` cannot be run; not installed | Mandated for every Infrahub code change | Same decision as cycles 010 and 011, and the same alternative evidence set: fixture unit tests, live execution, and artifact comparison. Needs maintainer sign-off, carried forward as one open item rather than re-litigated per cycle |
| **An object data file is edited in a generator cycle** | The two hand-written sessions must leave `objects/34_nfd41_cluster.yml`, or the second copy this feature exists to remove survives | Leaving them was rejected: object data and the generator would then both assert the same rows, and the file's values would silently win on the next `object load`. Deleting them is a subtraction of 2 rows, smaller than any alternative |

## Phase 0 — Research

See [research.md](./research.md). Ten decisions. The three that shape the implementation:

- **R3 — adoption without overwriting.** `save(allow_upsert=True)` writes every field passed
  in the payload, so preserving `name` and `peer_address` (FR-026, FR-027) means *not passing
  them* for a session that already exists. The query therefore fetches existing sessions and
  the generator builds a different payload for adopt versus create.
- **R4 — the tracking context deletes by identifier, not by kind.** This is what makes FR-022
  satisfiable rather than aspirational: objects the generator never touched under this
  identifier are outside the tracking set and are not candidates for deletion.
- **R2 — `connected_endpoints` returns both ends of the cable**, including the cluster node's
  own interface. Verified live. The near end must be excluded or the generator would try to
  peer the cluster with itself.

## Phase 1 — Design

See [data-model.md](./data-model.md), [contracts/generator-contract.md](./contracts/generator-contract.md),
and [quickstart.md](./quickstart.md).

The design is a four-stage pipeline inside `generate()`:

1. **Traverse** — cluster nodes → interfaces → links → far-end interfaces → devices
2. **Filter and dedupe** — keep fabric-leaf roles, drop the near end, reduce to distinct devices
3. **Reconcile** — for each device, adopt the existing session or build a new one
4. **Validate and write** — refuse an empty peer set, then upsert in a deterministic order

Stages 1–3 are pure functions of the query response, which is what makes the behaviour
unit-testable without a server and is how the error paths become reachable at all.
