# Tasks: Vidra Kubernetes Delivery

**Cycle**: 028 | **Branch**: `028-vidra-k8s-sync`
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

## Three things to read before starting

**1. This cycle writes almost no code, and the risk is all in the ordering.** One `.gql` file, one
line of `.infrahub.yml`, four YAML files and two docs pages. Every hard-won finding is in
[research.md](./research.md); the tasks below assume you have read it. What makes the cycle
non-trivial is that three separate steps fail *silently* if done out of order, and one step causes
an outage.

**2. T005 is a gate, not a check.** If the stored query does not answer under the name the
operator will use, every later step still reports success — the sync returns an empty artifact set
and marks itself `Succeeded`. Do not proceed past T005 on a partial result.

**3. T017 is the only destructive task in the cycle.** It deletes `fabricapp/nfd41-demo` and
`fabricpeering/nfd41` so the operator can create them rather than adopt them. **Crossplane tears
down the composed Objects behind them and rebuilds: the demo workload and the fabric BGP session
bounce.** This was the requester's explicit choice over annotating in place. It is sequenced after
the operator is running and credentialled so the gap is seconds, not however long troubleshooting
takes.

## On testing, and what this cycle cannot do

`uv run pytest tests/unit` is a **regression gate here, not coverage**. There is no new Python, so
there is nothing to unit test; the assertion that matters is that the transform diff stays empty
(T037). The behaviour this cycle delivers is an operator reconciling against a live cluster, which
is why [quickstart.md](./quickstart.md)'s scenarios are tasks in their own right rather than a
closing formality.

`$infrahub-run-integration-tests` **is not installed**, as in cycles 020–027. The constitution's
documented alternative applies: the quickstart scenarios (T019–T024, T025–T027, T028–T030) are the
non-live substitute, and the PR body must say so (T040).

---

## Phase 1: Setup — the query, and proving it answers

**Purpose**: give the operator something to poll. Nothing may be installed until T005 passes.

- [X] T001 Create `queries/artifact_ids.gql` from [contracts/artifact_ids.gql](./contracts/artifact_ids.gql), keeping the comment header — it records why `storage_id` is queried but unused, and why the operation name is PascalCase while the registration is not
- [X] T002 Register the query in `.infrahub.yml` under `queries` as `name: artifact_ids`, `file_path: "./queries/artifact_ids.gql"`. **This is the only line this cycle adds to that file** — no transform, no artifact definition
- [X] T003 Run `uv run yamllint .infrahub.yml` and confirm clean
- [X] T004 Sync the repository into Infrahub so the query is imported, then confirm it exists: `CoreGraphQLQuery(name__value: "artifact_ids")` returns one node
- [X] T005 **GATE** — call the query the way the operator will, and confirm two artifacts come back with non-empty `id` and `checksum`: `POST http://localhost:8000/api/query/artifact_ids?branch=main` with `{"variables":{"artifactname":["Crossplane FabricApp","Crossplane FabricPeering"]}}`. An empty `edges` list means the artifact names do not match `artifact_name` in `.infrahub.yml`; fix that before continuing, because nothing downstream will tell you

**Checkpoint**: Infrahub answers the operator's only read query, under the operator's configured name.

---

## Phase 2: Foundational — the operator, running and credentialled

**Purpose**: everything that must exist before any resource is delivered.

**⚠️ No user story work can begin until this phase completes**, and T017 in particular must not be
attempted before T015.

- [X] T006 Create the `vidra/` directory and `vidra/helm-values.yaml` from [contracts/helm-values.yaml](./contracts/helm-values.yaml) — image `registry.opsmill.io/opsmill/vidra:v0.0.6-opsmill2`, overriding the chart's `ghcr.io` default
- [X] T007 [P] Create `vidra/vidra-config.yaml` from [contracts/vidra-config.yaml](./contracts/vidra-config.yaml). `queryName: "artifact_ids"` is what ties it to T002; `requeueSyncAfter: "1m"` is what SC-001 is measured against
- [X] T008 [P] Create `vidra/infrahub-syncs.yaml` from [contracts/infrahub-syncs.yaml](./contracts/infrahub-syncs.yaml). Check three fields by eye: `artefactName` (the operator's spelling, not `artifactName`), the exact artifact display names including spaces and capitals, and `targetBranch: "main"`
- [X] T009 [P] Create `vidra/infrahub-credentials.example.yaml` from [contracts/infrahub-credentials.example.yaml](./contracts/infrahub-credentials.example.yaml). **Shape only** — the real Secret is never committed
- [X] T010 Run `uv run yamllint vidra/` and confirm clean
- [X] T011 Point `kubectl` at the lab cluster (`docker exec clab-nfd41-k8s-node1 cat /etc/rancher/k3s/k3s.yaml`) and confirm three nodes `Ready` and both CRDs present: `kubectl get crd fabricapps.nfd41.lab fabricpeerings.nfd41.lab`. If either is missing, stop — that is the lab repository's bootstrap, not this cycle's work
- [X] T012 Install the operator: `helm repo add vidra https://infrahub-operator.github.io/vidra`, create namespace `vidra-system`, `helm install vidra vidra/vidra-operator -n vidra-system -f vidra/helm-values.yaml`, and confirm the deployment rolls out
- [X] T013 Create the credential Secret in `vidra-system` with `username`/`password` (**not** an API token) and label it `infrahub-api-url=172.20.41.1` — **scheme and port stripped**, per [research.md](./research.md) §6. The full URL yields "no secret found" with nothing to suggest why
- [X] T014 Apply `vidra/vidra-config.yaml` and confirm the ConfigMap carries the `app: vidra` label, which is how the operator finds it — name and namespace are not what it matches on
- [X] T015 Confirm the operator pod is `Running` and its logs show no credential or config errors before any sync exists

**Checkpoint**: the operator is running, can authenticate, and knows which query to call — but has been given nothing to deliver.

---

## Phase 3: User Story 1 — a merged change reaches the cluster (Priority: P1) 🎯 MVP

**Goal**: a merge into `main` becomes cluster state with no human in between.

**Independent Test**: change one rendered field of a `ServiceFabricApp` on a branch, merge the
proposed change, and watch `fabricapp.nfd41.lab/nfd41-demo` carry the new value — no `kubectl
apply`, no artifact download.

- [X] T016 [US1] Capture the baseline **before** anything is deleted: `kubectl get fabricapp.nfd41.lab/nfd41-demo fabricpeering.nfd41.lab/nfd41 -o yaml` and both artifact checksums, saved outside the repository. T021 compares against this, and it cannot be recovered afterwards
- [~] T017 [US1] **WITHDRAWN — not executed.** The operator adopted both resources in place (`managed-by: vidra`, original `creationTimestamp`, workload never down), so the premise was false and deleting would have caused an outage to buy nothing. See [research.md](./research.md) §A1. Original text: **DESTRUCTIVE** — delete `fabricapp.nfd41.lab/nfd41-demo` and `fabricpeering.nfd41.lab/nfd41`. Crossplane tears down the composed Objects; **the demo workload and the fabric BGP session bounce**. Do this only once T015 has passed, so the resources are absent for seconds
- [X] T018 [US1] Apply `vidra/infrahub-syncs.yaml`
- [X] T019 [US1] Confirm both `InfrahubSync` objects reach `syncState: Succeeded`, and that both resources are recreated and reach `SYNCED=True READY=True` (SC-004)
- [X] T020 [US1] Confirm `fabricapp.nfd41.lab/nfd41-access` and `nfd41-observability` are **still present and untouched** — the operator never sees resources it did not deliver, and this is the evidence
- [X] T021 [US1] Compare the recreated resources against the T016 baseline. They must match apart from XRD-defaulted fields and Crossplane's own bookkeeping (`spec.crossplane`, `resourceRefs`, timestamps). **Any other difference is a bug**, because research established the artifacts already describe what was running
- [X] T022 [US1] Prove the merge path (SC-001): create a branch, change one field the transform actually renders on the `ServiceFabricApp`, open and merge a proposed change, then observe the artifact checksum move and the cluster resource carry the new value within one sync interval. Record the elapsed time
- [X] T023 [US1] Prove the no-op path (SC-002): merge a change to a field neither renderer reads. The artifact must re-render to the same checksum and the resource's `resourceVersion` must not move across a full sync interval
- [X] T024 [US1] Prove branch isolation (SC-005): make the same edit on a branch and **do not merge**. Nothing in the cluster may change over at least one full sync interval. This is the property that makes "on merge" mean something rather than "on any edit"

**Checkpoint**: the loop is closed and demonstrated. This alone is a shippable feature.

---

## Phase 4: User Story 2 — hand edits are reverted (Priority: P2)

**Goal**: the cluster returns to the modelled intent without an Infrahub-side change.

**Independent Test**: edit a delivered resource with `kubectl`, wait one reconcile interval, watch
it revert.

- [X] T025 [US2] Patch a field of `fabricapp.nfd41.lab/nfd41-demo` that the artifact sets, and confirm it returns to the artifact's value within one `requeueResourcesAfter` interval, with no Infrahub-side change and no new artifact generation (SC-003)
- [X] T026 [US2] Delete a delivered resource by hand and confirm it is re-created from the stored manifest
- [X] T027 [US2] Record the observed reconcile latency against the configured `requeueResourcesAfter: 10m`, so the documented number is measured rather than assumed

**Checkpoint**: Infrahub is the source of truth, not merely the starting point.

---

## Phase 5: User Story 3 — the state is legible (Priority: P3)

**Goal**: answer "is the cluster current, and if not why" without reading operator logs.

**Independent Test**: a documented command sequence reports state, freshness, checksums in effect
and last error, and the docs explain how to read each.

- [X] T028 [US3] Confirm `kubectl get infrahubsync -o …` surfaces `syncState`, `checksums`, `lastSyncTime` and `lastError`, and that comparing `checksums` against Infrahub answers "is the cluster current?" directly
- [X] T029 [US3] Prove failures are visible and non-destructive (SC-006): delete the credential Secret, wait a sync interval, confirm `syncState: Failed` with a reason **and that the delivered resources are still present**. A delivery pipeline that empties a cluster when its credentials expire is worse than no pipeline
- [X] T030 [US3] Restore the Secret and confirm recovery without intervention
- [X] T031 [US3] Write `docs/docs/developer-guide/vidra-delivery.md`: deployment, credentials (including the label trap), reading sync state, and what to check when a merge does not reach the cluster. Use **relative** Markdown links only — the aggregation site sets `onBrokenLinks: 'throw'`
- [X] T032 [US3] Register the page in `docs/sidebars.ts` under the `developer-guide` items, after `developer-guide/transforms`

**Checkpoint**: all three stories independently demonstrated.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T033 [P] Finish the sentence this feature exists to complete (FR-024): `docs/docs/developer-guide/transforms.md` describes the Crossplane loop as "change the model, re-render, review the diff, then push". Rewrite the ending now that "then push" is automatic, and link the new page
- [X] T034 [P] Record the `vidra/` directory in `AGENTS.md`'s repository-layout section — it is the cycle's one convention deviation and the constitution requires it to be visible
- [X] T035 [P] Document the dead-file consequence in `docs/docs/developer-guide/vidra-delivery.md`: the NFD41 lab repository's `crossplane/apps/10-demo.yaml` and `crossplane/platform/10-peering.yaml` must not be re-applied, because Infrahub now owns those resources. `10-access.yaml` and `20-observability.yaml` are unaffected
- [X] T036 Prove the deployment is reproducible (SC-009) — **scoped**: the operator Deployment, ConfigMap and Secret were torn down and rebuilt from committed files. A full `helm uninstall` was not run because it removes the CRDs, which cascades through the finalizers to the delivered resources and takes the workload down for up to a reconcile interval. Original text: delete the `vidra-system` namespace and both syncs, rebuild from committed files plus the documented Secret command alone, and confirm the loop returns with no undocumented step
- [X] T037 Run `uv run pytest tests/unit` and confirm `git diff --stat main -- transforms/` is **empty** (SC-008) — delivery was added without disturbing rendering, which is FR-011 as an assertion rather than an intention
- [X] T038 Run `uv run invoke lint` (ruff, ruff-format, yamllint, mypy, rumdl) and confirm clean
- [X] T039 Run `uv run rumdl check` and Vale over the new and changed Markdown
- [ ] T040 Write the PR body. It **must** state: that `$infrahub-run-integration-tests` is not installed and the quickstart scenarios are the documented non-live alternative; that T017 bounced the demo workload and the BGP session, and why; and that two lab-repository files are now dead

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies. **T005 gates everything.**
- **Phase 2 (Foundational)**: needs Phase 1. Blocks all stories.
- **Phase 3 (US1)**: needs Phase 2 complete — T017 specifically must not run before T015.
- **Phase 4 (US2)** and **Phase 5 (US3)**: need Phase 3, because both observe resources that only
  exist once US1 has delivered them. Once US1 is done they are independent of each other.
- **Phase 6 (Polish)**: T033–T035 can be written any time after Phase 2; T036–T040 close the cycle.

### The ordering that actually matters

```text
T005 ──gate──▶ T012 ──▶ T013 ──▶ T014 ──▶ T015 ──▶ T016 ──▶ T017 (destructive) ──▶ T018
 │                                                   │
 │ query must answer                                 │ baseline must be captured
 │ before anything is installed                      │ before anything is deleted
```

Both arrows are one-way. T005 skipped means silent success over an empty set; T016 skipped means
T021's no-op proof is unprovable, because the evidence was deleted.

### Within each story

Prove the delivery works before proving its edge properties: T019 before T020–T021, and T022
before T023–T024 — a broken pipeline makes "nothing changed" indistinguishable from success.

### Parallel opportunities

- T007, T008, T009 — three separate files under `vidra/`, no ordering between them
- T033, T034, T035 — three separate documents
- Phases 4 and 5 once Phase 3 is complete, if two people are available
- Nothing in Phase 1 or Phase 3 parallelises: each step's output is the next step's input

---

## Parallel Example: Phase 2 configuration files

```bash
Task: "Create vidra/vidra-config.yaml from contracts/vidra-config.yaml"
Task: "Create vidra/infrahub-syncs.yaml from contracts/infrahub-syncs.yaml"
Task: "Create vidra/infrahub-credentials.example.yaml from contracts/infrahub-credentials.example.yaml"
```

---

## Implementation Strategy

### MVP — Phases 1 to 3

Setup, Foundational, then User Story 1. At T024 the feature is complete in the sense the request
asked for: a merge in Infrahub updates Kubernetes, with the branch-isolation property that makes
that claim true rather than approximate. Stop and validate there.

### Incremental delivery

1. Phases 1–2 → the operator runs and can read Infrahub, delivering nothing
2. Phase 3 → **MVP**: the loop is closed and the merge path is demonstrated
3. Phase 4 → drift correction: Infrahub becomes the source of truth, not the starting point
4. Phase 5 → legibility: the state can be read, and failures are proven non-destructive
5. Phase 6 → documentation, conventions, and the reproducibility proof

### If you only have an hour

T001–T005 are worth doing alone. The query is the feature's only Infrahub-side artifact, and T005
proves the operator's read path works against this instance — which is the half of the system that
cannot be inspected from the cluster.
