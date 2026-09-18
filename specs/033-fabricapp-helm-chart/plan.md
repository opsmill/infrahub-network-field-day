# Implementation Plan: Fabric Application as a Helm Chart

**Branch**: `033-fabricapp-helm-chart` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/033-fabricapp-helm-chart/spec.md`

## Summary

`ServiceFabricApp` offers two ways to describe a workload — a Helm chart or raw
Kubernetes manifests — and every field of both is optional, so the renderer
decides which path an application took by looking at what happens to be
populated. This cycle makes the chart the only way: `chart_repository`,
`chart_name` and `chart_version` become mandatory, and the `manifests` attribute,
the `manifests_file` relationship and the `ServiceFabricAppManifestsFile` kind
are withdrawn.

Removing the manifests takes the firewall path with it, because
`generate-app-access` derives a grant's destination ports by reading them for
`LoadBalancer` Services and deliberately refuses rather than guessing when it
finds none. The application therefore gains `advertised_services`, a relationship
to the `SecurityService` objects its VIP answers on. That is not a replacement
for the derivation so much as its removal: `SecurityService` is already what a
`SecurityPolicyRule` names in `destination_services`, so the application's
advertised port and the rule's permitted port become one object rather than two
numbers that have to agree.

The approach is measured rather than assumed. Every shape in
[data-model.md](./data-model.md) was loaded onto a throwaway branch of the
running 1.10.6 instance, and three findings changed the plan: the mandatory
fields are refused against existing data, the schema loader removes the manifests
kind without deleting its instances, and `infrahubctl protocols` ignores `state:
absent` entirely. See [research.md](./research.md).

## Technical Context

**Language/Version**: Python >=3.11,<3.14 (stack runs 3.12.13; the Infrahub image is 3.13)

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]` >=1.19.0 (1.22.0 installed)

**Storage**: Infrahub graph (Neo4j); schema YAML under `schemas/` is the source of truth

**Testing**: pytest with pytest-asyncio; `tests/unit/test_service_layer_schema_contract.py` owns this surface

**Target Platform**: Linux, Docker Compose stack; ContainerLab lab alongside

**Project Type**: Infrahub reference-design repository — schema, generators, transforms, checks

**Performance Goals**: N/A. A schema change with no runtime hot path.

**Constraints**: The migration order inverts `invoke load` (objects before schema). The downstream Crossplane composite definition belongs to the sibling lab repository and must not change.

**Scale/Scope**: One schema file, one node changed, one kind withdrawn, one relationship added. Two `ServiceFabricApp` instances and two file objects exist in the developer stack today.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Pre-Phase 0 | Post-Phase 1 |
| --- | --- | --- | --- |
| I. Schema-Driven Architecture | Schema changes precede code that references them; protocols regenerated | **PASS** — this cycle is the schema, and the routing chain defers the renderer, generator, portals and seed data to later cycles | **PASS** — R3 makes protocol regeneration an explicit ordered step rather than an afterthought |
| II. Idempotent Operations | Generators idempotent; repeated runs validated | **PASS (N/A)** — no generator changes here | **PASS (N/A)** — `generate-app-access` changes land in the Generator cycle and carry the idempotence gate there |
| III. Type Safety | Typed models; protocols regenerated, never hand-edited | **PASS** | **PASS, and it is the tightest gate.** R3 found that leaving `state: absent` in the YAML makes `protocols.py` advertise three things that do not exist at runtime, with mypy clean because the types are internally consistent. Handled by deleting the blocks after the load; Scenario 6 asserts it |
| IV. Test-Required Quality | Unit tests for changed behaviour; all linters pass | **PASS** | **PASS** — `test_fabric_app_workload_source_supports_chart_manifests_or_both` inverts to assert a single source (SC-007), and `test_no_grant_is_seeded` is unaffected |
| V. Convention-Based Structure | Naming and directory conventions | **PASS** | **PASS** — the change stays in `schemas/service/kubernetes_services.yml`; relationship named snake_case, identifier follows the existing `service__app_*` convention |

**No violations.** The Complexity Tracking table is therefore omitted.

Two constitution items are worth stating rather than merely ticking:

- **Development Workflow gate 2 and 3** (`schema check` then regenerate
  protocols) are ordinarily two steps. R1 and R3 turn them into six, and the plan
  states the order explicitly because getting it wrong produces either a refused
  load or a silently wrong `protocols.py`.
- **Mandatory Validation Skills**: `$infrahub-run-integration-tests` applies to
  this change. `$infrahub-test-generator-idempotence` does not — no generator
  changes here — and applies to the Generator cycle instead.

## Project Structure

### Documentation (this feature)

```text
specs/033-fabricapp-helm-chart/
├── plan.md              # This file
├── research.md          # Phase 0 output — seven findings, all measured
├── data-model.md        # Phase 1 output — the node, the relationship, the migration order
├── quickstart.md        # Phase 1 output — seven validation scenarios
├── contracts/
│   └── schema-kinds.md  # Phase 1 output — withdrawn, tightened and published surface
├── checklists/
│   └── requirements.md  # From /speckit-specify
├── spec.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Changed by this cycle:

```text
schemas/
└── service/
    └── kubernetes_services.yml       # ServiceFabricApp; withdraw the manifests kind

src/solution_arista_avd/
└── protocols.py                      # REGENERATED, never hand-edited

tests/unit/
└── test_service_layer_schema_contract.py   # invert the workload-source assertion
```

Named by the contract but changed in later cycles:

```text
transforms/crossplane_fabric_app.py, .gql        # Transform cycle
generators/generate_app_access.py, .gql          # Generator cycle
scripts/seed_app_payloads.py                     # Objects cycle
objects/36_nfd41_app_services.yml                # Objects cycle
payloads/nfd41-demo-manifests.yaml               # Objects cycle — deleted
backstage/plugins/infrahub-backend/src/provider.ts
service_catalog/pages/6_Deploy_Application.py
```

**Structure Decision**: No new directories. The change is confined to one schema
file plus its regenerated protocol output and the contract test that guards the
surface, which is what "schema-first, one artifact type per cycle" means here —
the routing hook classified this feature as Schema → Transform → Objects and this
plan delivers only the first.

## Phase 0 — Research

Complete. [research.md](./research.md) records seven findings; four changed the
design:

| # | Finding | Effect on the plan |
| --- | --- | --- |
| R1 | Mandatory chart fields are **refused** against existing data, naming the node and never the attribute | Data migration precedes the schema load; `default_value` rejected |
| R2 | The loader removes the manifests kind **whether or not instances exist**, leaving them unreachable rather than deleted | File objects are deleted first, so SC-004 is verifiable |
| R3 | `infrahubctl protocols` reads the YAML and **ignores `state: absent`** | `state: absent` is a migration step; the blocks are deleted in the same cycle |
| R5 | The demo has **no two-tier chart**, and the lab's own file says why | Spec assumption corrected; single-tier `cowboysysop/whoami` 6.0.0 confirmed with the user |

R4 measured the relationship end to end, R6 confirmed no lab-repository change is
needed, and R7 confirmed the cross-file peer resolves without an `extensions:`
block — which also matters because `extensions:` is invisible to the protocol
generator.

## Phase 1 — Design & Contracts

Complete.

- **[data-model.md](./data-model.md)** — the changed node, the added
  relationship with the reasoning behind each of its six fields, the withdrawn
  kind, seven validation rules, the six-step migration order, and the seeded
  application's post-change shape.
- **[contracts/schema-kinds.md](./contracts/schema-kinds.md)** — the withdrawn,
  tightened and published surface, six guarantees with their basis, three
  explicit non-guarantees, and a consumer migration table for the later cycles.
- **[quickstart.md](./quickstart.md)** — seven scenarios, including the one that
  proves the migration order is real and the one that catches a `protocols.py`
  regenerated too early.

### Post-design constitution re-check

Passed — see the table above. The design added no new dependency, no new
directory, and no hand-edited generated file. The one risk it introduced,
`protocols.py` drifting from the graph, is a direct consequence of R3 and is
closed by an ordered step with an assertion in Scenario 6 rather than by a note.

## Open items carried into `/speckit-tasks`

1. **Enumerating the applications to migrate.** Two exist in the developer stack
   and only one is in `objects/`; the other arrived through the portal. The
   migration must query the graph rather than read the seed files.
2. **Whether the `state: absent` blocks are deleted in the same commit or a
   follow-up.** The plan says same cycle; a task must order the load between
   marking and deleting, because the two are not simultaneously correct.
3. **Chart values for `nfd41-demo`.** The shape is settled — `service.type:
   LoadBalancer`, `commonLabels: {nfd41.lab/advertise: "true"}`, `replicaCount:
   3` — but the payload file itself belongs to the Objects cycle.

## Known losses, recorded deliberately

Expressing `nfd41-demo` as a single-tier chart drops its backend `ClusterIP`
Service and the two L7 `CiliumNetworkPolicy` objects. That removes two things the
repository currently demonstrates: the ClusterIP backend's unreachability from
the app tenant as an asserted negative, and the L7 HTTP policy example. The user
chose this over the three alternatives in research R5. It is recorded here so its
absence later reads as a decision rather than a regression.
