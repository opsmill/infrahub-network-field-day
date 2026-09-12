---

description: "Task list for the WAN FRR config render"
---

# Tasks: FRR Configuration for the WAN

**Input**: Design documents from `/specs/022-frr-config-render/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/transform-contract.md](./contracts/transform-contract.md)

**Tests**: **REQUIRED.** Constitution IV, and unusually strong here — 448 lines of golden output
this repository did not write. `tests/unit/test_frr_config.py` renders from captured fixtures and
compares for equality, so the gate needs no server.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: the user story from [spec.md](./spec.md) this task serves

## Before you start

**Phase 0 already rendered three of these six devices zero-diff from live data** — both customer
edges and `isp-pe1`, using the lab's templates unmodified. The port is mechanical. What is
unproven is the transform's own context assembly and the three devices never probed.

Four traps, all found by running the render rather than reading it:

1. **`StrictUndefined` is mandatory**, not stylistic. It caught two real context gaps at named
   template lines. Without it both would have rendered a config with a missing BGP neighbour,
   which vtysh accepts and which never comes up.
2. **Inline fragments in both directions.** `ip_addresses` needs `... on InterfaceLayer3` going
   interface→address; `name` needs `... on DcimInterface` going address→interface. Each fails
   outright without it.
3. **Site ordering is a rule**: BGP attachments before static, each by name. The lab's order is
   authoring order and Infrahub stores none.
4. **All four Jinja2 environment settings matter** — `undefined`, `trim_blocks`, `lstrip_blocks`,
   `keep_trailing_newline`. Three of them are what make the output byte-identical rather than
   merely correct.

---

## Phase 1: Setup

**Purpose**: a stack, a branch, and the data this cycle renders from.

- [X] T001 **Commit cycle 021 first.** Its object data is uncommitted on `021-wan-addressing-objects`, and this cycle reads its interfaces, addresses, sessions and router IDs. This is a prerequisite, not a tidy-up
- [X] T002 Verify preflight: `uv run infrahubctl info` shows Connection Status ✅ against Infrahub 1.10.6
- [X] T003 Export `INFRAHUB_API_TOKEN` from the stack's environment
- [X] T004 Create the git branch `022-frr-config-render` from wherever 021 landed
- [X] T005 Create the Infrahub branch `wan-render` with `--sync-with-git`, then load `schemas/` and `objects/` into it. Do not reuse `wan-obj` or `wan-addr` — both carry earlier cycles' state

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the query. Every story reads from it, and its two inline fragments are the thing
most likely to be got wrong.

**⚠️ CRITICAL**: no story can proceed until T007 passes.

- [X] T006 Write `transforms/frr_config.gql` per [contracts/transform-contract.md](./contracts/transform-contract.md) §2 — `$device: String!`, the target device with its role, `router_id`, `asn` and `RoutingBGPNeighbor` set, plus every `WanSite`, `ServiceL3vpn`, `ServiceTenantCloud`, `ServiceInternetAccess`, the `WanInternetPeering`, the three provider devices, and `IpamIPAddress` with `interface → device`
- [X] T007 Run the query against `wan-render` and confirm it is accepted. **Both inline fragments are required**: `... on InterfaceLayer3` for `ip_addresses` and `... on DcimInterface` for an interface's `name` and `device` (R5). Either omission is rejected with a message naming the fragment
- [X] T008 Regenerate `transforms/frr_config_query.py` with `uv run infrahubctl graphql generate-return-types transforms/frr_config.gql`. Never hand-write it (Constitution III)
- [X] T009 [P] Create `transforms/templates/frr/` and `tests/unit/fixtures/frr/`
- [X] T010 Capture the query response for all six devices into `tests/unit/fixtures/frr/<device>.json`. Captured from the live graph, never hand-written, so model drift cannot mask a rendering bug (FR-041)

**Checkpoint**: the query is proven and the fixtures exist. Story work can begin.

---

## Phase 3: User Story 1 — The customer edges and the branch render byte-for-byte (Priority: P1) 🎯 MVP

**Goal**: three of six devices render from the model, and the golden-file harness every later
story reuses exists.

**Independent Test**: render `cust-acme-ce`, `cust-globex-ce` and `branch-rtr`; diff each against
`../lab/wan/rendered/<device>/frr.conf`, normalising only the provenance line. Zero diff.

### Implementation for User Story 1

- [X] T011 [US1] Port `../lab/wan/templates/customer-ce.frr.conf.j2` to `transforms/templates/frr/customer-ce.j2`, changing **only** the provenance line to name Infrahub. Every comment stays — they explain why the prefix-list exists and why the PE is where isolation is enforced (FR-021)
- [X] T012 [US1] Port `branch-router.frr.conf.j2` to `transforms/templates/frr/branch-router.j2` the same way
- [X] T013 [US1] Write `transforms/frr_config.py` with the `FrrConfig` class, `query = "frr_config"`, wrapping `data` in the generated `FrrConfigQuery` model as `transforms/avd_eos_config.py` does (R8)
- [X] T014 [US1] Build the Jinja2 environment with `FileSystemLoader(f"{self.root_directory}/transforms/templates/frr")` and **all four** settings: `undefined=StrictUndefined`, `trim_blocks=True`, `lstrip_blocks=True`, `keep_trailing_newline=True`
- [X] T015 [US1] Select the template from the device's `role`, per [data-model.md](./data-model.md) — not from its name, so a second router of an existing role needs no code change
- [X] T016 [US1] Assemble the customer-edge context: `isp.asn`, `isp.edge.node`, `tenant.name`, and the site's `name`, `asn`, `lan`, `ce.lan_address` and `pe.address`. The CE's own address comes from its `router_id`; the PE's from the CE-side session's `peer_address` plus `/30`
- [X] T017 [US1] Assemble the branch context: its ASN, its loopback-derived router id, its LAN prefix, and its single `RoutingBGPNeighbor` toward `border-leaf1`. The branch names no ISP at all
- [X] T018 [US1] Raise a named error when a required value is absent, rather than rendering a blank field (FR-013)

### Tests for User Story 1

- [X] T019 [US1] Create `tests/unit/test_frr_config.py` with a helper that loads a fixture, renders it, and compares against the golden file with only the provenance line normalised
- [X] T020 [US1] Add golden-file equality tests for `cust-acme-ce`, `cust-globex-ce` and `branch-rtr`. **Equality, not substring matching** — a substring test passes on a config with a missing neighbour
- [X] T021 [P] [US1] Add a test asserting a missing required value raises rather than returning text with a blank

**Checkpoint**: US1 complete, three devices rendering, harness in place.

---

## Phase 4: User Story 2 — The provider edge renders, and the service layer shows (Priority: P2)

**Goal**: `isp-pe1` and `isp-pe2` render byte-for-byte, and the difference between acme and
globex is visible as routing policy.

**Independent Test**: diff both against the lab. Then remove acme's `ServiceInternetAccess` on a
branch and confirm the six-line change SC-003 describes.

### Implementation for User Story 2

- [X] T022 [US2] Port `isp-edge.frr.conf.j2` (144 lines) to `transforms/templates/frr/isp-edge.j2`, provenance line only
- [X] T023 [US2] Port `isp-core.frr.conf.j2` (127 lines) to `transforms/templates/frr/isp-core.j2`
- [X] T024 [US2] Extend the context with `tenants[]` — name, `vrf` from `ServiceL3vpn`, `dc.subnet` from `ServiceTenantCloud`, and `internet` computed as **whether a `ServiceInternetAccess` exists for that tenant's L3VPN**. That last one is the architecture paying off; it is not an attribute anywhere
- [X] T025 [US2] Add `isp.dc_service_prefixes` from `ServiceL3vpn.dc_service_prefixes` — the shared DC range, identical on every L3VPN. Cycle 021 corrected this data; do not re-derive it per tenant
- [X] T026 [US2] Add the device-scoped sessions: `isp.edge.core.peer` (the iBGP session toward the core) and the core's handoff toward `border-leaf1`. **No `WanSite` names these** — they are provider infrastructure, and `StrictUndefined` will name the template line if they are missing (R3)
- [X] T027 [US2] Resolve a static site's `ce.node` through the static route's `next_hop` → interface → device. A static attachment has no session, so the CE is not reachable the way a BGP site's is (R4)
- [X] T028 [US2] Order each tenant's sites **BGP first, then static, each by name** (R6). Alphabetical ordering leaves a two-line diff in the per-tenant site-inventory comment
- [X] T029 [US2] Order the tenants themselves deterministically, so the two VRF blocks and two import route-maps render in the oracle's order

### Tests for User Story 2

- [X] T030 [US2] Add golden-file equality tests for `isp-pe1` and `isp-pe2`
- [X] T031 [US2] Add a test that renders `isp-pe1` twice — once with acme's internet-access service present in the fixture and once without — and asserts the diff is exactly the six lines SC-003 names: four for the `permit 30` clause and its separator, plus the tenant header flipping from `internet: yes` to `internet: no`
- [X] T032 [P] [US2] Add a test asserting `PL-DEFAULT` survives that removal, because it is guarded by the ISP having an internet connection rather than by a tenant buying access
- [X] T033 [P] [US2] Add a test asserting acme's DR site contributes `ip route 10.60.11.0/24 10.51.11.2` inside `vrf CUST_ACME` and `redistribute static` in that VRF's address family

**Checkpoint**: five of six devices rendering; the service layer is demonstrable.

---

## Phase 5: User Story 3 — The internet router renders (Priority: P3)

**Goal**: `internet-rtr` renders as AS 64500, completing the set.

**Independent Test**: diff against the lab's file.

### Implementation for User Story 3

- [X] T034 [US3] Port `internet-rtr.frr.conf.j2` to `transforms/templates/frr/internet-rtr.j2`
- [X] T035 [US3] Add the internet context: `isp.internet.asn`, `customer_aggregate`, the peering's two session ends, and the internet LAN

### Tests for User Story 3

- [X] T036 [P] [US3] Add a golden-file equality test for `internet-rtr`
- [X] T037 [P] [US3] Add a test asserting the inbound prefix-list permits `10.60.0.0/16 le 24` and denies the rest

**Checkpoint**: all six devices render from fixtures.

---

## Phase 6: Registration and Live Verification

- [X] T038 Add the `frr_routers` `CoreStandardGroup` to `objects/00_groups.yml` with exactly the six FRR-speaking routers as members
- [X] T039 **Exclude `cust-acme-dr-ce`.** It shares the `customer_edge` role, so a role-derived group would capture it and produce a seventh artifact for a device the lab renders no FRR config for (R9, FR-031)
- [X] T040 Register the query, the transform and the artifact definition in `.infrahub.yml` per [contracts/transform-contract.md](./contracts/transform-contract.md) §1 — `content_type: text/plain`, `targets: frr_routers`, `parameters: {device: name__value}`
- [X] T041 Verify `transformation` matches the `python_transforms` name and the class's `query` matches the registered query name. A mismatch in either fails silently — the artifact just never generates
- [X] T042 Render all six devices live against `wan-render` and diff against the lab, per [quickstart.md](./quickstart.md) §3. All six must be zero diff
- [X] T043 Confirm the artifact definition generates six artifacts and no seventh (SC-006)
- [X] T044 Run the SC-003 demonstration live on a throwaway branch, per [quickstart.md](./quickstart.md) §5

---

## Phase 7: Documentation and Close-Out

- [X] T045 [P] Add the transform, its query and its artifact to the inventories in `AGENTS.md` — it lists every generator, transform and check, and a new transform belongs there
- [X] T046 [P] Document the render in `docs/docs/developer-guide/transforms.md`, including that the WAN now renders from Infrahub and the lab's `render.py` is redundant
- [X] T047 [P] Record the two inline-fragment directions in the developer guide, so the next transform does not rediscover them
- [X] T048 Write [acceptance-evidence.md](./acceptance-evidence.md): the six zero-diff results, the SC-003 diff, the artifact count, and the SC-009 walk
- [X] T049 Run `uv run invoke test` and `uv run invoke lint` — ruff, mypy, yamllint, rumdl and Vale must all pass
- [ ] T050 Run `$infrahub-run-integration-tests`. If it is not installed, say so explicitly in the pull request as the constitution's documented exception and point at the live verification in Phase 6 — do not omit it silently
- [X] T051 Answer SC-009 per [quickstart.md](./quickstart.md) §7: what does `../lab/wan/tenants.yml` still hold that the graph does not? Expected answer — the host entries, the branch's bridged access ports, and `mtu`. Everything that drives a routing decision is in the graph
- [ ] T052 Merge to `main` and delete the `wan-render` Infrahub branch — **held for the user.** The work is complete and verified, but the integration gate is an unmet documented exception (T050)

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: T001 blocks everything — without cycle 021's data there is nothing to render
- **Phase 2 (Foundational)**: after Setup. **Blocks every story** — all three read from one query
- **Phase 3 (US1)**: after Phase 2. Creates the transform class and the test harness
- **Phase 4 (US2)**: after US1, because it extends US1's transform and reuses its harness
- **Phase 5 (US3)**: after US1 for the same reason; independent of US2
- **Phase 6**: after every story whose devices are being verified
- **Phase 7**: after Phase 6

### Story dependencies

Not independent, and the reason is the shared transform rather than the data:

```text
Phase 2 query ──► US1 (transform class + harness) ──► US2 (extends the context)
                                                 └──► US3 (extends the context)
```

US2 and US3 touch the same `transforms/frr_config.py` and the same test module, so they are
**not** parallel with each other. Their templates are separate files and can be ported in
parallel.

### Parallel opportunities

- T009 alongside T006–T008
- T011, T012, T022, T023, T034 — five template ports, five separate files, no shared state
- T032, T033, T036, T037 — assertion tasks, if the test module is not being edited concurrently
- T045, T046, T047 — documentation, different files

### Parallel example

```text
# After Phase 2, port every template at once — they share nothing:
T011 customer-ce.j2   T012 branch-router.j2   T022 isp-edge.j2
T023 isp-core.j2      T034 internet-rtr.j2

# Then serialize the transform and test edits: T013-T018, T024-T029, T035
```

---

## Implementation Strategy

**MVP**: Phases 1–3 (US1). Three of six devices rendering from the model, plus the golden-file
harness. Worth shipping alone: the branch router and both customer edges are real configs the
lab runs.

**Full cycle**: all three stories. They share one transform and one test module, so splitting
delivery costs review cycles and saves nothing — and US2 is where the cycle's actual argument
lives.

**What would make this cycle wrong**:

- A task that changes a schema. Cycles 020 and 021 supplied the model and the data; if something
  is unrepresentable it belongs in a schema cycle first.
- A task that seeds object data beyond the group. The group exists only because an artifact
  definition cannot target one that does not exist.
- A test that checks for substrings instead of file equality. It would pass on a config with a
  missing BGP neighbour, which is precisely the failure the last three cycles were about.
- Dropping the templates' comments to make the diff smaller. They are most of the teaching value
  of these configs, and FR-021 requires them.
