# Schema Design Specification: A Device Kind for Fabric Switches

**Feature Branch**: `027-fabric-switch-kind`
**Created**: 2026-09-14
**Status**: Draft
**Artifact type**: Schema

## Summary

`DcimDevice` currently describes two unrelated things: the EOS switches PyAVD renders, and the
FRR routers of the WAN. It carries the union of both, so an ISP provider edge exposes
`vtep_loopback_ip`, `mlag_domain` and `evpn_gateway_group` — fields that mean nothing for it and
that nothing prevents being set.

This cycle adds **`DcimFabricSwitch`** for the switches and leaves `DcimDevice` router-shaped.

## The repository already made this decision once

This is not a new architectural direction. `schemas/dcim_extensions.yml` says so, next to the
role dropdown:

> There is deliberately no `firewall` value: the marketplace security schema supplies
> `SecurityFirewall`, which inherits `DcimGenericDevice` and `DcimPhysicalDevice`, **so a firewall
> is its own device kind rather than a `DcimDevice` with a role**.

`SecurityFirewall` is already a sibling of `DcimDevice` inheriting the same generics, and
`transforms/junos_config.gql` already targets it by name rather than filtering `DcimDevice` by
role. `DcimFabricSwitch` is the same shape applied to the switches.

## What was measured first

Of the 26 populated-or-not fields on `DcimDevice`, counted across the 7 fabric switches and the
7 WAN routers in the live graph:

| | Count | Examples |
| --- | --- | --- |
| Fabric-only | **10** | `vtep_loopback_ip`, `mlag_domain`, `pod`, `rack`, `loopback_ip`, `mgmt_ip`, `node_id`, `index`, `avd_artifact`, `object_template` |
| Router-only | 3 | `router_id`, `bgp_neighbors`, `location` |
| Both | 2 | `rack_face`, `asn` |
| Neither | 11 | `serial`, `position`, `os_version`, `tenant`, `prefix_lists`, `route_maps`, `evpn_gateway_group`, … |

`evpn_gateway_group` is the sharpest case. It is valid on exactly one role out of thirteen, and
the only thing stopping misuse is a runtime `raise` in
`generators/generate_avd_device_hostvar.py`:

```python
if role != "border_leaf":
    raise _gateway_error(gateway, hostname,
        f"target device role must be 'border_leaf'; actual role is {role!r}")
```

That guard exists because the schema cannot express the constraint. A narrower kind lets the
model say it instead of a generator discovering it at run time.

## A correction this spec is built on

An earlier sketch proposed `DcimFabricSwitch` **inheriting `DcimDevice`**, so existing queries
would keep working unchanged. **That is not possible.** Checked across all 86 nodes and 28
generics in `schemas/`: every `inherit_from` targets a *generic*, never a node, and `DcimDevice`
is a node.

So `DcimFabricSwitch` is a **sibling**, not a subtype, and queries that name `DcimDevice` will
stop seeing fabric switches. That is the cycle's real cost and the spec is scoped around it
rather than around the easier thing that cannot be built.

## Schema Files

```text
schemas/base/dcim.yml         # EDIT — the new node, beside DcimDevice
schemas/dcim_extensions.yml   # EDIT — fabric-only fields move to the new kind
```

Neither file is marketplace-adopted; `schemas/MARKETPLACE.md` lists four adopted files and these
are not among them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A router no longer carries fabric fields (Priority: P1)

Someone reading `isp-pe1` in the UI or in a query sees the fields a router has, not the union of
every device type in the lab.

**Why this priority**: it is the cycle's purpose.

**Independent Test**: query an `isp-pe1` and confirm `vtep_loopback_ip`, `mlag_domain` and
`evpn_gateway_group` are not fields it has; query a spine and confirm they are.

**Acceptance Scenarios**:

1. **Given** the new schema, **When** `DcimDevice` is inspected, **Then** it has no
   `vtep_loopback_ip`, `mlag_domain`, `evpn_gateway_group`, `node_id`, `index`, `pod`,
   `avd_artifact` or `object_template`.
2. **Given** the new schema, **When** `DcimFabricSwitch` is inspected, **Then** it has all of
   them.
3. **Given** a router, **When** something tries to set a fabric-only field on it, **Then** the
   attempt fails at the schema rather than at run time.

### User Story 2 - The AVD pipeline still renders every switch (Priority: P1)

The seven EOS configurations come out exactly as they do today.

**Why this priority**: equal to US1. The split is only worth doing if nothing regresses, and
three queries in the AVD path name `DcimDevice` explicitly.

**Independent Test**: render all seven EOS configs and diff against the lab's intended configs,
which currently match line for line.

**Acceptance Scenarios**:

1. **Given** the split, **When** the AVD chain runs, **Then** all seven switches get hostvars and
   structured configs.
2. **Given** the rendered artifacts, **When** compared to `lab/avd/intended/configs/*.cfg` with
   device names normalised, **Then** zero lines differ — the same result as before this cycle.
3. **Given** the fabric generators, **When** they run on an empty instance, **Then** they create
   switches of the new kind and cable them.

### User Story 3 - The WAN and firewall are untouched (Priority: P2)

`frr_config` and `junos_config` render exactly as before.

**Why this priority**: separable, and the expected outcome — routers keep their kind, so those
paths should not move at all. It is here because "should not move" deserves a test rather than an
assumption.

**Independent Test**: render the six FRR configs and the Junos config and compare to today's
output.

**Acceptance Scenarios**:

1. **Given** the split, **When** `frr_config` renders, **Then** all six router configs are
   byte-identical to before.
2. **Given** the split, **When** `junos_config` renders, **Then** the 596-line artifact is
   byte-identical to before.

### Edge Cases

- **A query that names `DcimDevice` and expects a switch returns nothing, silently.** This is the
  failure mode the repository has hit three times — most recently the cabling plan, which dropped
  every cable for months because it spread only `... on DcimDevice`. Every such site must be
  found and changed deliberately.
- **Polymorphic relationships that peer `DcimGenericDevice`** — `RoutingStaticRoute.device`, which
  cycle 024 widened for exactly this reason — keep working with no change, because the new kind
  inherits that generic.
- **`ROLE_TO_AVD_TYPE` becomes the boundary.** Its ten roles are precisely the fabric set; the
  non-EOS roles are deliberately absent and `get_avd_type` raises for them. The split must not
  make that guard redundant *or* contradict it.
- **Group membership** — `avd_devices` is the only path into the AVD hostvar generator, and
  `src/solution_arista_avd/generator.py` is the single place membership is set.
- **Existing data.** The seven switches are seeded as `kind: DcimDevice` in
  `objects/26_nfd41_devices.yml`. See Assumptions.

## Requirements *(mandatory)*

### Nodes & Generics

- **FR-001**: A new node `DcimFabricSwitch` (namespace `Dcim`, name `FabricSwitch`) MUST be
  defined in `schemas/base/dcim.yml`.
- **FR-002**: It MUST inherit exactly what `DcimDevice` inherits — `CoreArtifactTarget`,
  `DcimGenericDevice`, `DcimPhysicalDevice` — so that every relationship peering those generics
  continues to resolve.
- **FR-003**: `DcimDevice` MUST continue to exist for routers. It is not renamed; renaming it
  would move the blast radius onto the WAN for no gain.
- **FR-004**: No new generic MUST be introduced. `DcimGenericDevice` already serves.

### Attributes & Relationships

- **FR-005**: These MUST move from `DcimDevice` to `DcimFabricSwitch`: `vtep_loopback_ip`,
  `mlag_domain`, `evpn_gateway_group`, `node_id`, `index`, `pod`, `rack`, `avd_artifact`,
  `object_template`, `loopback_ip`, `mgmt_ip`, `avd_custom_hostvars`.
- **FR-006** *(corrected during implementation)*: These MUST stay on `DcimDevice`: `router_id`,
  `bgp_neighbors`. **`location` was listed here in error** — it is not on `DcimDevice` at all, but
  on the `DcimPhysicalDevice` generic that `DcimDevice`, `DcimFabricSwitch`, `SecurityFirewall` and
  `ComputePhysicalServer` all inherit. Making it router-only would change a generic shared with the
  firewall and the servers, which is outside this cycle. It is pinned as shared under FR-007.
- **FR-007**: `status`, `role`, `rack_face`, `asn`, `device_type`, `platform` MUST be available on
  **both**, since both kinds use them.
- **FR-008**: The `role` dropdown on `DcimFabricSwitch` MUST offer only the fabric roles — the ten
  in `ROLE_TO_AVD_TYPE`. `DcimDevice`'s MUST offer only the non-fabric ones.
- **FR-009**: Both ends of every moved relationship MUST be updated together; a reverse side left
  pointing at `DcimDevice` produces two one-way relationships and no error.
- **FR-009a** *(added after Phase 1)*: All **thirteen** `peer: DcimDevice` sites in `schemas/` MUST
  be given an explicit disposition, not only those that are the reverse of a field in FR-005. Four
  of the seven needing change — `EvpnSviNode.device`, `RoutingVrfBgpPeer.devices`,
  `RoutingVrfL3Interface.device` and `RoutingVrfStaticRoute.devices` — have **no forward side on
  `DcimDevice` at all**, so FR-005's list does not reach them.
- **FR-009b** *(added after Phase 1)*: Two reverse sides MUST be widened to `DcimGenericDevice`
  rather than retargeted, because their objects span both kinds — measured, not inferred:
  `RoutingAsn.devices` (6 routers and 7 switches, since `asn` is on both kinds per FR-007) and
  `RoutingVrfStaticRoute.devices` (10 routes shared by `isp-pe1` and `leaf-nfd41-pod1-3-1`, the
  two ends of one tenant handoff).

### Display & Identification

- **FR-010**: `DcimFabricSwitch` MUST use the same `human_friendly_id`, `display_label` and
  `order_by` as `DcimDevice`, so nothing downstream has to special-case it.
- **FR-011**: It MUST appear in the menu alongside devices.

### Consumers

- **FR-012** *(corrected at task time — see research R8)*: **Six** GraphQL query roots that name
  `DcimDevice` MUST be retargeted: `generators/avd_device_hostvar.gql:2`,
  `transforms/avd_device_config.gql:2`, `transforms/avd_anta_catalog.gql:2` **and `:31`**,
  `transforms/avd_fabric_devices.gql:12`, and `checks/cv_config_check.gql:15`. The spec previously
  said three; the enumeration behind that number did not cover `checks/`.
- **FR-013** *(corrected at task time — see research R8)*: **Twelve** typed Python call sites that
  filter, create or get fabric devices MUST be retargeted: `generate_pod.py:244`,
  `generate_rack.py:179`, `generate_server_cabling.py:56`, `asn.py:46`, and **seven** in
  `src/solution_arista_avd/generator.py` (`:693` filters, `:712` creates, `:744`, `:1036`, `:1075`,
  `:1113`, `:1161` get). The spec previously said five.
- **FR-013a** *(added at task time)*: **Three raw GraphQL mutation strings** naming
  `DcimDeviceUpsert` MUST be retargeted: `generators/asn.py:21`,
  `src/solution_arista_avd/generator.py:1063` and `:1087`.
- **FR-013b** *(added at task time)*: **Seven Python sites that compare a kind name as a string**
  MUST be retargeted. Three of these fail **silently** and none was reachable by grepping for
  GraphQL fragments:
  `transforms/containerlab_topology.py:202` (`if node.typename != "DcimDevice": continue` — drops
  all seven switches and emits valid, empty YAML),
  `generators/generate_avd_device_hostvar.py:2786` (`raw_data.get("DcimDevice", {})` — the response
  key changes with the query root), and `checks/cv_config_check.py:57`. The rest are
  `generate_avd_device_hostvar.py:1836` and `:1857` (`kind="DcimDevice"`) and
  `src/solution_arista_avd/sorting.py:22` and `:38` (`cast("DcimDevice", ...)`).
- **FR-014** *(corrected at task time — see research R8)*: All **twenty** `... on DcimDevice`
  fragment sites across **ten** files MUST be reviewed and given a disposition. The spec
  previously named four files; it missed `generators/avd_device_hostvar.gql` (5 sites),
  `generators/generate_avd.gql`, `generators/backfill_structured_config.gql`,
  `generators/generate_fabric_peering.gql`, `checks/fabric_pool_check.gql` and
  `checks/peering_consistency_check.gql`. Where the generic carries the field, reading it from
  `DcimGenericDevice` is preferred to adding a second fragment.
- **FR-015**: `transforms/frr_config.gql` MUST NOT change. Its targets stay `DcimDevice`.
- **FR-016**: `src/solution_arista_avd/protocols.py` MUST be regenerated, never hand-edited.

### Objects

- **FR-017**: `objects/26_nfd41_devices.yml` MUST declare the switches as `DcimFabricSwitch`.
- **FR-018**: `objects/31_nfd41_offfabric_devices.yml` and `31a_nfd41_wan_addressing.yml` MUST
  keep declaring routers as `DcimDevice`.

### Migration

- **FR-019**: No in-place data migration. The environment is destroyed and rebuilt, on the
  requester's decision — see Assumptions.

## Key Entities

- **`DcimFabricSwitch`** — new. The EOS switches PyAVD renders: spines, leaves, border leaves.
- **`DcimDevice`** — existing, narrowed. The WAN's FRR routers.
- **`SecurityFirewall`** — existing, untouched. The precedent this cycle follows.
- **`ComputePhysicalServer`** — existing, untouched.
- **`DcimGenericDevice`** — the generic all four inherit, and what polymorphic relationships peer.

## Success Criteria *(mandatory)*

- **SC-001**: `infrahubctl schema check schemas/` passes with zero errors.
- **SC-002**: `DcimDevice` no longer exposes any of the twelve moved fields; `DcimFabricSwitch`
  exposes all twelve. Asserted against the loaded schema, not the YAML alone.
- **SC-003**: All seven EOS configurations render, and match `lab/avd/intended/configs/*.cfg`
  **line for line** after device-name normalisation — the same zero-difference result as before
  this cycle.
- **SC-004**: The six FRR configurations and the 596-line Junos configuration are byte-identical
  to their pre-cycle output.
- **SC-005**: The cabling plan still renders all 17 cables, and the ContainerLab topology still
  renders 14 nodes and 17 links.
- **SC-006**: A full `destroy` → `build` → `start` → `load` → `invoke avd --topology` produces the
  same 33 artifacts with the same content as today.
- **SC-007**: Every device still has a device type and a platform (cycle 026's guarantee holds).
- **SC-008**: No `... on DcimDevice` site anywhere can silently return nothing for a switch; each
  is either retargeted or proven not to encounter one.
- **SC-008a** *(added after Phase 1)*: Every relationship identifier declared on two ends names the
  **same** peer on both. Asserted by parsing all of `schemas/`, not only the files this cycle
  edits — a one-way relationship loads and validates without error, and surfaces later as a field
  that is silently always empty.
- **SC-009**: The full unit suite stays green at or above its current 1043.

## Assumptions

1. **The environment is destroyed and rebuilt rather than migrated**, on the requester's explicit
   decision. That removes the hardest part: the seven switches are *seeded* in
   `objects/26_nfd41_devices.yml`, so changing `spec.kind` plus a rebuild is the whole data story.
   Without it this cycle would need a kind-change migration Infrahub does not offer directly.
2. **Routers keep `DcimDevice` rather than gaining a new name.** Narrowing the existing kind moves
   less: the WAN's queries, objects and transforms stay as they are, and the churn lands on the
   AVD path, which is where the new kind is needed anyway.
3. **`ROLE_TO_AVD_TYPE` is the authoritative fabric/non-fabric boundary.** It already enumerates
   the ten EOS roles, the non-EOS roles are deliberately absent, and `get_avd_type` raises on an
   unmapped one. The split follows that line rather than drawing a new one.
4. **The eleven fields unused by both kinds are out of scope.** Some are upstream generality
   (`serial`, `position`), some are built-but-unpopulated (`evpn_gateway_group`), and some may be
   dead. Deciding that is a separate question; this cycle only moves the ones it must.

## Scope

**In scope**: one new node, twelve fields moved, the role dropdowns split, the AVD queries and
Python paths retargeted, the object files' `spec.kind`, and the tests that hold all of it.

**Out of scope**:

- **Renaming `DcimDevice`.** Assumption 2.
- **Removing the eleven unused fields.** Assumption 4.
- **`SecurityFirewall` and `ComputePhysicalServer`.** Already their own kinds.
- **The ContainerLab transform's fabric-only scope** — unchanged by request, and orthogonal.
- **Any in-place migration path.** Assumption 1.

## Dependencies

Cycles 023–026 are merged and pushed. The live environment currently renders all 33 artifacts
correctly, all seven EOS configs match the lab, and every device has a device type and platform —
which is the baseline SC-003 to SC-007 compare against.
