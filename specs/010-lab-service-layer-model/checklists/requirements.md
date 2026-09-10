# Specification Quality Checklist: Technical and Service Layers for the Full NFD41 Lab

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-10
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

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

### Validation record

**Iteration 1** — three items failed and were fixed:

1. *No implementation details* — the first draft named Infrahub schema YAML keys
   (`inherit_from`, `Component`, `identifier`) throughout the user stories. Schema
   mechanics are legitimate in the Functional Requirements of a schema spec, since the
   template's own FR skeleton names them, but they were removed from the user stories
   and acceptance scenarios so those read as modeling outcomes rather than YAML
   instructions.
2. *Success criteria are technology-agnostic* — a criterion asserted "`FabricPeering`
   renders identically". Replaced with SC-005, which measures whether every field those
   resources consume has a modeled destination — an outcome, not a rendering assertion.
3. *Scope is clearly bounded* — the draft had no Out of Scope section, leaving the
   generator, transform, object, and menu cycles ambiguous. Added, and cross-referenced
   from the Context section's closing paragraph.

**Iteration 2** — all items pass.

### Deviations from the template

- The template's `#### Hierarchy (if applicable)` FR block is omitted. No node in this
  feature is hierarchical; the location tree it exists for is already modeled in
  `schemas/location_extensions.yml`. Per the core skill's section guidance, an
  inapplicable section is removed rather than left as "N/A".
- A `#### Layering` FR block (FR-080 to FR-082) was added. It carries the constraint
  the request turns on — that the two layers are separable and that a generator can sit
  underneath each service kind — which no template block covers.
- `## Context`, `### Layering contract`, `## Assumptions`, and `## Out of Scope` were
  added. The template has no Assumptions section, but the core skill requires
  documented defaults, so this feature's nine assumptions are recorded there.

### Open scope decisions confirmed with the requester

Three material forks were resolved by asking rather than by defaulting silently:

1. **Cycle scope** — all seven stories. One schema covering ISP, branches, firewall, and
   Kubernetes, so the cross-domain relationships are designed together rather than
   retrofitted.
2. **Firewall source of truth** — Infrahub owns the whole vSRX configuration, not only
   the access grants issued against it. Recorded as assumption 8; drives US4's
   modeling of policies and rules and SC-004.
3. **Crossplane delivery** — artifacts rendered by a transform and reconciled in-cluster
   by the Vidra operator, following `opsmill/infrahub-dogfooding`. Recorded as
   assumption 9; adds FR-083, the only requirement this decision places on the schema.
