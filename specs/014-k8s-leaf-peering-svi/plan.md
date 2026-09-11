# Implementation Plan: k8s Leaf Peering SVIs

**Feature**: `specs/014-k8s-leaf-peering-svi` | **Branch**: `014-k8s-leaf-peering-svi`
**Spec**: [spec.md](./spec.md) | **Date**: 2026-09-10
**Infrahub branch**: `svi-model` | **Infrahub**: 1.10.6

## Summary

Add two `InterfaceVirtual` objects — a `Vlan110` SVI on each k8s leaf — each holding that leaf's
existing peering `IpamIPAddress`. This supplies the one missing edge that makes
`IpamIPAddress -> interface -> device` a complete traversal, which is what
`ClusterFabricPeering.peer_address` needs in order to become derivable the same way cycle 012
made `peer_asn` derivable.

The cycle adds **one object-data file** and changes **no schema, no generator, and no
transform**. Consuming the new edge is a follow-up cycle, deliberately kept separate so that this
cycle's entire regression surface is "two objects were added" and can be proved inert.

## Technical Context

| | |
| --- | --- |
| Artifact type | Object data (routed by `infrahub-speckit` `before_specify`/`before_plan` hooks) |
| Language | YAML seed data; Python for tests only |
| Node kinds added | `InterfaceVirtual` x2 |
| Schema changes | **None** — verified in research R1 |
| Generator changes | **None** — out of scope, spec FR-020 |
| Files added | `objects/36_nfd41_peering_svis.yml`, `tests/unit/test_peering_svi_seed_data.py` |
| Files modified | `objects/34_nfd41_cluster.yml` (annotation only, no values) |
| Regression oracle | Rendered Crossplane `FabricPeering`, normalised digest `0d800c9d5005b5fdb6b371bb5627d143` |
| Testing | `pytest tests/unit`; live queries on branch `svi-model` for evidence |

**No NEEDS CLARIFICATION remain.** Three candidate unknowns were resolved by verification before
the spec was written and are recorded in [research.md](./research.md) as R1, R2 and R3.

## Constitution Check

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ Compliant *by not applying*. The principle requires schema before code; here the schema already models everything needed. Research R1 records the verification, and R1's rejected alternative (making `EvpnSviNode.ip_address` a relationship) is the schema change that was deliberately *not* made. FR-019 and SC-008 make "no schema change" a checked outcome, not an assertion. |
| **II. Idempotent Operations** | ✅ No generator is added, so `$infrahub-test-generator-idempotence` does not apply. The seed data's idempotence is the relevant property and is measured by loading twice (SC-007). |
| **III. Type Safety** | ✅ No production Python is added. Tests parse YAML and are covered by `mypy` and `ruff` like the repo's existing seed-data tests. No `.gql` or query model changes, so no return types to regenerate. |
| **IV. Test-Required Quality** | ✅ Contract tests follow the existing `tests/unit/test_*_schema_contract.py` and `test_nfd41_seed_data.py` patterns. All five linters must pass. Integration tests: no Infrahub *code* changed, so the integration suite has nothing new to exercise; the live-query evidence in `acceptance-evidence.md` covers what integration coverage would have. This is a stated deviation, justified below. |
| **V. Convention-Based Structure** | ✅ Seed data goes in a numbered file under `objects/` at the next free sequence number (36). Test name matches the repo's `test_*_seed_data.py` convention. |

**Deviation to note for review**: Principle IV says integration tests MUST cover every Infrahub
code change. This cycle changes no Infrahub code — only data — so there is no code path to
exercise. Rather than add a hollow integration test, the cycle proves the data's behaviour
against a live instance and records the commands and output in `acceptance-evidence.md`. A
reviewer who disagrees should say so; the alternative is a test that asserts the loader loads.

## Project Structure

### Documentation (this feature)

```text
specs/014-k8s-leaf-peering-svi/
├── spec.md
├── plan.md                      <- this file
├── research.md                  <- Phase 0: R1-R8
├── data-model.md                <- Phase 1: the two objects, field by field
├── quickstart.md                <- Phase 1: how to re-verify
├── contracts/
│   └── object-contract.md       <- Phase 1: what a consumer may rely on
├── checklists/
│   └── requirements.md
├── tasks.md                     <- Phase 2 (speckit-tasks)
└── acceptance-evidence.md       <- Phase 3 (speckit-implement)
```

### Source (repository root)

```text
objects/
├── 34_nfd41_cluster.yml         <- MODIFIED: annotation only
└── 36_nfd41_peering_svis.yml    <- NEW

tests/unit/
└── test_peering_svi_seed_data.py  <- NEW

schemas/                         <- UNCHANGED (FR-019)
generators/                      <- UNCHANGED (FR-020)
transforms/                      <- UNCHANGED
```

## Phase 0 — Research

Complete. See [research.md](./research.md). The findings that shaped the design:

- **R1**: no schema change needed; `InterfaceVirtual` and `IpamIPAddress.interface` both exist.
- **R2** *(changed the design)*: `InterfaceVirtual` has **two** relationships to `IpamIPAddress`.
  Only `ip_addresses` (`interfacelayer3__ipamipaddress`) has a reverse side on the address node,
  so only it creates the traversal. Using the other one would look right and achieve nothing.
- **R3**: the SVI goes on `leaf-nfd41-pod1-1-*`, not the `k8s-leaf*` duplicates, because that is
  what `peer_device` points at.
- **R5**: every interface-enumerating consumer filters to `InterfacePhysical`; and every switch
  already carries an `InterfaceVirtual`, so this is not a new shape. Residual risk is closed by
  measuring an AVD render before/after, beyond the declared oracle.
- **R6**: new file at `36_`, because it must sort after `34_` which declares the addresses.

## Phase 1 — Design

Complete. [data-model.md](./data-model.md) fixes the two objects field by field, including the
fields deliberately left unset and why. [contracts/object-contract.md](./contracts/object-contract.md)
states what the follow-up cycle may rely on. [quickstart.md](./quickstart.md) is the re-verification
runbook.

## Execution strategy

Ordering is chosen so the regression oracle cannot be contaminated:

1. **Baseline before anything.** Render the Crossplane artifact on a clean `svi-model` and hash
   it. Establish it equals the cycle 011/012 digest before trusting it as an oracle. *(Done
   during research: the CLI's extra trailing newline had to be normalised away first, which is
   itself worth recording — an unreconciled mismatch here would have looked like a regression.)*
2. **Write the seed file**, then load schema and objects onto `svi-model`.
3. **Verify the traversal** with live queries before running any gate, so a fundamentally broken
   model is caught immediately rather than after a green test suite.
4. **Re-render and diff.** If it is not byte-identical, stop and report rather than proceed.
5. **Contract tests**, then the full gate set.
6. **Annotate** `34_nfd41_cluster.yml` — last, because it is the only edit to an existing file
   and keeping it separate makes the diff easy to confirm as comment-only.
7. **Evidence**, then clean up the Infrahub branch.

## Complexity Tracking

No constitution violations requiring justification. The one deviation (integration tests) is
recorded in the Constitution Check above with its rationale.

The cycle is deliberately smaller than it could be. Three larger changes were considered and
rejected into follow-ups, each recorded in research.md:

| Rejected | Where | Why deferred |
| --- | --- | --- |
| Make `EvpnSviNode.ip_address` a relationship | R1 | Schema change; would move AVD output via three call sites. Better model, needs its own cycle. |
| Wire the derivation into `generate_fabric_peering.py` | spec, out of scope | Keeps this cycle's regression surface to "data added". |
| Resolve the `k8s-leaf*` / `leaf-nfd41-*` device duplication | R3 | Pre-existing; fixing it touches cabling, groups and the containerlab topology. |
