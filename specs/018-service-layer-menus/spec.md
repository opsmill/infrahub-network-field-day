# Menu Specification: Service and Technical Layer Navigation

> **Workflow type**: Infrahub Menu
> **Skill**: Use the `infrahub-managing-menus` skill to implement this specification.

**Feature Branch**: `018-service-layer-menus`
**Created**: 2026-09-11
**Status**: Complete
**Input**: "Please tackle the outstanding items" — the menu cycle 010 deferred.

## Why this cycle exists

Cycle 010 added 28 menu-visible kinds across five new domains — services, security, cluster,
WAN and tenancy — and deferred the menu itself. Every one of those kinds is currently
**unreachable from the sidebar**: present in the schema, invisible in the UI.

010's FR-065 already states the requirement in full: *"Service nodes MUST be placed in the menu
beneath a service grouping, and technical nodes beneath their domain grouping, so the UI
reflects the two-layer split."* There is no design uncertainty to research, so this cycle is
deliberately lean — a spec, the work, and contract tests — rather than the five design
documents cycles 011 through 017 each needed. Recording that judgement is the point of writing
it down.

## Requirements

- **FR-001**: All six concrete service kinds MUST sit under one top-level `Services` grouping, because they are ordered intent rather than device fact
- **FR-002**: No service kind may appear anywhere else in the menu — the split is only legible if a service has one home
- **FR-003**: Technical kinds MUST sit under their domain grouping: Security, Kubernetes, WAN, Tenancy
- **FR-004**: The security address book and service catalogue MUST be nested, not flat — sixteen sibling entries is a list nobody reads
- **FR-005**: Every menu entry's `kind` MUST exist in the schema
- **FR-006**: Every menu-visible kind in the new domains MUST be reachable from the menu
- **FR-007**: Every leaf entry MUST carry a label and an icon
- **FR-008**: Namespace and name pairs MUST be unique
- **FR-009**: The menu MUST load without error and be idempotent across repeated loads

## Success Criteria

- **SC-001**: The menu has a `Services` section containing exactly the six service kinds
- **SC-002**: Security, Kubernetes, WAN and Tenancy sections exist with children
- **SC-003**: No menu entry names a kind that does not exist
- **SC-004**: No menu-visible kind in the new domains is unreachable
- **SC-005**: `infrahubctl menu load` succeeds, and a second load produces no error
- **SC-006**: All unit tests and the repository's linters pass

## Out of Scope

- Re-organising the eight pre-existing sections. They work; churn there would be gratuitous.
- `include_in_menu` changes. The schema already says which kinds are user-facing.
- Menu ordering weights. Infrahub renders declaration order, which is sufficient here.
