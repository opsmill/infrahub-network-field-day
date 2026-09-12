# Phase 0 Research: Device-Level Static Routes for the Perimeter Firewall

**Cycle**: 024 | **Date**: 2026-09-12 | **Branch**: `024-firewall-static-routes`

Seven findings. One overturns an assumption written into this cycle's own spec, and it is the
reason the plan's testing section is larger than a one-line schema change would suggest.

---

## R1 — `RoutingStaticRoute` exists and needs no new attributes

**Decision**: reuse the kind. Define nothing.

`schemas/routing/routing.yml` already defines `RoutingStaticRoute` with `prefix`, `gateway`,
`next_hop`, `interface`, `distance`, `tag`, `route_name` and `vrf` (default `"default"`),
`human_friendly_id: [device__name__value, prefix__value]`, `display_label: prefix__value` and
`uniqueness_constraints: [[device, prefix__value, vrf__value]]`.

The firewall's eight routes need `prefix`, `next_hop` and a home for the `/* … */` comment each
one carries. `route_name`, labelled "Route Description", is that home.

**Alternatives considered**: a new `SecurityStaticRoute` kind — rejected, it would duplicate an
existing model and give the next renderer two kinds to read.

---

## R2 — `routing/routing.yml` is not marketplace-adopted, so it can be edited directly

`schemas/MARKETPLACE.md` lists four adopted files: `security/security.yml`,
`cluster/cluster.yml`, `circuit/circuit.yml`, `tenancy/tenancy.yml`. `routing/routing.yml` is
this repository's own.

This is the difference between an ordinary edit and an `*_extensions.yml` workaround. It is also
why the spec's first draft was corrected: it claimed only one file was adopted.

---

## R3 — The blocker is one relationship peer, and `DcimGenericDevice` is the right widening

`RoutingStaticRoute.device` peers `DcimDevice`. Queried from the live schema:

```text
SecurityFirewall inherit_from: DcimGenericDevice, DcimPhysicalDevice,
                               CoreArtifactTarget, SecurityPolicyAssignment
DcimDevice       inherit_from: CoreArtifactTarget, DcimGenericDevice, DcimPhysicalDevice
DcimGenericDevice used_by:     ComputePhysicalServer, DcimDevice, SecurityFirewall
```

`SecurityFirewall` does not inherit `DcimDevice`, so no static route can name `fw1`. Both kinds
inherit `DcimGenericDevice`, which is defined once, in `schemas/base/dcim.yml`, and carries
`name` — which the static route's `human_friendly_id` reads.

`DcimPhysicalDevice` was considered as a narrower peer, since `ComputePhysicalServer` might not
inherit it. Rejected: it is a physicality distinction, not a routing one, and a virtual firewall
or router would then be excluded for no reason.

---

## R4 — Extending `DcimGenericDevice` from another file is established practice here

`schemas/tenancy/tenancy.yml` already does it:

```yaml
extensions:
  nodes:
    - kind: DcimGenericDevice
      relationships:
        - name: tenant
          peer: OrganizationTenant
          ...
```

That file is one of the four adopted from the marketplace, so the pattern is not merely
tolerated locally — it is what the published schema itself does. The reverse `static_routes`
relationship moves into the same shape.

---

## R5 — VERIFIED BY RUNNING: the change passes `schema check` and behaves as intended

The edit was applied to a scratch copy of `routing.yml`, checked and loaded against a real
Infrahub branch (`fw-routes`), probed, then reverted. Not reasoned about — run.

`infrahubctl schema check schemas/ --branch fw-routes`: all 38 files valid. The diff:

| Kind | Change |
| --- | --- |
| `RoutingStaticRoute` | `device` → `peer` changed |
| `DcimGenericDevice` | gains `static_routes` |
| `SecurityFirewall` | gains `static_routes` ← the goal |
| `ComputePhysicalServer` | gains `static_routes` ← the accepted side effect |

`DcimDevice` **does not appear in the diff at all**, and every `removed:` block in it is empty.
Nothing is lost: `DcimDevice` keeps `static_routes` by inheritance rather than by declaration.

Behaviour after loading, probed through GraphQL:

| Probe | Result |
| --- | --- |
| Create a route with `device: fw1` (a `SecurityFirewall`) | **accepted** |
| Create the same prefix again on `fw1` | **rejected** — uniqueness holds |
| Create a route with no device | **rejected** — `device is mandatory` |
| Read `fw1.static_routes` | returns the route |
| Read an existing `DcimDevice`'s `static_routes` | still resolves |

Every acceptance scenario in the spec's US1 and US2 is therefore already demonstrated against a
live instance, before implementation starts. The probe route was deleted afterwards.

---

## R6 — CORRECTION: `RoutingStaticRoute` is populated, and the spec said it was not

**This overturns Assumption 2 of [spec.md](./spec.md).**

The spec states: *"Nothing seeds `RoutingStaticRoute` today, verified by searching `objects/`. …
So there is no data migration, and SC-003 is a regression guard rather than a migration test."*

The search was real and its result was correct — `objects/` seeds none. The **conclusion** drawn
from it was wrong, because `objects/` is not the only thing that creates data. Counted live:

```text
main       RoutingStaticRoute count = 11
```

Eleven routes, on fabric spines and leaves, created by the **`backfill-structured-config`
generator** (`generators/backfill_structured_config.py:499`):

```python
route = await self.client.create(RoutingStaticRoute, **sr_attrs)
self._set_source(route, avd_source)
await route.save(allow_upsert=True)
```

It reads static routes out of AVD structured configs and writes them with `device` set to a
`DcimDevice` id.

**What this changes.** Not the decision — R5 demonstrated the widening works with those eleven
objects present, and a `DcimDevice` id remains valid for a `DcimGenericDevice` peer, so this is a
widening rather than a retype and needs no data migration. What it changes is the **risk**: this
cycle touches a kind a generator writes to on every run, and `allow_upsert=True` depends on the
uniqueness constraint that names `device`. Constitution principle II (Idempotent Operations) is
therefore in scope, and SC-003 has to cover the generator, not only `frr_config`.

**Why it was missed.** `grep -rln "RoutingStaticRoute" objects/` returned nothing and the search
stopped there. Generators were never searched. This is the sixth cycle running in which a claim
was wrong until it was measured, and the same failure shape every time: a conclusion drawn from
a read that did not cover its own claim. The spec asserted something about *the whole system*
from evidence about *one directory*.

---

## R7 — Nothing pins this kind, so the passing suite proves little

`uv run pytest tests/unit` passes 998 with the change applied. That is worth almost nothing as
evidence, and saying so is the point of this finding.

- No `tests/unit/*_schema_contract.py` covers `routing/routing.yml`. There are ten contract test
  modules; none reads this file.
- `tests/unit/test_backfill_structured_config.py` is the only module that mentions
  `RoutingStaticRoute`, and it **mocks `client.create`**, asserting the call shape
  (`prefix=…, device="dev-1", …`). It never touches the real schema, so it cannot notice a peer
  change in either direction.

So the suite would pass just as happily if the peer were widened to something wrong. The cycle
needs a new contract test — `tests/unit/test_routing_schema_contract.py` — that reads the YAML
and pins the peer, the cardinality, the mandatory flag, the shared identifier, and the fact that
`RoutingVrfStaticRoute` is untouched. Without it, SC-001 and SC-008 rest on a manual check.

---

## Summary of decisions

| # | Decision | Rationale |
| --- | --- | --- |
| R1 | Reuse `RoutingStaticRoute`; add no attribute | Everything the eight routes need already exists |
| R2 | Edit `routing/routing.yml` directly | Not marketplace-adopted |
| R3 | Widen the peer to `DcimGenericDevice` | The one generic both `DcimDevice` and `SecurityFirewall` inherit |
| R4 | Move the reverse side into a `DcimGenericDevice` extension block | The pattern `tenancy.yml` already uses |
| R5 | Apply in place; no `state: absent` migration | Demonstrated on a live branch with the eleven existing objects present |
| R6 | Treat the generator as in scope | It writes this kind on every run and upserts on a constraint naming `device` |
| R7 | Add a routing schema contract test | Nothing currently pins the kind; the green suite is not evidence |

## Spec amendments this research requires

1. **Assumption 2 is withdrawn and replaced.** `RoutingStaticRoute` holds eleven live objects,
   generator-created. The conclusion that survives is narrower: no *data migration* is needed,
   because a widening keeps existing `DcimDevice` references valid — demonstrated in R5, not
   assumed.
2. **SC-003 is widened** from "`frr_config` still renders" to include the backfill generator
   still creating and upserting static routes idempotently.
3. **A new success criterion** covers R7: the routing schema contract test exists and pins the
   peer, so a future change cannot silently narrow or re-widen it.
