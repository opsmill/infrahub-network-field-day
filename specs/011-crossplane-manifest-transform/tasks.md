---

description: "Task list for the Crossplane FabricPeering manifest transform"
---

# Tasks: Crossplane FabricPeering Manifest

**Input**: Design documents from `/specs/011-crossplane-manifest-transform/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/manifest-contract.md](./contracts/manifest-contract.md), [quickstart.md](./quickstart.md)

**Tests**: **REQUIRED.** Constitution IV mandates unit tests before merge, and spec FR-040/FR-041 name them explicitly. They also matter more here than usual: the three error paths in FR-017 are only reachable from fixtures, because the live schema's own constraints make an incomplete model hard to create. Each story writes its tests before its implementation.

**Organization**: Grouped by the three user stories from spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3
- Exact file paths appear in every task

## Path Conventions

Per the plan's Structure Decision, which follows `avd_anta_catalog` and
`containerlab_topology` rather than the skill template's suggested `queries/` layout:

- Query, generated model and transform all co-located in `transforms/`
- No template: the manifest is emitted with `yaml.dump` (research R1a)
- Registration in `.infrahub.yml`
- Unit tests in `tests/unit/`

---

## Phase 1: Setup

**Purpose**: A branch to work on, and confirmation the model actually holds what the transform will read

- [X] T001 Verify preflight: `uv sync --all-packages` then `uv run infrahubctl info`, confirming Connection Status ✅ and Infrahub 1.10.6, per [quickstart.md](./quickstart.md) Prerequisites
- [X] T002 Create the working branch with `uv run infrahubctl branch create cx-peering`, then `uv run infrahubctl schema load schemas --branch cx-peering --wait 30` and `uv run infrahubctl object load objects/ --branch cx-peering`
- [X] T003 Confirm the transform has data to read by querying `ClusterKubernetes` against `http://localhost:8000/graphql/cx-peering` (or the UI) and checking it returns `nfd41` with `local_asn` 65401, two `fabric_peerings`, and peer addresses `10.110.0.2/24` and `10.110.0.3/24`. If any is missing, stop — every acceptance criterion in this cycle depends on it

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The artifact target. Nothing renders against a target that does not exist, so this blocks the live render in US1 and all of US2.

**⚠️ CRITICAL**: US1's unit tests run without this, but US1's live render (T018) and every US2 task need it.

- [X] T004 Add a `service_fabric_peerings` entry to the `CoreStandardGroup` list in `objects/00_groups.yml`. The name is not invented here — `specs/010-lab-service-layer-model/contracts/schema-kinds.md` section 6 already declared it as this artifact's target group
- [X] T005 Create `objects/35_nfd41_peering_service.yml` defining one `ServiceFabricPeering` per [data-model.md](./data-model.md) section 6: name `nfd41-fabric-peering`, status `active`, an `owner`, `cluster` `nfd41`, both `ClusterFabricPeering` objects in `peerings`, `communities` `["65401:110"]`, and `advertisement_selector` `["nfd41.lab/advertise=fabric"]`. Add it to the `service_fabric_peerings` group
- [X] T006 Resolve the `owner` reference form while writing T005. `ServiceGeneric.owner` peers `OrganizationGeneric`, which does have a human-friendly id, so a scalar tenant name should resolve — but if the load reports `Unable to find the node`, switch to an inline `kind: OrganizationTenant` block. [data-model.md](./data-model.md) section 6 flags this as unverified, and this session hit the generic-reference distinction repeatedly
- [X] T007 Load it with `uv run infrahubctl object load objects/00_groups.yml objects/35_nfd41_peering_service.yml --branch cx-peering` and confirm zero errors
- [X] T008 Prove SC-011 by running `uv run infrahubctl object load objects/35_nfd41_peering_service.yml --branch cx-peering` a second time and confirming no uniqueness violation and exactly one `ServiceFabricPeering`. `ServiceFabricPeering` inherits its human-friendly id from `ServiceGeneric`, so unlike `SecurityPolicyRule` it upserts cleanly — but verify rather than assume

**Checkpoint**: The artifact has a target, and loading it is idempotent.

---

## Phase 3: User Story 1 - Render the peering manifest from the model (Priority: P1) 🎯 MVP

**Goal**: An operator changes the cluster's BGP settings in Infrahub and gets back the exact `FabricPeering` resource the lab's Crossplane composition consumes, without editing YAML by hand.

**Independent Test**: `uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering --branch cx-peering` prints a `FabricPeering` resource matching [contracts/manifest-contract.md](./contracts/manifest-contract.md) section 1, and `kubectl apply --dry-run=client` accepts it.

### Tests for User Story 1 ⚠️

> Write these first. They will fail on import until T014 exists — that is the expected starting state.

- [X] T009 [P] [US1] Create `tests/unit/test_crossplane_fabric_peering.py` with a fixture builder returning a query-response dictionary shaped like `CrossplaneFabricPeeringQuery`, following the fixture style of `tests/unit/test_avd_anta_catalog.py`. One helper that takes overrides keeps the error-path tests in Phase 5 short
- [X] T010 [P] [US1] Add selector-parsing tests to `tests/unit/test_crossplane_fabric_peering.py`: `nfd41.lab/bgp=true` becomes `{"nfd41.lab/bgp": "true"}`, and `nfd41.lab/x=a=b` becomes `{"nfd41.lab/x": "a=b"}` — split on the **first** `=` only, because a label value may legitimately contain one ([data-model.md](./data-model.md) section 3)
- [X] T011 [P] [US1] Add an address-stripping test to `tests/unit/test_crossplane_fabric_peering.py`: a `peer_address` of `10.110.0.2/24` renders as `10.110.0.2`, because a BGP neighbour is an address and not a prefix
- [X] T012 [P] [US1] Add a deterministic-ordering test to `tests/unit/test_crossplane_fabric_peering.py`: given peerings supplied in reverse order, `peers` renders sorted by name. Asserting this from a fixture is what makes the guarantee independent of the schema's `order_by`, per [research.md](./research.md) R7
- [X] T013 [P] [US1] Add a disabled-peering test and a structural test to `tests/unit/test_crossplane_fabric_peering.py`: a peering with `enabled: false` is absent from `peers` (FR-016), and the rendered output parses as YAML carrying `apiVersion: nfd41.lab/v1alpha1` and `kind: FabricPeering` (FR-041)

### Implementation for User Story 1

- [X] T014 [US1] Create `transforms/crossplane_fabric_peering.gql` exactly as specified in [contracts/manifest-contract.md](./contracts/manifest-contract.md) section 3: operation name `CrossplaneFabricPeeringQuery`, one `$name: String!` variable, the target aliased `target:`, traversing to `cluster` and `peerings` in a single round trip
- [X] T015 [US1] Generate the typed model with `uv run infrahubctl graphql generate-return-types transforms/crossplane_fabric_peering.gql`, producing `transforms/crossplane_fabric_peering_query.py`. This is also the first real proof the query is valid against the live schema — a wrong field name fails here. **Never hand-edit the result**, including to satisfy mypy
- [X] T016 [US1] ~~Create `transforms/templates/crossplane_fabric_peering.j2`~~ — **superseded, template deleted.** Per research R1a the manifest is emitted with `yaml.dump` through a `SafeDumper` subclass instead: key order fixed by dict insertion order plus `sort_keys=False`, per [contracts/manifest-contract.md](./contracts/manifest-contract.md) section 1; optional fields omitted when unset rather than `null` or empty (FR-018); quoting decided by the resolver, so `true` stays a string without a hand-written quote
- [X] T017 [US1] Create `transforms/crossplane_fabric_peering.py` with `CrossplaneFabricPeeringTransform(InfrahubTransform)`, `query = "crossplane_fabric_peering"` matching the **registered** query name rather than the GraphQL operation name, parsing through `CrossplaneFabricPeeringQuery(**data)` and aliasing the long generated class names at module scope as `transforms/avd_anta_catalog.py` does. Do the selector parsing, address stripping and sorting in Python, then emit with `yaml.dump`, per [research.md](./research.md) R1a
- [X] T018 [US1] Run `uv run pytest tests/unit/test_crossplane_fabric_peering.py -v` and confirm all pass, then render live with `uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering --branch cx-peering` and check by eye against [quickstart.md](./quickstart.md) Step 5: `localASN: 65401`, `nodeSelector` a map with a quoted value, both peers without `/24`, `k8s-leaf1` before `k8s-leaf2`, and no password anywhere
- [X] T019 [US1] Prove SC-004 per [quickstart.md](./quickstart.md) Step 6: render twice into separate files and confirm `diff` reports nothing. A difference here means key order or peer sorting is not pinned
- [X] T020 [US1] Prove SC-005 per [quickstart.md](./quickstart.md) Step 7: change the cluster's `local_asn` on the branch, re-render, confirm **exactly** the `localASN` line differs, then revert. This is the property the whole feature exists for — change the model, re-render, review the diff

**Checkpoint**: MVP complete. The manifest is generated from the model, deterministically, and a one-field change moves one line.

---

## Phase 4: User Story 2 - Store it as an artifact the cluster can pull (Priority: P2)

**Goal**: The rendered manifest is attached to its service as a versioned Infrahub artifact, so an in-cluster operator can fetch it rather than someone copying YAML into a repository.

**Independent Test**: After a repository sync and artifact generation, an artifact exists against the `ServiceFabricPeering` object with content type `application/yaml`, and fetching it returns the same bytes the transform prints.

**Dependencies**: US1 (the transform must render) and Phase 2 (the target must exist).

- [X] T021 [P] [US2] Register the query in `.infrahub.yml` under `queries` as `crossplane_fabric_peering` with `file_path: "./transforms/crossplane_fabric_peering.gql"`, following the existing entries' style
- [X] T022 [P] [US2] Register the transform in `.infrahub.yml` under `python_transforms` as `crossplane_fabric_peering` with `class_name: CrossplaneFabricPeeringTransform` and `file_path: "./transforms/crossplane_fabric_peering.py"`
- [X] T023 [US2] Register the artifact definition in `.infrahub.yml` under `artifact_definitions` exactly as [contracts/manifest-contract.md](./contracts/manifest-contract.md) section 2 specifies: `content_type: "application/yaml"` matching the repository's convention for YAML artifacts, `targets: "service_fabric_peerings"`, `transformation: "crossplane_fabric_peering"`, and `parameters.name: "name__value"`
- [X] T024 [US2] Run `uv run yamllint .infrahub.yml` and confirm the three new registrations are well-formed
- [X] T025 [US2] Sync the repository so Infrahub re-reads `.infrahub.yml`, and confirm all three registrations are accepted with no error (US2 acceptance scenario 1). A mismatch between the transform's `query` attribute and the registered query name surfaces here
- [X] T026 [US2] Generate artifacts for the `service_fabric_peerings` group (from the Infrahub UI's artifact view, or by triggering the definition registered in `.infrahub.yml`) and confirm one is produced against the `nfd41-fabric-peering` object with content type `application/yaml`, then fetch it and confirm the bytes match what T018 printed
- [X] T027 [US2] Prove US2 acceptance scenario 3 by regenerating the `crossplane_fabric_peering` artifact (same route as T026) with the model unchanged, and confirming the artifact's checksum is unchanged. Compare against the checksum recorded in T026. This is SC-004 observed through the artifact rather than through stdout, and it is what makes a changed checksum meaningful to an operator

**Checkpoint**: The manifest is a durable, versioned artifact whose checksum only moves when the model does.

---

## Phase 5: User Story 3 - Fail loudly on an incomplete model (Priority: P3)

**Goal**: A model that cannot produce a working manifest fails at render time with a message naming what is missing, rather than emitting a resource that applies cleanly and carries nothing.

**Independent Test**: Render a fixture whose cluster has no `local_asn` and confirm the transform raises with a message naming the cluster and the field.

**Dependencies**: US1. This hardens the transform rather than extending it — the validation guards the same render path.

### Tests for User Story 3 ⚠️

- [X] T028 [P] [US3] Add a test to `tests/unit/test_crossplane_fabric_peering.py` asserting that a fixture whose cluster omits `local_asn` raises, and that the message names both the cluster and the field (V-1 in [data-model.md](./data-model.md) section 4). A session with no local AS cannot come up, so rendering one is worse than failing
- [X] T029 [P] [US3] Add a test to `tests/unit/test_crossplane_fabric_peering.py` asserting that a fixture whose peerings are all disabled, or empty, raises rather than emitting an empty `peers` list (V-2). An empty list yields a resource that applies cleanly, reports healthy and carries no routes — the worst outcome available
- [X] T030 [P] [US3] Add a test to `tests/unit/test_crossplane_fabric_peering.py` asserting that a peering with no `peer_address` raises, naming that peering (V-3)
- [X] T031 [P] [US3] Add a test to `tests/unit/test_crossplane_fabric_peering.py` asserting that a selector entry containing no `=` raises, naming the entry (V-4), and that no rendered output ever contains a secret value — only `authSecretName` (V-5, SC-007)

### Implementation for User Story 3

- [X] T032 [US3] Implement the four validations in `transforms/crossplane_fabric_peering.py`, raising `ValueError` with a message naming the object and the field, following the shape `src/solution_arista_avd/avd.py` uses (`msg = f"..."` then `raise ValueError(msg)`, which is what ruff's rules expect). Do **not** add a status check — a `provisioning` service still renders, because whether to apply a manifest is an operator's decision and refusing would make the artifact useless for review before activation ([research.md](./research.md) R10)
- [X] T033 [US3] Run `uv run pytest tests/unit/test_crossplane_fabric_peering.py -v` and confirm every error path is covered and passing, then re-run T018's live render to confirm the happy path still works

**Checkpoint**: All three stories complete. The transform renders correctly, stores durably, and refuses to produce a manifest that would silently carry nothing.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: The acceptance oracle, the full gate, and the documentation

- [X] T034 Verify SC-002 per [quickstart.md](./quickstart.md) Step 8: render to a file and run `kubectl apply --dry-run=client -f` against it. If the lab cluster is not up, validate the shape by hand against `../lab/crossplane/platform/00-xrd-fabric-peering.yaml`, where `localASN` and `peers` are the only required fields
- [X] T035 Verify SC-003 by comparing the rendered manifest against `../lab/crossplane/platform/10-peering.yaml` field by field, normalising both through a sorted YAML dump as [quickstart.md](./quickstart.md) Step 8 shows. Expect the rendered version to be a **superset**: the hand-written file omits `authSecretName`, `timers`, `podCIDRCommunities` and both selectors because it relies on XRD defaults, and every field the render adds must carry the value the XRD would have defaulted to. Any difference in `localASN`, a peer name, address or ASN is a bug. Record the comparison in the feature directory as SC-003 evidence
- [X] T036 [P] Verify no **undeclared** dependency crept in: the transform imports `yaml`, so confirm `pyyaml` is listed in `[project].dependencies` in `pyproject.toml`, per [research.md](./research.md) R2. Declaring it also fixes the pre-existing undeclared `import yaml` in `generators/generate_avd_device_hostvar.py`
- [X] T037 [P] Verify no untyped response access: `grep -nE 'data\[.(ServiceFabricPeering|target).\]' transforms/crossplane_fabric_peering.py` must return nothing, and `CrossplaneFabricPeeringQuery` must be imported and used (Constitution III)
- [X] T038 Run `uv run mypy --show-error-codes src/solution_arista_avd transforms` and confirm it passes, then `uv run ruff check .` and `uv run ruff format .`
- [X] T039 Run the full gate: `uv run pytest tests/unit` and `uv run invoke lint`. Confirm ruff, yamllint, mypy and rumdl pass. `lint-prose` currently fails on 7 pre-existing errors in `docs/` unrelated to this feature — check the count is **unchanged** rather than assuming it is
- [X] T040 [P] Document the transform in `docs/docs/developer-guide/transforms.md`: what it renders, that `ServiceFabricPeering` is the artifact target and why the cluster is not, and that selectors are stored as `key=value` lists because of the JSON dotted-key server bug. Use relative Markdown links only, per the docs-sync constraints in AGENTS.md
- [X] T041 [P] Add the new prefix-role-style entries to `schemas/MARKETPLACE.md` only if this cycle changed anything there — it should not have. Instead confirm the JSON dotted-key finding recorded there is still accurate, since this transform is the first consumer of the `key=value` workaround
- [ ] T042 Delete the throwaway branch: `uv run infrahubctl branch delete cx-peering`, keeping only what the pull request needs
- [ ] T043 Obtain maintainer sign-off on the Principle IV exception recorded in [plan.md](./plan.md) (Complexity Tracking) — either install `$infrahub-run-integration-tests` and run it, or accept the alternative evidence set (fixture unit tests, live render, Kubernetes dry-run, repository sync and artifact generation) in the pull request description. This is the same open decision as cycle 010's T070

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — **blocks US1's live render and all of US2**
- **US1 (Phase 3)**: unit tests need only Setup; the live render needs Foundational
- **US2 (Phase 4)**: depends on US1 and Foundational
- **US3 (Phase 5)**: depends on US1 — it guards the same render path
- **Polish (Phase 6)**: depends on all three stories

### Dependency graph

```text
Setup → Foundational ─┬─→ US1 ─┬─→ US2 ──┐
                      │        │         ├─→ Polish
                      │        └─→ US3 ──┘
                      └─(blocks only US1's live render, not its unit tests)
```

### Within each story

1. Tests first — write them, watch them fail
2. Query, then the generated model (the model cannot exist before the query)
3. The transform (no template — research R1a)
4. Live render, then the determinism proofs

### One ordering constraint worth naming

T015 must follow T014 and cannot be parallelised with it: the generated model is derived
from the `.gql` file. It also cannot be hand-written to get ahead — regenerating is the
only correct way to produce it, and editing it is prohibited.

---

## Parallel Opportunities

### Phase 3 (US1) — the five test tasks

```bash
Task: "Fixture builder in tests/unit/test_crossplane_fabric_peering.py"
Task: "Selector-parsing tests"
Task: "Address-stripping test"
Task: "Deterministic-ordering test"
Task: "Disabled-peering and YAML-shape tests"
# All five extend one file, so write them in one pass; they are marked [P]
# because they are independent assertions with no ordering between them.
```

### Phase 4 (US2) — the two independent registrations

```bash
Task: "Register the query in .infrahub.yml"
Task: "Register the transform in .infrahub.yml"
# T023 (the artifact definition) must follow both, since it references them by name.
```

### Phase 5 (US3) — all four error tests

```bash
Task: "No local_asn raises"
Task: "No enabled peerings raises"
Task: "Missing peer_address raises"
Task: "Malformed selector raises; no secret in output"
```

### Phase 6 — the verification greps and the docs

```bash
Task: "grep for an undeclared yaml import"
Task: "grep for untyped response access"
Task: "Document the transform in docs/docs/developer-guide/transforms.md"
```

---

## Implementation Strategy

### MVP: User Story 1

US1 alone is a complete, useful increment: the manifest is generated from the model,
deterministically, and a one-field change moves one line. That is the property the feature
was requested for. US2 makes it durable; US3 makes it safe.

1. Phase 1: Setup (T001–T003)
2. Phase 2: Foundational (T004–T008)
3. Phase 3: US1 (T009–T020)
4. **STOP and VALIDATE**: render twice for a byte-identical diff, then change `local_asn`
   and confirm exactly one line moves
5. Demo: edit a value in the Infrahub UI, re-render, show the diff

### Incremental delivery

| Increment | Adds | Demonstrable outcome |
| --- | --- | --- |
| Foundational | The group and one service object | Nothing user-visible; the artifact has a target |
| US1 (MVP) | Query, model, transform | `FabricPeering` generated from the model, deterministically |
| US2 | Registration and the artifact | A versioned artifact whose checksum tracks the model |
| US3 | Four validations | An incomplete model fails loudly instead of shipping an empty peer list |

### Sequencing advice

Do **US3 before US2** if time is short. US2 is registration plumbing; US3 is the
difference between a renderer you can trust and one that can emit a manifest which
applies cleanly and carries nothing — which the lab's own notes call out as the failure
that "looks like a different problem" every time.

---

## Notes

- `[P]` = different files, or independent assertions with no ordering between them
- `transforms/crossplane_fabric_peering_query.py` is **generated**. Regenerate it with
  `infrahubctl graphql generate-return-types`; never hand-edit it, even to satisfy mypy
- The transform's `query` attribute matches the **registered** query name
  (`crossplane_fabric_peering`), not the GraphQL operation name
  (`CrossplaneFabricPeeringQuery`). Getting this wrong fails at repository sync
- Do not import `yaml`. The hybrid approach exists so the repository does not take a
  dependency it has not declared — see [research.md](./research.md) R2
- Selector storage is a `key=value` list because of an Infrahub 1.10.6 server bug, not a
  preference. `schemas/MARKETPLACE.md` records it
- The four limitations this transform cannot solve — cross-checking the rendered ASNs
  against what AVD put on the leaves, duplicate peer addresses, `bgp_timers` key
  validation, and two services referencing one cluster — belong to a `checks/` cycle and
  are catalogued in [data-model.md](./data-model.md) section 7. Do not try to solve them here
- Commit after each task or logical group; stop at any checkpoint to validate a story
