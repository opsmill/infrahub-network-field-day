# Phase 1 Data Model: FRR Configuration for the WAN

**Feature**: `022-frr-config-render` | **Date**: 2026-09-11

No new kinds and no new objects except one group. This cycle reads the graph and writes text.
What follows is the context each template needs and where every field comes from — verified by
rendering three of the six devices zero-diff from live data (R1).

## The render context

The lab's templates take a context shaped like `tenants.yml`: `node`, `isp`, `tenants`, `branch`.
The transform assembles that shape from Infrahub, which is the whole of its work.

### `isp`

| Context field | Source | Notes |
| --- | --- | --- |
| `isp.asn` | `DcimDevice(role: isp_edge).asn.asn` | 65500 |
| `isp.edge.node` | the `isp_edge` device's name | |
| `isp.edge.loopback` | its `router_id.address`, mask stripped | `10.50.0.1/32` → `10.50.0.1` |
| `isp.edge.core.peer` | its `RoutingBGPNeighbor` whose `remote_as` equals `isp.asn` | the iBGP session; **device-scoped, no site names it** (R3) |
| `isp.core.*` | the same, for the `isp_core` device | plus its handoff toward `border-leaf1` |
| `isp.dc_service_prefixes` | `ServiceL3vpn.dc_service_prefixes` | the shared DC range; identical on every L3VPN |
| `isp.internet.asn` | `WanInternetPeering.peer_asn` | 64500 |
| `isp.internet.customer_aggregate` | `WanInternetPeering.customer_aggregate` | `10.60.0.0/16` |

### `tenants[]`

| Context field | Source |
| --- | --- |
| `name` | `OrganizationTenant.name` |
| `vrf` | `ServiceL3vpn.vrf.name` — the PE-side `CUST_*` |
| `internet` | **whether a `ServiceInternetAccess` exists for this tenant's L3VPN** |
| `dc.subnet` | `ServiceTenantCloud.prefix` |
| `sites[]` | the tenant's `WanSite` objects, ordered per R6 |

`internet` is the field this whole architecture exists for. It is not an attribute anywhere — it
is the presence or absence of an object, computed at render time.

### `tenants[].sites[]`

| Context field | Source | Notes |
| --- | --- | --- |
| `name` | `WanSite.name` | |
| `kind` | `WanSite.attachment_kind` | `bgp` or `static` |
| `lan` | `WanSite.lan_prefix.prefix` | |
| `asn` | `WanSite.site_asn` | absent on a static site |
| `pe.address` | the CE-side session's `peer_address` + `/30` | the PE's own address, as the CE sees it |
| `ce.wan_address` | the PE-side session's `peer_address` + `/30` | and for a **static** site, the static route's `next_hop` |
| `ce.node` | the CE-side session's device; for a static site, `next_hop → interface → device` (R4) | |

**Site ordering**: BGP attachments first, then static, each by name. This reproduces the lab's
authoring order, which Infrahub does not store, and it matches how the template reads them — two
separate loops by kind (R6).

### `branch`

| Context field | Source |
| --- | --- |
| `asn` | `branch-rtr.asn.asn` |
| `loopback` | its `router_id.address`, mask stripped |
| `lan` | the branch `WanSite.lan_prefix` |
| `router.dc_peer`, `dc_peer_asn` | its single `RoutingBGPNeighbor` |

## Template selection

One template per device role. The transform picks by role, so adding a seventh router of an
existing role needs no code change.

| Role | Template | Devices | Golden lines |
| --- | --- | --- | --- |
| `isp_edge` | `isp-edge.j2` | `isp-pe1` | 159 |
| `isp_core` | `isp-core.j2` | `isp-pe2` | 108 |
| `internet_edge` | `internet-rtr.j2` | `internet-rtr` | 61 |
| `customer_edge` | `customer-ce.j2` | `cust-acme-ce`, `cust-globex-ce` | 43 each |
| `branch_router` | `branch-router.j2` | `branch-rtr` | 34 |

`cust-acme-dr-ce` also has role `customer_edge` and is **not** a target — the lab renders no FRR
config for it. This is why group membership is explicit rather than role-derived (R9).

## The one new object

A `CoreStandardGroup` in `objects/00_groups.yml` holding exactly the six routers above. An
artifact definition cannot target a group that does not exist, and cycle 017 set the precedent
for adding one inside a transform cycle.

## Invariants

- **Nothing is hardcoded but FRR's own syntax.** Every address, AS number, prefix and device
  name comes from the graph (SC-007).
- **A missing value fails the render.** `StrictUndefined`, because a blank neighbour address
  produces a config that vtysh accepts and that never comes up (R2).
- **Every comment survives.** The lab's comments explain why next-hop-self is needed and why the
  import route-map is what keeps tenants apart; a correct config that explains nothing is a
  worse artifact (FR-021).
- **One line differs from the oracle by design** — the provenance header, which must name
  Infrahub rather than claim to be `wan/render.py`.
- **Six artifacts, never seven.**
