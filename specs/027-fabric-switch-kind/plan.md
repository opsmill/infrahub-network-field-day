# Implementation Plan: A Device Kind for Fabric Switches

**Branch**: `027-fabric-switch-kind` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-fabric-switch-kind/spec.md`

## Summary

Add `DcimFabricSwitch` beside `DcimDevice`, move twelve fabric-only fields onto it, split the role
dropdown, retarget the AVD path, and prove that **nothing a device would see changes**: the seven
EOS configs, six FRR configs and the Junos config all render identically.

The data story is a destroy and rebuild, on the requester's decision. That is what makes the cycle
tractable — the seven switches are seeded, so changing `spec.kind` is the whole of it.

## What the two design phases changed

Phase 0 made the cycle **smaller** than the spec assumed. Phase 1 made one part of it
**substantially larger**, and that part was invisible from the spec's own requirement list.

### Phase 0: two earlier cycles had already done a third of the work

The riskiest question — does a sibling kind work, and what stops seeing it — was settled by
building one on a live branch and counting, not by reasoning:

```text
DcimDevice count        : 14    <- the new instance is NOT here
DcimFabricSwitch count  : 1
DcimGenericDevice count : 23    {DcimDevice: 14, ComputePhysicalServer: 7,
                                 SecurityFirewall: 1, DcimFabricSwitch: 1}
```

Both halves of the premise, measured. And two prior fixes turned out to be load-bearing here:
cycle 024 widened `RoutingStaticRoute.device` to the generic, so static routes need **no change
at all**; cycle 026 moved `name` onto the generic in the cabling plan, so a cable to a switch
still resolves and the row still renders — the worst case there dropped from *silent total data
loss* to *one blank column*.

Neither was planned for this cycle. Both happened because a bug was fixed properly rather than
patched.

### Phase 1: the reverse sides outnumber the moved fields

FR-005 lists twelve fields to move. Working from that list alone would miss most of the
relationship work, because **thirteen** `peer: DcimDevice` sites exist across `schemas/` and
**four of the seven that must change have no forward side on `DcimDevice` at all** — the device
end is declared only on the related node.

Every site's disposition came from counting the objects attached to it:

| Disposition | Count | Sites |
| --- | --- | --- |
| → `DcimFabricSwitch` | 7 | `NetworkPod.devices`, `AvdArtifact.device`, `MlagDomain.peers`, `EvpnSviNode.device`†, `RoutingVrfBgpPeer.devices`†, `RoutingVrfL3Interface.device`†, `EvpnGatewayGroup.members` |
| → `DcimGenericDevice` | **2** | `RoutingAsn.devices`, `RoutingVrfStaticRoute.devices` |
| stay `DcimDevice` | 4 | `RoutingBGPNeighbor.device`, `RoutingBGPPeerGroup.device`, `RoutingPrefixList.device`, `RoutingRouteMap.device` |
| already generic | 1 | `LocationRack.devices` peers `DcimPhysicalDevice` |

† no forward side on `DcimDevice`.

**The two widenings are the finding.** `RoutingAsn.devices` had to widen because `asn` is on both
kinds (FR-007) and a reverse side cannot name two concrete kinds. `RoutingVrfStaticRoute.devices`
had to widen because its ten objects are shared between **`isp-pe1` and `leaf-nfd41-pod1-3-1`** —
the two ends of one tenant handoff, genuinely spanning the split. Nothing in either field's name
says so. Only the count did.

This is the same shape as cycle 024's widening for the firewall, and `routing.yml:403` already
carries the comment explaining why a concrete peer there is wrong.

### The correction task generation forced

The enumeration in Phase 0 covered `transforms/` and part of `generators/`. Generating tasks
required naming every file, so the grep finally covered **`checks/`, `src/` and Python string
literals** — and the surface roughly quadrupled:

| Surface | Phase 0 said | Actually |
| --- | --- | --- |
| GraphQL query roots | 3 | **8** — 6 retarget, 2 in `frr_config` untouched |
| `... on DcimDevice` fragments | 6 | **20**, across 10 files |
| Python places | 5 | **12** call sites + 7 string checks + 3 mutation strings |

**The three that no fragment grep could ever have found** are Python comparing a kind as a string.
The sharpest is `transforms/containerlab_topology.py:202`:

```python
if node.typename != "DcimDevice" or node.name is None or not node.name.value:
    continue
```

After the split that `continue` skips every fabric switch and the transform emits a topology with
seven servers, no switches, **no error and valid YAML**. The other two are
`generate_avd_device_hostvar.py:2786` and `cv_config_check.py:57`, both `.get("DcimDevice", {})`
on a response whose key moves with the query root.

This is the recurring failure of this whole sequence — *a count established from a narrow search,
carried forward without being re-derived* — and it was mine. Caught at task time, which is the
cheapest place left. `research.md` R8 records it rather than quietly restating the numbers.

### The failure mode both phases keep pointing at

A one-way relationship — forward side moved, reverse side left behind — produces **no error**. It
loads, it validates, and the field is silently always empty. So does a `... on DcimDevice`
fragment that meets a switch. These are the same failure that hid the cabling plan's missing
cables for months, and C6e and C11 exist to make each one a test rather than a review comment.

## Technical Context

**Language/Version**: Python >=3.11,<3.14. YAML schema and object data; GraphQL queries.

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]` 1.22.0, PyAVD >=6.4.0,<6.5.0. No
version changes.

**Storage**: the graph. This cycle changes its shape, then rebuilds it from seed.

**Testing**: `pytest`. One new module (`test_dcim_schema_contract.py`), three extended. The schema
clauses parse YAML and need no server; the render comparisons use captured fixtures.

**Target Platform**: local Infrahub stack via Docker Compose.

**Project Type**: Infrahub repository — schemas, generators, transforms, checks, object data.

**Performance Goals**: N/A.

**Constraints**: every rendered artifact byte-identical or line-identical to its pre-cycle output;
no `... on DcimDevice` site left able to return nothing silently; both ends of every identifier
naming the same peer.

**Scale/Scope** *(corrected at task time — see research R8)*: 1 new node, 12 fields moved, 2 role
dropdowns, **13 peer lines across 7 schema files**, **6 GraphQL query roots**, **20 fragment sites
across 10 files**, **12 typed Python call sites**, **7 kind-name string comparisons**, **3 raw
mutation strings**, 2 object files, 1 new test module and 3 extended, plus a full
destroy/rebuild.

**Dependencies**: cycles 023–026 merged and pushed. The baseline is today's live state: 33
artifacts, 1043 unit tests, seven EOS configs matching the lab exactly. All three re-derived
today rather than carried from an earlier spec.

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1. Result recorded below.*

| Principle | Assessment |
| --- | --- |
| **I. Schema-Driven Architecture** | ✅ The cycle *is* a schema change, and it lands before the queries and code that read it. The new node goes in `schemas/base/dcim.yml` beside `DcimDevice`; its fields go in `schemas/dcim_extensions.yml`, matching where `DcimDevice`'s live. `protocols.py` is regenerated, never hand-edited (C14). None of the seven files touched is marketplace-adopted. |
| **II. Idempotent Operations** | ✅ No generator logic changes — only the kind four generators create and filter. `invoke load` upserts on HFID; a switch seeded as `DcimFabricSwitch` upserts to itself. **One caveat, carried from cycle 026 and stated in quickstart step 7**: `generate-pod` is destructive on re-run, which is why the topology generators sit behind `--topology`. That is pre-existing, not introduced here. |
| **III. Type Safety** | ✅ Three `.gql` files change, and each regenerates its `*_query.py`. `protocols.py` gains a `DcimFabricSwitch` protocol by regeneration. mypy must pass on the retargeted call sites — where a protocol type changes, the annotation changes with it. |
| **IV. Test-Required Quality** | ✅ **Strengthened, in the place that needed it.** C6e asserts every identifier's two ends agree, by parsing all of `schemas/` rather than the lines this cycle touched — the gap cycle 024 found when a careless `sed` flipped five relationships and *nothing* would have caught it. C11 gives every fragment site a named disposition, because SC-008 says counting them is not enough. The integration suite is the same documented exception as cycles 020–026. |
| **V. Convention-Based Structure** | ✅ The new node uses namespace `Dcim`, an approved one, and copies `DcimDevice`'s `human_friendly_id`, `display_label` and `order_by` (C7). No file is added outside an existing tree; object files keep their numbering. |

### One artifact type, for once

Cycle 026 covered three artifact types and recorded the deviation. This cycle is **Schema**, with
the query and code retargeting that a schema change necessarily drags behind it. The extension's
routing loaded `infrahub-managing-schemas`, which is the right one.

The object-file change is two `spec.kind` lines and does not make this an Objects cycle.

### Integration testing

`$infrahub-run-integration-tests` is not installed, as in cycles 020–026. The escape clause
applies and **the pull request must say so explicitly**.

The non-live alternative is unusually strong here: [quickstart.md](./quickstart.md) steps 6 to 12
are a full destroy → build → load → generate → compare against a baseline captured beforehand.
That exercises the generator chain, the schema load and repository-load behaviour end to end — more
than any cycle in this sequence has run.

**No unjustified violations. Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/027-fabric-switch-kind/
├── plan.md              # This file
├── spec.md              # 19 FR, 9 SC, 3 user stories
├── research.md          # Phase 0 — seven findings, one live probe
├── data-model.md        # Phase 1 — the node, the twelve fields, the two dropdowns
├── quickstart.md        # Phase 1 — thirteen steps, baseline capture first
├── contracts/
│   └── schema-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks
```

### Source code (repository root)

```text
schemas/base/dcim.yml                    # EDIT — the new node beside DcimDevice
schemas/dcim_extensions.yml              # EDIT — twelve fields move; two role dropdowns
schemas/logical_design.yml               # EDIT — NetworkPod.devices
schemas/objects/objects.yml              # EDIT — AvdArtifact.device
schemas/mlag/mlag.yml                    # EDIT — MlagDomain.peers
schemas/evpn/evpn_services.yml           # EDIT — EvpnSviNode.device
schemas/evpn/evpn_gateway.yml            # EDIT — EvpnGatewayGroup.members
schemas/routing/vrf_services.yml         # EDIT — 2 to the new kind, 1 WIDENED to the generic
schemas/routing/routing.yml              # EDIT — RoutingAsn.devices WIDENED to the generic

generators/avd_device_hostvar.gql        # EDIT — root + 5 fragments
transforms/avd_device_config.gql         # EDIT — root
transforms/avd_anta_catalog.gql          # EDIT — TWO roots (:2 and :31)
transforms/avd_fabric_devices.gql        # EDIT — root
checks/cv_config_check.gql               # EDIT — root
transforms/frr_config.gql                # MUST NOT CHANGE — asserted by C10
transforms/containerlab_topology.gql     # EDIT — 2 fragments, read `name` from the generic
transforms/cabling_plan.gql              # EDIT — DcimFabricSwitch fragment for `rack`
transforms/cabling_plan.py               # EDIT — 2 fragments
generators/generate_avd.gql              # EDIT — 1 fragment
generators/backfill_structured_config.gql # EDIT — 1 fragment
generators/generate_fabric_peering.gql   # EDIT — 1 fragment
checks/fabric_pool_check.gql             # EDIT — 1 fragment
checks/peering_consistency_check.gql     # EDIT — 1 fragment
*_query.py next to each changed .gql     # REGENERATE

generators/generate_pod.py               # EDIT — kind filter :244
generators/generate_rack.py              # EDIT — kind filter :179
generators/generate_server_cabling.py    # EDIT — kind filter :56
generators/asn.py                        # EDIT — get :46 AND the DcimDeviceUpsert string :21
src/solution_arista_avd/generator.py     # EDIT — 7 call sites + 2 DcimDeviceUpsert strings
src/solution_arista_avd/sorting.py       # EDIT — 2 cast("DcimDevice", …)
transforms/containerlab_topology.py      # EDIT — :202 typename guard, SILENT if missed
generators/generate_avd_device_hostvar.py # EDIT — :1836, :1857, :2786 (the last is silent)
checks/cv_config_check.py                # EDIT — :57 response key, silent if missed
src/solution_arista_avd/protocols.py     # REGENERATE
service_catalog/pages/4_Fabric_View.py   # EDIT — five fragment sites

objects/26_nfd41_devices.yml             # EDIT — spec.kind
tests/unit/test_dcim_schema_contract.py  # NEW — C1 to C8
tests/unit/test_avd.py                   # EDIT — C5; NON_AVD_DEVICE_ROLES does less work
tests/unit/test_device_type_and_platform.py # EDIT — C13 across four kinds
tests/unit/test_routing_schema_contract.py  # EDIT — C8, the pinned peer map
docs/docs/developer-guide/schemas.md     # EDIT — the four device kinds
AGENTS.md                                # EDIT — the data-model hierarchy line
```

**Structure Decision**: the new node goes in `schemas/base/dcim.yml` and its fields in
`schemas/dcim_extensions.yml`, mirroring exactly where `DcimDevice` keeps its own. Splitting them
differently would put two halves of one kind in unfamiliar places for no gain.

## Implementation sequence

The schema-contract tests go in **before** the schema changes, because C6e is what makes the
thirteen peer edits verifiable in one number instead of thirteen reviews.

1. **Write `tests/unit/test_dcim_schema_contract.py`** with C6e first — the identifier-agreement
   parse across all of `schemas/`. It passes today; it must keep passing after every edit below.
   Then C1 to C5, which fail.
2. **Extend the pinned peer map** in `test_routing_schema_contract.py` (C8). This is cycle 024's
   safety net and this cycle edits thirteen peer lines — the same hazard, larger.
3. **Add `DcimFabricSwitch`** to `schemas/base/dcim.yml` with the three inherited generics and the
   display properties. `infrahubctl schema check` — the diff must name one added kind.
4. **Move the twelve fields** in `schemas/dcim_extensions.yml` and split the two role dropdowns.
   Check again: the diff must name `DcimFabricSwitch` added and `DcimDevice` changed, **nothing
   else**.
5. **The thirteen reverse sides**, one file at a time, re-running C6e after each. Seven to the new
   kind, **two widened to the generic**, four deliberately untouched.
   **Anchor every edit on a unique surrounding block.** A global `sed` on `peer: DcimDevice` would
   flip all thirteen including the four that must not move — the precise mistake cycle 024 made,
   which is why step 2 comes before this one.
6. **Retarget the three AVD queries** and regenerate their `*_query.py`.
7. **Retarget the five Python call sites**; regenerate `protocols.py`; mypy.
8. **The four fragment sites** — generic where the field is generic, a concrete fragment only for
   `rack`, both fragments for `role`. Then C11.
9. **`objects/26_nfd41_devices.yml`** — `spec.kind`.
10. **`uv run pytest tests/unit`** — green at or above 1043 before touching the environment.
11. **Capture the baseline** (quickstart step 0), then **destroy, rebuild, load,
    `invoke avd --topology`**.
12. **Compare everything to the baseline**: 33 artifacts, seven EOS configs line-identical, six
    FRR configs and the Junos config byte-identical, 17 cables, 14 nodes and 17 links.
13. **Update the record** — `docs/docs/developer-guide/schemas.md` and `AGENTS.md`, whose
    data-model hierarchy line still reads `LocationRack -> DcimDevice`.
14. **`uv run invoke test` and `uv run invoke lint`.**

### The merge trap, which applies again

`infrahubctl graphql export-schema` has **no `--branch` flag**; it exports Infrahub `main`.
Loading this cycle's schema into `main` to regenerate `schema.graphql` is what made cycle 023's
Infrahub merge fail on a `SchemaAttribute` uniqueness violation.

**This cycle changes schema more than any since 023, so the trap is fully live.** Merge first,
regenerate after — as cycles 024 and 026 did.

## Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| A global `sed` on `peer: DcimDevice` flips the four that must stay | **Medium — this exact mistake was made in cycle 024** | Step 2 pins the complete peer map before any edit; step 5 requires anchored edits, one file at a time |
| A reverse side left on `DcimDevice` → two one-way relationships, **no error** | **Medium, and invisible** | C6e parses every identifier in `schemas/`, not the ones this cycle touched. Re-run after each file |
| A `... on DcimDevice` fragment meets a switch and returns nothing | **Medium** | C11a gives all 20 sites a named disposition. SC-008 explicitly rejects counting as sufficient |
| **A kind-name compared as a Python string is missed** — `containerlab_topology.py:202` drops every switch and emits valid empty YAML | **High, and entirely silent** | C11b names all seven. No fragment grep reaches them; quickstart step 5 checks the topology's node and link counts, which is what would actually catch it |
| A scope figure carried forward instead of re-derived | **High — it has happened in every cycle since 023, including this one** | R8 records the correction; every count in this plan was re-derived at task time |
| The two mixed relationships narrowed to a concrete kind instead of widened | Medium | Quickstart step 12 resolves both and checks each returns **both** kinds. Neither is predictable from its name |
| Baseline lost by rebuilding first | **Low, but unrecoverable** | Step 0 of the quickstart, stated as the one step that cannot be repeated |
| `role` moved to the generic to "fix" the fragments | Medium | C5 makes the two dropdowns different enumerations; moving it up would have to merge them and fail C5 |
| `frr_config.gql` swept up in the retarget | Medium | C10 asserts it byte-identical. It is the file "change every DcimDevice" would break |
| `generate-pod` re-run destroying the topology | Low | Behind `--topology`; quickstart step 7 states why |
| `schema.graphql` regenerated from the wrong branch | **Medium — it bit cycle 023** | Named above; step 13 defers it past the merge |

## Complexity Tracking

No constitution violations require justification. This section is intentionally empty.
