# Quickstart: Validating the WAN Addressing Schema

**Feature**: `specs/020-wan-addressing-schema` | **Date**: 2026-09-11

How to prove this cycle worked. Roughly ten minutes against a running stack, and the first two
sections need no stack at all.

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be ✅
```

If `schema check` returns `401 Unauthorized`, the CLI has no token. Export one from the
environment the stack was started with — `docker-compose.yml` names the variable
`INFRAHUB_INITIAL_ADMIN_TOKEN` and supplies a local-stack default:

```bash
export INFRAHUB_API_TOKEN="$INFRAHUB_INITIAL_ADMIN_TOKEN"
export INFRAHUB_ADDRESS="${INFRAHUB_ADDRESS:-$(uv run infrahubctl info | awk '/Address/{print $2}')}"
```

## 1. Offline checks

```bash
uv run pytest tests/unit/test_wan_schema_contract.py
uv run yamllint schemas/
```

The contract test is the gate that matters. It reads the YAML directly, so it passes or fails
without a server, and it is where the widened cardinality is pinned.

## 2. The diff is exactly four changes

```bash
uv run infrahubctl schema check schemas/
```

Expect every file `is Valid!`, then a diff matching
[contracts/schema-contract.md §6](./contracts/schema-contract.md) — four additions and one
removal, nothing else.

**Check the `removed:` line under `WanSite` specifically.** If `bgp_sessions` appears under
`added` but `bgp_session` does not appear under `removed`, the `state: absent` tombstone is
missing or malformed, and the old cardinality-one relationship will survive on the server with
no warning at all. That is the one failure this cycle can ship without noticing.

## 3. Load, and confirm against the live schema

```bash
uv run infrahubctl schema load schemas --branch main
```

Then read back what the server actually holds:

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" \
  "$INFRAHUB_ADDRESS/api/schema?branch=main" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for n in d['nodes']:
    k=(n['namespace'],n['name'])
    if k in {('Wan','Site'),('Wan','InternetPeering'),('Dcim','CircuitEndpoint'),('Dcim','Device')}:
        rels={r['name']:r['cardinality'] for r in n['relationships']}
        print(k, {x:rels[x] for x in rels if x in
              ('bgp_session','bgp_sessions','interface','router_id')})
"
```

Expected:

```text
('Dcim', 'CircuitEndpoint') {'interface': 'one'}
('Dcim', 'Device')          {'router_id': 'one'}
('Wan', 'Site')             {'bgp_sessions': 'many'}
('Wan', 'InternetPeering')  {'bgp_sessions': 'many'}
```

`bgp_session` must be **absent** from the `Wan/Site` line. If it is still there, the tombstone
did not take — see the fallback in [research.md R6](./research.md).

## 4. The existing seed still loads

The whole point of keeping every relationship optional:

```bash
uv run infrahubctl object load objects/
```

All four `WanSite` objects and both circuits load unchanged. A second run must also succeed —
these files are idempotent, and nothing in this cycle changes that.

## 5. Regenerate and type-check

```bash
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
uv run mypy --show-error-codes src/solution_arista_avd
```

`protocols.py` should show `bgp_sessions` as a many-cardinality relationship on `WanSite` and
`WanInternetPeering`, `router_id` on `DcimDevice`, and `interface` on `DcimCircuitEndpoint`.
The regenerated file is committed.

## 6. Full gates

```bash
uv run invoke test
uv run invoke lint
```

## 7. The real acceptance test — can the next cycle start?

SC-006 is the criterion that matters, and it is answered by hand rather than by a command.
Walk the six rendered configs and confirm every outstanding row is object data, with no row
left whose obstacle is schema:

```bash
ls ../lab/wan/rendered/*/frr.conf
```

For each of `isp-pe1`, `isp-pe2`, `internet-rtr`, `cust-acme-ce`, `cust-globex-ce` and
`branch-rtr`, every line must be traceable to somewhere it could come from:

| Config element | Destination after this cycle |
| --- | --- |
| `bgp router-id 10.50.0.1` | `DcimDevice.router_id` |
| `neighbor 10.51.10.2 remote-as 65010` | `WanSite.bgp_sessions` |
| `neighbor 10.52.0.2 remote-as 64500` | `WanInternetPeering.bgp_sessions` |
| interface addresses on both ends of a circuit | `DcimCircuitEndpoint.interface → ip_addresses` |
| `network 10.50.0.1/32` | a loopback-role interface's address |
| `router bgp 65500` | `DcimDevice.asn` *(already existed)* |
| `ip route 10.60.11.0/24 …` in `CUST_ACME` | `WanSite.static_routes` *(already existed)* |
| `PL-DC-SERVICES`, `PL-ACME-CLOUD`, `PL-DEFAULT` | derived from `ServiceL3vpn`, `ServiceTenantCloud`, `ServiceInternetAccess` *(already existed)* |

Every row resolves to a relationship that now exists. What remains is seeding objects into
them, which is the next cycle.

## Rollback

Nothing here is destructive, but if the load misbehaves:

```bash
git checkout schemas/ src/solution_arista_avd/protocols.py
rm -f schemas/circuit_extensions.yml
uv run infrahubctl schema load schemas --branch main
```

A relationship added by a load is not removed by reverting the file — that is R6's finding
applied to this cycle's own changes. Reverting cleanly needs the same `state: absent`
treatment, or a rebuild with `uv run invoke destroy && uv run invoke build && uv run invoke load`.
