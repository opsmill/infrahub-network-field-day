---
title: Vidra delivery
description: How a merge in Infrahub becomes Kubernetes state — deploying the Vidra operator, wiring its credentials, reading sync state, and diagnosing a merge that does not arrive.
audience: developer
sidebar_position: 6
---

The Crossplane transforms render `FabricApp` and `FabricPeering` custom resources, and until
this path existed those manifests never left Infrahub. Somebody downloaded an artifact and ran
`kubectl apply`. [Vidra](https://github.com/opsmill/vidra) is a Kubernetes operator that closes
that gap: it polls an artifact's checksum on a branch and applies the manifest when the checksum
moves.

Because it is pinned to `main`, the trigger is a **merge**. Work on a feature branch regenerates
that branch's artifacts, and they go nowhere.

## How the loop works

```text
merge into main
      │   Infrahub regenerates every artifact definition on the target branch
      ▼
artifact re-rendered      checksum moves only if the rendered bytes moved
      ▼
InfrahubSync polls POST /api/query/artifact_ids   ── unchanged ──▶ nothing happens
      │  checksum differs
      ▼
GET /api/artifact/{id}?branch=main
      ▼
VidraResource holds the manifest
      ▼
manifest applied ──▶ Crossplane reconciles the composite
```

Nothing in this repository schedules the regeneration. Infrahub's own
`branch-merge-post-process` flow triggers artifact generation for the target branch after every
merge, which is why no trigger definition was added.

## What is delivered, and what is not

| Resource | Owner | Why |
| --- | --- | --- |
| `fabricapp.otternet.lab/otternet-demo` | Infrahub | Modelled as a `ServiceFabricApp` in the `service_fabric_apps` group |
| `fabricpeering.otternet.lab/otternet` | Infrahub | Modelled as a `ServiceFabricPeering` |
| `fabricapp.otternet.lab/otternet-metrics` | Infrahub | Grafana and Prometheus, a seeded `ServiceFabricApp` (see [Observability](./observability.md)) |
| `fabricapp.otternet.lab/otternet-telemetry` | Infrahub | Telegraf, a seeded `ServiceFabricApp` |
| `configmap/telegraf-intent` in `otternet-telemetry` | Infrahub | The `Telemetry Collector Configuration` artifact, through a third sync whose destination namespace is Telegraf's own |

An application joins delivery by joining the target group. No cluster-side change is needed —
a sync selects by artifact **name**, so it already covers every member of the group.

**Those are the whole list, and that is enforced rather than assumed.** The lab's
bootstrap also applies `otternet-access`, which nothing in Infrahub models, and would apply
`otternet-observability`. `invoke cluster` sets `OTTERNET_SKIP_OBSERVABILITY` so that one is never
applied: two kube-prometheus-stack releases contend for the same CRDs. The handover deletes the
access broker along with the lab's copies of the demo and the peering, so a finished cluster carries
only applications a service object declares — a workload no proposed change can account for is
exactly what this delivery path exists to rule out. `scripts/verify_bootstrap.sh` checks their
absence and counts the applications, so a third one arriving from elsewhere fails too.

:::warning Two files in the lab are now dead
`crossplane/apps/10-demo.yaml` and `crossplane/platform/10-peering.yaml` declare the same two
resources Infrahub now owns. Re-applying either restores a second writer, and the two then fight over the resource.
:::

The operator only ever deletes a resource that leaves a manifest **it delivered**, so it plays no
part in removing the unmodelled applications — the handover deletes those directly, and Vidra
never sees them.

## Deploying the operator

Everything committed lives in `vidra/`. The one thing that is not committed is the credential.

**Create the namespace, the ConfigMap and the Secret before installing the chart.** The
operator reads its configuration once, at startup — see the warning below.

```bash
helm repo add vidra https://infrahub-operator.github.io/vidra && helm repo update
kubectl create namespace vidra-system

kubectl apply -f vidra/vidra-config.yaml
kubectl -n vidra-system create secret generic infrahub-credentials \
  --from-literal=username="$INFRAHUB_USERNAME" \
  --from-literal=password="$INFRAHUB_PASSWORD"
kubectl -n vidra-system label secret infrahub-credentials infrahub-api-url=172.20.41.1

kubectl apply -f vidra/writeback-crd-shim.yaml
helm install vidra vidra/vidra-operator -n vidra-system -f vidra/helm-values.yaml
kubectl apply -f vidra/infrahub-syncs.yaml
```

:::danger The shim is load-bearing — without it the operator crash-loops
The pinned image runs a third controller for an `InfrahubWriteBack` kind that the upstream 0.0.6
chart does not install. Its informer cannot build a cache for a kind the API server does not know,
so after about two minutes the manager exits:

```text
problem running manager {"error": "failed to wait for infrahubwriteback caches to sync ..."}
```

The pod then restarts, works for two minutes, and exits again. **Delivery appears to work**,
because each restart re-reconciles everything — which is what makes this worth stating plainly
rather than filing as log noise. `vidra/writeback-crd-shim.yaml` registers the kind and grants the
ServiceAccount access to it. No object of that kind is ever created.

Delete the shim when OpsMill publishes a chart matching the image.
:::

:::warning The ConfigMap is read at startup, not per sync
`InitConfigWithClient` runs once when the operator boots. Apply the ConfigMap afterwards and the
operator keeps its defaults — including `queryName: ArtifactIDs`, which this repository does not
register, giving `query failed with status 404 Not Found` on every sync.

After any change to `vidra-config.yaml`:

```bash
kubectl -n vidra-system rollout restart deploy/vidra-vidra-operator-controller-manager
```

:::

:::danger Two ways to get the Secret wrong, both silent
**The label value is the bare host — no scheme, no port.** The operator derives it from the API
URL by taking everything between `://` and the port, so `http://172.20.41.1:8000` becomes
`172.20.41.1`. It has to work this way: a colon is not a legal character in a Kubernetes label
value. Include the port and the operator reports `no secret found with InfrahubAPIURL`.

**These are a username and password, not an API token.** The operator exchanges them at
`/api/auth/login`. An `INFRAHUB_API_TOKEN`-shaped Secret does not authenticate.
:::

`vidra/infrahub-credentials.example.yaml` records the shape. It is an example and is never
applied.

### Configuration

`vidra/vidra-config.yaml` is found by its `app: vidra` label, not by its name, or its namespace.

| Key | Value | Meaning |
| --- | --- | --- |
| `queryName` | `artifact_ids` | Points the operator at this repository's registered query. Its own default is `ArtifactIDs`. |
| `requeueSyncAfter` | `1m` | How long a merge takes to reach the cluster. |
| `requeueResourcesAfter` | `10m` | How long drift survives before being reverted — an edited field or a deleted resource. This is the real bound; the sync interval does not correct drift. |
| `eventBasedReconcile` | `false` | Keys off Kubernetes events, not Infrahub ones, and disables the timed requeue. Leave it off. |

## Reading the state

```bash
kubectl get infrahubsync
kubectl get infrahubsync -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.syncState}{"\t"}{.status.lastSyncTime}{"\t"}{.status.lastError}{"\n"}{end}'
```

| Field | What it answers |
| --- | --- |
| `syncState` | `Pending`, `Running`, `Succeeded`, `Failed`, `Stale` |
| `checksums` | Which artifact versions the cluster is carrying. Compare against Infrahub to answer "is it current?" directly |
| `lastSyncTime` | Freshness — within one sync interval, or something is wrong |
| `lastError` | Why, when `syncState` is `Failed` |

To see what a delivered manifest produced, read the `VidraResource` the operator created:

```bash
kubectl get vidraresource -o custom-columns=NAME:.metadata.name,STATE:.status.DeployState
kubectl get vidraresource <name> -o jsonpath='{.status.managedResources}'
```

A `Failed` sync leaves what is already delivered in place. An unreachable Infrahub or an expired
credential degrades to stale-but-serving, never to an empty cluster.

:::warning `Succeeded` does not mean the resource exists
The sync compares the artifact's **checksum**. Unchanged means it skips the download and the apply
entirely — which is what makes an unchanged merge free, and also why a sync can sit at `Succeeded`,
checksums matching Infrahub, while the delivered resource has been deleted out from under it.

Drift of any kind is corrected by the `VidraResource` reconcile, on `requeueResourcesAfter`,
**not** by the sync. Check the resource, not just the sync.
:::

## When a merge does not arrive

| Symptom | Cause |
| --- | --- |
| `syncState: Succeeded`, nothing delivered | `artefactName` does not match `artifact_name` in `.infrahub.yml`. **An empty result set is a success** — this is the failure that looks most like health |
| `no secret found with InfrahubAPIURL` | The label value carries the scheme or the port. It is the bare host |
| `already exists but is not managed by this operator` | A resource exists that the operator did not create. It refuses to adopt on its first sync — delete the resource, or a dead lab file was re-applied |
| The query returns nothing | Not imported, or registered under a name other than `queryName` |
| `query failed with status 404 Not Found` | The operator is calling a query name that is not registered — almost always the ConfigMap was applied after the operator started. Restart it |
| `Failed to list InfrahubWriteBack resources` | Harmless. The OpsMill image carries a third controller whose CRD the upstream 0.0.6 chart does not ship. The sync and resource controllers start normally |
| Connection refused reaching Infrahub | `localhost` was used. Inside a node, that is the node — use the management gateway address |
| The artifact never changes | Check the checksum in Infrahub first. If it did not move, the merge changed nothing either renderer reads, and the cluster is correct to ignore it |

Start at the Infrahub end. Confirm the artifact's checksum actually moved before looking at the
cluster — half the time the answer is that the model change was real but nothing rendered from it.

## The Kubernetes half and who owns which resource

Moved from the repository instruction file: the install order, the handover and the failure modes.

```bash
uv run invoke cluster      # Cilium, then Vidra, then Crossplane, then the handover
uv run invoke vidra        # the operator on its own, for a re-install
```

`invoke cluster` runs the **lab's** installers for the CNI and
Crossplane rather than reimplementing them — those are the lab's, the same way
the topology is. Cilium has to be first and cannot be managed by Crossplane: it
*is* the pod network, so a controller needing a pod network cannot be what
creates one. The k3s nodes sit `NotReady` until it lands; that is expected, not
a fault.

**Vidra goes up second, before the platform it delivers into.** Its syncs fail
while the XRDs are absent and retry every `requeueSyncAfter`, so the ordering
costs nothing — and it buys the thing that matters: the resources Infrahub
models are created by Vidra first-hand rather than adopted from another writer.
Three measured behaviours are why that is worth arranging:

- **It refuses to adopt a resource it did not create** (`already exists but is
  not managed by this operator`), so whichever writer gets there first keeps it.
- **A resource deleted after a successful sync stays missing for up to
  `requeueResourcesAfter` — ten minutes — while the sync reports `Succeeded`
  throughout.** An unchanged checksum skips the download and the apply, so the
  sync never notices the resource is gone. Verified by deleting a delivered
  `FabricPeering` and its CRD: both the sync and the `VidraResource` read
  `Succeeded` for two minutes with nothing in the cluster.
- **Deleting the `VidraResource` does not cause redelivery at all.** The sync
  still considers itself current, and there is no longer a resource to
  reconcile, so it wedges silently. Recovery is to delete and re-apply the
  `InfrahubSync`, which resets its checksum state — the peering came back
  within 15 seconds of doing so.
- **You cannot delete a resource Vidra owns; it puts it back.** That is drift
  correction working as intended, but it means cleanup has to delete the
  `InfrahubSync` first. Deleting the claim while the sync is live restores it
  mid-teardown, and the new composed resources then collide with a namespace
  still `Terminating` — which leaves two composed `Namespace` objects and a
  `FabricApp` stuck `Ready=False`.

**The handover is the remaining seam.** The lab's bootstrap applies four claims —
`crossplane/platform/10-peering.yaml`, `crossplane/apps/10-demo.yaml`,
`crossplane/apps/20-observability.yaml` and `crossplane/access/10-access-portal.yaml`
— and its script has no flag to skip any of them. `invoke cluster` deletes **all
four** afterwards, and what happens next divides them:

| Resource | Owner | After the handover |
| --- | --- | --- |
| `fabricpeering.otternet.lab/otternet` | **Infrahub**, via `ServiceFabricPeering` | re-delivered by Vidra |
| `fabricapp.otternet.lab/otternet-demo` | **Infrahub**, via `ServiceFabricApp` | re-delivered by Vidra |
| `fabricapp.otternet.lab/otternet-observability` | the lab (`lab/`) | gone |
| `fabricapp.otternet.lab/otternet-access` | the lab (`lab/`) | gone |

**The bottom two are deleted because nothing models them.** A cluster carrying a
workload no service object declares is state no proposed change can explain, which
is the opposite of the claim this lab makes; the access broker and the
observability stack both predate the service layer that now requests applications.
`verify_bootstrap.sh` asserts their absence **and** counts the applications, because
two absence checks say nothing about a third application arriving from somewhere
else. `tests/unit/test_handover_scope.py` is the cheap version of the same claim:
it parses the lab installer's own `kubectl apply` lines and fails when it applies
a claim `HANDOVER_DELETIONS` does not name, so a lab that adds an application is
caught in a second rather than at the end of a twenty-minute rebuild. Pass `--no-handover` to keep the lab in charge of all four; Vidra will then
never adopt its two, and the other two stay up.

The delete is `--wait=false` and a poll afterwards rather than four blocking
deletes: a claim's finalizer holds the delete open until Crossplane has torn its
composed resources down, and kube-prometheus-stack takes minutes. `_wait_for_teardown`
waits for the same condition, so the four go in parallel.

The handover then **deletes and re-applies `vidra/infrahub-syncs.yaml`**, which is
not optional. Deleting a delivered resource does not move the artifact's checksum,
so the next sync skips the apply, reports `Succeeded`, and leaves the cluster
without it. Recreating the sync resets its checksum state and delivery follows in
seconds. This was measured twice: first by deleting a resource by hand, then by
`invoke cluster` itself walking into it before the reset was added.

The wait afterwards checks **the resources**, not `syncState`, for the same
reason — a wait on the sync state returns happily from a cluster where nothing
was delivered.

`scripts/install_vidra.sh` follows the order the
operator requires: namespace, ConfigMap, Secret and the CRD shim **before** the
chart, because `InitConfigWithClient` reads the configuration once at startup.
Install the chart first and the operator keeps `queryName: ArtifactIDs`, which
this repository does not register, and every sync returns
`query failed with status 404 Not Found`.

Three failure modes worth knowing before debugging a merge that does not arrive:

- **`syncState: Succeeded` is not evidence anything arrived.** The sync compares
  a checksum, and an `artefactName` that does not match `.infrahub.yml` exactly
  returns an empty set — which succeeds. Check the `VidraResource` count, which
  is what `invoke vidra` prints alongside the sync state.
- **The Secret's label is the bare host**, no scheme and no port, because a colon
  is not legal in a label value. `http://172.20.41.1:8000` becomes
  `172.20.41.1`. Get it wrong and the operator reports `no secret found`, having
  looked straight past an otherwise perfect Secret.
- **Those are a username and password, not an API token.** The operator exchanges
  them at `POST /api/auth/login`; an `INFRAHUB_API_TOKEN`-shaped Secret does not
  authenticate.

See [Vidra delivery](./vidra-delivery.md)
for the full loop and its diagnostics.
