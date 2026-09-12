# Acceptance Evidence: Completing the Perimeter Firewall Artifact

**Cycle**: 026 | **Date**: 2026-09-12 | **Infrahub branch**: `fw-complete`

## SC-001 — what the artifact now matches, and the one thing it cannot

**Corrected during implementation.** The spec demanded a clean whole-file diff. The model cannot
deliver that, and the reason was already on record: cycle 023 found it and relaxed its own
criterion, and this spec asserted the stronger claim without re-checking that the finding still
applied. That is the same failure this cycle was correcting in others.

What holds, asserted by three separate tests:

| Clause | Result |
| --- | --- |
| Everything **outside** the `policies` stanza | **byte-for-byte identical** — 230 lines, empty diff |
| All eleven zone pairs | **present, and each byte-for-byte identical** |
| Every line of content | **the same multiset** in both |

What does not: the **sequence** of the eleven zone-pair blocks, and the blank-line placement that
follows it. Measured rather than assumed — `SecurityPolicyRule.index` holds only **10, 20 and 30
across all nineteen rules**, so it orders rules *within* a pair and carries nothing about pairs.
No other attribute does either. A zone pair is derived from each rule's two zones, so there is no
pair object to order.

Junos matches a packet to its pair by zone, not by position, so the sequence is presentation.
Recording it would mean adding an attribute whose only purpose is to record it — which this cycle
declined for the same reason it declined to store the route-line spacing.

## SC-002 — the configuration, both directions

```text
config lines: device 459 | artifact 459
invented (artifact not device): 0
missing  (device not artifact): 0
```

440 before this cycle, 459 after. The 19 added are the 12 `routing-options` lines and the 7 of
`flow`. Nothing invented, then or now.

## SC-003 — the route lines, and the alignment that two cycles called impossible

Cycles 024 and 025 both recorded that no derivation reproduced all eight lines, and offered a
choice between storing spacing in the model and relaxing the criterion. Both had tested one rule,
scored 6/8, and stopped.

The invariant is the **semicolon**, at column 50 on all eight lines. Two rules, nothing stored:

| Value | Rule | Nature |
| --- | --- | --- |
| `pad` | `max(1, 14 - len(prefix))` | a real alignment rule — it produces the column-50 invariant |
| `gap` | `3 if len(next_hop) == 12 else 2` | reproduces an inconsistency: two lines were typed one space short |

**8/8 byte-exact.** Both are commented in the transform as which they are, because both
misreadings break the comparison — treating `gap` as policy invites a tidy-up, treating it as
arbitrary invites storing spacing in the data.

### The order turned out to be derivable too

The device file groups the routes by the port they leave through — ge-0/0/0 first with its three
k8s ranges, then one per remaining interface. Sorting by `(exit interface, prefix)` reproduces the
file exactly. The spec had assumed the order would simply be *chosen*; deriving it is better, and
the transform raises rather than guesses if a next hop is on no connected subnet.

## SC-004, SC-005 — the clamp, and emptiness

`fw1.tcp_mss = 9138`, rendered as the first block inside `security`.

The attribute is `optional: true` with **no default**, and that pair is asserted by its own test.
A default would give every firewall a value and render `mss 0` or an empty block on one that needs
no clamp. Verified from modified fixtures: no routes renders no `routing-options` stanza, no clamp
renders no `flow` stanza.

## SC-006 — the three recovered comment blocks

| Lines | Subject |
| --- | --- |
| 6 | the TCP-MSS clamp arithmetic |
| 4 | why the address book uses named objects rather than bare CIDRs |
| 9 | **why NAT is absent, and that its absence is load-bearing** |

The NAT block has its own assertion as well as the whole-file comparison, because it documents an
*absence*: nothing in the model implies "there is no NAT here", so nothing but the template can
carry it and nothing but a test can notice it going. Which is exactly what happened for three
cycles.

## SC-007 — no credential, re-verified rather than inherited

The firewall's hash (`$6$nfd41lab$X.Ccvvju…`) appears **nowhere in the repository** and nowhere in
the artifact; the rendered file contains no `system` stanza.

A repository-wide grep does hit `objects/22_nfd41_management.yml`, and it was checked rather than
waved away: that is a **different hash** (`$6$Nfd41Lab$EhS4…`), the EOS fabric's `NetworkLocalUser`
for AVD, present since the original modelling commit and unrelated to the firewall.

## SC-008 — braces and the newline

Braces balance across the artifact; it ends with exactly one newline.

## SC-010 — the accounting, computed rather than claimed

```text
677 = 72 header + 13 system + 592 rendered
```

All four numbers are derived from the device file at test time. Three literals would drift from
the file the way cycle 023's prose total did.

**The two exclusions are different in kind**, and the record now says so: `system` is
configuration deliberately never modelled; the 72-line header is 68 comments and 4 blanks of lab
documentation *about* the file, replaced by the artifact's own provenance line.

## SC-011 — the repository

```text
git merge-base --is-ancestor 213e83e main   -> succeeded, before anything was removed
git worktree remove .claude/worktrees/agent-a7e2fddc3b0b7c881
git worktree list                           -> only the main worktree
uv run invoke lint-yaml                     -> 0 errors, down from 623
```

The safety check ran **first**. It was a registered git worktree, not a stray directory, so
`rm -rf` would have left a stale registration that `git worktree list` keeps reporting.

`/.claude` was added to `.yamllint.yml` as well. Removing the worktree fixes today's errors; the
existing `/lab/avd/intended` ignore is anchored and does not cover a nested copy, so without this
the next agent worktree reintroduces all 623. yamllint does not read `.gitignore`, so being
git-excluded was never enough.

Fourteen merged per-cycle Infrahub branches were deleted, plus `worktree-agent-a7e2fddc3b0b7c881`
— including `023-junos-config-render`, which errored on every repository sync because its schema
predated cycle 023's attributes.

**Fifteen older branches were left alone and are listed for the requester** rather than deleted on
a guess: `app-files`, `app-render`, `avd-fabric-run`, `cx-peering`, `menu-check`,
`nfd41-fabric-model`, `no-internet`, `peer-addr`, `peer-check`, `svc-gen`, `svi-model`,
`wan-addr`, `wan-obj`, `wan-render`, `wan-svc`.

## SC-012 — gates

| Gate | Result |
| --- | --- |
| `uv run pytest tests/unit` | **1032 passed** (1021 before, plus 11) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 109 files formatted |
| `uv run yamllint .` | **0 errors**, from 623 |
| `uv run mypy src/solution_arista_avd` | no issues in 8 source files |
| `uv run rumdl check …` | no issues in 35 files |
| marketplace diff | `security/security.yml` byte-identical to `infrahub/security` 1.0.2 |

## The deliberate breaks

| Break | Fails |
| --- | --- |
| Before implementation | C1 and C2 fail, **C10 passes** — the render already invented nothing, and must not start |
| "Tidy" the two short-gap lines to 3 spaces | the outside-policies diff, the multiset check, **and the named 11-character spacing case** |
| Break the pad rule | all of the above **plus the column-50 invariant**, distinctly |

The middle one is the point. A whole-file diff catches a tidy-up only while the oracle is
untouched; naming the case catches it regardless.

## Corrections this cycle made to its own record

- **SC-001 was too strong.** It demanded a clean whole-file diff without re-checking cycle 023's
  zone-pair finding. Corrected in the spec during implementation, with the reason stated.
- **FR-004 named the wrong file.** It said `tcp_mss` goes in `objects/32_nfd41_security.yml`; `fw1`
  the `SecurityFirewall` is defined in `objects/31_nfd41_offfabric_devices.yml`, and that is where
  the value went.
- **A duplicate test name silently disabled cycle 023's `test_the_exclusions_add_up`.** Adding a
  second function of the same name shadows the first rather than colliding — ruff caught it. The
  stale version asserted `in_scope == 573` and `excluded == 104`, figures from a scope this cycle
  superseded, so it was replaced rather than renamed, with a comment where it stood explaining
  why.
- **An emptiness assertion was too broad.** `not any("tcp-mss" in line)` failed on the
  `interfaces` comment, which is the device's own prose referring to "`security flow tcp-mss`
  below". Narrowed to the stanza. Worth noting that on a firewall *without* a clamp that
  transcribed comment would point at a stanza that is not there — a wart in the device's words
  rather than in this renderer.

## A finding that unblocks future cycles

`infrahubctl graphql export-schema` has no `--branch` flag, and `generate-return-types` reads a
local `schema.graphql`. Cycle 023 worked around that by loading its schema into `main` mid-cycle,
which is what made its Infrahub merge fail on a `SchemaAttribute` uniqueness violation; cycle 024
avoided it only by deferring the regeneration entirely.

**This cycle needed generated types mid-cycle**, so neither workaround applied. The solution:
every branch has its own `/graphql/<branch>` endpoint, so introspect that and write a temporary
SDL, then point `generate-return-types --schema` at it. Nothing is loaded into `main`, and the
generated types are branch-correct.

That closes a trap that has cost two cycles.

## Integration tests: documented exception

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–025. The
constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative ran in full: schema checked and loaded on a branch, objects loaded and
read back, the artifact rendered live and compared against the fixture render (identical but for
the trailing newline the CLI adds), counts verified, braces checked, credentials grepped.

## What remains after this cycle

- **The `system` stanza and the file header.** Permanently excluded, for the two different reasons
  above.
- **The zone-pair sequence.** Not reproducible without modelling presentation. Documented in
  `AGENTS.md`, `.infrahub.yml`, the transform docstring and a test.
- **A check asserting the six `deny-spoofed-infra` rules stay identical.** A follow-up since cycle
  023; it is a check cycle.
- **`infrahubctl generator` cannot run a generator whose target members lack a `name`.** Found in
  cycle 024, pre-existing, unrelated.
- **Fifteen older Infrahub branches**, listed above, left for the requester.
