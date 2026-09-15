# Specification Quality Checklist: Deployment reconciler

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-15
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

**Both markers resolved.** FR-070 and FR-071 were carried from the design review's own
open-items list and left as questions rather than defaulted, because each changes *what gets
built*, not how. Answers taken:

- **FR-070 — the service lives in this repository**, beside the script it lifts and the schema
  it writes to. The editorial cost is real (this repo is the published reference design) and is
  handled by FR-072 and FR-073 rather than by hoping nobody notices.
- **FR-071 — the existing environment variables are reused.** A deliberate acceptance of a
  larger blast radius, bounded by `suspend`, the interval floor and the dry run, and written
  down in FR-074 and FR-075 so the next environment meets the decision instead of inheriting
  it.

Everything else the review left open **was** defaulted and documented in Assumptions rather
than asked: the orchestrator (a plain loop, not Temporal), ordering against Vidra (not
enforced — both are reconcilers and converge), and alerting (none; the record is the signal).
Each records the reasoning so the default can be challenged without reconstructing it.

**On "no implementation details"**: the spec names the three device families and the fact that
each computes its own diff. That is not implementation leakage — it is the load-bearing design
conclusion from decision log item 12, the difference between a reconciler that detects drift
and one that only detects changed intent. Mechanism (Nornir, the loop, the module lift) is
named only where a requirement constrains it, most notably FR-050's "lifted, not rewritten".

**One requirement deliberately demands a decision rather than making one**: FR-028, the write
cadence. Cycle 029 shaped the schema so either answer is expressible and recorded the cost of
each; this spec requires the choice to be made explicitly and stated, rather than inherited by
whichever way the first implementation happens to be written.
