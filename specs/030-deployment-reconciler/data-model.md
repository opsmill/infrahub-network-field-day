# Phase 1 data model: deployment reconciler

**Feature**: `specs/030-deployment-reconciler` | **Date**: 2026-09-15

This cycle defines **no new persisted entities**. The graph model was built in cycle 029 and
is unchanged; what follows is how this service reads and writes it, plus the in-process types
the reconciler needs.

---

## Persisted entities (existing — `schemas/deployment.yml`)

### `DeploymentState` — one record per device

This service is its **only** writer.

| Field | Kind | Written when | By what rule |
| --- | --- | --- | --- |
| `name` | Text, unique | On create, and refreshed each cycle | FR-023. It is the device's name copied; cycle 029 made keeping it in step this service's job |
| `status` | Dropdown | On change only | See the transition table below |
| `last_confirmed_at` | DateTime | **Only** when the device itself reported no difference | FR-021. Never because a push was sent |
| `last_checked_at` | DateTime | **Every cycle**, for every device visited | FR-022, research R8 |
| `last_attempt_at` | DateTime | When a push is attempted | — |
| `last_error` | TextArea | On failure; cleared on the next success | — |
| `suspend` | Boolean | **Never** — read only | FR-014. This is the operator's field |
| `suspend_reason` | Text | **Never** — read only | As above |
| `device` | rel → `DcimGenericDevice` | On create | Optional in the schema; see the sweep rule |
| `last_diff` | rel → `DeploymentDiffFile` | When a difference is found | FR-026 |

**Two fields this service must never write.** `suspend` and `suspend_reason` belong to the
operator. A reconciler that clears its own break-glass is not a break-glass.

### `DeploymentDiffFile` — the evidence

Written when a difference is found, holding the **normalised** device output (research R4) with
the raw output retained beneath it, so an operator sees both what was decided and what the
device actually said.

### The sweep

Records whose `device` no longer resolves are deleted (FR-025). Cycle 029 measured why this is
the service's job rather than the schema's: a mandatory `device` relationship makes any device
that has ever held a record permanently undeletable.

---

## Status transitions

Read against the device's **normalised** diff, never its raw output.

| From | Event | To | Also written |
| --- | --- | --- | --- |
| any | normalised diff empty | `in_sync` | `last_confirmed_at`, `last_checked_at` |
| `in_sync` | diff non-empty, artifact checksum **changed** | `pending` → push → `in_sync` | `last_checked_at`, `last_attempt_at` |
| `in_sync` | diff non-empty, artifact checksum **unchanged** | `drifted` → push → `in_sync` | as above, plus `last_diff` |
| any | push or comparison raised | `failed` | `last_error`, `last_checked_at` |
| any | `suspend` set | **unchanged** | nothing at all |

**`pending` vs `drifted` is the only place the artifact checksum is used.** It does not decide
*whether* to push — the device's diff does that (FR-010) — it decides which of two structurally
different causes to record, which is what an operator reading the record needs to know
(decision log item 15: drift "is the one that can fight a person").

**A suspended device has no transition.** Its status keeps whatever it last showed, and
`last_checked_at` does not move either — the device was not checked. A moving timestamp on a
device nobody looked at would be a lie.

---

## In-process types

Not persisted; they exist for the length of a cycle.

- **`Target`** (exists, `scripts/provision_lab.py`): one device, its rendered artifact, and the
  identifier it can be reached by — `mgmt_ip` for switches, container name for FRR and the
  firewall, because Infrahub's names and ContainerLab's do not match and there is no renaming
  layer. Reused unchanged.
- **`Comparison`**: `{target, raw_diff, normalised_diff, differs}`. `differs` is
  `bool(normalised_diff)` and nothing else reads `raw_diff` to make a decision.
- **`CycleReport`**: per-device outcome for one cycle — compared, differed, pushed, failed,
  skipped-suspended, skipped-not-due (the firewall on three cycles in four). This is what
  FR-060 logs.

---

## Validation rules

| Rule | Source | Enforced where |
| --- | --- | --- |
| One record per device | FR-024 | Upsert on `name`; the graph enforces uniqueness on `name`, not on the device relationship |
| Confirmation means the device matched | FR-021 | Only the empty-normalised-diff branch writes `last_confirmed_at` |
| An unrecognised diff line is a difference | FR-011a | Normalisation is an allowlist, not a denylist |
| Exit status is not a difference signal | FR-011b | Measured: `frr-reload.py --test` returns `0` either way |
| Never push an empty artifact | FR-012 | Download and length-check before comparison, regardless of `Ready` |
| A suspended device is not contacted | FR-014 | Suspension is read before the device is reached, not after |
| Nothing generates from these kinds | FR-027 | `tests/unit/test_deployment_schema_contract.py`, from cycle 029 |

---

## What this service does not model

- **Its own state.** It restarts with nothing and behaves correctly (FR-020). Everything it
  needs to know is either in Infrahub or on the device.
- **History.** Each record is current state; Infrahub's own versioning is the audit trail.
- **A schedule.** The interval is configuration, not data (spec assumption).
