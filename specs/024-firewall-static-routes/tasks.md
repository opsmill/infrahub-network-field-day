# Tasks: Device-Level Static Routes for the Perimeter Firewall

**Cycle**: 024 | **Branch**: `024-firewall-static-routes` | **Infrahub branch**: `fw-routes`
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/schema-contract.md](./contracts/schema-contract.md),
[quickstart.md](./quickstart.md)

## Why the test tasks come first

Not house style — a finding. [research.md](./research.md) R7 established that **nothing in this
repository pins the relationship this cycle changes**: ten `*_schema_contract.py` modules exist
and none reads `schemas/routing/routing.yml`, and the only module mentioning `RoutingStaticRoute`
mocks `client.create` so it never touches the schema. The full suite passes with the peer widened
to the *wrong* kind.

So T005–T008 write a test that **fails**, and T012 proves it fails for the right reason before
anything downstream is believed.

## Phase 1: Setup

- [X] T001 Confirm the working tree is clean and `schemas/routing/routing.yml` matches `main` — Phase 0 applied this change to a scratch copy and reverted it, so verify with `git diff schemas/` before starting
- [X] T002 Confirm the `fw-routes` Infrahub branch still exists with `uv run infrahubctl branch list`; it was created during Phase 0 and re-loading onto it is idempotent
- [X] T003 Record the pre-change baseline: `uv run pytest tests/unit -q` (expect 998 passed) and the live `RoutingStaticRoute` count on `main` (expect 11), so T027 and T031 have something to compare against
- [X] T004 Export `INFRAHUB_API_TOKEN` for this session — reads work anonymously, writes do not

## Phase 2: Foundational — the gate that does not exist yet

**Blocking**: every later phase depends on this, because without it nothing can tell a correct
peer from an incorrect one.

- [X] T005 Create `tests/unit/test_routing_schema_contract.py` following the shape of the ten existing `tests/unit/test_*_schema_contract.py` modules — load `schemas/routing/routing.yml` as YAML and expose the `RoutingStaticRoute` node and the `extensions.nodes` entries as fixtures
- [X] T006 [P] Add contract clause C1 to `tests/unit/test_routing_schema_contract.py`: `RoutingStaticRoute.device` has `peer: DcimGenericDevice`, `kind: Attribute`, `cardinality: one`, `optional: false`, `identifier: device__static_route`
- [X] T007 [P] Add contract clauses C2 and C3 to `tests/unit/test_routing_schema_contract.py`: the `DcimGenericDevice` extension entry declares `static_routes` (`peer: RoutingStaticRoute`, `kind: Generic`, `cardinality: many`, `optional: true`), and **both ends carry the same identifier string** — the specific failure mode the Infrahub identifier rule warns about, since mismatched identifiers silently create two one-way relationships and nothing errors
- [X] T008 [P] Add contract clauses C4, C5 and C6 to `tests/unit/test_routing_schema_contract.py`: `DcimDevice` does **not** also declare `static_routes` but still declares `bgp_peer_groups`, `bgp_neighbors`, `prefix_lists` and `route_maps`; `RoutingVrfStaticRoute` in `schemas/routing/vrf_services.yml` is untouched; and `human_friendly_id`, `display_label` and `uniqueness_constraints` are unchanged
- [X] T009 Run `uv run pytest tests/unit/test_routing_schema_contract.py -q` and confirm it **FAILS**. A passing test here means it is not asserting what it claims to

**Checkpoint**: a red test that names the exact peer the cycle is about to introduce.

---

## Phase 3: User Story 1 — A firewall can own a static route (P1)

**Goal**: `RoutingStaticRoute.device` accepts a `SecurityFirewall`.

**Independent test**: create a route with `device: fw1`; confirm it is accepted, and confirm a
route with no device is still rejected.

- [X] T010 [US1] Widen `RoutingStaticRoute.device` from `peer: DcimDevice` to `peer: DcimGenericDevice` in `schemas/routing/routing.yml`, leaving `kind`, `cardinality`, `optional`, `identifier` and `order_weight` untouched
- [X] T011 [US1] Add a comment above that relationship in `schemas/routing/routing.yml` explaining *why* the peer is the generic: `SecurityFirewall` inherits `DcimGenericDevice` but not `DcimDevice`, so a concrete peer silently excludes the firewall. The next reader cannot recover that from the YAML
- [X] T012 [US1] Run `uv run pytest tests/unit/test_routing_schema_contract.py -q` — C1 now passes. Then **revert the peer by hand, confirm it fails again, and restore it**. A contract test that passes either way is worse than none ([quickstart.md](./quickstart.md) §7)
- [X] T013 [US1] Run `uv run infrahubctl schema check schemas/ --branch fw-routes` and read the diff: exactly `RoutingStaticRoute`, `DcimGenericDevice`, `SecurityFirewall` and `ComputePhysicalServer` change, no `DcimDevice` entry appears, and every `removed:` block is empty
- [X] T014 [US1] Run `uv run infrahubctl schema load schemas --branch fw-routes`. Loading with the eleven existing `RoutingStaticRoute` objects present **is** the migration test — a widening that needed a migration fails here
- [X] T015 [US1] Verify behaviour B1 on the branch: a `RoutingStaticRoute` with `device: fw1` is created, and the stored `device.node.__typename` reads `SecurityFirewall`
- [X] T016 [US1] Verify behaviour B3: a `RoutingStaticRoute` created with no `device` is rejected, and the error names `device` as mandatory
- [X] T017 [US1] Verify behaviour B4: a second route with the same `prefix` and `vrf` on `fw1` is rejected by the uniqueness constraint

**Checkpoint**: the firewall can hold a static route; SC-002, SC-005 and SC-006 are demonstrated.

---

## Phase 4: User Story 2 — The routes are reachable from the device (P2)

**Goal**: both ends of `device__static_route` name the same peer, so the relationship is
navigable from the device side — which is what cycle 026's renderer will traverse.

**Independent test**: read `fw1.static_routes`; read an existing fabric device's `static_routes`.

- [X] T018 [US2] Remove the `static_routes` relationship from the `- kind: DcimDevice` entry in `schemas/routing/routing.yml`, leaving `bgp_peer_groups`, `bgp_neighbors`, `prefix_lists` and `route_maps` exactly where they are
- [X] T019 [US2] Add a `- kind: DcimGenericDevice` entry to the same `extensions.nodes` block containing `static_routes` with its body copied verbatim, matching the shape `schemas/tenancy/tenancy.yml` already uses to extend `DcimGenericDevice`
- [X] T020 [US2] Run `uv run pytest tests/unit/test_routing_schema_contract.py -q` — C2, C3 and C4 now pass, so the whole contract test is green
- [X] T021 [US2] Reload the schema onto `fw-routes` and verify behaviour B5: `fw1.static_routes` resolves the route from T015, and an existing `DcimDevice` still resolves its own — `DcimDevice` keeps the relationship by inheritance, not by declaration
- [X] T022 [US2] Delete the probe route created in T015 so the branch carries only the schema change, and confirm `RoutingStaticRoute` is back to 11 on the branch

**Checkpoint**: SC-004 demonstrated; the relationship is bidirectional and declared once.

---

## Phase 5: User Story 3 — The record stops misleading the next cycle (P3)

**Goal**: the two places that state the schema lacks a device-level static route stop saying so.

**Independent test**: read `AGENTS.md` and `.infrahub.yml`; neither claims a missing kind.

- [X] T023 [P] [US3] Correct the `junos_config` section of `AGENTS.md`: `routing-options` is not blocked by "a device-level static route the schema does not have" — `RoutingStaticRoute` always existed, the blocker was its peer, and that is now closed. Say what remains (seed data in 025, rendering in 026)
- [X] T024 [P] [US3] Correct the `junos_config` artifact comment in `.infrahub.yml`, which says `routing-options` is "pending a schema cycle" — it is now pending objects and a renderer
- [X] T025 [P] [US3] Note in `docs/docs/developer-guide/schemas.md` that `RoutingStaticRoute` peers the device generic, so a firewall or a server can own one, and that `RoutingVrfStaticRoute` is the separate VRF-scoped kind the WAN uses — the two are easy to confuse and nothing currently distinguishes them for a reader

**Checkpoint**: SC-009 met; cycle 025 can be planned from an accurate record.

---

## Phase 6: Polish & Cross-Cutting Concerns

### Consumers — the half of the cycle Phase 0 added

- [X] T026 Run `uv run pytest tests/unit/test_backfill_structured_config.py -q`. Note that this module mocks `client.create`, so it proves the call shape and **not** that the schema accepts it — T027 is the real test
- [X] T027 Verify generator idempotence — **done differently, and the deviation is the finding.** `infrahubctl generator backfill-structured-config` fails in this environment (`AttributeError: 'InfrahubNode' object has no attribute 'name'`) and fails **identically on a branch with the peer unchanged**, so it is pre-existing: the SDK CLI hard-codes `name` while this definition maps `name: artifact__name__value` and its target members have no `name`. The upsert path (`backfill_structured_config.py:499-501`) was driven directly instead, for a `SecurityFirewall` and a `DcimDevice`: both idempotent, same object, no duplicate. Counted, not read from the log
- [X] T028 Run `uv run pytest tests/unit/test_frr_config.py -q` — `frr_config` reads `RoutingVrfStaticRoute` through `WanSite`, a different kind, so this should be untouched. The task exists to prove that rather than assume it (D2)

### Generated files

- [X] T029 Regenerate `src/solution_arista_avd/protocols.py` with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py` and confirm `class RoutingStaticRoute` reflects the change. Never hand-edit
- [X] T030 `schema.graphql` regenerated **after the merge**, which is what the deferral was for: `export-schema` has no `--branch` flag, so running it before the merge would have exported the old schema, and loading the new one into `main` to work around that is exactly what broke cycle 023. Post-merge the export is correct and needs no workaround — `device: NestedEdgedDcimGenericDevice!`. Original task text: **Defer** regenerating `schema.graphql` until after the merge. `infrahubctl graphql export-schema` has **no `--branch` flag** — it exports Infrahub `main`. Loading this cycle's schema into `main` to work around that is exactly what made cycle 023's Infrahub merge fail on a `SchemaAttribute` uniqueness violation. Record in the commit that the file lags one cycle if it is not regenerated

### Gates

- [X] T031 Run `uv run invoke test` — 998 existing tests plus the new contract module, all green
- [X] T032 Run `uv run invoke lint` — ruff, ruff-format, yamllint, mypy and rumdl clean
- [X] T033 Verify the adopted schema is unmodified ([quickstart.md](./quickstart.md) §9): `diff <(uv run infrahubctl marketplace get infrahub/security --stdout) schemas/security/security.yml` produces no output (SC-007, C7)
- [~] T034 Run `$infrahub-run-integration-tests` — **not installed**, documented exception named in the commit. Original: Run `$infrahub-run-integration-tests`. If not installed, say so **explicitly** in the pull request as the constitution's documented exception — do not omit it silently. Note that for this cycle the non-live alternative is unusually strong: every behavioural clause was demonstrated against a running instance in Phase 0, before implementation existed

### Evidence and close-out

- [X] T035 Write `specs/024-firewall-static-routes/acceptance-evidence.md`: the schema-check diff, the five behavioural probes, the idempotence count, the FRR regression, and the red-then-green proof from T012
- [X] T036 Record in that file the assumption this cycle withdrew — Assumption 2 claimed `RoutingStaticRoute` was unused, and eleven generator-created objects existed — and that it was the sixth cycle running to state a system-wide claim from evidence about one directory
- [X] T037 Note the two follow-ups this cycle does not close: the `export-schema` `--branch` gap (T030's cause, and it will bite the next attribute-adding cycle too), and the five stale Infrahub branches, one of which errors on every repository sync
- [X] T038 Merged to `main` and the `fw-routes` Infrahub branch deleted, on the requester's instruction. The Infrahub merge succeeded first time, unlike cycle 023's — because this cycle never loaded its schema into `main` to regenerate `schema.graphql`, so there was no competing copy to conflict with

---

## Dependencies

```text
Phase 1 (Setup)
   └─> Phase 2 (Foundational: the red contract test)   ← BLOCKS EVERYTHING
          ├─> Phase 3 (US1, P1: forward peer)
          │      └─> Phase 4 (US2, P2: reverse side)   ← depends on US1
          ├─> Phase 5 (US3, P3: the record)            ← independent, can run any time after Phase 1
          └─> Phase 6 (Polish)                          ← needs US1 + US2
```

**US2 genuinely depends on US1**, unlike most story pairs. They are two halves of one
relationship: moving the reverse side while the forward side still peers `DcimDevice` would make
the two ends of `device__static_route` disagree, which is the silent failure C3 exists to catch.
They are separated into phases because they are separate assertions and separate lines in the
file, not because they can ship apart.

**US3 is genuinely independent** — it touches only prose and can be done at any point.

## Parallel opportunities

- **T006, T007, T008** — three contract clauses, same new file but disjoint test functions; write them together, then run once at T009
- **T023, T024, T025** — three different files, no shared state
- **T026 and T028** — two independent pytest modules
- Everything in Phase 3 and Phase 4 is strictly sequential: each task changes the same YAML file or depends on a reload of it

## Implementation strategy

**MVP is Phase 2 + Phase 3.** At T017 the firewall can own a static route and the cycle's
headline claim is demonstrated — but do not stop there, because a forward-only relationship is a
trap for cycle 026 rather than a partial delivery.

**The smallest honest increment is Phase 2 + 3 + 4**: about six lines of YAML, one new test
module, and both ends of the relationship agreeing.

Phases 5 and 6 are then documentation and proof. Phase 6's consumer tasks (T026–T028) are the
ones most likely to surface a real problem, because they cover the generator that writes this
kind on every run — which nothing in the spec knew about until Phase 0 counted the objects.

## Task summary

| Phase | Tasks | Story |
| --- | --- | --- |
| 1 Setup | T001–T004 | — |
| 2 Foundational | T005–T009 | — |
| 3 US1 | T010–T017 | P1 |
| 4 US2 | T018–T022 | P2 |
| 5 US3 | T023–T025 | P3 |
| 6 Polish | T026–T038 | — |
| **Total** | **38** | |
