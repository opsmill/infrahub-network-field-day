# Tasks: Application Catalogue

**Input**: Design documents in `specs/035-application-catalogue/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: Requested ("tests first where practical"). Each story's test tasks come before its implementation tasks and must fail first.

**Format**: `- [ ] T### [P?] [US?] Description with file path`. All paths are relative to the repository root. Run each gate on its own, never piped.

## Phase 1: Setup

- [ ] T001 Confirm the worktree `/home/ubuntu/dev/nfd41/infrahub-wt-catalogue` is on `feat/application-catalogue` and run `uv sync --all-packages`
- [ ] T002 Record the baseline: run `uv run invoke lint` and `uv run invoke test` once, each on its own, and note both exit 0 in `specs/035-application-catalogue/RUN-NOTES.md`

---

## Phase 2: Foundational (schema, menu, protocols). Blocks every story.

- [ ] T003 [P] Write `tests/unit/test_application_catalogue_schema_contract.py` asserting `contracts/schema-kinds.md` items 1 to 9 (kind exists in `schemas/catalogue/`, no `ServiceGeneric`/`GeneratorTarget`, `default_values` TextArea and no JSON attribute, `requestable` default false, `status` active/deprecated, HFID and display label, `definition` optional no-action, `definition_pinned` optional default false, `chart_*` still mandatory, not a trigger or generator-group target)
- [ ] T004 [P] Extend `tests/unit/test_service_layer_menu_contract.py` with a `CATALOGUE_KINDS` constant and compare the Services section to `SERVICE_KINDS | CATALOGUE_KINDS` without editing `SERVICE_KINDS`
- [ ] T005 Create `schemas/catalogue/application_catalogue.yml` defining `ServiceApplicationDefinition` per `data-model.md` (use the `infrahub-managing-schemas` skill; `include_in_menu: false`, `human_friendly_id`, `display_label`, `order_by`, uniqueness on `name__value`)
- [ ] T006 Add `definition` and `definition_pinned` to `ServiceFabricApp` in `schemas/service/kubernetes_services.yml` beside its other fields, with the inverse `applications` on the new kind
- [ ] T007 Add the "Application Catalogue" leaf to the Services section of `menus/menu.yml` (use the `infrahub-managing-menus` skill)
- [ ] T008 Regenerate `src/solution_arista_avd/protocols.py` with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py`; do not hand-edit it
- [ ] T009 Run the T003 and T004 tests and the existing `tests/unit/test_service_layer_schema_contract.py` and `tests/unit/test_demo_presentation_contract.py`; fix until green without editing existing assertions

**Checkpoint**: schema and menu done.

---

## Phase 3: User Story 4 - seeded applications keep rendering identically (P1)

**Goal**: three seeded applications are catalogue entries and render the same.

**Independent Test**: `uv run pytest tests/unit/test_fabric_app_chart_seed_data.py tests/unit/test_crossplane_fabric_app.py tests/unit/test_application_catalogue_seed_data.py`

- [ ] T010 [P] [US4] Write `tests/unit/test_application_catalogue_seed_data.py`: four entries exist (`whoami` requestable; three infrastructure entries not), each seeded application names a `definition`, has `definition_pinned: true`, and its chart fields equal its definition's; definitions load before the apps (file order); `whoami` values are valid YAML with the exposure keys the transform needs and the label with dots survives
- [ ] T011 [US4] Create `objects/35a_otternet_app_catalogue.yml` with the four entries (use the `infrahub-managing-objects` skill); `whoami` carries inline `default_values`; the infrastructure entries leave `default_values` to the seeding script
- [ ] T012 [US4] Add `definition` and `definition_pinned: true` to the three apps in `objects/36_otternet_app_services.yml` without changing any other field
- [ ] T013 [US4] Extend `scripts/seed_app_payloads.py` so each infrastructure entry's `default_values` is set from the same `assemble_payload` bytes, idempotently; add a unit test in `tests/unit/test_application_catalogue_seed_data.py` for the mapping and the unchanged-checksum no-op
- [ ] T014 [US4] Run `tests/unit/test_object_load_order.py`, `tests/unit/test_otternet_seed_data.py` and the T010 tests; confirm no rendered-artifact test changed

---

## Phase 4: User Story 2 - a catalogue change never upgrades a running application (P1)

**Goal**: generator pins once; later catalogue edits change nothing.

**Independent Test**: `uv run pytest tests/unit/test_fabric_app_pin.py tests/unit/test_fabric_app_generator.py tests/unit/test_service_trigger_contract.py`

- [ ] T015 [P] [US2] Write `tests/unit/test_fabric_app_pin.py` with fakes for the SDK client: pins an unpinned app once (chart fields, `definition_pinned`, selector and advertised services only when empty, values file created from `default_values`); no definition changes nothing; `definition_pinned` true changes nothing even after the entry's version changes; a withdrawn status is not pinned; empty `default_values` pins with no file and is not re-pinned; a second run writes nothing; `vip_block_size` is never written; typed chart fields that disagree with the entry are overwritten at pin time and the run logs it
- [ ] T016 [P] [US2] Update `tests/unit/test_service_trigger_contract.py`: add `definition_pinned` to `WRITE_BACKS["ServiceFabricApp"]`, leave `WATCHED` unchanged, add a test that `definition` is not watched and a test that no rule names `ServiceApplicationDefinition`
- [ ] T017 [US2] Implement `_pin_definition` in `generators/generate_fabric_app.py` per PD-4 (SDK reads, one save, `save_file_if_changed` for the file, guarded, called first on the build path; use the `infrahub-managing-generators` skill); do not touch `generators/generate_fabric_app.gql` or its query model
- [ ] T018 [US2] Add a guard to `build_chart` in `transforms/crossplane_fabric_app.py` raising on a chart name without repository and version, and tests in `tests/unit/test_crossplane_fabric_app.py` (the guard, and FR-016: an app whose entry differs from its pin renders the pin)
- [ ] T019 [US2] Run T015, T016 and the existing generator and transform tests; fix until green

---

## Phase 5: User Story 3 - the platform team maintains the catalogue (P2)

**Goal**: the catalogue is visible and maintainable in Infrahub.

- [ ] T020 [P] [US3] Add the catalogue to `docs/docs/developer-guide/schemas.md` (kind, fields, why a separate directory) and to `docs/docs/developer-guide/generator-transform-inventory.md` (the pin step and the transform guard, with traps)
- [ ] T021 [P] [US3] Update `docs/docs/developer-guide/service-triggers.md` with the unwatched `definition` and `definition_pinned` and the termination argument

---

## Phase 6: User Story 1 - request an application by picking from a catalogue (P1)

**Goal**: the portal asks for an entry, not chart details.

**Independent Test**: `uv run pytest tests/unit/test_combined_app_template_contract.py tests/unit/test_application_catalogue_portal.py`

- [ ] T022 [P] [US1] Write `tests/unit/test_application_catalogue_portal.py` for `contracts/template-contract.md`: removed fields gone; picker present with the single-tag filter; step order; the create sends chart fields from the definition read and the `definition` relationship; no values upload step; both app-configs list the kind as a Resource of type `application-definition` with no template; the read step carries the requestable and active filters
- [ ] T023 [P] [US1] Add a vitest case to `backstage/plugins/infrahub-backend/src/provider.test.ts` that an entry is tagged `requestable` only when requestable and active
- [ ] T024 [US1] Add the kind to `infrahub.catalog.kinds` in `backstage/app-config.yaml` and `backstage/app-config.docker.yaml`
- [ ] T025 [US1] Implement the `requestable` tag in `backstage/plugins/infrahub-backend/src/provider.ts` (include the attribute in the kind's query only if the provider builds the field list from the schema, which it does)
- [ ] T026 [US1] Rewrite the form and steps of `backstage/catalog/exposed-app-with-access.yaml` per the template contract; keep every existing contract test green
- [ ] T027 [US1] Update `tests/unit/test_combined_app_template_contract.py` only where the removed fields or the added step require it (no weakening: mandatory-field and ordering assertions stay)
- [ ] T028 [US1] Run the portal tests and `tests/unit/test_revoke_template_contract.py`, `tests/unit/test_portal_generator_groups.py`

---

## Phase 7: User Story 5 - the demo still runs act one (P2)

- [ ] T029 [P] [US5] Find act one in `scripts/demo_rehearsal.py` and `scripts/demo_full_run.py` and how `scripts/portal/run_template.py` passes values; change the inputs to the picker's entity reference and keep the chart `whoami` 6.0.0 and values assertions; add or extend a unit test over the inputs
- [ ] T030 [P] [US5] Update `docs/docs/demo-builder.md`, `docs/docs/demo-runbook.md` (act one) and `docs/docs/service-portal.md`

---

## Phase 8: Polish and gates

- [ ] T030a [P] Check `tests/unit/test_agents_docs_inventory.py`; update `AGENTS.md` and `docs/docs/developer-guide/architecture.md` where it or the project's own summary requires the catalogue
- [ ] T031 Write `specs/035-application-catalogue/RUN-NOTES.md`: what Spec Kit produced unaided versus corrected, skill gaps, extra decisions, files by area, what could not be verified offline, and the lab checklist (load order, regenerate `schema.graphql`, seed payloads, rebuild the portal, act one, the Claude Doc values that change)
- [ ] T032 Run `uv run invoke lint` on its own; fix until exit 0
- [ ] T033 Run `uv run invoke test` on its own; fix until exit 0
- [ ] T034 Commit with the required trailers, push `feat/application-catalogue`, open the pull request against `main` (do not merge)

## Dependencies

Phase 2 blocks all. US4 (seed) and US2 (generator) need the schema; US1 needs the schema and benefits from US4's seed; US3 and US5 are documentation and scripts after US1. T011 before T012; T017 after T015 and T016; T026 after T022 and T024. Parallel: T003/T004; T010 with T015/T016; T020/T021; T022/T023; T029/T030.

## Implementation strategy

MVP is Phase 2 plus US4 plus US2 (a safe schema, the seed and the pin, with the seeded apps unchanged), then US1 (the portal), then documentation and scripts.
