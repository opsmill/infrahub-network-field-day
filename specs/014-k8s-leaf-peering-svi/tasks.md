# Tasks: k8s Leaf Peering SVIs

**Feature**: `specs/014-k8s-leaf-peering-svi` | **Branch**: `014-k8s-leaf-peering-svi`
**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/object-contract.md](./contracts/object-contract.md),
[quickstart.md](./quickstart.md)

**Tests**: Requested. The spec's SC-009 requires the unit suite to pass at or above its current
count, and the contract in `contracts/object-contract.md` states clauses that only a test can
hold in place once this cycle's author is gone.

**Infrahub branch**: `svi-model` (created with `--sync-with-git`; without that flag the
repository never reads `.infrahub.yml` for the branch and transforms cannot render).

**Environment for every live command**:

```bash
export INFRAHUB_API_TOKEN=<token> INFRAHUB_ADDRESS=http://localhost:8000
```

---

## Phase 1: Setup

**Purpose**: Establish the working branch and, critically, the regression oracle — *before* any
data changes, because an oracle captured after the change proves nothing.

- [X] T001 Create the Infrahub branch: `uv run infrahubctl branch create svi-model --sync-with-git`
- [X] T002 Load the current schema onto the branch: `uv run infrahubctl schema load schemas --branch svi-model --wait 120`
- [X] T003 Load the current, unmodified seed objects: `uv run infrahubctl object load objects/ --branch svi-model`
- [X] T004 Capture the baseline render to `/tmp/svi-baseline.yaml`: `uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering --branch svi-model`
- [X] T005 Reconcile the baseline against the recorded oracle: normalise to a single trailing newline and confirm the md5 is `0d800c9d5005b5fdb6b371bb5627d143`. **If it does not match, stop** — either the oracle or the environment is wrong, and every later comparison is meaningless. Record the reconciliation (the CLI prints one extra trailing newline versus the stored artifact bytes).
- [X] T006 Capture a second, wider baseline beyond the declared oracle: render `avd_eos_config` for `leaf-nfd41-pod1-1-1` to `/tmp/svi-baseline-avd.txt`. Research R5 argues the new interfaces are inert to AVD; this is what turns that argument into a measurement.

**Checkpoint**: Two baselines captured, the primary one proven equal to the cycle 011/012 digest.

---

## Phase 2: Foundational

**Purpose**: Confirm the premises the whole cycle rests on. Every one of these is a claim that,
if false, invalidates the design rather than merely complicating it.

- [X] T007 Confirm the defect is real: query `IpamIPAddress` for `10.110.0.2/24` and `10.110.0.3/24` on branch `svi-model` and record that `interface` is `null` for both. This is the condition the cycle removes.
- [X] T008 Confirm no schema change is needed: verify `InterfaceVirtual` exists as a concrete node and `IpamIPAddress.interface` exists, both on the live branch schema. **If either is absent, stop and report** rather than adding a schema change to an object-data cycle.
- [X] T009 Confirm the relationship choice from research R2: dump every relationship on `IpamIPAddress` and confirm exactly one is interface-facing (`interface`, identifier `interfacelayer3__ipamipaddress`), and that `InterfaceVirtual.ip_address` (identifier `interface__ip_address`) has no reverse side. This is what forces the use of `ip_addresses`.
- [X] T010 Confirm the device names: verify both `ClusterFabricPeering` rows point at `leaf-nfd41-pod1-1-1` / `leaf-nfd41-pod1-1-2`, and that the `k8s-leaf1` / `k8s-leaf2` duplicates exist separately and are not the peer targets.
- [X] T011 Confirm no name collision: verify each target leaf currently carries exactly one `InterfaceVirtual` (`Loopback0`), so `Vlan110` is free.

**Checkpoint**: Every premise verified against the live instance. Design is safe to implement.

---

## Phase 3: User Story 1 — The peering address belongs to a device (P1)

**Goal**: `IpamIPAddress -> interface -> device` becomes a complete traversal for both peering
addresses.

**Independent test**: Query either address and follow `interface -> device`; it lands on the
matching leaf instead of dead-ending at null.

- [X] T012 [US1] Create `objects/36_nfd41_peering_svis.yml` with two `InterfaceVirtual` objects per [data-model.md](./data-model.md): `name: Vlan110`, `device` referencing the `leaf-nfd41-pod1-1-*` names as scalars, `role: peering`, `status: active`, `dot1q_id: 110`, a description naming the session, and `ip_addresses` as a list-of-lists (`[["10.110.0.2/24", "default"]]`). Include a header comment explaining why the file sorts at `36` and why `ip_addresses` rather than `ip_address` is used.
- [X] T013 [US1] Load the new objects: `uv run infrahubctl object load objects/ --branch svi-model`
- [X] T014 [US1] Verify the forward edge: each `Vlan110` carries exactly one address, and it is that leaf's own.
- [X] T015 [US1] Verify the **reverse** edge, which is the one that matters: `IpamIPAddress.interface` is now non-null for both addresses and resolves through to the correct device. A pass on T014 with a failure here means the wrong relationship was written (research R2).
- [X] T016 [US1] Verify the computed `index` attribute rendered without error on the new interfaces (expected `110`), per research R4.

**Checkpoint**: US1 delivered — the traversal exists.

---

## Phase 4: User Story 2 — The shared gateway is never mistaken for a peer (P1)

**Goal**: The derivation cannot select the MLAG pair's shared VARP gateway `10.110.0.1`.

**Independent test**: Enumerate every address reachable from either leaf's SVI; `10.110.0.1` is
not among them.

- [X] T017 [US2] Verify `10.110.0.1` is attached to no interface on either leaf (it lives on `EvpnSvi.ip_virtual_router_addresses` as intent, not as an attached address object)
- [X] T018 [US2] Verify the derivation is unambiguous per contract C2: for each peer device, exactly **one** address on its interfaces falls inside `10.110.0.0/24`
- [X] T019 [US2] Verify the two leaves' peering addresses are distinct

**Checkpoint**: US2 delivered — the derivation is single-valued.

---

## Phase 5: User Story 3 — Nothing that reaches the cluster moves (P1)

**Goal**: Prove the cycle changed nothing that is applied to the live Kubernetes cluster.

**Independent test**: Re-render and diff against the Phase 1 baseline.

- [X] T020 [US3] Re-render `crossplane_fabric_peering` on `svi-model` to `/tmp/svi-after.yaml`
- [X] T021 [US3] `diff /tmp/svi-baseline.yaml /tmp/svi-after.yaml` — **MUST be byte-identical**. If it is not, stop and report; the cycle has altered what a controller applies.
- [X] T022 [US3] Confirm the normalised digest of the post-change render still equals `0d800c9d5005b5fdb6b371bb5627d143`
- [X] T023 [US3] Close the residual risk research R5 flagged. **Executed differently from the plan, deliberately**: the `avd_eos_config` render is vacuous on this branch (the AVD generator chain has not run there, so it returns a 57-byte "No structured config available" stub, identical before and after regardless of the change). Substituted a real measurement — run `generators/avd_device_hostvar.gql`, the generator's own query, against the branch before and after for `leaf-nfd41-pod1-1-1` and characterise the diff. Result: the input gains exactly two field-less `{__typename, id}` stubs and is otherwise identical, and the generator discards non-`InterfacePhysical` entries. Both the vacuous check and the substitute are recorded in `acceptance-evidence.md`.
- [X] T024 [US3] Confirm the scope boundary held: `git diff --name-only` shows no file under `schemas/`, `generators/` or `transforms/` (SC-008, FR-019, FR-020)

**Checkpoint**: US3 delivered — the regression oracle holds.

---

## Phase 6: User Story 4 — The seed data can be loaded twice (P2)

**Goal**: The new object data is idempotent.

- [X] T025 [US4] Run `uv run infrahubctl object load objects/ --branch svi-model` a second time and confirm it succeeds
- [X] T026 [US4] Confirm the `InterfaceVirtual` count is unchanged (16 total: 14 pre-existing `Loopback0` plus the 2 new `Vlan110`) and each `Vlan110` still carries exactly one address
- [X] T027 [US4] Re-render the Crossplane transform after the repeated load and confirm it is still byte-identical to the baseline

**Checkpoint**: US4 delivered — repeated loads are safe.

---

## Phase 7: Tests

**Purpose**: Hold the contract in place after this cycle. These are seed-data contract tests in
the existing `tests/unit/test_nfd41_seed_data.py` style — they parse the YAML, so they run
without an Infrahub instance and catch a bad edit at review time rather than at load time.

- [X] T028 [P] Create `tests/unit/test_peering_svi_seed_data.py` with a `_load_objects(kind)` helper matching the pattern in `tests/unit/test_nfd41_seed_data.py`
- [X] T029 [P] Test: exactly two peering SVIs exist, one on each of `leaf-nfd41-pod1-1-1` and `leaf-nfd41-pod1-1-2` (FR-016)
- [X] T030 [P] Test: each peering SVI carries exactly one address, and the two are distinct (FR-013, FR-014)
- [X] T031 [P] Test: each SVI's address equals the `peer_address` of the `ClusterFabricPeering` row whose `peer_device` is that SVI's device — the cross-file check that makes the follow-up a no-op refactor (FR-017, contract C3)
- [X] T032 [P] Test: no peering SVI carries the VARP gateway `10.110.0.1`, and the address does not appear as an `IpamIPAddress` seed object at all (FR-013, contract C2)
- [X] T033 [P] Test: every peering SVI uses `ip_addresses` and none sets `ip_address` — guards research R2's finding against a well-meaning future edit that would silently break the traversal
- [X] T034 [P] Test: the SVI file sorts after the file declaring the peering addresses (FR-009), asserted from the filenames so a renumbering that breaks load order fails here
- [X] T035 [P] Test: every SVI's `device` is a name used by a `ClusterFabricPeering.peer_device`, never a `k8s-leaf*` duplicate (FR-006, contract C4)

---

## Phase 8: Polish & Cross-Cutting

- [X] T036 Update the annotation in `objects/34_nfd41_cluster.yml`: its comment says removal of the hand-declared rows "becomes possible once the leaves' peering SVIs are modelled". State that this is now done, point at `36_nfd41_peering_svis.yml`, and name what the follow-up must change. **Change comments only — no values** (FR-021, and it is what keeps the artifact byte-identical).
- [X] T037 Run `uv run pytest tests/unit` — must be >= the pre-change count (832) with none failing
- [X] T038 [P] Run `uv run invoke lint-ruff`
- [X] T039 [P] Run `uv run invoke lint-yaml`
- [X] T040 [P] Run `uv run invoke lint-mypy`
- [X] T041 [P] Run `uv run invoke lint-markdown`
- [X] T042 Run `uv run invoke lint-prose` and confirm the count is unchanged from the known baseline of 7 errors / 4 warnings. If a new word is flagged, add it to `.vale/config/vocabularies/OpsMill/accept.txt` as the repo already does for similar terms.
- [X] T043 Write `specs/014-k8s-leaf-peering-svi/acceptance-evidence.md` recording every success criterion with real command output, following the format of `specs/011-crossplane-manifest-transform/acceptance-evidence.md`. Record gaps as gaps.
- [ ] T044 Commit on `014-k8s-leaf-peering-svi` with the required trailer lines
- [ ] T045 Delete the `svi-model` Infrahub branch, or state why it was kept for inspection

---

## Dependencies

```text
Phase 1 (Setup, baselines)   -- MUST be first; an oracle captured later is worthless
   |
Phase 2 (Foundational)       -- premises; a failure here stops the cycle
   |
Phase 3 (US1)                -- the data change itself
   |
   +-- Phase 4 (US2)         -- both read the data US1 created
   +-- Phase 5 (US3)         -- needs the Phase 1 baseline AND the US1 change
   +-- Phase 6 (US4)         -- needs US1 loaded once already
   |
Phase 7 (Tests)              -- independent of the live instance; could run any time after T012
   |
Phase 8 (Polish)             -- T036 must come after T021, so the byte-identical
                                proof is against the data change alone
```

**Critical ordering constraints**:

- T004/T005/T006 **before** T012. A baseline taken after the change cannot detect the change.
- T021 **before** T036. Annotating first would mix a comment edit into the diff being proved
  inert.
- T015 is the load-bearing verification. T014 can pass while T015 fails; that combination means
  the wrong relationship was used and the cycle has achieved nothing.

## Parallel opportunities

- **Phase 7 (T028–T035)**: all in one new file but logically independent; write together, and
  they are independent of every live command, so this phase can run while an Infrahub load is in
  flight.
- **Phase 8 linters (T038–T041)**: mutually independent.
- Phases 4, 5 and 6 are independent of each other once Phase 3 completes.

## Implementation strategy

**MVP** is Phase 3 (US1) — the traversal existing is the entire feature. But US3 (Phase 5) is
non-negotiable before the cycle can be called done: a traversal that also moved the Crossplane
artifact would be a net loss, since that manifest is applied to a live cluster without further
review.

**Stop conditions** — report rather than proceed if:

- T005 cannot reconcile the baseline to the recorded digest
- T008 finds a schema change is required
- T021 shows any diff
- T023 shows the AVD config moved

## Task summary

| Phase | Tasks | Story |
| --- | --- | --- |
| 1 Setup | T001–T006 | — |
| 2 Foundational | T007–T011 | — |
| 3 | T012–T016 | US1 (P1) |
| 4 | T017–T019 | US2 (P1) |
| 5 | T020–T024 | US3 (P1) |
| 6 | T025–T027 | US4 (P2) |
| 7 Tests | T028–T035 | — |
| 8 Polish | T036–T045 | — |

**Total: 45 tasks.**
