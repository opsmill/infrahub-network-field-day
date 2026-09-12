# Schema Contract: `RoutingStaticRoute.device`

**Cycle**: 024 | **Consumed by**: `tests/unit/test_routing_schema_contract.py` (new)

This contract exists because nothing currently pins it. Ten schema-contract test modules exist
and none reads `schemas/routing/routing.yml`; the only module that mentions `RoutingStaticRoute`
mocks the client and never touches the schema. The suite therefore passes whether this
relationship is right or wrong — see [research.md](../research.md) R7.

Each clause below is an assertion the new test module must make by reading the YAML.

## C1 — The forward relationship

`RoutingStaticRoute` declares exactly one relationship named `device`, with:

| Property | Required value | Why it is pinned |
| --- | --- | --- |
| `peer` | `DcimGenericDevice` | The whole point of the cycle. A narrowing back to `DcimDevice` silently re-excludes the firewall |
| `kind` | `Attribute` | A `Generic`-kind relationship would change how it is stored and queried |
| `cardinality` | `one` | A route has one owning device |
| `optional` | `false` | A route with no device is meaningless. Verified rejected in R5 |
| `identifier` | `device__static_route` | Must match the reverse side exactly |

## C2 — The reverse relationship

The `extensions:` block declares a `DcimGenericDevice` entry containing a `static_routes`
relationship with:

| Property | Required value |
| --- | --- |
| `peer` | `RoutingStaticRoute` |
| `kind` | `Generic` |
| `cardinality` | `many` |
| `optional` | `true` |
| `identifier` | `device__static_route` |

## C3 — The two ends agree

The identifier on C1 and the identifier on C2 are the same string. This is stated separately from
C1 and C2 because it is the specific failure the Infrahub identifier rule warns about: mismatched
identifiers silently produce two one-way relationships instead of one bidirectional one, and
nothing errors.

## C4 — `static_routes` is not also declared on `DcimDevice`

The `DcimDevice` extension entry must **not** contain a `static_routes` relationship. It keeps
the relationship by inheriting `DcimGenericDevice`; declaring it in both places would be two
declarations of one identifier.

`DcimDevice`'s other four relationships — `bgp_peer_groups`, `bgp_neighbors`, `prefix_lists`,
`route_maps` — must still be present. This clause guards against the move taking neighbours with
it.

## C5 — `RoutingVrfStaticRoute` is untouched

`RoutingVrfStaticRoute` (in `schemas/routing/vrf_services.yml`) keeps its own relationships and
identifiers. It is a different kind for VRF-scoped routes, reached through `WanSite`, and
`transforms/frr_config.py` depends on it. Pinned so that a future "tidy-up" cannot merge the two
kinds without the test objecting.

## C6 — Display and uniqueness survive the widening

| Property | Required value |
| --- | --- |
| `human_friendly_id` | `[device__name__value, prefix__value]` |
| `display_label` | `prefix__value` |
| `uniqueness_constraints` | `[[device, prefix__value, vrf__value]]` |

`human_friendly_id` reads through the relationship to `name`, which `DcimGenericDevice` carries.
The uniqueness constraint is load-bearing beyond display: the backfill generator's
`save(allow_upsert=True)` resolves against it, so a change here would break generator
idempotence rather than merely a label.

## C7 — The adopted schema is unmodified

`schemas/security/security.yml` is byte-identical to marketplace `infrahub/security` 1.0.2.
`SecurityFirewall` gains `static_routes` only by inheritance; this cycle never edits the file.

Verified by the diff command in `schemas/MARKETPLACE.md` rather than by a unit test, since it
needs the marketplace.

## Behavioural clauses — proven live, not unit-testable

These need a running Infrahub and are covered by [quickstart.md](../quickstart.md) rather than by
the contract test. All five were already demonstrated in R5 before implementation began.

| # | Behaviour |
| --- | --- |
| B1 | A route with `device: fw1` (a `SecurityFirewall`) is accepted |
| B2 | A route with a `DcimDevice` device is still accepted |
| B3 | A route with no device is rejected |
| B4 | A duplicate `prefix`+`vrf` on the same device is rejected |
| B5 | `fw1.static_routes` and a fabric device's `static_routes` both resolve |

## Consumer clauses

| # | Clause |
| --- | --- |
| D1 | `generators/backfill_structured_config.py` still creates static routes, and a second run creates no duplicate |
| D2 | `transforms/frr_config.py` renders all six FRR configurations byte-for-byte as before |
| D3 | `src/solution_arista_avd/protocols.py` and `schema.graphql` are regenerated, and `RoutingStaticRoute`'s peer reads as the generic in both |
