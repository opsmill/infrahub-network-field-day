# Tasks: A Device Kind for Fabric Switches

**Cycle**: 027 | **Branch**: `027-fabric-switch-kind`
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md),
[contracts/schema-contract.md](./contracts/schema-contract.md),
[quickstart.md](./quickstart.md)

## Two things to read before starting

**1. The scope figures were corrected while these tasks were generated.** Phase 0 said "3
queries, 6 fragments, 5 Python places". Generating tasks required naming every file, so the grep
covered `checks/`, `src/` and Python string literals for the first time: it is **6 query roots, 20
fragments, 12 call sites, 7 kind-name strings and 3 mutation strings**. [research.md](./research.md)
R8 records how that happened. Every count below was re-derived, not copied.

**2. The dangerous sites are not GraphQL.** Three are Python comparing a kind as a string, which
no fragment grep reaches. The worst is `transforms/containerlab_topology.py:202`:

```python
if node.typename != "DcimDevice" or node.name is None or not node.name.value:
    continue
```

After the split that skips all seven switches and emits a topology with seven servers, no
switches, **no error and valid YAML**. T041 exists for it alone.

## Why the contract tests go in first

Not ritual. C6e — every relationship identifier's two ends naming the same peer — **passes today**
and must keep passing after each of 13 peer edits. It turns thirteen reviews into one number. And
cycle 024 proved the need: a careless global `sed` flipped five unrelated peers and *nothing*
would have caught it.

---

## Phase 1: Setup

- [X] T001 Confirm the working tree carries only `specs/027-fabric-switch-kind/` — the plan phase measured against the live graph but implemented nothing, so `git status --short` must show no `schemas/`, `objects/`, `transforms/`, `generators/`, `checks/`, `src/` or `tests/` change
- [X] T002 Record the test baseline: `uv run pytest tests/unit -q --collect-only` must report **1043**, so T060 has something to compare against
- [X] T003 Capture the artifact baseline into `/tmp/027-baseline/` per [quickstart.md](./quickstart.md) step 0 — all **33** artifacts across 10 definitions (7 EOS configs, 7 device docs, 7 ANTA catalogs, 1 fabric doc, 1 cabling plan, 1 ContainerLab topology, 2 Crossplane manifests, 6 FRR configs, 1 Junos config)
- [X] T004 Record the ContainerLab topology's **node and link counts** (expect 14 and 17) and the cabling plan's **row count** (expect 17) separately from T003 — these are the numbers that catch the silent `typename` failure, and a whole-file diff of a YAML topology is harder to read than two integers
- [X] T005 Record the kind counts: `DcimDevice` 14, `DcimGenericDevice` 22 `{DcimDevice 14, ComputePhysicalServer 7, SecurityFirewall 1}`, for T054

**⚠️ T003 to T005 cannot be repeated.** Once the environment is rebuilt in T052 the pre-cycle
output no longer exists, and re-deriving it afterwards proves only that the new code agrees with
itself.

---

## Phase 2: Foundational — the measurements that make 13 peer edits verifiable

**⚠️ BLOCKING**: no schema task may begin until T006 passes.

- [X] T006 Create `tests/unit/test_dcim_schema_contract.py` with clause **C6e**: parse every `identifier:` in `schemas/**/*.yml`, group by identifier name, and assert that where an identifier appears on two ends both name the **same** peer. It must **pass on the unmodified tree** — if it fails now, the test is wrong, not the schema
- [X] T007 Add clause **C8** to `tests/unit/test_routing_schema_contract.py`: extend the pinned complete `Dcim*` peer map with the `DcimFabricSwitch` entries and the two widened peers. This is cycle 024's safety net and this cycle edits 13 peer lines — the same hazard, larger
- [X] T008 [P] Add clauses **C1** to **C5** to `tests/unit/test_dcim_schema_contract.py` (node exists and inherits exactly three generics; the twelve moved fields present on the new kind and **absent** from `DcimDevice`; the three that stay; the six shared; the two disjoint role dropdowns). All five fail
- [X] T009 [P] Add clauses **C9**, **C10**, **C11a** to `tests/unit/test_dcim_schema_contract.py`: 6 query roots retargeted, `transforms/frr_config.gql` byte-identical, and all 20 fragment sites given a disposition. All fail except C10
- [X] T010 Add clause **C11b/C11c** to `tests/unit/test_dcim_schema_contract.py`: no hand-written Python outside `*_query.py` contains the string `"DcimDevice"` where it names the kind of a fabric device, and no `DcimDeviceUpsert` string remains in `generators/asn.py` or `src/solution_arista_avd/generator.py`. **This is the only clause that can catch the three silent failures**

**Checkpoint**: T006 green on the untouched tree; T007–T010 failing for the right reasons.

---

## Phase 3: User Story 1 — A router no longer carries fabric fields (P1) 🎯 MVP

**Goal**: `isp-pe1` stops exposing `vtep_loopback_ip`, `mlag_domain` and `evpn_gateway_group`; a
spine gains them.

**Independent test**: `infrahubctl schema check schemas/` passes with a diff naming exactly
`DcimFabricSwitch` added and `DcimDevice` changed; C1–C6 pass.

### The node and its fields

- [X] T011 [US1] Add the `FabricSwitch` node to `schemas/base/dcim.yml` beside `DcimDevice`, namespace `Dcim`, `inherit_from` **exactly** `[CoreArtifactTarget, DcimGenericDevice, DcimPhysicalDevice]`, copying `DcimDevice`'s `human_friendly_id`, `display_label` and `order_by` (C1, C7)
- [X] T012 [US1] Run `uv run infrahubctl schema check schemas/` — the diff must name **one added kind and nothing else**. Do **not** `schema load` onto the live instance; T003's baseline is still needed
- [X] T013 [US1] Move the twelve fields in `schemas/dcim_extensions.yml` from the `DcimDevice` entry to a new `DcimFabricSwitch` entry: `vtep_loopback_ip`, `mlag_domain`, `evpn_gateway_group`, `node_id`, `index`, `pod`, `rack`, `avd_artifact`, `object_template`, `loopback_ip`, `mgmt_ip`, `avd_custom_hostvars` (C2)
- [X] T014 [US1] Confirm `router_id`, `bgp_neighbors` and `location` stayed on `DcimDevice` (C3), and that `status`, `role`, `rack_face`, `asn`, `device_type`, `platform` resolve on both (C4)
- [X] T015 [US1] Split the `role` dropdown in `schemas/dcim_extensions.yml`: `DcimFabricSwitch` gets exactly the ten keys of `ROLE_TO_AVD_TYPE`; `DcimDevice` keeps exactly `isp_edge`, `isp_core`, `internet_edge`, `customer_edge`, `branch_router`, `k8s_node`. Keep the existing comment block explaining why there is no `firewall` value — it is now describing a second precedent (C5)
- [X] T016 [US1] Run `uv run pytest tests/unit/test_dcim_schema_contract.py -q` — C1 to C5 now pass; C6e must still pass

### The thirteen reverse sides — one file at a time

**⚠️ Anchor every edit on a unique surrounding block. A global `sed` on `peer: DcimDevice` flips
all thirteen, including the four that must not move — the exact mistake of cycle 024.** Re-run
C6e (T006) after each task below.

- [X] T017 [P] [US1] `schemas/logical_design.yml:169` — `NetworkPod.devices` (identifier `pod__device`, 7 objects, all switches) → `DcimFabricSwitch`
- [X] T018 [P] [US1] `schemas/objects/objects.yml:21` — `AvdArtifact.device` (7 objects, all switches) → `DcimFabricSwitch`
- [X] T019 [P] [US1] `schemas/mlag/mlag.yml:136` — `MlagDomain.peers` (identifier `device__mlag_domain`, 2 domains over 4 leaves) → `DcimFabricSwitch`
- [X] T020 [P] [US1] `schemas/evpn/evpn_services.yml:196` — `EvpnSviNode.device` (8 objects, all leaves; **no forward side on `DcimDevice`**) → `DcimFabricSwitch`
- [X] T021 [P] [US1] `schemas/evpn/evpn_gateway.yml:182` — `EvpnGatewayGroup.members` (**0 objects**, border-leaf-only by definition) → `DcimFabricSwitch`
- [X] T022 [US1] `schemas/routing/vrf_services.yml:163` — `RoutingVrfBgpPeer.devices` (5 objects, all leaves; no forward side) → `DcimFabricSwitch`
- [X] T023 [US1] `schemas/routing/vrf_services.yml:234` — `RoutingVrfL3Interface.device` (8 objects, all `leaf-nfd41-pod1-3-1`; no forward side) → `DcimFabricSwitch`
- [X] T024 [US1] `schemas/routing/vrf_services.yml:66` — `RoutingVrfStaticRoute.devices` → **`DcimGenericDevice`, not `DcimFabricSwitch`**. Its 10 objects span `isp-pe1` **and** `leaf-nfd41-pod1-3-1` — the two ends of one tenant handoff. Nothing in the name says so; only the count did
- [X] T025 [US1] `schemas/routing/routing.yml:190` — `RoutingAsn.devices` → **`DcimGenericDevice`**, because `asn` is on both kinds (C4) and a reverse side cannot name two concrete kinds. Same shape as cycle 024's widening; the comment at `routing.yml:403` already explains why
- [X] T026 [US1] Confirm the four that **must not move** are untouched in `schemas/routing/routing.yml`: `RoutingBGPNeighbor.device` (:143, 10 objects all routers), `RoutingBGPPeerGroup.device` (:87), `RoutingPrefixList.device` (:226), `RoutingRouteMap.device` (:288)
- [X] T027 [US1] Confirm `LocationRack.devices` in `schemas/location_extensions.yml:101` still peers `DcimPhysicalDevice` and needs **no** change — `rack` moves, its reverse does not move with it
- [X] T028 [US1] `uv run infrahubctl schema check schemas/` — **criterion corrected during implementation**: the diff names `DcimFabricSwitch` added, `DcimDevice` changed, **and the nine kinds whose reverse side was retargeted** (AvdArtifact, EvpnGatewayGroup, EvpnSviNode, MlagDomain, NetworkPod, RoutingAsn, RoutingVrfBgpPeer, RoutingVrfL3Interface, RoutingVrfStaticRoute). "Nothing else" was wrong — changing a reverse side necessarily changes its owning kind's entry. A **tenth** kind is the failure signal
- [X] T029 [US1] `uv run pytest tests/unit/test_dcim_schema_contract.py tests/unit/test_routing_schema_contract.py -q` — C1–C8 green, C6e still green

**Checkpoint US1**: the schema split is complete and self-consistent. Nothing downstream works yet.

---

## Phase 4: User Story 2 — The AVD pipeline still renders every switch (P1)

**Goal**: seven EOS configs, byte-for-byte what they are today.

**Independent test**: quickstart steps 6–10 — rebuild, generate, and diff against `/tmp/027-baseline/`.

### The six query roots

- [ ] T030 [P] [US2] `generators/avd_device_hostvar.gql:2` — `DcimDevice(name__value: $name)` → `DcimFabricSwitch(...)`
- [ ] T031 [P] [US2] `transforms/avd_device_config.gql:2` — same
- [ ] T032 [P] [US2] `transforms/avd_anta_catalog.gql` — **two** roots, `:2` (`target:`) and `:31`. The second is the one a single-site fix misses
- [ ] T033 [P] [US2] `transforms/avd_fabric_devices.gql:12` — root `DcimDevice {` → `DcimFabricSwitch {`
- [ ] T034 [P] [US2] `checks/cv_config_check.gql:15` — root `DcimDevice {` → `DcimFabricSwitch {`
- [ ] T035 [US2] Confirm `transforms/frr_config.gql:6` and `:30` are **unchanged** — `git diff transforms/frr_config.gql` must be empty (C10). This is the file that "change every `DcimDevice`" would break

### The twenty fragment sites

- [ ] T036 [US2] `generators/avd_device_hostvar.gql` — five fragments at `:319`, `:434`, `:779`, `:937`, `:1003`. `:319` and `:434` read `name` and `role`; `:779`, `:937`, `:1003` read `role` (and `asn` at `:1003`) with `name` already outside the fragment. `name` moves to `... on DcimGenericDevice`; `role` needs **both** concrete fragments, because C5 makes the two dropdowns different enumerations
- [ ] T037 [P] [US2] `generators/generate_avd.gql:25`, `generators/backfill_structured_config.gql:15`, `generators/generate_fabric_peering.gql:89` — one fragment each, all reading `name`/`role` off a device reached through a link or pod
- [ ] T038 [P] [US2] `checks/fabric_pool_check.gql:487` (reads `pod`, which **moved** — needs `... on DcimFabricSwitch`) and `checks/peering_consistency_check.gql:49` (reads `name`/`role`)
- [ ] T039 [P] [US2] `transforms/containerlab_topology.gql:17` and `:97` — both read `name`; move to `... on DcimGenericDevice`, which fixes every device kind at once
- [ ] T040 [P] [US2] `transforms/cabling_plan.gql:52` and `transforms/cabling_plan.py:83`, `:96` — all read `rack`, which is genuinely concrete; add a `... on DcimFabricSwitch { rack { … } }` sibling. Cycle 026 already moved `name` to the generic here, so these **degrade to a blank column** rather than dropping rows
- [ ] T041 [P] [US2] `service_catalog/pages/4_Fabric_View.py` — five sites: `:281` and `:287` read `interfaces` (→ generic), `:92`, `:341`, `:349` read `name` (→ generic) and `role` (→ both fragments)

### The seven kind-name strings — the silent ones

- [ ] T042 [US2] **`transforms/containerlab_topology.py:202`** — `if node.typename != "DcimDevice"` must accept **both** kinds. Missing this drops all seven switches and emits valid YAML with no error. Verify against T004's counts, not by eye
- [ ] T043 [US2] `generators/generate_avd_device_hostvar.py:2786` — `raw_data.get("DcimDevice", {})`; the response key moves with the root retargeted in T030. **Silent** if missed
- [ ] T044 [US2] `checks/cv_config_check.py:57` — `normalized.get("DcimDevice", {})`; the response key moves with T034. **Silent** if missed
- [ ] T045 [P] [US2] `generators/generate_avd_device_hostvar.py:1836` (`client.get(kind="DcimDevice", …)`) and `:1857` (the `kind: str = "DcimDevice"` default parameter) — these fail loudly, but fix them with the rest
- [ ] T046 [P] [US2] `src/solution_arista_avd/sorting.py:22` and `:38` — `cast("DcimDevice", …)`; type-only, but mypy will care once `protocols.py` is regenerated

### The three raw mutation strings

- [ ] T047 [P] [US2] `generators/asn.py:21` — `DcimDeviceUpsert(...)` → `DcimFabricSwitchUpsert(...)`
- [ ] T048 [US2] `src/solution_arista_avd/generator.py:1063` (`asn`) and `:1087` (`vtep_loopback_ip`) — same. The `vtep_loopback_ip` one fails loudly once the field moves; the `asn` one is the quiet kind

### The twelve typed call sites

- [ ] T049 [P] [US2] `generators/generate_pod.py:244` (`role="super_spine"`), `generators/generate_rack.py:179` (spine), `generators/generate_server_cabling.py:56` (leaf/l2leaf), `generators/asn.py:46` — `kind=DcimDevice` → `DcimFabricSwitch`, and update the `protocols` imports and `list[DcimDevice]` annotations in each file
- [ ] T050 [US2] `src/solution_arista_avd/generator.py` — seven sites: `:693` (`filters`), `:712` (`create`, the single device-creation path), `:744`, `:1036`, `:1075`, `:1113`, `:1161` (`get`). Also the `list[DcimDevice]` annotations at `:150`, `:679`, `:762`, `:851`, `:873`, `:890`, `:1097`
- [ ] T051 [P] [US2] `generators/generate_fabric.py:72`, `src/solution_arista_avd/cabling.py` (6 annotations), `generators/generate_rack.py:92`/`:94`/`:137`/`:361`/`:429`, `generators/generate_pod.py:72`/`:73`/`:237` — type annotations only, but mypy must pass

### Regenerate, seed, and prove

- [ ] T052 [US2] Regenerate every `*_query.py` beside a changed `.gql`, via `uv run infrahubctl graphql generate-return-types <file>.gql`. **Do not hand-edit** (Constitution III)
- [ ] T053 [US2] `objects/26_nfd41_devices.yml` — `spec.kind: DcimDevice` → `DcimFabricSwitch` (C12). Confirm `objects/31_nfd41_offfabric_devices.yml` and `31a_nfd41_wan_addressing.yml` still say `DcimDevice`
- [ ] T054 [US2] `uv run pytest tests/unit -q` — green at or above **1043** (T002) **before** touching the environment. Fix `tests/unit/test_avd.py` (C5: `NON_AVD_DEVICE_ROLES` now does less work, because the kinds separate what that list separated by hand) and `tests/unit/test_device_type_and_platform.py` (C13: across all four kinds)
- [ ] T055 [US2] `uv run mypy --show-error-codes src/solution_arista_avd` — clean
- [ ] T056 [US2] Rebuild: `uv run invoke destroy && uv run invoke build && uv run invoke start && uv run invoke load`. Switches load as `DcimFabricSwitch`, routers as `DcimDevice`
- [ ] T057 [US2] Regenerate `src/solution_arista_avd/protocols.py` with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py` and confirm it contains a `DcimFabricSwitch` protocol with an unmodified header (C14)
- [ ] T058 [US2] `uv run invoke avd --topology` — the topology generators run **once**, on a fresh instance only. Re-running them against cabled fabric takes spines from 9 interfaces to 4 and then `generate-rack` dies with `IndexError`
- [ ] T059 [US2] Verify the kind counts against T005: `DcimFabricSwitch` **7**, `DcimDevice` **7**, `DcimGenericDevice` **22** — unchanged, which is what proves the polymorphic paths survived (L2)
- [ ] T060 [US2] Verify **33** artifacts across the same 10 definitions with the same per-definition counts as T003. A missing definition means a target group lost its members — most likely `avd_devices`, set in one place in `src/solution_arista_avd/generator.py`
- [ ] T061 [US2] Diff the seven EOS configs against `/tmp/027-baseline/` **and** against `lab/avd/intended/configs/*.cfg` with device names normalised. **Zero lines differ in both.** This is SC-003 and the cycle's headline claim
- [ ] T062 [US2] Verify the ContainerLab topology still has **14 nodes and 17 links** and the cabling plan still has **17 rows**, against T004. This is the check that actually catches T042

**Checkpoint US2**: the fabric renders exactly as before, through a new kind.

---

## Phase 5: User Story 3 — The WAN and firewall are untouched (P2)

**Goal**: `frr_config` and `junos_config` render exactly as before.

**Independent test**: T063 is fully independent and runs offline at any point. T064–T065 need the
rebuild from T056, so they are **not** independent of US2 — stated rather than pretended.

- [ ] T063 [P] [US3] Offline and independent: `git diff transforms/frr_config.gql transforms/junos_config.gql` is **empty**, and neither file's `*_query.py` regenerated to anything different (C10)
- [ ] T064 [US3] Diff the six FRR configs against `/tmp/027-baseline/` — **byte-identical** (SC-004)
- [ ] T065 [US3] Diff the Junos config against `/tmp/027-baseline/` — **byte-identical**, still 592 rendered lines plus its provenance line
- [ ] T066 [US3] Verify the two widened relationships still resolve **both** kinds: `RoutingAsn.devices` returns 6 routers and 7 switches; a tenant `RoutingVrfStaticRoute` returns `isp-pe1` **and** `leaf-nfd41-pod1-3-1`. If either returns one kind, T024 or T025 narrowed instead of widening

**Checkpoint US3**: nothing outside the fabric moved.

---

## Phase 6: Polish & Cross-Cutting

- [ ] T067 [P] Update `docs/docs/developer-guide/schemas.md` — four device kinds, and the two role dropdowns with their distinct choice lists
- [ ] T068 [P] Update `AGENTS.md`: the architecture line still reads `LocationRack -> DcimDevice -> DcimInterface`, and the non-EOS-role checklist now describes a kind boundary rather than a dropdown exclusion
- [ ] T069 [P] Add a note to `schemas/dcim_extensions.yml` beside the split dropdowns recording that `SecurityFirewall` was the precedent and `DcimFabricSwitch` is the second application — the file already carries that reasoning for the firewall
- [ ] T070 `uv run invoke test` — green at or above 1043
- [ ] T071 `uv run invoke lint` — ruff, ruff-format, yamllint, mypy, rumdl clean
- [ ] T072 Write the PR body. It **must** state explicitly that `$infrahub-run-integration-tests` is not installed (as in cycles 020–026) and that quickstart steps 0–13 are the non-live alternative
- [ ] T073 **Merge first, regenerate `schema.graphql` after.** `infrahubctl graphql export-schema` has no `--branch` flag and exports Infrahub `main`; loading this cycle's schema into `main` to regenerate is what made cycle 023's merge fail on a `SchemaAttribute` uniqueness violation. This cycle changes schema more than any since 023

---

## Dependencies

```text
Phase 1 (T001-T005)  ──▶ Phase 2 (T006-T010)  ──▶ Phase 3 US1 (T011-T029)
                                                        │
                                                        ▼
                                          Phase 4 US2 (T030-T062)
                                                        │
                                    ┌───────────────────┴──────────┐
                                    ▼                              ▼
                          Phase 5 US3 (T064-T066)          Phase 6 (T067-T073)

T063 (US3, offline) has no dependency beyond Phase 4's edits and may run any time after T035.
```

- **T003–T005 gate everything**: the baseline is destroyed by T056 and cannot be recovered.
- **T006 gates all of Phase 3**: it must pass on the untouched tree, then after each of T017–T027.
- **T052 (regenerate query types) must follow every `.gql` edit** — T030 to T041.
- **T057 (regenerate protocols) must follow T056**, because it reads the loaded schema.
- **T058 must follow T056 and run exactly once.**

## Parallel opportunities

| Group | Tasks | Why safe |
| --- | --- | --- |
| Schema reverse sides, batch 1 | T017, T018, T019, T020, T021 | five different files, each an anchored single-line edit |
| Query roots | T030, T031, T032, T033, T034 | five different files |
| Fragment sites | T037, T038, T039, T040, T041 | different files; T036 is alone because it has five sites in one file |
| Kind-name strings | T045, T046 | different files, and both fail loudly |
| Typed call sites | T049, T051 | T050 is alone — seven sites in one file |
| Docs | T067, T068, T069 | different files |

T022–T025 are **not** parallel: three of them live in `schemas/routing/vrf_services.yml` and the
fourth needs C6e re-run against the same file.

## Independent test criteria

| Story | Criterion |
| --- | --- |
| **US1** | `infrahubctl schema check` diff names exactly two kinds; C1–C8 and C6e green. No downstream code needed |
| **US2** | 7 EOS configs diff clean against the baseline **and** the lab's intended configs; 33 artifacts; 14 nodes / 17 links / 17 cable rows |
| **US3** | T063 offline at any time. T064–T066 need US2's rebuild — an honest dependency, not an independent story |

## Implementation strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1).** That delivers the thing the requester asked for —
routers no longer carrying `vtep_loopback_ip` — and is verifiable entirely offline through
`schema check` and the contract module. Nothing renders yet, so it is not shippable, but it is the
increment worth reviewing on its own: 13 peer edits are much easier to review without 40 code
changes alongside them.

**US2 is where the risk is**, and inside it T042 to T044 are the three tasks most likely to be
missed and least likely to announce themselves. Do them before T056, and verify with T062's counts
rather than by reading YAML.

**US3 is expected to be a no-op** and is worth running precisely because of that.

## Format validation

All 73 tasks carry a checkbox, a sequential ID, a `[P]` marker where parallelisable, a `[US1]`,
`[US2]` or `[US3]` label in the three story phases and none in Setup, Foundational or Polish, and
an exact file path. Task counts: Setup 5, Foundational 5, US1 19, US2 33, US3 4, Polish 7.
