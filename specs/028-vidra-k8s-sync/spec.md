# Transform Specification: Vidra Kubernetes Delivery

> **Workflow**: Infrahub Transform
> **Skill**: Use the `infrahub-managing-transforms` skill to implement this spec.

**Feature Branch**: `028-vidra-k8s-sync`
**Created**: 2026-09-14
**Status**: Draft
**Input**: User description: "lets setup vidra so that on merge in infrahub k8's gets updated: https://github.com/opsmill/vidra"

## Transform Type

- **Approach**: Artifact delivery — **no new renderer**. The two Crossplane renderers this
  feature delivers already exist (`crossplane_fabric_peering`, `crossplane_fabric_app`,
  cycles 011 and 017) and are not modified. What is missing is the last hop: the rendered
  manifests never leave Infrahub. The one Infrahub-side artifact this cycle adds is a
  registered GraphQL query, `ArtifactIDs`, which is the interface the Vidra operator polls.
- **Output Format**: `application/yaml` — unchanged. Both existing artifact definitions already
  declare it, and both render one `nfd41.lab/v1alpha1` custom resource.
- **Target Nodes**: `ServiceFabricPeering` (group `service_fabric_peerings`) and
  `ServiceFabricApp` (group `service_fabric_apps`) — unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A merged change reaches the cluster on its own (Priority: P1)

A network engineer changes a fabric application or a cluster peering in Infrahub — a replica
count, an advertised prefix, a BGP timer — on a branch, opens a proposed change, and merges it.
The two Crossplane artifacts on `main` re-render, and within a bounded interval the matching
`FabricApp` / `FabricPeering` custom resources in the Kubernetes cluster carry the new values.
Nobody downloads an artifact, and nobody runs `kubectl apply`.

**Why this priority**: This is the entire request, and it is the sentence the transforms
documentation currently cannot finish. `docs/docs/developer-guide/transforms.md` describes the
loop as "change the model, re-render, review the diff, then push" — "then push" is a human with
a terminal. Without this story there is no feature; with it alone the feature is complete and
useful, because drift correction and observability both fall out of the same operator.

**Independent Test**: On a branch, change one field of a seeded `ServiceFabricApp`, merge the
proposed change into `main`, and watch the cluster. The corresponding `FabricApp` resource must
show the new field value without manual intervention, and `kubectl get infrahubsync` must report
a `syncState` of `Succeeded` with a `lastSyncTime` after the merge.

**Acceptance Scenarios**:

1. **Given** the operator is running and both artifacts are in sync, **When** a proposed change
   altering a `ServiceFabricApp` is merged into `main`, **Then** the rendered artifact's checksum
   changes and the operator applies the new manifest to the cluster without operator intervention.
2. **Given** a merged change alters nothing the Crossplane renderers read (a description, an
   unrelated tag), **When** the artifact re-renders to an identical checksum, **Then** the
   operator applies nothing and the cluster resources are left untouched.
3. **Given** a new `ServiceFabricApp` is created and joined to `service_fabric_apps` on `main`,
   **When** its artifact is generated, **Then** a corresponding cluster resource appears without
   any change to the operator's configuration.
4. **Given** the Infrahub instance is unreachable, **When** a sync interval elapses, **Then** the
   sync reports a failure state with the reason recorded, and the resources already in the cluster
   are left as they are rather than deleted.

---

### User Story 2 - Hand edits in the cluster are reverted to the modelled intent (Priority: P2)

Someone edits an applied `FabricApp` or `FabricPeering` resource directly with `kubectl`. The
cluster no longer matches what Infrahub says. The operator notices and restores the values the
model declares.

**Why this priority**: It is what makes Infrahub the source of truth rather than merely the
starting point, and it is the difference between a one-shot push and continuous delivery. It is
P2 because story 1 delivers value without it — a merge still propagates — but drift makes the
Infrahub diff a lie, which is the failure mode this repository's whole review workflow exists to
prevent.

**Independent Test**: Edit an applied resource in the cluster with `kubectl edit`, change a field
the artifact sets, and wait one reconcile interval. The field must return to the artifact's value,
with no Infrahub-side change and no new artifact generation.

**Acceptance Scenarios**:

1. **Given** an applied resource whose field has been changed by hand, **When** a reconcile
   interval elapses, **Then** the field is restored to the artifact's value.
2. **Given** an applied resource has been deleted by hand, **When** a reconcile interval elapses,
   **Then** it is re-created from the artifact.

---

### User Story 3 - An operator can see whether the cluster is current (Priority: P3)

Before trusting the cluster, someone needs to answer two questions without reading logs: is the
cluster carrying the artifacts as of the last merge, and if not, why not.

**Why this priority**: Diagnosis, not delivery. Stories 1 and 2 work without it; troubleshooting
them does not. It is last because the operator already exposes the state — this story is about
making it reachable and documented, not about building it.

**Independent Test**: With the operator running, a documented command sequence reports the
per-sync state, the last sync time, the artifact checksums in effect, and the last error, and the
documentation in `docs/docs/` explains how to read each.

**Acceptance Scenarios**:

1. **Given** a healthy sync, **When** an operator runs the documented status command, **Then**
   the state reads `Succeeded` and the last sync time is within one sync interval.
2. **Given** a sync failing on unreachable Infrahub or bad credentials, **When** the same command
   is run, **Then** the failure state and a human-readable reason are both visible.

---

### Edge Cases

- **A merge that regenerates no artifact.** If merging into `main` does not cause the two
  Crossplane artifacts to re-render, the operator polls an unchanged checksum forever and the
  cluster silently stays on the previous intent. This is the feature's single most important
  failure mode, because it is silent — see FR-012 through FR-014.
- **An artifact that fails to render.** `crossplane_fabric_app` fetches a `CoreFileObject`
  attachment; if the attachment is missing (the documented consequence of skipping the
  `payloads/` upload step) the artifact renders an app with an empty `manifests` list. The
  operator has no way to distinguish "deliberately empty" from "seed step skipped" and will
  faithfully apply the empty result.
- **An artifact deleted in Infrahub.** When a `ServiceFabricApp` is removed from its target group,
  its artifact stops being generated. Whether the cluster resource is then removed or orphaned
  must be a stated, tested outcome rather than whatever happens.
- **Two artifacts, one name.** Both artifact definitions produce one artifact per group member,
  and the operator selects by artifact *name*, not by object — so all members of a group are
  delivered by a single sync. A member joining the group mid-interval must be picked up.
- **Manifests rendering to invalid YAML or a rejected resource.** The Kubernetes API may reject a
  manifest the transform happily produced (a string where an integer is required, a namespace that
  does not exist). The rejection must surface as a sync failure, not as silence.
- **Credentials rotated or absent.** The operator authenticates to Infrahub; an expired or missing
  credential must produce a visible failure rather than an empty sync that looks like "no changes".
- **Branch confusion.** The operator is pinned to one branch. An artifact regenerated on a feature
  branch must not reach the cluster — only `main` does. This is the property that makes "on merge"
  mean something.
- **Both artifact kinds arriving together.** A peering change and an app change merged in the same
  proposed change must both land; neither sync may mask the other's failure.

## Requirements *(mandatory)*

### Functional Requirements

#### GraphQL Query

- **FR-001**: A GraphQL query named `ArtifactIDs` MUST be created at `queries/ArtifactIDs.gql`.
  The `queries/` directory exists in this repository and currently holds only `.gitkeep`; this is
  its first occupant, and it is the right home because the query has no Python consumer to be
  co-located with — the consumer is the operator.
- **FR-002**: The query MUST accept the artifact-name parameter the operator supplies
  (`$artifactname: [String]`) and filter `CoreArtifact` by name.
- **FR-003**: The query MUST return, for each matching artifact: the artifact id, the storage id,
  the checksum, and the name. The checksum is load-bearing — it is what lets the operator skip a
  download when nothing changed, which is what makes scenario 2 of story 1 testable.
- **FR-004**: The query MUST be registered in `.infrahub.yml` under `queries` so it is created by
  repository sync rather than by hand in the UI, consistent with every other query in this repo.

#### Delivery Configuration

- **FR-005**: Kubernetes deployment assets MUST be added to this repository so the operator's
  configuration is reviewable and reproducible rather than applied ad hoc. They MUST cover: the
  operator deployment itself, the credentials it uses to reach Infrahub, its behavioural
  configuration, and one sync declaration per artifact.
- **FR-006**: Exactly two sync declarations MUST be defined, one per existing artifact:
  `Crossplane FabricPeering` and `Crossplane FabricApp`. They are separate because their target
  groups are separate, for the reason already recorded in `.infrahub.yml`: applications and
  peerings are different sets, and one declaration pointed at both would try to deliver a resource
  it cannot render.
- **FR-007**: Both sync declarations MUST be pinned to the `main` branch. This is what makes the
  trigger a *merge* rather than any edit anywhere: work on a feature branch regenerates that
  branch's artifacts and must not reach the cluster.
- **FR-008**: The operator image MUST be `registry.opsmill.io/opsmill/vidra`, tag
  `v0.0.6-opsmill2`, overriding the upstream chart default of `ghcr.io/infrahub-operator/vidra`.
- **FR-009**: Infrahub credentials MUST be supplied to the operator through a Kubernetes Secret
  and MUST NOT be committed to this repository. The repository MUST commit the shape of the secret
  and how to create it, never its contents — consistent with the constitution's rule that
  environment-specific tokens stay uncommitted.
- **FR-010**: The sync interval MUST be configurable and its committed default MUST be stated,
  so "within a bounded interval" in story 1 has a number behind it.
- **FR-011**: The delivery path MUST NOT require changes to `crossplane_fabric_peering.py`,
  `crossplane_fabric_app.py`, their queries, or their artifact definitions. If a change to either
  renderer turns out to be required, that is a finding to report, not a silent edit — the
  artifacts are held by existing unit tests and by a documented byte-comparison contract.

#### Post-Merge Regeneration

- **FR-012**: Merging a proposed change into `main` MUST result in the affected Crossplane
  artifacts being regenerated on `main` without a human running a command.
- **FR-013**: **Resolved by Phase 0 — no trigger is needed.** `post_process_branch_merge` submits
  `TRIGGER_ARTIFACT_DEFINITION_GENERATE` for the target branch after every merge
  (`backend/infrahub/core/branch/tasks.py:641-660`), which re-renders every artifact definition on
  `main`. `triggers.yml` is untouched.
- **FR-014**: The regeneration path MUST be verified end to end either way. A test or a documented,
  repeatable procedure MUST demonstrate a merge producing a changed artifact checksum on `main`.
  This is not optional even if FR-012 turns out to be free: its failure mode is silence, which is
  indistinguishable from "nothing changed", and it is the single point on which the whole feature
  turns.

#### Artifact & Registration

- **FR-015**: No new transform is registered. The existing `python_transforms` entries for
  `crossplane_fabric_peering` and `crossplane_fabric_app` are unchanged.
- **FR-016**: No new artifact definition is created. The existing `crossplane_fabric_peering` and
  `crossplane_fabric_app` definitions already declare `content_type: application/yaml` and target
  `service_fabric_peerings` and `service_fabric_apps` respectively.
- **FR-017**: `.infrahub.yml` MUST gain exactly one entry: the `ArtifactIDs` query. Any further
  change to that file in this cycle is out of scope.

#### Target Environment

> **Revised after Phase 0 research.** This section originally required standing a cluster up, on
> a report that none was reachable — true of this host's kubeconfig, false about the lab. The
> NFD41 lab's three-node k3s cluster is running with Crossplane, the XRDs, the compositions and
> these very resources. The requester retargeted the cycle at it. See
> [research.md](./research.md) §2.

- **FR-018**: Delivery MUST target the running NFD41 lab cluster (`clab-nfd41-k8s-node{1,2,3}`),
  with the operator running in it. Nothing is created that the lab does not already provide.
- **FR-019**: Bringing the operator up MUST be reproducible from committed instructions. The
  *cluster's* own bring-up belongs to the NFD41 lab repository and is a prerequisite, not a
  deliverable of this cycle.
- **FR-020**: The `nfd41.lab/v1alpha1` `FabricApp` and `FabricPeering` kinds MUST be registered
  before delivery is attempted. **Already satisfied** by the lab's bootstrap — verified present as
  `fabricapps.nfd41.lab` and `fabricpeerings.nfd41.lab`. It remains stated because a cluster that
  does not know these kinds rejects every manifest, which looks like an operator fault and is not.
- **FR-021**: The deployment MUST make the destination explicit rather than relying on the
  in-cluster default, so a later move to a separate cluster is a configuration change rather than
  a rediscovery.
- **FR-022**: ~~The two resources the lab bootstrap applied MUST be deleted so the operator
  creates them itself.~~ **Withdrawn during implementation — the premise was false.** The operator
  adopted `fabricapp/nfd41-demo` and `fabricpeering/nfd41` in place, labelling them
  `managed-by: vidra` without recreating them; both kept their original four-day-old
  `creationTimestamp` and the demo workload never went down. The refusal guard is only evaluated
  when a `VidraResource` has never synced, which does not happen on the sync-driven path. Deleting
  them would have caused an outage to buy nothing. See [research.md](./research.md) §A1.
- **FR-023**: After cut-over the lab repository's `crossplane/apps/10-demo.yaml` and
  `crossplane/platform/10-peering.yaml` MUST be treated as dead files. Re-applying either restores
  a second writer for a resource Infrahub now owns. `10-access.yaml` and `20-observability.yaml`
  remain the lab's and are never touched — the operator only deletes what it delivered.

#### Documentation

- **FR-024**: `docs/docs/developer-guide/transforms.md` MUST be updated so the Crossplane
  section's "change the model, re-render, review the diff, then push" finishes — "then push" is
  the step this feature automates, and leaving the sentence as it is would be a documented
  falsehood the day this merges.
- **FR-025**: A page MUST document how to deploy the operator, how to supply credentials, how to
  read sync state (story 3), and what to check when a merge does not reach the cluster. It MUST
  use relative Markdown links, per the documentation-publishing rule for the aggregation site.

### Key Files

| File | Purpose |
|------|---------|
| `queries/ArtifactIDs.gql` | GraphQL query the operator polls for artifact ids and checksums |
| `.infrahub.yml` | Registers `ArtifactIDs` under `queries` — the only change to this file |
| *(deployment assets — location set during planning)* | Operator deployment, config, secret shape, and the two sync declarations |
| `docs/docs/developer-guide/transforms.md` | Finishes the Crossplane delivery story |
| *(new documentation page)* | Deployment, credentials, sync state, and troubleshooting |
| `vidra/` *(new)* | Operator values, config, sync declarations, and the credential Secret's shape |
| `transforms/crossplane_fabric_peering.py` | **Unchanged** — existing renderer |
| `transforms/crossplane_fabric_app.py` | **Unchanged** — existing renderer |

### Key Entities *(include if feature involves data)*

- **`ServiceFabricPeering`**: the ordered intent "this cluster peers with the fabric". Already the
  target of the `Crossplane FabricPeering` artifact; the artifact hangs off the service while every
  rendered value comes from the technical layer beneath it.
- **`ServiceFabricApp`**: an application deployed on the cluster, whose Kubernetes manifests and
  Helm values live as `CoreFileObject` attachments rather than JSON attributes.
- **`CoreArtifact`**: the rendered manifest as Infrahub stores it. Its **checksum** is the change
  signal this whole feature turns on, and its **name** is how a sync selects what to deliver.
- **Sync declaration**: the cluster-side statement "keep this cluster carrying this named artifact
  from this branch". One per artifact name, two in total.
- **Delivered resource**: a `nfd41.lab/v1alpha1` `FabricApp` or `FabricPeering` custom resource in
  the cluster, which the lab's Crossplane composition then consumes. This feature delivers the
  custom resource; Crossplane's own reconciliation of it is downstream and out of scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A merged change to a fabric application or cluster peering is visible in the cluster
  within one sync interval, with a committed default of no more than five minutes, and with zero
  manual commands between the merge and the cluster reflecting it.
- **SC-002**: A merge that changes nothing either renderer reads produces no change to any cluster
  resource — verified by resource generation or resourceVersion staying put across a full interval.
- **SC-003**: A hand edit to a delivered resource is reverted within one `requeueResourcesAfter`
  interval. Note this is **not** the sync interval: the sync path short-circuits on an unchanged
  checksum, so drift is corrected only by the resource reconcile. See [research.md](./research.md) §A4.
- **SC-004**: Both artifact kinds deliver: at least one `FabricApp` and one `FabricPeering` resource
  are present in the cluster and carry values traceable to their Infrahub source objects.
- **SC-005**: A change made on a feature branch and *not* merged produces no change in the cluster,
  demonstrated over at least one full sync interval.
- **SC-006**: Every failure mode in the Edge Cases list — unreachable Infrahub, bad credentials, a
  manifest the cluster rejects — produces a visible failure state naming a reason, and none of them
  silently deletes a resource that was previously delivered correctly.
- **SC-007**: A reader following the new documentation, starting from a cluster and an Infrahub
  instance, reaches a working sync without consulting the upstream project's documentation or this
  spec.
- **SC-008**: `uv run invoke lint` and `uv run pytest tests/unit` pass, and no existing Crossplane
  transform test changes — confirming FR-011, that delivery was added without disturbing rendering.
- **SC-009**: The operator's deployment — namespace, credentials, config and both sync
  declarations — can be torn down and rebuilt from committed instructions alone, and the
  merge-to-cluster loop works again afterwards with no undocumented step.

## Assumptions

- **The renderers are finished and correct.** Cycles 011 and 017 delivered both Crossplane
  transforms with tests; this cycle treats their output as a fixed contract.
- **Delivery is polling, not push.** The operator learns of a merge by polling the artifact's
  checksum on `main`. Infrahub does not push to it, and no webhook is added. The upstream
  operator's "event-based reconcile" setting refers to Kubernetes events, not Infrahub events, so
  it does not change how a merge is noticed.
- **The lab's cluster is the target.** The NFD41 lab bootstraps k3s with Cilium, Crossplane, the
  XRDs and compositions on its `ComputePhysicalServer` nodes, and it is running. Delivery is a
  no-op in effect: the peering artifact's spec is identical to the live resource, and the app
  artifact differs only in XRD-defaulted fields carrying the same values.
- **Both artifacts are in scope.** The user asked for "k8s gets updated", and the repository has
  exactly two artifacts that describe Kubernetes state. Delivering one and not the other would
  leave half the cluster manual.
- **Operator version.** `registry.opsmill.io/opsmill/vidra:v0.0.6-opsmill2`, as supplied. The
  upstream chart at that version defines the two custom resource kinds this feature configures;
  no upstream code change is assumed or required.
- **Crossplane and the `nfd41.lab/v1alpha1` definitions already exist**, installed by the lab's
  own bootstrap. This feature delivers custom resources; Crossplane's reconciliation of them into
  Cilium BGP policy and workloads is downstream and out of scope.
- **Infrahub models one of the cluster's three applications.** `nfd41-access` and
  `nfd41-observability` have no artifact and stay lab-managed; the operator never touches a
  resource it did not deliver.
- **Secrets stay out of the repository.** The constitution requires environment-specific tokens to
  remain uncommitted; the repository commits the shape and the instructions, not the values.
- **No schema change.** No node, attribute, relationship, or dropdown value is added. If planning
  finds one is needed, the schema-first principle means that becomes its own earlier cycle.
