# Specification Quality Checklist: The WAN's Addressing

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-11
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

The same two scoping caveats as cycle 020 apply, and for the same reasons: this is an object
data specification, so node kinds, relationships and counts *are* the subject matter and the
extension template mandates naming them; and success criteria that name repository commands are
unavoidable when the deliverable is YAML the repository loads.

Validation findings resolved during authoring:

- **The counts were internally inconsistent in the first draft** — 19 interfaces against 20
  addresses, which cannot both be true when every in-scope interface carries exactly one
  address. Re-parsing the oracle showed the error was in the scope cut, not the arithmetic: the
  draft excluded `br-branch` along with the three enslaved access ports. `br-branch` is the
  branch router's LAN-facing layer-3 interface holding `10.70.0.1/24`, which is the same thing
  every customer edge's `eth2` is; excluding it would have left the branch as the only router
  with no LAN side. Corrected to 20 and 20, with assumption 3 rewritten to explain the line
  between a bridged access port and an addressed LAN interface.
- Every count in the spec is derived by parsing `../lab/wan/tenants.yml`, not by reading it —
  20 interfaces, 20 addresses, 5 ASNs, 10 BGP neighbours, 6 router IDs, 1 static route.

Zero [NEEDS CLARIFICATION] markers were raised. Three candidates were considered and each had
a defensible default recorded in Assumptions or Out of Scope rather than a genuine fork needing
the user:

- whether to seed the lab's end hosts — no, their device objects do not exist, and creating
  them is a larger question than this cycle (assumption 2)
- whether the branch's bridged access ports belong in the model — no, they are plumbing
  (assumption 3)
- whether to reconcile `WanSite.site_asn` with the new `RoutingAsn` objects — no, that is a
  cleanup in a cycle that is otherwise purely additive (assumption 6)
