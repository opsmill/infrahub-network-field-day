# Implementation Plan: Deployment reconciler

**Branch**: `030-deployment-reconciler` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/030-deployment-reconciler/spec.md`

## Summary

Build the reconciler cycle 029 made room for: a loop that every 600 seconds asks each device to
compare itself against its rendered artifact, pushes when they differ, corrects drift, honours a
per-device `suspend` flag, and records **last confirmed to match** into the `Deployment` kinds.
No webhook, no approval gate, no separate state store — all removed under challenge in the
design review.

**Phase 0 found a defect in the spec, not a confirmation of it.** The review's conclusion that
all three families "compute the diff themselves" is true, and the conclusion drawn from it —
that an empty diff means in-sync — is false for two of them. Measured against the running lab:

| Family | Unchanged artifact reports | Verdict |
| --- | --- | --- |
| EOS | **0 characters** | Usable as-is |
| FRR | `Lines To Add` with BGP defaults, `service integrated-vtysh-config`, `line vty` | **Permanent false positive** |
| Junos | **55 changed lines** — zone-pair ordering and comment round-tripping | **Permanent false positive** |

A naive implementation would therefore replace the configuration of every FRR router and the
perimeter firewall **on every cycle, forever**, while reporting success. The plan adds a
per-family normalisation layer (FR-011a) as a first-class component, and the spec has been
amended rather than leaving this to be discovered at 3am.

Phase 0 also **dropped Nornir** (research R5). The inventory is already solved by
`provision_lab.discover()`, fifteen devices have ample sequential headroom at a 600-second
interval, and the review had itself recorded that per-host work inside Nornir's thread pool
does not survive contact with the surrounding async context. Two new direct dependencies need a
better reason than "we might parallelise later".

## Technical Context

**Language/Version**: Python 3.12.13 (project constraint >=3.11,<3.14).

**Primary Dependencies**: `httpx` (present), `pyyaml` (present), `infrahub-sdk` (present).
**No new direct dependency** — Nornir dropped in R5. Device access is eAPI over `httpx` and
`docker exec` via `subprocess`, exactly as `scripts/provision_lab.py` does today.

**Storage**: Infrahub graph only. The service holds no local state and restarts clean (FR-020).

**Testing**: `pytest`. Unit tests for the guards and the normalisation rules, run against
**captured real device output** from Phase 0 with no lab and no Infrahub. Integration tests for
the cycle against a live instance — unlike cycle 029, the constitution's integration gate
applies properly here.

**Target Platform**: a long-running container beside the existing stack, in this repository
(FR-070), plus an invoke entry point for a single cycle and for the dry run.

**Project Type**: standalone service. It creates no Infrahub artifact — no schema, generator,
transform, check, menu or object data.

**Performance Goals**: one cycle must complete well inside the 600-second interval for ~15
devices. The firewall's `_wait_for_vsrx` can block up to 600s on its own, which is a reason it
is checked every fourth cycle and last.

**Constraints**: `main` only. Never trust `Ready`. Every push is a replace. The firewall takes
an exclusive lock, so it is never parallelised and never checked more than once in four cycles.

**Scale/Scope**: 7 fabric switches, 6 FRR routers, 1 firewall. One new module package, one
compose service, two invoke tasks, and the lift of a 678-line script.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1.*

| Principle | Status | Evidence |
| --- | --- | --- |
| **I. Schema-Driven Architecture** | **Pass (not engaged)** | No schema change. The kinds this service writes were defined in cycle 029, before this code exists — which is the principle working as intended. `protocols.py` already carries them. |
| **II. Idempotent Operations** | **Pass** | Not a generator, but the principle is the core of the design: the loop is the retry, every push is a replace, and the next cycle recomputes from scratch. The measurable form is SC-002 — an in-sync fabric produces **zero** device changes across ten consecutive cycles. That is the assertion FR-011a exists to make true, and the one a naive implementation fails silently. |
| **III. Type Safety** | **Pass** | mypy with `disallow_untyped_defs` over the new module. The GraphQL discovery query is existing and typed by its dataclass; no new `.gql` is added, so no new `*_query.py`. |
| **IV. Test-Required Quality** | **Pass** | Unit tests for the guards (which have **none** today) and for the normalisation rules against captured output. `$infrahub-run-integration-tests` applies and is planned — this cycle has real Infrahub interactions, unlike 029. All linters via `uv run invoke lint`. |
| **V. Convention-Based Structure** | **Pass** | New code under `src/solution_arista_avd/`, tests under `tests/unit` and `tests/integration`, invoke tasks in `tasks.py`, documentation under `docs/docs/`. No new top-level directory. |

**Post-Phase-1 re-check**: passes, with one item promoted to Complexity Tracking — the
editorial cost of FR-070, which is a governance question rather than a principle violation.

## Project Structure

### Documentation (this feature)

```text
specs/030-deployment-reconciler/
├── spec.md                       # amended in Phase 0 with FR-011a/FR-011b
├── plan.md                       # this file
├── research.md                   # nine findings, all measured against the running lab
├── data-model.md                 # how the cycle-029 kinds are read and written
├── quickstart.md                 # ten-step validation, control tests included
├── contracts/
│   └── device-comparison.md      # the per-family compare/push/cleanup contract
└── checklists/requirements.md
```

### Source code (repository root)

```text
src/solution_arista_avd/deployment/
├── __init__.py
├── devices.py          # LIFTED from scripts/provision_lab.py — moved, not rewritten (FR-050)
├── compare.py          # per-family compare(); the contract in contracts/
├── normalise.py        # FR-011a — explicit, tested, fail-noisy
├── state.py            # reads and writes DeploymentState / DeploymentDiffFile
└── reconcile.py        # the cycle, the interval, the floor, the sweep

scripts/provision_lab.py          # becomes a thin CLI over deployment.devices (FR-051)

tests/unit/
├── test_deployment_devices.py    # the guards — none exist today
├── test_deployment_normalise.py  # against captured real device output
└── fixtures/deployment/          # the Phase 0 transcripts

tests/integration/
└── test_reconcile_cycle.py

tasks.py                          # `invoke reconcile`, `invoke reconcile --dry-run --branch X`
docker-compose.override.yml       # the long-running service
docs/docs/                        # FR-072, FR-075
```

**Structure Decision**: the reconciler lives in `src/solution_arista_avd/deployment/` rather
than under `scripts/`, because `scripts/` holds entry points and this is library code with
tests. The lift makes `provision_lab.py` a thin CLI over the same functions, which is what
keeps FR-051 honest — `invoke provision` keeps working because it is calling the same code, not
a copy of it.

## Key risks, and what covers them

| Risk | Cover |
| --- | --- |
| **Permanent false-positive diffs churn the fabric** | FR-011a normalisation, fail-noisy; SC-002 asserts zero changes over ten cycles; unit tests over captured output |
| **Normalisation hides a real change** | Allowlist, not denylist. An unrecognised line is a difference, so the failure mode is an unnecessary push |
| **An empty artifact is pushed as a replace** | FR-012: download and length-check, never trust `Ready` |
| **A killed cycle strands an EOS session or a Junos lock** | FR-030 sweep at cycle *start*; `try/finally` does not survive SIGKILL |
| **Two instances push to the same device** | Single compose service, sequential loop; a marker in Infrahub is the deferred belt-and-braces (R9) |
| **Credentials in a long-running service** | Accepted and bounded (FR-071, FR-074, FR-075): env only, `suspend`, the floor, the dry run. No least privilege exists here and the docs must say so |

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| A bespoke executor in the published reference design (FR-070) | The user chose this repository: it keeps the lift a file move within one test suite, beside the schema it writes to. | The lab repository or a standalone repo would split the device knowledge from the schema and version them independently. The editorial cost is real — this repo syncs to `opsmill/infrahub-docs` — and is paid down by FR-072 (documented as a reference implementation, not a supported component) and FR-073 (existing workflows behave identically whether or not the service runs). |
| Lab-admin credentials in a long-running service (FR-071) | The user chose to reuse the existing environment variables; no new credential machinery this cycle. | Scoped per-family accounts and a read-only compare pass are strictly better and were **deferred, not rejected**. They need accounts provisioned on the cEOS nodes, the FRR containers and the vSRX before anything can run. FR-075 requires the blast radius be documented so the next environment meets the decision rather than inheriting it. |

## Phase 2 preview (not executed by this command)

`/speckit-tasks` will split this roughly as: lift `provision_lab.py` into `deployment/devices.py`
with the guard tests (US7, and it unblocks everything else); `compare.py` and `normalise.py`
against the Phase 0 transcripts (the heart — US1 and US4 both depend on it); `state.py` (US2);
the cycle with its interval, floor, firewall cadence and sweep (US1, US5); `suspend` (US3);
the dry run (US6); then the compose service, the docs required by FR-072 and FR-075, and the
integration run.

**The order is not negotiable in one place**: normalisation must land with — not after — the
first working compare, because a compare that reports false positives is worse than no compare
at all. It will happily push every device in the fabric and report success.
