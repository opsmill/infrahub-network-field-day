# Implementation Plan: Peering Consistency Check

**Branch**: `016-peering-consistency-check` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

## Summary

A global proposed-change check enforcing six consistency rules over the peering model. Cycles
010–015 built a model to prevent drift and measured themselves against an artifact checksum;
none of them refuses a merge. This does.

Every rule is pure graph, because the fabric's rendered view does not exist on this instance —
verified, and recorded in the spec as the reason the most obvious rule is out of scope.

## Technical Context

**Language/Version**: Python 3.11–3.13
**Primary Dependencies**: `infrahub-sdk` (`InfrahubCheck`); no new dependency
**Storage**: Infrahub graph, read-only
**Testing**: pytest over fixture query responses, plus a live run against a seeded violation
**Target Platform**: Infrahub proposed-change pipeline
**Project Type**: Infrahub reference-design repository — check under `checks/`
**Performance Goals**: One query; the lab has 2 sessions and 16 SVI nodes
**Constraints**: Read-only. The check must not write, and must not fail a model the generator produced
**Scale/Scope**: 1 query, 1 generated model, 1 check class, 1 registration pair, 1 test module

## Constitution Check

| Principle | Initial | Post-Design |
| --- | --- | --- |
| **I. Schema-Driven** | ✅ PASS — no schema change; reads existing kinds | ✅ PASS |
| **II. Idempotent Operations** | ✅ PASS — read-only; a check writes nothing | ✅ PASS |
| **III. Type Safety** | ✅ PASS — `.gql` plus generated `*_query.py` | ✅ PASS |
| **IV. Test-Required Quality** | ⚠️ CONDITIONAL — unit coverage planned; `$infrahub-run-integration-tests` **not installed** | ⚠️ CONDITIONAL |
| **V. Convention-Based Structure** | ✅ PASS — follows `checks/fabric_pool_check.py` | ✅ PASS |

One conditional gate, unchanged from cycles 010–015. Principle II is genuinely satisfied here
rather than waived — a check has nothing to make idempotent.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **Principle IV** — `$infrahub-run-integration-tests` not installed | Mandated for every Infrahub change | Same exception and evidence set as cycles 010–015: fixture unit tests over every rule, plus a live run against a deliberately seeded violation and against a clean model |

## Phase 0 — Research

See [research.md](./research.md). The decisive finding is in the spec: there is nothing
rendered to compare against, so every rule is pure graph.

## Phase 1 — Design

Design artifacts:

- [data-model.md](data-model.md)
- [contracts/check-contract.md](contracts/check-contract.md)
- [quickstart.md](quickstart.md)
