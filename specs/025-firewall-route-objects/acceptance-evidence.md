# Acceptance Evidence: The Perimeter Firewall's Static Routes

**Cycle**: 025 | **Date**: 2026-09-12 | **Infrahub branch**: `fw-routes-obj`

## SC-001, SC-002, SC-003 — the eight routes, transcribed

`objects/32b_nfd41_fw_static_routes.yml` holds eight `RoutingStaticRoute` entries, all on `fw1`.
The values were **derived from the oracle programmatically**, not retyped, so no transcription
step existed to get wrong.

`tests/unit/test_fw_static_route_objects.py`: **13 passed**. The comparison against
`../lab/configs/fw/vsrx/junos.conf` runs in both directions as three separate assertions —
nothing missing, nothing invented, values equal.

## SC-004, SC-005 — the two cross-checks

| Destination | Next hop | Lands on | Address book |
| --- | --- | --- | --- |
| `10.110.0.0/24` | `10.250.110.1` | ge-0/0/0 | k8s-nodes |
| `10.111.0.0/16` | `10.250.110.1` | ge-0/0/0 | k8s-pods |
| `10.112.0.0/16` | `10.250.110.1` | ge-0/0/0 | k8s-services |
| `10.210.0.0/24` | `10.250.210.1` | ge-0/0/1 | app-hosts |
| `10.60.0.0/16` | `10.250.150.1` | ge-0/0/2 | wan-customers |
| `10.70.0.0/24` | `10.250.170.1` | ge-0/0/3 | branch-users |
| `10.220.10.0/24` | `10.250.10.1` | ge-0/0/4 | acme-cloud |
| `10.220.20.0/24` | `10.250.20.1` | ge-0/0/5 | globex-cloud |

The converse of SC-005 is **not** asserted, and a test pins that the five unrouted book entries
stay exactly the expected five: `fabric-infra` (never a destination — six appearances as a rule
`source_address` in the anti-spoofing rules), and `acme-hq`, `acme-dr`, `globex-hq` (inside
`10.60.0.0/16`). `access-portal` (`10.112.240.33/32`) carries an `ip_address` rather than an
`ip_prefix`, so it is outside that set, and sits inside `10.112.0.0/16` regardless.

## The two deliberate breaks

### T015 — a changed destination fails both directions separately

Changing `10.70.0.0/24` to `10.71.0.0/24`:

```text
FAILED test_every_route_in_the_device_file_is_in_the_object_file
FAILED test_every_route_in_the_object_file_is_in_the_device_file
FAILED test_every_destination_is_an_address_book_prefix
FAILED test_the_address_book_entries_without_a_route_are_the_expected_five
```

Both directions of the comparison fired **independently**, which is the point: a both-ways check
that only ever fires one way is a one-way check, and cycle 023 deleted fourteen lines of correct
data to exactly that.

### T018 — and the proof that the interface check is worth its place

Changing one digit of a next hop made both the value comparison and the connected-subnet check
fail. That alone does **not** prove the second is independent — it only shows both notice the
same edit. The claim needing proof is stronger: *the interface check catches something the oracle
comparison structurally cannot.*

So it was demonstrated directly. A corrupted copy of `junos.conf` and an object file that
**faithfully transcribes the corruption** — both saying `10.250.171.1` — were compared:

```text
C3 (both-ways comparison vs the device file): PASSES — sees nothing wrong
C6 (next hop on a connected subnet)        : FAILS — [('10.70.0.0/24', '10.250.171.1')]
```

The two files agree perfectly, so the comparison is satisfied. Only `fw1`'s interface addresses
notice that no port of the firewall is on that subnet — and on the device such a route is
accepted and then silently never installs.

**This is the entire argument for modelling the routes rather than copying a text file**: a text
file cannot check itself against the firewall's interfaces or its policy.

## SC-006 — idempotence, and the trap demonstrated

| Step | `RoutingStaticRoute` total | `fw1.static_routes` |
| --- | --- | --- |
| branch created | 11 | 0 |
| after first load | 19 | 8 |
| **after second load** | **19** | **8** |

The second load printed `Created node` **eight times**. The counts did not move. That is the trap
cycle 023 recorded and cycle 024 relied on, seen directly here: the log is not evidence of
creation, and only counting distinguishes an upsert from a duplicate.

Ownership after loading: `{'DcimDevice': 11, 'SecurityFirewall': 8}` — the eleven fabric routes
written by `backfill-structured-config` are untouched.

## B4, B5 — nothing invented

Read back from the loaded objects:

```text
vrf != 'default' : none — all eight defaulted
unexpectedly set : none — gateway/interface/distance/tag all unset
```

`vrf` is `"default"` on all eight **from the schema default**; the object file sets it nowhere.
The four unset attributes are unset because the device sets none of them — an invented `distance`
or `interface` would be rendered by cycle 026 as configuration the firewall does not have.

## SC-007, SC-008 — nothing else changed

`git diff --stat schemas/` is empty. No existing file under `objects/` is modified; the only
addition there is the new file. Confirmed by `git status --porcelain objects/`.

## SC-009 — gates

| Gate | Result |
| --- | --- |
| `uv run pytest tests/unit` | **1021 passed** (1008 before, plus 13) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 109 files formatted |
| `uv run yamllint objects/ schemas/ .infrahub.yml` | clean |
| `uv run mypy src/solution_arista_avd` | no issues in 8 source files |
| `uv run rumdl check …` | no issues in 35 files |

### A lint result that needed checking rather than reporting

`uv run yamllint .` reports 623 errors. **None are from this cycle.** They come entirely from
`.claude/worktrees/agent-a7e2fddc3b0b7c881/`, a stray worktree carrying a copy of
`lab/avd/intended/structured_configs/`. Verified by stashing this cycle's work and re-running on
a clean tree: the same 623.

Worth recording because a first pass of this section nearly reported "yamllint clean" on the
strength of `uv run yamllint . | tail -3 && echo clean` — where `&&` sees `tail`'s exit status,
not `yamllint`'s. The command was reporting success unconditionally.

## Corrections this cycle made to its own record

- **A guessed address.** While accounting for `access-portal` during research, `10.112.240.10`
  was used. It was not read from the file; the seeded value is `10.112.240.33/32`. The conclusion
  survived — both sit inside `10.112.0.0/16` — but a right answer from a wrong method is not
  evidence. Re-read and corrected before it reached any artifact (research R7).
- **A task's stated mechanism was wrong.** T020 expected `.infrahub.yml` to register `objects` as
  a directory. It has no `objects:` key at all; object loading is explicit, via `tasks.py`'s
  `load` task running `infrahubctl object load objects/`. Same conclusion — the new file is picked
  up with no registration — but by a different mechanism than the task assumed.
- **The misleading lint command**, above.

Three small ones, none of which changed a decision. The pattern across cycles is unchanged: a
claim is safe only once something has run.

## Integration tests: documented exception

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–024. The
constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative ran twice: once in Phase 0 against a generated draft, to decide whether
the approach worked at all, and again here against the committed file.

## Follow-ups this cycle does not close

- **Cycle 026**: render the stanza. The artifact goes 573 → 585 of 677 lines and the exclusion
  total drops 104 → 92. It carries a known difficulty, measured in cycle 024: the stanza is
  column-aligned **by hand and inconsistently**, and two of its eight route lines are misaligned
  by one column, so no single derivation reproduces all eight.
- **`infrahubctl generator`** cannot run any generator whose target members lack a `name`
  attribute — found in cycle 024, pre-existing, unrelated.
- **`export-schema` has no `--branch`** — cost cycles 023 and 024. Does not arise here, since this
  cycle changes no schema.
- **623 yamllint errors** from a stray agent worktree at
  `.claude/worktrees/agent-a7e2fddc3b0b7c881/`. Deleting it would make `invoke lint-yaml` usable
  again.
- **Stale Infrahub branches** — one (`023-junos-config-render`) errors on every repository sync.
