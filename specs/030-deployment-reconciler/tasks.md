---

description: "Task list for the deployment reconciler"
---

# Tasks: Deployment reconciler

**Input**: Design documents from `/specs/030-deployment-reconciler/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/device-comparison.md](./contracts/device-comparison.md),
[quickstart.md](./quickstart.md)

**Tests**: included, and not optional here. The spec requires them (FR-052), the constitution
requires them, and the push path this cycle turns into a ten-minute loop has **no tests at all**
today.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US7 from [spec.md](./spec.md)
- Exact file paths in every description

## Read this before starting

**The single thing that makes or breaks this cycle is normalisation.** Phase 0 measured all
three comparators against the running lab. An unchanged FRR router reports `Lines To Add`; an
unchanged firewall reports **55 changed lines**. Only EOS comes back clean. A reconciler that
treats "non-empty diff" as "push" will replace the configuration of every FRR router and the
perimeter firewall **on every cycle, forever**, and report success the whole time.

So **T017 and T018 must land together**. A working compare without normalisation is not a
partial feature; it is a fabric-wide config churn generator with a green log.

Four more things measured in Phase 0 that cost time if rediscovered:

1. **`frr-reload.py --test` returns `0` whether or not the config matches.** Exit status is
   not a signal (FR-011b).
2. **Its output is `Lines To Add` / `Lines To Delete` sections, not `+`/`-` prefixes.** A
   parser written against diff prefixes returns "0 differences" for a known-different control —
   a false negative that looks exactly like success.
3. **`scp -O` is load-bearing on the Junos path.** Without it the copy fails, `load replace`
   does nothing, and `show | compare` returns empty — which reads as "in sync".
4. **An empty diff proves nothing without a control.** Every comparator test needs an injected
   known difference, for the same reason this repository never trusts `Ready`.

---

## Phase 1: Setup

- [X] T001 Create the package skeleton `src/solution_arista_avd/deployment/__init__.py` with the module layout from plan.md (`devices`, `compare`, `normalise`, `state`, `reconcile`)
- [X] T002 [P] Create `tests/unit/fixtures/deployment/` and commit the Phase 0 transcripts as fixtures: an EOS empty diff and control diff, an FRR `--test` output for an unchanged device and for a control, and a Junos `show | compare` for both. These are the real device outputs research R1–R3 captured; regenerate them from the live lab rather than inventing them
- [X] T003 [P] Confirm no new dependency is added to `pyproject.toml` — Nornir was dropped in research R5 and the device path uses `httpx` and `subprocess`, both already direct dependencies

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: move the existing device knowledge somewhere importable. Nothing else can start
until `compare.py` has something to import.

**⚠️ CRITICAL**: blocks every user story

- [X] T004 Move the device functions from `scripts/provision_lab.py` into `src/solution_arista_avd/deployment/devices.py` — `Target`, `ProvisionError`, `discover`, `download`, `push_eos`, `push_frr`, `push_junos`, `_eos_config_lines`, `_assert_eos_lifeline`, `_assert_junos_scope`, `_junos_replace_tagged`, `_wait_for_vsrx`, `_vsrx`, `_vsrx_cli`, `_assert_junos_ok`, `_container_running`. **Move, do not rewrite** (FR-050): those 678 lines encode knowledge measured against the running lab, and every comment in them is a scar
- [X] T005 Reduce `scripts/provision_lab.py` to a thin CLI over `deployment.devices`, keeping its argument parsing and output format byte-identical
- [X] T006 Verify `uv run invoke provision --dry-run` produces the same output as before the lift (FR-051), then `uv run invoke provision` against the running lab and confirm it still reports `ok` for all three families
- [X] T007 [P] Add `uv run mypy --show-error-codes src/solution_arista_avd` to the loop — the new package must satisfy `disallow_untyped_defs` (constitution III)
- [X] T008 [P] Confirm `scripts/provision_lab.py` no longer contains device logic, so there is exactly one copy of it in the repository

**Checkpoint**: the device layer is importable and `invoke provision` is unchanged.

---

## Phase 3: User Story 1 - A merge reaches the devices without anyone typing a command (Priority: P1) 🎯 MVP

**Goal**: a loop that compares every device against its rendered artifact and pushes only when
they genuinely differ.

**Independent Test**: change one device's intent on `main`, wait one cycle, confirm the device
reports no difference afterwards — without running `invoke provision`.

### Tests for User Story 1

- [X] T009 [P] [US1] Write `tests/unit/test_deployment_normalise.py` against the fixtures from T002: an unchanged EOS diff normalises to empty; an unchanged FRR `--test` output normalises to empty; an unchanged Junos compare normalises to empty; and each control fixture normalises to **non-empty** with the injected line present
- [X] T010 [P] [US1] Add a test asserting the allowlist is **fail-noisy**: an unrecognised line in any family's output must survive normalisation and count as a difference (FR-011a)
- [X] T011 [P] [US1] Add a test asserting exit status is never consulted — an FRR fixture with `rc=0` and real differences must normalise to non-empty (FR-011b)

### Implementation for User Story 1

- [X] T012 [US1] Implement `Comparison` in `src/solution_arista_avd/deployment/compare.py` as `{target, raw_diff, normalised_diff, differs}` where `differs` is `bool(normalised_diff)` and nothing else may decide it (data-model.md)
- [X] T013 [US1] Implement `compare_eos` in `src/solution_arista_avd/deployment/compare.py` per contracts/device-comparison.md: `configure session infrahub-<ts>` → `rollback clean-config` → artifact lines → `show session-config named <s> diffs`, then **always** abort. Session names must be unique per run — EOS keeps one completed session per name and refuses to re-enter it
- [X] T014 [US1] Implement `compare_frr` in `src/solution_arista_avd/deployment/compare.py`: stage into `/tmp/infrahub-reconcile` (never over `/etc/frr/frr.conf`, which the lab repository bind-mounts read-only) and run `frr-reload.py --test --confdir`. Parse the `Lines To Add` / `Lines To Delete` **sections**, not `+`/`-` prefixes
- [X] T015 [US1] Implement `compare_junos` in `src/solution_arista_avd/deployment/compare.py`: stage, `scp -O` (without `-O` the load silently does nothing), then `configure exclusive` → `load replace` → `show | compare` → `rollback 0` → `exit`
- [X] T016 [US1] Implement artifact reading in `src/solution_arista_avd/deployment/compare.py`: download every artifact and **refuse to push an empty one regardless of `Ready`** (FR-012). `scripts/provision_lab.py:614` currently trusts `Ready`, which this repository documents twice as not being evidence of anything
- [X] T017 [US1] Implement `src/solution_arista_avd/deployment/normalise.py` with one named, commented rule per suppressed pattern from contracts/device-comparison.md — FRR's `neighbor <addr> activate`, `service integrated-vtysh-config`, `line vty` and enclosing-only scaffolding; Junos's `!  from-zone … to-zone …` reordering and comment-only round-trips. Allowlist, never denylist
- [X] T018 [US1] Wire normalisation into `compare` so `differs` is computed **only** from the normalised output. **T017 and T018 land with T012–T015, not after them** — see the note at the top of this file
- [X] T019 [US1] Implement the cycle in `src/solution_arista_avd/deployment/reconcile.py`: read intent, iterate devices, compare, push on difference, and continue past a failing device (FR-017)
- [X] T020 [US1] Add the interval to `src/solution_arista_avd/deployment/reconcile.py` — 600s default (FR-002), **refuse to start below 60s** rather than clamping (FR-003), and skip rather than queue a cycle that is still running (FR-005)
- [X] T021 [US1] Check the firewall on every fourth cycle only (FR-004) and last in the cycle, because it takes an exclusive lock on the device someone needs during an incident
- [X] T022 [US1] Add `invoke reconcile` to `tasks.py` running a single cycle, so the loop can be exercised without running the service

**Checkpoint**: MVP. A merge reaches the devices unattended, and an in-sync fabric is silent.

---

## Phase 4: User Story 2 - An operator can see whether their merge reached the fabric (Priority: P1)

**Goal**: per-device state in Infrahub, written by this service and nothing else.

**Independent Test**: run one cycle against an unchanged fabric and confirm every device has a
record whose confirmation timestamp moved, with no device written to.

### Tests for User Story 2

- [X] T023 [P] [US2] Add unit tests in `tests/unit/test_deployment_state.py` for the status transition table in data-model.md, including that an empty normalised diff is the **only** path that writes `last_confirmed_at`

### Implementation for User Story 2

- [X] T024 [US2] Implement `src/solution_arista_avd/deployment/state.py` upserting `DeploymentState` on `name` (FR-024) — the graph enforces uniqueness on `name`, not on the device relationship, so this is the service's job
- [X] T025 [US2] Write `last_confirmed_at` **only** when the device itself reported no difference, never because a push was sent (FR-021)
- [X] T026 [US2] Write `last_checked_at` on every comparison including failures (FR-022), and implement the cadence decided in research R8 — that field every cycle, everything else on change
- [X] T027 [US2] Record `status`, `last_attempt_at` and `last_error` per the transition table, distinguishing `pending` from `drifted` by whether the artifact checksum moved (data-model.md). This is the only use of the checksum in the design; it never decides whether to push
- [X] T028 [US2] Refresh the record's `name` from the device each cycle so a rename converges (FR-023)
- [X] T029 [US2] Sweep records whose `device` no longer resolves (FR-025)
- [X] T030 [US2] Ensure `suspend` and `suspend_reason` are **never written** by this service (data-model.md) — a reconciler that clears its own break-glass is not a break-glass

**Checkpoint**: an operator can answer "did my merge reach the fabric?" from the UI.

---

## Phase 5: User Story 3 - One device can be taken out of the loop (Priority: P1)

**Goal**: a per-device break-glass that works during an incident.

**Independent Test**: suspend one device, change its intent, run a cycle, confirm it was not
touched while another changed device was.

- [X] T031 [P] [US3] Add a unit test in `tests/unit/test_deployment_state.py` asserting a suspended device produces no comparison and no state write at all
- [X] T032 [US3] Read `suspend` in `src/solution_arista_avd/deployment/reconcile.py` **before the device is reached**, so a suspended device is never connected to, never opens a session and never takes a lock (FR-014)
- [X] T033 [US3] Leave a suspended device's `status` and `last_checked_at` untouched (data-model.md) — a moving timestamp on a device nobody looked at is a lie

**Checkpoint**: auto-push now has the mitigation decision log item 15 required. **Do not run
the service against the lab before this lands.**

---

## Phase 6: User Story 4 - Drift is corrected, not just intent changes (Priority: P2)

**Goal**: a device changed by hand is put back, even though the artifact never moved.

**Independent Test**: change a device by hand without touching Infrahub, run a cycle, confirm
it is returned to its rendered configuration.

- [X] T034 [P] [US4] Add a unit test asserting a non-empty normalised diff with an **unchanged** artifact checksum produces `drifted`, and with a changed checksum produces `pending`
- [X] T035 [US4] Correct drift without asking (FR-015) in `src/solution_arista_avd/deployment/reconcile.py`, skipping any device with `suspend` set
- [X] T036 [US4] Store the normalised diff as a `DeploymentDiffFile` against the record, with the raw device output retained beneath it (FR-026, data-model.md), so an operator sees both what was decided and what the device actually said

**Checkpoint**: it is a reconciler, not a deployment trigger.

---

## Phase 7: User Story 5 - Each cycle cleans up after the last one (Priority: P2)

**Goal**: a cycle killed with SIGKILL does not degrade the next one.

**Independent Test**: leave a session open on a switch by hand, run a cycle, confirm the session
is gone and the device still reconciles.

- [X] T037 [P] [US5] Add a unit test asserting the sweep matches only the `infrahub-` prefix and leaves other session names alone (FR-031)
- [X] T038 [US5] Sweep EOS configuration sessions at **cycle start** in `src/solution_arista_avd/deployment/reconcile.py` — `show configuration sessions` returns a JSON object keyed by name, so prefix matching is exact rather than textual (research R6)
- [X] T039 [US5] Release a Junos exclusive lock this service holds, at cycle start
- [X] T040 [US5] Verify recovery from SIGKILL against the lab: kill the service mid-compare ten times and confirm no switch accumulates sessions (SC-006). `try/finally` does not survive SIGKILL, which is how a container is stopped

**Checkpoint**: the service degrades safely.

---

## Phase 8: User Story 6 - A change can be checked before it is merged (Priority: P2)

**Goal**: the devices' own diffs for a branch, changing nothing.

**Independent Test**: dry-run a branch with a known change; confirm the diff is reported, no
device changed, and no record written.

- [X] T041 [P] [US6] Add a unit test asserting the dry-run path cannot reach any write in `src/solution_arista_avd/deployment/state.py`
- [X] T042 [US6] Implement the dry run in `src/solution_arista_avd/deployment/reconcile.py`, reading artifacts from a named branch and reporting per-device differences (FR-040)
- [X] T043 [US6] Guarantee the dry run writes no deployment state (FR-041) — deployment state is a fact about `main`
- [X] T044 [US6] Add `invoke reconcile --dry-run --branch X` to `tasks.py`

**Checkpoint**: "auto-push makes me nervous" has an answer.

---

## Phase 9: User Story 7 - The push path is covered by tests (Priority: P3)

**Goal**: the guards that make pushing safe are no longer untested.

**Independent Test**: the guards run in `tests/unit` with no devices and no Infrahub.

**P3 means "delivers least on its own", not "do last".** This phase touches only `tests/`, so it
can run alongside any phase from 2 onwards — see Parallel opportunities.

- [X] T045 [P] [US7] Test `_eos_config_lines` in `tests/unit/test_deployment_devices.py`: the trailing `end` is stripped and blank lines dropped. Left in place, `end` returns the CLI to enable mode, the commit is rejected as an invalid command, the session is abandoned and the switch silently keeps its old configuration
- [X] T046 [P] [US7] Test `_assert_eos_lifeline` refuses a configuration missing the management lifeline — `username admin`, `interface Management0`, the MGMT VRF, its default route, `management api http-commands` in that VRF — before anything is sent
- [X] T047 [P] [US7] Test `_assert_junos_scope` refuses a configuration containing a `system` stanza, which carries credential hashes that are never modelled
- [X] T048 [P] [US7] Test `_junos_replace_tagged` inserts a `replace:` tag before each top-level stanza, since `load override` and `load update` were both measured to delete the `system` stanza including the management path

**Checkpoint**: a regression in the push path is caught by CI rather than by a fabric.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T049 Add the long-running service to `docker-compose.override.yml` as a **single** service with no replicas (FR-006, research R9), taking `NFD41_EOS_PASSWORD` and `NFD41_VSRX_PASSWORD` from the environment only (FR-074)
- [X] T050 Implement the per-cycle log in `src/solution_arista_avd/deployment/reconcile.py` — compared, differed, pushed, failed, skipped-suspended, skipped-not-due — and assert no credential is ever logged (FR-060, FR-061)
- [X] T051 [P] Document the service in `docs/docs/` as a **reference implementation of the reconciler pattern for this lab**, not as a supported component of the AVD reference design (FR-072)
- [X] T052 [P] Document the blast radius in `docs/docs/` (FR-075): lab-admin credentials in a long-running service that can replace every device's configuration on a timer, bounded by `suspend`, the 60-second floor and the dry run, with no least privilege. Anyone lifting this pattern into a real environment must meet that decision rather than inherit it
- [X] T053 Verify FR-073 against the lab: `invoke provision`, `invoke bootstrap` and the artifact chain behave identically whether or not the reconciler is running
- [X] T054 Run the full quickstart in `specs/030-deployment-reconciler/quickstart.md`, including **SC-002** — ten consecutive cycles against an in-sync fabric producing **zero** device changes. This is the assertion that catches the normalisation defect; a green log is not evidence without it
- [ ] T055 **Written, not executed.** Add integration coverage in `tests/integration/test_reconcile_cycle.py` and run `$infrahub-run-integration-tests`, recording branch and commit (constitution IV — unlike cycle 029, this gate genuinely applies)
- [X] T056 Run `uv run pytest tests/unit` and `uv run invoke lint` and confirm both green
- [X] T057 Update `AGENTS.md` with the reconciler, the normalisation rule, and why an unchanged FRR router and firewall report differences

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: none
- **Phase 2 (Foundational)**: depends on Phase 1 — **blocks every user story**
- **Phase 3 (US1)**: depends on Phase 2. Everything else depends on US1's compare
- **Phases 4–8**: depend on Phase 3
- **Phase 9 (US7)**: depends only on Phase 2
- **Phase 10 (Polish)**: depends on Phases 3–9

### The dependency that is not negotiable

**T017 and T018 must land in the same change as T012–T015.** Normalisation is not a refinement
of the comparator; without it the comparator is wrong for two of three families in a way that
pushes configuration rather than failing. Splitting them across commits leaves a window in
which running the service churns the fabric.

### Story independence

- **US1 (P1)**: the MVP. Everything else builds on its compare
- **US2 (P1)**: independent of US3–US6; needs US1's `Comparison`
- **US3 (P1)**: small, and **gates running the service at all** — auto-push must not reach the
  lab before suspension works
- **US4 (P2)**: needs US1 and US2; adds the checksum distinction and the diff file
- **US5 (P2)**: independent of US2–US4; touches only the cycle's start
- **US6 (P2)**: needs US1's compare; must not reach US2's writes
- **US7 (P3)**: **fully independent of the live lab and of Infrahub.** Tests only

### Parallel opportunities

- T002, T003 in Phase 1
- T007, T008 in Phase 2
- T009–T011 (the normalisation tests) before their implementation
- **All of Phase 9 alongside any phase from 2 onward** — it touches only `tests/` and needs no
  lab and no Infrahub
- T051, T052 alongside any implementation phase — `docs/` conflicts with nothing
- Phases 5 (US3) and 7 (US5) touch different parts of `reconcile.py` and can be split between
  two people with care

---

## Parallel Example: Phase 9 alongside Phase 3

```bash
# Developer A, needs the lab:
Task: "T013 implement compare_eos in src/solution_arista_avd/deployment/compare.py"
Task: "T017 implement src/solution_arista_avd/deployment/normalise.py"

# Developer B, hermetic:
Task: "T045 test _eos_config_lines in tests/unit/test_deployment_devices.py"
Task: "T047 test _assert_junos_scope refuses a system stanza"
```

---

## Implementation Strategy

### MVP first

1. Phase 1 → Phase 2 (the device layer is importable, `invoke provision` unchanged)
2. Phase 3 (US1), with T017/T018 landing together
3. **Stop and validate SC-002**: ten cycles against an in-sync fabric, zero device changes
4. That is the whole feature in miniature — it just has nowhere to record what it did yet

### Incremental delivery

1. Setup + Foundational → the lift is done and nothing has regressed
2. US1 → **MVP**, devices match `main` unattended
3. US3 → **before the service runs against the lab unattended.** Drift correction without a
   per-device opt-out means the only mid-incident protection is stopping reconciliation
   everywhere
4. US2 → the result is visible where people already look
5. US4 → drift, with evidence
6. US5 → safe under SIGKILL
7. US6 → a branch can be checked before merging
8. US7 → the push path stops being untested

### What is deferred, on purpose

Nornir (research R5 — no new dependency until wall-clock is the constraint, and the firewall
stays serialised regardless). Scoped per-family credentials and a read-only compare pass
(deferred, not rejected — the obvious next step if this ever runs anywhere real). Alerting
(the record is the signal). Sequencing against Vidra (both are reconcilers and converge; this
is the assumption most likely to need revisiting).

---

## Notes

- `[P]` tasks touch different files with no ordering between them
- Commit per phase; the phases are the meaningful increments
- Every task names the requirement or research finding it discharges, so a failure points at a
  line in the spec rather than at a feeling
- The cycle adds **no** Infrahub artifact — no schema, generator, transform, check, menu or
  object data. If a diff shows one, something has gone wrong

---

## Implementation outcome

**56 of 57 tasks complete.** T055's integration test is written but **not run**: it boots a
fresh Infrahub through `infrahub-testcontainers`, which is a several-minute container spin-up
and the constitution's `$infrahub-run-integration-tests` path owns that execution, not this
command. The file is in place and ready for it.

### The feature is validated against the real fabric, not just unit tests

| Check | Result |
| --- | --- |
| **SC-002** — ten consecutive cycles on an in-sync fabric | **0 pushes**. PASS |
| **SC-006** — no accumulated EOS sessions after those cycles | none on any of seven switches. PASS |
| One live cycle | 14 devices compared, 14 `DeploymentState` records written, all `in_sync` |
| Suspend (US3) | `fw1` suspended: `last_checked_at` frozen at 17:02:22 and status preserved, while `branch-rtr` advanced to 17:02:43 |
| Firewall cadence (FR-004) | visible in the ten-cycle log: 14 devices on cycles 0, 4, 8; 13 on the rest |
| Dry run (US6) | reports differences, pushes nothing, writes no state |
| **FR-051 / FR-073** | `invoke provision` pushed 14/14 devices `ok` after the lift; default compose services unchanged (9, reconciler behind a profile) |

### Three things the implementation found that the plan did not

- **The plan said "no schema change". It was wrong.** FR-015 requires `pending` to be
  distinguishable from `drifted`, and cycle 029's `DeploymentState` had nowhere to remember the
  previous artifact. Added `last_artifact_checksum` (optional Text) rather than shipping a stub
  that silently disabled the requirement. Schema loaded, protocols regenerated, cycle 029's
  contract file re-synced.
- **The fail-noisy rule earned its keep on the first live run.** `isp-pe1` reported a
  difference: the FRR scaffold pattern matched `router bgp <asn>` but not
  `router bgp <asn> vrf <NAME>`, so on a provider edge every customer VRF left an unsuppressed
  wrapper behind its suppressed contents. It would have pushed that device on every cycle
  forever. Captured as `frr_vrf_clean.txt` with a regression test.
- **The first Junos control fixture tested nothing.** It injected a *comment*, which is exactly
  what Junos does not round-trip and what the suppression rules are built to drop — so it passed
  against a broken normaliser. Re-captured with a real static route. The same class of mistake
  as trusting an empty diff, one level up.

### One pre-existing fragility found and deliberately not fixed

`load replace` on `interfaces` deletes the vSRX's `fxp0` management interface, because the
artifact mentions it only inside a comment. The firewall survives because vrnetlab restores it
as root seconds later — visible in the device's commit log as a `root via other` commit after
every `invoke provision`, at 14:21/14:23 and again at 16:49/16:51. This predates cycle 030 and
`invoke provision` has always done it. The reconciler must suppress that diff (it can never
close) but **the underlying fragility is worth its own cycle**: the firewall's management path
currently depends on vrnetlab racing the commit.

### Deferred as planned

Nornir (research R5). Scoped per-family credentials and a read-only compare pass (FR-071 —
deferred, not rejected). Alerting. Sequencing against Vidra.
