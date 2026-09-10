# Phase 1 — Data Model: k8s Leaf Peering SVIs

**Feature**: `specs/014-k8s-leaf-peering-svi`
**Date**: 2026-09-10

No schema changes. Every kind below already exists; this cycle adds *instances* of one of them
and one relationship edge per instance.

---

## What the cycle adds

Two `InterfaceVirtual` objects, each linking a leaf device to the peering address it already
owns in the fabric's own records.

```text
BEFORE                                    AFTER

DcimDevice leaf-nfd41-pod1-1-1            DcimDevice leaf-nfd41-pod1-1-1
                                                    ^
                                                    | device (Parent)
                                          InterfaceVirtual "Vlan110"
                                                    |
                                                    | ip_addresses (many)
                                                    v
IpamIPAddress 10.110.0.2/24               IpamIPAddress 10.110.0.2/24
  interface -> null                         interface -> Vlan110    <-- the new traversal
```

The reverse edge (`IpamIPAddress.interface`) is not written separately. It is the same
relationship — identifier `interfacelayer3__ipamipaddress` — seen from the other side, and
Infrahub populates it when the forward side is set. Confirming that it is in fact populated is
SC-003, because it is the half the follow-up generator will actually traverse.

---

## Entity: `InterfaceVirtual` (added)

| Property | Value |
| --- | --- |
| Kind | `InterfaceVirtual` |
| Inherits | `DcimInterface`, `InterfaceLayer2`, `InterfaceLayer3` |
| Human-friendly id | `[device__name__value, name__value]` |
| Uniqueness | `[device, name__value]` |
| Instances added | 2 |

### Fields set

| Field | Kind | Value | Why |
| --- | --- | --- | --- |
| `name` | Text | `Vlan110` | The EOS/AVD name for the SVI of VLAN 110, and the name the existing seed comments already use in prose. Unique per device; does not collide with the template-generated `Loopback0`. |
| `device` | Relationship (Parent, one) | `leaf-nfd41-pod1-1-1` / `leaf-nfd41-pod1-1-2` | Mandatory. Peer `DcimGenericDevice` has HFID `[name__value]`, so a scalar reference is correct. These are the names `ClusterFabricPeering.peer_device` uses — **not** the `k8s-leaf*` duplicates. |
| `description` | Text | Names the leaf and the session it serves | Read by a human in the UI; states which BGP session the interface exists for. |
| `role` | Dropdown | `peering` | A choice that already exists on the `DcimInterface` role dropdown (`schemas/dcim_extensions.yml`). It is the honest label and it gives the follow-up generator a cheap, explicit filter should it want one. |
| `status` | Dropdown | `active` | The schema default, stated explicitly to match how the rest of the seed data reads. |
| `dot1q_id` | Number | `110` | Makes the interface self-describing: the VLAN it is the SVI for, matching `EvpnSvi.svi_id: 110`. |
| `ip_addresses` | Relationship (Attribute, many) | `[["10.110.0.2/24", "default"]]` / `[["10.110.0.3/24", "default"]]` | **The point of the cycle.** List-of-lists because `IpamIPAddress` has a two-element HFID `[address__value, ip_namespace__name__value]`. |

### Fields deliberately NOT set

| Field | Why not |
| --- | --- |
| `ip_address` (cardinality one) | A *different* relationship (`interface__ip_address`) with no reverse side on `IpamIPAddress`, so it would not create the traversal. It is also read by `src/solution_arista_avd/addressing.py` on the P2P addressing path. See research R2. |
| `mtu` | Schema default (1514) is correct; nothing about this cycle justifies pinning it. |
| `l2_mode`, `spanning_tree_*` | Layer-2 attributes an SVI does not have. |
| `index` | Read-only computed attribute. Expected to render `110`; asserted after load, never written. |
| `untagged_vlan` / `tagged_vlan` | The VLAN association is already modelled by `EvpnSvi`/`IpamVLAN` and duplicating it here would create a second place to keep in sync. |

---

## Entities read but not modified

| Kind | Role in this cycle |
| --- | --- |
| `IpamIPAddress` | `10.110.0.2/24` and `10.110.0.3/24`. Already declared in `objects/34_nfd41_cluster.yml`. This cycle attaches them; it does not create, move, or re-describe them. |
| `DcimDevice` | The two leaves. Referenced as parents. Not upserted — the top-level-object form is used precisely so the devices' own attributes are never restated and so cannot be accidentally overwritten. |
| `ClusterFabricPeering` | The two sessions. The oracle: their declared `peer_address` is what the new traversal must reproduce. Values unchanged (spec FR-021). |
| `EvpnSvi` / `EvpnSviNode` | The fabric's existing record of VLAN 110 and each leaf's address on it. The source of truth this cycle mirrors into a navigable form. Unchanged. |

---

## Validation rules

Derived from the spec's functional requirements; each is checked by a test or an evidence command.

| Rule | Source | Checked by |
| --- | --- | --- |
| Exactly 2 peering SVIs exist, one per leaf | FR-016 | contract test + live query |
| Each SVI carries exactly one address | FR-013 | contract test + live query |
| The address on each SVI equals that leaf's `ClusterFabricPeering.peer_address` | FR-017 | contract test cross-referencing the two seed files |
| The two addresses are distinct | FR-014 | contract test |
| `10.110.0.1` (VARP gateway) is attached to no interface | FR-013 | contract test + live query |
| Each SVI's device name appears as a `peer_device` on a session | FR-006 | contract test |
| `IpamIPAddress -> interface -> device` resolves for both addresses | FR-018 | live query (SC-003) |
| Deriving the address from the device yields exactly one candidate | FR-017 | live query (SC-005) |
| No file under `schemas/` or `generators/` changes | FR-019, FR-020 | `git diff --name-only` (SC-008) |
| The Crossplane artifact is byte-identical | FR-022 | `diff` against baseline (SC-006) |

---

## Load order

```text
20_nfd41_device_types.yml    device types + interface templates (creates Loopback0)
26_nfd41_devices.yml         the leaf devices
27_nfd41_vrf_services.yml    EvpnSvi VLAN 110, EvpnSviNode per leaf
34_nfd41_cluster.yml         the peering IpamIPAddress objects, the sessions
35_nfd41_peering_service.yml the service-layer wrapper
36_nfd41_peering_svis.yml    <-- NEW: the peering SVIs
```

The new file depends on `26` (devices) and `34` (addresses) and is depended on by nothing, so it
sorts last. No existing file's position changes.
