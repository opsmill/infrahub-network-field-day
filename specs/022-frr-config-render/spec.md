# Transform Specification: FRR Configuration for the WAN

> **Workflow**: Infrahub Transform
> **Skill**: Use the `infrahub-managing-transforms` skill to implement this spec.

**Feature Branch**: `022-frr-config-render`
**Created**: 2026-09-11
**Status**: Draft
**Input**: "cycle 22" — the FRR render, which cycles 020 and 021 existed to enable.

## Why this cycle exists

This is the end of the chain and the point of the last three cycles. Cycle 010's opening request
was to *"contain all of the information that is in the lab: the ISP, the branches, and the
firewall"* and render it. The fabric renders through AVD. Crossplane renders through cycles 011
and 017. **The WAN has never rendered at all.**

Cycle 019 named this cycle as its successor and could not start it: the addresses were prose in
description fields. Cycle 020 gave them somewhere to live, cycle 021 put them there, and 021's
SC-009 walk confirmed every element of the six rendered configs now resolves to live data.
Nothing is blocked.

The oracle is unusually good. `../lab/wan/rendered/` holds the six configs the lab actually
runs, and `../lab/wan/templates/` holds the five Jinja2 templates that produced them. This is
not a render that has to be invented and then judged by eye — it is a port, with 448 lines of
golden output to diff against.

### Where the service layer finally becomes visible

`isp-pe1` is the reason this cycle is worth doing rather than just tidy. Its per-tenant import
policy is where ordered intent turns into configuration:

```text
route-map RM-ACME-IMPORT permit 10     <- ServiceL3vpn.dc_service_prefixes  (shared DC range)
route-map RM-ACME-IMPORT permit 20     <- ServiceTenantCloud.prefix         (acme's own subnet)
route-map RM-ACME-IMPORT permit 30     <- a ServiceInternetAccess EXISTS    (acme bought it)
route-map RM-ACME-IMPORT deny 99
```

globex's equivalent has no `permit 30`, because globex bought no internet access. The
difference between the two tenants is the presence of one service object, and it shows up as
one clause of routing policy on a real device. Every previous cycle asserted that the layering
was worth having; this one demonstrates it.

## Transform Type

- **Approach**: **Hybrid** — Python prepares the context from a GraphQL query, Jinja2 renders it.
  The lab's templates are already Jinja2 and can be ported rather than reinvented, and the
  context they need (tenants with their sites, services and policies, assembled per device) is
  well past what a template should assemble for itself.
- **Output Format**: `text/plain` — FRR configuration
- **Target Nodes**: `DcimDevice`, the six FRR-speaking routers

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The customer edges and the branch render byte-for-byte (Priority: P1)

An engineer opens `cust-acme-ce` in Infrahub and reads its FRR configuration as an artifact:
its AS, its router ID, its neighbour toward the PE, its LAN network, and the prefix-list that
stops it leaking anything else. The file is identical to what the lab runs.

**Why this priority**: it is the smallest slice that proves the entire chain — query, context
assembly, template, artifact definition, and the golden-file diff harness every later story
reuses. Two templates, three devices, 77 template lines. If only this ships, three of the lab's
six routers are rendered from the model and the harness exists.

**Independent Test**: generate the artifact for `cust-acme-ce`, `cust-globex-ce` and
`branch-rtr` and diff each against `../lab/wan/rendered/<device>/frr.conf`. Zero diff, modulo
the provenance line.

**Acceptance Scenarios**:

1. **Given** the WAN's addressing is seeded, **When** the artifact is generated for
   `cust-acme-ce`, **Then** the output matches the lab's file on every line except the
   provenance header.
2. **Given** the same transform, **When** it runs for `cust-globex-ce`, **Then** the output
   differs from acme's only in the tenant's own values — the same template serves both.
3. **Given** `branch-rtr`, **When** its artifact is generated, **Then** it peers with
   `border-leaf1` and names no ISP at all, because the branch is not a WAN customer.

---

### User Story 2 - The provider edge renders, and the service layer shows (Priority: P2)

`isp-pe1` renders with a VRF per tenant, a per-tenant import route-map assembled from that
tenant's services, and the static route for acme's DR site redistributed into the VRF.
`isp-pe2` renders with the DC handoff and the internet transit session.

**Why this priority**: the payoff and the risk in one story. 271 of the 409 template lines, and
the only place the service layer is legible in a device configuration. Second rather than first
because the harness from US1 is what makes a 159-line diff tractable.

**Independent Test**: generate the artifact for `isp-pe1` and `isp-pe2` and diff against the
lab. Then delete acme's `ServiceInternetAccess` on a branch, re-render, and confirm the six-line
change SC-003 describes and nothing more.

**Acceptance Scenarios**:

1. **Given** both tenants' services, **When** `isp-pe1` is rendered, **Then** the output matches
   the lab byte-for-byte modulo provenance, including both tenant VRFs and both import
   route-maps.
2. **Given** acme has a `ServiceInternetAccess` and globex does not, **When** both import
   route-maps are compared, **Then** acme's has a default-route clause and globex's does not.
3. **Given** acme's DR site is statically attached, **When** `isp-pe1` is rendered, **Then**
   `ip route 10.60.11.0/24 10.51.11.2` appears inside `vrf CUST_ACME` and `redistribute static`
   appears in that VRF's address family.
4. **Given** `isp-pe2`, **When** it is rendered, **Then** it carries the iBGP session to
   `isp-pe1` with `next-hop-self`, the eBGP session to `border-leaf1` in VRF WAN, and the
   transit session to the internet.

---

### User Story 3 - The internet router renders (Priority: P3)

`internet-rtr` renders as AS 64500: a blackhole default, the customer aggregate it accepts from
the ISP, and what it announces back.

**Why this priority**: smallest remaining slice, one template, 61 lines, and the only device
that belongs to neither the provider nor a customer. It completes the set.

**Independent Test**: generate the artifact and diff against the lab's file.

**Acceptance Scenarios**:

1. **Given** the internet peering, **When** the artifact is generated, **Then** it matches the
   lab modulo provenance.
2. **Given** the customer aggregate, **When** the inbound prefix-list is inspected, **Then** it
   permits `10.60.0.0/16 le 24` and denies the rest.

---

### Edge Cases

- **The provenance line cannot be reproduced honestly.** Every lab file opens with
  `! Rendered by wan/render.py for <node> -- do not edit.` Infrahub is not `wan/render.py`, so
  the rendered artifact must name its real renderer and the comparison must normalise that one
  line. Reproducing it verbatim would embed a false claim in six device configurations.
- **A tenant with no internet access** must omit the default-route clause entirely, not emit an
  empty one. This is globex, and it is the whole demonstration.
- **A statically attached site** contributes a static route and no BGP session. Rendering an
  empty `neighbor` line for it would be accepted by vtysh and never come up.
- **A site with no circuit** — the branch — must render without reaching for a provider.
- **A device with no router ID** must not render a `bgp router-id` line. `cust-acme-dr-ce` has
  none, and is deliberately not a target of this transform.
- **Whitespace and ordering.** The oracle has trailing newlines, blank comment lines and a
  specific clause order. A diff that is "semantically equal" is a failed diff.
- **Route-map sequence numbers** are computed in the lab's template (`10 + loop.index0 * 5`).
  The port must reproduce the arithmetic, not hardcode the result.
- **An empty query result** — a device in the target group with no sessions or addresses — must
  fail loudly rather than render a config with blanks where addresses belong.

## Requirements *(mandatory)*

### Functional Requirements

#### GraphQL Query

- **FR-001**: A GraphQL query MUST be added under `transforms/` that retrieves everything a
  device's configuration needs, parameterised by device name.
- **FR-002**: The query MUST accept the device as a variable, matching the artifact definition's
  parameter mapping.
- **FR-003**: The query MUST retrieve, for the target device: its name, role, ASN, router ID,
  interfaces with their addresses, and its BGP neighbours.
- **FR-004**: The query MUST also retrieve the WAN context a provider edge needs — every tenant,
  its sites with their LAN prefixes and attachment kinds, its L3VPN with its DC service
  prefixes, its tenant cloud with its subnet, whether it has an internet-access service, its
  static routes, and the internet peering with its aggregate.
- **FR-005**: `ip_addresses` MUST be selected through an inline fragment on `InterfaceLayer3`.
  It is not selectable on the `DcimInterface` generic, and the plain form is rejected outright.
- **FR-006**: The query MUST be registered in `.infrahub.yml` under `queries`.

#### Transform Logic

- **FR-010**: The transform MUST be a Python class that prepares a per-device context and
  renders one of five Jinja2 templates.
- **FR-011**: The transform MUST select its template from the device's role — `isp_edge`,
  `isp_core`, `internet_edge`, `customer_edge`, `branch_router`.
- **FR-012**: The transform MUST return a string, so the artifact is `text/plain`.
- **FR-013**: The transform MUST raise rather than render when a required value is absent. A
  BGP neighbour line with a blank address is accepted by vtysh and never comes up, which is the
  failure this rule exists to prevent — it is also why the lab's own renderer uses
  `StrictUndefined`.
- **FR-014**: The transform MUST NOT reach for data the query did not return. Assembling
  context from a second query or from the SDK directly would make the artifact's inputs
  invisible to a reviewer.
- **FR-015**: Route-map and prefix-list sequence numbers MUST be computed as the lab's templates
  compute them, not restated as literals.

#### Jinja2 Templates

- **FR-020**: Five templates MUST be added under `transforms/templates/`, ported from
  `../lab/wan/templates/*.frr.conf.j2`.
- **FR-021**: The templates MUST reproduce the lab's output exactly, **including its comments**.
  The comments carry most of the teaching value of these configs — why next-hop-self is needed,
  why the import route-map is what keeps tenants apart — and dropping them would render a
  correct config that explains nothing.
- **FR-022**: The environment MUST use strict undefined handling, so a missing value fails the
  render instead of emitting a blank.
- **FR-023**: Each template MUST open with a provenance line naming Infrahub and the device.

#### Artifact & Registration

- **FR-030**: A `CoreStandardGroup` MUST be added for the FRR-speaking routers, and the six
  devices MUST be its members. An artifact definition cannot generate against a target group
  that does not exist.
- **FR-031**: `cust-acme-dr-ce` MUST NOT be a member. It runs no routing protocol and the lab
  renders no FRR config for it — membership would produce a seventh artifact with nothing in it.
- **FR-032**: The transform MUST be registered under `python_transforms` in `.infrahub.yml`.
- **FR-033**: An artifact definition MUST be registered with content type `text/plain`,
  targeting the new group, and mapping the device name to the query variable.

#### Tests

- **FR-040**: A unit test MUST render each of the six devices from a fixture and diff the result
  against `../lab/wan/rendered/<device>/frr.conf`, normalising only the provenance line.
- **FR-041**: The fixtures MUST be captured from the live graph rather than hand-written, so a
  drift between the model and the fixture cannot hide a rendering bug.
- **FR-042**: A test MUST assert that removing a tenant's internet-access service removes
  exactly the default-route clause from its import route-map and changes nothing else.

### Key Files

| File | Purpose |
|------|---------|
| `transforms/avd_frr_config.gql` | GraphQL query for one device plus its WAN context |
| `transforms/avd_frr_config_query.py` | Generated return types — regenerated, never hand-written |
| `transforms/frr_config.py` | The transform class and its context assembly |
| `transforms/templates/frr/isp-edge.j2` | The provider edge |
| `transforms/templates/frr/isp-core.j2` | The provider core |
| `transforms/templates/frr/internet-rtr.j2` | AS 64500 |
| `transforms/templates/frr/customer-ce.j2` | Both customer edges |
| `transforms/templates/frr/branch-router.j2` | The branch |
| `objects/00_groups.yml` | The new target group |
| `.infrahub.yml` | Query, transform and artifact registration |
| `tests/unit/test_frr_config.py` | Golden-file parity against the lab |

### Key Entities

- **`DcimDevice`**: the render target. Supplies role, ASN, router ID, interfaces and neighbours.
  Already inherits `CoreArtifactTarget`.
- **`WanSite`**: a tenant's attachment. Supplies the LAN prefix, the attachment kind, both ends
  of the BGP session, and any static route.
- **`WanInternetPeering`**: the transit peering, its aggregate and its two session ends.
- **`ServiceL3vpn`**: the tenant's VPN. Supplies the PE VRF and the shared DC service prefixes.
- **`ServiceTenantCloud`**: the tenant's DC subnet, which becomes one clause of its import policy.
- **`ServiceInternetAccess`**: **its presence or absence is the data.** One object is the
  difference between acme and globex.
- **Rendered FRR configuration**: one `text/plain` artifact per device, six in total.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All six devices render, and each output is identical to
  `../lab/wan/rendered/<device>/frr.conf` on every line except the provenance header.
- **SC-002**: The 448 lines of golden output are matched exactly — whitespace, blank lines,
  comments and clause order included.
- **SC-003**: Removing acme's internet-access service changes exactly six lines of `isp-pe1`'s
  configuration, **measured by rendering it both ways** rather than by reading the template:
  five removed — the `permit 30` clause, its description, its match, the `!` that closes the
  block, and the old tenant header — and one added, the header re-rendered as
  `! ==== tenant acme (VRF CUST_ACME, internet: no) ====`. Nothing else moves; in particular the
  `PL-DEFAULT` prefix-list stays, because it is guarded by the ISP having an internet connection
  rather than by any tenant buying access.
- **SC-004**: `cust-acme-ce` and `cust-globex-ce` render from one template, differing only in
  their tenants' values.
- **SC-005**: A device missing a required value fails the render with a named error rather than
  emitting a blank field.
- **SC-006**: The artifact definition generates six artifacts and no seventh.
- **SC-007**: Every value in every rendered config traces to an object in the graph; none is
  hardcoded in a template except FRR's own syntax.
- **SC-008**: All unit tests and the repository's linters pass.
- **SC-009**: **`../lab/wan/render.py` becomes redundant.** The lab could delete its renderer,
  its templates and its `tenants.yml` and lose nothing that Infrahub does not now hold. This is
  the criterion that says the end goal is met for the WAN.

## Assumptions

1. **The lab's templates are the starting point, not a reference.** They are already Jinja2,
   they are known correct, and porting them is both faster and safer than writing five
   templates against a golden file. The port changes the context variable names and nothing else.
2. **Byte-for-byte parity excludes exactly one line.** The provenance header. Everything else,
   including every comment, must match. See the edge cases for why.
3. **The transform reads the technical layer and the service layer both.** Cycle 010's
   assumption 6 says renderers read technical objects — and for the fabric that holds. The
   provider edge is the exception the layering was built for: its import policy *is* the service
   intent, so `ServiceL3vpn`, `ServiceTenantCloud` and `ServiceInternetAccess` are inputs. This
   is a deliberate reading of that assumption, not a violation of it, and it is why cycle 010
   made every service kind reachable.
4. **The group is object data added by this cycle.** Cycle 017 set the precedent, adding
   `service_fabric_apps` to `objects/00_groups.yml` in a transform cycle for the same reason: an
   artifact definition cannot target a group that does not exist.
5. **The generated protocols will not help.** `infrahubctl protocols --schemas` reflects no
   `extensions:` block, so `DcimDevice.router_id`, `DcimCircuitEndpoint.interface` and every
   other extension relationship are invisible to `protocols.py`. This transform will use the
   generated GraphQL return types instead, which are complete. Fixing the protocols generator is
   a separate cycle and remains on the backlog.

## Out of Scope

- **`init.sh`, `daemons`, and the host init scripts** the lab renders alongside the FRR configs.
  They are container plumbing — namespaces, veth pairs, MTU, bridges — not routing intent, and
  `daemons` is a static file. Rendering them would mean modelling ContainerLab's runtime, which
  is a different problem.
- **`cust-acme-dr-ce`, and every end host.** The lab renders no FRR config for the statically
  attached CE, and the hosts have no device objects.
- **Deploying the configs.** The lab's `make wan-deploy` pushes and reloads; nothing here talks
  to a device.
- **Deleting the lab's renderer.** SC-009 asserts it *could* go, which is a statement about this
  repository. Changing the lab is the lab's business.
- **The Junos firewall render.** An independent branch of the same end goal, with its own
  oracle, and fully unblocked — but not this cycle.
- **Any schema change.** Cycles 020 and 021 supplied the model and the data. If something turns
  out to be unrepresentable, it belongs in a schema cycle first.
- **Fixing the `protocols.py` extensions gap.** See assumption 5.

## Dependencies

- **Cycle 021's object data**, which is **uncommitted at the time of writing** — on git branch
  `021-wan-addressing-objects`, with the loaded data on Infrahub branch `wan-obj`. This cycle
  cannot render without it. Committing 021 is a prerequisite, not an optional tidy-up.
- Cycle 020's schema, merged to `main`.
