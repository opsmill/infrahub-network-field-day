# Phase 1 Data Model: Device-Level Static Routes for the Perimeter Firewall

**Cycle**: 024 | **Date**: 2026-09-12

One relationship changes. This document states what it is before and after, what depends on it,
and what deliberately stays put.

## The change, in full

### Forward side — `RoutingStaticRoute.device`

`schemas/routing/routing.yml`

```yaml
# BEFORE
- name: device
  peer: DcimDevice            # <- SecurityFirewall does not inherit this
  kind: Attribute
  cardinality: one
  optional: false
  identifier: device__static_route
  order_weight: 500

# AFTER
- name: device
  peer: DcimGenericDevice     # <- DcimDevice and SecurityFirewall both inherit this
  kind: Attribute
  cardinality: one
  optional: false
  identifier: device__static_route
  order_weight: 500
```

`kind`, `cardinality`, `optional`, `identifier` and `order_weight` are unchanged. Only `peer`
moves, and it moves *up* the inheritance chain rather than sideways.

### Reverse side — `static_routes`

The same file's `extensions:` block. The relationship moves from the `DcimDevice` entry to a
`DcimGenericDevice` entry; its body is copied verbatim so both ends keep naming
`device__static_route`.

```yaml
# BEFORE — inside `- kind: DcimDevice`, alongside four BGP/policy relationships
- name: static_routes
  label: Static Routes
  peer: RoutingStaticRoute
  optional: true
  cardinality: many
  kind: Generic
  identifier: device__static_route

# AFTER — its own entry, the same shape tenancy.yml uses for DcimGenericDevice
- kind: DcimGenericDevice
  relationships:
    - name: static_routes
      label: Static Routes
      peer: RoutingStaticRoute
      optional: true
      cardinality: many
      kind: Generic
      identifier: device__static_route
```

**Both ends move together or neither does.** A forward side on the generic and a reverse side on
the concrete kind would make the two halves of `device__static_route` disagree about their peer,
which is the failure the identifier rule exists to prevent.

The other four relationships in the `DcimDevice` entry — `bgp_peer_groups`, `bgp_neighbors`,
`prefix_lists`, `route_maps` — stay exactly where they are. Nothing in this cycle asks a firewall
to hold a BGP peer group.

## Entities

### `RoutingStaticRoute` (existing, unchanged apart from its peer)

| Field | Kind | Notes |
| --- | --- | --- |
| `prefix` | Text | The destination. Mandatory |
| `gateway` | Text | Optional |
| `next_hop` | Text | Optional. What all eight firewall routes use |
| `interface` | Text | Optional |
| `distance` | Number | Optional |
| `tag` | Number | Optional |
| `route_name` | Text | Optional, labelled "Route Description". The home for each route's `/* … */` comment |
| `vrf` | Text | Default `"default"`, which is the master routing instance |
| `device` | Relationship | **The one thing this cycle changes** |

- `human_friendly_id`: `[device__name__value, prefix__value]` — works unchanged, because
  `DcimGenericDevice` carries `name`.
- `display_label`: `prefix__value`.
- `uniqueness_constraints`: `[[device, prefix__value, vrf__value]]` — unchanged, and load-bearing
  for the generator's `allow_upsert=True`.

### `DcimGenericDevice` (existing generic, gains one relationship)

Defined once, in `schemas/base/dcim.yml`. `used_by`: `ComputePhysicalServer`, `DcimDevice`,
`SecurityFirewall`. Already extended from another file by `tenancy/tenancy.yml`.

### `SecurityFirewall` (adopted, not modified)

Gains `static_routes` purely by inheritance. `schemas/security/security.yml` must stay
byte-identical to marketplace version 1.0.2.

## What each kind gains

Confirmed by running `infrahubctl schema check` against a live branch, not by reading the YAML:

| Kind | Effect | Intended? |
| --- | --- | --- |
| `SecurityFirewall` | gains `static_routes` | **Yes — the point of the cycle** |
| `DcimGenericDevice` | gains `static_routes` | Yes, it is where the relationship now lives |
| `ComputePhysicalServer` | gains `static_routes` | Accepted side effect; see below |
| `DcimDevice` | **no change at all** — keeps it by inheritance | Yes; nothing is removed |
| `RoutingVrfStaticRoute` | untouched | Yes; different kind, different purpose |

### The side effect, stated plainly

`ComputePhysicalServer` also inherits `DcimGenericDevice`, so a server can now hold a static
route. This is accepted rather than prevented, because the schema language offers no peer that
names exactly two kinds. The alternatives were:

1. **Widen to the generic** — one relationship, one identifier, one place to look. Chosen.
2. **Keep `DcimDevice` and add a second `SecurityFirewall.static_routes`** — needs a second
   identifier, makes `device` ambiguous, and gives cycle 026's renderer two relationships to
   traverse. Rejected.

Nothing creates a server static route, and nothing will unless someone writes one.

## Dependents

| Dependent | Relationship to this change | Required action |
| --- | --- | --- |
| `generators/backfill_structured_config.py` | **Writes this kind on every run**, `client.create(RoutingStaticRoute, device=<DcimDevice id>)` then `save(allow_upsert=True)` | Must keep working and stay idempotent. A `DcimDevice` id is still valid for a generic peer |
| `src/solution_arista_avd/protocols.py` | Generated; contains `class RoutingStaticRoute` | Regenerate, do not hand-edit |
| `schema.graphql` | Generated | Regenerate |
| `transforms/frr_config.gql` | Reads `WanSite.static_routes` → `RoutingVrfStaticRoute`, a **different kind** | Should be unaffected; SC-003 proves it rather than assuming it |
| `menus/menu.yml` | Lists `RoutingStaticRoute` and `RoutingVrfStaticRoute` by kind | No change — kind names are unchanged |
| `tests/unit/test_backfill_structured_config.py` | Mocks `client.create`; never touches the real schema | No change needed, and no evidence provided either — see R7 |

## Validation rules

Each is an acceptance scenario in the spec, and each was already demonstrated in
[research.md](./research.md) R5 against a live branch:

1. A `RoutingStaticRoute` whose `device` is `fw1` is accepted.
2. A `RoutingStaticRoute` whose `device` is a `DcimDevice` is still accepted.
3. A `RoutingStaticRoute` with no `device` is rejected — `optional: false` holds.
4. A second route with the same `prefix` and `vrf` on the same device is rejected.
5. `fw1.static_routes` resolves; so does an existing fabric device's.

## Not in this cycle

- The eight route objects (cycle 025).
- The `routing-options` template and query (cycle 026).
- `RoutingVrfStaticRoute`, `WanSite`, and everything the WAN reaches through them.
- Any attribute addition. The comment each route carries has a home already.
