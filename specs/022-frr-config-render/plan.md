# Implementation Plan: FRR Configuration for the WAN

**Branch**: `022-frr-config-render` | **Date**: 2026-09-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-frr-config-render/spec.md`

## Summary

One hybrid Python + Jinja2 transform, five ported templates, one artifact definition, one target
group, and a golden-file test suite. Six devices, 448 lines of oracle. This is the cycle the last
three existed to enable, and after it the WAN renders from Infrahub.

**Phase 0 did not research this cycle — it rendered it.** The lab's templates were driven from
the live graph and diffed against the golden files: `cust-acme-ce`, `cust-globex-ce` and
`isp-pe1` all came out **zero diff**. `isp-pe1` is the largest config, the only one where the
service layer materialises, and the one carrying all the risk; it is byte-identical before
implementation starts. What remains is Infrahub plumbing, not rendering.

Four things the probe found that reading would not have:

- `StrictUndefined` caught two real context gaps at named template lines — the iBGP session
  toward the core, which hangs off the device rather than any site, and a static site's CE,
  which has to be resolved through the static route's next hop.
- Querying *from* an address needs an inline fragment just as querying *to* one does, in the
  opposite direction. Both are mandatory and both fail bluntly.
- Site ordering has to be a stated rule, because the lab's order is authoring order and Infrahub
  stores none. BGP attachments before static, each by name, reproduces it.
- SC-003's line count was wrong twice — written as three, corrected to four by reading the
  template, and finally six by rendering it both ways.

## Technical Context

**Language/Version**: Python >=3.11,<3.14, plus Jinja2 templates.

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]` 1.22.0, Jinja2 (already present).
No dependency changes.

**Storage**: reads the Infrahub graph; writes six `text/plain` artifacts.

**Testing**: `pytest`. `tests/unit/test_frr_config.py` renders from captured fixtures and
compares against `../lab/wan/rendered/*/frr.conf`, so the gate needs no server.

**Target Platform**: local Infrahub stack via Docker Compose.

**Project Type**: Infrahub repository — schemas, generators, transforms, checks, object data.

**Performance Goals**: N/A. Six documents, largest 159 lines.

**Constraints**: byte-for-byte parity with the oracle excluding one provenance line; every
comment preserved; `StrictUndefined`; exactly six artifacts.

**Scale/Scope**: 1 query, 1 transform class, 5 templates, 1 group entry, 1 artifact definition,
1 test module. Roughly 409 lines of ported template and a few hundred of Python.

**Dependency**: **cycle 021's object data, currently uncommitted.** See Risks.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1. Result recorded below.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ No schema change, and none needed — cycles 020 and 021 supplied the model and the data, proved by Phase 0 rendering three devices from it. `DcimDevice` already inherits `CoreArtifactTarget`. |
| **II. Idempotent Operations** | ✅ No generator, so `$infrahub-test-generator-idempotence` does not apply. A transform is a pure function of its query result: rendering twice yields identical text, which the golden-file tests assert by construction. The one new object is a group entry, loaded by upsert. |
| **III. Type Safety** | ✅ **Directly in scope.** The transform wraps its query result in the generated `FrrConfigQuery` Pydantic model, following `transforms/avd_eos_config.py`. `*_query.py` is regenerated from the `.gql`, never hand-written. This is how the principle is met despite `protocols.py` reflecting no extension relationship (R8) — the GraphQL return types are complete. |
| **IV. Test-Required Quality** | ⚠️ Unit coverage is the primary gate and is unusually strong here: 448 lines of third-party golden output. The integration suite is the same documented exception as cycles 020 and 021 — see below. |
| **V. Convention-Based Structure** | ✅ `transforms/frr_config.py` with `frr_config.gql` and `frr_config_query.py` beside it, matching the rule that a transform is named `<transform>.py` with matching query files. Templates under `transforms/templates/frr/`, following the existing `transforms/templates/` tree. |

### Integration testing

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020 and
021. The constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative is stronger here than in either previous cycle, because the output is
comparable against something this repository did not write: render all six devices on a live
branch and diff against the lab's files (quickstart §3), confirm the artifact definition
generates six and not seven (§4), and confirm the service-layer sensitivity (§5).

**No unjustified violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/022-frr-config-render/
├── plan.md              # This file
├── research.md          # Phase 0 — nine findings, three devices rendered zero-diff
├── data-model.md        # Phase 1 — the render context, field by field
├── quickstart.md        # Phase 1 — how to prove it, including the SC-003 demonstration
├── contracts/
│   └── transform-contract.md   # Phase 1 — registration, query, transform, output, tests
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code (repository root)

```text
transforms/
├── frr_config.gql              # NEW — one device plus the WAN context
├── frr_config_query.py         # NEW — generated, never hand-written
├── frr_config.py               # NEW — context assembly and template selection
└── templates/frr/
    ├── isp-edge.j2             # NEW — ported, 144 lines
    ├── isp-core.j2             # NEW — ported, 127 lines
    ├── internet-rtr.j2         # NEW — ported, 61 lines
    ├── customer-ce.j2          # NEW — ported, 43 lines
    └── branch-router.j2        # NEW — ported, 34 lines

objects/
└── 00_groups.yml               # EDIT — the frr_routers group, six members

tests/unit/
├── test_frr_config.py          # NEW — golden-file parity
└── fixtures/frr/               # NEW — captured graph responses, one per device

.infrahub.yml                   # EDIT — query, transform, artifact definition
```

**Structure Decision**: templates get their own `frr/` subdirectory because there are five of
them and they are selected by role at runtime; the transform loads the directory once with a
`FileSystemLoader` and picks by name, which is the skill's documented hybrid pattern. Fixtures
get a subdirectory for the same reason.

## Implementation sequence

Ordered so the riskiest verification happens as early as the dependencies allow.

1. **`transforms/frr_config.gql`** — the query, including both inline fragments. Regenerate
   `frr_config_query.py` from it immediately; never hand-write it.
2. **Port `customer-ce.j2`**, change only the provenance line.
3. **`transforms/frr_config.py`** — context assembly for a customer edge, template selection by
   role, `StrictUndefined` environment.
4. **Capture fixtures and write the golden-file test** for `cust-acme-ce` and `cust-globex-ce`.
   This establishes the harness the remaining four devices reuse, and it is why US1 is P1.
5. **Register the group, the query, the transform and the artifact definition**, then render the
   two CEs live and diff. Everything after this reuses a proven pipeline.
6. **Port `isp-edge.j2` and extend the context** — the tenant loop, the service-derived import
   policy, the device-scoped iBGP session, the static site's CE resolution, the R6 ordering rule.
   Phase 0 proved this context works; this step is transcribing it into the transform.
7. **`isp-core.j2`, `internet-rtr.j2`, `branch-router.j2`** — the three devices Phase 0 did not
   probe.
8. **All six live, diffed.** Then the SC-003 demonstration.
9. **`uv run invoke test` and `uv run invoke lint`.**
10. **The SC-009 walk** — what does `tenants.yml` still hold that the graph does not?

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| **Cycle 021 is uncommitted** — this cycle cannot render without its data | Certain, today | Commit 021 before starting. Not a tidy-up: the transform reads its interfaces, addresses, sessions and router IDs |
| Three devices were never probed — `isp-pe2`, `internet-rtr`, `branch-rtr` | Medium | Their templates are simpler than `isp-pe1`'s and their context is a subset plus the DC handoff, but "simpler" is not "verified". Step 7 is where surprises land |
| The probe's context was hand-assembled, so the transform's own assembly is unproven | Medium | This is what the golden-file tests are for. FR-041 requires fixtures captured from the live graph so model drift cannot mask a rendering bug |
| Whitespace drift breaks parity invisibly | Medium | All four Jinja2 environment settings are in the contract. A "semantically equal" diff is a failed diff |
| Site ordering breaks a comment while leaving config correct | Low | R6's rule is asserted only by the golden diff. A new site could reorder the inventory comment |
| `protocols.py` cannot type these relationships | Certain | Use the generated query model, as `avd_eos_config.py` does (R8). The protocols gap remains a separate backlog item |

## Complexity Tracking

No constitution violations require justification. This section is intentionally empty.
