# Specification Quality Checklist: Completing the Perimeter Firewall Artifact

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

The same scoping caveat as cycles 020 to 025: the extension's transform spec template mandates
naming the query, the transform, the templates and the artifact definition, so those are the
subject matter rather than implementation leaking in.

### The remaining work was larger than the running figure said

Every cycle since 023 has repeated "12 lines of `routing-options` and 7 of `flow`". Measured
against the **live render** rather than against the spec that produced it, the gap is bigger:

| Measured | Result |
| --- | --- |
| In-scope configuration lines | 459 |
| Rendered today | 440 |
| Missing configuration | **19** — the 12 + 7 already known |
| Configuration invented by the render | **0** |
| Comment blocks inside `security` | 13, of which **3 are absent** (~17 lines) |

So the configuration figure was right and the *file* figure was not: three explanatory comment
blocks are dropped, and one of them is the nine-line note on why NAT is absent and why that
absence is load-bearing. A renderer that drops it emits a configuration which looks complete and
has lost the reason it is safe.

This was found by diffing the live artifact against the device file rather than by re-reading the
earlier specs. Seven cycles running have now produced a claim that was wrong until something was
run; this one was inherited rather than newly invented, which is arguably worse — it had been
repeated in three commit messages, `AGENTS.md` and `.infrahub.yml`.

### Three counted claims in this spec were verified, not asserted

Computed from the file before the checklist was marked:

- `677 = 72 header + 13 system + 592 rest` — so SC-001's "592 lines" is the file minus the two
  excluded regions, not an estimate.
- `592 + 13 + 72 = 677` — SC-010's arithmetic closes.
- 459 in-scope configuration lines — SC-002's baseline.

SC-010 requires a **test** to assert the arithmetic, because a comment claiming a total is what
cycle 023 had when its accounting was wrong by seven lines.

### An accounting subtlety worth stating

The 72 "excluded" header lines are **68 comments and 4 blanks** — the lab's documentation about
the file, including how vrnetlab appends it to `init.conf`. They are not device configuration.
Calling them "excluded lines" alongside the `system` stanza flattens two different things:
`system` is configuration deliberately never modelled, the header is not configuration at all.
Assumption 3 states the distinction, and SC-001 is framed as "identical with the header and
`system` removed" rather than as a line count to hit.

### Deliberately not raised as clarifications

Zero [NEEDS CLARIFICATION] markers. Three candidates had defensible defaults recorded:

- **Fold three artifact types into one cycle?** Yes — the request was to complete all remaining
  tasks, which is the same kind of instruction cycle 023 acted on. The Deviation section argues
  it: the schema part is one optional attribute and the object part is one value, both existing
  solely so seven lines can render.
- **Reproduce the file header?** No. It would put a false provenance claim in the artifact; cycle
  022 made the same call for the FRR configurations.
- **Match the file's route ordering exactly?** Preferred, not required. Static routes are
  longest-prefix matched, so unlike cycle 023's zone-pair policies no behaviour depends on the
  sequence. Determinism is the requirement.

### Carried in from cycle 024's measurement — and then overturned

*As written before Phase 0:* the route lines are column-aligned by hand and inconsistently, no
single derivation reproduces all eight, so Assumption 2 chose the pad rule plus an enumerated
two-line exception.

**Phase 0 overturned this.** See the re-validation below: the semicolon is the invariant, and two
derived rules reproduce the file 8/8 byte-exact with no exception list. The observation about the
source being inconsistent stands; the conclusion drawn from it did not.

### Re-validated after Phase 0 (2026-09-12)

The checklist above was re-run against the amended spec and still passes. Phase 0 changed three
things, and one of them is the reverse of the usual direction — research made the cycle *easier*
rather than harder:

- **Assumption 2 replaced, and the cycle's defining risk removed.** It said column alignment
  "cannot be derived by one rule", inherited from cycle 024. Re-measured: the invariant is the
  **semicolon**, which lands at column 50 on all eight lines. Two derived rules reproduce the file
  **8/8 byte-exact** with nothing stored in the model. Cycles 024 and 025 each tested one rule,
  scored 6/8, and stopped — and both wrote the pessimistic conclusion into a spec.
- **FR-014 strengthened** from "any deviation enumerated" to "reproduced byte-exactly, with the
  source inconsistency documented and pinned by a test". SC-001 can now demand a clean diff.
- **FR-017 resolved and FR-017a added.** The worktree is a **registered** git worktree, so
  `rm -rf` would leave a stale registration; and removing it alone fixes today's 623 lint errors
  while leaving the next agent worktree free to reintroduce them. Both the removal and a
  `/.claude` entry in `.yamllint` are now required.

### A note on how the inherited figure survived three cycles

The "12 + 7 lines" gap appeared in three commit messages, `AGENTS.md`, `.infrahub.yml` and two
specs before this cycle diffed the artifact and found three dropped comment blocks as well. The
same applies to the alignment pessimism, which was written twice without being re-tested.

The pattern is not "a claim was wrong" — it is **a claim was carried forward without being
re-derived**. Six earlier corrections in this sequence were each about measuring something new;
these two are about re-measuring something already believed. That is the harder failure to catch,
because nothing about it looks like an open question.

### Scope note on User Story 4

Repository hygiene is not an Infrahub artifact and would not normally appear in a spec. It is here
only because the request was to complete all remaining tasks, it is P4, and it cannot affect the
render. FR-018 deliberately stops short of deleting Infrahub branches whose purpose is unclear —
those get listed for the requester instead of removed on a guess.
