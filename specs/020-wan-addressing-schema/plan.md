# Implementation Plan: Making the WAN's Addressing Real

**Branch**: `020-wan-addressing-schema` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-wan-addressing-schema/spec.md`

## Summary

Four optional relationships, across three schema files, so that the WAN's addressing stops
being prose in description fields and becomes data a renderer can query. The end goal is
rendering the six FRR configs in `../lab/wan/rendered/` from Infrahub; this is the schema link
in a three-cycle chain — schema here, object data next, the transform after that.

Phase 0 changed the shape of the work in two ways. The `loopback` interface role the
specification asked for **already exists** in `schemas/dcim_extensions.yml`, so one of the five
gaps was closed before this cycle began and the scope is four changes, not five. And the
`WanSite` widening turned out to have a silent failure mode: a relationship rename without a
`state: absent` tombstone leaves the old relationship live on the server while `schema check`
reports nothing wrong. Both findings came from running the change against the instance rather
than reasoning about it, and both are recorded in [research.md](./research.md).

## Technical Context

**Language/Version**: Python >=3.11,<3.14 — but this cycle writes no Python beyond a test.
The deliverable is YAML under `schemas/`.

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]>=1.19.0` for `infrahubctl`.
No dependency changes.

**Storage**: The Infrahub graph (Neo4j). Schema only — no object data is written this cycle.

**Testing**: `pytest`, via the existing `tests/unit/test_wan_schema_contract.py`, which reads
the schema YAML directly and therefore needs no running server.

**Target Platform**: Local Infrahub stack via Docker Compose.

**Project Type**: Infrahub repository — schemas, generators, transforms, checks, object data.

**Performance Goals**: N/A. Four relationship definitions.

**Constraints**: Every relationship optional, so the existing seed keeps loading unchanged
(FR-012, FR-041). `schemas/circuit/circuit.yml` is marketplace-adopted and must stay
byte-identical (SC-009). No `display_label`, `human_friendly_id`, `order_by` or uniqueness
constraint may change (FR-031).

**Scale/Scope**: 3 files touched, 1 created, ~40 lines of YAML, 1 test file updated, 1
generated file regenerated.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1 design. Re-check result recorded below.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ **This cycle is the principle.** Schema is defined before the object data and transform that will use it. Protocols will be regenerated (`infrahubctl protocols`). Namespaces are all existing and approved — `Dcim`, `Wan`, `Ipam`, `Routing`. The constitution's rule that "schema extensions MUST be used to add relationships to existing base nodes" is followed exactly: the `DcimCircuitEndpoint` change goes in a new `schemas/circuit_extensions.yml` rather than into the adopted marketplace file. |
| **II. Idempotent Operations** | ✅ No generator changes, so `$infrahub-test-generator-idempotence` does not apply. Schema loads are upserts and are re-runnable; §4 of [quickstart.md](./quickstart.md) re-runs the object load to prove the seed is unaffected. |
| **III. Type Safety** | ✅ `protocols.py` is regenerated, never hand-edited, and `mypy` is a gate. No `.gql` query or `*_query.py` model changes, because nothing queries these relationships yet. |
| **IV. Test-Required Quality** | ⚠️ **One gate needs a decision, flagged rather than assumed.** Unit coverage is in hand: `test_wan_schema_contract.py` is extended to pin all four relationships. But the constitution requires `$infrahub-run-integration-tests` for *every* Infrahub code change. See "Integration testing" below. All linters (`ruff`, `mypy`, `yamllint`, `rumdl`, Vale) run via `uv run invoke lint`. |
| **V. Convention-Based Structure** | ✅ `schemas/circuit_extensions.yml` matches the five existing `*_extensions.yml` files at `schemas/` top level. No generator, transform or object file is added, so their naming rules do not apply. |

### Integration testing

The constitution requires `$infrahub-run-integration-tests` for every Infrahub code change,
and this is an Infrahub change. It is also a change with no runtime behaviour: no generator
runs, no transform renders, no object is created or mutated. The integration suite exercises
generator chains, transforms and repository-load behaviour, none of which this touches.

The plan is to run it anyway rather than claim an exception, because "schema loads cleanly and
the repository still loads" is precisely what the suite would catch if the tombstone or the
extension file broke the load. If the suite cannot be run in this environment, that is a
documented exception under the constitution's escape clause and the pull request must say so
explicitly — it is not a decision to make silently. The quickstart's §3 and §4 are the
non-live alternative: load the schema, read the live schema back, re-load every object file.

**No unjustified violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/020-wan-addressing-schema/
├── plan.md              # This file
├── research.md          # Phase 0 output — nine findings, two of which changed the scope
├── data-model.md        # Phase 1 output — the four changes, field by field
├── quickstart.md        # Phase 1 output — how to prove it worked
├── contracts/
│   └── schema-contract.md   # Phase 1 output — exact YAML and the expected check diff
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output — created by /speckit-tasks, not by this command
```

### Source code (repository root)

```text
schemas/
├── circuit/
│   └── circuit.yml              # ADOPTED — must not change (SC-009)
├── circuit_extensions.yml       # NEW — DcimCircuitEndpoint.interface
├── dcim_extensions.yml          # EDIT — DcimDevice.router_id
└── wan/
    └── wan.yml                  # EDIT — WanSite.bgp_sessions + tombstone,
                                 #        WanInternetPeering.bgp_sessions

src/solution_arista_avd/
└── protocols.py                 # REGENERATED — never hand-edited

tests/unit/
└── test_wan_schema_contract.py  # EDIT — re-point and extend the assertions
```

**Structure Decision**: No new directory. `schemas/circuit_extensions.yml` sits at the
`schemas/` top level beside `dcim_extensions.yml`, `ipam_extensions.yml`, `l3ls_extensions.yml`,
`location_extensions.yml`, `security_extensions.yml` and `tenancy_extensions.yml` — the
convention this repository already uses for "what we need on top of a file we do not own".
`.infrahub.yml` declares `schemas: - schemas`, which loads the tree recursively, so the new
file needs no registration.

## Implementation sequence

Ordered by dependency, and by putting the one risky step where its failure is cheapest.

1. **`schemas/wan/wan.yml`** — the widening and the tombstone, plus the internet peering's
   sessions. This is the only step that can fail in an interesting way, so it goes first.
2. **`schemas/circuit_extensions.yml`** — new file, pure addition.
3. **`schemas/dcim_extensions.yml`** — `router_id`, pure addition.
4. **`uv run infrahubctl schema check schemas/`** — confirm the diff is exactly the five lines
   in [contracts/schema-contract.md §6](./contracts/schema-contract.md), with `bgp_session`
   under `removed`. This is the step that catches the ghost.
5. **`tests/unit/test_wan_schema_contract.py`** — re-point the existing assertion, add
   cardinality and the three new relationships, assert the tombstone is present.
6. **Load, then regenerate protocols, then `mypy`.**
7. **Re-load `objects/` twice** to prove the seed is unaffected and still idempotent.
8. **`uv run invoke test` and `uv run invoke lint`.**

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| `state: absent` is accepted by `schema check` but rejected by `schema load` | Low | Only `check` has been run (R6). Fallback is the rejected alternative — widen in place, keep the singular name — which is a one-line change plus a test edit. Bounded and reversible. |
| The tombstone is forgotten and lingers | Medium | It is documented in the schema file itself, in [data-model.md](./data-model.md) and in research R9's open risks, with the removal condition stated: after the next rebuild from empty. |
| `protocols.py` regeneration breaks a consumer | Very low | Nothing reads `bgp_session` outside the contract test. `mypy` is the gate. |
| Scope creeps into seeding objects | Medium | The spec's Out of Scope is explicit, and `tasks.md` must not contain an `objects/` file. Seeding is the next cycle. |

## Complexity Tracking

No constitution violations require justification. This section is intentionally empty.
