# Object Population Specification: The WAN's Addressing

> **Workflow**: This spec targets Infrahub object data population. The implementing agent MUST use the `infrahub-managing-objects` skill to generate all object files.

**Feature Branch**: `021-wan-addressing-objects`
**Created**: 2026-09-11
**Status**: Draft
**Input**: "cycle 021" — the object data cycle 020's schema was built for.

## Why this cycle exists

Cycle 020 added four relationships so the WAN's addressing would have somewhere to live. It
deliberately wrote nothing into `objects/`. This cycle fills them, and it is the last thing
standing between the repository and rendering the six FRR configs in `../lab/wan/rendered/`.

The debt being repaid is specific. `objects/33_nfd41_wan.yml` records the provider side of
acme's circuit like this:

```yaml
- side: a
  name: isp-pe1-eth2
  description: "Provider side, isp-pe1 eth2, 10.51.10.1/30"
```

An interface as a string and an address inside an English sentence. Cycle 010's assumption 4
forbade it — *"Free-text CIDRs are the failure mode this model exists to remove"* — and SC-008
said so plainly. The rule was written and the WAN seed broke it, because nothing read those
fields. This cycle replaces the prose with objects and then deletes the prose, so the two
cannot drift.

## The inventory, counted from the oracle

`../lab/wan/tenants.yml` is the authority, as it was for cycles 010 and 019. Parsing it yields
exactly what must be seeded:

| Kind | Count | Notes |
| --- | --- | --- |
| Interfaces | 20 | across seven routers — see the per-device table below |
| `IpamIPAddress` | 20 | every `/30` end, three loopbacks, three LAN addresses |
| `RoutingAsn` | 5 | 65500, 64500, 65010, 65020, 65030 |
| `RoutingBGPNeighbor` | 10 | both ends of five sessions |
| `RoutingVrfStaticRoute` | 1 | acme/dr, inside `CUST_ACME` |
| Router IDs | 6 | one per FRR-speaking router |
| Circuit endpoint links | 8 | every existing `DcimCircuitEndpoint` |

Interfaces per device, excluding the three enslaved branch access ports that are out of scope below:

| Device | Interfaces |
| --- | --- |
| `isp-pe1` | `lo`, `eth1` (core), `eth2` (acme/hq), `eth3` (globex/hq), `eth4` (acme/dr) |
| `isp-pe2` | `lo`, `eth1` (core), `eth2` (border-leaf1), `eth3` (internet) |
| `internet-rtr` | `eth1` (peering), `eth2` (LAN) |
| `cust-acme-ce` | `eth1` (WAN), `eth2` (LAN) |
| `cust-acme-dr-ce` | `eth1` (WAN), `eth2` (LAN) |
| `cust-globex-ce` | `eth1` (WAN), `eth2` (LAN) |
| `branch-rtr` | `lo`, `eth1` (to border-leaf1), `br-branch` (LAN) |

The ten BGP sessions, each as two device-scoped objects:

| Session | Provider/near side | Far side |
| --- | --- | --- |
| iBGP core | `isp-pe1` → 10.50.255.2 (AS 65500) | `isp-pe2` → 10.50.255.1 (AS 65500) |
| acme/hq | `isp-pe1` → 10.51.10.2 (AS 65010) | `cust-acme-ce` → 10.51.10.1 (AS 65500) |
| globex/hq | `isp-pe1` → 10.51.20.2 (AS 65020) | `cust-globex-ce` → 10.51.20.1 (AS 65500) |
| internet transit | `isp-pe2` → 10.52.0.2 (AS 64500) | `internet-rtr` → 10.52.0.1 (AS 65500) |
| DC handoff | `isp-pe2` → 10.250.50.1 (AS 65103) | *fabric side, already modelled* |
| branch | `branch-rtr` → 10.250.70.1 (AS 65103) | *fabric side, already modelled* |

acme/dr appears in none of them, and that is the point: it is `attachment_kind: static`, so it
contributes a static route instead of a session. Cycle 020 kept `bgp_sessions` optional for
exactly this site.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every circuit end resolves to a real address (Priority: P1)

An engineer opens acme's HQ circuit, follows the A side to `isp-pe1` `eth2`, and reads
`10.51.10.1/30` off the interface as an object. The Z side resolves the same way to
`cust-acme-ce` `eth1` and `10.51.10.2/30`. Nobody parses a description sentence, and the pair
is exactly what becomes `neighbor 10.51.10.2` on the PE and `neighbor 10.51.10.1` on the CE.

**Why this priority**: it is the debt repayment, it covers the largest share of the rendered
lines, and every other story leans on the interfaces it creates. An address cannot exist
without an interface to sit on.

**Independent Test**: traverse `circuit → endpoints → interface → ip_addresses` for all four
circuits and get eight addresses back. Valuable alone: the circuit model stops lying even if
stories 2 and 3 are dropped.

**Acceptance Scenarios**:

1. **Given** the schema from cycle 020 is loaded, **When** the object files are loaded, **Then**
   20 interfaces and 20 `IpamIPAddress` objects exist, each address reachable from its interface.
2. **Given** the objects are loaded, **When** each of the eight `DcimCircuitEndpoint` objects is
   queried, **Then** every one resolves to an interface, and that interface carries the address
   its description used to state in prose.
3. **Given** the addresses exist, **When** `objects/33_nfd41_wan.yml` is inspected, **Then** no
   endpoint description restates an address as text.

---

### User Story 2 - Every BGP session exists as two objects (Priority: P2)

The ten neighbor statements the six configs emit are all present as objects, each reachable
from the `WanSite` or `WanInternetPeering` that justifies it. A reviewer asking "where does
`neighbor 10.52.0.2 remote-as 64500` come from?" lands on the internet peering.

**Why this priority**: second because a session is worth little until the addresses in story 1
exist for it to point at, and because it is what turns cycle 020's `bgp_sessions` from an empty
relationship into the thing the renderer walks.

**Independent Test**: query `bgp_sessions` on all four `WanSite` objects and on the internet
peering; get eight sessions, with acme/dr returning zero.

**Acceptance Scenarios**:

1. **Given** the addresses are loaded, **When** the sessions are loaded, **Then** 10
   `RoutingBGPNeighbor` objects exist, each naming its device, peer address and remote AS.
2. **Given** a BGP-attached site, **When** its `bgp_sessions` is queried, **Then** both ends are
   returned — the PE's and the CE's.
3. **Given** acme's DR site, **When** its `bgp_sessions` is queried, **Then** it is empty, and
   its `static_routes` holds one route for `10.60.11.0/24` via `10.51.11.2` in `CUST_ACME`.
4. **Given** the five ASNs are loaded, **When** each router is queried, **Then** it names the
   `RoutingAsn` its `router bgp` line will use.

---

### User Story 3 - Every router names its own ID (Priority: P3)

Each of the six FRR-speaking routers names the address that is its router ID — a loopback for
three of them, a LAN or peering address for the other three.

**Why this priority**: smallest and most mechanical, but without it two lines of every rendered
config have no source, and the renderer would have to guess from interface naming.

**Independent Test**: query `router_id` on all six routers and compare to the lab's values.

**Acceptance Scenarios**:

1. **Given** the addresses are loaded, **When** each router is queried, **Then** its `router_id`
   matches the lab: `isp-pe1` 10.50.0.1, `isp-pe2` 10.50.0.2, `internet-rtr` 10.52.0.2,
   `cust-acme-ce` 10.60.10.1, `cust-globex-ce` 10.60.20.1, `branch-rtr` 10.70.255.1.
2. **Given** a router whose ID is a loopback, **When** its loopback interface is queried,
   **Then** the same `IpamIPAddress` object is reached both ways — one object, two paths, not a
   copy.
3. **Given** `cust-acme-dr-ce`, **When** it is queried, **Then** it has no router ID, because it
   runs no routing protocol.

---

### Edge Cases

- **acme/dr has no session.** A static site must load cleanly with an empty `bgp_sessions`.
  A file that seeds a session for it would be wrong, not merely redundant.
- **The branch has no circuit.** Its link into `border-leaf1` is a private fibre with no
  provider, so its site has no `DcimCircuitEndpoint` to link and only one interface to seed.
- **One address, reached two ways.** A loopback address is both `interface.ip_addresses` and
  `device.router_id`. It must be one object referenced twice; two objects with the same
  address would violate the `[address__value, ip_namespace]` uniqueness constraint.
- **`10.51.11.2` belongs to a CE that speaks no BGP.** acme/dr's CE still has interfaces and
  addresses — it is the static route's next hop — so "no session" must not become "no data".
- **Both ends of a session are separate objects** under a uniqueness constraint of
  `[device, peer_address__value]`. Two sessions on one device toward the same peer would
  collide; none of the ten do.
- **Addresses must carry a prefix length.** `10.50.0.1/32` for a loopback, not `10.50.0.1`.
- **`DcimCircuitEndpoint` is a component of its circuit.** The interface link must be added to
  the eight endpoints that already exist rather than creating a ninth.
- **A second load must change nothing.** Every file in this repository is re-runnable, and
  these must be too.

## Requirements *(mandatory)*

### Functional Requirements

**File Format & Structure**

- **FR-001**: Every object file MUST use `apiVersion: infrahub.app/v1` and `kind: Object`
- **FR-002**: Every `spec` block MUST name one schema kind and a `data` list
- **FR-003**: Multiple YAML documents in one file MUST be separated by `---`

**Relationship References**

- **FR-004**: Cardinality-one relationships MUST reference targets by `human_friendly_id` —
  scalar for single-element IDs, list for multi-element
- **FR-005**: `IpamIPAddress` references MUST use the two-element form
  `["<address>/<len>", "default"]`, because its `human_friendly_id` is
  `[address__value, ip_namespace__name__value]` — the form `objects/33_nfd41_wan.yml` already
  uses for prefixes
- **FR-006**: Interfaces MUST be nested inline under their device with the concrete kind named,
  since the relationship peer is a generic

**File Organization & Load Order**

- **FR-007**: New object files MUST live in `objects/` with numeric prefixes continuing the
  existing sequence, after `37_nfd41_wan_services.yml`
- **FR-008**: Interfaces and addresses MUST load before the sessions and router IDs that
  reference them
- **FR-009**: No new file may be referenced by an earlier-sorting file

**Data Integrity**

- **FR-010**: Dropdown values MUST use the choice `name`, not the display label
- **FR-011**: Address attributes MUST carry a prefix length; prefix attributes MUST use CIDR
- **FR-012**: Every address MUST be a single object even when reached by more than one path

**Population-Specific Requirements**

- **FR-013**: 20 interfaces MUST be created across the seven off-fabric routers, matching the
  per-device table above
- **FR-014**: Loopbacks MUST be created as virtual interfaces carrying the `loopback` role, so
  an announced `/32` is identifiable without inferring it from a name
- **FR-015**: 20 `IpamIPAddress` objects MUST be created and attached to their interfaces
- **FR-016**: Five `RoutingAsn` objects MUST be created and linked to the devices that use them
- **FR-017**: 10 `RoutingBGPNeighbor` objects MUST be created — both ends of every session
- **FR-018**: Every BGP-attached `WanSite` MUST name both of its sessions; the static site MUST
  name none
- **FR-019**: `WanInternetPeering` MUST name both ends of the transit session
- **FR-020**: One `RoutingVrfStaticRoute` MUST be created for acme/dr — `10.60.11.0/24` via
  `10.51.11.2` in `CUST_ACME`, on `isp-pe1` — and named by acme's DR site
- **FR-021**: Six devices MUST name their `router_id`; `cust-acme-dr-ce` MUST not
- **FR-022**: All eight existing `DcimCircuitEndpoint` objects MUST name their interface
- **FR-023**: The address prose in `objects/33_nfd41_wan.yml` endpoint descriptions MUST be
  removed once the objects replace it, so there is one source rather than two
- **FR-024**: Interfaces MUST carry the lab's MTU of 9214
- **FR-025**: Every file MUST load idempotently — a second run produces no error and no duplicate

### Key Entities

- **`InterfacePhysical` / `InterfaceVirtual`**: the routers' ports and loopbacks. Depend on the
  devices in `objects/31_nfd41_offfabric_devices.yml`. Virtual for loopbacks, physical for `eth*`.
- **`IpamIPAddress`**: every WAN address, attached to its interface. The `/30` prefixes it sits
  inside already exist in `objects/29_nfd41_offfabric_prefixes.yml`.
- **`RoutingAsn`**: the five autonomous systems, linked to devices through the existing
  `DcimDevice.asn` relationship. `fabric` stays unset — these are off-fabric.
- **`RoutingBGPNeighbor`**: one object per device per session. Unique on
  `[device, peer_address__value]`.
- **`RoutingVrfStaticRoute`**: acme/dr's route. Parented by `IpamVRF CUST_ACME`, which cycle 019
  created, and naming `isp-pe1` in `devices`.
- **`DcimCircuitEndpoint`** *(existing, updated)*: gains its `interface`.
- **`DcimDevice`** *(existing, updated)*: gains `router_id` and `asn`.
- **`WanSite`, `WanInternetPeering`** *(existing, updated)*: gain `bgp_sessions`, and acme/dr
  gains `static_routes`.

### Key Files

- `objects/*.yml` — loaded in filename sort order
- `objects/29_nfd41_offfabric_prefixes.yml` — the prefixes these addresses sit inside *(existing)*
- `objects/31_nfd41_offfabric_devices.yml` — the seven routers *(existing)*
- `objects/33_nfd41_wan.yml` — circuits, endpoints and sites *(updated: prose removed, links added)*
- `../lab/wan/tenants.yml` — the acceptance oracle

### Dependency Load Order

```text
29_nfd41_offfabric_prefixes.yml  -- IpamPrefix                        (existing)
31_nfd41_offfabric_devices.yml   -- the seven routers                 (existing)
33_nfd41_wan.yml                 -- circuits, endpoints, sites        (existing, updated)
37_nfd41_wan_services.yml        -- CUST_* VRFs, WAN services         (existing)
38_nfd41_wan_interfaces.yml      -- interfaces + addresses + ASNs     (new)
39_nfd41_wan_routing.yml         -- BGP neighbours, static route,
                                    router IDs, session links         (new)
```

Two new files rather than one, because the second references what the first creates. The split
is the load order, not an organisational preference.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every object file loads with no missing reference and no validation failure
- **SC-002**: The counts match the oracle: 20 interfaces, 20 addresses, 5 ASNs, 10 BGP
  neighbours, 1 static route, 6 router IDs, 8 circuit-endpoint interface links
- **SC-003**: `circuit → endpoints → interface → ip_addresses` returns an address for all eight
  endpoints across all four circuits
- **SC-004**: Every BGP-attached site returns exactly two sessions; acme's DR site returns zero
  and one static route
- **SC-005**: Every router's `router_id` matches the lab, and where it is a loopback it is the
  same object the loopback interface carries — not a duplicate
- **SC-006**: No address or prefix appears as free text in any endpoint description
- **SC-007**: A second load of every file produces no error and no duplicate object
- **SC-008**: Every value is traceable to `../lab/wan/tenants.yml`; nothing is invented
- **SC-009**: **Every line of the six rendered FRR configs has its data present in the graph.**
  This is the criterion that says the transform cycle can start, and it is the reason the other
  eight exist.
- **SC-010**: All unit tests and the repository's linters pass

## Assumptions

1. **`../lab/wan/tenants.yml` is the oracle, as in cycles 010 and 019.** Any value not derivable
   from it is a transcription error, not a judgement call.
2. **Hosts are out of scope because their devices do not exist.**
   `objects/31_nfd41_offfabric_devices.yml` holds the firewall and the seven routers, and no
   host. Seeding `cust-acme-host` or `internet-host` would mean creating device objects first,
   which is a different and larger question about what the lab's end hosts are for.
3. **The branch router's three enslaved access ports are lab plumbing; its LAN interface is not.**
   `eth2`, `eth3` and `eth4` are switch ports bridged into `br-branch` so the branch desktop,
   host and Guacamole gateway can reach each other. They carry no addresses, appear nowhere in
   `branch-rtr`'s FRR config, and cycle 010 already placed the Guacamole and desktop containers
   out of scope as "lab plumbing for demonstrating access". `br-branch` itself is kept: it is
   the router's LAN-facing layer-3 interface holding `10.70.0.1/24`, which is the same thing
   every customer edge's `eth2` is, and dropping it would leave the branch as the one router
   with no LAN side. Excluding the three ports is why the interface count is 20 rather than 23.
4. **Loopbacks are `InterfaceVirtual`, `eth*` is `InterfacePhysical`.** Both inherit
   `InterfaceLayer3` and so carry `ip_addresses`; no new interface kind is needed for a router
   that is not an EOS switch.
5. **The fabric ends of the two handoff sessions already exist.** `isp-pe2`'s session toward
   `border-leaf1` and `branch-rtr`'s toward the border leaf name a fabric peer that
   `objects/27_nfd41_vrf_services.yml` already models. Only the WAN side is seeded here.
6. **`WanSite.site_asn` stays as it is.** It duplicates what a `RoutingAsn` now holds, and
   reconciling them is a defensible cleanup but not this cycle's, which is purely additive.

## Out of Scope

- **The FRR transform.** The next cycle. This one puts the data in the graph; nothing here
  renders a line of configuration.
- **End hosts.** See assumption 2.
- **The branch router's three enslaved access ports.** See assumption 3.
- **`init.sh`, `daemons`, and the host init scripts** the lab renders alongside the FRR configs.
  They are container plumbing — namespaces, links, MTU — not routing intent, and `daemons` is a
  static file.
- **Generators beneath the WAN services.** Nothing here derives an object from a service; this
  is transcription. Deriving these objects from `ServiceL3vpn` is a separate cycle, and a good
  one, but it needs the transcribed truth first to check itself against.
- **Any schema change.** Cycle 020 added what this needs. If something turns out to be
  unrepresentable, it belongs in a schema cycle first, per the layering rule 010 established.
- **Reconciling `WanSite.site_asn` with `RoutingAsn`.** See assumption 6.
- **The Junos firewall render and the `protocols.py` extensions gap.** Both are live backlog
  items, both are independent of this chain.
