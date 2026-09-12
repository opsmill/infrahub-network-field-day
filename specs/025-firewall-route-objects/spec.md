# Object Population Specification: The Perimeter Firewall's Static Routes

**Feature Branch**: `025-firewall-route-objects`
**Created**: 2026-09-12
**Status**: Draft
**Artifact type**: Objects (second of three — see [Next cycle](#next-cycle))

## Summary

Eight static routes, transcribed from `../lab/configs/fw/vsrx/junos.conf` onto `fw1`. Cycle 024
widened `RoutingStaticRoute.device` so a `SecurityFirewall` can own one; this cycle puts the
device's real forwarding decisions into the graph. Cycle 026 renders them.

Nothing is designed here. The eight routes exist, on a device that is running, and the work is
getting them into Infrahub without changing them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The firewall's forwarding decisions are in the graph (Priority: P1)

A network engineer opens `fw1` in Infrahub and sees the eight routes the device actually holds —
destination, next hop, and the comment explaining what each prefix is for — instead of having to
open a configuration file on the device.

**Why this priority**: it is the cycle. Everything else here is a check on it.

**Independent test**: load the objects, query `fw1.static_routes`, and compare all eight
destination/next-hop pairs against the device file in both directions.

**Acceptance Scenarios**:

1. **Given** the schema from cycle 024, **When** the object file is loaded, **Then** `fw1` holds
   exactly eight `RoutingStaticRoute` objects.
2. **Given** those eight, **When** each is compared to the device file, **Then** every `prefix`
   and `next_hop` matches character for character.
3. **Given** the device file, **When** it is read for routes, **Then** every one of its eight
   appears in the graph — the comparison runs both ways, so neither a missing route nor an
   invented one passes.
4. **Given** each route, **When** its `route_name` is read, **Then** it carries the device's own
   `/* … */` comment text.
5. **Given** the load has run once, **When** it runs again, **Then** there are still eight routes
   and no duplicates.

### User Story 2 - The routes are consistent with the rest of the model (Priority: P2)

The routes agree with what the firewall already knows: every next hop is somewhere the firewall
can actually reach, and every destination is a prefix it already has policy for.

**Why this priority**: transcription can be faithful and still wrong if a digit slipped. These
two invariants catch that without needing the device file a second time, and they are the reason
to put the routes in a model rather than a text file.

**Independent test**: check each next hop against `fw1`'s interface subnets, and each destination
against the security address book.

**Acceptance Scenarios**:

1. **Given** the six distinct next hops, **When** each is checked, **Then** it lies inside a /30
   that one of `fw1`'s own interfaces is numbered on. A route whose next hop is not on a connected
   subnet would not install on the device.
2. **Given** the eight destinations, **When** each is checked against the address book, **Then**
   it equals the prefix of an existing `SecurityGenericAddress` — `k8s-nodes`, `k8s-pods`,
   `k8s-services`, `app-hosts`, `wan-customers`, `branch-users`, `acme-cloud`, `globex-cloud`.

### User Story 3 - Loading the repository from scratch still works (Priority: P3)

Someone running `invoke load` on an empty instance gets the routes along with everything else,
in an order that resolves.

**Why this priority**: a new object file that loads only when the graph is already populated is a
trap that appears months later.

**Independent test**: the file's numeric prefix places it after the file that defines `fw1`.

**Acceptance Scenarios**:

1. **Given** an empty instance, **When** `objects/` is loaded in filename order, **Then** the
   routes load after `fw1` exists and the `device` reference resolves.

### Edge Cases

- **A next hop that is not on a connected subnet.** Junos would accept the configuration and the
  route would never install. US2 scenario 1 is the guard.
- **`vrf` is left unset.** The device file's `routing-options` sits outside any
  `routing-instances` block, so these are master-instance routes. The attribute defaults to
  `"default"`, which is exactly that, so no route sets it — and the uniqueness constraint
  `[device, prefix, vrf]` depends on that default being consistent.
- **Two routes share a next hop.** Three of the eight point at `10.250.110.1`. That is correct —
  the k8s node, pod and service ranges all sit behind the same leaf — and uniqueness is on
  destination, not next hop, so it is allowed.
- **A second load.** `infrahubctl object load` upserts on the human-friendly ID, which for this
  kind is `[device__name__value, prefix__value]`. Reloading must not duplicate.
- **The device file gains a ninth route.** Out of scope, but the both-ways comparison in US1
  scenario 3 means the test fails rather than silently ignoring it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Exactly eight `RoutingStaticRoute` objects MUST be created, all owned by `fw1`.
- **FR-002**: Each route's `prefix` MUST equal the destination in the device file, character for
  character.
- **FR-003**: Each route's `next_hop` MUST equal the next hop in the device file, character for
  character.
- **FR-004**: Each route's `route_name` MUST carry the text of that route's `/* … */` comment
  from the device file.
- **FR-005**: No route MUST set `vrf`; the schema default `"default"` is the master instance,
  which is where these routes live.
- **FR-006**: No route MUST set `gateway`, `interface`, `distance` or `tag`. The device file sets
  none of them, and inventing a value would be a change rather than a transcription.
- **FR-007**: The `device` relationship MUST reference `fw1`.
- **FR-008**: The objects MUST live in a new file under `objects/`, numbered so it loads after
  the file that defines `fw1`.
- **FR-009**: No schema change. Cycle 024 did that work, and this cycle must not need more.
- **FR-010**: No existing object file MUST be modified.
- **FR-011**: Loading twice MUST leave eight routes, not sixteen.
- **FR-012**: A test MUST compare the graph against the device file **in both directions**, so
  that an omitted route fails as loudly as an invented one.

### Key Entities

- **`RoutingStaticRoute`** — existing kind, unchanged by this cycle. Uses `prefix`, `next_hop`,
  `route_name` and `device`; leaves `gateway`, `interface`, `distance`, `tag` and `vrf` alone.
  Unique per `[device, prefix, vrf]`, HFID `[device__name__value, prefix__value]`.
- **`fw1`** — a `SecurityFirewall`, defined in `objects/31_nfd41_offfabric_devices.yml`. Not
  modified here; the routes point at it.

### Key Files

| File | Change |
| --- | --- |
| `objects/32b_nfd41_fw_static_routes.yml` | **NEW** — the eight routes |
| `tests/unit/test_fw_static_route_objects.py` | **NEW** — both-ways comparison against the device file |

### Dependency Load Order

`fw1` is defined in `31_nfd41_offfabric_devices.yml`. The firewall's security objects are in
`32_nfd41_security.yml`. The routes reference `fw1` only, so anything after `31` would resolve;
`32b` places them next to the firewall's other data and after `32a` should one ever appear.

## The data

Transcribed from `../lab/configs/fw/vsrx/junos.conf` lines 161–172:

| # | Destination | Next hop | Comment | Reaches via |
| --- | --- | --- | --- | --- |
| 1 | `10.110.0.0/24` | `10.250.110.1` | k8s nodes | ge-0/0/0 |
| 2 | `10.111.0.0/16` | `10.250.110.1` | k8s pod CIDR | ge-0/0/0 |
| 3 | `10.112.0.0/16` | `10.250.110.1` | k8s service CIDR incl. LoadBalancer VIPs | ge-0/0/0 |
| 4 | `10.210.0.0/24` | `10.250.210.1` | app tenant hosts | ge-0/0/1 |
| 5 | `10.60.0.0/16` | `10.250.150.1` | WAN customer supernet | ge-0/0/2 |
| 6 | `10.70.0.0/24` | `10.250.170.1` | branch office LAN | ge-0/0/3 |
| 7 | `10.220.10.0/24` | `10.250.10.1` | acme cloud instances | ge-0/0/4 |
| 8 | `10.220.20.0/24` | `10.250.20.1` | globex cloud instances | ge-0/0/5 |

Two cross-checks fall out of this table, and both became requirements:

- **Every next hop is the far end of a /30 `fw1` is numbered on** — `10.250.110.2/30` on
  ge-0/0/0, `10.250.210.2/30` on ge-0/0/1, and so on, all six terminating on `border-leaf1`.
- **Every destination is already in the security address book**, one for one: `k8s-nodes`,
  `k8s-pods`, `k8s-services`, `app-hosts`, `wan-customers`, `branch-users`, `acme-cloud`,
  `globex-cloud`. The firewall routes to precisely the prefixes it filters.

## Success Criteria *(mandatory)*

- **SC-001**: `fw1` holds exactly eight `RoutingStaticRoute` objects after the load.
- **SC-002**: All eight `prefix` and `next_hop` values match the device file character for
  character, verified **both ways** — nothing missing, nothing invented.
- **SC-003**: All eight `route_name` values carry the device file's own comment text.
- **SC-004**: Every next hop lies within a /30 that one of `fw1`'s interfaces is numbered on.
- **SC-005**: Every destination equals the prefix of an existing `SecurityGenericAddress`.
- **SC-006**: A second `infrahubctl object load` leaves eight routes, verified by counting rather
  than by reading the log — the CLI prints "Created node" for an upsert, which cycle 023 already
  found misleading.
- **SC-007**: No file under `schemas/` changes.
- **SC-008**: No existing file under `objects/` changes.
- **SC-009**: The full unit suite stays green at its current count of 1008, plus whatever the new
  test module adds.

## Assumptions

1. **`fw1` can own a static route**, because cycle 024 made it so and demonstrated it live. This
   cycle depends on that and does not re-open it.
2. **A scalar HFID reference to `fw1` works** even though `device` now peers a generic. The
   Infrahub objects guidance flags generic peers as a failure case, but only when the generic has
   no `human_friendly_id`; `DcimGenericDevice` defines `[name__value]`, and cycle 024 verified an
   object load with `device: "fw1"` succeeding. So no inline concrete-kind block is needed here —
   the pattern cycle 023 had to use for the polymorphic address book does not apply.
3. **`route_name` is the right home for the comments.** It is optional, `Text`, and labelled
   "Route Description". Cycle 022 made the same argument for the FRR templates: these comments
   are most of the teaching value of the configuration.
4. **The comment text is transcribed as written**, including "incl." in route 3, rather than
   tidied. A renderer that reproduces the file must not have to undo an improvement.

## Scope

**In scope**: one new object file, one new test module, and the both-ways comparison against the
device file.

**Out of scope**:

- **Rendering the `routing-options` stanza** — cycle 026, and it carries a known difficulty
  (below).
- **The `system` stanza** — permanently excluded; two credential hashes that must never enter the
  model.
- **The `flow` block** — seven lines, still unmodelled.
- **Routes on any other device.** The eleven existing `RoutingStaticRoute` objects belong to
  fabric devices and are written by the `backfill-structured-config` generator. This cycle neither
  reads nor disturbs them.
- **A check enforcing route/address-book agreement.** SC-005 asserts it once, at this cycle's
  gate. Making it a standing rule over the whole graph is a check cycle, not this one.

## Next cycle

**026 — render the stanza.** The artifact goes 573 → 585 of 677 lines and the documented
exclusion list shrinks from 104 to 92.

It carries a difficulty measured during cycle 024 and recorded here so it is not rediscovered:
the stanza's route lines are **column-aligned by hand, and inconsistently**. The prefix field pads
to a minimum width of 13, putting `next-hop` at column 28 for six routes and 29 for the two whose
prefix is a character longer; the comment then starts at column 53 for those six and column
**52** for the other two. No single derivation reproduces all eight lines — two are simply
misaligned by one column in the source. That decides a success criterion in 026: byte-for-byte on
ten of twelve lines with the deviation enumerated, or a relaxed comparison. It affects nothing
here, because this cycle stores no presentation.

## Dependencies

Cycle 024 is merged and pushed, and its schema change is live on Infrahub `main` — verified after
that merge: `RoutingStaticRoute.device` peers `DcimGenericDevice` and `SecurityFirewall` exposes
`static_routes`. Nothing else is outstanding.
