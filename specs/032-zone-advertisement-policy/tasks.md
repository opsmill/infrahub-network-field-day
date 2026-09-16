---

description: "Task list for the zone advertisement policy schema"
---

# Tasks: Zone Advertisement Policy

**Input**: Design documents from `/specs/032-zone-advertisement-policy/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. The spec requires them (FR-060 to FR-062) and constitution principle IV makes them a merge gate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are given in every task

## A note on story independence

Both fields land in the same two files — `schemas/security_extensions.yml` and `objects/32_nfd41_security.yml` — so the stories are **sequential on files**, not parallelisable across people. They are independently *deliverable* and independently *testable*, which is what matters:

- **US1** alone gives a generator the prefix list's name. Useful on its own: a generator could hardcode the border leaf and still work, badly.
- **US2** removes that hardcode, and is where the trap lives (`peer:` choice).
- **US3** adds no schema at all. It proves the two are usable together, which is the only thing the next cycle actually needs.

This is a small cycle. Resist padding it.

---

## Phase 1: Setup (Baseline)

**Purpose**: prove the starting point is clean, so a later failure is attributable

- [X] T001 Create the working branch with `uv run infrahubctl branch create zone-advert`, and confirm `uv run infrahubctl info` reports a healthy connection. Every later step runs against this branch; `main` is untouched until merge.
- [X] T002 Record the baseline: `uv run infrahubctl schema check schemas/` reports no errors, and `uv run pytest tests/unit -q` passes. A schema cycle that starts red cannot tell you what it broke.

**Checkpoint**: clean baseline on a branch.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the test module both stories write into

**⚠️ No story work can begin until this phase is complete.**

- [X] T003 Create `tests/unit/test_zone_advertisement_contract.py` with the YAML-loading helpers it needs, following the pattern in `tests/unit/test_fw_static_route_objects.py` — read `schemas/security_extensions.yml` and `objects/32_nfd41_security.yml` from `REPO_ROOT` and parse with `yaml.safe_load_all`. Contract tests here assert against the **files**, not a live server, so they run in CI without an instance.

**Checkpoint**: the test module imports and collects.

---

## Phase 3: User Story 1 — A zone knows what the DC advertises toward it (P1) 🎯 MVP

**Goal**: `SecurityZone` carries the name of the prefix list governing DC advertisement toward it, and the two zones that have one carry the right value.

**Independent test**: `infrahubctl schema check schemas/` passes; the six zones load; `branch` and `wan` return their prefix-list names and the other four return empty.

### Tests for US1

- [X] T004 [P] [US1] Assert in `tests/unit/test_zone_advertisement_contract.py` that `dc_advertised_prefix_list` exists on the `SecurityZone` extension in `schemas/security_extensions.yml`, is `kind: Text`, and is `optional: true`. The optionality is the load-bearing half — attributes default to **mandatory**, and four of the six zones supply no value.
- [X] T005 [P] [US1] Assert in `tests/unit/test_zone_advertisement_contract.py` that the attribute's `description` states it is a soft reference that nothing enforces (FR-013). An undocumented soft reference is how the next reader mistakes it for a validated one.
- [X] T006 [P] [US1] Assert in `tests/unit/test_zone_advertisement_contract.py` that exactly two zones in `objects/32_nfd41_security.yml` carry a prefix-list name — `branch` → `PL-DC-ADVERTISED-BRANCH` and `wan` → `PL-DC-ADVERTISED` — **and that `k8s-prod`, `app-prod`, `acme-cloud` and `globex-cloud` carry none**. The negative half is the half that matters: populating `acme-cloud` would look more complete and invert the field's meaning. See [contracts/seed-values.md](./contracts/seed-values.md).

### Implementation for US1

- [X] T007 [US1] Add `dc_advertised_prefix_list` to the existing `SecurityZone` entry in the `extensions.nodes` block of `schemas/security_extensions.yml`, per [contracts/schema-fields.md](./contracts/schema-fields.md): `kind: Text`, `optional: true`, `order_weight: 1300`. Place it after `trust_level` (1200); do not renumber anything. **Do not edit `schemas/security/security.yml`** — local additions live in the extensions file so a later `marketplace get` diffs cleanly.
- [X] T008 [US1] Set the two values on the `branch` and `wan` zone rows in `objects/32_nfd41_security.yml`. Leave the other four zones untouched.
- [X] T009 [US1] Run `uv run infrahubctl schema check schemas/`, then `uv run infrahubctl schema load schemas --branch zone-advert`, then `uv run infrahubctl object load objects/32_nfd41_security.yml --branch zone-advert`. All six zones must load. Depends on T007, T008.
- [X] T010 [US1] Regenerate `src/solution_arista_avd/protocols.py` with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py`. The diff must be small and additive. **Never hand-edit it** to satisfy a linter — constitution principle I. Depends on T009.

**Checkpoint**: US1 is independently testable. Run quickstart steps 1–4.

---

## Phase 4: User Story 2 — A zone knows which device carries that policy (P2)

**Goal**: `SecurityZone` relates to the fabric switch applying that prefix list, navigable from both ends, and deleting a switch never deletes a zone.

**Independent test**: both populated zones resolve to `leaf-nfd41-pod1-3-1`; the switch answers which zones it advertises toward; deleting it leaves the zones intact.

### Tests for US2

- [X] T011 [P] [US2] Assert in `tests/unit/test_zone_advertisement_contract.py` that `advertising_device` exists on the `SecurityZone` extension, with `cardinality: one` and `optional: true`. **Cardinality is the trap here**: relationships default to `many`, unlike attributes which default to mandatory.
- [X] T012 [P] [US2] Assert in `tests/unit/test_zone_advertisement_contract.py` that its `peer` is **`DcimFabricSwitch`** and explicitly **not** `DcimDevice`. This is FR-061 and the single most valuable test in the cycle: `DcimDevice` is this repository's WAN FRR routers, so that peer would validate, load, and match nothing — silently. `AGENTS.md` states it directly.
- [X] T013 [P] [US2] Assert in `tests/unit/test_zone_advertisement_contract.py` that the relationship declares **no `on_delete`**. Its only value is `cascade`, which deletes the *peer* — deleting a switch would delete a security zone — and `infrahubctl schema check` accepts the line without complaint.
- [X] T014 [P] [US2] Assert in `tests/unit/test_zone_advertisement_contract.py` that the `SecurityZone` side and the `DcimFabricSwitch` side share the identifier `security_zone__advertising_device`. Mismatched identifiers produce two independent relationships that each look correct and never connect.
- [X] T015 [P] [US2] Assert in `tests/unit/test_zone_advertisement_contract.py` that the same two zones — and only those two — name `leaf-nfd41-pod1-3-1` as their advertising device.

### Implementation for US2

- [X] T016 [US2] Add the `advertising_device` relationship to the `SecurityZone` extension in `schemas/security_extensions.yml` per [contracts/schema-fields.md](./contracts/schema-fields.md): `peer: DcimFabricSwitch`, `kind: Attribute`, `cardinality: one`, `optional: true`, `identifier: security_zone__advertising_device`, `order_weight: 940`, no `on_delete`. Place it after `vrf` (930).
- [X] T017 [US2] Add the inverse `advertised_zones` relationship to a `DcimFabricSwitch` entry in the same `extensions.nodes` block, `cardinality: many`, `optional: true`, with the **same** identifier, so "what does this leaf advertise, and to whom" is answerable from the switch. Depends on T016.
- [X] T018 [US2] Set `advertising_device: leaf-nfd41-pod1-3-1` on the `branch` and `wan` zone rows in `objects/32_nfd41_security.yml`. The value is the bare device name because `DcimFabricSwitch` has `human_friendly_id: [name__value]`. That device is the lab's `border-leaf1`, matched by `mgmt_ip` `172.20.41.25` — **not** by role, because no device in this fabric carries `border_leaf` (research R4).
- [X] T019 [US2] Re-run schema check, schema load, object load and protocol regeneration as in T009 and T010. Depends on T016–T018.
- [~] T020 [US2] **Substituted, with evidence.** The delete is refused by an unrelated mandatory relationship (`RoutingVrfBgpPeer.devices`), so this switch cannot be deleted in this fabric at all and the route is inconclusive. Verified instead from the **loaded** schema on the server, which is stronger than reading the YAML: `on_delete` resolves to `no-action`. Original task: verify on the branch that deleting `leaf-nfd41-pod1-3-1` leaves the `branch` zone readable with an empty `advertising_device`, then discard the branch state rather than keeping a fabric with a missing leaf. This is the only behaviour a wrong `on_delete` silently changes, and T013 cannot catch it from the YAML alone. Depends on T019.

**Checkpoint**: US1 and US2 both work. Run quickstart steps 5 and 6.

---

## Phase 5: User Story 3 — A policy that does not exist is detectable (P3)

**Goal**: both values come back in one request, so a later check can compare them against a device's merged AVD inputs without a second traversal.

**This phase adds no schema.** It proves the model is usable by the thing that comes next.

- [X] T021 [US3] Verify against the branch that a single GraphQL query returns every zone with `dc_advertised_prefix_list` and `advertising_device { node { name } }`, as written in [quickstart.md](./quickstart.md) step 6. If this needs a second query or a JSON parse of `avd_custom_hostvars`, FR-030 is not met and the generator cycle inherits the problem. Depends on T019.
- [X] T022 [US3] Assert in `tests/unit/test_zone_advertisement_contract.py` that every zone naming a prefix list also names an advertising device, and vice versa. G3 in [data-model.md](./data-model.md) says the schema permits a half-modelled zone; this test says the *lab* has none, which is the difference between a tolerated state and an accidental one.

**Checkpoint**: the next cycle has what it needs.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T023 [P] Document the two fields in `docs/docs/developer-guide/schemas.md`, including why the prefix list is a name rather than a relationship and what that does not guarantee. Use relative Markdown links only — the aggregation site mounts this content under `/arista-avd` and root-absolute links fail its build.
- [X] T024 [P] Add the zone advertisement fields to the `security_extensions.yml` row in `schemas/MARKETPLACE.md`, which already lists `trust_level`, `vrf` and `managed_by_service` as local additions to adopted kinds.
- [X] T025 Run `uv run invoke lint` and `uv run pytest tests/unit`. Both must pass, including `tests/unit/test_junos_config.py` — this cycle renders nothing new, so any movement there means something unintended changed. Note that `invoke lint`'s yamllint step currently fails on the untracked `.emdash/` worktree; check tracked files with `uv run yamllint $(git ls-files '*.yml' '*.yaml')`.
- [ ] T026 **Not run.** Merge the branch, then run `scripts/verify_bootstrap.sh` — a full teardown and rebuild asserting sixteen things. A schema change that loads on a branch and breaks a cold build is a real failure mode, because the branch already had the old schema converged.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Foundational)**: depends on Phase 1; blocks both stories
- **Phase 3 (US1)**: depends on Phase 2
- **Phase 4 (US2)**: depends on US1 — same two files, and T019 supersedes T009/T010
- **Phase 5 (US3)**: depends on US2 for a device to query
- **Phase 6 (Polish)**: depends on all stories

### Story dependencies — read before parallelising

**Sequential.** Both stories edit `schemas/security_extensions.yml` and `objects/32_nfd41_security.yml`. Independent *testability* holds; independent *implementation* does not.

### Within each story

- Tests before implementation. Every test in this cycle can be written first, because they assert against YAML files whose target shape the contracts already fix.
- Schema before objects before protocol regeneration.

---

## Parallel Opportunities

```bash
# Phase 3 — four tests, same new file, different functions:
T004 T005 T006

# Phase 4 — same:
T011 T012 T013 T014 T015

# Phase 6 — different files:
T023 docs/docs/developer-guide/schemas.md
T024 schemas/MARKETPLACE.md
```

**Never parallel**: T007 and T016 and T017 (all edit `schemas/security_extensions.yml`); T008 and T018 (both edit `objects/32_nfd41_security.yml`).

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Phase 1 (T001–T002) — baseline
2. Phase 2 (T003) — test module
3. Phase 3 (T004–T010) — the prefix-list name

At that point a generator can find the list. It would still have to hardcode the border leaf, which is why US2 follows immediately rather than optionally.

### Incremental

1. MVP → the name is modelled
2. US2 → the device is modelled, and the `peer:` trap is closed by a test
3. US3 → both are queryable together, which is all the next cycle needs
4. Polish → docs, lint, cold rebuild

### Do not skip T012

It is one assertion. Without it, `peer: DcimDevice` passes schema check, loads cleanly, renders no error, and resolves to nothing — and the failure surfaces two cycles later as "the generator never finds a device".

---

## Notes

- `[P]` means different files, or different functions in a file nobody else is editing
- Commit after each task or logical group
- **No new node or generic** (FR-003). Needing one means the design drifted toward migrating the fabric's BGP policy rather than referencing it — stop and re-scope
- Nothing here reads, writes or triggers from `DeploymentState` or `DeploymentDiffFile`
- `src/solution_arista_avd/protocols.py` is generated. Regenerate it; never hand-edit it

---

## Phase 7: Findings during implementation

- [X] T027 **`infrahubctl protocols` does not apply the `extensions:` block.** `src/solution_arista_avd/protocols.py` renders `SecurityZone` with `name` and `interfaces` only — no `trust_level`, no `vrf`, and now no `dc_advertised_prefix_list` either. Those first two are long-standing local extensions, so this is pre-existing behaviour, not a regression. Consequence: FR-052 is satisfied trivially (regenerated, empty diff) rather than meaningfully, and **no code can get typed access to any extension-added field through the generated protocols**. Worth knowing before the generator cycle reaches for one.
- [X] T028 **`schemas/security_extensions.yml` now extends a non-security kind**, which an existing contract test caught: `test_extensions_touch_only_the_four_intended_kinds` asserted exactly four. Its own docstring says the count is "raised deliberately each time a kind is added -- never loosened", so it was updated to five and renamed, with the rationale recorded there. The precedent for extending a Dcim kind from the file that owns the concept is `schemas/service/service.yml`.
- [X] T029 **A `description` longer than 128 characters is rejected by `schema check`.** The first draft of `dc_advertised_prefix_list` failed on it. The reasoning that would not fit lives in a YAML comment above the field instead.
