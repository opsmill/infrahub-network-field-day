# Phase 0 Research: Vidra Kubernetes Delivery

**Feature**: `028-vidra-k8s-sync` | **Date**: 2026-09-14

Everything below was settled by observation against the running stack, not by reading
documentation and hoping. Two findings changed the shape of the cycle; both are marked.

## 1. Merge already regenerates artifacts — no trigger needed

**Decision**: Add nothing to `triggers.yml`. Infrahub 1.10.6 does this itself.

**Rationale**: `post_process_branch_merge` — the `branch-merge-post-process` flow — submits
`TRIGGER_ARTIFACT_DEFINITION_GENERATE` for the *target* branch after every merge:

```python
# backend/infrahub/core/branch/tasks.py:641-660
@flow(name="branch-merge-post-process", ...)
async def post_process_branch_merge(source_branch: str, target_branch: str, context) -> None:
    ...
    await get_workflow().submit_workflow(
        workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE,
        context=context,
        parameters={"branch": target_branch},
    )
```

That workflow resolves to `generate_artifact_definition(branch)`, which fetches **all**
`CoreArtifactDefinition` objects on the branch and submits
`REQUEST_ARTIFACT_DEFINITION_GENERATE` for each (`backend/infrahub/git/tasks.py:494-509`). So a
merge into `main` re-renders every artifact definition on `main`, the two Crossplane ones
included. The checksum moves if and only if the rendered bytes moved, which is exactly the signal
the operator polls on.

**This resolves FR-013 in the negative**: the branch of the spec that would have added a trigger
does not apply. FR-014's end-to-end verification still stands — the regeneration is real, but the
*whole chain* (merge → regenerate → checksum → download → apply) has never been run.

**Alternatives considered**: a `CoreGeneratorAction` entry in `triggers.yml` (rejected — it would
duplicate built-in behaviour and fire a second, redundant generation); a repository webhook
(rejected — nothing to add it to, and the operator polls rather than listens).

## 2. The target cluster already exists, and it is the lab's

**Decision**: Target the live NFD41 lab cluster. Run the operator in it.

> **This reversed a spec decision.** The spec said to stand a cluster up, on my own report that
> none was reachable. That was true of this host's kubeconfig and false about the lab. The
> requester was shown the evidence below and chose the lab cluster.

**Evidence**:

```text
clab-nfd41-k8s-node1   rancher/k3s:v1.31.3-k3s1   Up 4 days
clab-nfd41-k8s-node2   rancher/k3s:v1.31.3-k3s1   Up 4 days
clab-nfd41-k8s-node3   rancher/k3s:v1.31.3-k3s1   Up 4 days

NAME        STATUS   ROLES                  AGE    VERSION
k8s-node1   Ready    control-plane,master   4d5h   v1.31.3+k3s1
k8s-node2   Ready    <none>                 4d5h   v1.31.3+k3s1
k8s-node3   Ready    <none>                 4d5h   v1.31.3+k3s1
```

Crossplane is installed, and the kinds the artifacts render are registered:
`fabricapps.nfd41.lab`, `fabricpeerings.nfd41.lab`, plus their compositions. **FR-020 is already
satisfied** by the lab's own bootstrap (`lab/k8s/bootstrap/install-crossplane.sh` in the NFD41 lab
repo) — this cycle installs nothing of Crossplane's.

**Connectivity**: the nodes sit on the `nfd41-mgmt` bridge (172.20.41.0/24) whose gateway is the
host, and the host runs Infrahub on 8000. From inside `k8s-node1`:

```text
$ wget -qO- http://172.20.41.1:8000/api/config
{"main":{"docs_index_path":...,"allow_anonymous_access":true,...
```

So `infrahubAPIURL` is **`http://172.20.41.1:8000`**. Not `localhost` — that is the node.

**Alternatives considered**: a scratch k3d/kind cluster (rejected by the requester — it would need
Crossplane, the XRDs and the compositions installed before anything could land, and would prove
delivery against a cluster nobody uses); scratch first then cut over (rejected — roughly doubles
the environment work for a rehearsal).

## 3. Going live is a no-op in effect — which is why it is safe

**Finding**: both artifacts already match what the cluster is running.

| Artifact | Live resource | Result |
| --- | --- | --- |
| `Crossplane FabricPeering` → `nfd41` | `fabricpeering.nfd41.lab/nfd41` | **`spec` identical** |
| `Crossplane FabricApp` → `nfd41-demo` | `fabricapp.nfd41.lab/nfd41-demo` | differs only by XRD defaults |

The `FabricApp` difference is two keys the artifact omits and the live object carries:
`expose.communities` and `expose.advertisementSelector`. Both are **defaults declared in the
XRD** (`communities: ['65401:112']`, `advertisementSelector: {nfd41.lab/advertise: fabric}`), so
the API server re-injects the same values on apply. The reverse difference — the artifact
spelling out `policy.allowIntraNamespace`, `allowEgressToAPIServer`, `allowEgressToInternet` where
the lab's hand-written file omits them — is the same story in the other direction: identical
values, explicit rather than defaulted.

**Why this matters**: the riskiest thing about pointing a continuous-delivery operator at a
working cluster is that its first act is to overwrite live state. Here the state it would write is
the state already there. The cut-over is a formality, and any observed change is a bug.

## 4. The first sync would have failed, and why

**Finding**: the operator refuses to adopt a resource it did not create — but only on the first
sync of a given declaration:

```go
// internal/controller/vidraresource_controller.go:352
if existing.GetAnnotations()["managed-by"] != vidraOperator && res.Status.LastSyncTime.IsZero() {
    return fmt.Errorf("resource %s/%s already exists but is not managed by this operator", ...)
}
```

`fabricapp/nfd41-demo` and `fabricpeering/nfd41` were applied by the lab bootstrap and carry no
such annotation, so the first reconcile would have errored.

**Decision**: delete both resources and let the first sync create them — the requester's choice
over annotating in place.

**Consequence, stated plainly**: Crossplane tears down the composed Objects behind them and
rebuilds. The demo workload and the fabric BGP session **bounce**. That is accepted, not
overlooked; it buys unambiguous provenance — every delivered resource was created by the operator
rather than adopted, so nothing in the cluster has a murky origin.

Note an upstream inconsistency worth knowing when reading logs: the operator *writes*
`managed-by: vidra` as a **label** on the desired object but *reads* it as an **annotation** on the
existing one. The guard is therefore effectively "first sync must not collide", not a durable
ownership check. It is bypassed on every sync after the first, because `LastSyncTime` is no longer
zero.

## 5. Scope is one of three applications

**Finding**: the cluster runs three `FabricApp` resources; Infrahub models one.

```text
fabricapp.nfd41.lab/nfd41-access          <- no Infrahub artifact
fabricapp.nfd41.lab/nfd41-demo            <- Crossplane FabricApp artifact
fabricapp.nfd41.lab/nfd41-observability   <- no Infrahub artifact
```

**Decision**: deliver what is modelled. `nfd41-access` and `nfd41-observability` stay lab-managed.

**Why this is safe**: the operator only ever deletes resources that leave a manifest **it owns**
(owner annotations, `vidraresource_controller.go:294-308`). A resource it never delivered is
never touched. The two unmodelled apps are invisible to it.

**This is the honest answer to FR-022's two-writer question**: after cut-over there is exactly one
writer per resource. Infrahub owns `nfd41-demo` and `nfd41`; the lab repo's
`crossplane/apps/10-demo.yaml` and `crossplane/platform/10-peering.yaml` become **dead files that
must not be re-applied**, and the lab repo's bootstrap needs to know that. `10-access.yaml` and
`20-observability.yaml` remain the lab's, unchanged.

## 6. How the operator talks to Infrahub

Three endpoints, all verified by hand against the running instance with `admin` / `infrahub`:

| Call | Endpoint | Verified |
| --- | --- | --- |
| Authenticate | `POST /api/auth/login` (username + password) | token, 320 bytes |
| Poll | `POST /api/query/{queryName}?branch=…` with `{"artifactname": …}` | `http=200` |
| Fetch | `GET /api/artifact/{artifactID}?branch=…` | `http=200`, 494 bytes |

**Two details that would otherwise cost an afternoon:**

- **It authenticates with a username and password, not an API token.** The `Login` call exchanges
  them for a token internally (`internal/adapter/infrahub/client.go:152`). An
  `INFRAHUB_API_TOKEN`-shaped secret will not work.
- **The credential Secret's label value has the port stripped.** The operator finds the Secret by
  listing on `infrahub-api-url=<trimmed>`, where trimmed is computed as:

  ```go
  strings.TrimPrefix(strings.Split(apiURL, ":")[1], "//")   // "http://172.20.41.1:8000" -> "172.20.41.1"
  ```

  So the label is `infrahub-api-url: "172.20.41.1"`. Using the full URL, or keeping the port,
  silently yields "no secret found" — and it has to be this way round, because a colon is not a
  legal character in a Kubernetes label value.

It downloads by **artifact id**, not `storage_id`.

## 7. Query registration name

**Decision**: file `queries/artifact_ids.gql`, GraphQL operation `ArtifactIDs`, registered in
`.infrahub.yml` as `name: artifact_ids`, with the operator's ConfigMap setting
`queryName: "artifact_ids"`.

**Rationale**: the repository's registered query names are snake_case without exception
(`avd_device_hostvar`, `cabling_plan`, `crossplane_fabric_app`), while the operation name inside
each `.gql` is PascalCase (`CrossplaneFabricAppQuery`, `FabricCablingPlanQuery`). Following both
conventions costs one line of ConfigMap. Constitution principle V asks for exactly this, and the
operator made the name configurable so that it could be followed.

**Alternatives considered**: registering as `ArtifactIDs` to match the operator's default
(rejected — it would be the only PascalCase name in `.infrahub.yml`, for no gain).

## 8. Installation method and image

**Decision**: install the operator's Helm chart from the project's chart repository
(`https://infrahub-operator.github.io/vidra`, `index.yaml` returns 200), with the image overridden
to `registry.opsmill.io/opsmill/vidra:v0.0.6-opsmill2` as supplied. The chart's own default is
`ghcr.io/infrahub-operator/vidra:v0.0.6`.

**Verified**: `docker pull registry.opsmill.io/opsmill/vidra:v0.0.6-opsmill2` succeeds without
credentials (digest `sha256:d137c2f9…`), and the k3s nodes have working egress and DNS for
`registry.opsmill.io` — they already carry images pulled from quay.io, ghcr.io and docker.io.

**Alternatives considered**: `kubectl apply -k config/default` from the upstream repository
(rejected — pins nothing and makes the image override a patch file); vendoring the chart (rejected
— nothing to change in it).

## 9. Where the deployment assets live

**Decision**: a new top-level `vidra/` directory in this repository.

**Rationale**: the sync declarations name Infrahub artifacts by name and branch, so they belong
beside the artifact definitions that produce them — a change to one is a change to the other.

**`lab/` is the wrong home and it is worth saying why**: this repository's `lab/` is the
`infrahub-avd` ContainerLab topology, which its own README marks **stale** — it models the
example design this fork removed. The cluster this feature delivers into belongs to the *separate*
NFD41 lab repository (`nfd41.clab.yml`). Filing cluster assets under the stale lab would put them
next to the one topology they have nothing to do with.

**Cost, stated**: `vidra/` is a directory `AGENTS.md`'s repository-layout section does not list,
so that section must be updated in the same change. That is the whole of the deviation.

## 10. Sync cadence

**Decision**: `requeueSyncAfter: 1m`, `requeueResourcesAfter: 10m`, set in the `vidra-config`
ConfigMap (labelled `app: vidra`, which is how the operator finds it).

**Rationale**: SC-001 asks for five minutes or better; one minute makes a demonstration watchable
without polling Infrahub hard — one stored-query call per sync, and a download only when the
checksum moved. Resource reconciliation is the drift check of story 2 and is cheaper to do less
often.

**Alternatives considered**: `eventBasedReconcile: "true"` (rejected — it keys off Kubernetes
events, not Infrahub ones, so it does nothing for merge latency and disables the timed requeue
that story 1 depends on).

---

## Addendum: what implementation found that research got wrong

Four findings from actually running the thing. Two of them contradict decisions above, and one
cancelled a task.

### A1. The operator adopts. It does not refuse. (Contradicts §4)

§4 predicted the first sync would fail against the two pre-existing resources, and the cycle was
planned around deleting them — accepting an outage — so the operator could create them itself.

**It adopted both, in place, with no error and no recreation.**

```text
fabricapp.nfd41.lab/nfd41-demo    labels={"managed-by":"vidra"}  created=2026-09-10T08:43:14Z
fabricpeering.nfd41.lab/nfd41     labels={"managed-by":"vidra"}  created=2026-09-10T08:43:11Z
```

The `creationTimestamp` values are the originals, four days old. The demo workload never went
down — `frontend` and `backend` stayed at 4d7h uptime across the cut-over — and both specs came
through byte-identical to the pre-delivery baseline.

The guard is real but never fires on this path:

```go
if existing.GetAnnotations()["managed-by"] != vidraOperator && res.Status.LastSyncTime.IsZero() {
```

`LastSyncTime` is already stamped on the `VidraResource` by the sync controller before the
resource controller applies, so `IsZero()` is false on the very first apply. The guard only
protects a `VidraResource` that has never synced at all — which, in the sync-driven flow, is
never. **T017 was therefore not executed**: its entire justification was an adoption refusal that
does not happen, and running it would have caused the outage it was meant to be the price of.

The lesson for next time: reading a guard's condition is not the same as knowing when it is
evaluated.

### A2. The ConfigMap is read once, at startup

`InitConfigWithClient` runs at boot, not per reconcile. Creating the ConfigMap after `helm
install` — the order §8 and the first draft of the quickstart implied — leaves the operator on its
built-in defaults, including `queryName: ArtifactIDs`, which this repository does not register:

```text
ERROR  Failed to execute query  {"error": "query failed with status 404 Not Found: "}
```

Both syncs failed this way until the deployment was restarted, after which they reached
`Succeeded` within one interval. **The ConfigMap and Secret must exist before the chart is
installed**, and any later change to either needs a `rollout restart`. The install order in
[quickstart.md](./quickstart.md) and the documentation page were corrected.

### A3. The OpsMill image expects a CRD the upstream chart does not ship — and it is fatal

`registry.opsmill.io/opsmill/vidra:v0.0.6-opsmill2` runs a third controller for an
`InfrahubWriteBack` kind. The upstream `vidra-operator` 0.0.6 chart — the only published one —
installs `infrahubsyncs` and `vidraresources` and nothing else, and the kind appears nowhere in
the public repository or in GitHub code search. It is an OpsMill-only addition, and the image and
the chart are out of step.

**This was first written up here as harmless log noise. That was wrong, and the way it was wrong
is worth recording.** The controllers do start, the syncs do reach `Succeeded`, and delivery does
work — so a stack trace repeating in the logs looks like something to file and move past. What it
actually is:

```text
ERROR  setup  problem running manager  {"error": "failed to wait for infrahubwriteback caches to
       sync kind source: *v1alpha1.InfrahubWriteBack: timed out waiting for cache to be synced"}
```

The informer cannot build a cache for a kind the API server does not know. After roughly two
minutes, the manager gives up and the process exits. The pod restarts, works for two minutes, and
exits again — five restarts in the first nineteen minutes. Every observation made before this was
found is therefore suspect, because **each restart re-reconciles everything**: the system looked
healthy precisely because it was being rebooted often enough to hide the gaps.

It was found only by asking why `lastSyncTime` had stopped advancing, and the answer was in
`kubectl get pod`, not in the logs the failure was writing.

**Workaround, in `vidra/writeback-crd-shim.yaml`**: register the kind with a permissive schema
(`x-kubernetes-preserve-unknown-fields`, since the real schema is unknown and guessing one would
reject objects the real controller accepts) plus a ClusterRole, because the chart's manager role
predates the kind and cannot list or watch it either. No `InfrahubWriteBack` object is ever
created, so the controller idles.

Verified: zero restarts across a continuous run well past the two-minute mark that previously
killed it.

**The clean fix is an OpsMill chart matching the image.** The shim is an apology for a version
skew, and its file says to delete it when one exists.

### A4. Drift correction, measured twice — and why the first numbers were fiction

The first measurements were taken against the crash-looping operator of §A3, so they measured
**restart frequency**, not reconcile cadence: a hand-edited field reverted in 1m45s and a deleted
resource returned in 3m28s, both because the pod happened to restart and re-reconcile everything.
Neither number described the configured behaviour, and both would have gone into the documentation
as fact.

Repeated against the stabilised operator, with `restarts=0` throughout, the same hand edit took
**437 seconds** — 7m17s, consistent with a 10-minute `requeueResourcesAfter` and a patch landing
part-way through an interval. That is the number to plan against: it is four times the first
measurement, and the difference is the whole value of re-running it.

What holds regardless of which operator was running:

| Drift | Corrected by | Not corrected by |
| --- | --- | --- |
| A field edited by hand | the `VidraResource` reconcile | the sync interval |
| A delivered resource deleted | the `VidraResource` reconcile | the sync interval |

The 1-minute sync does **not** correct drift. The sync controller compares the artifact checksum,
finds it unchanged, and skips the apply entirely — which is exactly what makes an unchanged merge
free, and exactly why it cannot notice that the cluster has moved underneath it. A sync can
therefore report `Succeeded`, with checksums matching Infrahub, while the delivered resource is
**absent**: the checksum describes the artifact, not the cluster.

Deleting a delivered resource is the same mechanism with a much bigger blast radius. Crossplane
tears down the composed Objects behind the composite, so the demo workload went down and stayed
down until the reconcile restored it — after which it came back complete, same VIP, 3/3 and 2/2.
