---

description: "Task list for deriving the peering address"
---

# Tasks: Derive the Peering Address

**Input**: Design documents from `/specs/015-derive-peer-address/`

**Tests**: **REQUIRED.** Constitution II and IV, and the plan's Complexity Tracking makes the fixture suite the primary gate in place of two unavailable validation skills.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Verify preflight: `uv run infrahubctl info` shows Connection Status ✅ with Infrahub 1.10.6
- [ ] T002 Create the branch: `uv run infrahubctl branch create peer-addr --sync-with-git`, then `schema load` and `object load` against it
- [ ] T003 **Capture the baseline oracle before any change**: render `crossplane_fabric_peering` to a file and record the artifact checksum. SC-002 compares against it
- [ ] T004 Verify the traversal is complete: query every `leaf`-role device's virtual interfaces and confirm exactly two carry an address, each with `role: peering` (research R1)

## Phase 2: Foundational

- [ ] T005 Extend `generators/generate_fabric_peering.gql` to select the peer device's `interfaces`, each interface's `role`, and its `ip_addresses`, per [contracts/generator-contract.md](./contracts/generator-contract.md) §2
- [ ] T006 Select `__typename` at every new union point. Cycle 012 found that the generated models are discriminated unions and the server returns `__typename` only when asked; omitting it fails at run time with `union_tag_not_found`
- [ ] T007 Regenerate the typed model with `export-schema` from the branch followed by `generate-return-types --schema`, then confirm `uv run invoke lint-mypy` passes

## Phase 3: User Story 1 - The address follows the fabric (P1) 🎯 MVP

### Tests ⚠️

- [ ] T008 [P] [US1] Extend the fixture builder in `tests/unit/test_generate_fabric_peering.py` so a peer device can carry virtual interfaces with roles and addresses
- [ ] T009 [P] [US1] Add `test_peer_address_comes_from_the_peering_svi`, asserting the address is read from the interface whose role is `peering` (D-9, D-10)
- [ ] T010 [P] [US1] Add `test_loopback_is_never_selected`, asserting an interface with a non-`peering` role is ignored even when it carries an address. This is the positional-selection failure research R1 rejected
- [ ] T011 [P] [US1] Add `test_adopt_payload_now_carries_the_address`, asserting the adopt payload contains `peer_asn` and `peer_address` and still omits `name` and `enabled` (D-3, revised G-4)

### Implementation

- [ ] T012 [US1] Add SVI selection to `generators/generate_fabric_peering.py`: a pure function returning the peering address for a derived peer, selecting by interface role
- [ ] T013 [US1] Carry the derived address on `DerivedPeer`, and add it to the adopt payload
- [ ] T014 [US1] Set `peer_address` alongside `peer_asn` when adopting, using the same fetch-and-modify mechanism — an upsert would demand every mandatory field
- [ ] T015 [US1] Run `uv run pytest tests/unit/test_generate_fabric_peering.py` and confirm T008–T011 pass

## Phase 4: User Story 2 - A new leaf provisions itself (P1) 🎯 MVP

### Tests ⚠️

- [ ] T016 [P] [US2] Add `test_create_payload_is_reachable_again`, asserting a cabled peer with no session yields a create payload carrying all six fields. Cycle 012's `test_there_is_no_create_shape_at_all` asserted the opposite and **must be replaced**, not left to contradict this
- [ ] T017 [P] [US2] Add `test_peer_without_a_peering_svi_raises_naming_the_device` (V-6′)
- [ ] T018 [P] [US2] Add `test_multiple_peering_svis_raises` and `test_svi_with_multiple_addresses_raises` (V-8, V-9)

### Implementation

- [ ] T019 [US2] Restore the create payload removed by cycle 012, carrying `cluster`, `peer_device`, `peer_asn`, `peer_address`, `name` and `enabled`; `name` takes the peer device's name
- [ ] T020 [US2] Replace validation rule V-6 with V-6′ and add V-8 and V-9, all raising before any write
- [ ] T021 [US2] Update the module docstring: the claim that there is deliberately no create shape is now false and must not be left standing
- [ ] T022 [US2] Run the unit suite and confirm every cycle-012 behaviour still passes alongside the new ones

## Phase 5: User Story 3 - The manifest does not change (P1) 🎯 MVP

- [ ] T023 [US3] Add drift reporting: when a recorded address differs from the derived one, log the session, the old value and the new before correcting (R4, G-10)
- [ ] T024 [US3] Commit and push the branch so the repository sync picks it up; confirm `in-sync` at the new commit
- [ ] T025 [US3] Run the generator and confirm both sessions carry `10.110.0.2/24` and `10.110.0.3/24` derived from the SVIs (SC-001)
- [ ] T026 [US3] **The oracle**: re-render and diff against the T003 baseline. It MUST be byte-identical (SC-002)
- [ ] T027 [US3] Run the generator a second time and confirm nothing changes (SC-007)

## Phase 6: The create path, proven

- [ ] T028 Delete both `ClusterFabricPeering` objects, re-run the generator, and confirm both are recreated complete with derived addresses (SC-004). **This was impossible before this cycle** and is the clearest single proof it works
- [ ] T029 Re-render and confirm the artifact is byte-identical to the baseline after recreation
- [ ] T030 Change an SVI's address, re-run, and confirm the session and the artifact both move (SC-003). Revert afterwards

## Phase 7: Polish

- [ ] T031 Remove `peer_address` and `peer_asn` from `objects/34_nfd41_cluster.yml` and rewrite the split-ownership annotation: `name` is now the only field the file owns (FR-010, SC-008)
- [ ] T032 Re-run `object load` twice and confirm idempotence with the fields gone
- [ ] T033 [P] Update the `FabricPeeringGenerator` entry in `docs/docs/developer-guide/generators.md`: the address is derived, the create path exists, and the "what it does not do" paragraph is now wrong
- [ ] T034 [P] Update `schemas/MARKETPLACE.md` or the cycle-012 evidence if either still claims the address cannot be derived
- [ ] T035 Run the full gate: `uv run pytest tests/unit` and `uv run invoke lint`; confirm lint-prose is unchanged at 7 errors / 4 warnings
- [ ] T036 Write `specs/015-derive-peer-address/acceptance-evidence.md` with real output for SC-001 … SC-009
- [ ] T037 Delete the throwaway branch
- [ ] T038 Maintainer sign-off on the Principle II and IV exceptions

## Dependencies

```text
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6 ──► Phase 7
```

- **T003 blocks T026, T029 and T030.**
- **T016 must replace cycle 012's `test_there_is_no_create_shape_at_all`**, or the suite asserts both that a create path exists and that it cannot.
- **T031 depends on Phase 6** — removing the file's addresses before the create path is proven would leave nothing to recreate them from.

## Implementation Strategy

**MVP = Phases 1–5.** Phase 6 proves the limitation is gone; Phase 7 removes the last
hand-maintained copy, which is the point of the cycle.

**Stop-and-check**: T026. If the artifact moved, the derived address disagrees with the live
one — read the drift log before assuming a bug.
