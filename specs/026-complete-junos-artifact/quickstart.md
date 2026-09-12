# Quickstart Validation: Completing the Perimeter Firewall Artifact

**Cycle**: 026 | **Branch**: `026-complete-junos-artifact` | **Infrahub branch**: `fw-complete`

Twelve steps. The alignment question that steps 3 and 4 settle was already answered in Phase 0
against the device file; these repeat it against the real render.

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be ✅
export INFRAHUB_API_TOKEN=...    # writes need auth; reads do not
```

The lab repo must be checked out alongside. Without it the junos test modules skip rather than
fail.

## 1. The schema validates and loads

```bash
uv run infrahubctl branch create fw-complete
uv run infrahubctl schema check schemas/ --branch fw-complete
uv run infrahubctl schema load schemas --branch fw-complete
```

**Expected**: all files valid; the diff names `SecurityFirewall` gaining `tcp_mss` and nothing
else. If any other kind appears, the extension landed in the wrong place.

## 2. The value is seeded and reads back

```bash
uv run infrahubctl object load objects/32_nfd41_security.yml --branch fw-complete
```

**Expected**: `fw1.tcp_mss` is `9138`. Re-loading must not duplicate anything — count, do not read
the log; `infrahubctl` prints "Created node" for an upsert, a trap cycles 023–025 all recorded.

## 3. The offline gate

```bash
uv run pytest tests/unit/test_junos_config.py tests/unit/test_junos_seed_data.py -q
```

**Expected**: all pass, including the new whole-file comparison (C1) and the accounting
assertion (C2).

## 4. Prove the alignment test is real

Change the comment gap on **one** of the two short-next-hop lines from 2 spaces to 3 — the
"tidy-up" a well-meaning reader would make.

**Expected**: both C1 (the whole-file diff) and C3's 11-character case fail. If only C1 fails, the
named case is not actually asserting the spacing and the tidy-up would survive a future refactor
that relaxed the diff.

Restore afterwards.

## 5. The whole-file diff, live

```bash
uv run infrahubctl transform junos_config --branch fw-complete device=fw1 > /tmp/fw1.conf
```

Strip the provenance line from the render, and the 72-line header plus the `system` stanza from
the device file, then `diff`.

**Expected**: **no output**. This is SC-001, and it is the cycle's headline claim.

**Expected line count**: 592 plus the provenance line.

## 6. Nothing invented

Compare configuration lines (excluding comments and blanks) in both directions.

**Expected**: 459 in the render, 459 in the device file, **0 present in the render and absent from
the device**. The second number is the one worth checking; it was 0 before this cycle and must
stay 0.

## 7. Emptiness

Render from a fixture with the routes removed, and again with `tcp_mss` removed.

**Expected**: no `routing-options` stanza in the first, no `flow` stanza in the second. Not an
empty `static { }`, not `mss 0`.

## 8. The three comment blocks

**Expected**: all three present, each in position. Grep for the NAT block specifically — it is the
one that documents an absence, so nothing in the model implies it and only the template can carry
it.

## 9. No credential

```bash
grep -riE "encrypted-password|\\\$[0-9]\\\$" /tmp/fw1.conf transforms/junos_config.gql objects/
```

**Expected**: no hit outside the docstrings that explain the exclusion. Re-verified, not inherited
from cycle 023.

## 10. Braces and the trailing newline

**Expected**: braces balance across the whole artifact; the file ends with exactly one newline.

## 11. Repository hygiene

```bash
git worktree list                                    # before
git merge-base --is-ancestor 213e83e main && echo safe
git worktree remove .claude/worktrees/agent-a7e2fddc3b0b7c881
git worktree list                                    # after
uv run invoke lint-yaml
```

**Expected**: the ancestor check **succeeds before removal** — that is the safety gate, not an
afterthought. Afterwards `git worktree list` shows only the main worktree, and `lint-yaml` reports
zero errors, down from 623.

**Also**: `.yamllint` must now ignore `/.claude`. Removing the worktree alone fixes today's errors
and leaves the next agent worktree free to reintroduce them, because the existing
`/lab/avd/intended` ignore is anchored and does not cover a nested copy.

Then the Infrahub branches:

```bash
uv run infrahubctl branch list
```

Delete the merged per-cycle branches. **List anything whose purpose is unclear for the requester
rather than deleting it on a guess** — several predate this sequence of cycles.

## 12. The full gates

```bash
uv run invoke test
uv run invoke lint
```

**Expected**: the unit suite green at or above 1021; ruff, ruff-format, yamllint, mypy and rumdl
clean. `yamllint` now covers the whole tree meaningfully for the first time in this sequence.

## Integration tests

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–025. The
constitution's escape clause applies and **the pull request must say so explicitly**. Steps 1–11
are the non-live alternative.

## Merging

This cycle **does** change schema, so cycle 023's trap applies again: `export-schema` has no
`--branch` flag. Do not load this cycle's schema into `main` to regenerate `schema.graphql` —
that is what made 023's Infrahub merge fail on a `SchemaAttribute` uniqueness violation. Merge
first, regenerate after, as cycle 024 did successfully.

## Teardown

```bash
uv run infrahubctl branch delete fw-complete         # after merging
```
