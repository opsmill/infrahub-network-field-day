# Specification Quality Checklist: Zone Advertisement Policy

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-16
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

**Iteration 1 (2026-09-16)** — all items pass.

### The decision this spec turns on

**There are zero `RoutingPrefixList` objects in the graph.** Verified against
`main` before writing. The fabric's entire BGP policy lives inside
`NetworkFabric.avd_custom_hostvars` as AVD custom structured configuration, so
there is no object for a zone to point at.

That forced a fork, and the spec takes one side explicitly rather than marking
it for clarification:

- **Taken** — model the *reference*: the zone records the prefix list's name and
  the device carrying it, and User Story 3 requires the reference be checkable.
- **Rejected** — migrate the policy into `RoutingPrefixList` objects first. It is
  a large migration touching every rendered device configuration, and it fights
  a design the repository chose deliberately (custom structured config is AVD's
  documented channel for un-modelled inputs).

The rejected option is recorded in Assumptions with the condition under which it
would be revisited, so the choice is reviewable rather than buried.

### Why a soft name reference is defensible here, having been rejected once

Cycle 031 research R2 rejected deriving a value by naming convention
(`PL-DC-ADVERTISED-<ZONE>`), because it "happens to be right today". This spec
is not that: the name is **authored data**, not inferred, and FR-030 plus User
Story 3 require the mismatch to be detectable. An authored name a check
validates is a different thing from a name a generator guesses. Called out in
Assumptions because the distinction is easy to lose.

### Judgement calls recorded rather than raised as markers

- *One carrying device per zone* (cardinality one). Nothing in the lab needs
  many, and widening later is additive.
- *No new node or generic.* FR-003 makes this an explicit tripwire: needing one
  means the design drifted toward migration.
- *The write mechanism* — device-scope `avd_custom_hostvars` merged by
  `_merge_lists` identity — is recorded as settled context, not specified here.
  It is what makes the next cycle viable and it is verified, so stating it
  prevents the plan phase re-deriving it.

### Content-quality note

The spec names real repository artifacts (`SecurityZone`,
`avd_custom_hostvars`, `PL-DC-ADVERTISED-BRANCH`, `objects/32_nfd41_security.yml`).
For a schema spec these are the subject matter, not implementation leakage — a
data-model spec that could not name the data model could not be reviewed.

### Risk carried into planning

**FR-021 is the one easy to get wrong.** The carrying device is a border leaf,
which is a `DcimFabricSwitch`. `AGENTS.md` warns that the four device kinds are
siblings and that "a query naming `DcimDevice` does not see a fabric switch and
reports nothing". A relationship peered at `DcimDevice` would validate, load,
and match nothing — silently. FR-061 exists to catch exactly that.

Ready for `/speckit-clarify` or `/speckit-plan`.
