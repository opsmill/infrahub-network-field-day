---

description: "Task list for the WAN's addressing"
---

# Tasks: The WAN's Addressing

**Input**: Design documents from `/specs/021-wan-addressing-objects/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/object-contract.md](./contracts/object-contract.md)

**Tests**: **REQUIRED.** Constitution IV. A new `tests/unit/test_wan_addressing_objects.py`
compares the object files against `../lab/wan/tenants.yml` in both directions, so an invented
value fails as loudly as a missing one. It parses YAML and needs no server.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: the user story from [spec.md](./spec.md) this task serves

## Before you start: the trap that will cost you an hour

Every inline relationship block in this cycle is **cardinality one**, and for those the `data:`
key must be a **mapping**, not a list:

```yaml
interface:
  kind: InterfacePhysical
  data:
    name: eth2            # correct — no dash
    device: isp-pe1
```

A dash before `name:` produces `AttributeError: 'list' object has no attribute 'items'` from
inside the SDK, naming neither the file nor the field. The `infrahub-managing-objects` skill
documents the list form; it is wrong for cardinality one against SDK 1.22.0. See
[research.md](./research.md) R2.

---

## Phase 1: Setup

**Purpose**: a stack, a branch, and cycle 020's schema — which is not on `main`.

- [X] T001 Verify preflight: `uv run infrahubctl info` shows Connection Status ✅ against Infrahub 1.10.6
- [X] T002 Export `INFRAHUB_API_TOKEN` from the stack's environment; `object load` fails with `401 Unauthorized` without it
- [X] T003 Create the git branch `021-wan-addressing-objects`. Base it on `main` if cycle 020 has been merged, otherwise on `020-wan-addressing-schema` — this cycle cannot load without 020's four relationships
- [X] T004 Create a **fresh** Infrahub branch `wan-obj` with `--sync-with-git`. Do **not** reuse `wan-addr`: Phase 0 research loaded partial probe data into it, and it must not be merged (research open risk 1)
- [X] T005 Load the schema into `wan-obj` with `uv run infrahubctl schema load schemas --branch wan-obj`, so cycle 020's relationships exist before any object references them

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the oracle inventory and the before-counts. Two success criteria are statements
about a change and cannot be judged from the after-state alone.

**⚠️ CRITICAL**: T007 must run before any object file is edited.

- [X] T006 Extract the full inventory from `../lab/wan/tenants.yml` by parsing it, not reading it — 20 interfaces, 20 addresses, 5 ASNs, 10 sessions, 6 router IDs, 1 static route. Save it to [acceptance-evidence.md](./acceptance-evidence.md); it is the list every later task is checked against
- [X] T007 Record baseline counts of `InterfacePhysical`, `InterfaceVirtual`, `IpamIPAddress`, `RoutingAsn`, `RoutingBGPNeighbor` and `RoutingVrfStaticRoute` on `wan-obj` before loading, using the count query in [quickstart.md](./quickstart.md) §3. The fabric already has interfaces and addresses, so only a delta is meaningful
- [X] T008 [P] Confirm `31a_nfd41_wan_addressing.yml` sorts between `31_nfd41_offfabric_devices.yml` and `32_nfd41_security.yml` by sorting the real filenames. The whole file layout rests on this

**Checkpoint**: the oracle and the before-state are recorded; story work can begin.

---

## Phase 3: User Story 1 — Every circuit end resolves to a real address (Priority: P1) 🎯 MVP

**Goal**: `circuit → endpoint → interface → ip_addresses` resolves for all eight endpoints, and
the address prose comes out of the descriptions.

**Independent Test**: traverse all four circuits and get eight addresses back. Valuable alone —
the circuit model stops lying even if US2 and US3 are dropped.

### Implementation for User Story 1

- [X] T009 [US1] Create `objects/31a_nfd41_wan_addressing.yml` with the `$schema`-less object-file header and a comment explaining why the file sits at `31a`: after the devices its interfaces hang off, before the circuits and sites that name them
- [X] T010 [US1] Add the `InterfacePhysical` document — 17 interfaces with scalar `device`, `mtu: 9214`, and roles from the existing dropdown, per [data-model.md](./data-model.md) §1
- [X] T011 [US1] Add the `InterfaceVirtual` document — 3 loopbacks on `isp-pe1`, `isp-pe2`, `branch-rtr`, each `role: loopback`
- [X] T012 [US1] Add interfaces for `cust-acme-dr-ce` even though it speaks no routing protocol — its `eth1` address is the static route's next hop
- [X] T013 [US1] Add the `IpamIPAddress` document — 20 addresses, each attached with an inline concrete-kind `interface` block. **`data:` is a mapping** (R1, R2)
- [X] T014 [US1] In `objects/33_nfd41_wan.yml`, add `interface: ["<device>", "<iface>"]` to all eight `DcimCircuitEndpoint` entries, nested where they already are. The HFID list form works here because `DcimInterface` declares one, unlike `InterfaceLayer3` (R5)
- [X] T015 [US1] In the same file, **remove the address from every endpoint `description`** — `"Provider side, isp-pe1 eth2, 10.51.10.1/30"` becomes `"Provider side"`. Do this as its own commit so the diff shows the debt being repaid

### Tests for User Story 1

- [X] T016 [US1] Create `tests/unit/test_wan_addressing_objects.py` with helpers that load the object files and `../lab/wan/tenants.yml`, following the parsing style of `tests/unit/test_nfd41_seed_data.py`
- [X] T017 [US1] Add a two-directional parity test for interfaces and addresses: every one in the files appears in the lab file, and every one in the lab file appears in the files — excluding the three enslaved branch access ports (spec assumption 3)
- [X] T018 [P] [US1] Add a test asserting no endpoint `description` in `objects/33_nfd41_wan.yml` matches an IPv4 address or CIDR. This is the regression guard for the debt this cycle repays
- [X] T019 [P] [US1] Add a test asserting every inline `data:` block under a cardinality-one relationship is a mapping, not a list — the R2 guard, so a stray dash fails in pytest rather than inside the SDK

**Checkpoint**: US1 complete and independently testable.

---

## Phase 4: User Story 2 — Every BGP session exists as two objects (Priority: P2)

**Goal**: the ten neighbour statements the six configs emit exist as objects, each reachable
from the site or peering that justifies it.

**Independent Test**: query `bgp_sessions` on all four sites and the internet peering — eight
sessions, with acme/dr returning zero and one static route.

### Implementation for User Story 2

- [X] T020 [US2] Add the `RoutingAsn` document to `objects/31a_nfd41_wan_addressing.yml` — 5 ASNs, each with `devices: [names]` using the reverse relationship, which avoids a `DcimDevice` upsert entirely (R3, R4)
- [X] T021 [US2] Add the `RoutingBGPNeighbor` document — 10 neighbours per [data-model.md](./data-model.md) §4, with `remote_as` quoted because the attribute is Text
- [X] T022 [US2] Move the `CUST_ACME` and `CUST_GLOBEX` `IpamVRF` definitions **out** of `objects/37_nfd41_wan_services.yml` and into `31a`, verbatim. A VRF is a technical-layer object; cycle 019 put them in a service file only because it was the cycle that needed them (R8)
- [X] T023 [US2] Verify the `ServiceL3vpn` objects remaining in `objects/37_nfd41_wan_services.yml` still resolve their `vrf` reference — file 37 sorts after `31a`, so they should
- [X] T024 [US2] Add the `RoutingVrfStaticRoute` document — one route, `10.60.11.0/24` via `10.51.11.2`, `vrf: CUST_ACME`, `devices: [isp-pe1]`
- [X] T025 [US2] In `objects/33_nfd41_wan.yml`, add `bgp_sessions` to the three BGP-attached sites — both ends each, referenced as `["<device>", "<peer_address>"]`
- [X] T026 [US2] Add `static_routes` to acme's DR site and **no `bgp_sessions`**. A session on a static site would be wrong, not merely redundant
- [X] T027 [US2] Add both ends of the transit session to `WanInternetPeering.bgp_sessions` in the same file

### Tests for User Story 2

- [X] T028 [US2] Add a two-directional parity test for ASNs, sessions and the static route against the lab file
- [X] T029 [P] [US2] Add a test asserting acme's DR site declares `static_routes` and no `bgp_sessions`, and that every BGP-attached site declares exactly two sessions
- [X] T030 [P] [US2] Add a test asserting `CUST_ACME` and `CUST_GLOBEX` are defined in exactly one file — the guard against the move leaving a copy behind

**Checkpoint**: US1 and US2 both work.

---

## Phase 5: User Story 3 — Every router names its own ID (Priority: P3)

**Goal**: `bgp router-id` has an explicit source for all six FRR-speaking routers.

**Independent Test**: query `router_id` on the six routers and compare to the lab's values.

### Implementation for User Story 3

- [X] T031 [US3] Add the `DcimDevice` document to `objects/31a_nfd41_wan_addressing.yml` — six routers with `name`, `status: active` and `router_id: ["<address>", "default"]` (form 4)
- [X] T032 [US3] Comment why `status` is restated: a top-level upsert validates every mandatory attribute (R3), and duplicating a constant is safer than the alternative, which would put six address strings into `objects/31_nfd41_offfabric_devices.yml` as inline blocks
- [X] T033 [US3] Give `cust-acme-dr-ce` no router ID — it runs no routing protocol

### Tests for User Story 3

- [X] T034 [P] [US3] Add a test asserting the six router IDs match the lab, that `cust-acme-dr-ce` has none, and that each loopback-sourced router ID is the same address string the loopback interface carries — one object, not a copy

**Checkpoint**: all three stories independently functional.

---

## Phase 6: Load, Verify, and Prove Idempotence

- [X] T035 Run `uv run infrahubctl object load objects/ --branch wan-obj` and resolve any load error using the symptom table in [quickstart.md](./quickstart.md) §2
- [X] T036 Compare post-load counts against T007's baseline: +20 interfaces, +20 addresses, +5 ASNs, exactly 10 `RoutingBGPNeighbor` and exactly 1 `RoutingVrfStaticRoute`
- [X] T037 Run the circuit traversal query from [quickstart.md](./quickstart.md) §4 — all four circuits, both sides, must return an interface and an address. A `null` interface means a missed endpoint link
- [X] T038 Run the sessions and router-ID query — three sites with two sessions, acme/dr with zero and one static route, six routers with a router ID and an ASN
- [X] T039 **Load a second time and re-run the count query.** The CLI prints "Created node" for an upsert, so the log is not evidence — only unchanged counts prove idempotence (SC-007)
- [X] T040 Run `grep -nE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' objects/33_nfd41_wan.yml` and confirm it returns nothing (SC-006)

---

## Phase 7: Documentation and Close-Out

- [X] T041 [P] Update `docs/docs/developer-guide/schemas.md` if it enumerates the WAN object files, adding `31a_nfd41_wan_addressing.yml` and noting the VRF relocation
- [X] T042 [P] Add the two SDK reference forms that fail — the HFID-less generic and the cardinality-one mapping — to the repository's developer guide, so the next object cycle does not rediscover them
- [X] T043 Write [acceptance-evidence.md](./acceptance-evidence.md): the oracle inventory, before and after counts, the four traversal outputs, the twice-loaded counts, and the SC-009 walk
- [X] T044 Run `uv run invoke test` and `uv run invoke lint` — ruff, mypy, yamllint, rumdl and Vale must all pass
- [~] T045 Run `$infrahub-run-integration-tests` on this branch. If it is not installed, say so explicitly in the pull request as the constitution's documented exception, and point at the non-live alternative in Phases 6 — do not omit it silently
- [X] T046 Walk [quickstart.md](./quickstart.md) §8 and answer SC-009: every line of the six rendered FRR configs has its data in the graph. This is the criterion that says the transform cycle can start
- [ ] T047 Delete the polluted `wan-addr` Infrahub branch, or record explicitly why it is being kept. It must never be merged (research open risk 1) — **held for the user**, along with T048
- [ ] T048 Merge to `main` and delete the `wan-obj` Infrahub branch — **held for the user.** The work is complete and verified, but the integration gate is an unmet documented exception (T045)

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies, but T005 blocks everything — without cycle 020's schema, no object here can load
- **Phase 2 (Foundational)**: after Setup. **Blocks every story** — T007 must precede any edit
- **Phase 3 (US1)**: after Phase 2. Creates the file and the interfaces every later story references
- **Phase 4 (US2)**: after US1's interfaces exist (T010–T012); the addresses are not required for sessions, since `peer_address` is a Text attribute
- **Phase 5 (US3)**: after US1's addresses exist (T013) — a router ID references an address object
- **Phase 6**: after all three stories
- **Phase 7**: after Phase 6

### Story dependencies

Not independent, unusually for this template, and the reason is the data rather than the
process: a router ID *is* an address, and an address *is* on an interface.

```text
US1 interfaces ──► US1 addresses ──► US3 router IDs
       │
       └──────────► US1 endpoint links
US1 interfaces ──► US2 sessions (devices only; peer_address is Text)
```

Both US1 and US2 also edit `objects/33_nfd41_wan.yml`, and US1, US2 and US3 all append to
`objects/31a_nfd41_wan_addressing.yml` and to the one test file. **No task that writes those
three files is marked `[P]`.**

### Parallel opportunities

- T008 alongside T006 and T007
- T018, T019, T029, T030 and T034 are all test-assertion tasks, parallel only if the test file
  is split or they are written in one sitting
- T041 and T042 — documentation, different sections

### Parallel example

```text
# Phase 2, three agents:
T006  parse the oracle
T007  baseline counts
T008  filename sort order

# Phases 3–5 are sequential: one file, one dependency chain.
```

---

## Implementation Strategy

**MVP**: Phases 1–3 (US1). Eight circuit ends resolving to real addresses repays the SC-008 debt
cycle 010 incurred and is the half of the cycle with the most rendered lines behind it.

**Full cycle**: all three stories. They share one file and one dependency chain, so splitting
delivery costs review cycles and saves nothing.

**What would make this cycle wrong**:

- A task that adds a schema file. Cycle 020 added everything needed; if something is
  unrepresentable, it belongs in a schema cycle first.
- A task that seeds an end host. Their device objects do not exist (spec assumption 2).
- Restating a lab value — an address, a prefix, a tenant — in a second file to satisfy a
  mandatory attribute. That is the failure this cycle exists to remove, and the reason the file
  layout is what it is.
