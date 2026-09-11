# Contract: Object Data Surface

**Feature**: `specs/021-wan-addressing-objects` | **Date**: 2026-09-11

What must exist in the graph after this cycle, and the exact YAML forms that put it there. The
forms are not stylistic — four of them are the only ones that work, established by loading each
against a live instance in [research.md](../research.md).

## 1. The five reference forms

Every relationship this cycle writes uses one of these. Getting one wrong fails in a way that
does not name the field.

| # | Situation | Form | Why |
| --- | --- | --- | --- |
| 1 | Peer is a generic **with** an HFID | `interface: ["isp-pe1", "eth2"]` | `DcimInterface` declares `[device__name__value, name__value]` (R5) |
| 2 | Peer is a generic **without** an HFID | inline block naming the concrete kind | `InterfaceLayer3` declares none (R1) |
| 3 | Any inline block, cardinality **one** | `data:` is a **mapping** | a list raises `AttributeError: 'list' object has no attribute 'items'` (R2) |
| 4 | Peer is concrete with a multi-element HFID | `router_id: ["10.50.0.1/32", "default"]` | `IpamIPAddress` is `[address__value, ip_namespace__name__value]` |
| 5 | HFID element is a Number | `asn: "65500"` — quoted | an int is rejected as the wrong format (R4) |

Form 3 is the one to watch. Every inline block in this cycle is cardinality one, and the
`infrahub-managing-objects` skill documents the list shape.

## 2. `objects/31a_nfd41_wan_addressing.yml` — new

Filename must sort between `31_nfd41_offfabric_devices.yml` and `32_nfd41_security.yml`.

Seven documents, in this order, because each depends on the one before:

```yaml
# 1. InterfacePhysical    -- 17, scalar `device`, mtu 9214
# 2. InterfaceVirtual     -- 3 loopbacks, role loopback
# 3. IpamIPAddress        -- 20, each with an inline concrete-kind `interface` block (form 2+3)
# 4. RoutingAsn           -- 5, each with `devices: [names]` (reverse side, avoids device upsert)
# 5. IpamVRF              -- CUST_ACME, CUST_GLOBEX, moved verbatim from file 37
# 6. RoutingVrfStaticRoute -- 1, vrf CUST_ACME, devices [isp-pe1]
# 7. DcimDevice           -- 6, name + status + router_id (form 4)
```

The address block is the shape most likely to be written wrong:

```yaml
- address: 10.51.10.1/30
  description: "isp-pe1 eth2, provider side of acme/hq"
  interface:
    kind: InterfacePhysical
    data:
      name: eth2
      device: isp-pe1
```

`data:` is a mapping. A dash before `name:` fails.

## 3. `objects/33_nfd41_wan.yml` — edited in place

Three changes. All are edits rather than a new file because a top-level upsert would restate
every mandatory attribute — `location` on an endpoint, `lan_prefix` and `tenant` on a site (R3).

**Endpoints** gain `interface`, and lose the address from their description:

```yaml
- side: a
  name: isp-pe1-eth2
  status: active
  description: "Provider side"          # the address is gone
  location:
    kind: LocationSite
    data:
      name: provider-edge               # mapping, not a list
  interface: ["isp-pe1", "eth2"]
```

**Sites** gain their sessions:

```yaml
- name: hq
  tenant: acme
  attachment_kind: bgp
  bgp_sessions:
    - ["isp-pe1", "10.51.10.2"]
    - ["cust-acme-ce", "10.51.10.1"]
```

acme/dr gains `static_routes` and **no** `bgp_sessions`. The internet peering gains both ends of
the transit session.

## 4. `objects/37_nfd41_wan_services.yml` — edited

The `IpamVRF` document holding `CUST_ACME` and `CUST_GLOBEX` is removed; its content moves to
`31a` unchanged. The `ServiceL3vpn` objects that reference those VRFs stay, and still resolve —
file 37 sorts after `31a`.

## 5. The graph after loading

| From | Path | Must yield |
| --- | --- | --- |
| `DcimCircuit` (×4) | `endpoints → interface → ip_addresses` | an address on all 8 endpoints |
| `WanSite` acme/hq, globex/hq, branch/office | `bgp_sessions` | exactly 2 each |
| `WanSite` acme/dr | `bgp_sessions` / `static_routes` | 0 / 1 |
| `WanInternetPeering` | `bgp_sessions` | 2 |
| `DcimDevice` (×6) | `router_id → address` | the lab's value |
| `DcimDevice` (×6) | `asn → asn` | the lab's value |

Counts: 20 interfaces, 20 addresses, 5 ASNs, 10 `RoutingBGPNeighbor`, 1 `RoutingVrfStaticRoute`,
2 relocated `IpamVRF`.

## 6. Idempotence

A second `infrahubctl object load objects/` must produce no error and no duplicate. Verified by
counting, not by reading the log — the CLI prints "Created node" for an upsert, so the log is
not evidence.

## 7. Test contract

A new `tests/unit/test_wan_addressing_objects.py` parses the YAML and asserts against
`../lab/wan/tenants.yml` directly, so it needs no server:

- every interface, address, ASN, session, router ID and static route in the files appears in the
  lab file, and vice versa — the transcription is exact in both directions
- no endpoint description contains an IP address or CIDR, which is the debt this cycle repays
- every inline `data:` block under a cardinality-one relationship is a mapping (guards R2)
- `31a` sorts between `31` and `33`, so the load order is pinned rather than assumed
- `CUST_ACME` and `CUST_GLOBEX` appear in exactly one file
