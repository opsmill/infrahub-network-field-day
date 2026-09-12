# Specification Quality Checklist: Junos Configuration for the Perimeter Firewall

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-12
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

The same two scoping caveats as cycles 020 to 022, for the same reasons: the extension's
transform template mandates naming the approach, output format and target nodes, so those are
the subject matter rather than leaked implementation; and success criteria that name repository
commands are unavoidable when the deliverable is a rendered artifact.

Validation findings resolved during authoring:

- **The line accounting was wrong and self-contradictory.** The first draft claimed 580 in scope
  and 97 out, and separately excluded a `flow` block it had already counted inside the in-scope
  `security` stanza. Measuring the file gives **573 in, 104 out**, and the exclusions now sum
  exactly: `system` 13 + `routing-options` 12 + `flow` 7 + 72 outside any top-level stanza = 104.
  Two stale figures elsewhere in the spec (a "592 in-scope lines" in US1 and an incomplete
  omission list in US3) were reconciled to match. This is the fourth cycle running in which a
  counted claim was wrong until it was measured, which is why SC-010 requires the enumeration to
  total rather than merely to exist.
- **SC-010 exists because of that.** A renderer that silently omits part of a firewall's
  configuration is more dangerous than one that does not exist, so "what is not covered" is a
  success criterion with an arithmetic check rather than a prose caveat.
- **FR-015, FR-043 and SC-005 were added once the `system` stanza was read.** It holds two
  `encrypted-password` hashes. The requirement is not merely that the artifact omits them but
  that the model never acquires them and the query never asks — the difference matters, because
  an artifact can be inspected and a graph is harder to audit.

**Re-scope after implementation (2026-09-12).** Implementation stopped at T011 with a blocking
finding: the seeded data does not transcribe the oracle (research.md R9). On the requester's
decision the seed repair was folded into this cycle rather than split into its own, making this
**two artifact types in one cycle** where the extension's routing normally takes one. The
deviation is recorded in the spec's Scope section and in plan.md rather than left implicit.

The spec gained US1 (the seed repair, now P1), FR-050 to FR-057 and SC-011 to SC-014; the three
original stories were demoted to P2–P4. The checklist items above were re-validated against the
extended spec and still pass.

Two further corrections belong to that finding:

- **The first gap count was overstated.** An oracle extractor that did not handle Junos' bracket
  form read `destination-address [ a b c ];` as empty. Re-counted properly the repair is 20 rule
  fields and 12 interface fields, not a rewrite. T020 now requires the test's parser to handle
  the bracket form, because that parser is what got it wrong.
- **`fw1` is a `SecurityFirewall`, not a `DcimDevice`**, which the spec originally assumed. It
  could have been a blocker, since the adopted schema could not have been edited to add
  `CoreArtifactTarget`; it already inherits it.

Zero [NEEDS CLARIFICATION] markers were raised. Three candidates each had a defensible default
recorded rather than a genuine fork needing the user:

- whether to render the whole file or only the modelled part — only the modelled part, with the
  gap enumerated and the follow-up named (Out of Scope)
- whether the eight `routing-options` static routes justify a schema change inside this cycle —
  no, that is a schema cycle first, the same 019→020 pattern the repository already follows
- whether to reproduce the file's `/* ... */` comments — yes, as cycle 022 did for the FRR
  configs, and at no cost (assumption 5)
