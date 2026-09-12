# Transform Contract: Completing the Perimeter Firewall Artifact

**Cycle**: 026 | **Consumed by**: `tests/unit/test_junos_config.py` (extended) and
`tests/unit/test_junos_seed_data.py` (extended)

Every clause is an assertion made against the rendered output, the object files or the schema
YAML. None needs a running Infrahub — the existing modules render from
`tests/unit/fixtures/junos/fw1.json`.

## C1 — The whole-file comparison

The rendered artifact, minus its provenance line, is **identical** to
`../lab/configs/fw/vsrx/junos.conf` with these removed:

- the 72-line header (every line before the first top-level stanza)
- the 13-line `system` stanza

A unified diff produces **no output**. This clause subsumes every stanza-level check the module
already makes; those stay because they say *where* a failure is, but this one says *whether*.

The module must skip when the lab repo is not checked out alongside, as it already does.

## C2 — The accounting, asserted rather than claimed

```text
677 = 592 (rendered) + 13 (system) + 72 (header)
```

Computed from the device file at test time, not hard-coded as three literals that could drift
apart from it. Cycle 023 carried a prose comment claiming its total and the total was wrong by
seven lines; SC-010 exists because of that.

## C3 — The eight route lines, byte-exact

Each rendered line equals its device-file counterpart exactly, interior spacing included.

Assert **both** spacing cases explicitly, not just the aggregate:

| Case | Example | `pad` | `gap` |
| --- | --- | --- | --- |
| 12-character next hop | `10.110.0.0/24` → `10.250.110.1` | 1 | 3 |
| 12-char next hop, short prefix | `10.60.0.0/16` → `10.250.150.1` | 2 | 3 |
| **11-character next hop** | `10.220.10.0/24` → `10.250.10.1` | 1 | **2** |

The third row is the one that matters. Six lines carry three spaces before the comment and two
carry two, because those two were typed one space short. A test that only checks the aggregate
diff would pass if someone "tidied" the two lines *and* updated the oracle; a test that names the
case fails on the tidy-up alone.

## C4 — The semicolon alignment

Every rendered route line has its `;` at column 50. This is the actual invariant the `pad` rule
implements, so it is asserted directly rather than left implicit in C3.

## C5 — Stanza position

| Stanza | Position |
| --- | --- |
| `routing-options` | between `interfaces` and `security` |
| `flow` | the **first** block inside `security`, before `address-book` |

## C6 — Emptiness

| Condition | Required output |
| --- | --- |
| firewall has no static routes | **no** `routing-options` stanza — not an empty `static { }` |
| firewall has no `tcp_mss` | **no** `flow` stanza — not `mss 0`, not an empty block |

Both are rendered from a modified copy of the fixture, so neither needs a server.

## C7 — The three comment blocks

Each appears in the rendered output, verbatim, in the same position as in the device file:

| Lines | Position | Identifying text |
| --- | --- | --- |
| 6 | before `flow` | "Clamp TCP to what the 9192-byte interface MTU can actually carry" |
| 4 | before `address-book` | "Named objects rather than bare CIDRs" |
| 9 | after the address book | "NAT is absent from this file, and that absence is load-bearing" |

The NAT block is asserted by its own clause as well as by C1, because it documents an *absence* —
nothing in the model implies it, so nothing but the template can carry it, and nothing but a test
can notice it going missing.

## C8 — The schema addition

`schemas/security_extensions.yml` declares, under `extensions.nodes`, a `SecurityFirewall` entry
with a `tcp_mss` attribute:

| Property | Required |
| --- | --- |
| `kind` | `Number` |
| `optional` | `true` |
| default | **absent** |

`optional: true` with no default is the pair that makes C6's second row possible.

`tests/unit/test_security_schema_contract.py` currently asserts that the extensions file touches
exactly three kinds. That count becomes **four**, changed deliberately — as cycle 023 changed it
from two to three — not loosened to "at least".

## C9 — The seeded value

`objects/32_nfd41_security.yml` sets `tcp_mss: 9138` on `fw1`, and the value equals the one in the
device file's `mss` line. Asserted against the oracle, not hard-coded twice.

## C10 — Nothing invented

The rendered artifact contains **zero** configuration lines absent from the device file. True
today (measured: 0) and it must stay true. Distinct from C1 because it is the direction that
catches a template emitting something plausible but wrong.

## C11 — No credential

No `encrypted-password`, no hash, and no `system` stanza in the rendered artifact, in the
`.gql` query, or in the object files. Re-verified rather than inherited from cycle 023.

## C12 — Braces and trailing newline

Braces balance across the whole artifact, and the file ends with exactly one newline. Existing
clauses; they must still hold once two stanzas are added.

## Repository-hygiene clauses — not unit-testable

Verified by hand in [quickstart.md](../quickstart.md).

| # | Clause |
| --- | --- |
| H1 | `git worktree list` shows only the main worktree |
| H2 | `git merge-base --is-ancestor 213e83e main` succeeded **before** removal — nothing lost |
| H3 | `.yamllint` ignores `/.claude`, so a future agent worktree cannot reintroduce the errors |
| H4 | `uv run invoke lint-yaml` reports zero errors |
| H5 | Merged per-cycle Infrahub branches are deleted; any branch whose purpose is unclear is **listed for the requester**, not deleted on a guess |
