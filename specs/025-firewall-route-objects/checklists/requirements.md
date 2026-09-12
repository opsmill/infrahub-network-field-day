# Specification Quality Checklist: The Perimeter Firewall's Static Routes

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

The same scoping caveat as cycles 020 to 024: the extension's objects spec template mandates
naming the node kind, its attributes and the file's load order, so those are the subject matter of
an objects spec rather than implementation leaking into it.

### Two cross-checks found while writing the spec, both promoted to requirements

Neither was in the original framing of "transcribe eight routes". Both came from reading the
device file's own interface table and the existing security seed rather than only the
`routing-options` stanza:

- **Every next hop is the far end of a /30 `fw1` is numbered on.** `10.250.110.1` sits opposite
  `10.250.110.2/30` on ge-0/0/0, and so on for all six, every one terminating on `border-leaf1`.
  A route whose next hop is not on a connected subnet would be accepted by the device and never
  install — a transcription error that a character-for-character comparison against the same
  stanza could not catch, because the stanza is where the typo would be.
- **Every destination is already in the address book**, one for one: `k8s-nodes`, `k8s-pods`,
  `k8s-services`, `app-hosts`, `wan-customers`, `branch-users`, `acme-cloud`, `globex-cloud`.
  The firewall routes to precisely the prefixes it filters. Verified against
  `objects/32_nfd41_security.yml`, not assumed from the names.

These are SC-004 and SC-005. They are the reason to hold this data in a model rather than a file:
a text file cannot check itself against the interfaces or the policy.

### The generic-peer trap was checked, not assumed

The Infrahub objects guidance marks generic relationship references as a CRITICAL failure case —
a scalar HFID reference to a generic peer fails when the generic has no `human_friendly_id`, and
the fix is an inline block naming the concrete kind. `RoutingStaticRoute.device` now peers
`DcimGenericDevice`, so the rule appeared to apply.

It does not. `DcimGenericDevice` defines `human_friendly_id: [name__value]`, and cycle 024
verified an object load with `device: "fw1"` succeeding against the live instance. So the plan
should use the plain scalar form and **not** reach for the inline concrete-kind blocks cycle 023
needed for the polymorphic address book.

Worth recording because the wrong reading would have added eight unnecessary inline blocks and a
false precedent.

### Requirements that exist because of earlier cycles' mistakes

- **FR-012 and SC-002 require the comparison to run both ways.** Cycle 023 lost fourteen lines of
  correct data to a one-way read that concluded something was absent when the search was at
  fault. A one-way check here would pass with a route missing.
- **SC-006 requires counting, not reading the log.** `infrahubctl` prints "Created node" for an
  upsert; cycle 023 recorded that, and cycle 024 relied on counting for the same reason.

### Deliberately not raised as clarifications

Zero [NEEDS CLARIFICATION] markers. Three candidates had defensible defaults recorded instead:

- **Where should the file sit in load order?** `32b_nfd41_fw_static_routes.yml`. The routes need
  only `fw1`, defined in `31_…`, so anything after 31 resolves; `32b` keeps the firewall's data
  together.
- **Should the route prefixes reference the address-book objects rather than repeating the
  text?** They cannot — `prefix` is a `Text` attribute, not a relationship, and changing that is a
  schema cycle nobody has asked for. The agreement is asserted as SC-005 instead.
- **Should a check enforce that agreement permanently?** Not here. SC-005 covers this cycle's
  gate; a standing rule over the whole graph is a check cycle, and it is named in Out of Scope
  rather than smuggled in.

### Carried forward for cycle 026

The `routing-options` stanza is column-aligned by hand and **inconsistently** — two of its eight
route lines are misaligned by one column, so no single derivation reproduces all eight. Measured
during cycle 024 and restated in this spec's Next cycle section so it is not rediscovered a third
time. It affects nothing here: this cycle stores no presentation.
