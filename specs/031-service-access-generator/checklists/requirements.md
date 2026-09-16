# Specification Quality Checklist: Application Access Grant Generator

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

### Scope corrections made during validation

The first draft of this spec was a *schema* cycle proposing a generic
realization-and-ownership model. Two findings retired it before it reached the
checklist, and both are recorded in the spec so the next reader does not
re-derive them:

- **The SDK already owns realization and withdrawal.** `InfrahubGenerator.run()`
  wraps `generate()` in `start_tracking(..., delete_unused_nodes=True)`. A
  schema model for "what did this service build" would have duplicated the
  tracking group. `generate_fabric_peering.py` already relies on this.
- **Four of the five generator-less service kinds are not inert.** The three WAN
  kinds are read by `frr_config`; `ServiceFabricApp` is rendered by
  `crossplane_fabric_app`. Only `ServiceAppAccess` produces nothing, which is
  what makes it the cycle rather than all five.

The user's steer — "the service catalog can come later, but we just need the
services to work in Infrahub" — set the boundary. The catalogue and request
provenance are both listed under Out of Scope with the reason.

### Judgement calls recorded rather than raised as markers

- *Firewall rules only, not Kubernetes NetworkPolicy.* `policy_allow_ports` is
  declared intent on the application, not per-grant; two writers on one
  attribute is worse than a smaller cycle. In Assumptions and Out of Scope.
- *The destination VIP stays hand-modelled.* Allocating it from `vip_block`
  risks disagreeing with MetalLB's own allocator. In Assumptions.
- *Rule index allocation and destination-zone derivation* are stated as
  requirements (FR-027, FR-028) without prescribing the mechanism; the algorithm
  is a `/speckit-plan` decision.

### Content-quality note

The spec names existing repository artifacts — `SecurityPolicyRule`,
`managed_by_service`, `junos_config`, `objects/00_groups.yml`. For a generator
spec these are the subject matter, not implementation leakage: a spec for a
generator that would not name what it generates could not be reviewed. The
FR-001 to FR-003 SDK requirements come from the extension's own generator
template.

### Risks carried into planning

- **FR-062 / SC-005.** The seeded grant changes the rendered Junos artifact, and
  `tests/unit/test_junos_config.py` holds it byte-for-byte with a line-count
  assertion in `test_the_exclusions_add_up`. Planning must decide whether the
  seeded grant belongs in the default seed data at all, or only in a test
  fixture.
- **First-match ordering.** Junos evaluates first-match within a zone pair, so
  where a generated rule sits relative to the hand-written baseline is
  behaviour, not presentation. FR-027 requires determinism; it does not yet say
  where in the order the rule belongs.

No items require spec updates. Ready for `/speckit-clarify` or `/speckit-plan`.
