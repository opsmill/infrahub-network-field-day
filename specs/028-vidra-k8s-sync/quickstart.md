# Quickstart: Vidra Kubernetes Delivery

**Feature**: `028-vidra-k8s-sync` | **Date**: 2026-09-14

How to stand the delivery loop up and prove it works. Each scenario maps to a success criterion in
[spec.md](./spec.md); object shapes are in [contracts/](./contracts/) and are not repeated here.

## Prerequisites

| Requirement | Check | Expected |
| --- | --- | --- |
| Infrahub running | `uv run infrahubctl info` | Connection Status ✅, 1.10.6 |
| Both artifacts present on `main` | GraphQL `CoreArtifact(name__values: [...])` | `count: 2`, status `Ready` |
| Lab cluster up | `docker ps --filter name=clab-nfd41-k8s-node` | three `rancher/k3s` containers |
| Crossplane and the XRDs installed | `kubectl get crd fabricapps.nfd41.lab fabricpeerings.nfd41.lab` | both present |
| `kubectl` and `helm` on PATH | `which kubectl helm` | both found |

The cluster belongs to the **separate NFD41 lab repository**, not this one. This feature installs
nothing of Crossplane's; if the XRDs are missing, the lab's own bootstrap is what creates them.

## Setup

### 1. Point kubectl at the lab cluster

The k3s kubeconfig already names a routable address (`https://172.20.41.41:6443`), reachable from
this host:

```bash
docker exec clab-nfd41-k8s-node1 cat /etc/rancher/k3s/k3s.yaml > /tmp/nfd41-k3s.yaml
export KUBECONFIG=/tmp/nfd41-k3s.yaml
kubectl get nodes          # three nodes, all Ready
```

### 2. Register the query and let Infrahub import it

```bash
uv run infrahubctl object load repository.yml      # or wait for the repo to re-sync
```

Confirm the query is callable by the name the operator will use:

```bash
TOK=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"infrahub"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST "http://localhost:8000/api/query/artifact_ids?branch=main" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"variables":{"artifactname":["Crossplane FabricApp","Crossplane FabricPeering"]}}' | python3 -m json.tool
```

Expect two nodes back, each with an `id` and a `checksum`. **If this returns an empty list the
whole feature is inert** — nothing downstream will report an error, so do not continue past it.

### 3. Configuration and credentials — **before** the operator starts

The operator reads its ConfigMap **once, at boot** (`InitConfigWithClient`). Apply it afterwards
and it keeps `queryName: ArtifactIDs`, which this repository does not register, and every sync
fails with `query failed with status 404 Not Found`. This cost a restart during implementation;
done in this order it costs nothing.

```bash
kubectl create namespace vidra-system
kubectl apply -f vidra/vidra-config.yaml

kubectl -n vidra-system create secret generic infrahub-credentials \
  --from-literal=username=admin --from-literal=password=infrahub
kubectl -n vidra-system label secret infrahub-credentials infrahub-api-url=172.20.41.1
```

The Secret's label value is the host **without scheme or port** — shape and reasoning in
[contracts/infrahub-credentials.example.yaml](./contracts/infrahub-credentials.example.yaml).

### 4. Install the operator

```bash
helm repo add vidra https://infrahub-operator.github.io/vidra && helm repo update
helm install vidra vidra/vidra-operator -n vidra-system -f vidra/helm-values.yaml
kubectl -n vidra-system rollout status deploy/vidra-vidra-operator-controller-manager
```

Expect a repeating `Failed to list InfrahubWriteBack resources` stack trace in the logs. The
OpsMill image runs a third controller whose CRD the upstream 0.0.6 chart does not ship. It is
noise: `infrahubsync` and `vidraresource` both start workers and work normally.

After any later change to the ConfigMap:

```bash
kubectl -n vidra-system rollout restart deploy/vidra-vidra-operator-controller-manager
```

### 5. Apply the syncs

```bash
kubectl apply -f vidra/infrahub-syncs.yaml
```

**Nothing needs deleting first.** An earlier draft deleted the two resources the lab bootstrap
applied, believing the operator refuses to adopt what it did not create. It adopts them in place:
both kept their original `creationTimestamp` and the demo workload stayed up throughout. See
[research.md](./research.md) §A1.

> Once delivery is live, `crossplane/apps/10-demo.yaml` and `crossplane/platform/10-peering.yaml`
> in the lab repository are **dead files**. Re-applying either restores a second writer for a
> resource Infrahub now owns.

## Validation scenarios

### SC-004 — both artifact kinds deliver

```bash
kubectl get infrahubsync
kubectl get fabricapp.nfd41.lab,fabricpeering.nfd41.lab
```

Expect both syncs `Succeeded`, and `nfd41-demo` and `nfd41` recreated and reaching
`SYNCED=True READY=True`. The two unmodelled apps (`nfd41-access`, `nfd41-observability`) must
still be present and untouched — the operator never sees resources it did not deliver.

### SC-001 — a merge reaches the cluster

```bash
uv run infrahubctl branch create vidra-proof
# change one rendered field of the ServiceFabricApp on that branch, then merge the proposed change
kubectl get infrahubsync crossplane-fabric-app -o jsonpath='{.status.checksums} {.status.lastSyncTime}{"\n"}'
kubectl get fabricapp.nfd41.lab/nfd41-demo -o yaml | grep -A3 'the field you changed'
```

The checksum must move and the cluster must carry the new value, with no manual command between
the merge and the change. Pick a field the transform actually renders — a description the
renderer ignores will correctly produce nothing, which is SC-002, not a failure.

### SC-002 — an irrelevant change changes nothing

Merge a change to a field neither renderer reads. The artifact re-renders to the same checksum and
the cluster resource's `resourceVersion` must not move across a full sync interval.

### SC-005 — an unmerged branch changes nothing

Make the same edit on a branch and **do not merge**. Over at least one full sync interval the
cluster must not move. This is the property that makes "on merge" mean something.

### SC-003 — drift is corrected

```bash
kubectl patch fabricapp.nfd41.lab/nfd41-demo --type=merge -p '{"spec":{"tenant":"wrong"}}'
```

The value returns to what the artifact declares, with no Infrahub-side change. **Do not expect it
within the sync interval**: the sync path compares the artifact checksum, finds it unchanged and
skips the apply entirely, so drift is corrected only by the `VidraResource` reconcile. Measured at **437 seconds** for a hand
edit against a stable operator — consistent with `requeueResourcesAfter: 10m` and a patch landing
part-way through an interval, not with the 1-minute sync.

Deleting a delivered resource is the same story with a bigger blast radius: Crossplane tears down
the composed Objects, and the workload is down until the reconcile restores it.

### SC-006 — failures are visible, and never destructive

Break the credential (`kubectl -n vidra-system delete secret infrahub-credentials`) and wait a
sync interval:

```bash
kubectl get infrahubsync -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.syncState}{"\t"}{.status.lastError}{"\n"}{end}'
```

`syncState` must read `Failed` with a reason, and **the delivered resources must still be there**.
Restore the Secret and confirm recovery without intervention.

### SC-008 — nothing upstream was disturbed

```bash
uv run pytest tests/unit
uv run invoke lint
git diff --stat main -- transforms/
```

The transform diff must be empty: this cycle adds delivery without touching rendering.

### SC-009 — the loop survives a rebuild

Delete the operator's namespace and the syncs, then repeat Setup from step 3 using only what is
committed. The loop must come back with no undocumented step.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Sync `Succeeded`, nothing delivered | `artefactName` does not match `artifact_name` in `.infrahub.yml`. Empty result sets are a success. |
| "no secret found with InfrahubAPIURL" | Label value carries the scheme or the port. It is the bare host: `172.20.41.1`. |
| `query failed with status 404 Not Found` | The ConfigMap was applied after the operator started, so `queryName` is still the default. Restart the deployment. |
| A sync reports `Succeeded` but the resource is gone | Checksum equality describes the *artifact*, not the cluster. Deletion is healed by the `VidraResource` reconcile, not the sync. |
| Query returns nothing | Query not imported, or registered under a different name than `queryName`. |
| Connection refused to Infrahub | `localhost` used instead of `172.20.41.1` — inside the node, `localhost` is the node. |
