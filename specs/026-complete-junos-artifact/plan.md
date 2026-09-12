# Implementation Plan: Completing the Perimeter Firewall Artifact

**Branch**: `026-complete-junos-artifact` | **Date**: 2026-09-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-complete-junos-artifact/spec.md`

## Summary

Close the firewall artifact. Two stanzas, three comment blocks, one optional schema attribute and
one seeded value, after which the rendered configuration is **byte-for-byte identical to
`../lab/configs/fw/vsrx/junos.conf`** minus the 13-line `system` stanza and the 72-line header.

Plus the repository hygiene the request named: a registered git worktree removed and a lint
ignore added, taking `invoke lint-yaml` from 623 errors to none.

## Phase 0 in one paragraph

Two findings changed the plan and one changed the cycle's difficulty. The alignment problem that
cycles 024 and 025 both recorded as unsolvable **is solved** — the invariant is the semicolon, not
the comment, and two derived rules reproduce all eight route lines byte-exactly with nothing
stored in the model (R1). The gap this cycle is closing is **larger than the figure every cycle
since 023 has repeated**: three comment blocks are dropped as well as the 19 configuration lines,
and one of them is why the configuration is safe (R2). And the "stray directory" in
`.claude/worktrees/` is a **registered git worktree**, so `rm -rf` would have left a stale
registration (R5).

### The alignment problem was not what it looked like

Cycles 024 and 025 both wrote that "no single derivation reproduces all eight lines", and offered
a choice between storing spacing in the model and relaxing the success criterion. Both tested a
rule, found it scored 6/8, and stopped.

Measured again, the `;` lands at **column 50 on all eight lines**. Padding the prefix field by
`max(1, 14 - len(prefix))` produces that; the comment gap is then 3 or 2 depending on the next-hop
length. 8/8, byte-exact, nothing stored.

The second rule is a **correlation, not a cause** — two lines were typed one space short — and the
plan requires it to be commented as such and pinned by a test. That is the difference between
reproducing an inconsistency deliberately and encoding a rule that does not exist.

### The inherited figure

"12 lines of `routing-options` and 7 of `flow`" has appeared in three commit messages,
`AGENTS.md`, `.infrahub.yml` and two specs. It is correct about configuration — measured: 459
in-scope lines, 440 rendered, 19 missing, **0 invented** — and silent about three comment blocks
inside `security` that the render drops.

The nine-line NAT block is the one worth having: it records that a source-NAT rule here would
translate real pod addresses and silently make every downstream ACL meaningless, and that
`make verify` checks no `nat` stanza has appeared. It documents an **absence**, which nothing in
the model can imply. If the renderer does not carry it, it is gone.

Every cycle since 023 re-read the previous cycle's spec instead of diffing the artifact.

## Technical Context

**Language/Version**: Python >=3.11,<3.14, Jinja2 templates, YAML schema and object data.

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]` 1.22.0. No changes.

**Storage**: reads the graph; writes one `text/plain` artifact. One new attribute value.

**Testing**: `pytest`. `tests/unit/test_junos_config.py` and `test_junos_seed_data.py` extended;
both render from a captured fixture and need no server.

**Target Platform**: local Infrahub stack via Docker Compose.

**Project Type**: Infrahub repository — schemas, generators, transforms, checks, object data.

**Performance Goals**: N/A. One document, 592 lines.

**Constraints**: byte-for-byte with the device file minus two regions; no credential in the
artifact, the model or the query; the adopted security schema untouched; braces balanced.

**Scale/Scope**: 1 schema attribute, 1 object value, 1 query change, 1 transform change, 1 new
template + 3 edited, 2 test modules extended, 1 worktree removed, 1 lint ignore.

**Dependencies**: cycles 023–025 merged and pushed; the eight routes live on Infrahub `main`.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1. Result recorded below.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ The one attribute lands before the object value that needs it and the template that reads it. It goes in `schemas/security_extensions.yml`, the local file; the adopted `security/security.yml` stays byte-identical. |
| **II. Idempotent Operations** | ✅ No generator. `infrahubctl object load` upserts on HFID; the `tcp_mss` value is an attribute on an existing object, so a second load changes nothing. Verified by counting, not by reading the log. |
| **III. Type Safety** | ✅ `junos_config_query.py` is regenerated from the `.gql`, never hand-written, and the transform wraps its result in the generated model as it already does. |
| **IV. Test-Required Quality** | ✅ **Strengthened.** C1 replaces a set of stanza-level checks with a whole-file diff, and C2 turns the exclusion accounting from a prose claim into an assertion. The integration suite is the same documented exception as cycles 020–025. |
| **V. Convention-Based Structure** | ✅ `routing-options.j2` joins the existing `templates/junos/` tree. The schema extension matches the shape of cycle 023's two additions. |

### Three artifact types in one cycle

The extension's routing takes one artifact type per cycle. This cycle covers **Schema, Objects and
Transform**, on the explicit instruction to complete all remaining tasks.

Defensible because the schema part is one optional attribute and the object part is one value,
both existing solely so a seven-line stanza can render. Splitting them would give three cycles one
success criterion between them. The precedent is cycle 023, which folded its object repair in on
the same kind of instruction and recorded the deviation rather than hiding it.

### Integration testing

`$infrahub-run-integration-tests` is not installed, as in cycles 020–025. The escape clause
applies and **the pull request must say so explicitly**. [quickstart.md](./quickstart.md) steps
1–11 are the non-live alternative.

**No unjustified violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/026-complete-junos-artifact/
├── plan.md              # This file
├── spec.md              # Amended after Phase 0 — Assumption 2 replaced, FR-014/017 strengthened
├── research.md          # Phase 0 — eight findings, one problem solved, one figure corrected
├── data-model.md        # Phase 1 — the attribute, the value, the render context, the two derived gaps
├── quickstart.md        # Phase 1 — twelve validation steps
├── contracts/
│   └── transform-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code (repository root)

```text
schemas/security_extensions.yml               # EDIT — one optional Number attribute
objects/32_nfd41_security.yml                 # EDIT — tcp_mss: 9138 on fw1
transforms/junos_config.gql                   # EDIT — static_routes and tcp_mss
transforms/junos_config_query.py              # REGENERATE
transforms/junos_config.py                    # EDIT — route context and the two derived gaps
transforms/templates/junos/routing-options.j2 # NEW
transforms/templates/junos/junos.j2           # EDIT — stanza placement, the flow block
transforms/templates/junos/address-book.j2    # EDIT — two comment blocks
tests/unit/test_junos_config.py               # EDIT — C1 to C7, C10, C12
tests/unit/test_junos_seed_data.py            # EDIT — C9
tests/unit/test_security_schema_contract.py   # EDIT — three kinds becomes four
tests/unit/fixtures/junos/fw1.json            # REGENERATE
.yamllint                                     # EDIT — ignore /.claude
AGENTS.md, .infrahub.yml                      # EDIT — the figures
```

**Structure Decision**: one new template for `routing-options`, matching the one-file-per-stanza
choice cycle 023 made. The `flow` block goes inline in `junos.j2` rather than getting its own
file — it is seven lines and one value, and a separate file would be more ceremony than content.

## Implementation sequence

The whole-file comparison goes in early, because it is what makes every later step verifiable in
one number.

1. **Extend `tests/unit/test_junos_config.py` with C1 and C2** — the whole-file diff and the
   accounting assertion. Both fail: the two stanzas and three comment blocks are missing.
2. **The schema attribute**, then check and load on `fw-complete`. The diff must name
   `SecurityFirewall` and nothing else.
3. **The object value**, then read it back.
4. **The query and the regenerated types**; re-capture the fixture.
5. **`routing-options.j2` and the two derived gaps** in the transform. Comment the `gap` rule as
   reproducing a source inconsistency.
6. **C3 and C4** — the three spacing cases and the column-50 invariant. Then break one gap by hand
   and confirm the named case fails, not only the aggregate diff.
7. **The `flow` block**, and C6's emptiness cases from modified fixtures.
8. **The three comment blocks**, and C7.
9. **C1 now passes** — the diff is empty. This is SC-001.
10. **The hygiene**: ancestor check, `git worktree remove`, `.yamllint` ignore, branch cleanup.
11. **Update the record** — `AGENTS.md` and `.infrahub.yml`, with the figures and with the two
    exclusions described as the different things they are.
12. **`uv run invoke test` and `uv run invoke lint`.**

### The merge trap, which applies again

Cycle 024 avoided it and cycle 023 did not. `infrahubctl graphql export-schema` has **no
`--branch` flag**; it exports Infrahub `main`. Loading this cycle's schema into `main` to
regenerate `schema.graphql` is exactly what made 023's Infrahub merge fail on a `SchemaAttribute`
uniqueness violation.

**This cycle changes schema, so the trap is live.** Merge first, regenerate `schema.graphql`
after — as cycle 024 did, successfully.

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| A "tidy-up" of the two short-gap lines | **Medium, and invisible in review** | C3 names the 11-character case; step 6 proves it fails independently of the aggregate diff |
| `gap` read as an alignment policy rather than a reproduced inconsistency | Medium | The transform must carry a comment saying which it is. Both misreadings break SC-001 |
| The whole-file diff is too blunt to debug | Medium | The existing stanza-level assertions stay. C1 says *whether*; they say *where* |
| `tcp_mss` given a default | Low, but it silently breaks future firewalls | C8 pins `optional: true` with no default; C6 pins that an unset value renders no stanza |
| `rm -rf` on the worktree | **Averted in Phase 0** | R5: it is registered. `git worktree remove`, after the ancestor check |
| The lint fix treated as a one-off cleanup | Medium | R6: the next agent worktree reintroduces all 623 errors. `/.claude` goes in `.yamllint` |
| Deleting an Infrahub branch someone wanted | Low, irreversible | H5: merged per-cycle branches only; anything unclear is listed for the requester |
| `schema.graphql` regenerated from the wrong branch | **Medium — it bit cycle 023** | Named above; step 12 defers it past the merge |

## Complexity Tracking

No constitution violations require justification. This section is intentionally empty.
