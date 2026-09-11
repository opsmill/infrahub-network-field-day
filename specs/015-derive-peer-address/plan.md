# Implementation Plan: Derive the Peering Address

**Branch**: `015-derive-peer-address` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

## Summary

Change `generate_fabric_peering.py` to derive `peer_address` from the peer device's peering
SVI, the way it already derives `peer_asn` from the device's `RoutingAsn`. Cycle 014 supplied
the missing link; this consumes it.

Two consequences beyond the field itself. The **create path becomes reachable** — cycle 012
recorded "there is no create shape, and there cannot be" as a real limitation, because an
address could only come from an existing session. And `objects/34_nfd41_cluster.yml` loses its
last hand-declared value, so the split-ownership annotation cycle 012 wrote comes off.

## Technical Context

**Language/Version**: Python 3.11–3.13
**Primary Dependencies**: `infrahub-sdk`; no new dependency
**Storage**: Infrahub graph
**Testing**: pytest over fixture query responses, plus a live double-run and the artifact checksum
**Target Platform**: Infrahub task-worker and `infrahubctl generator`
**Project Type**: Infrahub reference-design repository
**Performance Goals**: One query round trip per service, unchanged
**Constraints**: The artifact checksum `0d800c9d5005b5fdb6b371bb5627d143` must not move
**Scale/Scope**: 1 query extended, 1 generated model regenerated, 1 generator changed, 1 object file trimmed, 1 test module extended

## Constitution Check

| Principle | Initial | Post-Design |
| --- | --- | --- |
| **I. Schema-Driven** | ✅ PASS — no schema change; cycle 014 established none is needed | ✅ PASS |
| **II. Idempotent Operations** | ⚠️ CONDITIONAL — mechanics are central to the design; `$infrahub-test-generator-idempotence` is **not installed**, as in cycle 012 | ⚠️ CONDITIONAL |
| **III. Type Safety** | ✅ PASS — regenerated `*_query.py`, consumed through Pydantic models | ✅ PASS |
| **IV. Test-Required Quality** | ⚠️ CONDITIONAL — unit coverage planned; `$infrahub-run-integration-tests` **not installed** | ⚠️ CONDITIONAL |
| **V. Convention-Based Structure** | ✅ PASS — extends an existing generator in place | ✅ PASS |

Two conditional gates, identical to cycle 012's and recorded in its Complexity Tracking. The
alternative evidence is the same and is stronger here: the artifact checksum is a direct
regression oracle for the exact field being changed.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **Principle II** — `$infrahub-test-generator-idempotence` not installed | Mandated for generator changes | Same alternative as cycle 012: fixture unit tests, a live double-run, and the artifact checksum compared before and after. The third validates the observable output rather than object counts |
| **Principle IV** — `$infrahub-run-integration-tests` not installed | Mandated for every Infrahub change | Same exception as cycles 010–014 |
| **An object data file is edited in a generator cycle** | `objects/34_nfd41_cluster.yml` must lose its hand-declared addresses, or the copy this cycle removes survives | Leaving them was rejected: object load would keep reasserting a value the generator derives, which is the drift the cycle exists to end |

## Phase 0 — Research

See [research.md](./research.md). The decisive one:

- **R1 — the SVI is selected by `role == "peering"`**, verified live: exactly one such interface
  exists per k8s leaf, carrying exactly one address. Selection by interface role is a property
  of the model rather than a position in a list.

## Phase 1 — Design

Design artifacts:

- [data-model.md](./data-model.md)
- [contracts/generator-contract.md](./contracts/generator-contract.md)
- [quickstart.md](./quickstart.md)
