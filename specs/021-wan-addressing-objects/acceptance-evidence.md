# Acceptance Evidence

**Feature**: `specs/021-wan-addressing-objects` | **Date**: 2026-09-11
**Branch**: `wan-obj` (Infrahub) / `021-wan-addressing-objects` (git)

## T006 — the oracle, parsed not read

`../lab/wan/tenants.yml` yields exactly what the plan predicted:

```text
mtu 9214 | interfaces 20 | addresses 20 | asns 5 | sessions 10 | router_ids 6 | static 1
```

## T007 — before-counts on `wan-obj`

```text
InterfacePhysical      143     RoutingAsn               4
InterfaceVirtual        14     RoutingBGPNeighbor      44
IpamIPAddress           54     RoutingVrfStaticRoute    9
IpamVRF                  8
```

The fabric already holds 44 BGP neighbours and 9 static routes, so **only deltas are
meaningful**. The task text's "exactly 10" and "exactly 1" were absolute counts and would have
been read wrongly without this baseline.

## T008 — the filename sorts where the design requires

```text
['31_nfd41_offfabric_devices.yml', '31a_nfd41_wan_addressing.yml',
 '32_nfd41_security.yml', '33_nfd41_wan.yml', '37_nfd41_wan_services.yml']
```

Pinned by `test_the_addressing_file_sorts_between_the_devices_and_the_circuits`.

## T036 — post-load deltas, all matching the oracle

```text
OK  InterfacePhysical      143 -> 160  delta +17 (want +17)
OK  InterfaceVirtual        14 ->  17  delta  +3 (want  +3)
OK  IpamIPAddress           54 ->  74  delta +20 (want +20)
OK  RoutingAsn               4 ->   9  delta  +5 (want  +5)
OK  RoutingBGPNeighbor      44 ->  54  delta +10 (want +10)
OK  RoutingVrfStaticRoute    9 ->  10  delta  +1 (want  +1)
OK  IpamVRF                  8 ->   8  delta  +0 (want  +0)
```

`IpamVRF` is unchanged because the two `CUST_*` VRFs moved between files rather than being
created — which is also the assertion that the move left no copy behind.

## T037 — the debt repaid: all eight circuit ends resolve

```text
acme-dr          side a -> eth4  ['10.51.11.1/30']
acme-dr          side z -> eth1  ['10.51.11.2/30']
acme-hq          side a -> eth2  ['10.51.10.1/30']
acme-hq          side z -> eth1  ['10.51.10.2/30']
globex-hq        side a -> eth3  ['10.51.20.1/30']
globex-hq        side z -> eth1  ['10.51.20.2/30']
isp-to-internet  side a -> eth3  ['10.52.0.1/30']
isp-to-internet  side z -> eth1  ['10.52.0.2/30']
```

`circuit → endpoint → interface → ip_addresses` resolves for every end. The addresses that
lived in description prose are objects.

## T038 — sessions, static route and router IDs

```text
acme  /dr       static  sessions=0  static=['10.60.11.0/24']
acme  /hq       bgp     sessions=2  [('10.51.10.1','65500'), ('10.51.10.2','65010')]
branch/office   bgp     sessions=1  [('10.250.70.1','65103')]
globex/hq       bgp     sessions=2  [('10.51.20.1','65500'), ('10.51.20.2','65020')]
peering isp-to-internet sessions=2  [('10.52.0.1','65500'), ('10.52.0.2','64500')]
```

**branch/office has one session, not two** — the spec and quickstart both said "three sites
with two sessions each". The far end is `border-leaf1`, a fabric device already modelled in
`objects/27_nfd41_vrf_services.yml`, so only the branch side belongs to the WAN. Corrected in
the test rather than forced into the data.

```text
OK  branch-rtr        router_id=10.70.255.1/32   asn=65030
OK  cust-acme-ce      router_id=10.60.10.1/24    asn=65010
OK  cust-acme-dr-ce   router_id=None             asn=None
OK  cust-globex-ce    router_id=10.60.20.1/24    asn=65020
OK  internet-rtr      router_id=10.52.0.2/30     asn=64500
OK  isp-pe1           router_id=10.50.0.1/32     asn=65500
OK  isp-pe2           router_id=10.50.0.2/32     asn=65500
```

Three of six router IDs are not loopbacks, which is why the relationship is explicit.

## T039 — idempotence, proved by counts not by the log

A second `object load objects/ --branch wan-obj` produced no error, and every count was
unchanged:

```text
InterfacePhysical 160 | InterfaceVirtual 17 | IpamIPAddress 74 | RoutingAsn 9
RoutingBGPNeighbor 54 | RoutingVrfStaticRoute 10 | IpamVRF 8
DcimCircuitEndpoint 8 | WanSite 4
```

The CLI prints "Created node" for an upsert, so the log is not evidence. The counts are.

## T040 — no address survives as prose

No `description:` in any object file contains an IPv4 address. The only textual match left in
the repository is inside a comment in `objects/31a_nfd41_wan_addressing.yml` quoting the old
form to explain why it was removed. Guarded by
`test_no_endpoint_description_restates_an_address`.

## Two corrections this cycle made to its own record

**R7 was wrong and is retracted.** Phase 0 claimed `RoutingVrfStaticRoute` has a weaker HFID
than its uniqueness constraint, drawing a parallel to the `SecurityPolicyRule` defect. The claim
came from a `grep -A` that truncated the list at its first element. The real HFID is
`['vrf__name__value', 'prefix__value', 'next_hop__value']` and matches the constraint exactly.

What the reference actually needs is all three elements **with the next hop in its normalised
form**:

```yaml
static_routes:
  - ["CUST_ACME", "10.60.11.0/24", "10.51.11.2/32"]
```

`next_hop` is an `IPHost` attribute, stored as `/32` even when written without it. The load
failed twice — first "HFID does not contain the same number of elements", then "Unable to find
the node" — two messages for one under-specified reference.

This is the second time in two cycles that a truncated `grep` produced a confident wrong claim
about a schema; cycle 020's R1 made the same mistake about `DcimInterface.role`. Query the live
schema or read the whole block.

## A cycle-019 transcription error, found by the SC-009 walk

`ServiceL3vpn.dc_service_prefixes` was seeded with each tenant's own cloud subnet —
`10.220.10.0/24` for acme, `10.220.20.0/24` for globex. The lab's value is a single shared
range, `10.112.240.0/24`, described in its own comment as "what EVERY tenant may reach in the
datacentre, regardless of what they buy". It is the same for both tenants, and the per-tenant
cloud subnet is a different concept that already lives on `ServiceTenantCloud.prefix`.

Rendered, this would put the wrong network in isp-pe1's `PL-DC-SERVICES` and duplicate the
cloud subnet into the shared policy. Corrected in `objects/37_nfd41_wan_services.yml` and
guarded by `test_dc_service_prefixes_are_the_shared_range_not_a_tenant_subnet`.

It is fixed here rather than deferred because a presence check passes on a wrong value; SC-009
only means something if the data is right, and the next cycle renders from it.

## T046 — SC-009: can the transform cycle start?

Every element of the rendered configs resolves to data now in the graph:

```text
OK  router bgp 65010                     <- cust-acme-ce.asn                    65010
OK  bgp router-id 10.60.10.1             <- cust-acme-ce.router_id              10.60.10.1/24
OK  neighbor 10.51.10.1 remote-as 65500  <- WanSite acme/hq bgp_sessions (CE)   ('10.51.10.1','65500')
OK  network 10.60.10.0/24                <- WanSite acme/hq lan_prefix          10.60.10.0/24
OK  router bgp 65500 (isp-pe1)           <- isp-pe1.asn                         65500
OK  bgp router-id 10.50.0.1 (isp-pe1)    <- isp-pe1.router_id                   10.50.0.1/32
OK  PL-DC-SERVICES                       <- ServiceL3vpn.dc_service_prefixes    ['10.112.240.0/24']
OK  PL-ACME-CLOUD                        <- ServiceTenantCloud.prefix           ['10.220.10.0/24', ...]
OK  PL-DEFAULT (acme buys internet)      <- ServiceInternetAccess exists        ['acme-internet']
```

**Nothing is blocked on data any more.** The FRR transform cycle can start.

## T044 — gates

```text
uv run pytest tests/unit                939 passed
  of which test_wan_addressing_objects.py: 27 passed
uv run ruff check .                     All checks passed
uv run ruff format --check .            102 files already formatted
uv run yamllint objects/ schemas/       clean
uv run mypy src/solution_arista_avd     Success
uv run rumdl check README AGENTS docs/  no issues in 31 files
```

## T045 — integration tests: documented exception

`$infrahub-run-integration-tests` is not installed in this environment, as in cycle 020. The
constitution's escape clause applies and **the pull request must say so explicitly**.

The non-live alternative actually executed is stronger here than in 020, because this cycle has
data to check:

- schema and objects loaded into a fresh branch (T035)
- post-load deltas compared against a captured baseline (T036)
- all four traversal queries run against the live graph (T037, T038)
- every object file loaded a second time with counts unchanged (T039)
- the SC-009 walk resolved against live data (T046)
