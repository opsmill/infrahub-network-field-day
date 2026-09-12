# Phase 0 Research: FRR Configuration for the WAN

**Feature**: `022-frr-config-render` | **Date**: 2026-09-11

Phase 0 did not research this cycle — it **rendered** it. The lab's templates were driven from
the live Infrahub graph on branch `wan-obj` and diffed against the golden files, which answers
the only question that mattered: does the model hold enough to reproduce the oracle?

It does. `cust-acme-ce`, `cust-globex-ce` and `isp-pe1` all render **zero diff** from live data
using the lab's templates unmodified. The cycle is a port, not a design.

## R1 — The port works, and it was proved rather than argued

**Decision**: port the lab's five templates unchanged in content; build the context in Python.

**Evidence**: a probe assembled each device's context from GraphQL against `wan-obj`, rendered
`../lab/wan/templates/*.frr.conf.j2` unmodified, and compared to
`../lab/wan/rendered/<device>/frr.conf` with only the provenance line normalised:

```text
ZERO DIFF  cust-acme-ce
ZERO DIFF  cust-globex-ce
ZERO DIFF  isp-pe1          (159 lines, both tenant VRFs, both import route-maps)
```

`isp-pe1` is the one that mattered. It is the largest config, the only one where the service
layer materialises, and it came out byte-identical. US2 — the story carrying 271 of the 409
template lines and all of the risk — is de-risked before implementation starts.

**What this means for the plan**: the remaining work is the Infrahub plumbing (query, transform
class, artifact definition, target group, tests), not the rendering. Three devices are still
unproven — `isp-pe2`, `internet-rtr`, `branch-rtr` — and their templates are simpler than
`isp-pe1`'s.

## R2 — `StrictUndefined` earns its place immediately

**Decision**: use `StrictUndefined`, as the lab does.

**Rationale**: it caught two real context gaps during the probe, each as a named error at the
exact template line:

```text
UndefinedError: 'dict object' has no attribute 'core'   <- isp-edge.frr.conf.j2 line 97
UndefinedError: 'dict object' has no attribute 'node'   <- isp-edge.frr.conf.j2 line 115
```

The lab's own renderer explains why in a comment: *"a typo in the data model must fail the
render, not silently emit a config with a blank where an IP should be. A BGP neighbor line with
an empty address is accepted by vtysh and never comes up."* Both gaps would have produced
plausible-looking configs with missing neighbours. This is FR-013 and FR-022, and it is not
optional.

## R3 — The iBGP session hangs off the device, not off a site

**Decision**: fetch `RoutingBGPNeighbor` for the target device directly, not only through
`WanSite.bgp_sessions`.

**Rationale**: the first `StrictUndefined` failure was `isp.edge.core.peer` — the iBGP session
between `isp-pe1` and `isp-pe2`. It is provider infrastructure, not a tenant attachment, so no
`WanSite` names it. Cycle 021 seeded it on the device, correctly. The same is true of the DC
handoff toward `border-leaf1`.

So the query needs both paths: sessions reached from a site (the tenant attachments) and
sessions reached from the device (everything else). Three of the ten neighbours are
device-only.

## R4 — A static site's CE is found through the route's next hop

**Decision**: resolve it by matching the static route's next hop against interface addresses.

**Rationale**: the second `StrictUndefined` failure was `site.ce.node` for acme's DR site. A
static attachment has no BGP session, so the CE device is not reachable the way a BGP site's is.
The static route's `next_hop` **is** the CE's WAN address, and cycle 021 attached every address
to its interface, so `address → interface → device` resolves it.

This is a small vindication of cycle 020's `DcimCircuitEndpoint.interface` work: the same
traversal serves a purpose nobody anticipated when it was specified.

**Alternative considered**: reading the CE from the site's circuit's Z-side endpoint. Equally
valid and arguably more direct. Rejected only because the next-hop path needs no circuit, and
the branch site has no circuit at all — one rule covering both is better than two.

## R5 — Querying *from* an address needs the inline fragment too

**Decision**: select `... on DcimInterface` when traversing `IpamIPAddress.interface`.

**Rationale**: the mirror of cycle 020's finding, and it fails just as bluntly:

```text
Cannot query field 'name' on type 'InterfaceLayer3'. Did you mean to use an inline
fragment on 'DcimInterface', 'GenericInterfaceBundle', 'InterfaceLag', ...
```

Cycle 020 recorded that `ip_addresses` needs a fragment when going *interface → address*. The
reverse direction needs one as well, because `IpamIPAddress.interface` peers with
`InterfaceLayer3` and `name` lives on `DcimInterface`. Both directions, both fragments. This is
FR-005, widened.

## R6 — Site ordering has to be a rule, because the lab's order is authoring order

**Decision**: order a tenant's sites **BGP attachments first, then static, each by name**.

**Rationale**: the `isp-pe1` diff came down to two lines, and both were ordering:

```diff
  ! ==== tenant acme (VRF CUST_ACME, internet: yes) ====
+ !   site dr: 10.60.11.0/24 via cust-acme-dr-ce (static)
  !   site hq: 10.60.10.0/24 via cust-acme-ce (bgp, AS 65010)
- !   site dr: 10.60.11.0/24 via cust-acme-dr-ce (static)
```

`tenants.yml` lists acme's sites in the order they were written — hq, then dr — and Infrahub has
no notion of authoring order. Alphabetical gives dr first.

The chosen rule reproduces the oracle and is not an arbitrary fudge: the template itself reads
the two kinds in separate loops (`for site in t.sites if site.kind == 'bgp'` and the static
equivalent), so grouping by attachment kind is how the configuration is already organised. With
the rule applied, `isp-pe1` is zero diff.

**Alternatives considered**:

- *An explicit `order` attribute on `WanSite`.* The most robust answer, and a schema change —
  out of scope, and overkill for four sites.
- *Accept the difference.* Rejected: FR-021 requires the comments to match, and the comment
  block is a per-tenant site inventory. A reader comparing it to the lab would see a diff.

## R7 — SC-003's line count, corrected twice, and only right once it was run

**Finding**: removing acme's `ServiceInternetAccess` changes **six** lines of `isp-pe1`.

Measured by rendering both ways:

```diff
-route-map RM-ACME-IMPORT permit 30
- description acme buys internet access
- match ip address prefix-list PL-DEFAULT
-!
-! ==== tenant acme (VRF CUST_ACME, internet: yes) ====
+! ==== tenant acme (VRF CUST_ACME, internet: no) ====
```

Five removed, one added. The spec said "three lines" when written, was corrected to "four" after
reading the template's `{% if t.internet %}` guard, and is only correct now because the render
was run both ways. The fourth line is the `!` separator inside the guard; the fifth and sixth are
the tenant header comment, which re-renders with `internet: no`.

That header flip is worth more than the line count: the presence of one service object changes
not just the routing policy but the human-readable summary above it. `PL-DEFAULT` stays put, as
predicted — it is guarded by the ISP having an internet connection, not by a tenant buying one.

**Method note.** This is the third finding in three cycles where reading a file produced a
confident wrong number that running it corrected. Cycle 020's R1 and cycle 021's R7 were the
others. For anything countable, render it.

## R8 — Typed access comes from the generated query model, not from protocols

**Decision**: use the generated `*_query.py` Pydantic model, following `avd_eos_config.py`.

**Rationale**: `transforms/avd_eos_config.py` does exactly this — `data: AvdDeviceConfigQuery =
AvdDeviceConfigQuery(**data)` — so the house pattern already exists and Constitution III is
satisfied without `protocols.py`.

This matters because `protocols.py` is missing every extension relationship, including
`DcimDevice.router_id`, which this transform needs (cycle 021's R11). The GraphQL return types
are generated from the live schema and are complete, so the gap does not block this cycle. It
remains worth fixing on its own.

## R9 — The target group, and the seventh artifact that must not exist

**Decision**: add a `CoreStandardGroup` to `objects/00_groups.yml` with the six FRR routers.

**Rationale**: an artifact definition targets a group, and no group covers these devices —
`objects/00_groups.yml` holds eleven, all fabric or service oriented. Cycle 017 set the
precedent by adding `service_fabric_apps` in a transform cycle for the same reason.

`cust-acme-dr-ce` must be excluded. It has `role: customer_edge` like the two BGP CEs, so a
role-derived group would capture it and produce a seventh artifact for a device the lab renders
no FRR config for. Membership is explicit for exactly this reason, and SC-006 asserts the count.

`DcimDevice` already inherits `CoreArtifactTarget`, so no schema change is needed.

## Open risks carried to implementation

1. **Three devices are still unrendered.** `isp-pe2` (108 lines), `internet-rtr` (61) and
   `branch-rtr` (34) were not probed. Their templates are simpler than `isp-pe1`'s and the
   context they need is a subset plus the DC handoff, but "simpler" is not "verified".
2. **Cycle 021 is uncommitted.** Its object data lives on git branch
   `021-wan-addressing-objects` and Infrahub branch `wan-obj`. This cycle renders from it and
   cannot start until it is committed.
3. **The probe context was hand-assembled.** It proves the data is sufficient and the templates
   are faithful; it does not prove the transform's own context-building code is right. That is
   what the golden-file unit tests are for, and why FR-041 requires fixtures captured from the
   live graph rather than written by hand.
4. **Ordering is load-bearing in one comment block.** R6's rule is asserted by the golden diff
   and nowhere else. A future site whose name or kind changes the sort could break a comment
   while leaving the configuration correct.
