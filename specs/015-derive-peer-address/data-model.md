# Data Model: Derive the Peering Address

**Feature**: `specs/015-derive-peer-address` | **Date**: 2026-09-11

No schema change. This extends one traversal and one derivation.

## 1. The extended traversal

```text
ServiceFabricPeering
└── cluster ──► ClusterKubernetes
    ├── fabric_peerings ──► ClusterFabricPeering   [existing sessions]
    └── nodes ──► ComputePhysicalServer
        └── interfaces ──► InterfacePhysical
            └── connector ──► NetworkLink
                └── connected_endpoints ──► [near end: excluded by id]
                                       └──► InterfacePhysical
                                            └── device ──► DcimDevice
                                                ├── role            (filter)
                                                ├── asn ──► RoutingAsn      → peer_asn
                                                └── interfaces ──► InterfaceVirtual   ★ NEW
                                                    ├── role == "peering"   (selection)
                                                    └── ip_addresses ──► IpamIPAddress → peer_address
```

★ is the only new hop, and it exists because cycle 014 modelled the SVIs.

## 2. Derivation rules

Existing rules D-1 … D-8 from cycle 012 are unchanged. Three are added:

| # | Rule | Source |
| --- | --- | --- |
| D-9 | The peering SVI is the peer device's interface whose `role` is `peering` | FR-003, R1 |
| D-10 | `peer_address` is the single `IpamIPAddress` on that SVI, referenced by id — not copied | FR-002, FR-004 |
| D-11 | Ambiguity is an error: zero or several peering SVIs, or several addresses on one, fails | FR-006, R5 |

## 3. Payload shapes

Cycle 012 had one shape. There are now two again, because the create path is reachable.

```text
ADOPT   (a session exists for this cluster + device)
  peer_asn, peer_address
  └── applied by fetching the node and setting those two attributes,
      because an upsert validates every mandatory field

CREATE  (no session exists)
  cluster, peer_device, peer_asn, peer_address, name, enabled
  └── name = the peer device's name; enabled = true
```

`name` and `enabled` are still absent from the adopt payload and so are preserved.

## 4. Validation rules

V-1 … V-5 and V-7 from cycle 012 are unchanged. **V-6 is replaced** and two are added:

| # | Condition | Message names |
| --- | --- | --- |
| ~~V-6~~ | ~~a new peer has no recorded address~~ | **removed** — the address is now derivable |
| V-6′ | A derived peer device has no interface with role `peering` | that device |
| V-8 | A peer device has more than one peering SVI | that device and the count |
| V-9 | A peering SVI carries more than one address | that device and the addresses |

All are checked before any write, preserving cycle 012's ordering guarantee.

## 5. Drift reporting

| State | Behaviour |
| --- | --- |
| Recorded address equals derived | Silent |
| Recorded address differs from derived | **Logged naming the session, the old and the new value**, then corrected |
| No recorded address (new session) | Created silently |

## 6. What object data loses

`objects/34_nfd41_cluster.yml` keeps `name`, `description` and `svi`, and loses
`peer_address` and `peer_asn`. The split-ownership annotation cycle 012 added is rewritten:
`name` is the only field the file still owns.
