# Phase 0 Research: Completing the Perimeter Firewall Artifact

**Cycle**: 026 | **Date**: 2026-09-12 | **Branch**: `026-complete-junos-artifact`

Eight findings. Two overturn things this project has been repeating for three cycles, and one
turns the cycle's defining risk from "probably impossible" into a solved problem.

---

## R1 — SOLVED: the column alignment does have a byte-exact reproduction

Cycles 024 and 025 both recorded the route lines as "column-aligned by hand and inconsistently…
no single derivation reproduces all eight", and framed it as forcing a choice between storing
presentation in the model and relaxing the success criterion.

Measured properly, **neither is necessary.** The alignment invariant is the **semicolon, not the
comment**:

```text
semicolon at column  50   comment at  54   10.110.0.0/24
semicolon at column  50   comment at  54   10.60.0.0/16
semicolon at column  50   comment at  53   10.220.10.0/24
```

The `;` lands at column 50 on **all eight lines**. What varies is only the gap between `;` and
the comment: 3 spaces on six lines, 2 on two.

Two rules reproduce the file exactly:

| Field | Rule |
| --- | --- |
| gap before `next-hop` | `max(1, 14 - len(prefix))` — pads the prefix field so the `;` aligns |
| gap before the comment | 3 when the next hop is 12 characters, 2 when it is 11 |

Tested against the file: **8/8 byte-exact.** Two earlier candidate rules were tested first and
both scored 6/8, which is how the previous cycles' pessimism arose — they stopped at the first
rule that failed.

**Honesty about the second rule.** The next-hop length is a *correlation*, not a cause. The real
explanation is that two lines were typed with one fewer space than the other six. But the
correlation is total over this data, deterministic, and stores nothing in the model — so it
reproduces the file without modelling presentation. It must be **commented as reproducing a
source inconsistency rather than implementing an alignment rule**, and pinned by a test so that
"tidying" the two lines fails loudly.

**Consequence**: SC-001 can demand a clean diff. No relaxation, no stored spacing.

---

## R2 — CORRECTION: the running "104 excluded lines" figure hid three comment blocks

Repeated in three commit messages, `AGENTS.md`, `.infrahub.yml` and two specs: the remaining gap
is "12 lines of `routing-options` and 7 of `flow`".

That is right about **configuration** and wrong about the **file**. Diffed against the live
render:

| Measure | Value |
| --- | --- |
| In-scope configuration lines | 459 |
| Rendered today | 440 |
| Missing configuration | 19 — exactly the 12 + 7 |
| **Configuration invented by the render** | **0** |
| Comment blocks inside `security` | 13, of which **3 absent** |

The three absent blocks are 6 lines (TCP-MSS arithmetic), 4 lines (why the address book uses
named objects) and 9 lines (**why NAT is absent and why that absence is load-bearing**).

The last one matters most: it records that a source-NAT rule here would translate real pod
addresses and silently make every downstream ACL meaningless, and that `make verify` checks no
`nat` stanza has appeared. A render that drops it emits a configuration that looks complete and
has lost the reason it is safe.

**Why it was missed**: every cycle since 023 re-read the previous cycle's *spec* instead of
diffing the *artifact*. The figure was inherited, not re-derived.

---

## R3 — The accounting, verified rather than asserted

```text
677 total = 72 header + 13 system + 592 rest
592 + 13 + 72 = 677
459 in-scope configuration lines
```

Computed from the file before the spec's checklist was marked. SC-010 requires a **test** to
assert this, because a prose comment claiming a total is exactly what cycle 023 had when its
accounting was wrong by seven lines.

**A distinction previous cycles flattened**: the 72 header lines are 68 comments and 4 blanks —
the lab's documentation *about* the file, including how vrnetlab appends it to `init.conf`.
Grouping them with `system` conflates "configuration deliberately never modelled" with "not
configuration at all". They are excluded for different reasons and the spec now says so.

---

## R4 — The `flow` block's position, and what it needs

`flow` is the **first** block inside `security`, before `address-book`, preceded by its 6-line
comment. The current `junos.j2` goes straight from `security {` to `address-book.j2`.

Nothing models the value: `SecurityFirewall`'s live attributes are `role`, `name`, `os_version`,
`description`, `position`, `serial`, `rack_face`. No `mss` or `tcp_mss` anywhere in `schemas/`,
`objects/` or `transforms/` — only three prose mentions of the clamp, one of which is in the
rendered `interfaces.j2` comment. **The artifact currently explains a clamp it does not emit.**

**Decision**: one optional `Number` attribute on `SecurityFirewall`, in
`schemas/security_extensions.yml` — the same local extension file that already holds `book_index`
and `log_session_close`, both added by cycle 023 in exactly this shape. `schemas/security/security.yml`
is marketplace-adopted and is not touched.

**Optional, not mandatory with a default**: a firewall with no clamp must render no `flow` stanza.
A default would render `mss 0` or an empty block on any future firewall.

---

## R5 — The stray worktree is a REGISTERED git worktree, not a stray directory

`rm -rf` would have been wrong. `git worktree list`:

```text
/home/ubuntu/dev/nfd41/infrahub                                  4cf9811 [026-complete-junos-artifact]
/home/ubuntu/dev/nfd41/infrahub/.claude/worktrees/agent-…        213e83e [014-k8s-leaf-peering-svi]
```

Deleting the directory alone leaves a stale registration that `git worktree list` keeps reporting.
The correct removal is `git worktree remove`.

**Safety, checked before proposing removal**: its working tree is clean, and
`git merge-base --is-ancestor 213e83e main` **succeeds** — its HEAD is fully merged, so nothing is
lost. Its last commit is "Close out the cycle: all 45 tasks done", from cycle 014.

---

## R6 — The 623 lint errors have a durable fix, not just a cleanup

`.yamllint` already ignores `/lab/avd/intended` — "Rendered by arista.avd.eos_designs; AVD's
emitter does not indent sequences". That is exactly the directory generating the errors.

The worktree carries its own copy at `.claude/worktrees/…/lab/avd/intended/structured_configs/`,
and the ignore pattern is **anchored** (`/lab/…`), so the copy is not covered. `invoke lint-yaml`
runs `yamllint .`, which does not read `.gitignore` — and the worktree *is* excluded from git, via
`.git/info/exclude`.

So removing the worktree fixes today's 623 errors, and the next agent worktree reintroduces them.

**Decision: do both.** Remove the worktree (R5) *and* add `/.claude` to `.yamllint`'s ignore list.
The spec's FR-017 asked for "a judgement to make once, not a workaround to repeat"; this is it.

---

## R7 — What must NOT change

| Thing | Why |
| --- | --- |
| `schemas/security/security.yml` | marketplace-adopted, byte-identical to `infrahub/security` 1.0.2 |
| The `system` stanza's absence | two `encrypted-password` hashes; the model must never hold them and the query must never ask |
| The artifact definition, transform registration, target group | already correct; this cycle adds no new output |
| The eight `RoutingStaticRoute` objects | seeded and verified in cycle 025; read, not rewritten |
| Rule order within a zone pair | first-match is semantic — cycle 023's finding, untouched here |

Static route order, by contrast, **is** presentational: routes are longest-prefix matched, so no
behaviour depends on the sequence. Determinism is required; matching the file's grouping is
preferred and achievable, since the transform can order by the stored data.

---

## R8 — A correction to how this cycle's own risk was described

The spec, written before this research, records Assumption 2: alignment "cannot be derived by one
rule", and offers "the pad rule plus an enumerated two-line exception" as the preferred route.

R1 supersedes that. Two rules reproduce all eight lines byte-exactly with no exception list and
nothing stored in the model. The assumption is not wrong in spirit — the source *is*
inconsistent — but its practical conclusion was pessimistic, and it was inherited from cycle 024
rather than re-tested.

The spec is amended rather than quietly left standing.

---

## Summary of decisions

| # | Decision | Rationale |
| --- | --- | --- |
| R1 | Derive both gaps; store no spacing | 8/8 byte-exact, verified against the file |
| R2 | Render the three comment blocks | One of them is why the configuration is safe |
| R3 | Assert the arithmetic in a test | A comment claiming a total is what failed in 023 |
| R4 | One optional Number attribute in the local extension file | Matches cycle 023's two additions; adopted schema untouched |
| R5 | `git worktree remove`, not `rm -rf` | It is registered; and its HEAD is merged, so removal is safe |
| R6 | Also ignore `/.claude` in `.yamllint` | Otherwise the next worktree reintroduces 623 errors |
| R7 | Change nothing else | Enumerated above |
| R8 | Amend the spec's Assumption 2 | Its conclusion was inherited and pessimistic |

## Spec amendments this research requires

1. **Assumption 2 replaced**: alignment is reproducible by two derived rules, verified 8/8. No
   enumerated exception list, no stored presentation.
2. **FR-014 strengthened**: from "any deviation enumerated" to "reproduced byte-exactly, with the
   source inconsistency documented and pinned by a test".
3. **FR-017 resolved**: the judgement is to remove the registered worktree *and* ignore `/.claude`
   in `.yamllint`.
