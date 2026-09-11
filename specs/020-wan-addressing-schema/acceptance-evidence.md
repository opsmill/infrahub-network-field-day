# Acceptance Evidence

**Feature**: `specs/020-wan-addressing-schema` | **Date**: 2026-09-11
**Branch**: `wan-addr` (Infrahub) / `020-wan-addressing-schema` (git)

## T005 — R1 re-confirmed before scoping US3

`schemas/dcim_extensions.yml` already carries both loopback roles, so FR-020 and FR-021 stay
withdrawn and the cycle is four changes, not five:

```text
185:            - name: loopback
187:            - name: vtep_loopback
```

## T006 — the before-state

Captured before any schema file was edited. This is the baseline the tombstone's effect is
measured against; once loaded, the failure it guards cannot be observed.

```text
=== branch: main ===
DcimDevice           {}
DcimCircuitEndpoint  {}
WanSite              {'bgp_session': 'one'}
WanInternetPeering   {}

=== branch: wan-addr ===
DcimDevice           {}
DcimCircuitEndpoint  {}
WanSite              {'bgp_session': 'one'}
WanInternetPeering   {}
```

## T007 — adopted circuit schema baseline

```text
1e4ba7a35df71a40e91b3600ca6fc975b4de78e7  Model the full NFD41 lab in a technical and a service layer
```

SC-009 is checked as "unchanged since this commit".

## T025, T026 — the `schema check` diff is exactly four changes

```text
changed:
    DcimCircuitEndpoint:  relationships added: {interface}
    DcimDevice:           relationships added: {router_id}
    WanInternetPeering:   relationships added: {bgp_sessions}
    WanSite:              relationships added: {bgp_sessions}
                          relationships removed: {bgp_session}
```

Nothing else appears. The `removed` line is the one that matters: it is what proves the
`state: absent` tombstone took. Without it the rename reports as a pure addition and the old
cardinality-one relationship survives on the server with no warning (research R6).

## T027, T028 — loaded, and the after-state

`uv run infrahubctl schema load schemas --branch wan-addr` — 38 schemas processed in 19.4s, no
error. This was the first time `state: absent` was **loaded** rather than checked; it was
accepted, so R6's fallback was not needed.

```text
DcimCircuitEndpoint  {'interface': 'one'}
DcimDevice           {'router_id': 'one'}
WanInternetPeering   {'bgp_sessions': 'many'}
WanSite              {'bgp_sessions': 'many'}
```

`bgp_session` is **gone** from `WanSite`, against the before-state above. The tombstone works
end to end, not only in `check`.

## T029 — the existing seed still loads, twice

Two consecutive `object load objects/ --branch wan-addr` runs, then a count query. The CLI logs
"Created node" on both runs — that is its wording for an upsert, so the counts are the actual
evidence:

```text
WanSite 4 | WanInternetPeering 1 | ServiceL3vpn 2 | DcimCircuit 4 | DcimCircuitEndpoint 8 | IpamVRF 8
```

No duplicates. Keeping all four relationships optional did what it was for (FR-041, SC-002).

## T030, T031 — protocols regenerated, type check clean

`protocols.py` gained `bgp_sessions` on both `WanSite` and `WanInternetPeering`.
`uv run mypy --show-error-codes src/solution_arista_avd` — Success, no issues in 8 source files.

**Two findings recorded rather than papered over** (research R10, R11):

1. The generator does not honour `state: absent`, so `protocols.py` still carries
   `WanSite.bgp_session` although the server no longer has it. Bounded: nothing references it
   (grep confirms), the contract test pins `bgp_sessions` as the real one, and the phantom
   disappears with the tombstone at the next rebuild.
2. `infrahubctl protocols --schemas` reflects **no** `extensions:` block at all, so neither
   `router_id` nor `interface` appears — and neither do `loopback_ip`, `mgmt_ip` or `asn`,
   which have been extension fields for many cycles. Pre-existing, repository-wide, and worth
   its own cycle.

## T032 — the adopted circuit schema is untouched

`git diff --stat schemas/circuit/circuit.yml` is empty (SC-009).

## T039 — SC-006: can the next cycle start?

Every element of the six rendered FRR configs now resolves to a relationship that exists,
checked against the live schema on `wan-addr`:

```text
OK  bgp router-id 10.50.0.1              -> DcimDevice.router_id          (IpamIPAddress, one)
OK  neighbor 10.51.10.2 remote-as 65010  -> WanSite.bgp_sessions          (RoutingBGPNeighbor, many)
OK  neighbor 10.52.0.2 remote-as 64500   -> WanInternetPeering.bgp_sessions (RoutingBGPNeighbor, many)
OK  circuit end -> interface -> address  -> DcimCircuitEndpoint.interface (DcimInterface, one)
OK  router bgp 65500                     -> DcimDevice.asn                (RoutingAsn, one)
OK  ip route 10.60.11.0/24 (CUST_ACME)   -> WanSite.static_routes         (RoutingVrfStaticRoute, many)
OK  PL-DC-SERVICES                       -> ServiceL3vpn.dc_service_prefixes
OK  PL-ACME-CLOUD                        -> ServiceTenantCloud.prefix
OK  PL-DEFAULT (buys internet)           -> ServiceInternetAccess.l3vpn
```

Both new traversals were also exercised as live GraphQL against `wan-addr` and accepted;
the interface relationships return `None` because the objects are the next cycle's work.

**No remaining row is blocked on schema.** Everything outstanding is object data, which is
what SC-006 asks.

One consequence for that next cycle, found by running the query rather than reading the
schema: because the peer is the `DcimInterface` generic, `ip_addresses` needs an inline
fragment (`... on InterfaceLayer3`). The plain form is rejected. Recorded in
[contracts/schema-contract.md](./contracts/schema-contract.md) §5.

## T037 — gates

```text
uv run pytest tests/unit          912 passed
  of which test_wan_schema_contract.py: 29 passed (21 existing + 8 new)
uv run ruff check .               All checks passed
uv run ruff format --check .      101 files already formatted
uv run yamllint schemas/          clean
uv run rumdl check <authored md>  no issues
uv run mypy src/solution_arista_avd  Success
```

## T038 — integration tests: documented exception

`$infrahub-run-integration-tests` is **not installed in this environment** — `.agents/skills/`
contains the six `infrahub-managing-*` skills and no validation skills. The constitution's
escape clause applies: "If a validation skill or project safety rule prohibits a live
validation scenario, the change MUST include an approved alternative validation plan and
document why live validation was not run."

**A partial local run was attempted and deliberately stopped.** `uv run invoke test` runs
`pytest tests`, which includes the testcontainers-backed integration suite. It collected 943
items and got through:

```text
tests/integration/test_avd_transforms.py    ........  (8 passed)
tests/integration/test_bgp_asn_schema.py    ..        (2 passed)
tests/integration/test_device_design_schema.py   <stopped here>
```

It was killed during the third file after ten minutes of container startup, because AGENTS.md
restricts local integration runs to "ad-hoc local/lab debugging when explicitly appropriate"
and it was competing with the running stack. **The suite therefore did not complete, and no
claim is made that it passed** — 10 of 31 integration tests ran and passed; the rest did not
run. The job's shell exit code of 0 is an artifact of the kill combined with a `tail` pipe, not
a result.

The non-live alternative actually executed, as planned in [plan.md](./plan.md):

- schema loaded to a real branch against a real server (T027)
- live schema read back and compared to the before-state (T006, T028)
- every object file re-loaded twice with counts verified (T029)
- both new traversals exercised as live GraphQL (T039)

This change has no runtime behaviour — no generator runs, no transform renders, no object is
created or mutated by it — so the generator-chain and transform coverage the suite provides has
nothing to exercise here. **This must be stated in the pull request rather than omitted.**
