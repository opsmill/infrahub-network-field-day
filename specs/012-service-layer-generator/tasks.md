---

description: "Task list for the service-layer fabric peering generator"
---

# Tasks: Service-Layer Fabric Peering Generator

**Input**: Design documents from `/specs/012-service-layer-generator/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/generator-contract.md](./contracts/generator-contract.md), [quickstart.md](./quickstart.md)

**Tests**: **REQUIRED.** Constitution IV mandates tests for every generator, and the plan's Complexity Tracking makes `tests/unit/test_generate_fabric_peering.py` the primary quality gate in place of the unavailable `$infrahub-test-generator-idempotence` skill. Tests are written **before** the implementation they cover.

**Organization**: Grouped by the three user stories from spec.md. US1 and US2 are both P1 and together form the MVP — US1 produces the sessions, US2 proves doing so changed nothing observable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task belongs to (US1–US3)
- Exact file paths appear in every task

## Path Conventions

Infrahub reference-design repository, per the plan's Structure Decision:

- Generator, its query, and its generated model: `generators/` (co-located, per AGENTS.md)
- Unit tests: `tests/unit/test_*.py`
- Registration: `.infrahub.yml`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: A working branch with the schema and data loaded, and — critically — the baseline that every later comparison depends on.

- [X] T001 Verify preflight: run `uv sync --all-packages`, then `uv run infrahubctl info` and confirm Connection Status ✅ with Infrahub 1.10.6
- [X] T002 Create the working branch with `uv run infrahubctl branch create svc-gen --sync-with-git`. The flag is mandatory: cycle 011 established that a branch created without it is never associated with a git branch, so Infrahub never reads `.infrahub.yml` for it and no registration can appear
- [X] T003 Load the branch: `uv run infrahubctl schema load schemas --branch svc-gen --wait 120` then `uv run infrahubctl object load objects/ --branch svc-gen`. Schema must precede objects, and both must precede any repository sync — see [quickstart.md](./quickstart.md) Prerequisites
- [X] T004 **Capture the baseline oracle** before any change: `uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering --branch svc-gen > /tmp/baseline.yaml`, and record the artifact checksum currently on the branch. Every acceptance claim in US2 is a comparison against this file, so capturing it after a change silently invalidates the whole cycle

**Checkpoint**: A branch that renders the artifact from hand-written sessions, and a recorded copy of what it renders.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The query and its typed model. Every user story reads through them, so nothing else can start.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Write `generators/generate_fabric_peering.gql` with operation `GenerateFabricPeeringQuery($name: String!)`, aliasing the service as `target:`, per [contracts/generator-contract.md](./contracts/generator-contract.md) §2. The operation name determines the generated root model's class name, so it must end in `Query` to match the repository's convention
- [X] T006 In the same file, traverse to the cluster and select `local_asn`, then the cluster's existing `fabric_peerings` with `id`, `name`, `peer_asn`, `enabled`, `peer_device` and `peer_address`. Omitting the existing sessions breaks adoption and is a contract violation, not an optimisation — see [research.md](./research.md) R3
- [X] T007 In the same file, traverse the cluster's `nodes` → `interfaces` → `connector` → `connected_endpoints` → far interface → `device`, selecting each interface's `id`, and each device's `id`, `name`, `role` and `asn`. The near-end interface `id` must be selectable or the exclusion in [research.md](./research.md) R2 cannot be implemented
- [X] T008 Export the branch schema and generate the typed model: `INFRAHUB_DEFAULT_BRANCH=svc-gen uv run infrahubctl graphql export-schema --destination /tmp/schema.svc-gen.graphql`, then `uv run infrahubctl graphql generate-return-types generators/generate_fabric_peering.gql --schema /tmp/schema.svc-gen.graphql`. Without the branch export this fails with `Cannot query field 'ServiceFabricPeering'` — see [research.md](./research.md) R9
- [X] T009 Confirm no `pyproject.toml` change is needed: `generators/*_query.py` is already a glob exclude in `[tool.ruff]`, unlike the `transforms/` entries which are listed individually. Verify by running `uv run ruff check generators/generate_fabric_peering_query.py` and confirming it is skipped
- [X] T010 Run `uv run invoke lint-mypy` (which checks `src/solution_arista_avd` only — the repository's actual gate) and confirm it passes. Do not widen it to `generators/`: that reports 141 pre-existing errors in the seven existing generators and says nothing about this change. Never hand-edit the generated file to satisfy mypy — regenerate it

**Checkpoint**: The query returns every field the derivation needs, in one round trip, through typed models.

---

## Phase 3: User Story 1 - Sessions derived from cabling (Priority: P1) 🎯 MVP

**Goal**: One `ClusterFabricPeering` per distinct fabric device, derived from the graph, with `peer_asn` read from the fabric's own `RoutingAsn`.

**Independent Test**: Delete the two hand-written sessions, run the generator against `nfd41-fabric-peering`, and confirm two sessions reappear with the same peer devices and ASNs.

### Tests for User Story 1 ⚠️

> Write these first and confirm they FAIL before T018.

- [X] T011 [P] [US1] Create `tests/unit/test_generate_fabric_peering.py` with a fixture builder shaping a `GenerateFabricPeeringQuery` response — three cluster nodes, two leaves, one node sharing a leaf — following the fixture-based pattern of `tests/unit/test_crossplane_fabric_peering.py`
- [X] T012 [P] [US1] Add `test_near_end_interface_is_never_a_peer` asserting no derived `peer_device` is the cluster node's own interface or its device. `connected_endpoints` returns **both** ends of the cable (verified live, [research.md](./research.md) R2), so without exclusion the generator peers the cluster with itself
- [X] T013 [P] [US1] Add `test_two_nodes_on_one_leaf_yield_one_session` asserting the peer set is distinct devices, not one per node (D-4)
- [X] T014 [P] [US1] Add `test_non_fabric_peer_is_skipped_silently` for a node cabled to a device whose role is outside `{leaf, border_leaf, l2leaf}`, and `test_mlag_pair_sharing_one_asn_yields_two_sessions` asserting equal ASNs never collapse the set (D-3, D-6)
- [X] T015 [P] [US1] Add `test_peer_asn_comes_from_the_device_routing_asn` asserting the value is read from the peer device, not from the service, a file, or an existing session (D-5, the requirement the whole feature exists for)
- [X] T016 [P] [US1] Add `test_adopt_payload_omits_preserved_fields` and `test_create_payload_includes_them`, asserting the two payload shapes in [data-model.md](./data-model.md) §3 — an adopted session's payload MUST NOT contain `name`, `enabled` or `peer_address`, because `save(allow_upsert=True)` writes whatever it is given
- [X] T017 [P] [US1] Add one test per validation rule V-1 … V-7 from [data-model.md](./data-model.md) §5, each asserting the message names the object and the field, and asserting **nothing was written** before the raise

### Implementation for User Story 1

- [X] T018 [US1] Create `generators/generate_fabric_peering.py` with `FabricPeeringGenerator(InfrahubGenerator)` and `async def generate(self, data: dict) -> None`, parsing through `GenerateFabricPeeringQuery(**data)` and aliasing long generated class names at module scope as `transforms/avd_anta_catalog.py` does. Do **not** copy the `sys.path`/module-reload preamble from `generate_rack.py`: it exists only for generators importing repository-local `solution_arista_avd` modules, and this one imports none — `generate_server_cabling.py` is the precedent for a generator without it
- [X] T019 [US1] Implement the traversal as a module-level pure function returning candidate `(device, near_interface_id)` pairs from the parsed response, so it is testable without a client
- [X] T020 [US1] Implement near-end exclusion by interface id, and role filtering against `{leaf, border_leaf, l2leaf}`, per D-2 and D-3. Filter by id rather than by device kind: kind-based filtering works today only because cluster nodes happen not to be `DcimDevice`
- [X] T021 [US1] Implement distinct-device reduction and deterministic ordering by device name (D-4, D-7)
- [X] T022 [US1] Implement the reconciliation: index existing sessions by `peer_device` id, then build the adopt or create payload per [data-model.md](./data-model.md) §3
- [X] T023 [US1] Implement all seven validations, raising before any write. Ordering matters: a partial write is the only path by which this generator can delete a real session — see [research.md](./research.md) R4
- [X] T024 [US1] Write the sessions with `await session.save(allow_upsert=True)`, relying on the `[["cluster", "peer_device"]]` uniqueness constraint as the natural key so an upsert adopts rather than duplicates
- [X] T025 [US1] Link the written sessions to the ordering service through its `peerings` relationship (FR-016)
- [X] T026 [US1] Run `uv run pytest tests/unit/test_generate_fabric_peering.py -v` and confirm every test written in T011–T017 now passes

**Checkpoint**: The derivation is correct and fully covered without a server.

---

## Phase 4: User Story 2 - The rendered manifest does not change (Priority: P1) 🎯 MVP

**Goal**: Prove that replacing hand-written rows with generated ones did not alter what reaches Kubernetes.

**Independent Test**: Run the generator, regenerate the artifact, and diff against the T004 baseline.

- [X] T027 [US2] Register the query and the generator in `.infrahub.yml` exactly as specified in [contracts/generator-contract.md](./contracts/generator-contract.md) §1, targeting the existing `service_fabric_peerings` group rather than creating a second group over the same object (FR-025)
- [X] T028 [US2] Commit and push the branch so the repository sync picks it up, then confirm `sync_status: in-sync` at the new commit and that a `CoreGeneratorDefinition` named `generate-fabric-peering` exists on the branch. A mismatch between the transform's `query` attribute and the registered query name surfaces only here
- [X] T029 [US2] Run the generator: `uv run infrahubctl generator generate-fabric-peering --branch svc-gen name=nfd41-fabric-peering`
- [X] T030 [US2] Confirm the adoption was pure: exactly two `ClusterFabricPeering` objects, `name` still `k8s-leaf1`/`k8s-leaf2`, `peer_address` still `10.110.0.2/24` and `10.110.0.3/24`, `peer_device` the two leaves and never a `ComputePhysicalServer` (G-2, G-4)
- [X] T031 [US2] Re-render and diff against the baseline: `uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering --branch svc-gen | diff /tmp/baseline.yaml -`. **Expected: no output.** This is SC-004 and the single most important check in the cycle
- [X] T032 [US2] Regenerate the artifact through `POST /api/artifact/generate/<definition-id>?branch=svc-gen` and confirm the checksum is unchanged from T004. Pass the **artifact definition** id, not the artifact id — cycle 011 found the latter returns HTTP 200 then fails in the background with `NodeNotFoundError`, which looks exactly like a passing test
- [X] T033 [US2] Confirm the regeneration actually executed by finding `Generate artifact Crossplane FabricPeering` in the task-worker log after the trigger timestamp. An unchanged checksum from a run that never happened is not evidence
- [X] T034 [US2] Run the generator a second time and repeat T031 and T032, proving idempotence at the level an operator observes (SC-002, contract §4)

**Checkpoint**: MVP complete. The generator produces the sessions, and the artifact is byte-identical.

---

## Phase 5: User Story 3 - Cleanup removes only what it justified (Priority: P2)

**Goal**: Pin down the tracking context's destructive behaviour deliberately rather than discovering it later.

**Independent Test**: Remove one node's cabling, re-run, and check the arithmetic of what disappeared.

### Tests for User Story 3 ⚠️

- [X] T035 [P] [US3] Add `test_empty_peer_set_raises_before_writing` asserting that a cluster with no cabled nodes produces an error and zero writes, so a partial set can never reach the tracking group (FR-019, V-7)
- [X] T036 [P] [US3] Add `test_disabled_session_stays_disabled` asserting `enabled` is absent from the adopt payload, so an operator who disabled a session keeps it disabled across runs (FR-017)

### Implementation and validation for User Story 3

- [X] T037 [US3] Review every `save()` call and add `update_group_context=False` to any object the generator touches but does not own, following `generate_rack.py` and `generate_fabric.py`. Sessions the generator owns must NOT carry this flag, or cleanup will never remove them
- [X] T038 [US3] Live-verify FR-022: create a `ClusterFabricPeering` by hand that the derivation would not produce, run the generator, and confirm the object survives. This holds by construction — deletion candidates are last run's group members minus this run's ([research.md](./research.md) R4) — but it is the destructive path, so prove it rather than reason about it
- [X] T039 [US3] Live-verify FR-021: remove the cabling of the only node attached to one leaf, re-run, and confirm exactly that leaf's session is deleted and the other survives
- [X] T040 [US3] Confirm the artifact now renders one peer, and that its checksum **moved** — the complement of T032. If nothing can move the checksum, T032 proves nothing (SC-005)
- [X] T041 [US3] Restore the cabling, re-run, and confirm the session and the original checksum both return, leaving the branch as US2 left it

**Checkpoint**: The destructive path is understood and bounded.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T042 **Revised during implementation — the rows are NOT removed.** Removing them was impossible: `peer_address` is recorded only on the session, so a deleted session could never be recreated (proved live in T041, where restoring required re-loading this file). Instead `objects/34_nfd41_cluster.yml` is annotated to record the split ownership — `name`, `peer_address`, `description` and `svi` are declared there and authoritative; `peer_asn` is a seed the generator overwrites from the fabric. The `peer_asn` duplication therefore remains in the file, but is no longer authoritative, which is a smaller win than this task originally assumed and is recorded as such in acceptance-evidence.md
- [X] T043 Re-ran `uv run infrahubctl object load objects/34_nfd41_cluster.yml --branch svc-gen` with the rows present and confirmed it is idempotent and does not disturb the generated sessions — done as part of the T041 restore, which depended on exactly this behaviour
- [X] T044 [P] Add a `### FabricPeeringGenerator` entry to `docs/docs/developer-guide/generators.md` alongside the seven existing generators, covering the design object, generated objects, target group, the derivation, and the adopt-versus-create distinction
- [X] T045 [P] Update the generator inventory in `AGENTS.md` to include `generate-fabric-peering`
- [X] T046 [P] Add any new vocabulary to `.vale/config/vocabularies/OpsMill/accept.txt` only if `lint-prose` reports a new error; confirm the count is unchanged rather than assuming
- [X] T047 Run the full gate: `uv run pytest tests/unit` and `uv run invoke lint`. `lint-prose` fails on 7 pre-existing errors in `docs/`; confirm the count is unchanged
- [X] T048 Write `specs/012-service-layer-generator/acceptance-evidence.md` recording SC-001 through SC-010 with the actual checksums, object counts and command output, following the format cycle 011 established
- [X] T049 Record the Principle II exception evidence explicitly: the unit tests, the live double-run, and the artifact checksum comparison, stated as the documented alternative to `$infrahub-test-generator-idempotence`
- [X] T050 `svc-gen` deleted, git branch and Infrahub mirror. Original: Delete the throwaway branch once the evidence is captured: `uv run infrahubctl branch delete svc-gen`
- [ ] T051 Obtain maintainer sign-off on the Principle II and Principle IV exceptions recorded in [plan.md](./plan.md) Complexity Tracking — the same open decision as cycles 010 and 011, now with a second principle attached

---

## Dependencies

```text
Phase 1 (Setup) ──► Phase 2 (Foundational) ──┬──► Phase 3 (US1, P1) ──► Phase 4 (US2, P1) ──► Phase 6
                                              └──► Phase 5 (US3, P2) ─────────────────────────┘
```

- **Phase 2 blocks everything.** No story can read the graph without the query and its typed model.
- **US2 depends on US1.** There is nothing to prove unchanged until the generator produces sessions.
- **US3 depends on US1** but not on US2; its tests (T035, T036) can be written alongside US1's.
- **T042 depends on Phase 4.** Removing the hand-written rows before the generator is proven would leave the branch with no sessions at all.
- **T004 blocks T031, T032 and T040.** The baseline must exist before anything changes.

## Parallel Execution Opportunities

- **T011–T017** (US1 tests) are all in one new file but independent in content; if split across agents, write the fixture builder (T011) first and merge the rest.
- **T012–T017** are marked [P] against T019–T025: tests and implementation touch different files.
- **T035, T036** (US3 tests) can be written while US1 implementation proceeds.
- **T044, T045, T046** are three different files with no interdependency.
- Everything in Phase 4 is strictly sequential — each task consumes the previous one's output.

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 + Phase 4.** That delivers a generator that derives the sessions and proof that doing so changed nothing observable. US3 hardens the destructive path; Phase 6 removes the second copy and records the evidence.

**Stop-and-check point**: T031. If the diff is not empty, do not proceed to Phase 5 — the adopt payload is sending a field it must omit ([research.md](./research.md) R3), and every later comparison would be against a corrupted baseline.
