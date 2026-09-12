# Tasks: Completing the Perimeter Firewall Artifact

**Cycle**: 026 | **Branch**: `026-complete-junos-artifact` | **Infrahub branch**: `fw-complete`
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md),
[contracts/transform-contract.md](./contracts/transform-contract.md),
[quickstart.md](./quickstart.md)

## Why the whole-file comparison goes in first

Not TDD ritual. The existing module already has stanza-level assertions that pass, and they will
keep passing while three comment blocks are missing — that is how the gap survived three cycles.

**C1 turns "is the artifact complete?" into one number.** It goes in at T005, fails, and is the
thing every later task is measured against. The existing stanza checks stay: C1 says *whether*,
they say *where*.

## Phase 1: Setup

- [X] T001 Confirm the working tree carries only `specs/026-complete-junos-artifact/` — the plan phase measured against the live render but implemented nothing, so `git status --short` must show no `schemas/`, `objects/`, `transforms/` or `tests/` change
- [X] T002 Confirm `../lab/configs/fw/vsrx/junos.conf` is readable; without the lab repo the junos modules skip rather than fail
- [X] T003 Record the baseline: `uv run pytest tests/unit -q` (expect 1021), the live render's line count (expect 555 including its provenance line), and `uv run invoke lint-yaml` error count (expect 623), so T034, T036 and T041 have something to compare against
- [X] T004 Create the `fw-complete` Infrahub branch and export `INFRAHUB_API_TOKEN`

## Phase 2: Foundational — the measurement that makes the rest verifiable

**Blocking**: every later phase is judged by C1.

- [X] T005 Add contract clause C1 to `tests/unit/test_junos_config.py`: the rendered artifact minus its provenance line is **identical** to `../lab/configs/fw/vsrx/junos.conf` minus the 72-line header and the 13-line `system` stanza, asserted as a unified diff that must be empty
- [X] T006 Add contract clause C2 to `tests/unit/test_junos_config.py`: `677 = 592 + 13 + 72`, with all four numbers **computed from the device file at test time**, not hard-coded as literals that can drift from it
- [X] T007 Add contract clause C10 to `tests/unit/test_junos_config.py`: the artifact contains **zero** configuration lines absent from the device file. It is 0 today and must stay 0 — this is the direction that catches a template emitting something plausible but wrong
- [X] T008 Run `uv run pytest tests/unit/test_junos_config.py -q` and confirm **C1 and C2 fail while C10 passes**. C10 passing now is the point: the render invents nothing today, and the cycle must not change that

**Checkpoint**: one failing number that measures the whole cycle.

---

## Phase 3: User Story 1 — The firewall's routes reach the device configuration (P1)

**Goal**: the `routing-options` stanza renders from the eight routes cycle 025 seeded.

**Independent test**: render `fw1` and compare the stanza to the device file.

- [X] T009 [US1] Extend `transforms/junos_config.gql` to fetch `static_routes` on the firewall — `prefix`, `next_hop`, `route_name` — through the `SecurityFirewall.static_routes` relationship cycle 024 created
- [X] T010 [US1] Regenerate `transforms/junos_config_query.py` with `infrahubctl graphql generate-return-types transforms/junos_config.gql`; never hand-edit it. Watch the generated file name — it comes from the GraphQL **operation** name, which bit cycle 022
- [X] T011 [US1] Re-capture `tests/unit/fixtures/junos/fw1.json` from the branch so the offline tests see the routes
- [X] T012 [US1] Add a `_static_routes()` helper to `transforms/junos_config.py` returning `prefix`, `next_hop`, `comment`, and the two derived spacing values, ordered to match the device file — deterministic, and free to be chosen because static routes are longest-prefix matched, not first-match
- [X] T013 [US1] Implement the two derived gaps in `transforms/junos_config.py`: `pad = max(1, 14 - len(prefix))` and `gap = 3 if len(next_hop) == 12 else 2`
- [X] T014 [US1] Comment that code with what [research.md](./research.md) R1 established: `pad` is a **real alignment rule** — it puts the `;` at column 50 on every line — while `gap` **reproduces an inconsistency**, because two lines were typed one space short. Both misreadings break SC-001: treating `gap` as policy invites a tidy-up, treating it as arbitrary invites storing spacing in the model
- [X] T015 [US1] Create `transforms/templates/junos/routing-options.j2` rendering the stanza, and omitting it entirely when there are no routes — an empty `static { }` is not what the device would hold
- [X] T016 [US1] Edit `transforms/templates/junos/junos.j2` to include it between `interfaces` and `security`
- [X] T017 [US1] Add contract clauses C3 and C4 to `tests/unit/test_junos_config.py`: all three spacing cases named separately — 12-char next hop with a 13-char prefix, 12-char next hop with a 12-char prefix, and the **11-char next hop** case that carries `gap = 2` — plus the column-50 invariant asserted directly
- [X] T018 [US1] Add contract clause C5's first half: `routing-options` sits between `interfaces` and `security`
- [X] T019 [US1] Add contract clause C6's first half: a firewall with no routes renders no `routing-options` stanza, from a modified copy of the fixture
- [X] T020 [US1] **Prove C3 is not redundant with C1**: change one of the two short-gap lines from 2 spaces to 3 — the tidy-up a well-meaning reader would make — and confirm **both** C1 and C3's 11-character case fail. If only C1 fails, C3 is not asserting the spacing and the tidy-up would survive any future relaxation of the diff. Restore

**Checkpoint**: twelve of the nineteen missing configuration lines rendered; SC-003 demonstrated.

---

## Phase 4: User Story 2 — The TCP-MSS clamp is modelled, not lost (P2)

**Goal**: the value the `interfaces` comment already explains is in the model and rendered.

**Independent test**: query `fw1` for the clamp; render and compare the `flow` stanza.

- [X] T021 [US2] Add a `tcp_mss` attribute to `SecurityFirewall` in `schemas/security_extensions.yml` — `kind: Number`, `optional: true`, **no default** — matching the shape cycle 023 used for `book_index` and `log_session_close`. `schemas/security/security.yml` is marketplace-adopted and must not be touched
- [X] T022 [US2] Update `tests/unit/test_security_schema_contract.py`: the extensions file now touches **four** kinds, not three. Change the count deliberately, as cycle 023 changed it from two to three — do not loosen it to "at least"
- [X] T023 [US2] Add contract clause C8 to `tests/unit/test_security_schema_contract.py`: `tcp_mss` is `Number`, `optional: true`, and has **no default**. That pair is what makes an unset clamp render no stanza rather than `mss 0`
- [X] T024 [US2] Run `uv run infrahubctl schema check schemas/ --branch fw-complete` and read the diff: `SecurityFirewall` gains `tcp_mss` and **nothing else changes**. Then load
- [X] T025 [US2] Set `tcp_mss: 9138` on `fw1` — **the task named the wrong file.** `fw1` the `SecurityFirewall` is defined in `objects/31_nfd41_offfabric_devices.yml`, not `32_nfd41_security.yml`, and that is where the value went. The reasoning held: it is an attribute of the firewall, so it goes on the firewall's existing entry
- [X] T026 [US2] Add contract clause C9 to `tests/unit/test_junos_seed_data.py`: the seeded value equals the `mss` value in the device file, read from the oracle rather than hard-coded a second time
- [X] T027 [US2] Load the objects onto the branch and read the value back; load again and confirm nothing duplicates — **count, do not read the log**, which prints "Created node" for an upsert
- [X] T028 [US2] Extend `transforms/junos_config.gql` and re-run T010's regeneration to fetch `tcp_mss`; re-capture the fixture
- [X] T029 [US2] Render the `flow` block in `transforms/templates/junos/junos.j2` as the **first** block inside `security`, before `address-book`, preceded by its 6-line comment; omit the whole stanza when `tcp_mss` is unset
- [X] T030 [US2] Add contract clause C5's second half and C6's second half: `flow` is first inside `security`, and a firewall with no clamp renders no `flow` stanza — the latter from a modified fixture

**Checkpoint**: all nineteen missing configuration lines rendered; SC-004 and SC-005 demonstrated.

---

## Phase 5: User Story 3 — The configuration keeps its explanations (P3)

**Goal**: the three dropped comment blocks come back.

**Independent test**: all three appear in the rendered artifact, in position.

- [X] T031 [P] [US3] Add the 4-line "Named objects rather than bare CIDRs" comment block to `transforms/templates/junos/address-book.j2`, in the device file's position
- [X] T032 [P] [US3] Add the 9-line NAT comment block — "NAT is absent from this file, and that absence is load-bearing" — to `transforms/templates/junos/address-book.j2` after the address book. It records that a source-NAT rule here would translate real pod addresses and silently make every downstream ACL meaningless, and that `make verify` checks no `nat` stanza has appeared
- [X] T033 [US3] Add contract clause C7 to `tests/unit/test_junos_config.py`: all three blocks present and in position, with the NAT block asserted by its own clause as well as by C1 — it documents an **absence**, so nothing in the model implies it and nothing but a test can notice it going missing
- [X] T034 [US3] Run `uv run pytest tests/unit/test_junos_config.py -q` — **C1 now passes**. The diff is empty. This is SC-001, and the artifact is 592 lines plus its provenance line

**Checkpoint**: the headline claim demonstrated offline.

---

## Phase 6: User Story 4 — The repository is left clean (P4)

**Goal**: `invoke lint-yaml` is usable and the branch list is not noise.

**Independent test**: zero lint errors; only the main git worktree.

- [X] T035 [US4] **Check before removing**: `git merge-base --is-ancestor 213e83e main` must succeed, proving the worktree's HEAD is fully merged and nothing is lost. This is the safety gate, not an afterthought
- [X] T036 [US4] Remove it with `git worktree remove .claude/worktrees/agent-a7e2fddc3b0b7c881` — **not** `rm -rf`. It is a registered git worktree ([research.md](./research.md) R5); deleting the folder alone leaves a stale registration that `git worktree list` keeps reporting
- [X] T037 [P] [US4] Add `/.claude` to the ignore list in `.yamllint`, with a comment saying why: agent worktrees carry their own copy of `lab/avd/intended`, and the existing ignore for it is anchored so it does not cover a nested copy. Without this the next worktree reintroduces all 623 errors
- [X] T038 [US4] Run `uv run invoke lint-yaml` — zero errors, down from 623
- [X] T039 [US4] Deleted 14 merged per-cycle branches plus `worktree-agent-a7e2fddc3b0b7c881`. **Fifteen older branches were listed for the requester rather than deleted on a guess**, per H5 — they predate this sequence and nothing in-session establishes they are finished. Original: Delete the merged per-cycle Infrahub branches (`012-` through `025-`, and the working branches `wan-*`, `app-*`, `svi-model`, `svc-gen`, `peer-*`, `menu-check`, `cx-peering`, `no-internet`, `avd-fabric-run`, `nfd41-fabric-model`). **List anything whose purpose is unclear for the requester instead of deleting it on a guess**
- [X] T040 [US4] Confirm `023-junos-config-render` is gone — it errors on every repository sync because its schema predates cycle 023's attributes — and that `git worktree list` shows only the main worktree

**Checkpoint**: the housekeeping the request named, done.

---

## Phase 7: Polish & Cross-Cutting Concerns

### Live validation

- [X] T041 Render live on `fw-complete` and diff against the device file minus the header and `system` — no output, 592 lines plus the provenance line ([quickstart.md](./quickstart.md) §5)
- [X] T042 Verify SC-002 live: 459 configuration lines in both, and **0** present in the render and absent from the device
- [X] T043 Verify SC-007 — no `encrypted-password`, no hash, no `system` stanza in the artifact, the query or the objects. Re-verified, not inherited from cycle 023
- [X] T044 Verify SC-008 — braces balance and the file ends with exactly one newline

### Gates

- [X] T045 Run `uv run invoke test` — 1021 existing tests plus the new clauses, all green
- [X] T046 Run `uv run invoke lint` — ruff, ruff-format, yamllint, mypy and rumdl clean. `yamllint` covers the whole tree meaningfully for the first time in this sequence
- [X] T047 Verify `schemas/security/security.yml` is byte-identical to marketplace `infrahub/security` 1.0.2

### The record

- [X] T048 [P] Update the `junos_config` section of `AGENTS.md` with the final figures, and describe the two exclusions as the **different things they are**: `system` is configuration deliberately never modelled, the 72-line header is 68 comments and 4 blanks of lab documentation about the file, not configuration at all
- [X] T049 [P] Update the `junos_config` artifact comment in `.infrahub.yml` for the same reason
- [X] T050 [P] Update the `transforms/junos_config.py` module docstring — it currently says the `flow` block is unmodelled and `routing-options` awaits a template. Both are now false

### Evidence and close-out

- [X] T051 Write `specs/026-complete-junos-artifact/acceptance-evidence.md`: the empty diff, the accounting assertion, the three spacing cases, the emptiness cases, the comment blocks, the lint count before and after, and the two deliberate-break proofs from T008 and T020
- [X] T052 Record the two corrections this cycle made to inherited claims — the "12 + 7 lines" figure that omitted three comment blocks, and the alignment pessimism that two cycles wrote without re-testing. Both had been carried forward rather than re-derived, which is a different failure from the six earlier ones and harder to catch
- [X] T053 Note what remains after this cycle: the `system` stanza and the file header, both permanently excluded for stated and different reasons; the `deny-spoofed-infra` check, still a follow-up; and the `infrahubctl generator` CLI limitation from cycle 024
- [~] T054 Run `$infrahub-run-integration-tests` — **not installed**, documented exception named in the commit. Original: Run `$infrahub-run-integration-tests`. If not installed, say so **explicitly** in the pull request as the constitution's documented exception — do not omit it silently
- [ ] T055 Merge to `main`, then **regenerate `schema.graphql` after the merge** — `export-schema` has no `--branch` flag, and loading this cycle's schema into `main` to work around that is what made cycle 023's Infrahub merge fail. Cycle 024 deferred it and succeeded. Delete the `fw-complete` branch. **Hold for the requester**, as in cycles 020–025

---

## Dependencies

```text
Phase 1 (Setup)
   └─> Phase 2 (Foundational: C1, C2, C10)        ← BLOCKS EVERYTHING
          ├─> Phase 3 (US1, P1: routing-options)
          │      └─> Phase 4 (US2, P2: the clamp)  ← shares the .gql and the fixture
          │             └─> Phase 5 (US3, P3: the comments) ← C1 only passes once all three land
          ├─> Phase 6 (US4, P4: hygiene)           ← fully independent
          └─> Phase 7 (Polish)                      ← needs US1 to US3
```

**US2 depends on US1** for a practical reason rather than a logical one: both edit
`transforms/junos_config.gql` and both force a fixture re-capture, so doing them concurrently
means doing T010 and T011 twice.

**US3 depends on both** only in that C1 cannot go green until all three parts are in. The comment
blocks themselves are template text and could be written at any point.

**US4 is genuinely independent** of everything else and could be done first, last, or by someone
else entirely. It touches no file the render reads.

## Parallel opportunities

- **T005, T006, T007** — three clauses, same module, disjoint test functions
- **T031, T032** — two comment blocks in the same template but different positions; write together
- **T037** is independent of the worktree removal and can be done first
- **T048, T049, T050** — three different files
- Phases 3 and 4 are strictly sequential internally: each task changes the query, the transform,
  a template or the fixture that the next one reads

## Implementation strategy

**MVP is Phase 2 + Phase 3** — at T020 the twelve `routing-options` lines render and the alignment
is proven reproducible, which is the piece cycles 023, 024 and 025 were all building toward.

**The honest stopping point is Phase 5**, when C1 goes green and the diff is empty. Stopping at
Phase 4 leaves the artifact configurationally complete and missing the reason it is safe — the NAT
block documents an absence nothing in the model implies.

**Phase 6 can be lifted out** if you would rather keep repository hygiene separate from the render.
It is in this cycle only because the request was to complete all remaining tasks, and nothing in
Phases 2–5 depends on it.

## Task summary

| Phase | Tasks | Story |
| --- | --- | --- |
| 1 Setup | T001–T004 | — |
| 2 Foundational | T005–T008 | — |
| 3 US1 routing-options | T009–T020 | P1 |
| 4 US2 the clamp | T021–T030 | P2 |
| 5 US3 the comments | T031–T034 | P3 |
| 6 US4 hygiene | T035–T040 | P4 |
| 7 Polish | T041–T055 | — |
| **Total** | **55** | |
