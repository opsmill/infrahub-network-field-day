# Specification Quality Checklist: FRR Configuration for the WAN

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

The same two scoping caveats as cycles 020 and 021, for the same reasons: the extension's
transform template mandates naming the approach, the output format and the target nodes, so
those are the subject matter rather than leaked implementation; and success criteria that name
repository commands are unavoidable when the deliverable is an artifact the repository renders.

One caveat specific to this cycle: **SC-009 is deliberately a judgement, not a command.** "The
lab could delete its renderer and lose nothing" cannot be asserted by a test. It is the
criterion that says the end goal is met for the WAN, and it is answered by a person walking the
six configs — which is how cycles 020 and 021 answered their equivalent criteria too.

Validation findings resolved during authoring:

- **SC-003 said "three lines" and the oracle says four.** The clause the lab's template guards
  behind `{% if t.internet %}` is `route-map ... permit 30`, its description, its match, **and
  the `!` separator that closes the block** — verified by reading the template and the rendered
  output rather than counting the visible statements. Corrected in SC-003, in US2's independent
  test, and in the introduction, which had repeated the same wrong number.
- **The `PL-DEFAULT` prefix-list was checked and does *not* move.** It is guarded by
  `{% if isp.internet is defined %}` — the ISP having an internet connection — not by any tenant
  buying access, so removing acme's service leaves it in place. Stated in SC-003 so the test
  cannot be written against the wrong expectation.
- **Byte-for-byte parity has exactly one exclusion, and it was nearly missed.** Every lab config
  opens with `! Rendered by wan/render.py for <node> -- do not edit.` Asserting literal
  byte-for-byte parity would have required Infrahub to claim it was `wan/render.py` in six
  device configurations. Recorded as an edge case, in assumption 2, in FR-023 and in SC-001.

Zero [NEEDS CLARIFICATION] markers were raised. The three candidates each had a defensible
default recorded rather than a genuine fork needing the user:

- whether to port the lab's templates or write fresh ones against the golden files — port
  (assumption 1); they are already Jinja2 and known correct
- whether a renderer may read the service layer, given cycle 010's assumption 6 — yes for the
  provider edge, whose import policy *is* the service intent (assumption 3)
- whether to also render `init.sh`, `daemons` and the host scripts — no, they are container
  plumbing rather than routing intent (Out of Scope)
