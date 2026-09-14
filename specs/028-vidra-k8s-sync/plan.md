# Implementation Plan: Vidra Kubernetes Delivery

**Branch**: `028-vidra-k8s-sync` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/028-vidra-k8s-sync/spec.md`

## Summary

Close the last hop. The two Crossplane renderers already turn service intent into
`nfd41.lab/v1alpha1` manifests; nothing carries those manifests into the cluster, so the
documented loop ends at "then push" — a human with a terminal. This cycle deploys the Vidra
operator into the NFD41 lab's Kubernetes cluster, registers the one query it polls, and pins it to
`main` so a merged proposed change becomes cluster state on its own.

**The cycle is much smaller than the spec assumed, and its one real risk is not where the spec
looked.**

## What the two design phases changed

### Phase 0 removed two of the four deliverables

The spec named four workstreams: a query, delivery configuration, a possible merge trigger, and
standing up a cluster. Research killed half of that.

**The merge trigger does not exist because it does not need to.** Infrahub 1.10.6 already
regenerates every artifact definition on the target branch after a merge:

```python
# backend/infrahub/core/branch/tasks.py:641-660
async def post_process_branch_merge(source_branch: str, target_branch: str, context) -> None:
    await get_workflow().submit_workflow(
        workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE,
        context=context,
        parameters={"branch": target_branch},
    )
```

FR-013 asked the question; the answer is "no trigger", and `triggers.yml` is untouched.

**The cluster does not need standing up because one is already running.** Three k3s nodes, four
days up, with Crossplane, the `nfd41.lab` XRDs, the compositions, and the resources applied and
healthy. My own earlier report that no cluster was reachable was true of this host's kubeconfig and
wrong about the lab. The requester saw the evidence and retargeted the cycle at the live cluster.

### Phase 1 found the risk, and it is a bounce, not a breakage

The spec's stated worry was the two-writer problem — what happens when Infrahub and the lab repo
both declare the same resource. Comparing the artifacts against what is actually running turned
that into something milder and something sharper.

**Milder:** delivery is a no-op in effect. The `FabricPeering` artifact's `spec` is *identical* to
the live resource. The `FabricApp` differs only in `expose.communities` and
`expose.advertisementSelector` — both XRD defaults carrying the same values the API server
re-injects. Pointing a delivery operator at a working cluster is usually frightening because its
first act is to overwrite live state; here the state it writes is the state already there.

**Sharper:** the first sync would have failed outright, and the fix costs an outage.

```go
// internal/controller/vidraresource_controller.go:352
if existing.GetAnnotations()["managed-by"] != vidraOperator && res.Status.LastSyncTime.IsZero() {
    return fmt.Errorf("resource %s/%s already exists but is not managed by this operator", ...)
}
```

The two live resources were applied by the lab bootstrap and carry no such annotation. The
requester chose to delete them and let the operator create them, over annotating in place. **That
bounces the demo workload and the fabric BGP session** — Crossplane tears the composed Objects
down and rebuilds them. It buys unambiguous provenance: every delivered resource was created by
the operator, none adopted.

## Technical Context

**Language/Version**: Python 3.12 for the repository; the operator itself is a prebuilt Go binary
this cycle configures rather than builds.

**Primary Dependencies**: no new Python dependency. Cluster-side: the `vidra-operator` Helm chart
from `https://infrahub-operator.github.io/vidra`, image
`registry.opsmill.io/opsmill/vidra:v0.0.6-opsmill2` (verified pullable without credentials).

**Storage**: N/A — no new Infrahub data. The operator's state lives in `InfrahubSync` and
`VidraResource` status.

**Testing**: `pytest tests/unit` for the repository's own gates; the delivery loop itself is
validated by the scenarios in [quickstart.md](./quickstart.md), which are cluster-side and cannot
be unit tested.

**Target Platform**: the NFD41 lab's k3s cluster (`clab-nfd41-k8s-node{1,2,3}`, v1.31.3+k3s1),
reaching Infrahub at `http://172.20.41.1:8000` over the `nfd41-mgmt` bridge.

**Project Type**: configuration and one GraphQL query, added to an existing Infrahub repository.

**Performance Goals**: merge to cluster within one `requeueSyncAfter` interval, set to `1m` against
SC-001's five-minute bar. One stored-query call per interval; a download only when a checksum moved.

**Constraints**: credentials never committed; no change to either Crossplane renderer, their
queries, or their artifact definitions; `main` only.

**Scale/Scope**: two artifacts, two sync declarations, two delivered resources. Infrahub models one
of the cluster's three applications; the other two stay lab-managed and are never touched.

## Constitution Check

*GATE: evaluated before Phase 0, re-evaluated after Phase 1. Result unchanged: **PASS**.*

| Principle | Verdict | Reasoning |
| --- | --- | --- |
| **I. Schema-Driven Architecture** | **Pass, vacuously** | No schema change, so nothing to put first. The intent is already modelled (`ServiceFabricApp`, `ServiceFabricPeering`); what this cycle adds — a cluster address and a credential — is deliberately *not* graph data. Modelling it would make the graph describe its own deployment, and the constitution separately forbids committing environment-specific endpoints. `protocols.py` is not regenerated because there is nothing new to generate from. |
| **II. Idempotent Operations** | **Pass** | No generator is added or changed. Idempotence still bites, one layer out: applying an unchanged artifact must be a no-op, which SC-002 tests by watching `resourceVersion` across a full interval. The operator's own checksum comparison is the mechanism. |
| **III. Type Safety** | **Pass, not applicable** | No Python is added, so there is no GraphQL response to type. `artifact_ids.gql` is consumed by the Go operator over `POST /api/query/…`, never by this repository's code — so no `*_query.py` model is generated for it. Generating one would create an unused file implying a Python consumer that does not exist. |
| **IV. Test-Required Quality** | **Pass, with a stated limit** | `uv run invoke lint` (ruff, mypy, yamllint, rumdl, Vale) covers everything committed, and the YAML contracts are linted like any other. **There is no unit-testable code in this cycle** — the behaviour is an operator reconciling against a live cluster. That is not a gap to be papered over with a test of a YAML file's contents; it is why quickstart.md is written as executable scenarios mapped one-to-one onto the success criteria. Integration coverage is the `$infrahub-run-integration-tests` path, which this change does not alter. |
| **V. Convention-Based Structure** | **Pass, one justified deviation** | The query follows both conventions: snake_case registration (`artifact_ids`), PascalCase operation (`ArtifactIDs`), `.gql` under `queries/`. The deviation is a new top-level `vidra/` directory, recorded below. |

### Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| New top-level `vidra/` directory, not in `AGENTS.md`'s layout | The sync declarations name Infrahub artifacts by name and branch, so a change to an artifact definition is a change to them. They belong beside what produces them. | `lab/` looks like the obvious home and is the wrong one: this repository's `lab/` is the `infrahub-avd` topology its own README marks **stale** — it models the example design this fork removed. The cluster here belongs to the separate NFD41 lab repository. Filing these under the stale lab would sit them next to the one topology they have nothing to do with. `AGENTS.md`'s layout section is updated in the same change, which is the whole cost. |

## Project Structure

### Documentation (this feature)

```text
specs/028-vidra-k8s-sync/
├── plan.md              # This file
├── research.md          # Phase 0 — ten decisions, each settled by observation
├── data-model.md        # Phase 1 — what is read from Infrahub, what is declared in Kubernetes
├── quickstart.md        # Phase 1 — setup and the scenarios that prove each success criterion
├── contracts/           # Phase 1 — the query and the four cluster objects
│   ├── artifact_ids.gql
│   ├── infrahub-syncs.yaml
│   ├── vidra-config.yaml
│   ├── infrahub-credentials.example.yaml
│   └── helm-values.yaml
├── checklists/requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks, not here
```

### Source Code (repository root)

```text
queries/
└── artifact_ids.gql                  # NEW — first occupant of a directory that held only .gitkeep

vidra/                                # NEW directory
├── helm-values.yaml                  # image override; the chart needs nothing else
├── vidra-config.yaml                 # ConfigMap: queryName, intervals
├── infrahub-syncs.yaml               # the two InfrahubSync declarations
└── infrahub-credentials.example.yaml # shape only — the real Secret is never committed

.infrahub.yml                         # +1 entry under `queries`. Nothing else.

docs/docs/
├── developer-guide/transforms.md     # finish the Crossplane section's "then push"
└── developer-guide/vidra-delivery.md # NEW — deploy, credentials, sync state, troubleshooting

docs/sidebars.ts                      # register the new page
AGENTS.md                             # record the vidra/ directory

transforms/crossplane_fabric_*.py     # UNCHANGED — the diff here must stay empty
schemas/                              # UNCHANGED
triggers.yml                          # UNCHANGED — Phase 0 removed the reason to touch it
```

**Structure Decision**: the query lives in `queries/`, which exists for exactly this — a query with
no Python consumer to be co-located with. Everything cluster-side lives in `vidra/`, justified
above. The three files the spec worried about — both renderers and their artifact definitions — are
untouched, and SC-008 makes that an assertion rather than an intention.

## Phase 2 outlook (not executed here)

Roughly: add the query and register it; create the four `vidra/` files from the contracts; install
the chart and the Secret; delete the two pre-existing resources and apply the syncs; walk the
quickstart scenarios; write the docs page and finish the transforms sentence; update `AGENTS.md`.

Two sequencing constraints worth carrying into `/speckit-tasks`:

1. **Verify the query answers before installing anything.** An unregistered or misnamed query
   produces a sync that reports success over an empty set. Every later step would look fine.
2. **The deletion step is the only destructive act in the cycle** and must come after the operator
   is running and credentialled, so the window where the resources are absent is seconds rather
   than however long troubleshooting takes.
