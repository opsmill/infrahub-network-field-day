# Quickstart Validation: Device-Level Static Routes for the Perimeter Firewall

**Cycle**: 024 | **Branch**: `024-firewall-static-routes` | **Infrahub branch**: `fw-routes`

Nine steps. Steps 3 to 5 were already run once during Phase 0 research, on a scratch copy that
was then reverted — they are repeated here against the real implementation.

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be ✅
export INFRAHUB_API_TOKEN=...    # writes need auth; reads do not
```

The `fw-routes` Infrahub branch already exists from Phase 0. Re-loading the schema onto it is
idempotent, so there is no need to recreate it.

## 1. The schema validates

```bash
uv run infrahubctl schema check schemas/ --branch fw-routes
```

**Expected**: all 38 files `Valid!`, and a diff naming exactly four changed kinds —
`RoutingStaticRoute` (peer changed), `DcimGenericDevice`, `SecurityFirewall` and
`ComputePhysicalServer` (each gaining `static_routes`).

**Expected to be absent**: any `DcimDevice` entry, and any non-empty `removed:` block. If
`DcimDevice` appears with `static_routes` removed, the reverse side moved without inheritance
covering it, and step 5's second half will fail.

## 2. The schema loads

```bash
uv run infrahubctl schema load schemas --branch fw-routes
```

**Expected**: 38 schemas processed, no error. Loading with the eleven existing
`RoutingStaticRoute` objects present is itself the migration test — a widening that needed a
migration would fail here.

## 3. A firewall can own a static route (B1, B3, B4)

Create a route on `fw1`, then try two things that must fail.

**Expected**:

- `device: fw1` → accepted, and the created object's `device.node.__typename` is
  `SecurityFirewall`.
- the same `prefix` again on `fw1` → rejected by the uniqueness constraint.
- a route with no `device` at all → rejected, message names `device` as mandatory.

## 4. Existing devices are unaffected (B2, B5)

```bash
# read any DcimDevice and its static_routes
```

**Expected**: a fabric device still exposes `static_routes` and still resolves its existing
routes. `fw1.static_routes` returns the route from step 3.

**Count check**: `RoutingStaticRoute` totals 11 on `main` and 12 on `fw-routes` while the probe
route exists. Delete the probe afterwards so the branch carries only the schema change.

## 5. The generator still works and is still idempotent (D1)

This is the step R6 added, and the one most likely to catch a real problem — the backfill
generator writes this kind on every run and its `save(allow_upsert=True)` resolves against the
uniqueness constraint that names `device`.

```bash
uv run pytest tests/unit/test_backfill_structured_config.py -q
```

Then, on the branch, run the generator twice and count.

**Expected**: the second run creates no new `RoutingStaticRoute`. Count before and after rather
than reading the log — the CLI prints "Created node" for an upsert, which cycle 023 already found
misleading.

## 6. The FRR configurations are unchanged (D2)

```bash
uv run pytest tests/unit/test_frr_config.py -q
```

**Expected**: all pass. `frr_config` reads `RoutingVrfStaticRoute` through `WanSite`, a different
kind, so this should be untouched — the step exists to prove that rather than assume it.

## 7. The new contract test pins the relationship

```bash
uv run pytest tests/unit/test_routing_schema_contract.py -q
```

**Expected**: passes, covering C1–C6 of [contracts/schema-contract.md](./contracts/schema-contract.md).

**Also expected**: reverting the peer to `DcimDevice` makes it **fail**. Check that once, by hand,
before trusting it. A contract test that passes either way is worse than none, and R7 is the
record of exactly that situation existing today.

## 8. Generated files are regenerated, not hand-edited (D3)

```bash
uv run infrahubctl graphql export-schema --destination schema.graphql
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
grep -n "class RoutingStaticRoute" -A12 src/solution_arista_avd/protocols.py
```

**Expected**: both regenerate cleanly and `RoutingStaticRoute`'s device field reflects the
generic.

**Note the trap cycle 023 hit**: `export-schema` has **no `--branch` flag`**. It exports whatever
Infrahub `main` holds. Running it before the branch is merged exports the *old* schema, and
loading the new schema into `main` to work around it is what caused 023's merge to be refused on
a `SchemaAttribute` uniqueness violation. Do this step **after** merging, or accept that
`schema.graphql` lags by one cycle.

## 9. The adopted schema is untouched (C7)

```bash
diff <(uv run infrahubctl marketplace get infrahub/security --stdout) \
     schemas/security/security.yml
```

**Expected**: no output.

## 10. The full gates

```bash
uv run invoke test
uv run invoke lint
```

**Expected**: 998 unit tests plus whatever the new contract test adds; ruff, ruff-format,
yamllint, mypy and rumdl clean.

## Integration tests

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–023. The
constitution's escape clause applies and **the pull request must say so explicitly**. Steps 1–9
above are the non-live alternative, and for this cycle they are unusually strong: every
behavioural clause was demonstrated against a running instance in Phase 0 before any code was
written.

## Teardown

```bash
uv run infrahubctl branch delete fw-routes    # after merging
```

Note that five stale Infrahub branches already exist from earlier cycles, one of which
(`023-junos-config-render`) errors on every repository sync. Not this cycle's job, but do not add
a sixth.
