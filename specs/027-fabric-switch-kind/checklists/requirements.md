# Specification Quality Checklist: A Device Kind for Fabric Switches

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-14
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

The same scoping caveat as cycles 020 to 026: the extension's schema spec template mandates naming
kinds, attributes and relationships, so those are the subject matter rather than implementation
leaking in.

### A correction the spec is built on, not a footnote

The recommendation that led to this cycle said `DcimFabricSwitch` could **inherit `DcimDevice`**,
making the change additive so existing queries kept working. That was asserted without checking,
and it is wrong: Infrahub inheritance targets generics, and `DcimDevice` is a node. Verified
across all 86 nodes and 28 generics in `schemas/` — **every `inherit_from` targets a generic,
never a node**.

So the new kind is a **sibling**, queries naming `DcimDevice` stop seeing switches, and the cycle
is considerably larger than the recommendation implied. The spec is scoped around what can be
built rather than the easier thing that cannot, and the requester agreed to the cost knowing it.

This is the eighth correction of its kind in this sequence and the third caused by asserting how
something works instead of running a check first.

### What measurement changed

Three things were counted before the spec was written, not after:

- **The field spread**: 10 fabric-only, 3 router-only, 2 shared, 11 used by neither. The
  complaint that prompted this cycle — "lots of optional fields like vtep that FRR routers do not
  need" — is accurate, and now has a number.
- **The blast radius**: exactly **three** GraphQL queries break, all in the AVD path.
  `frr_config.gql` does not, because routers keep the kind. That is far smaller than the raw file
  counts (35 test files, 19 transform files) suggested, and it changed the shape of Assumption 2.
- **`evpn_gateway_group`**: zero objects exist, on any device, and the generator *raises* if a
  non-border-leaf carries one. It is the strongest single argument for the split — a constraint
  the schema cannot express, enforced by a runtime exception instead.

### The precedent that made this straightforward

`schemas/dcim_extensions.yml` already records the same decision for the firewall: *"a firewall is
its own device kind rather than a `DcimDevice` with a role"*. `SecurityFirewall` is already a
sibling inheriting the same generics, and `junos_config.gql` already targets it by name. This
cycle applies an established pattern rather than introducing one, which is why FR-002 copies
`DcimDevice`'s `inherit_from` exactly rather than designing a new hierarchy.

### Deliberately not raised as clarifications

Zero [NEEDS CLARIFICATION] markers. Three candidates had defensible defaults recorded:

- **Rename `DcimDevice` to something router-shaped?** No (Assumption 2). Narrowing the existing
  kind keeps the WAN's queries, objects and transforms still, and lands the churn on the AVD path
  where the new kind is needed anyway.
- **Where is the fabric/non-fabric boundary?** `ROLE_TO_AVD_TYPE` (Assumption 3). It already
  enumerates the ten EOS roles and already raises on anything else; drawing a second line would
  create somewhere for the two to disagree.
- **Remove the eleven unused fields while in there?** No (Assumption 4). They divide into upstream
  generality, built-but-unpopulated, and possibly dead, and telling those apart is its own
  question.

### The risk this cycle carries

A query that names `DcimDevice` and meets a switch returns **nothing, silently**. That is the
exact failure that hid the cabling plan's missing cables for months, and SC-008 exists because of
it: every `... on DcimDevice` site must be retargeted or proven never to encounter a switch.
Counting them is not enough — the plan needs each one decided.
