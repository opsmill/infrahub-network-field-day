# Phase 1 Data Model: The Perimeter Firewall's Static Routes

**Cycle**: 025 | **Date**: 2026-09-12

Eight objects of one existing kind. No schema change, no new kind, no attribute added. This
document states what each object holds, what it deliberately leaves empty, and what the values
are checked against.

## The kind

`RoutingStaticRoute`, unchanged by this cycle. Cycle 024 widened its `device` relationship; that
is the only reason this cycle is possible and the only recent change to it.

| Field | Kind | Used here | Why |
| --- | --- | --- | --- |
| `prefix` | Text, **mandatory** | **yes** | the destination |
| `next_hop` | Text, optional | **yes** | the gateway the device forwards to |
| `route_name` | Text, optional | **yes** | the device's own `/* … */` comment |
| `gateway` | Text, optional | no | the device file sets none |
| `interface` | Text, optional | no | the device file sets none |
| `distance` | Number, optional | no | the device file sets none |
| `tag` | Number, optional | no | the device file sets none |
| `vrf` | Text, optional, default `"default"` | **no — left to the default** | these are master-instance routes, which is what the default means |
| `device` | Relationship → `DcimGenericDevice`, mandatory, cardinality one | **yes** | `fw1` |

**Leaving four attributes unset is a decision, not an omission.** A transcription that invents a
`distance` of 5 or an `interface` of `ge-0/0/0` is no longer a transcription: it renders extra
configuration the device does not have, and cycle 026 would emit it.

### `vrf` is left to the default deliberately

The device file's `routing-options` block sits outside any `routing-instances` stanza, so these
are master-instance routes — which is exactly what `vrf: "default"` means. Setting it explicitly
would be redundant, and R1 found the live schema carries a uniqueness constraint on
`[device, prefix]` *in addition to* the declared `[device, prefix, vrf]`, so consistency of this
field matters more than it appears from the YAML.

Verified on the loaded objects: all eight read back `vrf = "default"` with the file setting it
nowhere.

## The eight objects

| `prefix` | `next_hop` | `route_name` |
| --- | --- | --- |
| `10.110.0.0/24` | `10.250.110.1` | `k8s nodes` |
| `10.111.0.0/16` | `10.250.110.1` | `k8s pod CIDR` |
| `10.112.0.0/16` | `10.250.110.1` | `k8s service CIDR incl. LoadBalancer VIPs` |
| `10.210.0.0/24` | `10.250.210.1` | `app tenant hosts` |
| `10.60.0.0/16` | `10.250.150.1` | `WAN customer supernet` |
| `10.70.0.0/24` | `10.250.170.1` | `branch office LAN` |
| `10.220.10.0/24` | `10.250.10.1` | `acme cloud instances` |
| `10.220.20.0/24` | `10.250.20.1` | `globex cloud instances` |

All eight carry `device: fw1`.

`route_name` is transcribed as written — `incl.` in row three stays `incl.`. A renderer that
reproduces the file must not have to undo a tidy-up.

## Identity and uniqueness

- **HFID**: `[device__name__value, prefix__value]` — so `["fw1", "10.110.0.0/24"]`. This is what
  `infrahubctl object load` upserts on, and why a second load produces no duplicate.
- **Uniqueness**: `[device, prefix, vrf]` as declared, plus `[device, prefix]` derived from the
  HFID (R1). Eight distinct prefixes on one device satisfy both.

Three routes share the next hop `10.250.110.1`. That is correct — the k8s node, pod and service
ranges sit behind one leaf — and uniqueness is on destination, not next hop.

## The relationship reference

```yaml
device: "fw1"
```

A plain scalar, **not** an inline concrete-kind block. `device` peers `DcimGenericDevice`, which
would normally trigger the generic-relationship rule — but that rule's precondition is that the
generic has no `human_friendly_id`, and `DcimGenericDevice` defines `[name__value]`. R2 confirmed
the scalar form by loading it.

This is the opposite conclusion from cycle 023, which *did* need inline blocks for the address
book. The difference is the peer: `SecurityGenericAddress` has no HFID, `DcimGenericDevice` does.

## What the values are checked against

Three independent sources, none of which is the others:

| Check | Source | Catches |
| --- | --- | --- |
| `prefix` / `next_hop` / `route_name` exact, **both ways** | `../lab/configs/fw/vsrx/junos.conf` | a mistyped, missing or invented route |
| every `next_hop` inside a /30 `fw1` is numbered on | `objects/32_nfd41_security.yml` interface addresses | a typo in the next hop — which the oracle comparison **cannot** catch, since the oracle is where the typo would be |
| every `prefix` equals an address-book entry | `objects/32_nfd41_security.yml` address book | a destination the firewall has no policy for |

The second is the one worth the effort. It is an independent witness.

### What is deliberately not asserted

**The converse of the third check is false.** Four address-book entries have no route of their
own, and all four are correct (R5): `acme-hq`, `acme-dr` and `globex-hq` sit inside
`10.60.0.0/16`; `access-portal` (`10.112.240.33/32`) sits inside `10.112.0.0/16`; and
`fabric-infra` is never a destination at all — it appears six times as a rule `source_address`, in
the anti-spoofing rules. Asserting "every address-book prefix has a route" would fail on five
correct entries.

## File and load order

`objects/32b_nfd41_fw_static_routes.yml`, one document, `spec.kind: RoutingStaticRoute`.

| File | Provides | Needed by |
| --- | --- | --- |
| `31_nfd41_offfabric_devices.yml` | `fw1` | the `device` reference |
| `32_nfd41_security.yml` | zones, interfaces, address book | nothing here — but it is the firewall's other data, and keeping these adjacent is the point of `32b` |
| **`32b_nfd41_fw_static_routes.yml`** | the eight routes | cycle 026's renderer |

Only `fw1` is actually required, so any number above `31` would resolve. `32b` is chosen for
adjacency, and leaves `32a` free.

## What this cycle does not touch

- **The eleven existing `RoutingStaticRoute` objects.** They belong to fabric spines and leaves
  and are written by the `backfill-structured-config` generator. The load took the total from 11
  to 19 and left those eleven alone.
- **Any existing object file.** `32_nfd41_security.yml` is read by the tests, never edited.
- **Any schema file.**
