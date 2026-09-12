# Transform Specification: Completing the Perimeter Firewall Artifact

**Feature Branch**: `026-complete-junos-artifact`
**Created**: 2026-09-12
**Status**: Draft
**Artifact types**: Schema → Objects → Transform, **folded into one cycle on the requester's
instruction** ("complete all remaining tasks"). The deviation is recorded here rather than left
implicit, as cycle 023 did.

## Summary

Close the perimeter firewall artifact. After this cycle the rendered configuration is
**byte-for-byte identical to `../lab/configs/fw/vsrx/junos.conf`** with two things removed: the
13-line `system` stanza, which holds credential hashes and is excluded permanently, and the
72-line file header, which is the lab's documentation *about* the file and is replaced by the
artifact's own provenance line.

Everything else — 592 of 677 lines — is rendered from the model.

## What is actually left, measured

The previous cycles' framing of "104 excluded lines" was accurate but coarse. Measured against
the live render:

| Category | Lines | Status |
| --- | --- | --- |
| Configuration lines in scope | 459 | **440 rendered, 19 missing, 0 invented** |
| — `routing-options` | 12 | missing; data seeded in cycle 025, needs only a template |
| — `security { flow { tcp-mss } }` | 7 | missing; nothing models the value |
| Comment blocks inside `security` | 13 blocks | **10 rendered, 3 absent** (~17 lines) |
| `system` stanza | 13 | excluded permanently — credential hashes |
| File header | 72 | the lab's documentation about the file, not device configuration |

**The render invents nothing**: zero configuration lines appear in the artifact that are not in
the device file. That was checked, not assumed.

The three absent comment blocks are:

| Lines | Subject |
| --- | --- |
| 6 | the TCP-MSS clamp arithmetic — belongs with the `flow` block |
| 4 | why the address book uses named objects rather than bare CIDRs |
| 9 | **why NAT is absent, and that its absence is load-bearing** |

The third is the one worth having. It documents a deliberate *absence* — that source-NAT here
would translate real pod addresses and quietly make every downstream ACL meaningless — and notes
that `make verify` checks no `nat` stanza has appeared. A renderer that drops it produces a
configuration that looks complete and has lost the reason it is safe.

## Transform Type

Hybrid Python + Jinja2, unchanged. `transforms/junos_config.py` gains context; the templates
gain one new stanza file and two comment blocks. No new transform, no new artifact definition.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The firewall's routes reach the device configuration (Priority: P1)

A network engineer changes a static route in Infrahub and the rendered configuration changes with
it, instead of the route living only in a file nobody regenerates.

**Why this priority**: it is the last piece of the chain cycles 023, 024 and 025 were built for.
Twelve lines, and the data is already in the graph.

**Independent Test**: render `fw1` and compare the `routing-options` stanza to the device file.

**Acceptance Scenarios**:

1. **Given** the eight routes seeded in cycle 025, **When** the artifact renders, **Then** the
   `routing-options { static { … } }` stanza appears and matches the device file byte for byte,
   including each route's `/* … */` comment.
2. **Given** the stanza, **When** its position is checked, **Then** it sits between `interfaces`
   and `security`, as in the device file.
3. **Given** a route removed from the model, **When** the artifact re-renders, **Then** that line
   disappears and the other seven are unchanged.

### User Story 2 - The TCP-MSS clamp is modelled, not lost (Priority: P2)

The one value that keeps large packets flowing across the firewall is held in the model and
rendered, rather than being a number only the device knows.

**Why this priority**: seven lines, but it needs a schema attribute and a seeded value, so it is
the only part of this cycle that touches three artifact types. It is also the value the
`interfaces` stanza's own comment already refers to — the render currently explains a clamp it
does not emit.

**Independent Test**: query `fw1` for the clamp value; render and compare the `flow` stanza.

**Acceptance Scenarios**:

1. **Given** the schema extension, **When** `fw1` is queried, **Then** it exposes a TCP-MSS value
   of 9138.
2. **Given** that value, **When** the artifact renders, **Then** `security { flow { tcp-mss {
   all-tcp { mss 9138; } } } }` appears as the first block inside `security`, matching the device
   file byte for byte.
3. **Given** a firewall with no clamp value set, **When** the artifact renders, **Then** no
   `flow` stanza is emitted — an absent clamp must not render as `mss 0` or an empty block.

### User Story 3 - The configuration keeps its explanations (Priority: P3)

Whoever reads the rendered configuration gets the reasoning the device file carries, including
the reasoning about what is deliberately *not* there.

**Why this priority**: no data and no schema — template text only. But the NAT block is the one
piece of this file that explains a safety property of the whole lab, and it is currently dropped.

**Independent Test**: the three comment blocks appear in the rendered artifact.

**Acceptance Scenarios**:

1. **Given** the render, **When** the `security` stanza is read, **Then** the TCP-MSS, named-object
   and NAT comment blocks all appear, each in the same position as in the device file.
2. **Given** the whole artifact, **When** it is compared to the device file with the header and
   `system` stanza removed, **Then** everything outside `policies` is identical, every zone pair
   is identical, and every line of content appears in both — see SC-001 for the one thing the
   model cannot reproduce.

### User Story 4 - The repository is left clean (Priority: P4)

Someone running the project's own lint and branch commands gets usable output.

**Why this priority**: it is housekeeping, it is not an Infrahub artifact, and it is included only
because the request was to complete all remaining tasks. It cannot break the render.

**Independent Test**: `invoke lint-yaml` passes; the Infrahub branch list holds only branches
someone is using.

**Acceptance Scenarios**:

1. **Given** the repository, **When** `uv run invoke lint-yaml` runs, **Then** it reports no
   errors. It currently reports 623, all from a 652 MB stray agent worktree at
   `.claude/worktrees/agent-a7e2fddc3b0b7c881/`.
2. **Given** the Infrahub instance, **When** its branches are listed, **Then** the merged
   per-cycle branches are gone. One of them, `023-junos-config-render`, currently errors on every
   repository sync because its schema predates cycle 023's attributes.

### Edge Cases

- **A firewall with no TCP-MSS value.** Must render no `flow` stanza rather than an empty one or
  a zero. US2 scenario 3.
- **A firewall with no static routes.** Must render no `routing-options` stanza. An empty
  `static { }` block is not what the device would hold.
- **Route ordering.** The device file lists the eight routes in neither prefix nor next-hop order;
  it groups them by destination. The order is presentational — unlike zone-pair policies, static
  routes are longest-prefix matched, not first-match — so a stable, reproducible order is
  required but it need not be the file's.
- **Column alignment.** The stanza is aligned by hand and **inconsistently**: two of the eight
  lines carry one fewer space before their comment. Reproducible without storing presentation —
  see Assumption 2.
- **The `system` stanza must stay absent**, and the model must still never hold a credential.
- **Deleting the stray worktree** must not remove anything tracked by git.

## Requirements *(mandatory)*

### Schema

- **FR-001**: A TCP-MSS value MUST be modelled on the firewall. It MUST go in
  `schemas/security_extensions.yml`, the local extension file that already holds `book_index` and
  `log_session_close`; `schemas/security/security.yml` is marketplace-adopted and MUST stay
  byte-identical.
- **FR-002**: The attribute MUST be optional, so a firewall without a clamp is valid and renders
  no `flow` stanza.

### Objects

- **FR-003**: `fw1` MUST carry the value `9138`, transcribed from the device file.
- **FR-004**: The value MUST be set in the existing `objects/32_nfd41_security.yml`, on the
  `SecurityFirewall` entry, rather than in a new file — it is an attribute of the firewall, not a
  new kind.

### GraphQL Query

- **FR-005**: `transforms/junos_config.gql` MUST fetch the firewall's static routes and its
  TCP-MSS value.
- **FR-006**: The query MUST NOT request anything from the `system` stanza's domain. The
  credential requirement from cycle 023 stands unchanged.
- **FR-007**: `transforms/junos_config_query.py` MUST be regenerated from the `.gql`, never
  hand-edited.

### Transform Logic

- **FR-008**: The transform MUST provide the routes in a deterministic order, and the same order
  on every render.
- **FR-009**: The transform MUST omit the `routing-options` stanza entirely when the firewall has
  no routes, and the `flow` stanza when it has no clamp value.
- **FR-010**: Route comments MUST come from the stored route description, not be reconstructed.

### Jinja2 Template

- **FR-011**: A new `routing-options.j2` MUST render the stanza, and `junos.j2` MUST place it
  between `interfaces` and `security`.
- **FR-012**: The `flow` block MUST render as the first block inside `security`, preceded by its
  comment.
- **FR-013**: The three absent comment blocks MUST be reproduced verbatim, in position.
- **FR-014**: The route lines MUST be reproduced byte-exactly by deriving both gaps from the
  data (research R1). The transform MUST NOT store rendered spacing, and MUST carry a comment
  saying that the second rule reproduces an inconsistency in the source rather than implementing
  an alignment policy. A test MUST pin both the six-line and the two-line case.

### Artifact & Registration

- **FR-015**: No new artifact definition, transform registration or target group. The existing
  `junos_config` definition already covers this.
- **FR-016**: The `.infrahub.yml` comment and `AGENTS.md` MUST be updated to state what is
  rendered and what remains excluded, with the new figures.

### Repository hygiene

- **FR-017**: The worktree MUST be removed with `git worktree remove` — it is a **registered**
  git worktree, not a stray directory, so deleting the folder alone would leave a stale
  registration (research R5). Its HEAD is already an ancestor of `main`, so nothing is lost.
- **FR-017a**: `/.claude` MUST be added to `.yamllint`'s ignore list. Removing the worktree fixes
  today's 623 errors; without this the next agent worktree reintroduces them, because the existing
  `/lab/avd/intended` ignore is anchored and does not cover a copy nested inside `.claude`.
- **FR-018**: Merged per-cycle Infrahub branches MUST be deleted. Branches whose purpose is
  unclear MUST be listed for the requester rather than deleted on a guess.

### Key Files

| File | Change |
| --- | --- |
| `schemas/security_extensions.yml` | EDIT — one optional Number attribute |
| `objects/32_nfd41_security.yml` | EDIT — one value on `fw1` |
| `transforms/junos_config.gql` | EDIT — routes and the clamp |
| `transforms/junos_config_query.py` | REGENERATE |
| `transforms/junos_config.py` | EDIT — route context, clamp passthrough |
| `transforms/templates/junos/routing-options.j2` | NEW |
| `transforms/templates/junos/junos.j2` | EDIT — stanza placement |
| `transforms/templates/junos/{zones,address-book}.j2` | EDIT — the two comment blocks |
| `tests/unit/test_junos_config.py` | EDIT — the new stanzas and the whole-file comparison |
| `tests/unit/fixtures/junos/fw1.json` | REGENERATE |
| `AGENTS.md`, `.infrahub.yml` | EDIT — the figures |

### Key Entities

- **`RoutingStaticRoute`** — eight objects on `fw1`, seeded in cycle 025. Read, not modified.
- **`SecurityFirewall`** — gains one optional attribute by local extension. The adopted schema is
  not touched.

## Success Criteria *(mandatory)*

- **SC-001**: *(Corrected during implementation — the original demanded a clean whole-file diff,
  which the model cannot deliver. See below.)* Against `../lab/configs/fw/vsrx/junos.conf` with
  the 72-line header and 13-line `system` stanza removed:
  - **everything outside the `policies` stanza is byte-for-byte identical** — interfaces,
    `routing-options`, the `flow` clamp, the address book, every comment block, and the zones;
  - **all eleven zone pairs are present and each is byte-for-byte identical**;
  - **every line of content appears in both**, in the same multiset.

  What is **not** reproducible is the **sequence** of the eleven zone-pair blocks, and the
  blank-line placement that follows from it. A zone pair is *derived* from each rule's source and
  destination zone, so there is no pair object to carry an order, and
  `SecurityPolicyRule.index` orders rules *within* a pair — it holds only 10, 20 and 30 across all
  nineteen rules. Junos matches a packet to its zone pair by zone, not by position, so the
  sequence is presentation; reproducing it would mean adding an attribute whose only purpose is to
  record it, which this cycle declined for the same reason it declined to store the route-line
  spacing. Cycle 023 found this and relaxed its own criterion accordingly; this spec asserted the
  stronger claim without re-checking that the finding still applied.
- **SC-002**: All 459 in-scope configuration lines are rendered — up from 440 — and the artifact
  still contains **zero** configuration lines absent from the device file.
- **SC-003**: The eight route lines match the device file exactly, comments and interior spacing
  included, or every deviation is enumerated and asserted by a test.
- **SC-004**: The `flow` stanza renders `mss 9138` and appears first inside `security`.
- **SC-005**: A firewall with no clamp renders no `flow` stanza; one with no routes renders no
  `routing-options` stanza.
- **SC-006**: All three previously absent comment blocks appear, in position.
- **SC-007**: No credential appears in the artifact, the model or the query — re-verified, not
  assumed from cycle 023.
- **SC-008**: Braces balance and the file ends with exactly one newline.
- **SC-009**: `schemas/security/security.yml` stays byte-identical to marketplace
  `infrahub/security` 1.0.2.
- **SC-010**: The exclusion accounting totals: 592 rendered + 13 `system` + 72 header = 677, and
  a test asserts the arithmetic rather than a comment claiming it.
- **SC-011**: `uv run invoke lint-yaml` reports zero errors, down from 623.
- **SC-012**: The full unit suite stays green, at or above its current 1021.

## Assumptions

1. **The route order is presentational and may be chosen.** Static routes are longest-prefix
   matched, so unlike the zone-pair policies of cycle 023 — where first-match ordering is
   semantic — no behaviour depends on the sequence. A deterministic order is required; matching
   the file's grouping is preferred but not a correctness condition.
2. **Column alignment IS reproducible, by two derived rules.** *(Replaces the assumption written
   before Phase 0, which inherited cycle 024's conclusion that no single derivation existed.)* The
   invariant is the **semicolon, not the comment**: it lands at column 50 on all eight lines. Pad
   the prefix field by `max(1, 14 - len(prefix))` and that falls out; the comment then follows
   after 3 spaces when the next hop is 12 characters and 2 when it is 11. Tested against the file:
   **8/8 byte-exact**, with nothing stored in the model and no exception list. The second rule is a
   correlation rather than a cause — two lines were simply typed one space short — so it must be
   commented as reproducing a source inconsistency, and pinned by a test so a later "tidy-up"
   fails. See [research.md](./research.md) R1.
3. **The 72-line header is not rendered, and that is correct.** It is the lab's documentation
   about the file, including how vrnetlab appends it to `init.conf`. Reproducing it would put a
   false provenance claim in the artifact, which is the same decision cycle 022 made for the FRR
   configurations.
4. **The three comment blocks are reproduced verbatim**, as cycles 022 and 023 did for every other
   comment in this file. They are most of its teaching value.

## Scope

**In scope**: 19 configuration lines, three comment blocks, one schema attribute, one object
value, and the repository hygiene the request named.

**Out of scope**, permanently or by decision:

- **The `system` stanza.** Two `encrypted-password` hashes. They must never enter the model and
  the query must never ask.
- **The file header.** Assumption 3.
- **A check enforcing that the six `deny-spoofed-infra` rules stay identical.** Named as a
  follow-up since cycle 023; it is a check cycle, and this one is already three artifact types.

## Deviation from one-artifact-per-cycle

The extension's routing takes one artifact type per cycle. This cycle covers **Schema, Objects
and Transform**, on the explicit instruction to complete all remaining tasks.

It is defensible: the schema part is one optional attribute, the object part is one value, and
both exist solely so the seven-line `flow` stanza can render. Splitting them would give three
cycles one success criterion between them. The precedent is cycle 023, which folded its object
repair in on the same kind of instruction and recorded the deviation rather than hiding it.

## Dependencies

Cycles 023, 024 and 025 are merged and pushed. The eight static routes are live on Infrahub
`main` — verified after cycle 025's merge: 19 `RoutingStaticRoute` objects,
`{DcimDevice: 11, SecurityFirewall: 8}`, all eight at `vrf=default`.
