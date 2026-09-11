# Implementation Plan: The WAN's Addressing

**Branch**: `021-wan-addressing-objects` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-wan-addressing-objects/spec.md`

## Summary

56 new objects and 25 relationship links, transcribed from `../lab/wan/tenants.yml`, filling the
four relationships cycle 020 created. One new object file, two edited. After this, every line of
the six rendered FRR configs has its data in the graph and the transform cycle can start.

Phase 0 changed the file layout and found five reference forms, four of which fail on the
obvious attempt. The most expensive: **an inline `data:` block for a cardinality-one
relationship must be a mapping, not a list**, and the list form — which is what the
`infrahub-managing-objects` skill documents — crashes the SDK with a Python traceback that names
neither the file nor the field. The repository's own `objects/33_nfd41_wan.yml` already uses the
correct form, which is why it loads while a faithful copy of the documented example does not.

The layout changed because a top-level `spec` block is a full upsert: adding `router_id` to a
device demands `status`, adding `bgp_sessions` to a site demands `lan_prefix` and `tenant`. The
spec proposed two new files; restating those fields in them would have duplicated lab data
across files, which is the precise failure this cycle exists to remove. So updates are edited
into the files that already define their objects, and only genuinely new objects go in a new
file — placed between the devices and the circuits, where the dependency chain requires.

## Technical Context

**Language/Version**: none. This cycle writes YAML under `objects/` and one Python test.

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]` 1.22.0 for `infrahubctl object
load`. No dependency changes.

**Storage**: the Infrahub graph. Object data only — no schema change.

**Testing**: `pytest`. A new `tests/unit/test_wan_addressing_objects.py` compares the object
files against the lab file in both directions and needs no server.

**Target Platform**: local Infrahub stack via Docker Compose.

**Project Type**: Infrahub repository — schemas, generators, transforms, checks, object data.

**Performance Goals**: N/A.

**Constraints**: every value must trace to `../lab/wan/tenants.yml`; no address may remain as
free text; every file idempotent; load order must hold across four files.

**Scale/Scope**: 1 file created, 2 edited, 1 test added. 56 objects, 25 links.

**Dependency**: cycle 020's schema. It is on branch `wan-addr`, not `main` — see Risks.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1. Result recorded below.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ Schema came first, in cycle 020. This cycle adds no schema and needs none — every kind, attribute and relationship it writes already exists. No protocol regeneration required. |
| **II. Idempotent Operations** | ✅ **Directly in scope.** `infrahubctl object load` upserts by HFID. §5 of [quickstart.md](./quickstart.md) loads twice and compares counts, explicitly *not* the log — the CLI prints "Created node" for an upsert, so reading the log would be a false positive. No generator changes, so `$infrahub-test-generator-idempotence` does not apply. |
| **III. Type Safety** | ✅ No Python beyond a test that parses YAML. No `.gql` query, no `*_query.py` model, no protocol change. |
| **IV. Test-Required Quality** | ⚠️ Unit coverage is planned and is the primary gate. The integration suite is the same documented exception as cycle 020 — see below. |
| **V. Convention-Based Structure** | ✅ `objects/31a_nfd41_wan_addressing.yml` keeps the numbered-prefix convention and the `nfd41_` naming. The `31a` position is required by the dependency chain, not chosen for tidiness, and a test pins it. |

### Integration testing

`$infrahub-run-integration-tests` is not installed in this environment, exactly as in cycle 020.
The constitution's escape clause applies and the pull request must say so explicitly rather than
omit it.

The non-live alternative here is stronger than 020's, because this cycle has data to check:
load into a fresh branch, run the four traversal queries, load again and compare counts. That is
§2 through §5 of the quickstart.

**No unjustified violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/021-wan-addressing-objects/
├── plan.md              # This file
├── research.md          # Phase 0 — eight findings, four of them failing forms
├── data-model.md        # Phase 1 — the 56 objects, field by field
├── quickstart.md        # Phase 1 — how to prove it worked
├── contracts/
│   └── object-contract.md   # Phase 1 — the five reference forms and the required graph
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code (repository root)

```text
objects/
├── 29_nfd41_offfabric_prefixes.yml   # the prefixes these addresses sit inside  (unchanged)
├── 31_nfd41_offfabric_devices.yml    # the seven routers                        (unchanged)
├── 31a_nfd41_wan_addressing.yml      # NEW — interfaces, addresses, ASNs,
│                                     #       BGP neighbours, VRFs, static route,
│                                     #       router IDs
├── 33_nfd41_wan.yml                  # EDIT — endpoint links, site sessions,
│                                     #        static-route link, prose removed
└── 37_nfd41_wan_services.yml         # EDIT — the two CUST_* VRFs move out

tests/unit/
└── test_wan_addressing_objects.py    # NEW — transcription parity against the lab file
```

**Structure Decision**: one new file at `31a`, not the two at `38`/`39` the spec proposed. The
name must sort after `31_nfd41_offfabric_devices.yml` (the devices interfaces hang off) and
before `32_nfd41_security.yml` and `33_nfd41_wan.yml` (the circuits and sites that name those
interfaces). Verified by sorting the real filenames. Everything else is an in-place edit,
because a top-level upsert restates mandatory attributes.

## Implementation sequence

1. **`objects/31a_nfd41_wan_addressing.yml`** — seven documents in dependency order: physical
   interfaces, virtual interfaces, addresses, ASNs, VRFs, static route, router IDs.
2. **Move the two `CUST_*` VRFs** out of `objects/37_nfd41_wan_services.yml`. Do this in the
   same commit as step 1, so the VRFs are never absent from the tree.
3. **`objects/33_nfd41_wan.yml`** — eight endpoint `interface` links, four sites' sessions,
   acme/dr's static route, the internet peering's two sessions.
4. **Remove the address prose** from the endpoint descriptions in the same file. Separate step
   from 3 so the diff shows the debt being repaid rather than burying it.
5. **`tests/unit/test_wan_addressing_objects.py`** — two-directional parity against the lab file,
   plus the guards in the contract's §7.
6. **Load into a fresh branch, twice**, and run the four traversal queries.
7. **`uv run invoke test` and `uv run invoke lint`.**
8. **Walk one rendered config end to end** (quickstart §8) to answer SC-009.

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| A stray dash under a cardinality-one `data:` block | **High** — every inline block here is cardinality one, and the skill documents the wrong shape | The contract states the form twice; a unit test asserts every such block is a mapping; the quickstart names the traceback |
| Cycle 020's schema is not on `main` | Certain, today | This cycle's branch must load `schemas/` before `objects/`. If 020 is merged first the step is redundant but harmless |
| `wan-addr` carries partial probe data from Phase 0 | Certain | Recorded in research R8/risk 1. **It must not be merged.** Use a fresh branch; nothing is lost, since its schema comes from git and its objects from `objects/` |
| Load order breaks silently if the file is renamed | Low | A unit test pins that `31a` sorts between `31` and `33` |
| A second static route would collide on a weak HFID | Not this cycle | `RoutingVrfStaticRoute` HFID is `[vrf__name__value]` while uniqueness is `[vrf, prefix, next_hop]` (R7). One route here. Recorded for the next statically attached site |
| Transcription drift from the lab file | Medium — 56 objects of hand-copied addresses | The test compares both directions, so an invented value fails as loudly as a missing one |

## Complexity Tracking

No constitution violations require justification. This section is intentionally empty.
