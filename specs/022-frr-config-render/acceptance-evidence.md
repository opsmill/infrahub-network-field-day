# Acceptance Evidence

**Feature**: `specs/022-frr-config-render` | **Date**: 2026-09-11
**Branch**: `wan-render` / `no-internet` (Infrahub) / `022-frr-config-render` (git)

## SC-001, SC-002 — all six devices, byte for byte

Rendered from captured fixtures and compared to `../lab/wan/rendered/<device>/frr.conf`, with
only the provenance line normalised:

```text
ZERO DIFF   isp-pe1          158 lines rendered
ZERO DIFF   isp-pe2          107 lines rendered
ZERO DIFF   internet-rtr      60 lines rendered
ZERO DIFF   cust-acme-ce      42 lines rendered
ZERO DIFF   cust-globex-ce    42 lines rendered
ZERO DIFF   branch-rtr        33 lines rendered

total differing lines across all six: 0
```

Whitespace, blank comment lines, clause order and every explanatory comment included.

`transform()` output is byte-identical to the golden file after the provenance swap — 1413
bytes against 1418, the difference being exactly the length of `wan/render.py` versus
`Infrahub`. `infrahubctl transform` adds one newline when printing to stdout, which is why the
CLI comparison shows one extra line and the unit test is the authoritative check.

## SC-003 — the service layer is visible, measured live

Deleting acme's `ServiceInternetAccess` on a throwaway branch and re-rendering `isp-pe1`:

```diff
-route-map RM-ACME-IMPORT permit 30
- description acme buys internet access
- match ip address prefix-list PL-DEFAULT
-!
-! ==== tenant acme (VRF CUST_ACME, internet: yes) ====
+! ==== tenant acme (VRF CUST_ACME, internet: no) ====
```

**Six lines, and nothing else moves.** One service object deleted, and a real router's import
policy *and* the human-readable summary above it both change. This is what every cycle since
010 has been arguing for.

`PL-DEFAULT` survives, as predicted — it is guarded by the ISP having an internet connection,
not by any tenant buying access.

The spec's line count was wrong twice before this measurement: written as three, corrected to
four by reading the template's `{% if t.internet %}` guard, and finally six by rendering it both
ways. The fourth line is the `!` inside the guard; the fifth and sixth are the tenant header.

## SC-004 — one template, two customer edges

`cust-acme-ce` and `cust-globex-ce` both render from `customer-ce.j2`, differing only in their
tenants' values. Asserted by both golden-file tests passing against one template.

## SC-005 — a missing value fails loudly

Two guards, both asserted:

- An absent `router_id` fails in the **generated query model** before the transform runs —
  stronger than expected, and worth knowing.
- A present-but-unresolved `router_id` raises `FrrConfigError`, the shape a device with no
  router id actually produces.

`StrictUndefined` earned its place during Phase 0, catching two real context gaps at named
template lines. Both would otherwise have rendered a config with a missing BGP neighbour, which
vtysh accepts and which never comes up.

## SC-006 — six artifacts, not seven

```text
frr_routers members: 6
  branch-rtr  cust-acme-ce  cust-globex-ce  internet-rtr  isp-pe1  isp-pe2
cust-acme-dr-ce excluded: True
```

`cust-acme-dr-ce` shares the `customer_edge` role, so a role-derived group would have captured
it and produced a seventh artifact for a device the lab renders no FRR config for. Membership
is explicit for exactly that reason.

Registration verified name by name — a mismatch between `transformation`, the
`python_transforms` name and the class's `query` attribute fails silently:

```text
query registered:        True
transform registered:    FrrConfig
class query attr:        frr_config == registered query: True
artifact transformation: frr_config == transform name: True
targets: frr_routers | content_type: text/plain
```

## SC-007 — nothing hardcoded but FRR's own syntax

Every address, AS number, prefix, VRF name and device name in all six outputs comes from the
graph. The two literals in the transform are `ROLE_TO_TEMPLATE` (a role-to-filename map) and
`TENANT_ORDER`, which exists because Infrahub stores no authoring order.

## SC-008 — gates

```text
uv run pytest tests/unit                960 passed
  of which test_frr_config.py:           21 passed
uv run ruff check .                     All checks passed
uv run ruff format --check .            104 files already formatted
uv run yamllint objects/ schemas/ .infrahub.yml menus/   clean
uv run mypy src/solution_arista_avd     Success
uv run rumdl check AGENTS.md docs/      no issues
```

Three ruff findings in this cycle's own code were fixed rather than suppressed: a blind
`pytest.raises(Exception)` narrowed to `FrrConfigError`, a missing `maxsplit`, and
`autoescape=False` justified in a comment (escaping a router config would corrupt it) with a
targeted `noqa`.

**Pre-existing, not introduced here**: `uv run yamllint .` reports 686 errors, every one inside
`.claude/worktrees/agent-a7e2fddc3b0b7c881/` — a stray agent worktree holding a full copy of the
repository including its `.venv`. It is untracked and unrelated to this cycle, but it means
`invoke lint-yaml` fails on a clean checkout until someone removes it.

## Findings recorded during implementation

**The exported GraphQL schema was badly stale.** `schema.graphql` was 3.9 MB and predated cycle
010 — it knew nothing of `ServiceInternetAccess` or `WanInternetPeering`, so
`generate-return-types` rejected the query. Re-exporting produced 5.4 MB. It also exports from
Infrahub's `main` branch only, with no `--branch` option, which meant loading cycles 020 and
021's schema into `main` before the typed models could be generated at all. That load was
outstanding from cycle 020 and is now done.

**The return-type generator names its output from the operation name, not the filename.**
`query FrrConfig(...)` produced `frr_config.py` — which would have collided with the transform
module. Renaming the operation to `FrrConfigQuery` produced `frr_config_query.py`, which is why
the repository's existing pairs look the way they do.

**An inline fragment must name the concrete kind for the typed model, not just for GraphQL.**
Cycle 020 recorded that `ip_addresses` needs `... on InterfaceLayer3`. Going the other way,
`... on DcimInterface` is accepted by the server but the generated Pydantic model discriminates
on `__typename` — which is `InterfacePhysical` or `InterfaceVirtual`, never `DcimInterface` — so
the typed result silently fell back to a variant with no `device` field. The fragment must name
both concrete kinds, and `__typename` must be selected at every nested union point, which is
cycle 016's finding applying one level deeper than before.

**The generated field names are not the GraphQL names.** `IpamIPAddress` becomes
`ipam_ip_address`, `ServiceL3vpn` becomes `service_l_3_vpn`, and `l3vpn` becomes `l_3_vpn` —
the generator splits on digits.

**An Infrahub branch forks `main`, not the branch you were working on.** The `no-internet`
branch for the SC-003 demonstration came up with the schema but no object data, because `main`
had none. The live demonstration needed `object load` into that branch first.

## SC-009 — is the lab's renderer redundant?

Every line of all six rendered configs is now produced from Infrahub. What remains in
`../lab/wan/tenants.yml` that the graph does not hold:

- the end-host entries — their device objects do not exist (cycle 021, assumption 2)
- the branch router's three bridged access ports — plumbing, no addresses (assumption 3)
- `mtu`, which is on every interface object

Nothing that drives a routing decision. The lab could delete `render.py`, `templates/` and
`tenants.yml` and lose nothing this repository does not now hold, **which is what "contain all
of the information that is in the lab" meant for the WAN.**

## Integration tests: documented exception

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020 and
021. The constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative here is the strongest of the three cycles, because the output is
comparable against something this repository did not write:

- all six devices rendered live against `wan-render` and diffed against the lab
- the artifact definition's group verified at six members with the seventh device excluded
- the SC-003 demonstration run live on a separate branch, with a real service object deleted
- registration name-matching verified programmatically
