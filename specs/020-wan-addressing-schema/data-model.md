# Phase 1 Data Model: Making the WAN's Addressing Real

**Feature**: `020-wan-addressing-schema` | **Date**: 2026-09-11

Four changes across three files. Nothing new is created — every kind involved already exists,
and this cycle only adds the connections between them that the WAN's addressing needs in order
to be data rather than prose.

## Change map

| # | Kind | Change | File | Justifying config line |
| --- | --- | --- | --- | --- |
| 1 | `DcimCircuitEndpoint` | add `interface` | `schemas/circuit_extensions.yml` *(new)* | `neighbor 10.51.10.2` on isp-pe1 |
| 2 | `WanSite` | `bgp_session` → `bgp_sessions`, many | `schemas/wan/wan.yml` | both ends of every PE↔CE session |
| 3 | `WanInternetPeering` | add `bgp_sessions`, many | `schemas/wan/wan.yml` | `neighbor 10.52.0.2 remote-as 64500` |
| 4 | `DcimDevice` | add `router_id` | `schemas/dcim_extensions.yml` | `bgp router-id 10.50.0.1` |

## 1. `DcimCircuitEndpoint.interface`

The endpoint gains the interface that terminates it. This is the change that makes the rest of
the WAN's addressing reachable, because `InterfaceLayer3.ip_addresses` already exists — so one
relationship completes the path `circuit → endpoint → interface → address` end to end.

| Property | Value | Why |
| --- | --- | --- |
| `name` | `interface` | snake_case, ≥3 chars |
| `peer` | `DcimInterface` | the generic, so physical and virtual both fit (R5) |
| `kind` | `Attribute` | a reference, not ownership; the device owns its interfaces |
| `cardinality` | `one` | one end of a circuit lands on one interface |
| `optional` | `true` | the branch's private fibre has no provider side (FR-012) |
| `identifier` | `circuit_endpoint__interface` | explicit, unidirectional |
| `order_weight` | `960` | after the endpoint's existing `location` |

Delivered as an `extensions:` block. `circuit/circuit.yml` is adopted from the marketplace at
version 1.0.1 and stays byte-identical (R4, SC-009).

## 2. `WanSite.bgp_sessions`

A BGP attachment is two `RoutingBGPNeighbor` objects — one on the PE, one on the CE — because
that kind is device-scoped and unique on `[device, peer_address__value]`. The existing
cardinality-one relationship can hold only one of them.

| Property | Before | After |
| --- | --- | --- |
| `name` | `bgp_session` | `bgp_sessions` |
| `label` | `BGP Session` | `BGP Sessions` |
| `cardinality` | `one` | `many` |
| `identifier` | `wan_site__bgp_session` | `wan_site__bgp_sessions` |
| `description` | "Present when attachment_kind is bgp" | "Both ends of the attachment session; present when attachment_kind is bgp" |
| `peer`, `kind`, `optional`, `order_weight` | `RoutingBGPNeighbor`, `Attribute`, `true`, `940` | unchanged |

The old relationship stays in the file as a tombstone and is not deleted from it:

```yaml
- name: bgp_session
  peer: RoutingBGPNeighbor
  kind: Attribute
  cardinality: one
  optional: true
  identifier: wan_site__bgp_session
  state: absent
```

Without the tombstone the server keeps the old relationship and `schema check` reports
nothing — proven both ways in R6. It stays until the instance is next rebuilt from empty.

**Stays optional.** acme's DR site has `attachment_kind: static` and runs no protocol at all;
zero sessions is a valid state, not a missing one.

## 3. `WanInternetPeering.bgp_sessions`

Identical shape, for the same reason: the transit link is `neighbor 10.52.0.2` on isp-pe2 and
`neighbor 10.52.0.1` on internet-rtr, which is two objects (R8).

| Property | Value |
| --- | --- |
| `name` | `bgp_sessions` |
| `peer` | `RoutingBGPNeighbor` |
| `kind` | `Attribute` |
| `cardinality` | `many` |
| `optional` | `true` |
| `identifier` | `internet_peering__bgp_sessions` |
| `order_weight` | `950` — after `internet_prefixes` at 940 |

This is an addition, not a change; `WanInternetPeering` has no session relationship today.

## 4. `DcimDevice.router_id`

| Property | Value | Why |
| --- | --- | --- |
| `name` | `router_id` | |
| `label` | `Router ID` | |
| `peer` | `IpamIPAddress` | the address object, never a text copy of it |
| `kind` | `Attribute` | |
| `cardinality` | `one` | a router has one |
| `optional` | `true` | every fabric device has none and derives its own through AVD |
| `identifier` | `device__router_id` | distinct from `device__ip_address` (`loopback_ip`) |

Placed in `schemas/dcim_extensions.yml` beside `loopback_ip`, `vtep_loopback_ip` and `mgmt_ip`,
which have exactly this shape. Kept separate from `loopback_ip` because three of the six WAN
routers use a non-loopback address as their router ID (R3).

## Invariants this design preserves

- **No address is ever text.** Every new relationship peers with an object kind. Nothing here
  introduces a CIDR or an IP as a string, which is 010's assumption 4 and the debt this cycle
  repays.
- **Nothing becomes mandatory.** All four relationships are optional, so the existing seed
  continues to load untouched (FR-012, FR-041).
- **No identity changes.** No `display_label`, `human_friendly_id`, `order_by` or uniqueness
  constraint is touched (FR-031).
- **The adopted file is untouched.** Only `*_extensions.yml` files and the locally authored
  `wan/wan.yml` change (SC-009).
- **One direction only.** All four are unidirectional with explicit identifiers; no reverse
  side is declared on `DcimInterface`, `RoutingBGPNeighbor` or `IpamIPAddress`, so no
  identifier can mismatch (FR-009).

## What this deliberately does not model

Confirmed present and sufficient in research, listed so their absence from the change map reads
as a finding rather than an oversight:

- `RoutingAsn` and `DcimDevice.asn` — AS 65500 and AS 64500 are object data (R2).
- The `loopback` interface role — already in the effective dropdown (R1).
- `InterfaceLayer3.ip_addresses` — already many and optional; the reason change 1 suffices.
- `WanSite.static_routes` → `RoutingVrfStaticRoute` — already present for acme/dr's static
  route inside `CUST_ACME`.
- `RoutingPrefixList` and `RoutingRouteMap` — they exist, and the FRR renderer should *derive*
  the import policies from service intent rather than read seeded copies. Seeding them would
  move the interesting part of the demonstration out of the model and into the data.
