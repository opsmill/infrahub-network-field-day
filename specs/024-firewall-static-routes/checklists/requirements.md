# Specification Quality Checklist: Device-Level Static Routes for the Perimeter Firewall

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

The same scoping caveat as cycles 020 to 023: the extension's schema spec template mandates
naming kinds, attributes, relationships and constraints, so those are the subject matter of a
schema spec rather than implementation leaking into it.

### Findings resolved during authoring

- **The premise this cycle inherited was wrong.** Cycle 023 recorded, and `AGENTS.md` repeats,
  that `routing-options` needs "a device-level static route the schema does not have".
  `RoutingStaticRoute` has existed in `schemas/routing/routing.yml` throughout, with every
  attribute the eight routes need. The real blocker is one relationship peer. This shrinks the
  cycle from designing a kind to widening a relationship, and US3 exists so the incorrect
  sentence is corrected rather than left to mis-size cycle 025.

  This was the fifth cycle running in which a claim was wrong until it was measured, and the
  second time the wrong claim was one this project had written down about itself. Phase 0 then
  made it six, with a claim this spec wrote about itself. The pattern is unchanged: a conclusion
  drawn from an incomplete read, stated with more confidence than it had earned.

- **A claim in the first draft of this very spec was also wrong.** It said `MARKETPLACE.md` lists
  only `security/security.yml` as adopted. It lists four files. The load-bearing fact —
  `routing/routing.yml` is not adopted, so it can be edited directly — survived, but the
  supporting claim was corrected before the checklist was marked, rather than after.

- **SC-002 measures the change, not the end state.** "A static route on `fw1` loads" would pass
  trivially if the schema were already correct. Requiring the before-state to fail makes the
  criterion about this cycle's effect.

- **SC-003 is a regression guard, and it needs to be.** Widening a peer touches a kind other
  code reads, and that is exactly the kind of risk that passes a schema check and fails at render
  time. *(As first written this bullet went on to say the kind holds no data. Phase 0 disproved
  that — see the re-validation below — and SC-003 was widened accordingly.)*

- **An unavoidable side effect is recorded rather than hidden.** `DcimGenericDevice` is inherited
  by `ComputePhysicalServer` as well, so the widening lets a server hold a static route. The
  schema language offers no peer that names exactly two kinds, so the alternatives were a generic
  peer or a second relationship; the spec argues for the generic in Assumption 1 and names the
  consequence in Edge Cases instead of omitting it.

### Deliberately not raised as clarifications

Zero [NEEDS CLARIFICATION] markers. Two candidates had defensible defaults recorded instead:

- **Widen the peer, or add a firewall-specific relationship?** Widen. Assumption 1 gives the
  argument: a second relationship would need a second identifier, would make `device` ambiguous,
  and would give the next renderer two places to look.
- **Fold the seed data into this cycle?** No. Cycle 023 folded its objects in because
  implementation was *blocked* by a discovery mid-cycle; here the seed work is ordinary
  transcription that can wait for a proven schema. The Next cycles section records that folding
  remains available on request.

### Re-validated after Phase 0 (2026-09-12)

Phase 0 overturned one of this spec's own assumptions, so the checklist above was re-run against
the amended spec and still passes. Three amendments were made:

- **Assumption 2 withdrawn and replaced.** It claimed nothing seeds `RoutingStaticRoute`, from a
  search of `objects/`. The search was right; the conclusion was not. Eleven objects exist on
  `main`, created by the `backfill-structured-config` generator. The decision is unchanged —
  research R5 loaded the widening onto a branch holding all eleven — but the assumption now
  states what was demonstrated rather than what was inferred.
- **SC-003 widened** to cover the generator, not only `frr_config`. The generator writes this
  kind on every run and upserts against a constraint naming `device`, which puts Constitution
  principle II in scope.
- **SC-010 added.** Nothing in the repository pins this relationship: ten schema-contract test
  modules exist and none reads `routing/routing.yml`. The suite passes whether the peer is right
  or wrong, so SC-001 and SC-008 were resting on a manual check.

The failure shape was the same one the notes above already record for cycle 023 and its
predecessors: **a claim about the whole system asserted from evidence about one part of it.** The
difference this time is that it was caught inside the same cycle, by Phase 0 running the change
instead of reasoning about it.

### Carried forward for cycle 026, not resolved here

The `routing-options` stanza is column-aligned by hand and **inconsistently** — two of its eight
route lines are misaligned by one column, so no single derivation reproduces all eight. That was
measured while sizing this cycle and is recorded in the spec while the evidence is in hand. It
decides a success criterion in 026 and affects nothing here, because this cycle stores no
presentation.
