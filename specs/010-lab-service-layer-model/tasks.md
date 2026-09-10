---

description: "Task list for the technical and service layer schema feature"
---

# Tasks: Technical and Service Layers for the Full NFD41 Lab

**Input**: Design documents from `/specs/010-lab-service-layer-model/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/schema-kinds.md](./contracts/schema-kinds.md), [quickstart.md](./quickstart.md)

**Tests**: **REQUIRED.** Constitution IV mandates unit tests before merge, and the plan's Complexity Tracking makes four `test_*_schema_contract.py` suites the primary quality gate in place of the unavailable `$infrahub-run-integration-tests` skill. Each story writes its contract test **before** its schema YAML.

**Organization**: Tasks are grouped by the seven user stories from spec.md so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US7)
- Exact file paths appear in every task

## Path Conventions

Infrahub reference-design repository, per the plan's Structure Decision:

- Schema definitions: `schemas/<domain>/*.yml`, plus root-level `schemas/*_extensions.yml`
- Generated protocols: `src/solution_arista_avd/protocols.py` (**never hand-edited**)
- Unit tests: `tests/unit/test_*_schema_contract.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Working environment, directories, and a branch to load schema against

- [X] T001 Verify preflight: run `uv sync --all-packages` then `uv run infrahubctl info` and confirm Connection Status ✅ with Infrahub 1.10.6, per [quickstart.md](./quickstart.md) Prerequisites
- [X] T002 [P] Create the four new schema directories `schemas/service/`, `schemas/kubernetes/`, `schemas/security/`, `schemas/wan/` per the plan's Structure Decision
- [X] T003 Create the Infrahub working branch with `uv run infrahubctl branch create svc-layer` for all `schema check` and `schema load` runs in later phases

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The three shared files every story depends on. Each is a single file that multiple stories would otherwise edit concurrently, so all edits happen once, here.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. `OrganizationCustomer` gates US1's mandatory `owner` relationship and US6's `WanTenant.customer`; the two dropdown extensions gate US2, US4, US6, and US7.

- [X] T004 [P] Write the foundational contract test in `tests/unit/test_lab_layers_foundation_schema_contract.py` asserting: `OrganizationCustomer` exists and inherits `OrganizationGeneric`; `DcimDevice.role` contains the 7 new choices; `IpamPrefix.role` contains the 6 new choices; and that all pre-existing role choices in both dropdowns are still present (the additive-compatibility guarantee in [contracts/schema-kinds.md](./contracts/schema-kinds.md) §7). Follow the local-helper pattern of `tests/unit/test_fabric_pool_schema_contract.py`
- [X] T005 [P] Create `schemas/organization_extensions.yml` defining the `OrganizationCustomer` node per [data-model.md](./data-model.md) §2 — `inherit_from: [OrganizationGeneric]`, one optional `account_reference` Text attribute, `icon: mdi:domain`, `include_in_menu: true`. Do **not** redeclare `human_friendly_id`, `display_label`, `order_by`, or uniqueness: all are inherited
- [X] T006 Add the 7 non-EOS device roles (`firewall`, `isp_edge`, `isp_core`, `internet_edge`, `customer_edge`, `branch_router`, `k8s_node`) to the existing `DcimDevice.role` dropdown in `schemas/dcim_extensions.yml` per [data-model.md](./data-model.md) §3, appending to the existing `choices` list without reordering it
- [X] T007 Verify the invariant from [research.md](./research.md) R7 by confirming `ROLE_TO_AVD_TYPE` in `src/solution_arista_avd/avd.py` is **unchanged** — none of the 7 new roles may be added there, because `get_avd_type` raises `ValueError` on an unmapped role and adding one would let a non-EOS device render as EOS
- [X] T008 Add the 6 new prefix roles (`pod`, `service`, `vip_pool`, `wan_customer`, `branch_lan`, `tenant_cloud`) to the existing `IpamPrefix.role` dropdown in `schemas/ipam_extensions.yml` per [data-model.md](./data-model.md) §4. Note `role` is `optional: false` on this node, so every new prefix object will require one
- [X] T009 Run `uv run yamllint schemas/` and `uv run pytest tests/unit/test_lab_layers_foundation_schema_contract.py` and confirm both pass
- [X] T010 Run `uv run infrahubctl schema check schemas/ --branch svc-layer` and confirm zero validation errors, establishing the baseline diff before any new kind is added

**Checkpoint**: Foundation ready — the shared dropdowns carry every value the seven stories need, and `ServiceGeneric.owner` has an instantiable peer.

---

## Phase 3: User Story 1 - Services layer foundation (Priority: P1) 🎯 MVP (with US2)

**Goal**: The abstraction that separates ordered intent from device fact — `ServiceGeneric` plus the binding generics, and the single `extensions:` block that is the only place the technical layer learns the service layer exists.

**Independent Test**: `uv run infrahubctl schema check schemas/` passes, and after loading, a GraphQL query on `ServiceGeneric` returns an empty typed result set with `name`, `status`, and `owner` selectable — the abstraction is queryable across service kinds before any concrete kind exists.

### Tests for User Story 1 ⚠️

> Write these first and confirm they FAIL before T013.

- [X] T011 [P] [US1] Write the service-layer contract test in `tests/unit/test_service_layer_schema_contract.py` asserting: `ServiceGeneric` exists as a **generic** with `name` (Text, unique), `status` (Dropdown with exactly the 5 choices in [data-model.md](./data-model.md) §5 and `default_value: provisioning`), and a mandatory `owner` relationship of cardinality one peering `OrganizationGeneric`; that `ServiceGenericDevice` and `ServiceGenericInterface` exist with matching `identifier` values `device_services` / `interface_services`; and that `ServiceGeneric.name` is **not** `branch: agnostic` (the deliberate divergence from demo-dc documented in [data-model.md](./data-model.md) §5)
- [X] T012 [P] [US1] Add the layering test `test_no_technical_schema_references_a_service_kind` to `tests/unit/test_service_layer_schema_contract.py`, walking every node, generic, and extension relationship in `schemas/kubernetes/`, `schemas/security/`, `schemas/wan/`, and `schemas/organization_extensions.yml` and failing on any `peer` value starting with `Service`. Write it to tolerate files that do not exist yet, so it stays valid through US2–US7 and strengthens as each adds a technical file. This is the only enforcement of FR-080 and SC-009 that no server-side check can perform

### Implementation for User Story 1

- [X] T013 [US1] Create `schemas/service/service.yml` defining `ServiceGeneric`, `ServiceGenericDevice`, and `ServiceGenericInterface` per [data-model.md](./data-model.md) §5, with `include_in_menu: false` on all three and `uniqueness_constraints: [["name__value"]]` on `ServiceGeneric`
- [X] T014 [US1] Add the `extensions:` block to `schemas/service/service.yml` adding `device_services` to `DcimGenericDevice` and `interface_services` to `DcimInterface`, both `peer: ServiceGeneric`, cardinality many, optional, `on_delete: no-action`, with identifiers matching the binding generics per [research.md](./research.md) R6. This block must live in this file and nowhere else — placing it in `schemas/base/dcim.yml` would violate Constitution I and break SC-009
- [X] T015 [US1] Run `uv run pytest tests/unit/test_service_layer_schema_contract.py`, `uv run yamllint schemas/`, and `uv run infrahubctl schema check schemas/ --branch svc-layer`; confirm the diff adds exactly 3 generics and modifies `DcimGenericDevice` and `DcimInterface`
- [X] T016 [US1] Load and regenerate: `uv run infrahubctl schema load schemas --branch svc-layer --wait 30`, then `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py`, then `uv run mypy --show-error-codes src/solution_arista_avd`. Confirm a `ServiceGeneric` class appears in `protocols.py` and mypy passes

**Checkpoint**: The service layer's query surface exists. A `ServiceGeneric` query answers "what services exist, who owns them, what state are they in" (SC-006) against an empty set.

---

## Phase 4: User Story 2 - Kubernetes and Cilium technical layer (Priority: P1) 🎯 MVP (with US1)

**Goal**: The k3s cluster as a first-class routing participant in the fabric — cluster, nodes, CNI, the pod/service/node prefixes, the VIP pool, and the BGP sessions Cilium holds with the two `k8s-leaf` switches.

**Independent Test**: Schema check passes; the cluster, its three nodes, and its two BGP peerings can be created as objects, and each peering's leaf-side neighbour resolves to an existing `DcimDevice` in the fabric — proving the cross-domain link without any service kind or renderer existing.

### Tests for User Story 2 ⚠️

- [X] T017 [P] [US2] Write `tests/unit/test_kubernetes_schema_contract.py` asserting the three nodes and their fields per [data-model.md](./data-model.md) §6: `KubernetesCluster` inherits `GeneratorTarget` and carries `local_asn` as Number with the 32-bit AS `parameters` range; `pod_prefix`, `service_prefix`, and `node_prefix` are **relationships** to `IpamPrefix` with cardinality one and not `IPNetwork` attributes (FR-022); `nodes` and `fabric_peerings` are `Component` relationships with `Parent` counterparts sharing an identifier (FR-041); and `KubernetesFabricPeering` has `uniqueness_constraints: [["cluster", "leaf_device"]]` (FR-071)
- [X] T018 [P] [US2] Add an assertion to `tests/unit/test_kubernetes_schema_contract.py` that `KubernetesNode.device` peers `DcimGenericDevice` — the generic, not `DcimDevice` — so a `ComputePhysicalServer` also satisfies it, per [research.md](./research.md) R7
- [X] T019 [P] [US2] Add an assertion that no attribute of kind `IPNetwork` or `IPHost` appears anywhere in `schemas/kubernetes/kubernetes.yml`, enforcing SC-008 for this domain

### Implementation for User Story 2

- [X] T020 [US2] Create `schemas/kubernetes/kubernetes.yml` defining `KubernetesCluster` per [data-model.md](./data-model.md) §6 — 12 attributes including the `bgp_timers`, `node_selector`, and `advertisement_selector` JSON fields, and 7 relationships. Store `bgp_auth_secret_name` as the secret's **name** only, never its value
- [X] T021 [US2] Add `KubernetesNode` to `schemas/kubernetes/kubernetes.yml` with its `Parent` relationship to the cluster, its mandatory `device` relationship to `DcimGenericDevice`, the optional `node_address` and `pod_cidr` IPAM relationships, and `uniqueness_constraints: [["cluster", "name__value"]]`
- [X] T022 [US2] Add `KubernetesFabricPeering` to `schemas/kubernetes/kubernetes.yml` with `peer_asn`, the mandatory `leaf_device` and `leaf_address` relationships, and the optional `svi` relationship to `EvpnSvi`. `leaf_address` must reference a leaf's **unique** SVI address (`10.110.0.2` / `.3`), never the MLAG pair's shared VARP gateway `10.110.0.1` — an anycast address is ambiguous across the pair, which is US2 acceptance scenario 4
- [X] T023 [US2] Validate and load: `uv run pytest tests/unit/test_kubernetes_schema_contract.py tests/unit/test_service_layer_schema_contract.py`, `uv run yamllint schemas/`, `uv run infrahubctl schema check schemas/ --branch svc-layer`, then load, regenerate protocols, and run mypy per T016's command sequence

**Checkpoint**: MVP complete. The service abstraction exists and the Kubernetes domain the request names first is modeled, with its BGP contract to the fabric in the same graph as the leaves.

---

## Phase 5: User Story 3 - Kubernetes platform and application services (Priority: P2)

**Goal**: The two service kinds that render Crossplane manifests — a fabric-peering service and a fabric-application service carrying namespace, tenant, workload source, VIP block, service selector, and network-policy baseline.

**Independent Test**: The lab's `FabricPeering` and `FabricApp` custom resources can each be represented as a single Infrahub object with no field left unmodeled, verified by transcribing `../lab/crossplane/platform/10-peering.yaml` and `../lab/crossplane/apps/10-demo.yaml` and confirming a lossless round trip of every field the compositions consume.

**Dependencies**: US1 (`ServiceGeneric`) and US2 (`KubernetesCluster`, `KubernetesFabricPeering`).

### Tests for User Story 3 ⚠️

- [X] T024 [P] [US3] Extend `tests/unit/test_service_layer_schema_contract.py` asserting `ServiceFabricPeering` and `ServiceFabricApp` each inherit all three of `ServiceGeneric`, `GeneratorTarget`, and `CoreArtifactTarget` (FR-081, FR-083, per [research.md](./research.md) R2 and R3)
- [X] T025 [P] [US3] Add assertions to `tests/unit/test_service_layer_schema_contract.py` that `ServiceFabricApp.allowed_source_prefixes` is a relationship to `IpamPrefix` with cardinality many — not a List of CIDR strings — because it must name the same objects the firewall zone policy and the leaf ACL reference (US3 acceptance scenario 3, SC-008); and that every service→technical relationship in the file sets `on_delete: no-action` (FR-053)
- [X] T026 [P] [US3] Add an assertion to `tests/unit/test_service_layer_schema_contract.py` that `ServiceFabricApp.vip_block` and `service_selector` are **optional**, so an object with `exposed: false` and no VIP validates as a cluster-internal application (US3 acceptance scenario 4)

### Implementation for User Story 3

- [X] T027 [US3] Create `schemas/service/kubernetes_services.yml` defining `ServiceFabricPeering` per [data-model.md](./data-model.md) §7 — `communities` List, `advertisement_selector` JSON, a mandatory `cluster` relationship, and a `peerings` relationship recording the technical objects that realize it (FR-082)
- [X] T028 [US3] Add `ServiceFabricApp` to `schemas/service/kubernetes_services.yml` with its 16 attributes and 5 relationships. Name the namespace attribute `namespace_name`, not `namespace`, which is a reserved schema word. Keep the chart fields (`chart_repository`, `chart_name`, `chart_version`, `chart_values`) and `manifests` all optional so a chart-only, manifest-only, or combined workload source all validate (FR-025)
- [X] T029 [US3] Verify SC-005 for the platform half: transcribe every field of `../lab/crossplane/platform/10-peering.yaml` and `../lab/crossplane/apps/10-demo.yaml` against the new kinds and record any field with no modeled destination as a gap in `specs/010-lab-service-layer-model/` rather than working around it
- [X] T030 [US3] Validate and load per T016's command sequence, confirming `ServiceFabricApp` appears in `protocols.py` listing both `CoreArtifactTarget` and `GeneratorTarget`

**Checkpoint**: The two service kinds a later transform will render into Crossplane manifests exist and are artifact-capable, so that cycle needs no schema change.

---

## Phase 6: User Story 4 - Firewall and security technical layer (Priority: P2)

**Goal**: The perimeter vSRX as data — six security zones, the interfaces each binds, the address book and its groups, and the zone-pair policies with ordered rules, match criteria, and actions. Infrahub becomes the source of truth for the whole device, per the requester's confirmed decision (spec assumption 8).

**Independent Test**: All six zones, all address-book entries, all four address groups, and every zone-pair policy in `../lab/configs/fw/vsrx/junos.conf` can be represented as objects with rule evaluation order preserved — verified by transcription, without a renderer existing.

**Dependencies**: Foundational only (the `firewall` device role). Independent of US2 and US3.

### Tests for User Story 4 ⚠️

- [X] T031 [P] [US4] Write `tests/unit/test_security_schema_contract.py` asserting the six nodes exist per [data-model.md](./data-model.md) §8, that `SecurityZone.device` is mandatory cardinality one peering `DcimDevice` (FR-045), and that `SecurityZone` has `uniqueness_constraints: [["device", "name__value"]]` so two firewalls may each hold a zone named `wan`
- [X] T032 [P] [US4] Add assertions to `tests/unit/test_security_schema_contract.py` that `SecurityAddress` references IPAM (`prefix` → `IpamPrefix` or `ip_address` → `IpamIPAddress`) and declares **no** text CIDR attribute (FR-044), and that `SecurityAddressGroup` can nest via a self-referential `groups` relationship (US4 acceptance scenario 3)
- [X] T033 [P] [US4] Add assertions to `tests/unit/test_security_schema_contract.py` that `SecurityPolicy` has `uniqueness_constraints: [["source_zone", "destination_zone"]]` (FR-072) and carries **no** `name` attribute — the zone pair is its identity; and that `SecurityPolicyRule` has both `[["policy", "name__value"]]` and `[["policy", "sequence__value"]]` constraints (FR-073) plus `order_by: [sequence__value]` so consumers need not sort
- [X] T034 [P] [US4] Add an assertion to `tests/unit/test_security_schema_contract.py` that `SecurityPolicyRule.action` is a Dropdown whose choices include `permit` and `deny` as distinct values, so a deny is distinguishable from the absence of a permit (FR-026, US4 acceptance scenario 5); and that `managed_by_service` exists as a Boolean defaulting to false — the guard that lets a generator reconcile only the rules it owns and leave the hand-written anti-spoofing baseline alone

### Implementation for User Story 4

- [X] T035 [US4] Create `schemas/security/security.yml` defining `SecurityZone` per [data-model.md](./data-model.md) §8 — `trust_level` Number with a 0–100 `parameters` range, mandatory `device`, and the `interfaces` and `vrf` relationships that make the fabric handoff a graph path
- [X] T036 [US4] Add `SecurityAddress`, `SecurityAddressGroup`, and `SecurityApplication` to `schemas/security/security.yml`. Model `port` and `port_range_end` as separate Number attributes so a single port and a range are both expressible
- [X] T037 [US4] Add `SecurityPolicy` and `SecurityPolicyRule` to `schemas/security/security.yml` with the `Component`/`Parent` pair sharing identifier `policy__rules` (FR-042), the mandatory `sequence` ordering attribute, and the six match relationships. Do **not** add `match_any_source` / `match_any_destination` booleans — the lab's `destination-address any` is represented by a `SecurityAddress` named `any` bound to `0.0.0.0/0`, which keeps every rule's match explicit
- [X] T038 [US4] Verify SC-004: transcribe every zone, address-book entry, address group, and zone-pair policy in `../lab/configs/fw/vsrx/junos.conf` against the new kinds — 6 zones, 13 addresses, 4 groups, 11 zone pairs and 19 rules — confirming rule evaluation order is preserved and the anti-spoofing rule repeated at the head of the first six zone pairs is representable with `managed_by_service: false`
- [X] T039 [US4] Validate and load per T016's command sequence, running `uv run pytest tests/unit/test_security_schema_contract.py` alongside the earlier suites

**Checkpoint**: The one device in the lab with no model now has a complete one. The three limitations no schema constraint can express (exactly-one-of on `SecurityAddress`, non-empty groups, acyclic nesting) are recorded in [data-model.md](./data-model.md) §13 for the checks cycle.

---

## Phase 7: User Story 5 - Self-service application access (Priority: P3)

**Goal**: The access grant — requester, application, source, destination VIP, ports — gated by an approval flag, composing the application deployment and the firewall rule as two halves of one declaration.

**Independent Test**: The lab's `AppAccess` and the `FirewallAccess` it emits can both be represented; an unapproved grant is inert and composes nothing, and an approved grant names every object a reviewer would need to revoke it.

**Dependencies**: US3 (`ServiceFabricApp`) and US4 (`SecurityZone`, `SecurityAddress`, `SecurityPolicyRule`).

### Tests for User Story 5 ⚠️

- [X] T040 [P] [US5] Extend `tests/unit/test_service_layer_schema_contract.py` asserting `ServiceAppAccess` inherits `ServiceGeneric`, `GeneratorTarget`, and `CoreArtifactTarget`, and that `approved` is a Boolean with `default_value: false` — the gate that makes an unapproved request inert rather than merely hidden (FR-029, US5 acceptance scenario 2)
- [X] T041 [P] [US5] Add assertions to `tests/unit/test_service_layer_schema_contract.py` that `application`, `source_zone`, `source_address`, and `destination_vip` are all mandatory cardinality-one relationships (FR-049), that `source_address` peers `SecurityAddress` rather than carrying a CIDR (the firewall's own vocabulary stays the vocabulary), and that `granted_rules` peers `SecurityPolicyRule` so revocation is traceable (FR-082, US5 acceptance scenario 5)
- [X] T042 [P] [US5] Add an assertion to `tests/unit/test_service_layer_schema_contract.py` that `approved_by` and `approved_at` exist, so the audit trail lives on the grant rather than only in change history (US5 acceptance scenario 3)

### Implementation for User Story 5

- [X] T043 [US5] Create `schemas/service/access_services.yml` defining `ServiceAppAccess` per [data-model.md](./data-model.md) §9 — 6 attributes including the `approved` gate and a `ports` List, and 5 relationships all with `on_delete: no-action`
- [X] T044 [US5] Verify SC-005 for the access half: transcribe every field of `../lab/crossplane/access/01-xrd-app-access.yaml` and `../lab/crossplane/access/00-crd-firewall-access.yaml` against `ServiceAppAccess` and `SecurityPolicyRule`, recording any field with no destination. Note that US5 acceptance scenario 4 (a VIP outside the range the border leaf re-advertises) is *detectable* from the graph but not constraint-enforceable — it belongs to the checks cycle per [data-model.md](./data-model.md) §13
- [X] T045 [US5] Validate and load `schemas/service/access_services.yml` per T016's command sequence, running `uv run pytest tests/unit/test_service_layer_schema_contract.py` alongside the earlier suites

**Checkpoint**: An access grant is one object naming the application, the firewall source, and the rules it caused to exist — the two halves the lab notes are "always forgotten separately".

---

## Phase 8: User Story 6 - Provider, WAN and branch technical layer (Priority: P3)

**Goal**: Everything outside the fabric that `../lab/wan/tenants.yml` holds — the ISP and its AS, the customer-facing and DC-facing PE roles, the internet AS and its peering, each site's attachment circuit and how it attaches, and the branch office's private circuit.

**Independent Test**: Every field of `../lab/wan/tenants.yml` — both tenants, all three sites, both attachment kinds, the internet peering, and the branch — can be represented as objects, verified by transcription against the file.

**Dependencies**: Foundational only (`OrganizationCustomer` and the ISP/CE/branch device roles). Independent of US2–US5.

### Tests for User Story 6 ⚠️

- [X] T046 [P] [US6] Write `tests/unit/test_wan_schema_contract.py` asserting the four nodes exist per [data-model.md](./data-model.md) §10, that `WanTenant.provider` peers `OrganizationProvider` and `customer` peers `OrganizationCustomer` (FR-006, [research.md](./research.md) R8), and that `WanTenant.kind` is a Dropdown with choices `customer` and `internal` — the mechanism that holds the branch without forcing it into a customer shape ([research.md](./research.md) R10)
- [X] T047 [P] [US6] Add assertions to `tests/unit/test_wan_schema_contract.py` that `WanSite.attachment_kind` is a Dropdown with choices `bgp` and `static` (FR-028), that `WanSite` has `uniqueness_constraints: [["tenant", "name__value"]]` (FR-074), and that `WanCircuit` has `uniqueness_constraints: [["provider_edge_interface"]]` so two circuits cannot claim one PE interface
- [X] T048 [P] [US6] Add an assertion to `tests/unit/test_wan_schema_contract.py` that `WanCircuit` models the provider-edge and customer-edge sides as **four separate** relationships (`provider_edge_interface`, `provider_edge_address`, `customer_edge_interface`, `customer_edge_address`) on two distinct devices (FR-046) — the lab warns that conflating the two sides "is how the internet router ends up waiting forever for an interface that only exists on isp-pe2"
- [X] T049 [P] [US6] Add assertions that `WanCircuit.bgp_session` peers the existing `RoutingBGPNeighbor` and `static_routes` peers the existing `RoutingVrfStaticRoute` rather than introducing parallel session or route kinds (FR-010), and that no `IPNetwork`/`IPHost` attribute appears in `schemas/wan/wan.yml` (SC-008)

### Implementation for User Story 6

- [X] T050 [US6] Create `schemas/wan/wan.yml` defining `WanTenant` per [data-model.md](./data-model.md) §10 — `tenant_id`, the `kind` dropdown, `vrf_name` and `vrf_table_id`, an optional `customer`, a mandatory `provider`, the `sites` Component relationship, and the optional `dc_vrf` relationship that bridges to the fabric ([research.md](./research.md) R9)
- [X] T051 [US6] Add `WanSite` and `WanCircuit` to `schemas/wan/wan.yml`. `WanCircuit.provider_edge_interface` must peer the `DcimInterface` **generic** so the branch's circuit can terminate on `border-leaf1` rather than a PE. Default `mtu` to 9214 — the lab warns the veth default of 9500 makes the mismatch "silent and expensive"
- [X] T052 [US6] Add `WanInternetPeering` to `schemas/wan/wan.yml` with two distinct `OrganizationProvider` relationships (the ISP and AS 64500), two distinct interface relationships, the `customer_aggregate` prefix, and the `internet_prefixes` set
- [X] T053 [US6] Verify SC-003: transcribe every field of `../lab/wan/tenants.yml` against the new kinds — both tenants, hq and dr with their two different attachment kinds, the internet peering, and the branch as an `internal` tenant — then validate and load per T016's command sequence

**Checkpoint**: The largest domain by object count is modeled, including the two attachment kinds that normalize into one VPN and the branch office that is deliberately not a customer.

---

## Phase 9: User Story 7 - Provider and tenant services (Priority: P3)

**Goal**: The service kinds above US6 — the tenant L3VPN, the internet-access product a tenant either buys or does not, and the isolated tenant cloud coupling a fabric VRF, a firewall zone, and a subnet.

**Independent Test**: The difference between the lab's two WAN tenants is expressible purely as the presence or absence of one internet-access service — acme has one, globex does not — with no other field differing between them.

**Dependencies**: US1 (`ServiceGeneric`), US4 (`SecurityZone` for the tenant cloud), US6 (`WanTenant`, `WanCircuit`, `WanInternetPeering`).

### Tests for User Story 7 ⚠️

- [X] T054 [P] [US7] Extend `tests/unit/test_service_layer_schema_contract.py` asserting `ServiceL3vpn`, `ServiceInternetAccess`, and `ServiceTenantCloud` each inherit `ServiceGeneric` and `GeneratorTarget` but **not** `CoreArtifactTarget` — they render through device-scoped artifacts, not cluster manifests ([research.md](./research.md) R3)
- [X] T055 [P] [US7] Add assertions to `tests/unit/test_service_layer_schema_contract.py` that `ServiceL3vpn.tenant` is cardinality one and `circuits` cardinality many (FR-048), and that `ServiceTenantCloud` has all three of `vrf`, `zone`, and `prefix` as mandatory cardinality-one relationships (FR-047) — the coupling that makes a tenant's isolation structural
- [X] T056 [P] [US7] Add an assertion to `tests/unit/test_service_layer_schema_contract.py` that `ServiceInternetAccess` carries no attribute duplicating what `ServiceL3vpn` already holds, so the presence of the object is the only difference between a tenant that buys internet access and one that does not (SC-007, US7 acceptance scenario 3)

### Implementation for User Story 7

- [X] T057 [US7] Create `schemas/service/wan_services.yml` defining `ServiceL3vpn` per [data-model.md](./data-model.md) §11 — a mandatory `tenant`, optional `vrf`, the `circuits` set spanning member sites, and `dc_service_prefixes` for the shared half of the import policy
- [X] T058 [US7] Add `ServiceInternetAccess` to `schemas/service/wan_services.yml` with the two Boolean product flags and a mandatory `l3vpn` relationship
- [X] T059 [US7] Add `ServiceTenantCloud` to `schemas/service/wan_services.yml` with mandatory `tenant`, `vrf`, `zone`, and `prefix` relationships plus an optional `vlan`. This is the bridge between the provider edge and the fabric that `../lab/wan/tenants.yml` documents in its `dc:` block
- [X] T060 [US7] Verify SC-007 against `../lab/wan/tenants.yml` by comparing the acme and globex representations field by field and confirming the only difference is one `ServiceInternetAccess` object, then validate and load `schemas/service/wan_services.yml` per T016's command sequence

**Checkpoint**: All seven stories complete. Every domain of the lab has a modeled destination and the two-layer split holds across all four.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Whole-feature validation, the layering proof, and documentation

- [X] T061 Run the full layering proof from [quickstart.md](./quickstart.md) Step 5: `uv run infrahubctl branch create tech-only`, then `schema check` on the technical set only (`schemas/base schemas/kubernetes schemas/security schemas/wan schemas/organization_extensions.yml schemas/dcim_extensions.yml schemas/ipam_extensions.yml schemas/generator.yml`) and confirm zero errors — this is SC-009
- [X] T062 Confirm the reverse fails as designed: `uv run infrahubctl schema check schemas/service --branch tech-only` must report unresolvable peers (`KubernetesCluster`, `SecurityZone`, `WanTenant`), proving the dependency is one-way
- [X] T063 Run the convergence proof from [quickstart.md](./quickstart.md) Step 6: `schema load` followed by a second `schema check` reporting **no diff**. This is the alternative integration evidence the plan's Complexity Tracking offers in place of `$infrahub-run-integration-tests`, and it must be recorded in the pull request
- [X] T064 [P] Verify SC-008 across all four domains: `grep -rnE 'kind: (IPNetwork|IPHost)' schemas/kubernetes/ schemas/security/ schemas/wan/ schemas/service/` must return no hits
- [X] T065 [P] Verify the coupling count from [quickstart.md](./quickstart.md) Step 3: `grep -rln 'peer: ServiceGeneric' schemas/` must name only `schemas/service/service.yml`, and the occurrence count must be exactly 2
- [X] T066 Run the full local gate: `uv run pytest tests/unit`, then `uv run invoke lint` (ruff, mypy, yamllint, rumdl, Vale), and confirm zero unaddressed findings per Constitution IV
- [X] T067 Regenerate protocols one final time with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py` and confirm via `grep -nE 'class (ServiceFabricApp|ServiceAppAccess|ServiceL3vpn)\(' src/solution_arista_avd/protocols.py` that the artifact-target inheritance matches [research.md](./research.md) R3 — the first two list `CoreArtifactTarget`, `ServiceL3vpn` does not
- [X] T068 [P] Document the two layers in `docs/docs/developer-guide/schemas.md`, describing the technical/service split, the `GeneratorTarget` + `CoreArtifactTarget` inheritance contract, and the one-way dependency rule. Use relative Markdown links only, per the docs-sync constraints in AGENTS.md
- [X] T069 [P] Update `AGENTS.md` to record that the 7 new device roles are deliberately absent from `ROLE_TO_AVD_TYPE`, so the existing "When adding a device role" checklist is not applied to non-EOS roles ([research.md](./research.md) R7)
- [ ] T070 Obtain maintainer sign-off on the Principle IV exception recorded in `specs/010-lab-service-layer-model/plan.md` (Complexity Tracking) — either install `$infrahub-run-integration-tests` and run it, or accept the T061–T063 alternative in the pull request description

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — **blocks all seven stories**
- **US1 (Phase 3)** and **US2 (Phase 4)**: both depend only on Foundational, and are independent of each other — the MVP pair
- **US3 (Phase 5)**: depends on US1 + US2
- **US4 (Phase 6)**: depends on Foundational only
- **US5 (Phase 7)**: depends on US3 + US4
- **US6 (Phase 8)**: depends on Foundational only
- **US7 (Phase 9)**: depends on US1 + US4 + US6
- **Polish (Phase 10)**: depends on all desired stories

### Dependency graph

```text
Setup → Foundational ─┬─→ US1 ─┬─────────────→ US3 ──┬──→ US5 ──┐
                      │        │                     │          │
                      ├─→ US2 ─┘                     │          ├─→ Polish
                      │                              │          │
                      ├─→ US4 ───────────────────────┴──┐       │
                      │                                 ├───────┤
                      └─→ US6 ──────────────────→ US7 ──┘       │
                                        (US7 also needs US1+US4)┘
```

### Three independent tracks after Foundational

US1+US2, US4, and US6 have no dependency on one another. With three people they run
concurrently; US3, US5, and US7 then join them up.

### One shared-file caveat

`src/solution_arista_avd/protocols.py` is a **generated** file that every story's
checkpoint task regenerates (T016, T023, T030, T039, T045, T053, T060). Regeneration is
idempotent and last-run-wins, so sequential work is unaffected — but stories worked in
parallel must serialize that single task or accept that only the final regeneration is
meaningful. Never resolve a conflict in that file by hand; re-run the generator.

### Within each user story

1. Contract tests first — write them, confirm they FAIL
2. Schema YAML — nodes before the relationships that reference them
3. Lab transcription verification against the acceptance oracle
4. Validate → load → regenerate protocols → mypy

---

## Parallel Opportunities

### Phase 2 (Foundational)

```bash
# T004, T005 touch different files and can run together:
Task: "Write foundational contract test in tests/unit/test_lab_layers_foundation_schema_contract.py"
Task: "Create schemas/organization_extensions.yml defining OrganizationCustomer"
# T006 and T008 edit different existing files (dcim_extensions.yml, ipam_extensions.yml)
# and can also run in parallel with the above.
```

### Phase 4 (US2) — all three test tasks

```bash
Task: "Assert the three Kubernetes nodes and their fields"
Task: "Assert KubernetesNode.device peers the DcimGenericDevice generic"
Task: "Assert no IPNetwork/IPHost attribute appears in schemas/kubernetes/kubernetes.yml"
# All three extend one file, so in practice write them in one pass; they are
# marked [P] because they are independent assertions with no ordering between them.
```

### Phase 6 (US4) — four independent assertion groups

```bash
Task: "Assert the six security nodes and SecurityZone.device"
Task: "Assert SecurityAddress references IPAM and groups nest"
Task: "Assert SecurityPolicy and SecurityPolicyRule uniqueness and ordering"
Task: "Assert the action dropdown and the managed_by_service guard"
```

### Cross-story parallelism

```bash
# After Foundational, three tracks in parallel:
Developer A: US1 (T011-T016) then US2 (T017-T023)
Developer B: US4 (T031-T039)
Developer C: US6 (T046-T053)
```

---

## Implementation Strategy

### MVP: User Stories 1 and 2

Both are P1 and the MVP is the pair, not US1 alone. `ServiceGeneric` on its own delivers
an abstraction with nothing in it; the Kubernetes layer on its own delivers a model with
no intent above it. Together they demonstrate the two-layer pattern the request asks for
against the domain the request names first.

1. Phase 1: Setup (T001–T003)
2. Phase 2: Foundational (T004–T010) — blocks everything
3. Phase 3: US1 (T011–T016)
4. Phase 4: US2 (T017–T023)
5. **STOP and VALIDATE**: `ServiceGeneric` is queryable; the cluster, its 3 nodes, and its 2 peerings load; each peering resolves to a real fabric `DcimDevice`
6. Demo: the cluster's BGP contract with the fabric, in the same graph as the leaves it peers with

### Incremental delivery

| Increment | Adds | Demonstrable outcome |
| --- | --- | --- |
| Foundational | Shared dropdowns + `OrganizationCustomer` | Nothing user-visible; unblocks everything |
| US1 + US2 (MVP) | Service abstraction + Kubernetes domain | "What services exist?" answerable; cluster is a modeled routing peer |
| US3 | The two Crossplane-bound service kinds | A `FabricApp` is one Infrahub object; artifact-ready |
| US4 | The firewall, in full | The one device with no model has one; Infrahub is its source of truth |
| US5 | Access grants | "This person may use that application" is one reviewable object |
| US6 | ISP, tenants, sites, branch | `wan/tenants.yml` has a modeled destination for every field |
| US7 | WAN services | acme and globex differ by exactly one object |

Each increment is loadable and leaves the repository valid.

### Sequencing advice

Do **US4 before US5** and **US6 before US7** — the dependency is hard, not stylistic.
If time is short, US4 is the highest-value single story after the MVP: it is the only
domain in the lab with no model at all, and it is the enforcement point every other
domain routes through.

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks
- Each contract test file defines its own local `_load_yaml` / `_node` / `_attributes` /
  `_relationships` / `_choice_names` helpers, following the four existing
  `test_*_schema_contract.py` files. This duplicates helpers across files and is
  deliberate: Constitution V requires following established structure, and the plan
  lists exactly four new test files with no shared helper module
- Every schema file starts with the `# yaml-language-server: $schema=...` comment and
  `version: "1.0"`
- Attributes are mandatory by default; relationships are optional and default to
  cardinality `many`. Set `cardinality: one` explicitly wherever the data model says one
- `src/solution_arista_avd/protocols.py` is generated — regenerate, never hand-edit,
  even to satisfy mypy
- The seven limitations no schema constraint can express are catalogued in
  [data-model.md](./data-model.md) §13 and belong to a later `checks/` cycle. Do not
  attempt to encode them as schema constraints
- Commit after each task or logical group; stop at any checkpoint to validate a story
  independently
