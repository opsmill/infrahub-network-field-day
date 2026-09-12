# Implementation Plan: Device-Level Static Routes for the Perimeter Firewall

**Branch**: `024-firewall-static-routes` | **Date**: 2026-09-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-firewall-static-routes/spec.md`

## Summary

One relationship peer widens from `DcimDevice` to `DcimGenericDevice`, its reverse side moves to
match, two generated files are regenerated, and a schema contract test appears for a file that
has never had one. That lets the perimeter firewall own static routes, which cycle 025 will seed
and cycle 026 will render as the twelve-line `routing-options` stanza the junos artifact is
currently missing.

The schema work itself is about six lines of YAML. The plan is longer than that because Phase 0
found the change touches a kind a generator writes to on every run, and found that nothing in the
test suite pins the thing being changed.

## Phase 0 in one paragraph

The riskiest question — *does Infrahub accept an in-place peer widening on a schema with live
data?* — was answered by running it, not by reasoning. The edit was applied to a scratch copy,
checked, loaded onto a real branch, probed through GraphQL, and reverted. It passes, and all five
behavioural acceptance scenarios in the spec were demonstrated before implementation started
([research.md](./research.md) R5). Two findings changed the plan: `RoutingStaticRoute` is **not**
unused as the spec assumed (R6), and the green test suite is **not** evidence the change is right
(R7).

### The assumption Phase 0 overturned

The spec asserted that nothing seeds `RoutingStaticRoute`, from a search of `objects/`. The search
was correct; the conclusion was not. Eleven objects exist on `main`, created by the
**`backfill-structured-config` generator** from AVD structured configs. The decision survives —
R5 demonstrated the widening works with all eleven present — but the risk profile does not:
Constitution principle II is now in scope, and SC-003 grew to cover the generator.

That is the sixth cycle running in which a claim was wrong until measured, and the same shape
every time: a conclusion about the whole system drawn from evidence about one directory. The spec
has been amended in place and the withdrawal recorded rather than quietly edited.

### The gate that did not exist

`uv run pytest tests/unit` passes 998 with the change applied. That proves very little. Ten
`*_schema_contract.py` modules exist and **none** reads `routing/routing.yml`; the one module
mentioning `RoutingStaticRoute` mocks `client.create` and never touches the schema. The suite
would pass just as happily with the peer widened to the wrong kind. Hence a new contract test,
and a quickstart step that requires checking it **fails** when the peer is reverted.

## Technical Context

**Language/Version**: YAML schema definitions; Python >=3.11,<3.14 for the contract test.

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]` 1.22.0. No changes.

**Storage**: the Infrahub graph. Eleven existing `RoutingStaticRoute` objects, untouched.

**Testing**: `pytest`. One new module, `tests/unit/test_routing_schema_contract.py`, which reads
the YAML and needs no server.

**Target Platform**: local Infrahub stack via Docker Compose.

**Project Type**: Infrahub repository — schemas, generators, transforms, checks, object data.

**Performance Goals**: N/A.

**Constraints**: `schemas/security/security.yml` stays byte-identical to marketplace 1.0.2;
existing `RoutingStaticRoute` data keeps resolving; the backfill generator stays idempotent.

**Scale/Scope**: 1 schema file, ~6 lines changed, 2 regenerated files, 1 new test module, 1 doc
correction.

**Dependencies**: none outstanding. Cycles 020–023 are merged and pushed.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1. Result recorded below.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ This cycle *is* the schema change, and it lands before the objects (025) and the renderer (026) that need it. `routing/routing.yml` is the repository's own file, so no `*_extensions.yml` indirection. The adopted `security/security.yml` is not touched — `SecurityFirewall` gains the relationship by inheritance. |
| **II. Idempotent Operations** | ⚠️ **In scope, and only because Phase 0 looked.** `backfill-structured-config` creates `RoutingStaticRoute` with `save(allow_upsert=True)`, which resolves against the uniqueness constraint naming `device`. The constraint is unchanged, but "unchanged" is a claim that needs testing. `$infrahub-test-generator-idempotence` is not installed here, so the approved non-live alternative is quickstart §5: run the generator twice on a branch and **count** objects rather than read the log. Documented exception, per the principle's own escape clause. |
| **III. Type Safety** | ✅ `protocols.py` and `schema.graphql` are regenerated from the schema, never hand-edited. No `.gql` query changes in this cycle. |
| **IV. Test-Required Quality** | ✅ **Improved by this cycle rather than merely satisfied.** A new contract test covers a file that had none, and the quickstart requires proving it fails on a reverted peer. The integration suite is the same documented exception as cycles 020–023 — see below. |
| **V. Convention-Based Structure** | ✅ `tests/unit/test_routing_schema_contract.py` matches the ten existing `*_schema_contract.py` modules. The `DcimGenericDevice` extension entry matches the shape `tenancy/tenancy.yml` already uses. |

### Integration testing

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–023. The
constitution's escape clause applies and **the pull request must say so explicitly**.

For this cycle the non-live alternative is unusually strong: every behavioural clause (B1–B5) was
already demonstrated against a running Infrahub in Phase 0, before any implementation existed.
[quickstart.md](./quickstart.md) repeats them against the real change.

**No unjustified violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/024-firewall-static-routes/
├── plan.md              # This file
├── spec.md              # Amended after Phase 0 — Assumption 2 withdrawn, SC-003 widened, SC-010 added
├── research.md          # Phase 0 — seven findings, one withdrawal
├── data-model.md        # Phase 1 — the relationship before and after, and what depends on it
├── quickstart.md        # Phase 1 — ten validation steps
├── contracts/
│   └── schema-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code (repository root)

```text
schemas/routing/routing.yml               # EDIT — peer widened; reverse side moved
src/solution_arista_avd/protocols.py      # REGENERATE
schema.graphql                            # REGENERATE (see the export-schema trap below)
tests/unit/test_routing_schema_contract.py # NEW — the gate that did not exist
AGENTS.md                                 # EDIT — correct the "schema does not have" sentence
.infrahub.yml                             # EDIT — the junos artifact comment says "pending a schema cycle"
```

**Structure Decision**: no new schema file. Adding `routing_extensions.yml` to hold an override
would be the wrong instinct — that pattern exists for adopted files this repository must not
edit, and `routing/routing.yml` is not one.

## Implementation sequence

The test goes in before the change, because the point of R7 is that the suite currently cannot
tell the difference.

1. **Write `tests/unit/test_routing_schema_contract.py`** against C1–C6, asserting the peer is
   `DcimGenericDevice`. It **fails** at this point. That failure is the evidence the test works.
2. **Edit `schemas/routing/routing.yml`** — widen the peer, move the reverse relationship into a
   `DcimGenericDevice` extension entry, leave the other four `DcimDevice` relationships alone.
   Comment why, in the file: the next reader needs to know a firewall is not a `DcimDevice`.
3. **The contract test passes.** Revert the peer by hand once and confirm it fails again, then
   restore. Quickstart §7.
4. **`infrahubctl schema check` then `schema load`** on `fw-routes`, and read the diff for the
   four expected kinds and no `DcimDevice` entry.
5. **Probe the five behaviours** (B1–B5), then delete the probe object.
6. **Generator idempotence** — quickstart §5, counting rather than reading the log.
7. **`frr_config` regression** — quickstart §6.
8. **Regenerate `protocols.py`**, and `schema.graphql` *after* merge — see the trap below.
9. **Correct the record**: `AGENTS.md`'s claim that the schema lacks a device-level static route,
   and the `.infrahub.yml` comment saying `routing-options` is "pending a schema cycle".
10. **`uv run invoke test` and `uv run invoke lint`.**
11. **Verify the adopted schema is unmodified** against the marketplace.

### The `export-schema` trap, carried forward from cycle 023

`infrahubctl graphql export-schema` has **no `--branch` flag**. It exports Infrahub `main`.

Cycle 023 worked around that by loading its schema into `main` mid-cycle, and that is precisely
what made its Infrahub branch merge fail: `main` and the branch each ended up with their own copy
of the new attributes, and merging tried to create a second `SchemaAttribute` of each name.

So: **do not load this cycle's schema into `main` to regenerate `schema.graphql`.** Either
regenerate after the merge, or accept that the file lags one cycle. This is the first cycle to
know about the trap in advance; leaving it unrecorded would guarantee repeating it.

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| **The suite cannot detect a wrong peer** | **Realised** — this is today's state, R7 | The new contract test, plus a required check that it fails on a reverted peer |
| **The backfill generator breaks or stops being idempotent** | Medium, and the highest-impact | R6 put it in scope. Quickstart §5 runs it twice and counts objects |
| Reverse side left on `DcimDevice` while the forward side moves | Medium — silently produces two one-way relationships, nothing errors | C3 pins that both ends share `device__static_route`; C4 pins that `DcimDevice` does not also declare it |
| The peer widening needs a data migration | Low | Disproved in R5: loaded onto a branch holding all eleven existing objects, no migration, no error |
| `ComputePhysicalServer` gains `static_routes` | **Certain, and accepted** | Recorded in the spec's Edge Cases and data-model. No peer names exactly two kinds; the alternative was a second ambiguous relationship |
| `schema.graphql` regenerated from the wrong branch | Medium — it bit cycle 023 | Named explicitly above; step 8 defers it past merge |
| The adopted security schema is edited by accident | Low, high severity | Quickstart §9 diffs against the marketplace |

## Complexity Tracking

No constitution violations require justification. This section is intentionally empty.
