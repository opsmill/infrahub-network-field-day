# Acceptance Evidence: Device-Level Static Routes for the Perimeter Firewall

**Cycle**: 024 | **Date**: 2026-09-12 | **Infrahub branch**: `fw-routes`

## SC-001 — the schema validates

`uv run infrahubctl schema check schemas/ --branch fw-routes`: all 38 files `Valid!`.

The diff names exactly four kinds, and that set is itself the evidence:

| Kind | Change | Intended |
| --- | --- | --- |
| `RoutingStaticRoute` | `device.peer` changed | yes |
| `DcimGenericDevice` | gains `static_routes` | yes |
| `SecurityFirewall` | gains `static_routes` | **the point of the cycle** |
| `ComputePhysicalServer` | gains `static_routes` | accepted side effect |

`DcimDevice` does **not** appear in the diff, and every `removed:` block is empty — checked
explicitly rather than eyeballed. It keeps `static_routes` by inheritance, not declaration.

**A half-wired intermediate state was observed and is worth recording.** With only the forward
peer widened and the reverse side still on `DcimDevice`, the diff listed `RoutingStaticRoute`
alone: `SecurityFirewall` gained nothing. That is exactly the failure contract clauses C3 and C4
exist to catch, seen in passing rather than argued about.

## SC-002, SC-005, SC-006 — behaviour, on a live branch

Loaded with all eleven existing `RoutingStaticRoute` objects present, which is itself the
migration test: a widening that needed a migration fails at load.

```text
baseline RoutingStaticRoute on fw-routes: 11
B1 route on fw1                 : ACCEPTED {'__typename': 'SecurityFirewall', 'display_label': 'fw1'}
B4 duplicate prefix on fw1      : REJECTED (uniqueness holds)
B3 route with no device         : REJECTED (device mandatory)
B5a fw1.static_routes           : count=1 ['10.110.0.0/24']
B2/B5b spine-nfd41-pod1-1       : static_routes count=1
after probes: 12 (baseline 11 + 1 probe)
```

Probe deleted afterwards; the branch is back to 11.

**SC-002 requires the before-state to fail, and it did.** The branch was deleted and recreated
from `main` before implementation so the check was genuine: `RoutingStaticRoute.device peer =
DcimDevice`, `SecurityFirewall has static_routes = False`. Without that reset the Phase 0 probe
load would have made the diff empty and the criterion meaningless.

## SC-003 — the consumers

| Consumer | Result |
| --- | --- |
| `tests/unit/test_backfill_structured_config.py` | 85 passed |
| `tests/unit/test_frr_config.py` | 21 passed |
| `tests/unit/test_junos_config.py` + seed data | 37 passed |
| Full suite | **1008 passed** (998 before, plus the ten new contract tests) |

### Generator idempotence — and why it was tested a different way

`infrahubctl generator backfill-structured-config` **fails in this environment**, and it fails
identically on a branch with the peer **unchanged**:

```text
File ".../infrahub_sdk/ctl/generator.py", line 89, in run
AttributeError: 'InfrahubNode' object has no attribute 'name'
```

The cause is pre-existing and unrelated to this cycle. The CLI does
`member.peer._get_attribute(name="name").value` unconditionally, ignoring the definition's
`parameters` mapping; this generator targets `avd_structured_configs`, whose seven members are
`AvdStructuredConfigFile` nodes with **no `name` attribute** — hence `name: artifact__name__value`
in `.infrahub.yml`. Verified both halves: the mapping, and that the kind has no `name`.

Isolating it before blaming the cycle mattered: the first run was on the changed branch, and it
would have been easy to read the traceback as a regression.

So the upsert path was driven directly — the exact two lines the generator uses
(`backfill_structured_config.py:499-501`), with the node **id** the generator passes:

```text
baseline                              : 11
SecurityFirewall (fw1)                : after 1st=12 after 2nd=12 -> SAME object -> IDEMPOTENT
DcimDevice (spine-nfd41-pod1-1)       : after 1st=13 after 2nd=13 -> SAME object -> IDEMPOTENT
final                                 : 13 (baseline 11 + 2 probes)
```

Both probes deleted; back to 11. Counted rather than read from the log, because `infrahubctl`
prints "Created node" for an upsert — a trap cycle 023 already recorded.

This is stronger evidence than the CLI run would have been: it exercises `allow_upsert=True`
against the uniqueness constraint for a `SecurityFirewall` *and* a `DcimDevice`, which is the
behaviour the widening could plausibly have broken.

## SC-004 — both directions resolve

`fw1.static_routes` returned the route; `spine-nfd41-pod1-1.static_routes` returned its own.
Contract clause C3 pins that both ends carry `device__static_route`, C4 that `DcimDevice` does
not re-declare it.

## SC-007 — the adopted schema is untouched

```bash
diff <(uv run infrahubctl marketplace get infrahub/security --stdout) schemas/security/security.yml
```

No output. `schemas/security/security.yml` is byte-identical to marketplace `infrahub/security`
1.0.2, and `git diff` shows this cycle never touched it. `SecurityFirewall` gained
`static_routes` purely by inheritance.

## SC-008 — generated files

`protocols.py` regenerated; the diff is one line, which is the right size:

```diff
-    device: RelationshipAttribute[DcimDevice]
+    device: RelationshipAttribute[DcimGenericDevice]
```

`schema.graphql` is **deliberately not regenerated** — see the deferred-work section.

## SC-009 — the record

Four files corrected, one more than the tasks listed:

| File | Was | Now |
| --- | --- | --- |
| `AGENTS.md` | "`routing-options` needs a device-level static route the schema does not have" | names the real blocker and what remains (025, 026) |
| `.infrahub.yml` | "`routing-options` pending a schema cycle" | pending seed data and a template |
| `transforms/junos_config.py` | "eight routes with no device-level home in the schema" | the gap closed in 024 |
| `docs/docs/developer-guide/schemas.md` | documented only `RoutingVrfStaticRoute` | documents both kinds and warns they are distinct |

The transform docstring was not in the task list. It carried the same wrong sentence and would
have outlived the other three.

## SC-010 — the gate that did not exist

`tests/unit/test_routing_schema_contract.py`, ten tests. Proven to work in both directions:

- Before the change: **4 failed, 5 passed** — and the four were exactly C1–C4.
- After: 10 passed.
- Peer reverted to `DcimDevice` by hand: `test_static_route_device_peers_the_device_generic`
  **failed**. Restored: passed.

That last check is the point. A contract test that passes either way is worse than none.

## An error this cycle made, and what it changed

**A careless `sed` widened five unrelated relationships.** Reverting the peer for the T012
red-green check was done with
`sed -i 's/^        peer: DcimDevice$/        peer: DcimGenericDevice/'`, which is a global
replace. It flipped `RoutingBGPPeerGroup.device`, `RoutingBGPNeighbor.device`, `RoutingAsn.devices`,
`RoutingPrefixList.device` and `RoutingRouteMap.device` along with the intended one — six
occurrences where one was meant.

It was caught by reading the diff before continuing, and fixed by restoring from `git` and
reapplying the edit anchored on a unique surrounding block.

**Nothing would have caught it.** Measured, not assumed — the mistake was deliberately
reintroduced and both gates run:

| Gate | Result with all six peers wrongly widened |
| --- | --- |
| `infrahubctl schema check` | **all 38 files `Valid!`** |
| `uv run pytest tests/unit` | 1004 passed, 3 failed — and all three were the C2/C3/C4 failures already expected at that point. None concerned the five collateral relationships |

So a schema contract test was added for it:
`test_only_the_static_route_peers_the_device_generic` asserts the complete map of `Dcim*` peers in
`routing.yml`, pinning the other five to the concrete kind. It is the eleventh test in the module
and the only one that exists because of a mistake made while writing the other ten.

The lesson is narrower than "be careful with sed": **widening a peer is not a neutral act**, and a
whole-file substitution on a schema is a change of blast radius, not of syntax.

## Findings for the next cycles

**Object-load HFID references work through a generic peer** — tested, because it would have
blocked cycle 025. A `RoutingStaticRoute` with `device: "fw1"` loads from an object file without
complaint.

This was worth checking because the Python SDK's `client.create(..., device="fw1")` **fails** on
the generic peer:

```text
Unable to find the node fw1 / DcimGenericDevice in the database. (NODE_NOT_FOUND)
```

Raw GraphQL with `device: {hfid: ["fw1"]}` works, and `infrahubctl object load` works. Only the
SDK's string-shorthand path does not. Cycle 025 uses object files, so it is unaffected — but any
future generator creating a route on the firewall must pass an id or an explicit HFID.

## Gates

| Gate | Result |
| --- | --- |
| `uv run pytest tests/unit` | 1008 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 108 files formatted |
| `uv run yamllint schemas/ .infrahub.yml` | clean |
| `uv run mypy src/solution_arista_avd` | no issues in 8 source files |
| `uv run rumdl check …` | no issues in 35 files |

## Integration tests: documented exception

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–023. The
constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative is unusually strong here: every behavioural clause was demonstrated
against a running Infrahub *twice* — once in Phase 0 against a scratch copy, to decide whether the
approach worked at all, and again here against the real implementation.

## Deferred, with reasons

- **`schema.graphql` is not regenerated.** `infrahubctl graphql export-schema` has no `--branch`
  flag; it exports Infrahub `main`. Loading this cycle's schema into `main` to work around that is
  exactly what made cycle 023's Infrahub branch merge fail on a `SchemaAttribute` uniqueness
  violation. The file lags one cycle by choice. Regenerate after merge.
- **The `export-schema --branch` gap itself.** It has now cost two cycles. Worth either a
  branch-aware export or a convention that the schema load to `main` happens only at merge time.
- **`infrahubctl generator` cannot run any generator whose target members lack a `name`
  attribute.** Pre-existing SDK CLI limitation, unrelated to this cycle, but it means generator
  idempotence cannot be validated through the documented command here.
- **Five stale Infrahub branches**, one of which (`023-junos-config-render`) errors on every
  repository sync because its schema predates cycle 023's attributes.
