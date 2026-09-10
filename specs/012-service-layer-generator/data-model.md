# Data Model: Service-Layer Fabric Peering Generator

**Feature**: `specs/012-service-layer-generator` | **Date**: 2026-09-10

No schema changes. Every kind here was published by cycle 010 and is loaded. This document
describes what the generator *reads*, what it *writes*, and the rules that decide which.

---

## 1. The traversal

One query, one round trip. Each hop was verified against loaded data (see research R2).

```text
ServiceFabricPeering (the target, resolved by name)
├── cluster ─────────────► ClusterKubernetes
│                          ├── local_asn                    (validated, not written)
│                          ├── fabric_peerings ───────────► ClusterFabricPeering  [existing sessions]
│                          │                                 ├── name             ← preserved on adopt
│                          │                                 ├── peer_asn         ← overwritten
│                          │                                 ├── enabled          ← preserved on adopt
│                          │                                 ├── peer_device
│                          │                                 └── peer_address     ← preserved on adopt
│                          └── nodes ─────────────────────► ComputePhysicalServer
│                                                            └── interfaces ────► InterfacePhysical
│                                                                └── connector ─► NetworkLink
│                                                                    └── connected_endpoints
│                                                                        ├── [near end: the node's own interface]  ✗ excluded
│                                                                        └── [far end] ──► InterfacePhysical
│                                                                                          └── device ──► DcimDevice
│                                                                                              ├── role  (filter)
│                                                                                              └── asn ──► RoutingAsn  → peer_asn
└── peerings ────────────► ClusterFabricPeering  [the service's own link, written]
```

---

## 2. Read set

| Kind | Fields read | Used for |
| --- | --- | --- |
| `ServiceFabricPeering` | `id`, `name` | The target; error messages; owning the written sessions |
| `ClusterKubernetes` | `id`, `name`, `local_asn` | Parent of every session; `local_asn` presence is validated (FR-018) |
| `ComputePhysicalServer` | `id`, `interfaces` | Starting point of the traversal |
| `InterfacePhysical` (node side) | `id`, `connector` | The near end — its `id` is what excludes it at the far end |
| `NetworkLink` | `id`, `connected_endpoints` | The cable |
| `InterfacePhysical` (far side) | `id`, `device` | Reaching the peer |
| `DcimDevice` | `id`, `name`, `role`, `asn` | Filter, dedup key, `peer_asn` |
| `RoutingAsn` | `asn` | The value written to `peer_asn` |
| `ClusterFabricPeering` (existing) | `id`, `name`, `peer_asn`, `enabled`, `peer_device`, `peer_address` | Deciding adopt versus create, and carrying preserved values |

Nothing in the read set is mutated except `ClusterFabricPeering`.

---

## 3. Write set

**One kind: `ClusterFabricPeering`.** Its schema constraints define the whole reconciliation:

| Property | Value | Consequence for the generator |
| --- | --- | --- |
| `uniqueness_constraints` | `[["cluster", "peer_device"]]` | This *is* the natural key. The derivation produces exactly one candidate per `(cluster, device)`, so upsert matches an existing session rather than duplicating it — which is what makes adoption work without an id lookup |
| `human_friendly_id` | `[cluster__name__value, name__value]` | Reference form in errors and logs |
| `cluster` | mandatory `Parent`, cardinality one | Always written; identifies the session's owner |
| `peer_device` | mandatory, cardinality one, peer `DcimGenericDevice` | Always written |
| `peer_asn` | mandatory `Number` | **The only field this cycle makes model-derived** |
| `name` | mandatory `Text` | Written on create, omitted on adopt (FR-026) |
| `enabled` | mandatory `Boolean`, default `true` | Written on create, omitted on adopt (FR-017) |
| `peer_address` | relationship | Written on create from the recorded address, omitted on adopt (FR-027) |

### Payload shapes

Derived from research R3. The difference between these two dicts is the entire implementation
of both clarifications.

```text
ADOPT   (a session already exists for this cluster + device)
  cluster, peer_device, peer_asn

CREATE  (no session exists)
  cluster, peer_device, peer_asn, name, enabled, peer_address
  └── and if no address is recorded for this device → raise (FR-027)
```

---

## 4. Derivation rules

| # | Rule | Source |
| --- | --- | --- |
| D-1 | Candidate peers are the far-end devices of every link from every cluster node interface | FR-009 |
| D-2 | The near end is excluded by interface id, not by device kind | R2 |
| D-3 | Devices whose `role` is not in `{leaf, border_leaf, l2leaf}` are skipped silently | FR-010, R6 |
| D-4 | The peer set is the set of **distinct** devices; two nodes on one leaf yield one session | FR-009 |
| D-5 | `peer_asn` comes from the device's `RoutingAsn`, never from the service or a file | FR-011, R5 |
| D-6 | Equal ASNs across peers are legal (MLAG pair shares one AS) and never collapse the set | R5 |
| D-7 | The set is sorted by device name before writing | FR-013, R10 |
| D-8 | An uncabled interface contributes nothing and is not an error | Edge case |

---

## 5. Validation rules

All are checked **before any write**, so a failing run leaves the graph untouched — which
matters because a partial write is the one case that can delete real sessions (R4).

| # | Condition | Message names | Requirement |
| --- | --- | --- | --- |
| V-1 | Target resolved no service | the kind | FR-018 |
| V-2 | Service has no cluster | the service | FR-018 |
| V-3 | Cluster has no `local_asn` | the cluster and the field | FR-018 |
| V-4 | Cluster has no nodes, or no node has any cabling | the cluster | FR-018 |
| V-5 | A derived peer device has no `RoutingAsn` | that device | FR-018 |
| V-6 | A newly derived peer has no recorded `peer_address` | that device | FR-027 |
| V-7 | The peer set is empty after filtering | the cluster, and why an empty set is worse than an error | FR-019 |

V-7 restates cycle 011's finding: an empty `peers` list produces a manifest that applies
cleanly, reports healthy, and carries no routes.

---

## 6. State transitions

The reconciliation is a three-way comparison between the derived peer set and the sessions
already attached to the cluster.

| Derived | Existing | Action | Tracking effect |
| --- | --- | --- | --- |
| yes | no | **Create** with the full payload | Joins the tracking group |
| yes | yes | **Adopt** — upsert `peer_asn` only | Joins the tracking group; managed from now on |
| no | yes, in the tracking group | **Delete** (by the SDK, not by generator code) | Removed |
| no | yes, *not* in the tracking group | **Leave alone** | Never a candidate — see R4 |

The last row is FR-022 and is guaranteed by the SDK's set difference over the previous run's
group members, not by anything the generator does.

---

## 7. What this leaves for a later cycle

`peer_address` remains the one hand-maintained fact. The live graph shows `10.110.0.2/24`
with `interface: null`, so no traversal connects it to `leaf-nfd41-pod1-1-1`. Modelling the
leaves' peering SVIs would make it derivable exactly as `peer_asn` now is — and that is a
schema change, so it is a cycle of its own that must come first.
