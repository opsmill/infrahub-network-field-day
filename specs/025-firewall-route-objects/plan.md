# Implementation Plan: The Perimeter Firewall's Static Routes

**Branch**: `025-firewall-route-objects` | **Date**: 2026-09-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-firewall-route-objects/spec.md`

## Summary

One object file holding eight static routes, transcribed from
`../lab/configs/fw/vsrx/junos.conf` onto `fw1`, and one offline test module that checks them
against three independent sources. No schema change, no existing file edited.

Cycle 024 made the firewall able to own a route. This cycle puts its real forwarding decisions in
the graph. Cycle 026 renders them, taking the junos artifact from 573 to 585 of 677 lines.

## Phase 0 in one paragraph

The file was generated from the oracle, loaded onto a live branch, compared both ways, loaded
again, and read back — before this plan was written. It is correct, complete and idempotent, and
the eleven pre-existing fabric routes were untouched (11 → 19, and 19 again on reload). Two
findings shaped the design: the CRITICAL generic-relationship rule that appeared to forbid a
scalar `device: "fw1"` **does not apply** here (R2), and the converse of the address-book check
would have been **wrong** to assert (R5).

### The rule that looked like it applied, and does not

The Infrahub objects guidance marks generic relationship references as a CRITICAL failure, fixed
by an inline block naming the concrete kind — the pattern cycle 023 needed for the polymorphic
address book. Since cycle 024 made `device` peer `DcimGenericDevice`, it appeared to apply here
too.

Its precondition is that the generic has **no** `human_friendly_id`. `DcimGenericDevice` defines
`[name__value]`. Confirmed by loading, not by reading: the scalar form works. Taking the rule at
face value would have added eight unnecessary inline blocks and a precedent the next reader would
copy without the reason.

### The criterion that would have been wrong

Eight destinations map one-for-one onto address-book entries, which invites the converse: *every
address-book prefix has a route*. It is false, and it fails on five correct entries — `acme-hq`,
`acme-dr` and `globex-hq` sit inside `10.60.0.0/16`; `access-portal` sits inside
`10.112.0.0/16`; and `fabric-infra` is never a destination, appearing six times as a rule
`source_address` in the anti-spoofing rules. All thirteen book entries are accounted for in R5,
and the account closes: 8 + 3 + 1 + 1 = 13.

## Technical Context

**Language/Version**: YAML object data; Python >=3.11,<3.14 for the test module.

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]` 1.22.0. No changes.

**Storage**: the Infrahub graph. Eight new objects; the eleven existing ones untouched.

**Testing**: `pytest`. One new module, `tests/unit/test_fw_static_route_objects.py`, reading three
files and needing no server.

**Target Platform**: local Infrahub stack via Docker Compose.

**Project Type**: Infrahub repository — schemas, generators, transforms, checks, object data.

**Performance Goals**: N/A. Eight objects.

**Constraints**: exact transcription; no schema change; no existing object file edited; the
eleven fabric routes untouched; a second load must not duplicate.

**Scale/Scope**: 1 new object file (8 objects), 1 new test module, 0 edits to existing files.

**Dependencies**: cycle 024 is merged and pushed and its schema is live on Infrahub `main` —
verified, not assumed (R1).

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1. Result recorded below.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ The schema landed first, in cycle 024, and this cycle needs no further change — confirmed by loading the objects successfully against the live schema. `RoutingStaticRoute` is used as it stands. |
| **II. Idempotent Operations** | ✅ **In scope, and demonstrated.** `infrahubctl object load` upserts on the HFID `[device__name__value, prefix__value]`. A second load left `fw1.static_routes = 8` and the total at 19. Counted, not read from the log. No generator, so `$infrahub-test-generator-idempotence` does not apply. |
| **III. Type Safety** | ✅ No Python production code, no GraphQL query, no generated file. The test module reads YAML. Nothing to type against. |
| **IV. Test-Required Quality** | ✅ A new offline module covering C1–C8. The integration suite is the same documented exception as cycles 020–024 — see below. |
| **V. Convention-Based Structure** | ✅ `objects/32b_nfd41_fw_static_routes.yml` follows the numeric-prefix load order and the `31a_` precedent for an inserted file. The test module matches the existing offline modules. |

### Integration testing

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–024. The
constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative is [quickstart.md](./quickstart.md) steps 2–6, which were additionally
run during Phase 0 against a scratch branch before this plan existed.

**No unjustified violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/025-firewall-route-objects/
├── plan.md              # This file
├── spec.md              # Unamended — Phase 0 overturned nothing
├── research.md          # Phase 0 — seven findings, one self-correction
├── data-model.md        # Phase 1 — the eight objects and what checks them
├── quickstart.md        # Phase 1 — nine validation steps
├── contracts/
│   └── object-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code (repository root)

```text
objects/
└── 32b_nfd41_fw_static_routes.yml     # NEW — the eight routes

tests/unit/
└── test_fw_static_route_objects.py    # NEW — C1 to C8, offline
```

Two new files. Nothing else.

**Structure Decision**: a new file rather than an addition to `32_nfd41_security.yml`. The routes
are a routing kind, not a security kind, and that file is already 600 lines of firewall policy;
mixing a second kind into it would make both harder to read. `32b` keeps them adjacent without
merging them.

## Implementation sequence

The test goes in first, as in cycle 024 — but for a weaker reason, so it is worth being honest
about it. There is no claim here that nothing pins the data: the file will not exist yet, so the
test cannot pass. Writing it first is what makes the parser (C4) and the both-ways comparison
(C3) get written properly instead of being shaped to fit data already on disk.

1. **Write `tests/unit/test_fw_static_route_objects.py`** against C1–C8. It fails: no file yet.
2. **Write `objects/32b_nfd41_fw_static_routes.yml`** — eight routes, transcribed. Comment the
   file: what the source is, why `vrf` is absent, why `device` is a scalar.
3. **The test passes.** Then break one `next_hop` digit by hand and confirm **two** clauses fail,
   C3 and C6. If only one fails, the independent witness is not independent.
4. **Load onto `fw-routes-obj`** and check the counts: 11 → 19, `fw1.static_routes = 8`.
5. **Read the objects back** — `vrf = "default"` from the default, four attributes unset.
6. **Load again**; counts unchanged.
7. **`uv run invoke test` and `uv run invoke lint`** — `yamllint` covers `objects/`.
8. **Confirm nothing else changed**: no `schemas/` diff, no existing `objects/` file diff.
9. **Update the record**: `AGENTS.md` and `.infrahub.yml` currently say `routing-options` awaits
   "seed data and a template". After this cycle it awaits only the template.

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| **A typo in a `next_hop`** | Medium, and the oracle comparison cannot catch it — the oracle is the thing being compared to | C6 checks every next hop against `fw1`'s interface addresses, an independent source. Step 3 proves the two clauses fail independently |
| The oracle parser mishandles the aligned columns | **Medium — this exact bug cost cycle 023 a six-correction overstatement** | C4 pins that the parser returns eight routes from the real file |
| A one-way comparison hides a missing route | Medium | C3 asserts both directions separately. Cycle 023 deleted fourteen lines of correct data to a one-way read |
| An inline concrete-kind block is added "to be safe" | Medium — the guidance appears to demand it | R2 records why it is unnecessary; C2 pins the scalar form so a later "fix" fails |
| `vrf` set explicitly, or an attribute invented | Low | C5 pins that only four fields are set. An invented `distance` would be rendered by cycle 026 |
| The eleven fabric routes disturbed | Low, high severity | Counts checked before and after: 11 → 19 → 19 |
| The address-book converse asserted | **Averted in Phase 0** | R5 accounts for all five unrouted entries; the contract says explicitly not to assert it |

## Complexity Tracking

No constitution violations require justification. This section is intentionally empty.
