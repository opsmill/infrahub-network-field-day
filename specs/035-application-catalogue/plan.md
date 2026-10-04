# Implementation Plan: Application Catalogue

**Branch**: `feat/application-catalogue` | **Date**: 2026-10-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/035-application-catalogue/spec.md`, including its Clarifications.

## Summary

Add a platform-owned catalogue of applications to Infrahub (`ServiceApplicationDefinition`), link `ServiceFabricApp` to it optionally, snapshot ("pin") the chosen entry onto each requested application once, and replace the portal's typed chart fields with a catalogue picker. The seeded applications are re-expressed as non-requestable entries and render exactly as before.

The pin is made in two places that agree. The portal reads the entry at request time and sends the three mandatory chart fields, the entry's block size, selector and advertised services in the create. The existing `generate-fabric-app` generator then pins once on the request branch: chart fields, the values attachment produced from `default_values`, and selector and advertised services when empty. A write-back Boolean `definition_pinned` makes it once-only.

## Technical Context

**Language/Version**: Python 3.12 (project range `>=3.11,<3.14`); TypeScript for the Backstage provider.

**Primary Dependencies**: `infrahub-sdk` generators (`InfrahubGenerator`), PyAVD `>=6.4.0,<6.5.0` (untouched), Backstage scaffolder and the `infrahub-backend` plugin.

**Storage**: Infrahub graph; the values attachment is a `CoreFileObject` (`ServiceFabricAppValuesFile`) in object storage.

**Testing**: pytest unit tests (`uv run invoke test`); vitest for the plugin (needs `node_modules`, absent in this worktree, so not runnable here).

**Target Platform**: Infrahub 1.10.6 on the lab; Backstage portal in the tooling cluster.

**Project Type**: Infrahub repository (schemas, objects, generators, transforms, menus) plus a portal plugin.

**Performance Goals**: A creation costs the build run plus at most one no-op run (SC-006). The pin's own write is not a watched field, so it fires no run.

**Constraints**: Offline run: no live Infrahub, no docker, no portal build. `schema.graphql` cannot be re-exported offline. Hard rules in `AGENTS.md` apply (never mandatory-on-existing-data, never hand-edit generated files, no `Deployment*` or `Monitoring*` trigger).

**Scale/Scope**: Four seeded entries, one requestable. One schema file, one schema extension, one objects file, one generator step, one transform guard, one template, one provider tag, two scripts, six doc pages.

## Constitution Check

| Principle | Gate | Result |
| --- | --- | --- |
| I Schema-driven | Schema before code; protocols regenerated | Pass. Schema first (task order); `protocols.py` regenerated offline with `infrahubctl protocols`. Note the existing caveat that it ignores `extensions:`. |
| II Idempotent | Upserts; guarded writes; repeat-run validation | Pass. The pin is guarded by `definition_pinned`; file write uses the checksum-guarded `save_file_if_changed`; a unit test runs the generator twice and asserts the second run writes nothing. |
| III Type safety | Typed query models, no untyped GraphQL access | Justified exception. The pin reads the entry through SDK node objects, as the generator's existing writes do, because a new query model cannot be generated offline (`schema.graphql` is stale until the lab re-exports it). `generate_fabric_app.gql` and its model are unchanged. |
| IV Test-required | Unit tests; lint gate; integration where needed | Pass for unit and lint. Integration (`invoke test --integration`) needs the stack and is a lab-phase item. |
| V Convention | Numbered objects; naming; docs in `docs/docs/` and sidebar | Pass. New schema in `schemas/catalogue/`; objects as `35a_`; docs under existing pages (no new page, so no sidebar change). |

Re-check after design: unchanged. The one exception (III) is recorded in Complexity Tracking.

## Plan decisions

- **PD-1 Schema location.** The kind lives in `schemas/catalogue/application_catalogue.yml`, not `schemas/service/`. Existing contract tests in `tests/unit/test_service_layer_schema_contract.py` iterate `schemas/service/*.yml` and require every node there to inherit `ServiceGeneric` and `GeneratorTarget`, which a catalogue entry deliberately does not. Moving the kind is cheaper and honest; editing those tests would weaken them. `infrahubctl schema load schemas` is recursive, so the directory loads.
- **PD-2 Application extension.** `definition` (optional relationship, `on_delete: no-action`, peer `ServiceApplicationDefinition`) and `definition_pinned` (optional Boolean, default false) are added to `ServiceFabricApp` in `schemas/service/kubernetes_services.yml`, beside its other fields. The inverse relationship `applications` on the entry gives the entry's page a list of what was built from it. `chart_*` stay mandatory; the existing assertion is untouched.
- **PD-3 Display and menu.** Both the entry's `display_label` (its `title` attribute) and the menu entry are required. The menu entry goes under Services. `tests/unit/test_service_layer_menu_contract.py` gets a `CATALOGUE_KINDS` constant and compares the section against `SERVICE_KINDS | CATALOGUE_KINDS`; `SERVICE_KINDS` is not edited.
- **PD-4 Generator.** `generate-fabric-app` gains `_pin_definition`, run first on the build path (not for a withdrawn status). It reads the application and its definition through the SDK, and returns at once if there is no definition or `definition_pinned` is true. Otherwise it sets the three chart fields, `definition_pinned` true, and fills `service_selector` and `advertised_services` only when empty, in one save; then it attaches the values file when `default_values` is non-empty. It never writes `vip_block_size`, `exposed`, `status` or `cluster`. No change to `generate_fabric_app.gql`, its model, or `.infrahub.yml`.
- **PD-5 Trigger contract.** `definition` and `definition_pinned` are not watched. `definition_pinned` joins `WRITE_BACKS["ServiceFabricApp"]` in the contract test, and a new test asserts `definition` is not watched. `triggers.yml` needs no new rule; the existing `created` rule runs the pin.
- **PD-6 Transform.** `crossplane_fabric_app.build_chart` raises when a chart name is present without a repository and a version. Rendering is otherwise unchanged and never reads the definition.
- **PD-7 Seed data.** `objects/35a_otternet_app_catalogue.yml` declares four entries; `36_otternet_app_services.yml` gains `definition:` and `definition_pinned: true` on its three apps. `35a_` sorts between `35_` and `36_` (`_` before `a`). The infrastructure entries take their `default_values` from `payloads/*.yaml` through `scripts/seed_app_payloads.py`; `whoami` carries inline values.
- **PD-8 Portal.** `backstage/app-config.yaml` lists `ServiceApplicationDefinition` as a Resource of type `application-definition` with no generated template (`app-config.docker.yaml` layers over it and restates only the catalogue locations, so it needs no change). `definition_pinned` joins the `ServiceFabricApp` form exclusions. `provider.ts` adds a `requestable` tag, emitted only for an entry that is requestable and active. The template drops the removed fields, gains an entity picker, a catalog fetch, a definition read, and a required-variable assertion, and sends the entry's chart fields, block size and selector in the application create. Advertised services are filled by the generator, because the scaffolder cannot template a list out of a relationship read. Values are no longer uploaded by the portal.
- **PD-9 Demo.** `scripts/demo_rehearsal.py` and `scripts/demo_full_run.py` submit the picker's entity reference; checks on the rendered artifact keep asserting chart `whoami` 6.0.0 and values.

## Risks

- **R1 File creation inside a generator is unproven offline.** `save_file_if_changed` is used by `scripts/seed_app_payloads.py` against a live instance; inside a generator on a branch it is new. Unit tests use fakes. Lab phase must create a request and read the attachment back.
- **R2 Text attribute with dots and slashes.** `default_values` is Text, so the HTTP 500 for JSON keys with a dot or slash does not apply; the object-load path with a multi-line text containing `app.kubernetes.io/name` is unproven offline and is a lab check.
- **R3 Two runs on create.** The pin does not add a run (its writes are not watched), but the create costs the build plus the `provisioning -> active` no-op, as today.
- **R4 Stale `schema.graphql`.** It lacks the new kind. Nothing offline reads it for this change, but the lab phase must re-export it.
- **R5 Portal untestable here.** `node_modules` is absent, so the TypeScript change is type-reasoned only.

## Project Structure

### Documentation (this feature)

```text
specs/035-application-catalogue/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── schema-kinds.md
│   └── template-contract.md
├── tasks.md
└── RUN-NOTES.md
```

### Source Code (repository root)

```text
schemas/catalogue/application_catalogue.yml     # new kind
schemas/service/kubernetes_services.yml         # definition, definition_pinned
objects/35a_otternet_app_catalogue.yml          # new seed file
objects/36_otternet_app_services.yml            # link + pin the three apps
menus/menu.yml                                  # catalogue under Services
generators/generate_fabric_app.py               # pin step
transforms/crossplane_fabric_app.py             # partial-chart guard
src/solution_arista_avd/protocols.py            # regenerated
scripts/seed_app_payloads.py                    # entries' default_values
scripts/demo_rehearsal.py, scripts/demo_full_run.py
backstage/app-config.yaml, app-config.docker.yaml
backstage/catalog/exposed-app-with-access.yaml
backstage/plugins/infrahub-backend/src/provider.ts (+ test)
tests/unit/                                     # new and extended contract tests
docs/docs/                                      # portal, runbook, builder, schemas, inventory
```

**Structure Decision**: One repository, existing layout; the only new directory is `schemas/catalogue/`.

## Complexity Tracking

| Departure | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| SDK node access in the pin (Principle III) | A typed query model cannot be generated offline | Hand-writing `*_query.py` is forbidden; extending `schema.graphql` by hand is not a supported route |
| Pin in portal and generator | Mandatory `chart_*` forces the portal to send them; non-portal creators still need pinning | Relaxing `chart_*` to optional would weaken an existing contract test |
| New directory `schemas/catalogue/` | Keeps service-layer invariants intact | Loosening the service-schema tests |
