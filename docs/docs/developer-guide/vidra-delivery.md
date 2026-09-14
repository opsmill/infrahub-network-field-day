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
| `fabricapp.nfd41.lab/nfd41-demo` | Infrahub | Modelled as a `ServiceFabricApp` in the `service_fabric_apps` group |
| `fabricpeering.nfd41.lab/nfd41` | Infrahub | Modelled as a `ServiceFabricPeering` |
| `fabricapp.nfd41.lab/nfd41-access` | the lab repository | Not modelled |
| `fabricapp.nfd41.lab/nfd41-observability` | the lab repository | Not modelled |

An application joins delivery by joining the target group. No cluster-side change is needed —
a sync selects by artifact **name**, so it already covers every member of the group.

:::warning Two files in the lab repository are now dead
`crossplane/apps/10-demo.yaml` and `crossplane/platform/10-peering.yaml` declare the same two
resources Infrahub now owns. Re-applying either restores a second writer, and the two then fight over the resource.
`10-access.yaml` and `20-observability.yaml` are unaffected and remain the lab's.
:::

The operator only ever deletes a resource that leaves a manifest **it delivered**. Resources it
never created are invisible to it, which is what keeps the two unmodelled applications safe.

## Deploying the operator

Everything committed lives in `vidra/`. The one thing that is not committed is the credential.

```bash
helm repo add vidra https://infrahub-operator.github.io/vidra && helm repo update
kubectl create namespace vidra-system
helm install vidra vidra/vidra-operator -n vidra-system -f vidra/helm-values.yaml
```

Then the credential Secret, and the configuration:

```bash
kubectl -n vidra-system create secret generic infrahub-credentials \
  --from-literal=username="$INFRAHUB_USERNAME" \
  --from-literal=password="$INFRAHUB_PASSWORD"
kubectl -n vidra-system label secret infrahub-credentials infrahub-api-url=172.20.41.1

kubectl apply -f vidra/vidra-config.yaml
kubectl apply -f vidra/infrahub-syncs.yaml
```

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
| `requeueResourcesAfter` | `10m` | How long a hand edit survives before being reverted. |
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

## When a merge does not arrive

| Symptom | Cause |
| --- | --- |
| `syncState: Succeeded`, nothing delivered | `artefactName` does not match `artifact_name` in `.infrahub.yml`. **An empty result set is a success** — this is the failure that looks most like health |
| `no secret found with InfrahubAPIURL` | The label value carries the scheme or the port. It is the bare host |
| `already exists but is not managed by this operator` | A resource exists that the operator did not create. It refuses to adopt on its first sync — delete the resource, or a dead lab file was re-applied |
| The query returns nothing | Not imported, or registered under a name other than `queryName` |
| Connection refused reaching Infrahub | `localhost` was used. Inside a node, that is the node — use the management gateway address |
| The artifact never changes | Check the checksum in Infrahub first. If it did not move, the merge changed nothing either renderer reads, and the cluster is correct to ignore it |

Start at the Infrahub end. Confirm the artifact's checksum actually moved before looking at the
cluster — half the time the answer is that the model change was real but nothing rendered from it.
