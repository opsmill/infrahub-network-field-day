# Implementation Plan: Crossplane FabricApp Manifest

**Branch**: `017-fabric-app-transform` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

## Summary

Render the `FabricApp` resource the lab's Crossplane composition consumes from a
`ServiceFabricApp`, with the manifests payload read from the `CoreFileObject` attachment cycle
013 added. Pure Python emitting through `yaml.dump`, following cycle 011's R1a.

Three things ship together because the transform cannot be proven without them: the VIP prefix
(absent from object data), the seeded application, and a committed seeding script that uploads
the payload — `object load` cannot upload file content.

## Technical Context

**Language/Version**: Python 3.11–3.13
**Primary Dependencies**: `infrahub-sdk`, `pyyaml` (declared in cycle 011); no new dependency
**Storage**: Infrahub graph plus object storage for the attachment
**Testing**: pytest over fixture query responses; live render compared with the lab's hand-written manifest
**Target Platform**: Infrahub task-worker and `infrahubctl transform`
**Project Type**: Infrahub reference-design repository
**Performance Goals**: One query round trip; the payload is a few kilobytes
**Constraints**: The `crossplane_fabric_peering` artifact checksum `0d800c9d5005b5fdb6b371bb5627d143` must not move (SC-010)
**Scale/Scope**: 1 query, 1 generated model, 1 transform, 1 seeding script, 1 payload file, 2 object additions, 1 test module, 3 registrations

## Constitution Check

| Principle | Initial | Post-Design |
| --- | --- | --- |
| **I. Schema-Driven** | ✅ PASS — cycle 013 added the attachment kinds; nothing new here | ✅ PASS |
| **II. Idempotent Operations** | ✅ PASS — the transform is read-only; the seeding script is idempotent by checksum (FR-021) | ✅ PASS |
| **III. Type Safety** | ✅ PASS — `.gql` plus generated `*_query.py` | ✅ PASS |
| **IV. Test-Required Quality** | ⚠️ CONDITIONAL — unit coverage planned; `$infrahub-run-integration-tests` **not installed** | ⚠️ CONDITIONAL |
| **V. Convention-Based Structure** | ✅ PASS — follows `crossplane_fabric_peering` exactly | ✅ PASS |

One conditional gate, unchanged from cycles 010–016.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **Principle IV** — `$infrahub-run-integration-tests` not installed | Mandated for every Infrahub change | Same exception and evidence set as cycles 010–016 |
| **A seeding script ships with a transform cycle** | `object load` cannot upload file content, and the transform cannot be proven against an empty attachment | Seeding the payload as an inline JSON attribute was rejected: `object load` returns HTTP 500 for dotted keys, which is the defect cycle 013 existed to route around |
| **Object data is added in a transform cycle** | The VIP prefix `10.112.240.0/28` does not exist, and `spec.expose.vipBlock` cannot be rendered without it | Hardcoding the CIDR in the transform was rejected — it is a modelled fact, and `vip_block` is a relationship for exactly that reason |

## Phase 0 — Research

See [research.md](research.md).

## Phase 1 — Design

See [data-model.md](data-model.md), [contracts/manifest-contract.md](contracts/manifest-contract.md) and [quickstart.md](quickstart.md).
