---

description: "Task list for the application access grant generator"
---

# Tasks: Application Access Grant Generator

**Input**: Design documents from `/specs/031-service-access-generator/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. The spec requires them (FR-070 to FR-073) and constitution principle IV makes them a merge gate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are given in every task

## A note on story independence

The three stories share one Python module, so they are **not** independently deliverable in the way the template's parallel-team strategy assumes. They are independently *testable*, which is what matters here:

- **US1** is the creation path. It is the MVP and stands alone.
- **US2** is revocation. Its production code is almost entirely the adoption-not-upsert decision made inside US1's helpers (research R6), so US2's tasks are the ones that *prove* revocation is safe against a hand-maintained firewall. Do not skip them on the grounds that the SDK handles deletion — the whole risk is that it deletes too much.
- **US3** adds **no production code at all**. `junos_config.gql` already queries these kinds unfiltered. Its tasks are end-to-end verification, which is a different claim from "the objects exist".

Work them in order. Parallelism here is between *files*, not between stories.

---

## Phase 1: Setup (Wiring)

**Purpose**: everything the generator needs to exist and be reachable, before there is a generator

- [X] T001 [P] Write the GraphQL query in `generators/generate_app_access.gql` per [contracts/graphql-query.md](./contracts/graphql-query.md): `target: ServiceAppAccess(name__value: $name)` plus unfiltered `SecurityPolicy`, `SecurityZone`, `SecurityService` and `SecurityGenericAddress`. Use an inline fragment `... on SecurityIPAMIPAddress` to reach `ip_address`; the generic has no such field. Do **not** fetch `SecurityFirewallInterface` or the baseline `SecurityPolicyRule` set — the contract says why.
- [X] T002 Generate return types with `uv run infrahubctl graphql generate-return-types generators/generate_app_access.gql`, producing `generators/generate_app_access_query.py`. Never hand-edit it (FR-014, constitution III). Depends on T001.
- [X] T003 [P] Add the `service_app_accesses` entry to the existing `CoreStandardGroup` document in `objects/00_groups.yml`, with the comment from [contracts/registration.md](./contracts/registration.md) recording why it is a group and why a standard group rather than a `CoreGeneratorGroup` (research R7).
- [X] T004 [P] Create `objects/38_nfd41_access_grants.yml` with exactly one `ServiceAppAccess`, `approved: false`, `member_of_groups: [service_app_accesses]`, naming objects that already exist in the lab — the `ServiceFabricApp` from `objects/36_nfd41_app_services.yml`, the `branch` zone and the `branch-users` address entry from `objects/32_nfd41_security.yml`, and an `IpamIPAddress` for the destination VIP. **`approved: false` is the design, not a placeholder** (research R5): it keeps the rendered Junos artifact byte-identical.
- [X] T005 Register the query and the generator in `.infrahub.yml` exactly as [contracts/registration.md](./contracts/registration.md) specifies: `queries` entry `generate_app_access`, `generator_definitions` entry `generate-app-access` with `class_name: AppAccessGenerator` and `convert_query_response: false`. Depends on T001.

**Checkpoint**: `uv run infrahubctl object load objects/00_groups.yml --branch <b>` and `objects/38_nfd41_access_grants.yml` both load, and `uv run infrahubctl generator --list` shows `generate-app-access`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the module, its validation, and its two derivations. Every story depends on these.

**⚠️ No story work can begin until this phase is complete.**

- [X] T006 Create `generators/generate_app_access.py` with the module docstring and `class AppAccessGenerator(InfrahubGenerator)`, importing the generated query models from `generate_app_access_query.py` and aliasing the verbose ones at module level, following `generators/generate_fabric_peering.py`. The docstring must record the two non-obvious decisions a later reader will otherwise undo: the index/`book_index` floors and why they exist, and that adoption fetches rather than upserts. Depends on T002.
- [X] T007 Implement the validation helper in `generators/generate_app_access.py` covering V1–V8 from [data-model.md](./data-model.md) §6. **It must run to completion before any object is written** — `generate_fabric_peering.py` calls this ordering load bearing, because a partial write is the one path by which the tracking context deletes a real object. V2 must reject an empty `ports` list outright and never read it as "all ports". Depends on T006.
- [X] T008 Implement the destination-zone derivation in `generators/generate_app_access.py`: `application.vrf → IpamVRF ← SecurityZone.vrf`, raising when the application has no VRF, when no zone carries it, or when more than one does. **Do not derive this from firewall-interface containment** — the handoff interfaces are `/30` point-to-points containing no VIP, so containment matches nothing (research R2). Depends on T006.
- [X] T009 Implement the policy derivation in `generators/generate_app_access.py`: the `SecurityPolicy` whose `device_target` is the firewall, raising unless exactly one matches. Depends on T006.
- [X] T010 Implement the deterministic allocation helpers in `generators/generate_app_access.py`: `index` from a floor of 100 and `book_index` from a floor of 1000, both pure functions of the grant's name. Two runs must produce identical numbers or the tracking context churns. Depends on T006.
- [X] T011 [P] Create `tests/unit/test_app_access_generator.py` with fixtures built from the real shapes in `objects/32_nfd41_security.yml` — six zones, one `nfd41-perimeter` policy, the four existing `SecurityService` objects, and the address book's `book_index` values 10–130. Fixtures invented from scratch will not catch the adoption cases.

**Checkpoint**: `uv run pytest tests/unit/test_app_access_generator.py` collects and runs; validation and derivation helpers are importable and unit-testable in isolation.

---

## Phase 3: User Story 1 — An approved grant becomes a firewall rule (P1) 🎯 MVP

**Goal**: an approved grant produces the address-book entry, the service objects and the rule that permit the session, marked as service-owned and linked back through `granted_rules`.

**Independent test**: create one `ServiceAppAccess` with `approved: true`, run `infrahubctl generator generate-app-access`, and verify the three objects exist, are linked from `granted_rules`, and carry `managed_by_service: true` while every hand-written rule still reads `false`.

### Tests for US1

- [X] T012 [P] [US1] Test the destination-zone derivation in `tests/unit/test_app_access_generator.py`: the happy path, no VRF on the application, no zone carrying that VRF, and two zones carrying it. The last two must raise, not fall back.
- [X] T013 [P] [US1] Test the empty-ports rejection and port-range validation in `tests/unit/test_app_access_generator.py`. Assert the empty case **raises** rather than producing a permit-all rule — this is the test that would catch the worst possible defect in this generator.
- [X] T014 [P] [US1] Test the unapproved no-op in `tests/unit/test_app_access_generator.py`: `approved: false` writes nothing and leaves `status` unchanged. Assert zero writes, not just the absence of a rule.
- [X] T015 [P] [US1] Test the allocation helpers in `tests/unit/test_app_access_generator.py`: indices land at or above their floors, are stable across repeated calls, and never collide with the hand-written 10/20/30 or with `book_index` 10–130.

### Implementation for US1

- [X] T016 [US1] Implement the address-book entry step in `generators/generate_app_access.py`: create a `SecurityIPAMIPAddress` named `svc-<grant>-vip` wrapping the grant's `destination_vip`, with a `book_index` from T010. **Adopt by the wrapped `IpamIPAddress`, not by name**, so an entry that already wraps that VIP is reused. A generated entry with no `book_index` is skipped by `junos_config.py::_addresses` and the configuration will not load. Depends on T007–T010.
- [X] T017 [US1] Implement the service-object step in `generators/generate_app_access.py`: one `SecurityService` per permitted port, **adopted by `(ip_protocol, port)` rather than by name**, so a grant for 443 references the existing `junos-https` instead of declaring a duplicate application for the same port (FR-022). Depends on T016.
- [X] T018 [US1] Implement the rule step in `generators/generate_app_access.py`: a `SecurityPolicyRule` named `svc-<grant>` with `action: permit`, `log: true`, `log_session_close: true`, `managed_by_service: true`, the derived policy and destination zone, the grant's source zone and address, and the objects from T016/T017. Depends on T017.
- [X] T019 [US1] Link every created rule into the grant's `granted_rules` in `generators/generate_app_access.py`. Depends on T018.
- [X] T020 [US1] Write the grant's `status` in `generators/generate_app_access.py` — `active` on success, `error` on a validation or derivation failure, unchanged when unapproved. **Set `active` last**, so a run that fails halfway cannot claim it. Depends on T019.
- [X] T021 [US1] Verify all `save()` calls in `generators/generate_app_access.py` use `allow_upsert=True`, and that the module stays under ruff's C901 max-complexity of 17 by keeping validation, derivation, allocation and each creation step in named helpers rather than one `generate()` body. Depends on T020.

**Checkpoint**: US1 is independently testable. Run quickstart steps 1–4.

---

## Phase 4: User Story 2 — Revocation removes what it created, and nothing else (P2)

**Goal**: revoking a grant removes its rule and the objects the generator created, while the hand-written baseline and any adopted object survive.

**Independent test**: run the generator for an approved grant, confirm the rule exists, set `approved: false`, run again, and confirm the rule is gone while the nineteen hand-written rules and their `book_index` ordering are unchanged.

**Note**: the SDK's tracking context does the deleting. These tasks exist because the risk is that it deletes *too much* — an empty result is only evidence when a non-empty one is proven beside it.

### Tests for US2

- [X] T022 [P] [US2] Test in `tests/unit/test_app_access_generator.py` that revoking a grant removes the rule it created and leaves every hand-written rule in the same zone pair intact, with its `index` unchanged.
- [X] T023 [P] [US2] Test in `tests/unit/test_app_access_generator.py` that an **adopted** object survives revocation: a grant using port 443 adopts `junos-https`, and revoking the grant leaves `junos-https` in place for the baseline rules that also reference it. This is the test that fails if adoption was implemented as an upsert.
- [X] T024 [P] [US2] Test in `tests/unit/test_app_access_generator.py` that narrowing a grant's ports from three to one removes exactly the two service objects no longer justified, and that the surviving rule permits only the remaining port.
- [X] T025 [P] [US2] Test in `tests/unit/test_app_access_generator.py` that `managed_by_service` is set only on objects the generator created, and that all nineteen hand-written rules still read `false` after a run.

### Implementation for US2

- [X] T026 [US2] Confirm and, where needed, correct the adoption paths in `generators/generate_app_access.py` so an adopted object is fetched and modified rather than upserted, is never renamed or re-indexed, and is never marked `managed_by_service`. An upsert validates every mandatory field, so a payload omitting them to preserve them is rejected outright. Depends on T021.
- [X] T027 [US2] Add the idempotence test to `tests/unit/test_app_access_generator.py`: a second run against unchanged input creates nothing, modifies nothing and deletes nothing. Constitution principle II. Depends on T026.

**Checkpoint**: US1 and US2 both work. Run quickstart steps 4 and 7.

---

## Phase 5: User Story 3 — The rule reaches the firewall (P3)

**Goal**: the generated rule is rendered into the Junos artifact and pushed onto `fw1`.

**Independent test**: create an approved grant on a branch, run the generator, regenerate and **download** the artifact, confirm the permitted session appears, then reconcile and confirm `fw1` matches.

**This phase adds no production code.** `transforms/junos_config.gql` queries `SecurityGenericAddress` and `SecurityPolicy` unfiltered, so generated objects render through the existing artifact. The tasks are verification, which is a different claim from "the objects exist".

- [X] T028 [US3] Confirm `tests/unit/test_junos_config.py` still passes unchanged with the seeded grant present. It holds the artifact byte-for-byte against `junos.conf`, including `test_the_exclusions_add_up`. **If it fails here, the seed grant was approved by mistake** — an unapproved grant generates nothing and the artifact must be byte-identical. Depends on T005.
- [X] T029 [US3] Add a rendering test to `tests/unit/test_app_access_generator.py` (or a fixture in the junos test module) proving that a *generated* rule renders into the expected zone pair with its address-book entry declared after every hand-written entry. Depends on T018, T028.
- [~] T030 [US3] **Partly done.** Live-verified on branch `verify-031-access`: objects load, the generator creates/adopts/withdraws correctly, three runs are idempotent, `main` untouched, branch deleted. NOT done: regenerating the artifact and pushing to `fw1`. Run quickstart steps 5 and 6 against a branch: regenerate the artifact, **download it** rather than trusting its `Ready` status, confirm the rule is present, then `uv run invoke reconcile --once --dry-run --branch <b>` reports `fw1` differing, push, and confirm it matches. Depends on T029.

**Checkpoint**: the full loop is demonstrated end to end.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T031 [P] Add the generator to the inventory list in `AGENTS.md` under "Generator and transform inventory", and record the two things a reader must know before changing it: the index/`book_index` floors, and that the seeded grant is unapproved on purpose.
- [X] T032 [P] Document the grant workflow in `docs/docs/developer-guide/generators.md`, using relative Markdown links only — the aggregation site mounts this content under `/arista-avd` and root-absolute links fail its build.
- [X] T033 Run `uv run invoke lint` (ruff, mypy, yamllint, rumdl, Vale) and `uv run pytest tests/unit`. All must pass; constitution principle IV makes this a merge gate.
- [ ] T034 Run `$infrahub-test-generator-idempotence` for the generator, and `$infrahub-run-integration-tests` for the change, recording the branch and commit. Constitution principles II and IV.
- [ ] T035 Run `scripts/verify_bootstrap.sh` — a full teardown and rebuild, asserting all sixteen checks with the seeded grant present. "It worked" and "it is stable" are different claims and only a full teardown distinguishes them.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies; T001 → T002 and T001 → T005 are the only ordering inside it
- **Phase 2 (Foundational)**: depends on T002; **blocks all stories**
- **Phase 3 (US1)**: depends on Phase 2
- **Phase 4 (US2)**: depends on US1 — it corrects and proves the adoption paths US1 wrote
- **Phase 5 (US3)**: depends on US1 for a rule to render; T028 depends only on Phase 1
- **Phase 6 (Polish)**: depends on all stories

### Story dependencies — read this before parallelising

Unlike the template's default, **these stories are sequential**. They share `generators/generate_app_access.py`, and US2 modifies code US1 writes. US3 adds no code but needs US1's output to verify. Independent *testability* holds; independent *implementation* does not.

### Within each story

- Tests before implementation where the test can be written first (T012–T015 before T016–T021)
- Address entry before service objects before the rule — the rule references both
- Status written last

---

## Parallel Opportunities

```bash
# Phase 1 — three files, no shared state:
T001 generators/generate_app_access.gql
T003 objects/00_groups.yml
T004 objects/38_nfd41_access_grants.yml

# Phase 3 — all four tests target the same new test file but different
# functions; write them together, they do not conflict:
T012 T013 T014 T015   in tests/unit/test_app_access_generator.py

# Phase 4 — same:
T022 T023 T024 T025

# Phase 6:
T031 AGENTS.md
T032 docs/docs/developer-guide/generators.md
```

**Never parallel**: T006–T010 and T016–T021 and T026. All touch `generators/generate_app_access.py`.

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Phase 1 (T001–T005) — wiring
2. Phase 2 (T006–T011) — module, validation, derivations
3. Phase 3 (T012–T021) — the creation path
4. **Stop and validate**: quickstart steps 1–4

At that point an approved grant produces a firewall rule, which is the request in one story.

### Incremental

1. MVP → grants materialize
2. US2 → revocation is safe against a hand-maintained firewall
3. US3 → the loop is demonstrated onto `fw1`
4. Polish → docs, lint, idempotence evidence, full rebuild

### Do not skip US2

US1 without US2 is a generator that creates firewall rules and has never been shown to remove them correctly. The failure mode is not "revocation does not work" — it is the tracking context deleting an adopted object that baseline rules still reference, which shows up as a firewall that stops permitting traffic it should.

---

## Notes

- `[P]` means different files, or different functions in a file nobody else is editing
- Every task names its file; none should need more context than this document plus the contracts
- Commit after each task or logical group
- No file under `schemas/` changes in this cycle (SC-008). If implementation finds a genuine schema gap, stop — that is a schema cycle first, per constitution principle I
- Nothing here reads, writes or triggers from `DeploymentState` or `DeploymentDiffFile`

---

## Phase 7: Defects found during implementation (added, then fixed)

Two bugs a live run found and no unit test could. Both are fixed, regression-tested and documented in [research.md](./research.md) R8.

- [X] T036 An object the generator created on an earlier run must be **written again every run**. Returning its id without touching it leaves it out of the tracking group and `delete_unused_nodes=True` deletes it, while the rule referencing it survives — an address referenced and declared nowhere, which stops the configuration loading. Fixed with `Existing.is_ours`; regression test `test_a_second_run_rewrites_the_objects_the_first_run_created`, confirmed to fail without the fix.
- [X] T037 **Revocation is not covered by the tracking context at all.** `InfrahubGroupContext.update_group` opens with `if not members: return`, so the unapproved path — which touches nothing — prunes nothing. Un-approving a grant left its rule, its address entry and its service object in place. Fixed with an explicit `_withdraw`, keyed on the generated name so a referenced object like `junos-https` is never a candidate. Verified live.
