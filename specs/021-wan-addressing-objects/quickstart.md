# Quickstart: Validating the WAN's Addressing

**Feature**: `specs/021-wan-addressing-objects` | **Date**: 2026-09-11

How to prove this cycle worked. The first section needs no stack.

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be ✅
export INFRAHUB_API_TOKEN="$INFRAHUB_INITIAL_ADMIN_TOKEN"
export INFRAHUB_ADDRESS="${INFRAHUB_ADDRESS:-$(uv run infrahubctl info | awk '/Address/{print $2}')}"
```

**Use a fresh Infrahub branch.** `wan-addr` carries partial probe data from cycle 021's Phase 0
research and must not be merged — see [research.md](./research.md), open risk 1.

```bash
uv run infrahubctl branch create wan-obj --sync-with-git
uv run infrahubctl schema load schemas --branch wan-obj
```

The schema load is required: this cycle depends on cycle 020's four relationships, which are not
on `main` until 020 is merged.

## 1. Offline checks

```bash
uv run pytest tests/unit/test_wan_addressing_objects.py
uv run yamllint objects/
```

The transcription test is the real gate. It compares both directions against
`../lab/wan/tenants.yml`, so a value invented in the object files fails just as loudly as one
omitted from them.

## 2. Load, in order

```bash
uv run infrahubctl object load objects/ --branch wan-obj
```

Watch for two specific failures, because neither names the field that caused it:

| Symptom | Cause |
| --- | --- |
| `AttributeError: 'list' object has no attribute 'items'` | a dash under a cardinality-one inline `data:` block — it must be a mapping |
| `Unable to lookup node by HFID, schema 'InterfaceLayer3' does not have a HFID defined` | an address referencing its interface by HFID instead of an inline concrete-kind block |

A third, `Unable to find the node X :: Y`, means the form was right but load order is wrong —
check that `31a` still sorts before `33`.

## 3. The counts

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"query { InterfacePhysical{count} InterfaceVirtual{count} IpamIPAddress{count} RoutingAsn{count} RoutingBGPNeighbor{count} RoutingVrfStaticRoute{count} }"}' \
  "$INFRAHUB_ADDRESS/graphql/wan-obj" | python3 -m json.tool
```

`RoutingBGPNeighbor` must be exactly 10 and `RoutingVrfStaticRoute` exactly 1. The interface and
address counts include the fabric's existing objects, so compare them to a baseline taken before
the load rather than to 20.

## 4. The traversals

This is the check that matters — it is what the transform cycle will do:

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"query { DcimCircuit{edges{node{circuit_id{value} endpoints{edges{node{side{value} interface{node{name{value} ...on InterfaceLayer3{ip_addresses{edges{node{address{value}}}}}}}}}}}}} }"}' \
  "$INFRAHUB_ADDRESS/graphql/wan-obj" | python3 -m json.tool
```

All four circuits, both sides each, must return an interface and an address. A `null` interface
means an endpoint link was missed.

Note the `... on InterfaceLayer3` fragment: `ip_addresses` is not selectable on the
`DcimInterface` generic. Without it the query is rejected outright.

Then the sessions and router IDs:

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"query { WanSite{edges{node{name{value} tenant{node{name{value}}} attachment_kind{value} bgp_sessions{edges{node{peer_address{value} remote_as{value}}}} static_routes{edges{node{prefix{value} next_hop{value}}}}}}} DcimDevice{edges{node{name{value} router_id{node{address{value}}} asn{node{asn{value}}}}}} }"}' \
  "$INFRAHUB_ADDRESS/graphql/wan-obj" | python3 -m json.tool
```

Expected: three sites with two sessions each, acme/dr with zero sessions and one static route,
six routers with a router ID and an ASN, and `cust-acme-dr-ce` with neither.

## 5. Idempotence

```bash
uv run infrahubctl object load objects/ --branch wan-obj   # second run
```

Then re-run the count query from §3. **The log is not evidence** — `infrahubctl` prints
"Created node" for an upsert too. Only the counts prove it.

## 6. The prose is gone

```bash
grep -nE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' objects/33_nfd41_wan.yml
```

Should return nothing. Any hit is an address that still lives in two places.

## 7. Gates

```bash
uv run invoke test
uv run invoke lint
```

## 8. The real acceptance test — can the transform cycle start?

SC-009 asks whether every line of the six rendered FRR configs has its data in the graph. Walk
one config end to end and find each element:

```bash
grep -v '^ *!' ../lab/wan/rendered/cust-acme-ce/frr.conf | grep -v '^$'
```

| Line | Where it now comes from |
| --- | --- |
| `router bgp 65010` | `cust-acme-ce.asn` |
| `bgp router-id 10.60.10.1` | `cust-acme-ce.router_id` |
| `neighbor 10.51.10.1 remote-as 65500` | the site's CE-side session |
| `network 10.60.10.0/24` | `WanSite.lan_prefix` *(already present)* |
| `PL-OUR-LAN permit 10.60.10.0/24` | the same prefix |

Then `isp-pe1`, which is the hard one — its per-tenant route-maps come from the service layer
(`ServiceL3vpn.dc_service_prefixes`, `ServiceTenantCloud.prefix`, the presence or absence of a
`ServiceInternetAccess`), all of which cycle 019 already seeded.

Nothing should be missing. If something is, it is a transcription gap in this cycle, not a
schema gap — cycle 020 closed those.

## Rollback

```bash
git checkout objects/
uv run infrahubctl branch delete wan-obj
```

Object data lives only in the branch, so deleting it discards everything this cycle loaded.
