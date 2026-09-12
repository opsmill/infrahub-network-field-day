# Quickstart Validation: The Perimeter Firewall's Static Routes

**Cycle**: 025 | **Branch**: `025-firewall-route-objects` | **Infrahub branch**: `fw-routes-obj`

Nine steps. Steps 2–6 were run once during Phase 0 against a generated draft; they are repeated
here against the committed file.

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be ✅
export INFRAHUB_API_TOKEN=...    # writes need auth; reads do not
```

The lab repo must be checked out alongside this one for the oracle comparison. Without it the
test module skips rather than fails.

## 1. The offline gate

```bash
uv run pytest tests/unit/test_fw_static_route_objects.py -q
```

**Expected**: all pass, covering C1–C8 of
[contracts/object-contract.md](./contracts/object-contract.md). No server needed — everything
comes from the two object files and the device file.

**Also check once, by hand**: change a single digit of one `next_hop` and confirm **two** clauses
fail — the oracle comparison (C3) and the connected-subnet check (C6). If only one fails, the
independent witness is not independent.

## 2. Record the baseline before loading

```bash
uv run infrahubctl branch create fw-routes-obj
```

Count `RoutingStaticRoute` on the branch.

**Expected**: 11 — the fabric routes written by `backfill-structured-config`. This cycle must
leave them alone, so the number matters at the end as well as the start.

## 3. Load (B1)

```bash
uv run infrahubctl object load objects/32b_nfd41_fw_static_routes.yml --branch fw-routes-obj
```

**Expected**: eight nodes created, no error.

## 4. The routes are on the firewall (B2, B3)

Query `fw1.static_routes` and the total.

**Expected**: `fw1.static_routes = 8`, total `RoutingStaticRoute = 19`. The 11 pre-existing fabric
routes are untouched — check the count, not just the firewall's own.

## 5. Only the intended fields are set (B4, B5)

Read all eight back.

**Expected**: `vrf = "default"` on every one, **from the schema default** — the object file sets
it nowhere. `gateway`, `interface`, `distance` and `tag` all unset.

This is worth reading back rather than trusting the file: an invented `distance` or `interface`
would be rendered by cycle 026 as configuration the device does not have.

## 6. Idempotence (B6)

Load the same file a second time, then count again.

**Expected**: still 8 on `fw1`, still 19 in total.

**Count — do not read the log.** `infrahubctl` prints "Created node" for an upsert. Cycle 023
recorded that trap and cycle 024 relied on counting for the same reason.

## 7. Both-ways comparison against the device (SC-002)

The unit test covers this, but confirm the shape of the check once by eye: a route present in the
device file and absent from the graph must fail, and so must the reverse.

**Why this is called out separately**: cycle 023 deleted fourteen lines of correct data after a
one-way read concluded something was missing when the search was at fault.

## 8. Nothing else changed (SC-007, SC-008)

```bash
git status --short
git diff --stat schemas/ objects/
```

**Expected**: one new file under `objects/`, one new file under `tests/unit/`, the spec
directory. **No** modification to any existing `objects/` file and **nothing** under `schemas/`.

## 9. The full gates

```bash
uv run invoke test
uv run invoke lint
```

**Expected**: 1008 existing unit tests plus the new module; ruff, ruff-format, yamllint, mypy and
rumdl clean.

`yamllint` covers `objects/`, so the new file must satisfy it — line length included.

## Integration tests

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–024. The
constitution's escape clause applies and **the pull request must say so explicitly**. Steps 2–6
are the non-live alternative and were additionally run in Phase 0 before the plan was written.

## Teardown

```bash
uv run infrahubctl branch delete fw-routes-obj      # after merging
```

Six stale Infrahub branches already exist from earlier cycles, one of which
(`023-junos-config-render`) errors on every repository sync. Not this cycle's job — but do not
leave a seventh.

## Merging, and the trap to avoid

Cycle 024's Infrahub merge succeeded where 023's failed, for one reason: 024 never loaded its
schema into `main` to regenerate `schema.graphql`.

**This cycle changes no schema**, so `schema.graphql` needs no regeneration and the trap does not
arise. Merge the Infrahub branch normally.
