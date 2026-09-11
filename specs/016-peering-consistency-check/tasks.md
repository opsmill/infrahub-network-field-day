---

description: "Task list for the peering consistency check"
---

# Tasks: Peering Consistency Check

**Input**: Design documents from `/specs/016-peering-consistency-check/`

**Tests**: **REQUIRED.** Constitution IV; the fixture suite is the primary gate in place of the unavailable integration skill.

## Phase 1: Setup

- [X] T001 Verify preflight: `uv run infrahubctl info` shows Connection Status ✅ with Infrahub 1.10.6
- [X] T002 Create the branch `peer-check` with `--sync-with-git`, then `schema load` and `object load`
- [X] T003 Re-confirm the R1 measurement on this branch: `RoutingBGPNeighbor`, `AvdStructuredConfigFile`, `AvdHostvarFile` and `AvdArtifact` are all zero, and `EvpnSviNode` is not. If any is non-zero the spec's Out of Scope is wrong and the AVD comparison rule should be added

## Phase 2: Foundational

- [X] T004 Write `checks/peering_consistency_check.gql`: every `ServiceFabricPeering` with its cluster, the cluster's sessions with `peer_asn`, `peer_device` and `peer_address`, each peer device's `role`, `asn` and `peering`-role interfaces with their addresses, the cluster's cabled node set, and every `EvpnSviNode` with device, VLAN and address
- [X] T005 Select `id` and `__typename` on every node the check may report on — without them `log_error` cannot carry attribution (G-3), and the generated models need `__typename` at union points
- [X] T006 Regenerate the typed model via `export-schema` from the branch then `generate-return-types --schema`; confirm `uv run invoke lint-mypy` passes

## Phase 3: User Story 1 - A hand-edited session fails the merge (P1) 🎯 MVP

### Tests ⚠️

- [X] T007 [P] [US1] Create `tests/unit/test_peering_consistency_check.py` with a fixture builder shaping a `PeeringConsistencyCheckQuery` response, following `tests/unit/test_generate_fabric_peering.py`
- [X] T008 [P] [US1] Add `test_clean_model_passes` — the single most important test. If the check fails a model the generator produced, it and the generator disagree and neither can be trusted (C-1, C-2, G-1)
- [X] T009 [P] [US1] Add `test_asn_mismatch_is_reported` asserting the message names the session, the recorded value and the device's value (C-1)
- [X] T010 [P] [US1] Add `test_address_mismatch_is_reported` (C-2)
- [X] T011 [P] [US1] Add `test_every_violation_is_reported` with several simultaneous problems, asserting all appear (G-2, SC-007)
- [X] T012 [P] [US1] Add `test_every_error_carries_attribution`, asserting `object_id` and `object_type` on each (G-3)

### Implementation

- [X] T013 [US1] Create `checks/peering_consistency_check.py` with `PeeringConsistencyCheck(InfrahubCheck)`, `query = "peering_consistency_check"`, and `validate(self, data: dict) -> None`
- [X] T014 [US1] Implement C-1 and C-2 as pure functions returning violations, so they are testable without a client and the check body stays a loop over findings
- [X] T015 [US1] Accumulate findings and emit them all; never return early (G-2)
- [X] T016 [US1] Run the unit suite and confirm T008–T012 pass

## Phase 4: User Story 2 - Structural impossibilities (P2)

- [X] T017 [P] [US2] Add tests for C-3 (two services on one cluster), C-4 (uncabled peer device) and C-5 (non-leaf role)
- [X] T018 [US2] Implement C-3, C-4 and C-5
- [X] T019 [US2] Confirm the clean model still passes after adding them — each new rule is a chance to introduce a false positive

## Phase 5: User Story 3 - The SVI duplication (P2)

- [X] T020 [P] [US3] Add a test for C-6 matching on device **and** VLAN, and a test that matching on device alone would produce a false positive (R5)
- [X] T021 [P] [US3] Add a test for C-7 using `log_info` rather than `log_error`, since an `EvpnSviNode` with no matching SVI is not necessarily wrong (R3)
- [X] T022 [US3] Implement C-6 and C-7

## Phase 6: Live verification

- [X] T023 Register the query and the check in `.infrahub.yml` per [contracts/check-contract.md](contracts/check-contract.md) §1 — **no `targets`**, because it is global
- [X] T024 Commit, push the branch, and confirm the repository syncs and the check definition appears
- [X] T025 Run the check against the clean model and confirm zero errors (SC-001)
- [X] T026 Seed a violation — edit a session's `peer_asn` — re-run, and confirm it fails naming both values (SC-002). Revert
- [X] T027 Seed two unrelated violations and confirm both are reported in one run (SC-007). Revert
- [X] T028 Confirm an empty result set passes rather than erroring (SC-008)

## Phase 7: Polish

- [X] T029 [P] Document the check in `docs/docs/developer-guide/checks.md` or the developer guide's check section, including why the AVD comparison is absent
- [X] T030 [P] Update `AGENTS.md`'s check inventory, which currently names only `cv-config-validation`
- [X] T031 Run the full gate: `uv run pytest tests/unit` and `uv run invoke lint`; confirm lint-prose is unchanged
- [X] T032 Write `acceptance-evidence.md` with real output for SC-001 … SC-010
- [X] T033 Delete the throwaway branch
- [ ] T034 Maintainer sign-off on the Principle IV exception

## Dependencies

```text
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6 ──► Phase 7
```

- **T003 gates the whole cycle's scope.** If the AVD collections are non-empty, the most valuable rule is back in scope.
- **T008 is the stop-and-check.** A check that fails a generator-produced model is worse than no check.

## Implementation Strategy

**MVP = Phases 1–3.** C-1 and C-2 are the rules that close the actual gap; C-3 … C-7 harden it.
