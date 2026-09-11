---

description: "Task list for the Crossplane FabricApp transform"
---

# Tasks: Crossplane FabricApp Manifest

**Input**: Design documents from `/specs/017-fabric-app-transform/`

**Tests**: **REQUIRED.** Constitution IV; the fixture suite is the primary gate.

## Phase 1: Setup

- [ ] T001 Verify preflight: `uv run infrahubctl info` shows Connection Status ✅ with Infrahub 1.10.6
- [ ] T002 Create the branch `app-render` with `--sync-with-git`, then `schema load` and `object load`
- [ ] T003 **Record cycle 011's peering render before starting.** SC-010 asserts this cycle does not disturb it, and this is the first cycle since 011 to add a second artifact definition

## Phase 2: Foundational — seed data the transform cannot be proven without

- [ ] T004 Add `IpamPrefix 10.112.240.0/28` with role `vip_pool` to object data. Verified absent; `spec.expose.vipBlock` cannot render without it (FR-018, research R4)
- [ ] T005 Add the `service_fabric_apps` group to `objects/00_groups.yml` — a group per service kind, so an artifact definition cannot generate against a target it cannot render (research R6)
- [ ] T006 Seed `ServiceFabricApp nfd41-demo` in a new object file, transcribing every field from `../lab/crossplane/apps/10-demo.yaml`: namespace, VRF, exposure, the three `allowFrom` prefixes, the port, and both selectors as `key=value` lists
- [ ] T007 Commit the manifests payload as a reviewable YAML file under `objects/payloads/`, transcribed verbatim from the oracle's `spec.manifests`
- [ ] T008 Write `scripts/seed_app_payloads.py`, uploading the payload to the `ServiceFabricAppManifestsFile` attachment via `upload_from_bytes()` before the first `save()` — cycle 013 found `create()` + `save()` raises without content. Reuse `save_file_if_changed` so a re-run with unchanged content is a no-op (FR-020, FR-021)
- [ ] T009 Run the seeding script twice and confirm one attachment with one unchanged checksum (SC-008)

## Phase 3: Foundational — the query

- [ ] T010 Write `transforms/crossplane_fabric_app.gql`, aliasing the app as `target:` and fetching every field in [data-model.md](data-model.md) §1 plus both attachment relationships
- [ ] T011 Select `__typename` at every union point **including nested relationship nodes** — cycle 016 found the generator needs it in both places
- [ ] T012 Regenerate the typed model via `export-schema` from the branch then `generate-return-types --schema`; confirm `uv run invoke lint-mypy` passes

## Phase 4: User Story 1 - The app renders (P1) 🎯 MVP

### Tests ⚠️

- [ ] T013 [P] [US1] Create `tests/unit/test_crossplane_fabric_app.py` with a fixture builder, following `tests/unit/test_crossplane_fabric_peering.py`
- [ ] T014 [P] [US1] Add tests for the field mapping in [data-model.md](data-model.md) §1 — namespace, tenant lower-casing, expose, and all five policy booleans
- [ ] T015 [P] [US1] Add `test_selectors_become_label_maps` and `test_label_values_stay_strings`, asserting `'true'` does not become a boolean (FR-014, G-3)
- [ ] T016 [P] [US1] Add `test_ports_render_as_strings` — the XRD types `allowFromPorts[].port` as a string (G-3)
- [ ] T017 [P] [US1] Add `test_allow_from_lists_every_prefix`, asserting all three CIDRs appear. This list is a security control (SC-005)
- [ ] T018 [P] [US1] Add `test_unset_optional_fields_are_omitted` and `test_empty_policy_is_omitted` — an emitted `policy: {}` could override the XRD's own defaults
- [ ] T019 [P] [US1] Add one test per validation rule V-1 … V-5 from [data-model.md](data-model.md) §4
- [ ] T020 [P] [US1] Add `test_rendering_is_byte_identical_for_an_unchanged_model` (SC-004)

### Implementation

- [ ] T021 [US1] Create `transforms/crossplane_fabric_app.py` with `CrossplaneFabricAppTransform(InfrahubTransform)` and `async def transform` — async because `download_file()` is (research R1); `avd_anta_catalog` is the async precedent
- [ ] T022 [US1] Implement selector parsing and the field mapping as pure functions over the parsed response, so they are testable without a client
- [ ] T023 [US1] Implement attachment reading: `download_file()`, `yaml.safe_load`, and the precedence rule — attachment first, inline attribute second (research R2, G-7)
- [ ] T024 [US1] Implement all five validations, raising before any output is produced
- [ ] T025 [US1] Emit through `yaml.dump` with a `SafeDumper` subclass, reusing cycle 011's approach: `sort_keys=False`, indented sequences, and a forced quote on colon-bearing scalars
- [ ] T026 [US1] Run the unit suite and confirm T013–T020 pass

## Phase 5: User Story 2 - It matches the oracle (P1) 🎯 MVP

- [ ] T027 [US2] Register the query, transform and artifact definition in `.infrahub.yml` per [contracts/manifest-contract.md](contracts/manifest-contract.md) §1
- [ ] T028 [US2] Commit, push the branch, and confirm the repository syncs with all three registrations accepted
- [ ] T029 [US2] Render against the seeded app (SC-001)
- [ ] T030 [US2] **The oracle**: normalise both documents and compare field by field with `10-demo.yaml`. Every difference must be a field the render adds carrying an XRD default; `policy.allowFrom` and `spec.manifests` must not appear in the diff at all (SC-003, SC-005)
- [ ] T031 [US2] Render twice and confirm byte-identical (SC-004)
- [ ] T032 [US2] **SC-010**: re-render the peering manifest and diff against the T003 baseline. It MUST be byte-identical
- [ ] T033 [US2] Generate the artifact and confirm `application/yaml` and a stable checksum across a regeneration (SC-009)

## Phase 6: Polish

- [ ] T034 [P] Add a `### CrossplaneFabricAppTransform` entry to `docs/docs/developer-guide/transforms.md`, covering the attachment precedence and why the transform is async
- [ ] T035 [P] Document the seeding script in `docs/docs/quick-start.md` or the developer guide — `invoke load` alone no longer fully seeds the repository, which is a change to how a fresh instance is brought up
- [ ] T036 [P] Update `AGENTS.md`'s transform inventory
- [ ] T037 Run the full gate: `uv run pytest tests/unit` and `uv run invoke lint`; confirm lint-prose is unchanged
- [ ] T038 Write `acceptance-evidence.md` with real output for SC-001 … SC-011
- [ ] T039 Delete the throwaway branch
- [ ] T040 Maintainer sign-off on the Principle IV exception

## Dependencies

```text
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
```

- **T003 blocks T032.**
- **Phase 2 blocks Phase 5** — the transform cannot be rendered against an empty attachment.
- **T030 is the stop-and-check.** If a shared field differs, the render is not a faithful replacement.

## Implementation Strategy

**MVP = Phases 1–5.** Phase 2 is unusually large for a transform cycle because the transform
cannot be proven without seeded data, and `object load` cannot upload file content.
