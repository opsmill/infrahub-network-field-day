# Phase 1 Data Model: Crossplane FabricPeering Manifest

**Feature**: `specs/011-crossplane-manifest-transform` | **Date**: 2026-09-10

This transform creates no schema. Its "data model" is the **render mapping**: which graph
field becomes which manifest field, and what happens on the way. Values below are the
ones actually loaded, verified against the live graph.

## 1. Sources

Three kinds, reached in one traversal from the artifact target.

| Kind | Role | Why it is read |
| --- | --- | --- |
| `ServiceFabricPeering` | the artifact target | Supplies the artifact's identity; contributes `communities` and `advertisement_selector`. Does **not** supply `metadata.name` — see below |
| `ClusterKubernetes` | the substance | Every other rendered value: local ASN, secret name, timers, pod-CIDR communities, both selectors |
| `ClusterFabricPeering` | one per fabric leaf | Each peer's name, ASN and address |

## 2. Field-by-field mapping

`spec.*` paths are on the rendered `FabricPeering` resource, per the lab's XRD at
`../lab/crossplane/platform/00-xrd-fabric-peering.yaml`.

| Manifest field | Source | Transformation | Loaded value |
| --- | --- | --- | --- |
| `apiVersion` | *constant* | `nfd41.lab/v1alpha1` | — |
| `kind` | *constant* | `FabricPeering` | — |
| `metadata.name` | `ClusterKubernetes.name` | verbatim | `nfd41` |
| `spec.localASN` | `ClusterKubernetes.local_asn` | verbatim, **mandatory** | `65401` |
| `spec.authSecretName` | `ClusterKubernetes.bgp_auth_secret_name` | verbatim; omit if unset | `nfd41-bgp-auth` |
| `spec.nodeSelector` | `ClusterKubernetes.node_selector` | **parse `key=value` → map** | `{nfd41.lab/bgp: "true"}` |
| `spec.advertisementSelector` | `ServiceFabricPeering.advertisement_selector`, falling back to the cluster's | **parse `key=value` → map** | `{nfd41.lab/advertise: fabric}` |
| `spec.podCIDRCommunities` | `ClusterKubernetes.pod_cidr_communities` | verbatim list; omit if empty | `["65401:110"]` |
| `spec.timers.connectRetrySeconds` | `ClusterKubernetes.bgp_timers` | pass through by key | `5` |
| `spec.timers.holdTimeSeconds` | `ClusterKubernetes.bgp_timers` | pass through by key | `9` |
| `spec.timers.keepAliveSeconds` | `ClusterKubernetes.bgp_timers` | pass through by key | `3` |
| `spec.peers[].name` | `ClusterFabricPeering.name` | verbatim | `k8s-leaf1`, `k8s-leaf2` |
| `spec.peers[].address` | `ClusterFabricPeering.peer_address` → `IpamIPAddress.address` | **strip the prefix length** | `10.110.0.2`, `10.110.0.3` |
| `spec.peers[].asn` | `ClusterFabricPeering.peer_asn` | verbatim | `65101` |

### Not rendered, deliberately

| Graph field | Why not |
| --- | --- |
| `ClusterFabricPeering.peer_device` | The manifest addresses a neighbour by IP. The device relationship exists to make the address a real object on a real leaf, and to let a check confirm the two halves agree — it is not manifest content |
| `ClusterFabricPeering.svi`, `peer_neighbor` | The fabric side of the session. AVD renders those; this renders the cluster side |
| `ClusterKubernetes.pod_prefix`, `service_prefix`, `node_prefix`, `vip_pools`, `vrf` | Consumed by the `FabricApp` manifest and the leaves' route policy, not by `FabricPeering` |
| `ClusterKubernetes.nodes` | Membership; the CNI selects speakers by label, which is what `nodeSelector` carries |
| `ServiceFabricPeering.status`, `owner`, `checksum` | Infrahub-side lifecycle and ownership. R10: status does not gate rendering |
| any secret **value** | FR-019 and SC-007. Only `authSecretName` — the name — is rendered |

## 3. The two transformations

Everything else is a copy. These two are the transform's only real work.

### Selector parsing

Storage is a `List` of `key=value` strings; the manifest wants a map. Split on the
**first** `=` only, because a label value may legitimately contain one.

```text
"nfd41.lab/bgp=true"            -> {"nfd41.lab/bgp": "true"}
"nfd41.lab/advertise=fabric"    -> {"nfd41.lab/advertise": "fabric"}
"nfd41.lab/x=a=b"               -> {"nfd41.lab/x": "a=b"}
"nfd41.lab/bgp"                 -> raise: no "=" in selector entry
```

The storage shape is a workaround, not a preference: Infrahub 1.10.6 returns a 500 for a
JSON attribute key containing a dot or a slash (`schemas/MARKETPLACE.md`). Values render
quoted where the manifest needs them quoted — `"true"` is a label value, not a boolean.

### Address stripping

`peer_address` resolves to an `IpamIPAddress`, whose value carries the mask. A BGP
neighbour address must not.

```text
"10.110.0.2/24"  ->  "10.110.0.2"
```

## 4. Validation rules

Drawn from FR-013 and FR-017, all enforced before the manifest dict is built.

| # | Rule | On failure |
| --- | --- | --- |
| V-1 | The cluster has a `local_asn` | raise, naming the cluster and the field — a session with no local AS cannot come up |
| V-2 | The service has at least one **enabled** peering | raise — an empty `peers` list yields a resource that applies cleanly and carries nothing |
| V-3 | Every rendered peering has a `peer_address` | raise, naming the peering |
| V-4 | Every selector entry contains `=` | raise, naming the entry |
| V-5 | No secret value is emitted | structural: only `bgp_auth_secret_name` is read |

`ClusterFabricPeering.peer_asn` needs no check — the schema makes it mandatory.

## 5. Ordering and omission

| Rule | Reason |
| --- | --- |
| `peers` sorted by peering name | SC-004. The schema's `order_by` already returns them ordered, but sorting explicitly makes it independent of a future schema edit and testable without a server |
| Manifest key order fixed by the template | The other half of SC-004, and free with the hybrid approach |
| Peerings with `enabled: false` omitted | FR-016. A disabled session is not a peer |
| Optional spec fields omitted when unset, never emitted empty or null | FR-018. The XRD carries its own defaults; an explicit `null` would override them |

## 6. Seed object

One `ServiceFabricPeering`, the minimum for the artifact to have a target (FR-030).

| Field | Value | Note |
| --- | --- | --- |
| `name` | `nfd41-fabric-peering` | The artifact's identity; **not** `metadata.name` |
| `status` | `active` | Does not gate rendering |
| `owner` | an `OrganizationTenant` | Mandatory on `ServiceGeneric` |
| `cluster` | `nfd41` | Mandatory |
| `peerings` | both `ClusterFabricPeering` objects | What realizes the service |
| `communities` | `["65401:110"]` | |
| `advertisement_selector` | `["nfd41.lab/advertise=fabric"]` | |

`ServiceGeneric.owner` peers `OrganizationGeneric` and the loaded concrete tenants are
`OrganizationTenant` objects, which inherit it. Whether a scalar name resolves through
that generic or needs an inline `kind:` block is a load-time detail for the task phase —
this session hit that distinction repeatedly, and the generic's own HFID is what decides
it.

## 7. Known limitations carried forward

| Limitation | Why it is not solved here | Where it belongs |
| --- | --- | --- |
| Nothing verifies the rendered ASNs and addresses match what AVD put on the leaves | Requires comparing two renderings, not producing one | `checks/` |
| Nothing prevents two peerings resolving to the same address (the VARP-gateway mistake) | The schema's mandatory cardinality-one relationships make it hard, not impossible | `checks/` |
| `bgp_timers` keys are not validated against the XRD | The XRD owns its own schema; a wrong key is rejected at apply time | `checks/`, or accept |
| Two `ServiceFabricPeering` objects could reference one cluster | Would render two manifests with the same content and different names | `checks/` |
