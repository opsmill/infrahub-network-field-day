# Implementation Plan: Crossplane FabricPeering Manifest

**Branch**: `nfd41-fabric-model` (feature directory `011-crossplane-manifest-transform`) | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-crossplane-manifest-transform/spec.md`

## Summary

Render the lab's `FabricPeering` Crossplane resource from the Infrahub model, store it as
an artifact against `ServiceFabricPeering`, and close the loop the schema feature was
built for: change the model, re-render, review the diff, push.

The approach changed during Phase 0. The spec proposed a pure-Python transform emitting
YAML through a dumper; research found that **neither existing YAML transform in this
repository does that** — `containerlab_topology` is hybrid (Python prepares data, Jinja2
renders), and `avd_anta_catalog` uses pyavd's own dumper. Jinja2 also has firmer
provenance than PyYAML here: it is required by `infrahub-sdk`, a declared first-order
dependency. So this is a **hybrid** transform, matching the closest analogue. Details in
[research.md](./research.md) R1.

Python does the work that is actually logic — parsing `key=value` selectors back into
label maps, stripping prefix lengths off peer addresses, ordering peers deterministically,
and raising when the model cannot produce a working manifest. The template does nothing
but lay out the resource.

## Technical Context

**Language/Version**: Python >=3.11,<3.14

**Primary Dependencies**: `infrahub-sdk[all]>=1.19.0` (supplies `InfrahubTransform` and,
transitively, `jinja2`), Infrahub 1.10.6. **No new dependency is added** — see
[research.md](./research.md) R2 for why PyYAML was rejected.

**Storage**: Infrahub graph. The transform is read-only; the artifact it produces is
stored by Infrahub against the target object.

**Testing**: `pytest` unit tests over fixture dictionaries, following
`tests/unit/test_avd_anta_catalog.py` and `tests/unit/test_containerlab_topology.py`.
No live server for unit tests; `infrahubctl transform` for the end-to-end check.

**Target Platform**: Infrahub 1.10.6 at `http://localhost:8000`, with the technical layer
already loaded (verified this session on branch `final2`).

**Project Type**: Infrahub transform inside an existing reference-design repository.

**Performance Goals**: N/A. One artifact per peering service, and the lab has one.

**Constraints**:

- The rendered manifest must satisfy the lab's existing XRD
  (`../lab/crossplane/platform/00-xrd-fabric-peering.yaml`, group `nfd41.lab`, version
  `v1alpha1`, cluster-scoped). The composition is not changed.
- The artifact target must inherit `CoreArtifactTarget`. `ServiceFabricPeering` does;
  `ClusterKubernetes` deliberately does not. So the target is the service, and every
  rendered value comes from the technical layer beneath it.
- Selectors are stored as `key=value` lists, not JSON maps, because Infrahub 1.10.6
  returns a 500 for a JSON attribute key containing a dot or a slash. Recorded in
  `schemas/MARKETPLACE.md`.
- No secret value may appear in output — only the name of the secret holding it.
- GraphQL responses must be typed through generated Pydantic models (Constitution III).

**Scale/Scope**: 1 query, 1 generated model module, 1 transform class,
3 `.infrahub.yml` registrations, 1 group, 1 seed object, 1 unit-test module.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.2.0.

| Principle | Gate | Pre-Phase-0 | Post-Phase-1 |
| --- | --- | --- | --- |
| **I. Schema-Driven Architecture** | Schema defined before code references it | ✅ PASS — every kind this transform reads was defined and loaded in the previous cycle | ✅ PASS — no schema change. R4 confirms the target already inherits `CoreArtifactTarget`, so nothing is needed |
| **II. Idempotent Operations** | Repeated runs produce the same result | ✅ PASS (transform is read-only) | ✅ PASS — R7 makes rendering deterministic (peers sorted, key order fixed), so an unchanged model yields a byte-identical artifact and an unchanged checksum. The one seed object loads idempotently |
| **III. Type Safety** | Typed models, generated not hand-written, mypy clean | ✅ PASS | ✅ PASS — R5 generates `crossplane_fabric_peering_query.py` with `infrahubctl graphql generate-return-types`; the transform parses through it, as `avd_anta_catalog` does. `disallow_untyped_defs` is satisfied by annotating every helper |
| **IV. Test-Required Quality** | Unit tests for changed behaviour; integration for Infrahub changes; all linters | ⚠️ CONDITIONAL — see Complexity Tracking | ⚠️ CONDITIONAL — unit coverage is fully planned (R9) and the four available linters pass. The mandated `$infrahub-run-integration-tests` skill is still not installed; the same documented alternative as cycle 010 applies |
| **V. Convention-Based Structure** | Established naming and layout; deviations justified | ✅ PASS | ✅ PASS — R3 follows `avd_anta_catalog`: `.gql` co-located in `transforms/`, `*_query.py` generated beside it, artifact target aliased `target:` in the query. Emitting through `yaml.dump` rather than a template is the skill's own guidance for structured output — see research R1a |

### Gate detail — Principle IV

Unchanged from cycle 010 and for the same reason: `$infrahub-run-integration-tests` is not
present in this environment. What *is* satisfiable here is stronger for a transform than
it was for a schema, because a transform can be executed end to end without the
integration suite:

- **Unit tests** over fixture dictionaries, covering selector parsing, address stripping,
  ordering, the disabled-peering omission, and all three error paths.
- **`infrahubctl transform`** against the loaded model — a real render against real data,
  which is the behaviour the artifact will produce.
- **A client-side Kubernetes dry-run** of the output against the lab's XRD, which
  validates the contract with the consumer rather than with our own expectations.
- **Repository sync** proving the query, transform and artifact definition are all
  accepted, and artifact generation proving one is produced.

That is a materially better evidence set than a schema cycle could offer, but it still
needs the same maintainer decision as cycle 010's T070.

## Project Structure

### Documentation (this feature)

```text
specs/011-crossplane-manifest-transform/
├── plan.md                       # This file
├── research.md                   # Phase 0 — 10 decisions
├── data-model.md                 # Phase 1 — the field-by-field render mapping
├── quickstart.md                 # Phase 1 — validation guide
├── contracts/
│   └── manifest-contract.md      # Phase 1 — the rendered resource and the artifact
├── spec.md
├── checklists/requirements.md
└── tasks.md                      # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
transforms/
├── crossplane_fabric_peering.gql          # NEW  the query
├── crossplane_fabric_peering_query.py     # NEW  GENERATED — never hand-edited
├── crossplane_fabric_peering.py           # NEW  the transform class
└── templates/
    └── crossplane_fabric_peering.j2       # NEW  the manifest layout

objects/
├── 00_groups.yml                          # EDIT add the target group
└── 35_nfd41_peering_service.yml           # NEW  one seed ServiceFabricPeering

tests/unit/
└── test_crossplane_fabric_peering.py      # NEW  fixture-based unit tests

.infrahub.yml                              # EDIT query + transform + artifact definition
```

**Structure Decision**: Every path follows the repository's existing transform layout
rather than the skill template's suggested `queries/` directory. AGENTS.md is explicit —
"GraphQL queries MUST be stored in `.gql` files co-located with their Python consumers" —
and both `avd_anta_catalog` and `containerlab_topology` do exactly this, with the
generated `*_query.py` beside the `.gql` and templates under `transforms/templates/`.

The seed object takes the next free number after the six object files added this session
(`29_` to `34_`), so it loads after the cluster and peerings it references.

## Complexity Tracking

> Constitution Check violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principle IV** — `$infrahub-run-integration-tests` cannot be run; not installed | The constitution mandates it for every Infrahub code change | Skipping validation was rejected. **Alternative plan**: fixture unit tests, a live `infrahubctl transform` render, a Kubernetes dry-run of the output against the consumer's XRD, and a repository sync plus artifact generation. For a transform this exercises the real behaviour end to end. Needs maintainer sign-off, same decision as cycle 010's T070 |
| **A service-layer object is loaded** in a cycle that follows one which deliberately loaded none | An artifact needs a target that inherits `CoreArtifactTarget`, and only the service kinds do. Without it there is nothing to render against | Making `ClusterKubernetes` an artifact target was rejected: spec 010's FR-083 deliberately scoped `CoreArtifactTarget` to the three cluster-delivered service kinds, and widening it would blur the layer boundary that feature exists to draw. One object is the smaller change |
| ~~**Hybrid rather than the pure-Python approach the spec proposed**~~ — **reversed during implementation**, see research R1a | The hybrid rationale did not survive review: the "no transform imports yaml" finding was scoped to one directory, and a generator already imports it in production code | The transform is now pure Python emitting through `yaml.dump`, `pyyaml` is a declared dependency, and the template is deleted. This removes the entry rather than justifying it: pure Python was the spec's own proposal, so no deviation remains to track |

## Phase Status

- [x] **Phase 0** — [research.md](./research.md): 10 decisions, no NEEDS CLARIFICATION remaining
- [x] **Phase 1** — [data-model.md](./data-model.md), [contracts/manifest-contract.md](./contracts/manifest-contract.md), [quickstart.md](./quickstart.md)
- [ ] **Phase 2** — `tasks.md` (run `/speckit-tasks`)
