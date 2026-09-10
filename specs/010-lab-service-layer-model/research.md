# Phase 0 Research: Technical and Service Layers for the Full NFD41 Lab

**Feature**: `specs/010-lab-service-layer-model` | **Date**: 2026-09-10

Fourteen decisions. Each was resolved against the `infrahub-managing-schemas` reference
material, the repository's existing schema, the lab at `../lab`, or the two OpsMill
reference repositories. No NEEDS CLARIFICATION items remain.

---

## R1 — Namespace allocation

**Decision**: Four new namespaces — `Service`, `Kubernetes`, `Security`, `Wan` — plus an
extension to the existing `Organization` namespace.

**Rationale**: All four satisfy the namespace pattern `^[A-Z][a-z0-9]+$` with a 3–32
character length: `Service` (7), `Kubernetes` (10), `Security` (8), `Wan` (3, at the
minimum but valid). None collides with an Infrahub-reserved namespace — the reserved set
visible in the regenerated protocols is `Core`, `Internal`, `Builtin`, `Lineage`,
`Profile`, `Template`, and `Ipam` — nor with any of the repository's existing eleven
(`Avd`, `Cloudvision`, `Compute`, `Dcim`, `Evpn`, `Generator`, `Interface`, `Ipam`,
`Location`, `Mlag`, `Network`, `Organization`, `Routing`, `Virtualization`).

`Security` deliberately matches `opsmill/infrahub-demo-dc`, which uses the same
namespace for zones, address objects, address groups, services, and policies. Keeping
the name identical means the two repositories' security models can be compared and
patterns lifted between them.

**Alternatives considered**:

- *Fold everything into `Network`* — rejected. `NetworkTenant` would sit beside
  `EvpnTenant` (a fabric EVPN tenant) and `NetworkFabric`/`NetworkPod`/`NetworkLink`
  (fabric building blocks), overloading a namespace that currently means "fabric
  topology". See R9.
- *`K8s` instead of `Kubernetes`* — rejected. `K8s` fails `^[A-Z][a-z0-9]+$`? It does
  technically match (`K` + `8s`), but the kind `K8sCluster` reads worse than
  `KubernetesCluster` and abbreviation buys nothing in a graph browsed by name.
- *`Firewall` instead of `Security`* — rejected. The address book, service objects, and
  policies are not firewall-specific concepts, and `demo-dc` already settled on
  `Security` for exactly this set.

---

## R2 — How a generator "sits underneath" a service

**Decision**: Every concrete service kind inherits the project's existing
`GeneratorTarget` generic (`schemas/generator.yml`), and a later cycle registers a
`generator_definitions` entry in `.infrahub.yml` targeting a `CoreStandardGroup` whose
members are those service objects.

**Rationale**: This is the mechanism the repository already uses. `GeneratorTarget` is a
one-attribute generic carrying `checksum: Text (optional)`, and `NetworkPod`,
`LocationRack`, and `ComputePhysicalServer` all inherit it. Generator definitions in
`.infrahub.yml` target group names (`fabrics`, `pods`, `racks`, `avd_devices`,
`servers`, `avd_structured_configs`) declared in `objects/00_groups.yml`. The `checksum`
attribute is what Constitution II's "checksum-based change detection" and
`GeneratorMixin.calculate_checksum()` operate on, so inheriting it is not decoration —
it is the idempotence contract.

The schema's whole obligation for spec FR-081 is therefore satisfied by one
`inherit_from` entry per service kind. No new generic is needed.

**Alternatives considered**:

- *A new `ServiceTarget` generic* — rejected as duplication. `GeneratorTarget` already
  means "a node a generator runs against".
- *Relying on the group alone without `GeneratorTarget`* — rejected. A generator can
  target a group of nodes lacking `checksum`, but then every run does full work and the
  idempotence principle has no field to hang on.

---

## R3 — How a service becomes an artifact target for Crossplane rendering

**Decision**: The three service kinds whose intent is delivered to the cluster —
`ServiceFabricPeering`, `ServiceFabricApp`, `ServiceAppAccess` — additionally inherit
`CoreArtifactTarget`.

**Rationale**: `CoreArtifactTarget` is Infrahub's built-in generic marking a node as
something an artifact definition can render against. The repository uses it on
`DcimDevice` (`schemas/base/dcim.yml`) and `NetworkFabric`
(`schemas/logical_design.yml`), and every entry under `artifact_definitions:` in
`.infrahub.yml` targets a group of such nodes. Adding it now means the later Crossplane
cycle registers a transform and an artifact definition without a schema change —
satisfying spec FR-083 at zero cost, since the generic contributes no attributes the
user sees.

Multiple inheritance combining this with `GeneratorTarget` and `ServiceGeneric` is
supported and already in use: `ComputePhysicalServer` inherits four generics and
`DcimDevice` inherits three including `CoreArtifactTarget`.

The delivery path itself follows `opsmill/infrahub-dogfooding`, confirmed with the
requester: a Python transform renders each object into a Crossplane manifest stored as
an Infrahub artifact, and the Vidra operator (`integration/vidra/vidra-config.yml`,
driven by an `artifacts_query`) pulls and reconciles them in-cluster.

**Alternatives considered**:

- *Add `CoreArtifactTarget` to every service kind* — rejected. `ServiceL3vpn`,
  `ServiceInternetAccess`, and `ServiceTenantCloud` render FRR and EOS configuration
  through device-scoped artifacts, not cluster manifests; marking them as artifact
  targets would imply a per-service artifact that will never exist.
- *Defer `CoreArtifactTarget` to the transform cycle* — rejected. It would force a
  second schema migration and a second protocol regeneration for a one-line change.

---

## R4 — Where user-defined structured content lives

**Decision**: `JSON` attributes for content whose shape is defined by the user or by an
upstream chart — Helm values, raw manifests, label selectors, BGP timers. Discrete
attributes or relationships for everything with a fixed shape.

**Rationale**: The `FabricApp` composite resource accepts
`chart.values` and `manifests` as `x-kubernetes-preserve-unknown-fields`, and
`serviceSelector` / `advertisementSelector` / `nodeSelector` as free-form string maps.
There is no fixed schema to model, and modeling one would reject valid input. Infrahub's
`JSON` attribute kind is the right container, and the repository already uses it for
exactly this purpose: `DcimDevice.avd_custom_hostvars` is a `JSON` attribute holding
"device-scope custom pyAVD hostvars".

Everything else in those resources — `localASN`, `namespace`, `tenant`, `vipBlock`,
`defaultDeny`, `allowDNS`, port numbers — has a fixed shape and becomes a typed
attribute or a relationship, so it is queryable and validatable.

**Migration path noted**: the lab's `apps/10-demo.yaml` carries roughly 200 lines of raw
manifests. A `JSON` attribute holds that comfortably, but if manifest payloads grow, the
repository's own precedent for large generated content is a `CoreFileObject` child —
`AvdHostvarFile` and `AvdStructuredConfigFile` both inherit it and hang off
`AvdArtifact` via a `Component` relationship. That is the documented escape hatch, not
this cycle's design.

**Alternatives considered**:

- *Model Kubernetes manifests as first-class nodes* — rejected. It reimplements the
  Kubernetes API inside Infrahub and breaks on the first CRD the model has not seen.
- *`TextArea` holding YAML* — rejected. `JSON` is validated on write; a YAML string is
  not, and a malformed value would surface only at render time.

---

## R5 — Prefixes and addresses

**Decision**: Every network and address a new node needs is a relationship to
`IpamPrefix` or `IpamIPAddress`. No `IPNetwork` or `IPHost` attribute is used for a
network that any other object also references.

**Rationale**: This is the failure mode the feature exists to remove. The lab has three
independent enforcement points matching on the same networks — the leaves' `RM-CILIUM-IN`
route policy, the vSRX zone policies, and the Cilium network policies — and today each
restates the CIDR as text in a different file. `10.112.240.0/24` appears in
`avd/group_vars/`, in `wan/tenants.yml` as `dc_service_prefixes`, in `junos.conf` as the
`k8s-services` address-book entry, and in `crossplane/apps/10-demo.yaml`. Making them
relationships to one `IpamPrefix` object is what turns "these four should agree" into a
graph fact.

Infrahub's IPAM handles prefix nesting natively, so a per-application VIP block
(`10.112.240.0/28`) is an `IpamPrefix` whose parent is the service range
(`10.112.0.0/16`); the containment does not need modeling by hand.

The repository already has `schemas/ipam_extensions.yml` adding a `role` dropdown to
`IpamPrefix`, so new prefix roles (`pod`, `service`, `vip_pool`, `wan_customer`,
`branch_lan`, `tenant_cloud`) are an extension to an existing dropdown rather than a new
kind.

**Alternatives considered**:

- *`IPNetwork` attributes* — rejected for shared networks; retained only where a value
  is genuinely local to one object and referenced by nothing else.
- *Free-text CIDR with a validation regex* — rejected outright. It is the current state
  and the problem.

---

## R6 — Cross-file back-references to DCIM

**Decision**: The `device_services` relationship on `DcimGenericDevice` and the
`interface_services` relationship on `DcimInterface` are declared in an `extensions:`
block inside `schemas/service/service.yml`, not by editing `schemas/base/dcim.yml`.

**Rationale**: The `extension-cross-file` rule is explicit — use `extensions` for
relationships to nodes you do not own, to avoid a circular dependency between schema
files. `schemas/base/dcim.yml` is base schema; adding a `peer: ServiceGeneric`
relationship to it would make the base layer depend on the service layer and break spec
SC-009 (the technical layer must load standalone). Placing the extension in the service
file keeps the dependency one-way. `opsmill/infrahub-demo-dc` does exactly this in
`schemas/extensions/service/service.yml`.

Both sides use matching `identifier` values (`device_services`, `interface_services`) per
the `relationship-identifiers` rule, and both use `on_delete: no-action` so deleting a
service never cascades into a device.

Peer choice: `DcimInterface` is the *generic* in this repository (with
`InterfacePhysical` and `InterfaceVirtual` as the concrete nodes), so peering the generic
covers both without enumerating them.

**Alternatives considered**:

- *Edit `schemas/base/dcim.yml` directly* — rejected; violates the constitution's
  "Schema extensions MUST be used to add relationships to existing base nodes".
- *Omit the back-references* — rejected. Without them a device's page cannot answer
  "what services touch this device", which is US1's third acceptance scenario.

---

## R7 — Device roles for non-EOS devices (and the trap in the AVD role map)

**Decision**: Add seven roles to the existing `DcimDevice.role` dropdown in
`schemas/dcim_extensions.yml` — `firewall`, `isp_edge`, `isp_core`, `internet_edge`,
`customer_edge`, `branch_router`, `k8s_node` — and **do not** add any of them to
`ROLE_TO_AVD_TYPE`.

**Rationale and the trap**: `src/solution_arista_avd/avd.py:78` raises
`ValueError(f"Unknown device role: {role}")` for any role absent from
`ROLE_TO_AVD_TYPE`. If a non-EOS device reached the AVD hostvar generator, generation
would fail hard. Tracing the call path shows this is safe under one condition:

- `get_avd_type` is called from exactly one place, `generators/generate_avd_device_hostvar.py:2556`.
- That generator is registered in `.infrahub.yml` with `targets: avd_devices`.
- Membership of `avd_devices` is set in one place,
  `src/solution_arista_avd/generator.py:893`, on the device-creation path the fabric and
  rack generators run from device designs.

So a manually loaded vSRX, ISP PE, CE router, or k3s node never joins `avd_devices` and
is never passed to `get_avd_type`. The invariant to preserve is therefore: **new roles
stay out of `ROLE_TO_AVD_TYPE`, and non-EOS devices stay out of `avd_devices`.** This
inverts the AGENTS.md "adding a device role" checklist, whose steps 3–5 assume the role
is an AVD switch role — that checklist applies to fabric roles, not to these.

The firewall is currently absent from DCIM entirely: `objects/28_nfd41_endpoints.yml`
models the *border-leaf interfaces facing it* (with descriptions such as
`FW1_ge-0/0/0_ZONE-K8S-PROD`) but no `fw1` device exists. The vSRX must be created as a
`DcimDevice` before any `SecurityZone` can relate to it, which makes this an object-cycle
prerequisite recorded in the data model.

**Alternatives considered**:

- *A separate `SecurityFirewall` device kind* — rejected. It would duplicate
  `DcimGenericDevice`'s interfaces, addresses, and cabling, and the lab's border-leaf
  links already terminate on interfaces that need a device on the far end.
- *Add the roles to `ROLE_TO_AVD_TYPE` mapped to something inert* — rejected. It would
  make a non-EOS device silently renderable as EOS, which is worse than a loud failure.

---

## R8 — Where a WAN tenant's identity lives

**Decision**: Add `OrganizationCustomer` (a concrete node inheriting
`OrganizationGeneric`) in a new `schemas/organization_extensions.yml`. `WanTenant` holds
the provider-edge construct — VRF, route-table id, policy — and relates to an
`OrganizationCustomer` for identity.

**Rationale**: `ServiceGeneric.owner` peers `OrganizationGeneric` (spec FR-040), which is
a generic and cannot be instantiated. The repository's only concrete organization kinds
are `OrganizationManufacturer` and `OrganizationProvider`, neither of which describes
acme or globex. Without a customer kind, `owner` has nothing to point at and the
service layer's ownership requirement is unsatisfiable.

Separating identity from edge construct matters because the lab's own data model makes
the point: `wan/tenants.yml` says "a tenant gets one VRF on the PE, one identity, one
policy" and warns that conflating tenant and site "is what makes multi-site customers
painful later". The same separation applies one level up — acme the company is not
`CUST_ACME` the VRF.

The ISP and the internet autonomous system reuse `OrganizationProvider`, which already
exists, per spec FR-006.

**Alternatives considered**:

- *Reuse `OrganizationProvider` for tenants* — rejected; inverts the relationship. A
  tenant buys from a provider.
- *Put customer identity on `WanTenant` itself* — rejected. `ServiceGeneric.owner` needs
  an `OrganizationGeneric`, and a tenant-cloud service owned by acme should resolve to
  the same object as an L3VPN owned by acme.

---

## R9 — `WanTenant` versus the existing `EvpnTenant`

**Decision**: Keep both. They are different concepts. `WanTenant` relates to the
`IpamVRF` and `EvpnTenant` on the fabric side where a tenant has cloud resources.

**Rationale**: `EvpnTenant` is the fabric's EVPN tenant — the repository already has
four (`TENANT_K8S`, `TENANT_APP`, `TENANT_CLOUD`, `TENANT_EXTERNAL`, per
`objects/24_nfd41_tenants.yml`) and they group VRFs for EVPN route-target allocation.
`WanTenant` is a provider-edge customer with a VRF on `isp-pe1`. acme is one
`WanTenant` and has no `EvpnTenant` of its own — its cloud subnet lives in the
`TENANT_CLOUD` EVPN tenant's `TENANT_ACME` VRF. Merging them would force either the
fabric's EVPN grouping or the provider's customer isolation to bend.

The bridge is `ServiceTenantCloud`, which relates a `WanTenant` to the `IpamVRF` and
`SecurityZone` that give it presence in the datacentre — exactly the coupling
`wan/tenants.yml` documents in its `dc:` block.

**Alternatives considered**:

- *One unified `Tenant` kind* — rejected; would require the fabric's four EVPN tenants
  and the provider's two customers to be the same list, which they are not.

---

## R10 — The branch office, which is deliberately not a customer

**Decision**: Model the branch as a `WanTenant` carrying a `kind` dropdown set to
`internal`, with one `WanSite` and a `WanCircuit` terminating on the border leaf rather
than on a PE.

**Rationale**: The lab is emphatic — "The branch office is deliberately not a customer.
It has a private circuit into border-leaf1 and never touches the ISP, so it is a
different trust level." The model must honour that without inventing a parallel
structure for a site, a LAN, a router, and three hosts, all of which `WanSite` and
`WanCircuit` already describe.

A `kind: customer | internal` dropdown on `WanTenant` records the trust distinction as
data, keeps the `["tenant", "name__value"]` uniqueness constraint on `WanSite` intact
(spec FR-074), and lets a query separate paying customers from internal sites. The
circuit's provider-edge side peers `DcimInterface` generally rather than a
PE-specific kind, so terminating on `border-leaf1` needs no special case.

This resolves the spec's edge case "the branch office, which is deliberately neither a
WAN tenant nor a fabric tenant, without forcing it into either shape".

**Alternatives considered**:

- *Make `WanSite.tenant` optional* — rejected. It weakens the uniqueness constraint for
  every site to accommodate one, and leaves "which sites have no tenant" as the only way
  to find the branch.
- *A separate `WanBranch` kind* — rejected. Duplicates `WanSite` and `WanCircuit` to
  encode one boolean.

---

## R11 — Schema file layout and load order

**Decision**: Nine files in per-domain directories under `schemas/`, plus two
root-level extension files. Load order is irrelevant within one `infrahubctl schema
load schemas` invocation.

**Rationale**: `infrahubctl schema load schemas` loads a directory recursively and
resolves cross-file references across the whole batch, so `peer: KubernetesCluster` in
`schemas/service/kubernetes_services.yml` resolves regardless of filename ordering. The
project loads schemas explicitly via `invoke load-schema` rather than declaring them in
`.infrahub.yml`, so there is no repository-sync ordering concern either.

What does matter is the *dependency direction*: service files name technical kinds, and
technical files name no service kind (spec FR-080). That makes `schemas/kubernetes/` +
`schemas/security/` + `schemas/wan/` loadable as a set without `schemas/service/`,
which is spec SC-009 and is directly testable.

Per-domain directories match the existing convention — `schemas/avd/`, `schemas/base/`,
`schemas/compute/`, `schemas/cv/`, `schemas/evpn/`, `schemas/lag/`, `schemas/mlag/`,
`schemas/routing/`, `schemas/vlan/`, `schemas/vrf/`. Root-level `*_extensions.yml` files
match `dcim_extensions.yml`, `ipam_extensions.yml`, `l3ls_extensions.yml`, and
`location_extensions.yml`.

**Alternatives considered**:

- *One file per user story (7 files, flat)* — rejected; puts `security.yml` and
  `wan.yml` at the same level as the fabric's `logical_design.yml`, losing the domain
  grouping the rest of `schemas/` uses.

---

## R12 — Menu placement

**Decision**: New nodes set `include_in_menu`, `label`, and `icon`, but **not**
`menu_placement`. Placement is deferred to the menu cycle, which owns `menus/menu.yml`.

**Rationale**: `menus/menu.yml` in this repository is the single authority for menu
structure — it defines eight top-level groups by namespace (`Network`, `Dcim`, `Ipam`,
`Routing`, `Evpn`, `Location`, `Compute`) and assigns kinds to them. Setting
`menu_placement` in the schema would create a second, competing placement mechanism.

Note that `opsmill/infrahub-demo-dc`'s `security.yml` sets `menu_placement: SecurityZone`
on its own `Zone` node — a node placing itself under itself. That is not a pattern to
copy.

Spec FR-065 ("service nodes MUST be placed beneath a service grouping") is therefore
satisfied at the menu cycle; the schema's contribution is to be menu-capable.

**Alternatives considered**:

- *Set `menu_placement` now* — rejected per above.
- *`include_in_menu: false` on everything* — rejected. The lab's operators need these
  objects browsable, and the fabric's own user-facing kinds are all `true`.

---

## R13 — Infrahub 1.10.6 capability check

**Decision**: No feature outside Infrahub 1.10.6's capabilities is required.

**Rationale**: The design uses multiple inheritance (in use: `ComputePhysicalServer`
inherits four generics), `JSON` attributes (in use: `DcimDevice.avd_custom_hostvars`),
`Dropdown` with `choices` (in use throughout), `Component`/`Parent` pairs (in use:
`AvdArtifact` → `AvdHostvarFile`), relationship `on_delete: no-action` (in use:
`schemas/dci.yml` and demo-dc's service extensions), composite
`uniqueness_constraints` mixing attributes and relationships (in use: `AvdArtifact` uses
`[device, name__value]`), and `human_friendly_id` traversing relationships (in use:
`AvdHostvarFile` uses `artifact__name__value`). Nothing is hierarchical, so no
`hierarchical: true` generic is needed — the location tree that pattern exists for is
already modeled in `schemas/location_extensions.yml`.

The constitution pins `INFRAHUB_BASE_VERSION=1.10.6` and `infrahubctl info` confirmed a
live 1.10.6 server with SDK 1.22.0 during the specify cycle.

**Alternatives considered**: none required.

---

## R14 — Validation approach

**Decision**: Four `tests/unit/test_*_schema_contract.py` suites that parse the schema
YAML and assert the spec's functional requirements, plus live `infrahubctl schema check`
and `schema load` on a feature branch, plus protocol regeneration under `mypy`.

**Rationale**: The repository has an established and well-suited pattern for this —
`test_dci_schema_contract.py`, `test_fabric_pool_schema_contract.py`,
`test_evpn_gateway_schema_contract.py`, `test_l2ls_services_schema_contract.py`, and
`test_avd_example_fabrics_schema_contract.py` all load YAML with `yaml.safe_load` and
assert node presence, attribute kinds, relationship cardinality, dropdown choices, and
uniqueness-constraint shape. Helper functions (`_node`, `_attributes`,
`_relationships`, `_choice_names`) are already written in each and can be mirrored.

This matters for two reasons. It makes the FRs executable — `test_service_layer_...` can
assert FR-080 by walking every technical file and failing on any `peer:` beginning with
`Service`, which no server-side check would catch. And it keeps the quality gate
satisfiable without the missing `$infrahub-run-integration-tests` skill (see the plan's
Complexity Tracking).

Server-side validation still runs, because a contract test cannot catch a "peer not
found" or an identifier mismatch across files: `infrahubctl schema check schemas/`
returns both a validation result and a diff, and a second `schema check` after
`schema load` proves the load converged.

**Alternatives considered**:

- *Live validation only* — rejected. It cannot assert layering direction, and it is
  unavailable in CI.
- *Contract tests only* — rejected. YAML parsing cannot resolve cross-file peers or
  validate against Infrahub's Pydantic models.

---

## Resolved risks

| Risk | Resolution |
| --- | --- |
| A non-EOS device role reaching `get_avd_type` and raising `ValueError` | R7 — roles stay out of `ROLE_TO_AVD_TYPE`; membership of `avd_devices` is set in exactly one code path that these devices never take |
| The firewall device not existing, leaving `SecurityZone` with nothing to relate to | R7 — recorded as an object-cycle prerequisite; `fw1` must be loaded as a `DcimDevice` with role `firewall` |
| `ServiceGeneric.owner` peering a generic with no instantiable concrete kind | R8 — `OrganizationCustomer` added |
| Technical files accidentally depending on service files, breaking SC-009 | R6 places the DCIM back-references in the service file; R14 makes the direction an executable assertion |
| `EvpnTenant` and `WanTenant` being conflated | R9 — kept separate, bridged by `ServiceTenantCloud` |
| Manifest payloads outgrowing a `JSON` attribute | R4 — documented `CoreFileObject` migration path, following `AvdHostvarFile` |
