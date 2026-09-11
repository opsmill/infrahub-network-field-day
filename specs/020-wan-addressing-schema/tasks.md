---

description: "Task list for the WAN addressing schema"
---

# Tasks: Making the WAN's Addressing Real

**Input**: Design documents from `/specs/020-wan-addressing-schema/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/schema-contract.md](./contracts/schema-contract.md)

**Tests**: **REQUIRED.** Constitution IV. `tests/unit/test_wan_schema_contract.py` already
exists and is the gate for this cycle — it reads the schema YAML directly, so it needs no
running server.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: the user story from [spec.md](./spec.md) this task serves

## A note on ordering

[plan.md](./plan.md) sequences `wan/wan.yml` first, on the grounds that it is the one step that
can fail interestingly. That ordering was written before Phase 0 retired the risk: R6 proved
the tombstone works against the live instance, both with and without. The phases below
therefore run in user-story priority order instead, which is the normal arrangement, and the
difference is deliberate rather than an oversight. If T014 does fail, the fallback is in R6 and
costs one line.

---

## Phase 1: Setup

**Purpose**: a working stack and a branch to work on.

- [X] T001 Verify preflight: `uv run infrahubctl info` shows Connection Status ✅ against Infrahub 1.10.6
- [X] T002 Export `INFRAHUB_API_TOKEN` from the stack's environment — `schema check` returns `401 Unauthorized` without it, and the failure does not mention authentication in its first line
- [X] T003 Create the git branch `020-wan-addressing-schema` from `main`
- [X] T004 Create the Infrahub branch `wan-addr` with `uv run infrahubctl branch create wan-addr --sync-with-git`, and target every `schema load` in this cycle at it rather than at `main`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: capture the "before" state, because two success criteria are statements about a
change and cannot be evaluated against the "after" alone.

**⚠️ CRITICAL**: T006 must run *before* any schema file is edited. Once the tombstone has been
loaded, the failure it guards against can no longer be observed.

- [X] T005 Re-confirm R1 before scoping US3: `grep -n "loopback" schemas/dcim_extensions.yml` must show the `loopback` and `vtep_loopback` role choices already present. If they are absent, FR-020 is back in scope and this cycle is five changes, not four
- [X] T006 Record the live schema's current relationship names for `WanSite`, `WanInternetPeering`, `DcimCircuitEndpoint` and `DcimDevice`, using the read-back command in [quickstart.md](./quickstart.md) §3. Save the output into [acceptance-evidence.md](./acceptance-evidence.md) as the "before" block — `WanSite` must show `bgp_session`, and that line is what SC-006's removal proof is measured against
- [X] T007 [P] Confirm the adopted file's baseline: `git log -1 --format=%H -- schemas/circuit/circuit.yml`, recorded so SC-009 can be checked as "unchanged since" rather than by eye

**Checkpoint**: the before-state is recorded; story work can begin.

---

## Phase 3: User Story 1 — A circuit end names its interface and its address (Priority: P1) 🎯 MVP

**Goal**: `circuit → endpoint → interface → ip_addresses` resolves end to end, so the PE↔CE
addresses stop living in description prose.

**Independent Test**: create a circuit endpoint pointing at an interface that carries an
address, and traverse to the address in one GraphQL query. Delivers value alone: the circuit
model stops lying even if US2 and US3 are dropped.

### Implementation for User Story 1

- [X] T008 [US1] Create `schemas/circuit_extensions.yml` with the `extensions:` block from [contracts/schema-contract.md](./contracts/schema-contract.md) §1 — `DcimCircuitEndpoint.interface`, peer `DcimInterface`, `kind: Attribute`, `cardinality: one`, `optional: true`, `identifier: circuit_endpoint__interface`, `order_weight: 960`
- [X] T009 [US1] Open the file with the `$schema` comment and `version: "1.0"`, matching the five existing `*_extensions.yml` files
- [X] T010 [US1] Write the file's header comment explaining *why* it exists — `circuit/circuit.yml` is marketplace-adopted at 1.0.1 and stays byte-identical, so additions live here. A reader who does not know that will try to edit the adopted file
- [X] T011 [US1] Peer with the `DcimInterface` **generic**, not `InterfacePhysical`. R5: a concrete peer works for every WAN circuit today and fails the first time one terminates on a sub-interface

### Tests for User Story 1

- [X] T012 [US1] Add to `tests/unit/test_wan_schema_contract.py` a test asserting `DcimCircuitEndpoint` gains `interface` with peer `DcimInterface` and `cardinality: one`, reading `schemas/circuit_extensions.yml` through the existing `_extension_nodes` helper
- [X] T013 [P] [US1] Add a test asserting `schemas/circuit/circuit.yml` declares no `interface` relationship on `DcimCircuitEndpoint` — this is what pins the addition to the extension file rather than to the adopted one (SC-009)

**Checkpoint**: US1 is complete and independently testable.

---

## Phase 4: User Story 2 — Every BGP session in the WAN has a home (Priority: P2)

**Goal**: both ends of every session are reachable from the object that justifies them.

**Independent Test**: attach two `RoutingBGPNeighbor` objects to one `WanSite` and two to a
`WanInternetPeering`; query each from the service side. A statically attached site with zero
sessions stays valid.

### Implementation for User Story 2

- [X] T014 [US2] In `schemas/wan/wan.yml`, replace `WanSite.bgp_session` with the two entries in [contracts/schema-contract.md](./contracts/schema-contract.md) §2 — the `state: absent` tombstone first, then `bgp_sessions` at `cardinality: many` with identifier `wan_site__bgp_sessions`
- [X] T015 [US2] Comment the tombstone in the schema file itself with the reason and the removal condition: a schema load is an upsert, so deleting the entry would leave the old relationship live while `schema check` reported nothing; remove it once the instance has been rebuilt from empty
- [X] T016 [US2] Add `WanInternetPeering.bgp_sessions` per §3 — `cardinality: many`, identifier `internet_peering__bgp_sessions`, `order_weight: 950`. Many, not one: the transit link is `neighbor 10.52.0.2` on isp-pe2 *and* `neighbor 10.52.0.1` on internet-rtr, which is two device-scoped objects (R8). This corrects FR-004, which specified cardinality one
- [X] T017 [US2] Keep both relationships optional — acme's DR site is `attachment_kind: static` and has no session at all (FR-006, FR-012)

### Tests for User Story 2

- [X] T018 [US2] Re-point `test_site_reuses_existing_routing_kinds_for_both_handoffs` in `tests/unit/test_wan_schema_contract.py` from `bgp_session` to `bgp_sessions`, and **add** an assertion that its cardinality is `many`. Do not loosen the test to accept either name — that would remove the guard this cycle depends on (FR-043)
- [X] T019 [US2] Add a test asserting the `bgp_session` tombstone is still present with `state: absent`, so a future tidy-up that deletes it has to do so deliberately
- [X] T020 [P] [US2] Add a test asserting `WanInternetPeering.bgp_sessions` exists with peer `RoutingBGPNeighbor` and `cardinality: many`

**Checkpoint**: US1 and US2 both work independently.

---

## Phase 5: User Story 3 — A router knows its own ID (Priority: P3)

**Goal**: `bgp router-id` has an explicit source that does not depend on inferring which
interface is "the" loopback.

**Independent Test**: set a device's router ID to an existing address object and read it back.

### Implementation for User Story 3

- [X] T021 [US3] Add `DcimDevice.router_id` to `schemas/dcim_extensions.yml` per §4 — peer `IpamIPAddress`, `kind: Attribute`, `cardinality: one`, `optional: true`, `identifier: device__router_id`. Place it among the existing `loopback_ip` / `vtep_loopback_ip` / `mgmt_ip` relationships, whose shape it copies exactly
- [X] T022 [US3] Keep it distinct from `loopback_ip` and comment why: three of the six WAN routers use a non-loopback address as their router ID — the customer edges use their LAN address and internet-rtr uses its peering address — so reusing `loopback_ip` would record a falsehood, and deriving it would be wrong half the time and silently, because a mismatched router-id still forms a session (R3)
- [X] T023 [US3] Do **not** add a `loopback` interface role. It already exists — confirmed in T005 and recorded as R1; FR-020 and FR-021 are withdrawn

### Tests for User Story 3

- [X] T024 [P] [US3] Add a test asserting `DcimDevice.router_id` exists with peer `IpamIPAddress`, `cardinality: one`, `optional: true`, and an identifier distinct from `device__ip_address`

**Checkpoint**: all three stories are independently functional.

---

## Phase 6: Validation, Regeneration and Evidence

**Purpose**: prove the four changes landed and nothing else did.

- [X] T025 Run `uv run infrahubctl schema check schemas/` and confirm the diff matches [contracts/schema-contract.md](./contracts/schema-contract.md) §6 exactly — four additions and one removal, nothing more
- [X] T026 **Confirm `bgp_session` appears under `removed:`.** If `bgp_sessions` is added but nothing is removed, the tombstone did not take, and the old cardinality-one relationship will survive on the server with no warning. This is the one failure this cycle can ship without noticing (R6)
- [X] T027 Run `uv run infrahubctl schema load schemas --branch wan-addr`. This is the first time `state: absent` has been *loaded* rather than checked; if it is rejected, fall back to R6's rejected alternative — widen in place under the singular name — and revise T014, T018 and the contract accordingly
- [X] T028 Read the live schema back per [quickstart.md](./quickstart.md) §3 and confirm `bgp_session` is gone from `WanSite` while `bgp_sessions`, `interface` and `router_id` are present with the expected cardinalities
- [X] T029 Run `uv run infrahubctl object load objects/` **twice** against the branch. Every existing object must load unchanged both times — the proof that keeping all four relationships optional did what it was for (FR-041, SC-002)
- [X] T030 Regenerate `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py` and commit the result. Never hand-edit it (Constitution III)
- [X] T031 Run `uv run mypy --show-error-codes src/solution_arista_avd` against the regenerated protocols (SC-007)
- [X] T032 Verify `git diff --stat schemas/circuit/circuit.yml` is empty (SC-009)

---

## Phase 7: Documentation and Close-Out

- [X] T033 [P] Add `router_id` to the `DcimDevice` relationship list in `docs/docs/developer-guide/schemas.md` line ~229, beside `loopback_ip` / `mgmt_ip` / `asn`, noting that it is explicit because it is not always a loopback
- [X] T034 [P] Document `schemas/circuit_extensions.yml` in the schema-file table in `docs/docs/developer-guide/schemas.md` (~line 55, beside the marketplace `circuit/circuit.yml` row), so the adopted file and its extension are visible together
- [X] T035 [P] Note the `WanSite.bgp_sessions` cardinality and the transit peering's sessions wherever the WAN kinds are described in `docs/docs/developer-guide/`
- [X] T036 Write [acceptance-evidence.md](./acceptance-evidence.md) with the before/after schema read-backs, the `schema check` diff, the twice-run object load, and the SC-006 inventory from [quickstart.md](./quickstart.md) §7
- [X] T037 Run `uv run invoke test` and `uv run invoke lint` — ruff, mypy, yamllint, rumdl and Vale must all pass with zero unaddressed findings (Constitution IV)
- [~] T038 Run `$infrahub-run-integration-tests` on branch `020-wan-addressing-schema`, recording branch and commit. If it cannot run in this environment, say so explicitly in the pull request as the constitution's documented exception — do not omit it silently (see plan.md, "Integration testing")
- [X] T039 Walk [quickstart.md](./quickstart.md) §7 and confirm SC-006: every remaining row in the six rendered configs is blocked on object data, with no row left whose obstacle is schema. This is the criterion that says the next cycle can start
- [ ] T040 Merge to `main`, then delete the Infrahub branch `wan-addr` — **held for the user.** The work is complete and verified, but the integration gate is an unmet documented exception (T038), and merging to `main` is the maintainer's call, not the implementer's

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Foundational)**: after Setup. **Blocks every story** — T006 must capture the before-state before any schema edit
- **Phases 3–5 (Stories)**: after Phase 2. Mutually independent — each touches a different file
- **Phase 6 (Validation)**: after every story phase whose changes are being validated
- **Phase 7 (Close-out)**: after Phase 6

### Story dependencies

None. US1 touches `schemas/circuit_extensions.yml`, US2 touches `schemas/wan/wan.yml`, US3
touches `schemas/dcim_extensions.yml`. Any one can ship without the others; all three land in
one `schema check`.

The only shared file is `tests/unit/test_wan_schema_contract.py`, which every story appends to.
Tasks within it are therefore **not** marked `[P]` across stories.

### Parallel opportunities

- T007 alongside T005 and T006
- The three implementation tasks T008, T014 and T021 — different files, no shared state
- T013, T020 and T024 once their story's implementation task is done, if the test file is not
  being edited concurrently
- T033, T034 and T035 — all documentation, different sections

### Parallel example

```text
# After Phase 2, one agent per story:
T008–T011  (US1)  schemas/circuit_extensions.yml
T014–T017  (US2)  schemas/wan/wan.yml
T021–T023  (US3)  schemas/dcim_extensions.yml
# Then serialize the test edits: T012, T018, T019, T024
```

---

## Implementation Strategy

**MVP**: Phase 1 → Phase 2 → Phase 3 (US1). That alone repays the SC-008 debt cycle 010
incurred, and makes the largest of the five gaps queryable.

**Full cycle**: all three stories land together. They are small, independent, and validated by
one `schema check`, so splitting the delivery would cost three review cycles to save nothing.

**What would make this cycle wrong**: a task that writes to `objects/`. Seeding the interfaces,
addresses, ASNs and sessions this schema makes expressible is the next cycle, and a `tasks.md`
containing an `objects/` file is the signal that scope has crept (plan.md, Risks).
