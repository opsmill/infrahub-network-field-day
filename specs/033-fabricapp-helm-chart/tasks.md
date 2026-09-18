---
description: "Task list for 033-fabricapp-helm-chart"
---

# Tasks: Fabric Application as a Helm Chart

**Input**: Design documents from `/specs/033-fabricapp-helm-chart/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/schema-kinds.md](./contracts/schema-kinds.md), [quickstart.md](./quickstart.md)

**Tests**: Included. Not optional here — Constitution IV requires tests for changed
behaviour, and SC-007 names a specific existing test that must be inverted.

**Organization**: Tasks are grouped by user story. **Read the Dependencies section
before starting**: these stories are *not* independently deliverable, and the
reason is structural rather than an oversight.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths are given in every task

## Path Conventions

Infrahub reference-design repository. Schema YAML under `schemas/`, seed data
under `objects/` and `payloads/`, generated protocols at
`src/solution_arista_avd/protocols.py`, tests under `tests/unit/`.

---

## Phase 1: Setup

**Purpose**: Get to a state where a schema load is safe to attempt.

- [ ] T001 Reconcile the uncommitted working-tree changes to `schemas/service/access_services.yml` and `generators/generate_app_access.gql` — commit, stash or revert them. They add a `granted_source_prefixes` relationship to `ServiceAppAccess`; `infrahubctl schema load schemas/` loads the **whole directory**, so this feature's load will carry that change too and a failure in it will read as a failure in this feature
- [ ] T002 Create the working branch: `uv run infrahubctl branch create 033-fabricapp-helm-chart`
- [ ] T003 [P] Capture the pre-change baseline — record the rendered Junos artifact checksum for `fw1` and the current `ServiceFabricApp` list, so SC-008 ("the firewall artifact does not move") can be asserted against a recorded value rather than a memory

**Checkpoint**: A clean tree, a branch, and a baseline to compare against.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The data migration. Research R1 and R2 measured that the schema load
is **refused** until this is done, and that the manifests file objects become
unreachable rather than deleted once the kind is gone.

**⚠️ CRITICAL**: No schema change may be loaded until this phase is complete.

- [ ] T004 Write the migration script at `scripts/migrate_fabric_app_charts.py` that queries **every** `ServiceFabricApp` from the graph and reports which lack `chart_repository`, `chart_name` or `chart_version`. It must enumerate from the graph, not from `objects/` — the developer stack carries a `podinfo` application created through the portal that appears in no seed file (research R1)
- [ ] T005 Extend `scripts/migrate_fabric_app_charts.py` to populate the three chart fields on every application that lacks them, taking values per application rather than a shared default. `default_value` is rejected: an application silently acquiring a chart nobody chose renders, merges and delivers (research R1)
- [ ] T006 Extend `scripts/migrate_fabric_app_charts.py` to delete every `ServiceFabricAppManifestsFile` instance and report the count. This must run **before** the kind is withdrawn — the loader removes the kind whether or not instances exist, after which there is no way to query for what remains (research R2), which is what makes SC-004 checkable
- [ ] T007 Run the migration against branch `033-fabricapp-helm-chart` and record its output: how many applications were populated and how many file objects were deleted

**Checkpoint**: Every application carries a chart and no manifests file objects
remain. The schema load will now be accepted.

---

## Phase 3: User Story 1 - A chart is the whole workload source (Priority: P1)

**Goal**: The three chart fields become mandatory, so a renderer may read them
without a null check and an incomplete chart is refused by the model rather than
by the cluster.

**Independent Test**: Create a `ServiceFabricApp` naming only a cluster, a
namespace and the three chart fields — accepted. Create one omitting
`chart_version` — refused at create time.

### Tests for User Story 1

- [ ] T008 [US1] Invert `test_fabric_app_workload_source_supports_chart_manifests_or_both` in `tests/unit/test_service_layer_schema_contract.py` — rename it to assert the single supported source and assert `chart_repository`, `chart_name` and `chart_version` are `optional: false` while `chart_values` stays `optional: true` (SC-007). It must FAIL before T010

### Implementation for User Story 1

- [ ] T009 [US1] Add a comment block above the chart attributes in `schemas/service/kubernetes_services.yml` recording why all three are mandatory together: the XRD requires `[repository, name, version]` whenever `chart` is present, so this states downstream's existing constraint a step earlier, where it can be caught before an artifact is rendered (research R6)
- [ ] T010 [US1] Set `optional: false` on `chart_repository`, `chart_name` and `chart_version` in `schemas/service/kubernetes_services.yml`; leave `chart_values` at `optional: true`

**Checkpoint**: T008 passes. The load itself happens in Phase 6.

---

## Phase 4: User Story 2 - Raw manifests leave the model (Priority: P1)

**Goal**: An application cannot be expressed as raw API objects, and nothing is
left pointing at a kind that no longer exists.

**Independent Test**: The loaded schema has no `manifests` attribute, no
`manifests_file` relationship, and `ServiceFabricAppManifestsFile` does not
resolve.

### Tests for User Story 2

- [ ] T011 [P] [US2] Narrow `APP_FILE_KINDS` to `("FabricAppValuesFile",)` in `tests/unit/test_service_layer_schema_contract.py` and drop the `FabricAppManifestsFile` entry from `APP_FILE_IDENTIFIERS`. Six parametrized tests run off these and all six currently assert the withdrawn kind exists
- [ ] T012 [P] [US2] Drop the `attributes["manifests"]["kind"] == "JSON"` assertion from `test_app_keeps_its_inline_payload_attributes` in `tests/unit/test_service_layer_schema_contract.py`, keeping the `chart_values` one
- [ ] T013 [US2] Add a test to `tests/unit/test_service_layer_schema_contract.py` asserting the YAML declares **no** `manifests` attribute, **no** `manifests_file` relationship and **no** `FabricAppManifestsFile` node — this is what catches a `state: absent` block left behind after the load (research R3)

### Implementation for User Story 2

- [ ] T014 [US2] Mark `manifests`, `manifests_file` and the `FabricAppManifestsFile` node with `state: absent` in `schemas/service/kubernetes_services.yml`. **This is a migration step, not the end state** — T025 deletes these blocks after the load
- [ ] T015 [US2] Update the block comment on `ServiceFabricAppValuesFile` in `schemas/service/kubernetes_services.yml` so the precedence rule (attachment beats the inline attribute) is still stated. It is currently written once for the pair; removing the manifests half removes the only place two of the three reasons for file attachments are recorded

**Checkpoint**: T011–T013 pass against the YAML. T013 will still fail until T025.

---

## Phase 5: User Story 3 - An exposed application names the services its VIP answers on (Priority: P1)

**Goal**: An application relates to the `SecurityService` objects its VIP answers
on, so a grant reads one object that carries both a port and a protocol.

**Independent Test**: Relate an application to `junos-http`; it resolves to
`('junos-http', 80, 'tcp')` and the service object is unchanged.

### Tests for User Story 3

- [ ] T016 [P] [US3] Add a test to `tests/unit/test_service_layer_schema_contract.py` asserting the `advertised_services` relationship on `FabricApp` has `peer: SecurityService`, `kind: Generic`, `cardinality: many`, `optional: true`, `on_delete: no-action` and identifier `service__app_advertised_services`
- [ ] T017 [P] [US3] Add a test to `tests/unit/test_service_layer_schema_contract.py` asserting the peer is `SecurityService` and **not** `SecurityGenericService`, naming the reason: the generic also covers `SecurityServiceRange` and `SecurityServiceGroup`, neither of which has a single `port`, and the access generator works in integers throughout (FR-027)

### Implementation for User Story 3

- [ ] T018 [US3] Add the `advertised_services` relationship to `ServiceFabricApp` in `schemas/service/kubernetes_services.yml` at `order_weight: 945`, exactly as specified in [data-model.md](./data-model.md)
- [ ] T019 [US3] Add a comment block above it recording the two things that are not visible from the YAML: `on_delete: no-action` is deliberate because the only alternative, `cascade`, deletes the **peer** — deleting an application would delete `junos-http` and the four baseline rules that share it; and naming a service never marks it `managed_by_service`, which is what makes revocation safe without a name comparison

**Checkpoint**: T016–T017 pass. The schema file now carries all three stories'
changes and is ready for a single load.

---

## Phase 6: Integration — the load, and the second edit

**Purpose**: One load serves US1, US2 and US3. The `state: absent` blocks are
then deleted, because `infrahubctl protocols` reads the YAML and ignores them
(research R3) — leaving them would make `protocols.py` advertise three things
that do not exist at runtime, with mypy clean.

- [ ] T020 Run `uv run infrahubctl schema check schemas/ --branch 033-fabricapp-helm-chart` and confirm the diff is exactly: `manifests` removed, `manifests_file` removed, `advertised_services` added, `ServiceFabricAppManifestsFile` removed, and `optional` changed on the three chart attributes. Any other entry is a failure
- [ ] T021 Run `uv run infrahubctl schema load schemas/ --branch 033-fabricapp-helm-chart --wait 60` and confirm "Schema updated on all workers"
- [ ] T022 Run quickstart Scenario 3 to confirm the withdrawn surface is gone: `ServiceFabricAppManifestsFile` raises `SchemaNotFoundError`, and the application has no `manifests` and no `manifests_file` but does have `advertised_services` (SC-003, SC-004)
- [ ] T023 Run quickstart Scenario 5 to confirm `advertised_services` resolves to `('junos-http', 80, 'tcp')` and leaves the service object unchanged (SC-005). Remember `await ...fetch()` before `add()`, or it raises `UninitializedError` (research R4)
- [ ] T024 Run quickstart Scenario 4 to confirm an application omitting `chart_version` is refused at create time (SC-002)
- [ ] T025 Delete the three `state: absent` blocks from `schemas/service/kubernetes_services.yml` entirely, now that the load has applied them. T013 should now pass
- [ ] T026 Regenerate protocols: `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py`. Never hand-edit the result (Constitution III)
- [ ] T027 Verify the regenerated `src/solution_arista_avd/protocols.py`: `grep -c "ServiceFabricAppManifestsFile"` prints `0`, the three chart fields are `String` rather than `StringOptional`, `advertised_services` appears as `RelationshipManager[SecurityService]`, and neither `manifests` nor `manifests_file` is present (quickstart Scenario 6)

**Checkpoint**: The graph and the generated protocols agree. US1, US2 and US3 are
complete and verifiable.

---

## Phase 7: User Story 4 - The seeded application is a chart (Priority: P2)

**Goal**: A freshly bootstrapped instance demonstrates the only supported shape.

**Independent Test**: A fresh load produces an `nfd41-demo` naming a chart and
carrying no manifests, whose artifact renders without raising.

**Knowingly lost**: the backend `ClusterIP` Service and the two L7
`CiliumNetworkPolicy` objects, and with them the ClusterIP backend's
unreachability as an asserted negative and the L7 policy example. Decided in
research R5; recorded so its absence later reads as a decision.

### Implementation for User Story 4

- [ ] T028 [P] [US4] Create `payloads/nfd41-demo-values.yaml` with the chart values: `service.type: LoadBalancer`, `service.ports.http: 80`, `commonLabels: {nfd41.lab/advertise: "true"}` and `replicaCount: 3`. `commonLabels` feeds the Service's `metadata.labels` while the selector uses the chart's narrower `whoami.selectorLabels` helper, so this does not mutate an immutable field (research R5)
- [ ] T029 [P] [US4] Delete `payloads/nfd41-demo-manifests.yaml`
- [ ] T030 [US4] Update `objects/36_nfd41_app_services.yml`: add `chart_repository: https://cowboysysop.github.io/charts/`, `chart_name: whoami`, `chart_version: "6.0.0"` and `advertised_services: [junos-http]`. Replace the file header comment, which currently explains why the manifests payload is a file attachment rather than an attribute
- [ ] T031 [US4] Update `PAYLOADS` in `scripts/seed_app_payloads.py` to map `nfd41-demo` to the values file and the `ServiceFabricAppValuesFile` kind, and remove the `ServiceFabricAppManifestsFile` entry — the kind no longer resolves, so the script raises on the old one
- [ ] T032 [US4] Add a test to `tests/unit/` asserting `objects/36_nfd41_app_services.yml` names a chart repository, name and version and lists `junos-http` under `advertised_services`, and that no `payloads/*manifests*.yaml` file remains
- [ ] T033 [US4] Verify chart version `6.0.0` against the live repository index before pinning it, and record the app version it ships. `6.0.0` maps to `traefik/whoami:v1.11.0`, which is the image the demo already runs — if that has moved, the pin is the thing to change, not the image

**Checkpoint**: A fresh `invoke load` seeds an application that is a chart.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T034 [P] Update `docs/docs/developer-guide/schemas.md` where it describes the application's workload source as a chart, manifests, or both
- [ ] T035 [P] Update the `ServiceFabricApp` description in `AGENTS.md` — the generator and transform inventory says `manifests` and `chart_values` are `JSON` kind and that `crossplane_fabric_app` raises when both are missing, neither of which will be true
- [ ] T036 [P] Add a note to `AGENTS.md` recording the two findings a future cycle will otherwise rediscover: making an attribute mandatory is refused against existing data and names the node but never the attribute, and `infrahubctl protocols` ignores `state: absent` so the blocks must be deleted after the load
- [ ] T037 Run `uv run pytest tests/unit` on its own and read the result. Do not pipe it to `tail` or `head` — a pipeline reports the last command's status, so a failing suite exits `0` through the pipe
- [ ] T038 Run `uv run invoke lint` on its own and read the result, same reason
- [ ] T039 Confirm SC-008: re-render the Junos artifact for `fw1` and compare against the T003 baseline. It must be unchanged — `junos-http` is port 80 and the seeded application's chart serves on 80, so no grant's rendered ports move
- [ ] T040 Run `$infrahub-run-integration-tests` and record the tested branch and commit (Constitution IV, Mandatory Validation Skills). `$infrahub-test-generator-idempotence` does **not** apply: no generator changes in this cycle
- [ ] T041 Delete the working branch once merged: `uv run infrahubctl branch delete 033-fabricapp-helm-chart`

---

## Dependencies & Execution Order

### These four stories are not independently deliverable, and that is structural

The template's usual assumption — each story ships alone — does not hold here,
for two measured reasons:

1. **US1, US2 and US3 are three edits to one file applied by one load.**
   `schemas/service/kubernetes_services.yml` is loaded whole; there is no way to
   load the mandatory chart fields without also loading the withdrawn manifests
   and the new relationship. Phase 6 therefore exists as a shared integration
   phase rather than being duplicated three times.
2. **US1 depends on US4's content, inverting the priority order.** Making the
   chart fields mandatory is refused until every existing application carries a
   chart (research R1), and deciding what `nfd41-demo`'s chart *is* belongs to
   US4. Phase 2 resolves this by migrating the data with the values US4 will
   later seed, so the dependency is discharged before US1 rather than left as a
   cycle.

What each story *does* keep is an independent **test**: US1's mandatory fields,
US2's withdrawn surface and US3's relationship are each separately assertable
after the shared load, which is what the checkpoints verify.

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies. T001 first — an unreconciled tree makes every later load ambiguous
- **Phase 2 (Foundational)**: depends on Phase 1. **BLOCKS Phases 3–7**
- **Phases 3, 4, 5 (US1, US2, US3)**: depend on Phase 2. Edits to one file, so sequential
- **Phase 6 (Integration)**: depends on Phases 3, 4 and 5 all being complete
- **Phase 7 (US4)**: depends on Phase 6 — `scripts/seed_app_payloads.py` cannot reference a kind until it is gone
- **Phase 8 (Polish)**: depends on Phase 7

### Ordering traps

- **T014 before T021 before T025.** `state: absent` must be *loaded* before the blocks are deleted. The two states are not simultaneously correct, and skipping straight to deletion leaves an existing instance carrying the kind forever
- **T026 after T025.** Regenerating protocols while the absent blocks are still present prints `2` for `ServiceFabricAppManifestsFile` — expected as an intermediate state, wrong as a committed one
- **T006 before T021.** Once the kind is withdrawn the file objects cannot be found, so deleting them afterwards is not possible

### Parallel Opportunities

- T003 runs alongside T001–T002
- T011 and T012 are different functions in one file and may be written together; T016 and T017 likewise
- T028 and T029 are different files in `payloads/`
- T034, T035 and T036 are documentation, all independent
- **Nothing in Phases 3–5 is parallel across stories** — all three edit `schemas/service/kubernetes_services.yml`

### Parallel Example: Phase 8

```text
T034  docs/docs/developer-guide/schemas.md
T035  AGENTS.md — inventory description
T036  AGENTS.md — the two findings
```

T035 and T036 touch the same file; do them in one pass rather than concurrently.

---

## Implementation Strategy

### MVP scope

**Phases 1, 2, 3, 4, 5 and 6** — the schema, migrated, loaded and verified, with
protocols regenerated. That is the whole of this cycle's contract: the surface
downstream consumers are written against. At that point `nfd41-demo` carries the
chart the migration gave it and the graph is correct, but the seed data does not
yet reproduce it on a fresh instance.

US4 (Phase 7) makes the result survive a rebuild and is what SC-006 asserts.
Phase 8 is the gate.

### Incremental delivery

1. Phases 1–2: safe to stop. Data is migrated; nothing is withdrawn yet
2. Phases 3–6: the schema change, complete and verified. Safe to stop and review
3. Phase 7: the seeded example follows the new shape
4. Phase 8: documentation, linters, integration tests, SC-008 evidence

### What this cycle deliberately does not do

The renderer, the access generator and the two portals are listed in
[contracts/schema-kinds.md](./contracts/schema-kinds.md) §6 and land in the
Transform and Generator cycles the routing chain names. **They will be broken
between this cycle and those**: `crossplane_fabric_app` queries `manifests` and
`generate-app-access` derives ports from it, and neither field will exist. That
is the cost of one artifact type per cycle, and it is the reason Phase 8 runs the
integration suite rather than declaring victory on unit tests.
