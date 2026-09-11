# Phase 1 Data Model: The WAN's Addressing

**Feature**: `021-wan-addressing-objects` | **Date**: 2026-09-11

No new kinds. 56 new objects and 25 relationship links on existing ones, every value transcribed
from `../lab/wan/tenants.yml`.

## What lands where

| File | Status | Contents |
| --- | --- | --- |
| `objects/31a_nfd41_wan_addressing.yml` | **new** | 20 interfaces, 20 addresses, 5 ASNs, 10 BGP neighbours, 2 VRFs, 1 static route, 6 router IDs |
| `objects/33_nfd41_wan.yml` | edited | 8 endpoint interface links, 4 sites' sessions, 1 site's static route, prose removed |
| `objects/37_nfd41_wan_services.yml` | edited | the two `CUST_*` VRF definitions move out |

One new file, not two. The spec proposed `38` and `39` split by load order; research R3 and R8
showed the real constraint is the opposite — everything new must land *before* `33`, and
everything that updates an existing object must be edited *into* `33`.

`31a` sorts after `31_nfd41_offfabric_devices.yml` and before `32_nfd41_security.yml`, verified
by sorting the actual filenames. That position is the whole design: it is after the devices the
interfaces hang off, and before the circuits and sites that name them.

## 1. Interfaces — 20

Created standalone with a scalar `device`, which is the pattern
`objects/28_nfd41_endpoints.yml` already uses.

| Device | Interfaces | Kind |
| --- | --- | --- |
| `isp-pe1` | `lo` | `InterfaceVirtual`, role `loopback` |
| `isp-pe1` | `eth1` core, `eth2` acme/hq, `eth3` globex/hq, `eth4` acme/dr | `InterfacePhysical` |
| `isp-pe2` | `lo` | `InterfaceVirtual`, role `loopback` |
| `isp-pe2` | `eth1` core, `eth2` border-leaf1, `eth3` internet | `InterfacePhysical` |
| `internet-rtr` | `eth1` peering, `eth2` LAN | `InterfacePhysical` |
| `cust-acme-ce` | `eth1` WAN, `eth2` LAN | `InterfacePhysical` |
| `cust-acme-dr-ce` | `eth1` WAN, `eth2` LAN | `InterfacePhysical` |
| `cust-globex-ce` | `eth1` WAN, `eth2` LAN | `InterfacePhysical` |
| `branch-rtr` | `lo` | `InterfaceVirtual`, role `loopback` |
| `branch-rtr` | `eth1` to border-leaf1, `br-branch` LAN | `InterfacePhysical` |

All carry `mtu: 9214`, the lab's value. Roles come from the existing dropdown — `loopback`,
`core`, `cust`, `upstream`, `peering`, `access` — none of which needs adding.

`cust-acme-dr-ce` gets interfaces despite speaking no routing protocol: its `eth1` address is
the static route's next hop.

## 2. Addresses — 20

One per interface, attached from the address side with an inline block naming the concrete kind,
because `IpamIPAddress.interface` peers with an HFID-less generic (R1):

```yaml
- address: 10.51.10.1/30
  interface:
    kind: InterfacePhysical
    data:                    # a mapping, never a list (R2)
      name: eth2
      device: isp-pe1
```

Three loopbacks (`10.50.0.1/32`, `10.50.0.2/32`, `10.70.255.1/32`), eleven `/30` ends, six LAN
and peering addresses. Every one sits inside a prefix that
`objects/29_nfd41_offfabric_prefixes.yml` already holds.

## 3. Autonomous systems — 5

Stated once each, with their devices, using the reverse relationship so no device upsert is
needed (R4):

| ASN | Devices |
| --- | --- |
| 65500 | `isp-pe1`, `isp-pe2` |
| 64500 | `internet-rtr` |
| 65010 | `cust-acme-ce` |
| 65020 | `cust-globex-ce` |
| 65030 | `branch-rtr` |

`fabric` stays unset — these are off-fabric.

## 4. BGP neighbours — 10

`peer_address` and `remote_as` are Text attributes, not relationships, so these depend only on
the devices. Unique on `[device, peer_address__value]`.

| Device | Peer | Remote AS |
| --- | --- | --- |
| `isp-pe1` | 10.50.255.2 | 65500 |
| `isp-pe2` | 10.50.255.1 | 65500 |
| `isp-pe1` | 10.51.10.2 | 65010 |
| `cust-acme-ce` | 10.51.10.1 | 65500 |
| `isp-pe1` | 10.51.20.2 | 65020 |
| `cust-globex-ce` | 10.51.20.1 | 65500 |
| `isp-pe2` | 10.52.0.2 | 64500 |
| `internet-rtr` | 10.52.0.1 | 65500 |
| `isp-pe2` | 10.250.50.1 | 65103 |
| `branch-rtr` | 10.250.70.1 | 65103 |

`remote_as` is quoted — the attribute is Text.

## 5. VRFs — 2, relocated

`CUST_ACME` and `CUST_GLOBEX` move here verbatim from
`objects/37_nfd41_wan_services.yml`. They are technical-layer objects that cycle 019 created in
a service-layer file because it was the cycle that needed them (R8). Moving them lets the static
route below exist before the site that names it.

## 6. Static route — 1

acme's DR site, the one attachment with no protocol:

```yaml
- prefix: 10.60.11.0/24
  next_hop: 10.51.11.2
  vrf: CUST_ACME
  devices: [isp-pe1]
```

This is what becomes `ip route 10.60.11.0/24 10.51.11.2` inside `vrf CUST_ACME` on isp-pe1, and
then `redistribute static` inside that VRF's address family.

## 7. Router IDs — 6

A `DcimDevice` document restating `name` and `status` alongside `router_id`, because a
top-level upsert validates every mandatory attribute (R3):

| Device | Router ID | Source |
| --- | --- | --- |
| `isp-pe1` | 10.50.0.1/32 | loopback |
| `isp-pe2` | 10.50.0.2/32 | loopback |
| `branch-rtr` | 10.70.255.1/32 | loopback |
| `cust-acme-ce` | 10.60.10.1/24 | LAN address |
| `cust-globex-ce` | 10.60.20.1/24 | LAN address |
| `internet-rtr` | 10.52.0.2/30 | peering address |

`cust-acme-dr-ce` gets none.

Referenced as `["10.50.0.1/32", "default"]` — `IpamIPAddress` is a concrete kind with an HFID,
so the list form works here where it failed for the interface (R1 versus R5).

**Restating `status: active` six times is the one duplication this design accepts.** The
alternative was creating the addresses inline inside
`objects/31_nfd41_offfabric_devices.yml`, which would put six address strings in a second file.
Duplicating a constant is safer than duplicating lab data — a wrong `status` is visible, a
stale address is not.

## 8. Edits to `objects/33_nfd41_wan.yml`

Three changes, all in place, because each updates an object that file already defines (R3).

**Endpoint interface links** — eight, nested where the endpoints already are, by HFID (R5):

```yaml
- side: a
  name: isp-pe1-eth2
  status: active
  location: {kind: LocationSite, data: {name: provider-edge}}
  interface: ["isp-pe1", "eth2"]
```

**And the prose comes out.** `description: "Provider side, isp-pe1 eth2, 10.51.10.1/30"` becomes
`description: "Provider side"` or is dropped. Leaving it would restore the two-sources-of-truth
problem the cycle exists to end, one commit after removing it.

**Site sessions** — both ends on each BGP-attached site, none on acme/dr:

```yaml
bgp_sessions:
  - ["isp-pe1", "10.51.10.2"]
  - ["cust-acme-ce", "10.51.10.1"]
```

**Site static route** — acme/dr only, and the internet peering gains its two transit sessions.

## Invariants

- **Every address is one object.** A loopback address is reached as
  `interface.ip_addresses` and as `device.router_id`; it must not be written twice. The
  `[address__value, ip_namespace]` uniqueness constraint would reject a duplicate, so this is
  enforced rather than merely intended.
- **No address or prefix survives as free text** anywhere in `objects/33_nfd41_wan.yml`.
- **Nothing is invented.** Every value traces to `../lab/wan/tenants.yml`.
- **Every file stays idempotent.** Loads are upserts keyed on HFID; a second run changes nothing.
- **Load order is asserted, not assumed.** A test pins that `31a` sorts between `31` and `33`.
