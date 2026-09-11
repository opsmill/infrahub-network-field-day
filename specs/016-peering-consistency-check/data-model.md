# Data Model: Peering Consistency Check

**Feature**: `specs/016-peering-consistency-check` | **Date**: 2026-09-11

Read-only. No kind is created or modified.

## 1. What the check reads

```text
ServiceFabricPeering ──► cluster ──► ClusterKubernetes
                                     ├── fabric_peerings ──► ClusterFabricPeering
                                     │     ├── peer_asn                (compared)
                                     │     ├── peer_device ──► DcimDevice
                                     │     │     ├── role              (compared)
                                     │     │     ├── asn ──► RoutingAsn        (authority for peer_asn)
                                     │     │     └── interfaces ──► InterfaceVirtual
                                     │     │           ├── role == "peering"
                                     │     │           └── ip_addresses         (authority for peer_address)
                                     │     └── peer_address ──► IpamIPAddress  (compared)
                                     └── nodes ──► ComputePhysicalServer
                                           └── interfaces ──► NetworkLink ──► far device  (the cabled set)

EvpnSviNode ──► device, vlan, ip_address    (the fabric's second record)
```

## 2. The six rules

| # | Rule | Authority | Severity |
| --- | --- | --- | --- |
| C-1 | `peer_asn` equals the peer device's `RoutingAsn` | the device | error |
| C-2 | `peer_address` is the address on the peer device's `peering` SVI | the device | error |
| C-3 | At most one `ServiceFabricPeering` per cluster | structural | error |
| C-4 | `peer_device` is in the cluster's cabled set | the cabling | error |
| C-5 | `peer_device` has a fabric-leaf role | the role dropdown | error |
| C-6 | `EvpnSviNode.ip_address` agrees with the matching SVI, matched on device **and** VLAN | either — they must agree | error |

Plus one advisory:

| # | Finding | Severity |
| --- | --- | --- |
| C-7 | An `EvpnSviNode` with no matching SVI | **info** — not every SVI node is a peering SVI |

## 3. Severity rationale

The SDK has no `log_warning`. `log_error` blocks the merge; `log_info` does not. So severity is
a binary decision about whether a finding should stop a human, and C-7 is the only one that
should not.

## 4. Reporting contract

| Property | Value |
| --- | --- |
| Accumulation | Every violation reported; never return early |
| Attribution | Every `log_error` carries `object_id` and `object_type` |
| Message shape | Names the object, the recorded value, and the authoritative value |
| Empty model | Passes — deliberately, and asserted by SC-008 rather than left to chance |

## 5. What the check deliberately does not validate

| Not checked | Why |
| --- | --- |
| Cluster has a `local_asn` | The generator refuses to run without one; object data cannot produce a session that needs it |
| The session's `name` | Not derivable; a lab-facing label by design (cycle 012) |
| Agreement with AVD's rendered config | Nothing rendered exists on this instance — research R1 |
