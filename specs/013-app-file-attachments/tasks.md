---

description: "Task list for the application file attachments schema feature"
---

# Tasks: Application File Attachments

**Input**: Design documents from `/specs/013-app-file-attachments/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/schema-kinds.md](./contracts/schema-kinds.md), [quickstart.md](./quickstart.md)

**Tests**: **REQUIRED.** Constitution IV mandates tests before merge, and the plan's Complexity Tracking makes the contract suite the primary gate in place of the unavailable `$infrahub-run-integration-tests` skill. Contract assertions are written **before** the schema YAML.

**Organization**: Grouped by the two user stories from spec.md. US1 is the MVP; US2 is the precedence rule that keeps the two mechanisms coherent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task belongs to (US1–US2)
- Exact file paths appear in every task

## Path Conventions

- Schema: `schemas/service/kubernetes_services.yml`
- Generated protocols: `src/solution_arista_avd/protocols.py` (**never hand-edited**)
- Contract tests: `tests/unit/test_service_layer_schema_contract.py`

---

## Phase 1: Setup

- [X] T001 Verify preflight: `uv sync --all-packages`, then `uv run infrahubctl info` showing Connection Status ✅ with Infrahub 1.10.6
- [X] T002 Create the working branch: `uv run infrahubctl branch create app-files --sync-with-git`. The flag is mandatory — a branch without it is never associated with a git branch
- [X] T003 Load the branch: `uv run infrahubctl schema load schemas --branch app-files --wait 120` then `uv run infrahubctl object load objects/ --branch app-files`
- [X] T004 **Capture the baseline oracle before any change**: `uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering --branch app-files > /tmp/baseline.yaml`, and record the artifact checksum. SC-008 compares against this, so capturing it afterwards would silently invalidate the whole cycle

**Checkpoint**: A branch that renders the peering artifact, and a recorded copy of what it renders.

---

## Phase 2: User Story 1 - The payload is stored as a file (Priority: P1) 🎯 MVP

**Goal**: Two file kinds attached to `ServiceFabricApp`, inheriting `CoreFileObject`.

**Independent Test**: Load the schema, attach a file, read it back with its checksum.

### Tests for User Story 1 ⚠️

> Write these first and confirm they FAIL before T010.

- [X] T005 [P] [US1] Add `test_app_file_kinds_exist_and_inherit_core_file_object` to `tests/unit/test_service_layer_schema_contract.py`, asserting both kinds exist, are nodes, and list `CoreFileObject` in `inherit_from` — following the local-helper pattern already in that module
- [X] T006 [P] [US1] Add `test_app_file_kinds_do_not_redeclare_inherited_fields`, asserting neither kind declares `file_name`, `file_size`, `file_type`, `checksum` or `storage_id`. Redeclaring them would look harmless and would silently stop them being inherited
- [X] T007 [P] [US1] Add `test_app_file_parent_relationship`, asserting each kind has an `app` relationship to `ServiceFabricApp` with `kind: Parent`, `cardinality: one`, `optional: false` (GI-1)
- [X] T008 [P] [US1] Add `test_app_file_relationship_identifiers_match`, asserting the identifier on each side of both relationships is the same string — `fabricapp__values_file` and `fabricapp__manifests_file`. A mismatch silently creates two one-way links instead of one bidirectional one (GI-5), which is the skill's CRITICAL relationship rule
- [X] T009 [P] [US1] Add `test_app_file_uniqueness_and_hfid`, asserting `uniqueness_constraints: [["app"]]` written **bare** (no `__value`, since it is a relationship) and `human_friendly_id: ["app__name__value"]` (with `__value`, since it crosses to an attribute)

### Implementation for User Story 1

- [X] T010 [US1] Add `ServiceFabricAppValuesFile` to `schemas/service/kubernetes_services.yml` per [data-model.md](./data-model.md) §3 — namespace `Service`, `inherit_from: [CoreFileObject]`, `include_in_menu: false`, HFID, uniqueness, and the `app` Parent relationship with identifier `fabricapp__values_file`
- [X] T011 [US1] Add `ServiceFabricAppManifestsFile` the same way, with identifier `fabricapp__manifests_file`
- [X] T012 [US1] Add `values_file` and `manifests_file` to `ServiceFabricApp` — `Component`, cardinality one, optional, with the matching identifiers (data-model §4)
- [X] T013 [US1] Run `uv run yamllint schemas/` and `uv run pytest tests/unit/test_service_layer_schema_contract.py` and confirm the tests written in T005–T009 now pass
- [X] T014 [US1] Run `uv run infrahubctl schema check schemas/ --branch app-files` and confirm zero validation errors and a diff that adds exactly two kinds and modifies only `ServiceFabricApp` (SC-001)
- [X] T015 [US1] Load it: `uv run infrahubctl schema load schemas --branch app-files --wait 120`
- [X] T016 [US1] Regenerate protocols with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py`, then `uv run invoke lint-mypy`. Never hand-edit the generated file

**Checkpoint**: The kinds exist and load.

---

## Phase 3: User Story 2 - Precedence between file and attribute (Priority: P2)

**Goal**: The rule that keeps two mechanisms for one payload coherent.

- [X] T017 [US2] Add the precedence rule to both kinds' `description` in `schemas/service/kubernetes_services.yml`, per [data-model.md](./data-model.md) §5 and research R2: the attachment wins, and the attribute is an inline escape hatch read only when no file is attached
- [X] T018 [US2] Add `test_precedence_rule_is_documented` to `tests/unit/test_service_layer_schema_contract.py`, asserting each kind's description states which source wins. FR-011 requires the rule to be discoverable from the schema rather than only from a spec document
- [X] T019 [US2] Confirm `chart_values` and `manifests` are still present on `ServiceFabricApp` and unchanged (FR-010, GI-6)

---

## Phase 4: Live verification

- [X] T020 Attach a values file to an application through the SDK and read it back byte-for-byte, including keys containing dots and slashes (SC-002, SC-006). There is no CLI path — `infrahubctl object load` cannot upload file content
- [X] T021 Re-upload identical content and confirm the checksum is unchanged (SC-003), using the `save_file_if_changed` helper in `src/solution_arista_avd/generator.py`
- [X] T022 Attach a payload of at least 150 lines of nested YAML and confirm it round-trips unchanged (SC-007)
- [X] T023 Attempt to attach a second values file to the same application and confirm it is rejected (SC-004)
- [X] T024 Delete a test application and confirm its attached files do not survive (SC-005)
- [X] T025 **The regression oracle**: re-render the peering artifact and diff against the T004 baseline. It MUST be byte-identical, and the artifact checksum must still be `0d800c9d5005b5fdb6b371bb5627d143` (SC-008). A schema change that moves it is not additive, whatever the diff said

---

## Phase 5: Polish

- [X] T026 [P] Document the two kinds in `docs/docs/developer-guide/schemas.md`, including the precedence rule and why the payload is a file rather than an attribute
- [X] T027 [P] Add any new vocabulary to `.vale/config/vocabularies/OpsMill/accept.txt` only if `lint-prose` reports a new error; confirm the count is unchanged rather than assuming
- [X] T028 Run the full gate: `uv run pytest tests/unit` and `uv run invoke lint`. `lint-prose` has a pre-existing baseline of 7 errors / 4 warnings; confirm it is unchanged
- [X] T029 Write `specs/013-app-file-attachments/acceptance-evidence.md` recording SC-001 through SC-009 with real command output, following the format cycle 011 established
- [ ] T030 Delete the throwaway branch once evidence is captured: `uv run infrahubctl branch delete app-files`
- [ ] T031 Obtain maintainer sign-off on the Principle IV exception recorded in [plan.md](./plan.md) Complexity Tracking — the same open decision as cycles 010, 011 and 012

---

## Dependencies

```text
Phase 1 (Setup) ──► Phase 2 (US1, P1) ──► Phase 3 (US2, P2) ──► Phase 4 (Live) ──► Phase 5
```

- **T004 blocks T025.** The baseline must exist before anything changes.
- **T005–T009 precede T010–T012**, per the tests-first rule.
- **T015 blocks Phase 4** — nothing can be attached until the schema is loaded.
- **T017 is independent of Phase 2's YAML edits** in content but touches the same file, so it runs after them.

## Parallel Execution Opportunities

- **T005–T009** are five assertions in one new block; independent in content, so they can be drafted together and merged.
- **T010 and T011** are two sibling kinds — parallelisable in principle, but they touch one file, so sequential in practice.
- **T026 and T027** are different files with no interdependency.
- Phase 4 is strictly sequential: each step depends on the previous one's state.

## Implementation Strategy

**MVP = Phase 1 + Phase 2.** That delivers the kinds and proves they load. Phase 3 makes the
two mechanisms coherent, Phase 4 proves the change was additive, Phase 5 records it.

**Stop-and-check point**: T025. If the peering artifact moved, this was not an additive
change and something in the diff was wrong — investigate before proceeding to Phase 5.
