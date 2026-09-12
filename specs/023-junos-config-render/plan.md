# Implementation Plan: Junos Configuration for the Perimeter Firewall

**Branch**: `023-junos-config-render` | **Date**: 2026-09-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-junos-config-render/spec.md`

## Summary

One hybrid Python + Jinja2 transform, templates for the four in-scope Junos stanzas, one artifact
definition, one target group, and a golden-file test. 573 of the firewall's 677 configuration
lines, rendered from a model cycle 010 seeded and nothing has read since.

This is the fourth and last of the lab domains cycle 010 listed as hand-maintained. When it
lands, the original request — *"contain all of the information that is in the lab: the ISP, the
branches, and the firewall"* — is answered.

## Re-scope: the seed repair is inside this cycle

The plan below was written before implementation, and implementation stopped at T011 with a
blocking finding: **the seeded data does not transcribe the oracle** (research.md R9). Cycle 010
modelled the firewall's structure faithfully and seeded its values approximately, so no renderer
could reach SC-001.

On the requester's decision the seed repair is folded into this cycle rather than split out. That
makes this **two artifact types in one cycle** — Objects then Transform — where the extension's
routing normally takes one. The deviation is deliberate and recorded here rather than left
implicit.

It is defensible because the object work is transcription, not design: 33 corrections from a file
that already exists, no schema component, and verified by the same golden-file diff that verifies
the transform. Splitting it would give two cycles one oracle and one acceptance test between them.

**The correction inventory**, measured after fixing an extractor that had missed Junos' bracket
form and overstated the gap:

| Correction | Count |
| --- | --- |
| Rule `application` links | 14 (11 of them `any`) |
| Rule address-**group** references — 3 source, 3 destination | 6 |
| Interface descriptions | 6 |
| Interface MTUs (`1514` → `9192`) | 6 |
| New service object `any` | 1 |
| **Total** | **33** |

No schema change: `SecurityAddressGroup` is already a concrete kind of `SecurityGenericAddress`,
and `mtu`/`description` already exist on `SecurityFirewallInterface`.

**Phase 0 settled the riskiest question and overturned the spec's headline argument.**

The riskiest question was whether the model reproduces the eleven zone pairs and their evaluation
order, since Junos evaluates first-match and a wrong order loads cleanly while enforcing
something else. Queried from the live graph: eleven pairs for eleven, nineteen rules for
nineteen, order matching in every pair.

The overturned argument was the claim that the render would collapse six hand-written copies of
`deny-spoofed-infra` into one stored rule. It will not. The model holds six distinct objects
because `SecurityPolicyRule.source_zone` and `.destination_zone` are cardinality-one and
mandatory in an adopted marketplace schema this repository keeps byte-identical. The cycle is
still worth doing — 010's assumption 8 asked for a rendered artifact, not for deduplication — but
the argument is smaller than the spec first claimed, and [research.md](./research.md) R2 records
it in full.

Three further findings, each caught by checking rather than assuming:

- **`fw1` is a `SecurityFirewall`, not a `DcimDevice`.** It could have been a blocker; it is not,
  because the kind already inherits `CoreArtifactTarget` — which matters, since the adopted
  schema could not have been edited to add it.
- **`any` is in the model and must not be in the address book.** Junos treats it as a keyword.
  Rendering it produces one unexplained diff line.
- **The line accounting was wrong**: 573 in scope and 104 out, not the 580/97 first written, and
  the excluded `flow` block had been double-counted inside the in-scope `security` stanza.

## Technical Context

**Language/Version**: Python >=3.11,<3.14, plus Jinja2 templates.

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]` 1.22.0, Jinja2. No changes.

**Storage**: reads the Infrahub graph; writes one `text/plain` artifact.

**Testing**: `pytest`. `tests/unit/test_junos_config.py` renders from a captured fixture and
compares against the golden file, so the gate needs no server.

**Target Platform**: local Infrahub stack via Docker Compose.

**Project Type**: Infrahub repository — schemas, generators, transforms, checks, object data.

**Performance Goals**: N/A. One document, 573 lines.

**Constraints**: byte-for-byte parity with the in-scope stanzas; no credential in the artifact,
the model or the query; rule order preserved; balanced braces.

**Scale/Scope**: 33 object corrections, 1 query, 1 transform class, ~5 templates, 1 group entry,
1 artifact definition, 2 test modules.

**Dependencies**: none outstanding. Cycles 020–022 are merged and pushed; this cycle stands alone.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1. Result recorded below.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ No schema change and none needed — the kinds, attributes and relationships the seed repair uses all exist. `SecurityFirewall` already inherits `CoreArtifactTarget`. The adopted `security/security.yml` is not touched. |
| **II. Idempotent Operations** | ✅ **Now in scope for the object half.** `infrahubctl object load` upserts by HFID; SC-014 requires a second load to produce no error and no duplicate, verified by counting rather than by reading the log — the CLI prints "Created node" for an upsert. No generator, so `$infrahub-test-generator-idempotence` does not apply. |
| **III. Type Safety** | ✅ The transform wraps its result in the generated `JunosConfigQuery` model, as `transforms/frr_config.py` does. `*_query.py` is regenerated from the `.gql`, never hand-written. |
| **IV. Test-Required Quality** | ⚠️ Unit coverage is the primary gate, against 573 lines of third-party golden output. The integration suite is the same documented exception as cycles 020–022 — see below. |
| **V. Convention-Based Structure** | ✅ `transforms/junos_config.py` with `junos_config.gql` and `junos_config_query.py` beside it. Templates under `transforms/templates/junos/`, matching the `frr/` tree cycle 022 established. |

### Integration testing

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–022.
The constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative is in [quickstart.md](./quickstart.md): render on a live branch and diff
against the lab, verify the counts, verify brace balance, verify the group has one member, and
grep for credentials in both the artifact and the repository.

**No unjustified violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/023-junos-config-render/
├── plan.md              # This file
├── research.md          # Phase 0 — eight findings, one withdrawal
├── data-model.md        # Phase 1 — the render context, stanza by stanza
├── quickstart.md        # Phase 1 — eight validation steps
├── contracts/
│   └── transform-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code (repository root)

```text
transforms/
├── junos_config.gql             # NEW — the firewall, its zones, book, services and rules
├── junos_config_query.py        # NEW — generated, never hand-written
├── junos_config.py              # NEW — context assembly and zone-pair grouping
└── templates/junos/
    ├── junos.j2                 # NEW — the outer document and stanza order
    ├── interfaces.j2            # NEW
    ├── address-book.j2          # NEW
    ├── zones.j2                 # NEW
    └── policies.j2              # NEW

objects/
└── 00_groups.yml                # EDIT — the junos_firewalls group, one member

tests/unit/
├── test_junos_config.py         # NEW — golden-file parity
└── fixtures/junos/fw1.json      # NEW — captured graph response

.infrahub.yml                    # EDIT — query, transform, artifact definition
```

**Structure Decision**: one template per stanza, included from an outer `junos.j2`. The stanzas
are independent and one of them — policies — is two thirds of the output, so splitting keeps the
diff-driven iteration this cycle expects from happening in a single 400-line file.

## Implementation sequence

The seed first, because everything after it is only correct if the data is. Then the hardest
stanza gets the harness before it starts.

**Already done** (T001–T011, before the re-scope): the query with its concrete-kind fragments,
the generated types, and the captured fixture. All three are correct and reusable — they are what
revealed the gap.

1. **Repair `objects/32_nfd41_security.yml`** — the 33 corrections above, transcribed from the
   oracle. Add `any` as a service object first, since 11 rules reference it.
2. **A seed-parity test**, comparing every rule's addresses, groups and applications and every
   interface's description and MTU against the oracle, in both directions. This is US1's gate and
   it needs no renderer.
3. **Reload and re-capture the fixture**, so the transform is built against corrected data.
4. **`transforms/junos_config.py`** — the class, the `StrictUndefined` environment, the zone-pair
   grouping, and the `any` exclusion.
5. **`interfaces.j2` and `address-book.j2`** — the smallest stanzas, and the ones that establish
   the bracket-form helpers everything else reuses.
6. **The golden-file test**, comparing the stanzas rendered so far. This is the harness; it must
   exist before the policies stanza, which is where the iteration will happen.
7. **`zones.j2`.**
8. **`policies.j2`** — two thirds of the output, eleven pairs, nineteen rules, order-sensitive.
9. **`junos.j2`** — the outer document, stanza order, brace balance, trailing newline.
10. **Register the group, query, transform and artifact definition**; verify the names match
    programmatically, as cycle 022 did.
11. **Render live and diff**; then the credential grep, the counts and the brace check.
12. **`uv run invoke test` and `uv run invoke lint`.**
13. **The SC-010 arithmetic** — confirm the exclusions still total 104.

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| **The seed was not a transcription** — found at T011, after Phase 0 checked structure but not rule contents | **Realised.** This is why the cycle was re-scoped | The 33 corrections are enumerated and bounded; a seed-parity test gates them before any rendering |
| **No templates to port** — they are authored against the golden file with no prior art | **Certain**, and this remains the cycle's defining rendering risk | The diff harness goes in before the largest stanza. Expect iteration; the first failures will be Junos syntax rather than missing data |
| Phase 0 verified structure and identity but not field contents | **Realised** — the lesson for the next cycle | A research step that compares *values* both ways, not only counts and names |
| Bracket form wrong for single-member lists | High — four groups and many rules have one member | A shared helper, used by every list site, and a test over the rendered output |
| Polymorphic address/service fragments name a generic | Medium | Cycle 022's finding: the model falls back silently, so a field reads `None` rather than erroring. The contract names the three concrete kinds |
| `any` rendered into the address book | Medium | R8; one explicit exclusion and a test |
| Rule order wrong within a pair | Medium — invisible in review, changes behaviour | Sort by `index`; a test asserts order per pair against the golden file |
| A credential reaches the model or the artifact | Low, but the highest-severity | Nothing models it today. FR-015/FR-043/SC-005, a test, and a repository-wide grep in quickstart §4 |
| The artifact is mistaken for a complete `junos.conf` | Medium | SC-010 makes the 104 excluded lines an arithmetic criterion rather than a caveat |

## Complexity Tracking

No constitution violations require justification. This section is intentionally empty.
