# Run notes: application catalogue (Spec Kit cycle 035)

Branch `feat/application-catalogue`. Built offline: no docker, no kubectl, no Infrahub, no portal build. Nothing here has run against the lab.

## What Spec Kit and the skills produced unaided, and what I corrected

Run for real through the Skill tool, in order: `speckit-specify`, `speckit-clarify`, `speckit-plan`, `speckit-tasks`, `speckit-analyze`, `speckit-implement`, with the `infrahub-managing-*` skills their hooks route to (schemas, generators, objects, menus, transforms; schemas and generators were loaded early and not re-loaded per command, because their text was already in the session).

| Step | Produced by the skill | My corrections |
| --- | --- | --- |
| specify | Directory scaffold, `feature.json`, quality checklist shape, the section order. The spec text itself was written by me from the brief; the skill supplies a template and rules, not content. | Used the schema template's intent by hand (the pre-hook's live check was skipped). Wrote decisions D1 to D8 as a section. |
| clarify | The `## Clarifications` section structure and the re-validation of the checklist. | The skill's loop is interactive and capped at five. The brief asked me to answer my own questions, so I answered six from the decisions and the repository's contracts, and wrote them in. |
| plan | `plan.md` template, `setup_plan.py`, the Constitution Check gate. | All design decisions (PD-1 to PD-9) are mine. The constitution gate surfaced Principle III (typed models) and Principle IV (integration tests), both recorded. |
| tasks | Task format, phase layout. | I wrote the task list; the skill's template drove the layout. |
| analyze | Nothing automated: it is a read-only prompt. I performed the analysis and then applied its remediations myself (FR-016 test, the disagreeing-chart edge case, AGENTS.md). |
| implement | Hook ordering, checklist gate. | Everything else. |

### Skill and tooling gaps found

1. **`before_specify` hook needs a live Infrahub** (`infrahubctl info`). It halts without one. Skipped by instruction. It also routes one artifact type per cycle, while this feature is schema, objects, generator, menu and transform together.
2. **`before_plan` and `before_implement` hooks dump the entire `.infrahub.yml` into every skill load.** Five loads cost roughly 60 KB of repeated text. A path list would do.
3. **`speckit-infrahub-speckit-route-friction` depends on `infrahub-reporting-skill-gaps`, which is not installed here.** The hook skipped, as designed, so no friction report could be offered. There was friction to report (below).
4. **`check_prerequisites.py` reports `BRANCH` as `035-application-catalogue`**, read from `feature.json`, although the git branch is `feat/application-catalogue`. Cosmetic, but a script that trusts it would be wrong.
5. **The schemas skill gives no offline validation route.** I validated the YAML with `infrahub_sdk.schema.SchemaRoot(**doc)`, which catches shape errors but not server rules (relationship direction pairing, reserved names). The skill's `infrahubctl schema check` needs a server.
6. **The generators skill says to carry a `watch:` block on every generator.** This repository's `.infrahub.yml` carries none for any generator, so I followed the repository, not the skill. The skill and the repository disagree, and the skill does not say what to do then.
7. **No rule covers reading a cardinality-many relationship in a generator without a query model.** I assumed the SDK leaves it uninitialised until `fetch()` is called and wrote the code and the test double that way; unproven live.
8. **Spec Kit's `catalogFilter` guidance does not exist at all**, and nothing in the Backstage docs says that a filter ORs the values of one key. I found it by reasoning and recorded it (one derived `requestable` tag).

## Decisions beyond the brief, and why

1. **Attribute `title`, not `label`.** `label` risks a reserved-name clash I could not check offline. The spec says "label/title".
2. **Schema in `schemas/catalogue/`, not `schemas/service/`** (PD-1). The service-layer contract tests would otherwise force `ServiceGeneric` and `GeneratorTarget` on a catalogue entry.
3. **`definition_pinned`, a new optional Boolean write-back.** Without a once-only marker, a catalogue edit would silently re-pin. Chosen over relaxing `chart_*` to optional, which would have meant weakening an existing contract test.
4. **The portal sends the chart fields; the generator also pins** (the `chart_*` fields are mandatory, so a create without them is refused). The generator is the only place that can produce the values file and covers non-portal creators.
5. **`definition` is not a watched input** (re-pointing is an upgrade). Both new fields are unwatched; `generate_fabric_app.gql` and its generated model did not change, because the entry is read through the SDK. That is why no return types needed regeneration.
6. **The generator never writes `vip_block_size`** (watched). The portal reads the entry's default and sends it.
7. **The generator, not the portal, fills advertised services.** The scaffolder has no `map` filter to template a list out of a relationship read.
8. **Entries named `lab-whoami`, `lab-metrics`, `lab-telemetry`** for the three seeded applications, so they cannot be mistaken for the requestable `whoami`.
9. **Infrastructure entries hold the committed payload file, not the assembled attachment.** The metrics attachment folds in 220 KB of dashboard JSON; a 237 KB attribute would be read by every catalogue refresh.
10. **One derived `requestable` tag, set only for requestable AND active entries**, because a catalogue filter ORs the values of one key.
11. **The template reads the entry on the request branch, after creating it**, not on `main` before: this keeps the existing "every step names its branch" contract untouched, at the cost of an orphan branch when a stale form is refused.
12. **Only `backstage/app-config.yaml` names the kind.** `app-config.docker.yaml` layers over it and restates only the locations; a test asserts it.
13. **`definition_pinned` is excluded from the generated `ServiceFabricApp` form** (`formExclude`).
14. **The transform refuses a partial chart** (name without repository or version). Added so a half-pinned application fails where it can be read.
15. **Six clarification questions, not five**, because the author supplied a list.

### Existing tests I changed

Nothing was deleted or weakened. Two were changed, each because the thing it asserted moved:

- `tests/unit/test_crossplane_fabric_app.py::test_the_portal_prefill_states_local` read the template's prefilled values. The prefill is gone (the requester picks an entry), so it now asserts the same claim, `externalTrafficPolicy: Local`, on the requestable entry's `default_values`, and asserts the field is gone.
- `tests/unit/test_fabric_app_generator.py`: the test double `_RecordingNode` gained a `definition` that is unset, because the generator now reads it first.
- Added, not changed: `CATALOGUE_KINDS` in `tests/unit/test_service_layer_menu_contract.py`; `definition_pinned` in `WRITE_BACKS` of `tests/unit/test_service_trigger_contract.py`.

## Files touched, by area

- **Schema**: `schemas/catalogue/application_catalogue.yml` (new), `schemas/service/kubernetes_services.yml`, `src/solution_arista_avd/protocols.py` (regenerated with `infrahubctl protocols`; remember it ignores `extensions:`).
- **Menu**: `menus/menu.yml`.
- **Objects and seeding**: `objects/35a_otternet_app_catalogue.yml` (new), `objects/36_otternet_app_services.yml`, `scripts/seed_app_payloads.py`, `.vale/config/vocabularies/OpsMill/accept.txt` (`requestable`).
- **Generator and transform**: `generators/generate_fabric_app.py`, `transforms/crossplane_fabric_app.py`.
- **Portal**: `backstage/catalog/exposed-app-with-access.yaml`, `backstage/app-config.yaml`, `backstage/plugins/infrahub-backend/src/provider.ts`, `provider.test.ts`.
- **Demo**: `scripts/demo_rehearsal.py` (act one; `demo_full_run.py` delegates to it and needed no change).
- **Docs**: `docs/docs/service-portal.md`, `demo-runbook.md`, `demo-builder.md`, `developer-guide/{schemas,generator-transform-inventory,service-triggers,tooling-cluster}.md`, `AGENTS.md`.
- **Tests (new)**: `test_application_catalogue_schema_contract.py`, `test_application_catalogue_seed_data.py`, `test_fabric_app_pin.py`, `test_application_catalogue_portal.py`, `test_demo_act_one.py`. **Extended**: `test_service_layer_menu_contract.py`, `test_service_trigger_contract.py`, `test_crossplane_fabric_app.py`, `test_fabric_app_generator.py`.
- **Spec Kit**: `specs/035-application-catalogue/`, `.specify/feature.json`.

## What could not be verified offline

- **Schema load.** Only `SchemaRoot` shape validation ran. Relationship direction pairing (`definition` outbound, `applications` inbound, same identifier), the `TextArea` and `Number` parameters, and the new kind's reserved-name check are server rules.
- **Object load of the new file**, including a multi-line text value with `otternet.lab/advertise` in it, and the relationship references `lab-whoami` and `junos-http`.
- **File creation inside a generator on a branch.** `save_file_if_changed` is proven for the seeding script against a live instance, not as a generator step. Also the SDK assumptions: `service.definition.fetch()` then `.peer`, `fetch()` on the many relationships before `peer_ids`, `.add(id)`.
- **The two-run cost.** I argue the pin adds no run (its writes are unwatched); a live run counts it.
- **The portal.** No `node_modules`, so `provider.ts` and the jest cases in `provider.test.ts` were not compiled or run. The template was only parsed, never rendered or submitted. Backstage's treatment of `catalogFilter` with `metadata.tags`, and the annotation key in `catalog:fetch`, are from reading the provider's source.
- **Entity graph.** The entry's inverse `applications` relationship may make the provider emit `dependsOn` links from the entry to every application, and each application's `definition` link back: a cycle in the catalogue graph. Check it renders.
- **Integration tests** (`invoke test --integration`) and the repeated-run idempotence skill.
- **`schema.graphql`** is stale (no new kind). Nothing offline reads it for this change.

## Lab-phase checklist

1. **Schema.** `infrahubctl schema check schemas` on a branch, then `infrahubctl schema load schemas`. Expect the new kind, the `definition` and `definition_pinned` fields. Existing applications must keep loading (nothing became mandatory).
2. **Objects.** `invoke load` loads `35a_otternet_app_catalogue.yml` before `36_otternet_app_services.yml`. Run it twice: the second must change nothing. Then run `scripts/seed_app_payloads.py` (the `invoke load` path calls it): expect the three `lab-*` entries to report `default_values set`, and a second run `unchanged`.
3. **Regenerate** `schema.graphql`: `uv run infrahubctl graphql export-schema --destination schema.graphql`; commit it. No `*_query.py` needs regenerating (the `.gql` files did not change); confirm with `git diff --stat`.
4. **Rendered output unchanged.** After the load, regenerate nothing and compare the three seeded applications' `Crossplane FabricApp` artifacts with their checksums from before. They must be identical.
5. **Rebuild the portal.** `uv run invoke backstage-build` (never a bare `docker compose build`), then `uv run invoke tooling` to roll it. Run the plugin tests first: `cd backstage && yarn workspace @opsmill/backstage-plugin-infrahub-backend test`.
6. **Check the portal.** The catalogue shows one Resource of type `application-definition`: `whoami`, tagged `requestable`; the three `lab-*` entries are present and untagged. The template's picker lists only Who am I. Check the entry graph for a cycle (above).
7. **Request one.** Run act one, `uv run invoke demo-run`. Expect the new `PASS` lines: the application points at `whoami`, was pinned (chart whoami 6.0.0, `definition_pinned` true), has a values file, advertises `junos-http`, and the rendered `FabricApp` shows chart `whoami` 6.0.0 and the entry's values. Count `action-run-generator` runs on the branch: a create costs two.
8. **Pin holds.** Edit `whoami`'s `chart_version` on a branch in Infrahub, regenerate, and confirm the earlier application's artifact does not change. Set `whoami` to `deprecated` and confirm it leaves the picker.
9. **Refusal.** Submit the template with a hand-edited form naming `lab-metrics`; the run must stop at `create_app` with no application created (an orphan branch remains: delete it).
10. **Restore.** `uv run invoke demo-restore` must still report the baseline: the catalogue entries are seed data and stay.

## The Claude Doc 'NFD41 demo: complete run-through'

Act one's form changes. **Remove** the rows for the chart repository, chart name and chart version, and every mention of the ports, the `/28` block and the prefilled chart values as things the presenter leaves at their defaults. **Add** a row: *Application: Who am I* (the only entry in the picker). Keep the application name `otter-shop`, the namespace, the request reference and the defaults for cluster, VRF and source site. Add a sentence for the presenter: the lab's own Grafana, Prometheus and Telegraf are catalogue entries and are not in the list, because they are not requestable. Two new things worth saying: the run now **reads the entry again** before creating anything, and the generator **pins** the chart and values once, so editing the catalogue later changes nothing already requested.
