# Tasks: The Perimeter Firewall's Static Routes

**Cycle**: 025 | **Branch**: `025-firewall-route-objects` | **Infrahub branch**: `fw-routes-obj`
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/object-contract.md](./contracts/object-contract.md),
[quickstart.md](./quickstart.md)

## Why the test comes first here — and the honest caveat

Cycle 024 put its test first because **nothing pinned the thing being changed**, and the suite
passed either way. That argument does not apply this time: the object file will not exist, so of
course the test fails.

The real reason is narrower and worth stating plainly. Two clauses are easy to write *wrong* once
the data is on disk, because a parser shaped to fit known-good data looks like it works:

- **C4**, the oracle parser, must handle hand-aligned columns. The equivalent bug overstated
  cycle 023's gap by six corrections and was believed for a while.
- **C3**, the comparison, must run in **both** directions. Cycle 023 deleted fourteen lines of
  correct data after a one-way read concluded something was absent when the search was at fault.

Writing them against a file that does not exist yet forces them to be written from the contract
rather than from the data.

## Phase 1: Setup

- [X] T001 Confirm the working tree carries only `specs/025-firewall-route-objects/` — Phase 0 loaded a generated draft onto a scratch branch and deleted it, so `git status --short` must show no `objects/` or `schemas/` change
- [X] T002 Confirm `../lab/configs/fw/vsrx/junos.conf` is readable; without the lab repo the new module must skip rather than fail, as `tests/unit/test_junos_config.py` does
- [X] T003 Record the baseline: `uv run pytest tests/unit -q` (expect 1008 passed) and the live `RoutingStaticRoute` count on `main` (expect 11, all on fabric devices), so T018 and T022 have something to compare against
- [X] T004 Export `INFRAHUB_API_TOKEN` for this session — reads work anonymously, writes do not

## Phase 2: Foundational — the parser and the comparison

**Blocking**: every later phase reads through these two pieces, and both have a recorded history
of being written wrong.

- [X] T005 Create `tests/unit/test_fw_static_route_objects.py` with the three sources from [contracts/object-contract.md](./contracts/object-contract.md) — `objects/32b_nfd41_fw_static_routes.yml`, `objects/32_nfd41_security.yml`, `../lab/configs/fw/vsrx/junos.conf` — and a skip guard when the lab repo is absent
- [X] T006 Write the oracle parser in that module: extract `routing-options { static { … } }` into `{prefix: (next_hop, comment)}`, handling the **variable-width column alignment** — a single-space assumption reads six of eight lines
- [X] T007 Add contract clause C4 to `tests/unit/test_fw_static_route_objects.py`: the parser returns exactly eight routes from the real device file. This pins the parser itself, which is the thing that was wrong in cycle 023
- [X] T008 Run `uv run pytest tests/unit/test_fw_static_route_objects.py -q` — C4 passes against the oracle alone; every clause needing the object file fails, because it does not exist yet

**Checkpoint**: a parser proven against the real file, before any data exists to shape it.

---

## Phase 3: User Story 1 — The firewall's forwarding decisions are in the graph (P1)

**Goal**: eight `RoutingStaticRoute` objects on `fw1`, transcribed exactly.

**Independent test**: load the file, query `fw1.static_routes`, compare all eight
destination/next-hop pairs against the device file in both directions.

- [X] T009 [US1] Add contract clauses C1 and C2 to `tests/unit/test_fw_static_route_objects.py`: the file is one document with `apiVersion: infrahub.app/v1`, `kind: Object`, `spec.kind: RoutingStaticRoute`; `spec.data` has eight entries; every `device` is the **scalar string** `"fw1"` — pinned so a later "fix" to an inline concrete-kind block fails loudly
- [X] T010 [US1] Add contract clause C3 to `tests/unit/test_fw_static_route_objects.py` as **three separate assertions**: oracle→file (nothing missing), file→oracle (nothing invented), and value equality for shared destinations. Three assertions, not one, so a failure says which direction broke
- [X] T011 [US1] Add contract clause C5 to `tests/unit/test_fw_static_route_objects.py`: each entry sets `prefix`, `next_hop`, `route_name`, `device` and **nothing else** — no `gateway`, `interface`, `distance`, `tag` or `vrf`
- [X] T012 [US1] Create `objects/32b_nfd41_fw_static_routes.yml` with the eight routes from [data-model.md](./data-model.md), transcribed from `../lab/configs/fw/vsrx/junos.conf` lines 163–170. `route_name` carries each `/* … */` comment as written, `incl.` included
- [X] T013 [US1] Comment the file header: where the data comes from, why `vrf` is absent (the schema default `"default"` *is* the master instance, and the live schema carries a `[device, prefix]` uniqueness constraint derived from the HFID), and why `device` is a scalar rather than an inline block
- [X] T014 [US1] Run `uv run pytest tests/unit/test_fw_static_route_objects.py -q` — C1, C2, C3, C4 and C5 all pass
- [X] T015 [US1] **Prove the comparison is real**: change one `prefix` in the object file by hand, confirm the oracle→file and file→oracle assertions fail *separately*, then restore. A both-ways check that only ever fires one way is a one-way check

**Checkpoint**: SC-001, SC-002 and SC-003 demonstrated offline.

---

## Phase 4: User Story 2 — The routes agree with the rest of the model (P2)

**Goal**: two cross-checks against sources that are not the device file.

**Independent test**: every next hop lands on a connected /30; every destination is an
address-book prefix.

- [X] T016 [US2] Add contract clause C6 to `tests/unit/test_fw_static_route_objects.py`: each `next_hop` lies inside a network one of `fw1`'s `SecurityFirewallInterface` addresses in `objects/32_nfd41_security.yml` is numbered on — expect `10.250.110.1`→ge-0/0/0, `.210.1`→ge-0/0/1, `.150.1`→ge-0/0/2, `.170.1`→ge-0/0/3, `.10.1`→ge-0/0/4, `.20.1`→ge-0/0/5
- [X] T017 [US2] Add contract clause C7 to `tests/unit/test_fw_static_route_objects.py`: each `prefix` equals the `ip_prefix` of a `SecurityGenericAddress` in `objects/32_nfd41_security.yml`. **Do not assert the converse** — five book entries correctly have no route, and [research.md](./research.md) R5 accounts for all of them
- [X] T018 [US2] **Prove C6 is an independent witness**: change one digit of one `next_hop`, confirm **both** C3 and C6 fail, then restore. If only C3 fires, C6 is checking the same thing twice and adds nothing — the whole argument for it is that a comparison against the device file cannot catch a typo *in* the device file

**Checkpoint**: SC-004 and SC-005 demonstrated, and C6 shown to be worth its place.

---

## Phase 5: User Story 3 — Loading from scratch still works (P3)

**Goal**: the file's position in load order resolves `fw1` on an empty instance.

**Independent test**: the filename sorts after the file defining `fw1`.

- [X] T019 [P] [US3] Add contract clause C8 to `tests/unit/test_fw_static_route_objects.py`: `32b_nfd41_fw_static_routes.yml` sorts after `31_nfd41_offfabric_devices.yml`, which defines `fw1`
- [X] T020 [P] [US3] Confirm no registration is needed — **the stated mechanism was wrong.** `.infrahub.yml` has no `objects:` key at all; object loading is explicit, via `tasks.py`'s `load` task running `infrahubctl object load objects/` over the whole directory. Same conclusion, different mechanism

**Checkpoint**: a fresh `invoke load` resolves the `device` reference.

---

## Phase 6: Polish & Cross-Cutting Concerns

### Live validation

- [X] T021 Create the `fw-routes-obj` Infrahub branch and record the pre-load count: 11 `RoutingStaticRoute`, all on fabric devices
- [X] T022 Load with `uv run infrahubctl object load objects/32b_nfd41_fw_static_routes.yml --branch fw-routes-obj` and verify B1–B3: eight created, `fw1.static_routes = 8`, total 19, and the eleven fabric routes untouched
- [X] T023 Read the eight back and verify B4 and B5: `vrf = "default"` on every one **from the schema default** with the file setting it nowhere, and `gateway`, `interface`, `distance`, `tag` all unset — an invented value here becomes rendered configuration in cycle 026
- [X] T024 Load the same file a second time and verify B6: still 8 on `fw1`, still 19 in total. **Count — do not read the log**; `infrahubctl` prints "Created node" for an upsert, which cycle 023 recorded and cycle 024 relied on

### Gates

- [X] T025 Run `uv run invoke test` — 1008 existing tests plus the new module, all green
- [X] T026 Run `uv run invoke lint` — ruff, ruff-format, yamllint, mypy and rumdl clean. `yamllint` covers `objects/`, so the new file must satisfy it, line length included
- [X] T027 Confirm SC-007 and SC-008: `git diff --stat schemas/` is empty and no existing file under `objects/` is modified — only the new file is added

### The record

- [X] T028 [P] Update the `junos_config` section of `AGENTS.md`: `routing-options` no longer awaits "seed data and a template" — the seed data is here, and only the template remains (cycle 026)
- [X] T029 [P] Update the `junos_config` artifact comment in `.infrahub.yml` for the same reason

### Evidence and close-out

- [X] T030 Write `specs/025-firewall-route-objects/acceptance-evidence.md`: the both-ways comparison result, the two cross-check tables, the load counts 11 → 19 → 19, the read-back of unset fields, and the two deliberate-break proofs from T015 and T018
- [X] T031 Record in that file the research self-correction — `access-portal` was cited as `10.112.240.10` from memory when the seeded value is `10.112.240.33/32`; the conclusion survived because both sit inside `10.112.0.0/16`, but a right answer from a guess is not evidence
- [X] T032 Note the follow-ups this cycle does not close: the `$infrahub-run-integration-tests` exception, the `infrahubctl generator` CLI limitation found in cycle 024, and the stale Infrahub branches — one of which (`023-junos-config-render`) errors on every repository sync
- [~] T033 Run `$infrahub-run-integration-tests` — **not installed**, documented exception named in the commit. Original: Run `$infrahub-run-integration-tests`. If not installed, say so **explicitly** in the pull request as the constitution's documented exception — do not omit it silently
- [X] T034 Merged to `main` and the `fw-routes-obj` Infrahub branch deleted, on the requester's instruction. The Infrahub merge succeeded first time and needed no conflict resolution — `main` held none of these objects, and this cycle changed no schema, so neither 023's `SchemaAttribute` collision nor its `export-schema` trap could arise. Verified on `main` afterwards: 19 routes, `{DcimDevice: 11, SecurityFirewall: 8}`, all eight firewall routes at `vrf=default`

---

## Dependencies

```text
Phase 1 (Setup)
   └─> Phase 2 (Foundational: parser + skip guard)   ← BLOCKS EVERYTHING
          ├─> Phase 3 (US1, P1: the eight objects)
          │      ├─> Phase 4 (US2, P2: the cross-checks)   ← needs the file to exist
          │      └─> Phase 6 (Polish)                      ← needs the file to exist
          └─> Phase 5 (US3, P3: load order)                ← independent of US1's content
```

**US2 depends on US1** in the weak sense that it checks data US1 creates. The clauses are
genuinely independent assertions about different sources, but they have nothing to run against
until the file exists.

**US3 is independent of both** — it is a statement about a filename, and could be written first.

## Parallel opportunities

- **T009, T010, T011** — three contract clauses in the same new module but disjoint test
  functions; write together, run once at T014
- **T016, T017** — two clauses, two different sections of the same source file
- **T019, T020** — a test clause and a config check, unrelated
- **T028, T029** — two different files
- T012 and T013 both edit the new object file and are strictly sequential

## Implementation strategy

**MVP is Phase 2 + Phase 3.** At T015 the eight routes are in the repository and proven against
the device file in both directions — the cycle's headline claim.

**Do not stop there.** Phase 4 is the half that makes this worth modelling rather than copying a
text file: a text file cannot check itself against the firewall's interfaces or its policy. T018
in particular is the task that proves the second witness is a second witness.

Phase 6's live steps (T021–T024) re-run what Phase 0 already demonstrated against a generated
draft; they are cheap and they check the committed file rather than a scratch one.

## Task summary

| Phase | Tasks | Story |
| --- | --- | --- |
| 1 Setup | T001–T004 | — |
| 2 Foundational | T005–T008 | — |
| 3 US1 | T009–T015 | P1 |
| 4 US2 | T016–T018 | P2 |
| 5 US3 | T019–T020 | P3 |
| 6 Polish | T021–T034 | — |
| **Total** | **34** | |
