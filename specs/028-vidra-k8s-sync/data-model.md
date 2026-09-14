# Data Model: Vidra Kubernetes Delivery

**Feature**: `028-vidra-k8s-sync` | **Date**: 2026-09-14

## No Infrahub schema change

This cycle adds no node, generic, attribute, relationship or dropdown value, and touches no file
under `schemas/`. `src/solution_arista_avd/protocols.py` is not regenerated, because there is
nothing new to generate from.

That is not an oversight to be checked later — it is the design. The two things the model would
need to carry for a delivery pipeline are *what to render* and *where it goes*. The first is
already modelled: `ServiceFabricApp` and `ServiceFabricPeering`, each in an artifact target group.
The second is not model data at all — it is the address of a cluster and a credential, which the
constitution requires to stay out of the repository. Putting a cluster endpoint in the graph would
make the model describe the deployment of the model.

The entities below are therefore split into **what the feature reads from Infrahub** (existing,
unchanged) and **what it declares in Kubernetes** (new, and outside the graph).

## Read from Infrahub

### `CoreArtifact` — the change signal

Built-in kind. Not defined by this repository, not modified here. The feature depends on four
fields of it, and on one of them very heavily.

| Field | Type | Role in this feature |
| --- | --- | --- |
| `id` | UUID | What the artifact is fetched by — `GET /api/artifact/{id}`. Not `storage_id`. |
| `checksum` | Text | **The entire change-detection mechanism.** A sync downloads only when this differs from what it last saw. |
| `name` | Text | What a sync selects on: `Crossplane FabricApp` or `Crossplane FabricPeering`. Selection is by name, so one sync covers every member of the target group. |
| `storage_id` | UUID | Returned by the query, unused by the fetch path. Kept because the operator's query shape expects it. |

**Validation rule that falls out of this**: the names in the sync declarations MUST equal the
`artifact_name` values in `.infrahub.yml` — `Crossplane FabricPeering` and `Crossplane FabricApp`,
spaces and capitals included. They are display names, not identifiers, and nothing at either end
will warn about a mismatch; the sync simply returns no artifacts and reports success over an
empty set.

### `ServiceFabricApp` / `ServiceFabricPeering` — the intent

Existing kinds, unchanged. They matter here only as the artifact targets: group membership
(`service_fabric_apps`, `service_fabric_peerings`) is what decides whether an object's manifest
reaches the cluster at all. A new application joins delivery by joining the group — no
configuration change on the cluster side.

Current population, which sets the cycle's expected blast radius:

| Kind | Members with an artifact | Delivered |
| --- | --- | --- |
| `ServiceFabricApp` | `nfd41-demo` | yes |
| `ServiceFabricPeering` | `nfd41-fabric-peering` → resource `nfd41` | yes |

## Declared in Kubernetes

These are cluster-side objects. They are configuration, not graph data, and they live in `vidra/`.

### `InfrahubSync` — "keep this cluster carrying this artifact"

`infrahub.operators.com/v1alpha1`, **cluster-scoped**. Two instances, one per artifact name.

| Field | Value for this feature | Why |
| --- | --- | --- |
| `spec.source.infrahubAPIURL` | `http://172.20.41.1:8000` | The `nfd41-mgmt` gateway is the host running Infrahub. Not `localhost` — that is the node. |
| `spec.source.targetBranch` | `main` | **This is what makes the trigger a merge.** A feature branch regenerates its own artifacts and they go nowhere. |
| `spec.source.artefactName` | `Crossplane FabricApp` / `Crossplane FabricPeering` | Note the field's spelling — `artefactName`, not `artifactName`. |
| `spec.source.targetDate` | unset | Unset means now. Setting it pins delivery to a point in the past, which is a debugging tool, not a mode to run in. |
| `spec.destination.namespace` | `nfd41-demo` / `default` | Only applies to manifests that carry no namespace of their own. Both artifacts render cluster-scoped composite resources, so it is a fallback that should never fire. |
| `spec.destination.reconcileOnEvents` | `false` | Story 2's drift correction comes from the timed requeue. Event-based reconcile keys off Kubernetes events and disables the timer. |
| `spec.destination.server` | set explicitly | Same cluster, but stated rather than defaulted, per FR-021. |

**Status**, which is what story 3 reads:

| Field | Meaning |
| --- | --- |
| `syncState` | `Pending` / `Running` / `Succeeded` / `Failed` / `Stale` |
| `checksums` | The artifact checksums in effect. Comparing these to Infrahub answers "is the cluster current?" directly. |
| `lastSyncTime` | Freshness. Within one sync interval or something is wrong. |
| `lastError` | Why, when `syncState` is `Failed`. |

### `VidraResource` — one delivered manifest

`infrahub.operators.com/v1alpha1`, cluster-scoped. **Created by the operator, never by hand.**
One per downloaded artifact; it holds the manifest and the record of what that manifest produced.

| Field | Meaning |
| --- | --- |
| `spec.manifest` | The artifact's bytes as downloaded. |
| `status.managedResources` | Every resource created from it — kind, apiVersion, name, namespace. This is the ownership ledger. |
| `status.DeployState` | `Succeeded`, or `Stale` when old resources remain to be cleaned up. |

It is listed here because it is what an operator actually inspects when delivery misbehaves, and
because its `managedResources` list is the evidence for "the operator only deletes what it owns".

### `Secret` — Infrahub credentials

**Never committed.** The repository holds its shape and the command to create it.

| Field | Value | Trap |
| --- | --- | --- |
| `metadata.labels["infrahub-api-url"]` | `172.20.41.1` | **Port stripped, scheme stripped.** The operator computes this as `strings.Split(apiURL, ":")[1]` with `//` trimmed. A colon is not legal in a label value, so it could not be otherwise — but the full URL here yields "no secret found" with nothing to suggest why. |
| `data.username` / `data.password` | base64 | A username and password, **not** an API token — the operator exchanges them at `/api/auth/login`. |

Selection is by label across the whole cluster, newest first, so more than one matching Secret is
a hazard rather than a fallback.

### `ConfigMap` — operator behaviour

Named `vidra-config`, labelled `app: vidra`, which is how the operator finds it.

| Key | Value | Why |
| --- | --- | --- |
| `queryName` | `artifact_ids` | Overrides the operator's `ArtifactIDs` default so the registered query can follow this repository's snake_case convention. |
| `requeueSyncAfter` | `1m` | Merge-to-cluster latency. SC-001 asks for five minutes or better. |
| `requeueResourcesAfter` | `10m` | Drift correction cadence for story 2. |
| `eventBasedReconcile` | `false` | Keying off Kubernetes events does nothing for merge latency and disables the timed requeue. |

## State transitions

The loop this feature exists to close, and where each step can stall:

```text
merge into main
      │  post_process_branch_merge -> TRIGGER_ARTIFACT_DEFINITION_GENERATE (built in)
      ▼
artifact re-rendered on main
      │  checksum moves only if the bytes moved
      ▼
sync polls POST /api/query/artifact_ids   ── unchanged checksum ──▶ nothing happens (correct)
      │  checksum differs
      ▼
GET /api/artifact/{id}?branch=main
      ▼
VidraResource created/updated
      ▼
manifest applied ──▶ Crossplane reconciles the composite
```

`syncState` transitions `Pending → Running → Succeeded`, or `→ Failed` with `lastError` set.
`Failed` leaves already-delivered resources in place; it never deletes on error — which is why an
unreachable Infrahub degrades to "stale but serving" rather than "empty cluster".
