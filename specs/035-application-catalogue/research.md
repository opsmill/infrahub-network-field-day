# Research: Application Catalogue

## R1. Where to pin

- **Decision**: Portal sends chart fields from the entry it read; `generate-fabric-app` pins once, guarded by `definition_pinned`.
- **Rationale**: `chart_repository`, `chart_name` and `chart_version` are mandatory and `tests/unit/test_service_layer_schema_contract.py::test_fabric_app_workload_source_is_a_chart_and_nothing_else` asserts it, so a create without them is refused. The generator is still the one place that covers creators other than the portal and the only place that can produce the values file (a `CoreFileObject` cannot be created by the create mutation; content arrives via an upload).
- **Alternatives**: (a) Relax `chart_*` to optional and pin only in the generator: cleaner, but weakens an existing test. (b) Portal only: leaves the UI path unpinned and cannot upload values atomically with the entry. (c) Pin at every generator run: silently upgrades a running application, which is the failure this feature prevents.

## R2. Is `definition` watched?

- **Decision**: No, nor `definition_pinned`.
- **Rationale**: `docs/docs/developer-guide/service-triggers.md` scopes rules to inputs and forbids watching write-backs. Re-pointing an application is an upgrade, which is its own reviewed change (D3), so it should not auto-rebuild. `definition_pinned` is the generator's write-back.
- **Alternatives**: Watching `definition` would re-pin on re-point, contradicting D3.

## R3. Reading the entry without a new query model

- **Decision**: Read through the SDK (`client.get` and relationship `fetch`).
- **Rationale**: `generate_fabric_app_query.py` is generated from `schema.graphql`, which `infrahubctl graphql export-schema` regenerates from a live instance only (`docs/docs/developer-guide/development-workflow.md`). Adding `definition` to the `.gql` would need that. The existing generator already writes through SDK nodes, so this is consistent.
- **Alternatives**: Hand-extend `schema.graphql` (unsupported route, rejected by the brief).

## R4. How the values file is produced

- **Decision**: In the generator, create `ServiceFabricAppValuesFile` with `parent app`, `upload_from_bytes(content, name)`, `save(allow_upsert=True, update_group_context=False)`, through `save_file_if_changed` (`src/solution_arista_avd/generator.py`).
- **Rationale**: Same primitive `scripts/seed_app_payloads.py` uses on a live instance; checksum-guarded so a repeat writes nothing.
- **Alternatives**: Portal `infrahub:file:upload` step with the entry's text: works for portal only and was the old path for user-typed values; rejected for catalogue requests so one place decides.

## R5. Non-requestable entries' values

- **Decision**: `scripts/seed_app_payloads.py` applies `assemble_payload` output to each entry's `default_values` for the three infrastructure entries; `whoami` is inline.
- **Rationale**: One source in git (the payload files) for both the attachment on the seeded app and the entry; `objects/` cannot hold the Grafana payload with dashboards sensibly, and `object load` of large multi-line text is unproven.
- **Alternatives**: Inline everything (duplicates 13 KB plus dashboards); leave infrastructure entries without values (entries lie about what the app runs).

## R6. Picker filtering in the portal

- **Decision**: Ingest the kind as a Resource of type `application-definition` (`slugFor` drops the `Service` prefix), tag an entry `requestable` in `provider.ts` only when it is requestable and active, filter the picker on `kind`, `spec.type` and `metadata.tags: requestable`; re-read in the template as the control.
- **Rationale**: The existing provider already tags the status value; `catalogFilter` supports tags, but ORs the values of one key, so requestable-and-active is one derived tag. A filter on the client is UX; the server-side re-read is the guarantee.
- **Alternatives**: A new `status`-style enum for requestability (rejected: spec fixes two attributes). A free-text field validated at run time (poor UX).

## R7. Seed ordering

- **Decision**: `35a_otternet_app_catalogue.yml`.
- **Rationale**: Files load in filename order; `31a_` already exists as a precedent; `_` (0x5F) sorts before `a` (0x61), so `35_`, `35a_`, `36_` is the order. The entries reference only `junos-http` (`32_`).

## R8. Block size, selector, advertised services

- **Decision**: Portal reads and sends them; generator fills selector and advertised services only when empty; generator never writes `vip_block_size`.
- **Rationale**: `vip_block_size` is a watched input (`test_service_trigger_contract.py`); writing it from the generator would be a write-back to a watched field. Selector and advertised services are not watched.
