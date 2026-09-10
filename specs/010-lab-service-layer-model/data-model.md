# Phase 1 Data Model: Technical and Service Layers for the Full NFD41 Lab

**Feature**: `specs/010-lab-service-layer-model` | **Date**: 2026-09-10

> **⚠️ Superseded in part by marketplace adoption.** This document describes the
> technical layer as originally designed, before `opsmill/schema-library` and the
> Infrahub Marketplace were consulted. Four domains were subsequently replaced by
> published schemas pulled with `infrahubctl marketplace get`:
>
> | Originally designed here | Now adopted |
> | --- | --- |
> | `SecurityZone`, `SecurityAddress`, `SecurityAddressGroup`, `SecurityApplication`, `SecurityPolicy`, `SecurityPolicyRule` | `infrahub/security` (22 kinds), plus `schemas/security_extensions.yml` for `trust_level`, `vrf` and `managed_by_service` |
> | `KubernetesCluster`, `KubernetesNode`, `KubernetesFabricPeering` | `infrahub/cluster` + authored `ClusterKubernetes` / `ClusterFabricPeering`; cluster members are `ComputeGenericUnit` objects, so there is no node kind |
> | `WanCircuit` | `infrahub/circuit` (`DcimCircuit` + `DcimCircuitEndpoint`) |
> | `OrganizationCustomer` | `infrahub/tenancy` (`OrganizationTenant`) |
>
> The **service layer is unchanged** — nothing in the marketplace covers it. The layering
> contract, the two-layer split, and every requirement about IPAM references and delete
> behaviour still hold.
>
> Current state of record: **`schemas/MARKETPLACE.md`** and the contract tests under
> `tests/unit/test_{security,cluster,wan,service_layer,lab_layers_foundation}_schema_contract.py`.


3 generics, 26 nodes, 4 new namespaces, 1 extended dropdown. Conventions throughout:
attributes are mandatory by default and relationships optional by default; `order_weight`
follows the project convention (900–999 primary relationships, 1000–1099 identifiers,
1100–1499 secondary, 1500–1999 tertiary, 2000+ metadata, 3000+ tags); every
`Component`/`Parent` pair shares an `identifier`; every relationship from a service to a
technical object uses `on_delete: no-action`.

The `Legend` for each table: **Kind** is the attribute kind or the relationship peer;
**Card** is cardinality; **Opt** is whether it is optional.

---

## 1. Prerequisites (object cycle, not this cycle)

Three things must exist as data before the new nodes have anything to relate to. They
are not schema work but they gate the acceptance scenarios:

| Prerequisite | Why | Source |
| --- | --- | --- |
| `fw1` as a `DcimDevice` with role `firewall` | `SecurityZone.device` is mandatory; the firewall is currently absent from DCIM | R7 |
| ISP, CE, internet and branch routers as `DcimDevice` with the new roles | `WanCircuit` needs a device on each end | R7 |
| The k3s nodes as `DcimDevice` or `ComputePhysicalServer` | `KubernetesNode.device` is mandatory | R7 |

---

## 2. Extension: `schemas/organization_extensions.yml`

### `OrganizationCustomer` (node)

Identity of a paying tenant, separate from the provider-edge construct that serves it
(R8). Inherits `OrganizationGeneric`, so it can be a `ServiceGeneric.owner`.

- `inherit_from: [OrganizationGeneric]`
- `icon: mdi:domain`, `include_in_menu: true`
- HFID, `display_label`, and `order_by` are **inherited** — `OrganizationGeneric`
  already sets `human_friendly_id: [name__value]`, `display_label: name__value`, and
  `order_by: [name__value]`, so redeclaring them is unnecessary. Same for uniqueness:
  the inherited `name` is already `unique: true`.

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| *(inherited)* | | | `OrganizationGeneric` supplies `name` (`unique: true`), `description`, and a `tags` relationship |
| `account_reference` | Text | yes | External billing or CRM key; `order_weight: 1100` |

---

## 3. Extension: `schemas/dcim_extensions.yml` (modified)

Seven roles appended to the existing `DcimDevice.role` dropdown. **None is added to
`ROLE_TO_AVD_TYPE`** (R7).

| Choice | Label | Description |
| --- | --- | --- |
| `firewall` | Firewall | Perimeter security device; not an AVD-rendered node |
| `isp_edge` | ISP Edge (PE) | Customer-facing provider edge, holds a VRF per tenant |
| `isp_core` | ISP Core | Provider core; default VRF transit, hands off to the border leaf |
| `internet_edge` | Internet Edge | The internet autonomous system's border router |
| `customer_edge` | Customer Edge (CE) | Tenant-side router on an attachment circuit |
| `branch_router` | Branch Router | Branch office router with an integrated switched LAN |
| `k8s_node` | Kubernetes Node | Cluster member; may also be a `ComputePhysicalServer` |

Note the existing `pe` role means *MPLS provider edge in an AVD-rendered ISIS-LDP
fabric* and is mapped in `ROLE_TO_AVD_TYPE`. `isp_edge` is the FRR-rendered lab ISP and
is deliberately a different value.

---

## 4. Extension: `schemas/ipam_extensions.yml` (modified)

Six roles appended to the existing `IpamPrefix.role` dropdown, so every prefix the new
nodes reference carries its purpose (R5).

| Choice | Label | Example from the lab |
| --- | --- | --- |
| `pod` | Pod CIDR | `10.111.0.0/16` |
| `service` | Service CIDR | `10.112.0.0/16` |
| `vip_pool` | LoadBalancer VIP Pool | `10.112.240.0/24`, and `/28` blocks within it |
| `wan_customer` | WAN Customer LAN | `10.60.10.0/24`, `10.60.11.0/24`, `10.60.20.0/24` |
| `branch_lan` | Branch LAN | `10.70.0.0/24` |
| `tenant_cloud` | Tenant Cloud Subnet | `10.220.10.0/24`, `10.220.20.0/24` |

---

## 5. Service layer: `schemas/service/service.yml`

### `ServiceGeneric` (generic) — US1

The abstraction the whole layer turns on. Every concrete service inherits it, so one
query answers "what services exist, who owns them, what state are they in" (SC-006).

- `include_in_menu: false` (concrete kinds appear; the generic is the query surface)
- `human_friendly_id: [name__value]`, `display_label: "{{ name__value }}"`, `order_by: [name__value]`
- `uniqueness_constraints: [["name__value"]]` (FR-070)

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `unique: true`, `order_weight: 1000`. Branch-**aware** (the default) — see note |
| `description` | Text | yes | `order_weight: 1100` |
| `status` | Dropdown | no | `default_value: provisioning`, `order_weight: 1200`. Choices below |
| `checksum` | Text | yes | Inherited from `GeneratorTarget`, not redeclared — listed here for clarity |

`status` choices (FR-020) — a pre-deployment, an active, and a decommissioning state at
minimum, following `opsmill/infrahub-demo-dc`'s `ServiceGeneric`:

| Choice | Label | Meaning | Color |
| --- | --- | --- | --- |
| `provisioning` | Provisioning | Ordered; the generator has not yet materialized it | `#ffff7f` |
| `active` | Active | Materialized and in service | `#7fbf7f` |
| `error` | Error | The generator ran and failed — distinct from `provisioning`, which is the spec's edge case about telling the two apart | `#ff7f7f` |
| `decommissioning` | Decommissioning | Being withdrawn | `#fbfbfb` |
| `decommissioned` | Decommissioned | Withdrawn | `#bfbfbf` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `owner` | `OrganizationGeneric` | one | no | `kind: Generic`, `on_delete: no-action`, `order_weight: 900` (FR-040) |

**Note on branch behaviour.** `opsmill/infrahub-demo-dc` marks its `ServiceGeneric.name`
`branch: agnostic`. This design deliberately does not. A branch-agnostic attribute is
global — a change on a branch takes effect everywhere immediately — which would bypass
the proposed-change review that AGENTS.md requires of every service workflow ("every
workflow should operate on an Infrahub branch and produce a proposed change for
review"). Leaving `name` branch-aware, the default, keeps ordering a service and
reviewing it the same operation.

### `ServiceGenericDevice` (generic) — US1

Binding generic: lets a service attach to the devices that realize it.
`include_in_menu: false`.

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `devices` | `DcimGenericDevice` | many | yes | `identifier: device_services`, `direction: inbound`, `on_delete: no-action`, `order_weight: 1000` |

### `ServiceGenericInterface` (generic) — US1

Binding generic for interface-scoped services. `include_in_menu: false`.

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `interfaces` | `DcimInterface` | many | yes | `identifier: interface_services`, `on_delete: no-action`, `order_weight: 1000` |

### Extensions block (same file) — FR-052, R6

| Extended kind | Relationship | Peer | Card | Notes |
| --- | --- | --- | --- | --- |
| `DcimGenericDevice` | `device_services` | `ServiceGeneric` | many | `identifier: device_services`, `direction: outbound`, `on_delete: no-action`, `optional: true` |
| `DcimInterface` | `interface_services` | `ServiceGeneric` | many | `identifier: interface_services`, `on_delete: no-action`, `optional: true` |

This block is the **only** place the technical layer learns the service layer exists,
and it lives in a service file — which is what keeps FR-080 true and SC-009 testable.

---

## 6. Kubernetes technical layer: `schemas/kubernetes/kubernetes.yml` — US2

### `KubernetesCluster` (node)

- `inherit_from: [GeneratorTarget]`
- `human_friendly_id: [name__value]`, `display_label: name__value`, `order_by: [name__value]`
- `uniqueness_constraints: [["name__value"]]`
- `icon: mdi:kubernetes`, `label: Kubernetes Cluster`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `unique: true`, `order_weight: 1000`. Lab: `nfd41` |
| `description` | Text | yes | `order_weight: 1100` |
| `distribution` | Dropdown | no | `default_value: k3s`. Choices `k3s`, `k8s`, `rke2`, `openshift`, `eks`, `gke`, `aks`. `order_weight: 1200` |
| `kubernetes_version` | Text | yes | `order_weight: 1300`. Lab: `v1.31.3` |
| `cni_kind` | Dropdown | no | `default_value: cilium`. Choices `cilium`, `calico`, `flannel`, `other`. `order_weight: 1400` |
| `cni_version` | Text | yes | `order_weight: 1500`. Lab: `1.18.6` |
| `local_asn` | Number | yes | `parameters: {min_value: 1, max_value: 4294967295}`, `order_weight: 1600`. Lab: `65401` (FR-021) |
| `bgp_auth_secret_name` | Text | yes | `order_weight: 1700`. Lab: `nfd41-bgp-auth`. The secret's *name*, never its value |
| `pod_cidr_communities` | List | yes | `order_weight: 1800`. Lab: `["65401:110"]` |
| `bgp_timers` | JSON | yes | `order_weight: 1900`. Lab: connect-retry 5, hold 9, keepalive 3 (R4) |
| `node_selector` | JSON | yes | `order_weight: 2000`. Which nodes run a BGP speaker. Lab: `{"nfd41.lab/bgp": "true"}` |
| `advertisement_selector` | JSON | yes | `order_weight: 2010`. Lab: `{"nfd41.lab/advertise": "fabric"}` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `pod_prefix` | `IpamPrefix` | one | no | `kind: Attribute`, `identifier: cluster__pod_prefix`, `order_weight: 900`. Lab: `10.111.0.0/16` (FR-022) |
| `service_prefix` | `IpamPrefix` | one | no | `kind: Attribute`, `identifier: cluster__service_prefix`, `order_weight: 910`. Lab: `10.112.0.0/16` |
| `node_prefix` | `IpamPrefix` | one | no | `kind: Attribute`, `identifier: cluster__node_prefix`, `order_weight: 920`. Lab: `10.110.0.0/24` |
| `vip_pools` | `IpamPrefix` | many | yes | `identifier: cluster__vip_pools`, `order_weight: 930`. Lab: `10.112.240.0/24` |
| `nodes` | `KubernetesNode` | many | yes | `kind: Component`, `identifier: cluster__nodes`, `order_weight: 940` (FR-041) |
| `fabric_peerings` | `KubernetesFabricPeering` | many | yes | `kind: Component`, `identifier: cluster__fabric_peerings`, `order_weight: 950` (FR-041) |
| `vrf` | `IpamVRF` | one | yes | `kind: Attribute`, `identifier: cluster__vrf`, `order_weight: 960`. The fabric VRF its traffic lands in. Lab: `K8S_PROD` |

### `KubernetesNode` (node)

- `human_friendly_id: [cluster__name__value, name__value]`
- `display_label: "{{ cluster__name__value }} / {{ name__value }}"`, `order_by: [name__value]`
- `uniqueness_constraints: [["cluster", "name__value"]]`
- `icon: mdi:server-network`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `order_weight: 1000`. Lab: `k8s-node1`..`k8s-node3` |
| `role` | Dropdown | no | `default_value: worker`. Choices `control_plane`, `worker`, `both`. `order_weight: 1100` |
| `bgp_enabled` | Boolean | no | `default_value: false`, `order_weight: 1200`. BGP is opt-in per node |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `cluster` | `KubernetesCluster` | one | no | `kind: Parent`, `identifier: cluster__nodes`, `order_weight: 900` |
| `device` | `DcimGenericDevice` | one | no | `kind: Attribute`, `identifier: device__kubernetes_nodes`, `order_weight: 910`. Peers the generic so a `DcimDevice` or a `ComputePhysicalServer` both work (R7) |
| `node_address` | `IpamIPAddress` | one | yes | `kind: Attribute`, `identifier: kubernetes_node__address`, `order_weight: 920`. Lab: `10.110.0.11`.. |
| `pod_cidr` | `IpamPrefix` | one | yes | `kind: Attribute`, `identifier: kubernetes_node__pod_cidr`, `order_weight: 930`. The per-node slice Cilium advertises |

### `KubernetesFabricPeering` (node)

One BGP session between the cluster and one leaf. The object that makes the cluster a
routing peer rather than a guest.

- `human_friendly_id: [cluster__name__value, name__value]`
- `display_label: "{{ cluster__name__value }} ↔ {{ name__value }}"`, `order_by: [name__value]`
- `uniqueness_constraints: [["cluster", "leaf_device"]]` (FR-071)
- `icon: mdi:vector-polyline`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `order_weight: 1000`. Lab: `k8s-leaf1`, `k8s-leaf2` |
| `peer_asn` | Number | no | `parameters: {min_value: 1, max_value: 4294967295}`, `order_weight: 1100`. Lab: `65101` (FR-023) |
| `enabled` | Boolean | no | `default_value: true`, `order_weight: 1200` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `cluster` | `KubernetesCluster` | one | no | `kind: Parent`, `identifier: cluster__fabric_peerings`, `order_weight: 900` |
| `leaf_device` | `DcimDevice` | one | no | `kind: Attribute`, `identifier: device__kubernetes_peerings`, `order_weight: 910` (FR-023) |
| `leaf_address` | `IpamIPAddress` | one | no | `kind: Attribute`, `identifier: kubernetes_peering__leaf_address`, `order_weight: 920`. Lab: `10.110.0.2` / `.3` — the leaves' **unique** SVI addresses, never the shared VARP gateway `10.110.0.1`, which US2 scenario 4 exists to enforce |
| `svi` | `EvpnSvi` | one | yes | `kind: Attribute`, `identifier: kubernetes_peering__svi`, `order_weight: 930`. The fabric-side SVI, so both halves of the session are one graph path. Lab: VLAN 110 |

---

## 7. Kubernetes services: `schemas/service/kubernetes_services.yml` — US3

### `ServiceFabricPeering` (node)

- `inherit_from: [ServiceGeneric, GeneratorTarget, CoreArtifactTarget]` (R2, R3)
- `icon: mdi:handshake`, `label: Fabric Peering Service`, `include_in_menu: true`
- HFID, display label, ordering and the name constraint are inherited

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `communities` | List | yes | `order_weight: 1300`. Lab: `["65401:110"]` |
| `advertisement_selector` | JSON | yes | `order_weight: 1400`. Must agree with the cluster's; the mismatch is the failure the lab documents (an advertisement created and never attached to a session) |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `cluster` | `KubernetesCluster` | one | no | `kind: Attribute`, `identifier: service__cluster_peering`, `on_delete: no-action`, `order_weight: 910` |
| `peerings` | `KubernetesFabricPeering` | many | yes | `identifier: service__fabric_peerings`, `on_delete: no-action`, `order_weight: 920`. The technical objects that realize it (FR-082) |

### `ServiceFabricApp` (node)

An application that is a participant in the fabric. One object carrying what the lab
splits across a namespace, a chart, a VIP pool, a BGP advertisement, and a network
policy — because, as the lab's own comment says, those "are not really separable".

- `inherit_from: [ServiceGeneric, GeneratorTarget, CoreArtifactTarget]`
- `icon: mdi:apps`, `label: Fabric Application`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `namespace_name` | Text | no | `order_weight: 1300`. Not `namespace` — that is a reserved schema word. Lab: `nfd41-demo` |
| `chart_repository` | Text | yes | `order_weight: 1400` |
| `chart_name` | Text | yes | `order_weight: 1410` |
| `chart_version` | Text | yes | `order_weight: 1420` |
| `chart_values` | JSON | yes | `order_weight: 1430` (R4) |
| `manifests` | JSON | yes | `order_weight: 1440`. Raw API objects; the escape hatch for workloads with no chart (R4, FR-025) |
| `exposed` | Boolean | no | `default_value: false`, `order_weight: 1500`. False means cluster-internal: no pool, no advertisement, no route off the cluster (US3 scenario 4) |
| `service_selector` | JSON | yes | `order_weight: 1510`. Which Services get a VIP. A Service is never exposed just by being `type: LoadBalancer` |
| `communities` | List | yes | `order_weight: 1520`. Lab: `["65401:112"]` |
| `policy_default_deny` | Boolean | no | `default_value: true`, `order_weight: 1600` (FR-024) |
| `policy_allow_dns` | Boolean | no | `default_value: true`, `order_weight: 1610` |
| `policy_allow_intra_namespace` | Boolean | no | `default_value: true`, `order_weight: 1620` |
| `policy_allow_egress_api_server` | Boolean | no | `default_value: false`, `order_weight: 1630` |
| `policy_allow_egress_internet` | Boolean | no | `default_value: false`, `order_weight: 1640` |
| `policy_allow_ports` | JSON | yes | `order_weight: 1650`. Lab: `[{"port": "8080", "protocol": "TCP"}]` |
| `workload_selector` | JSON | yes | `order_weight: 1660`. Empty means every pod in the namespace |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `cluster` | `KubernetesCluster` | one | no | `kind: Attribute`, `identifier: service__cluster_apps`, `on_delete: no-action`, `order_weight: 910` |
| `vrf` | `IpamVRF` | one | yes | `kind: Attribute`, `identifier: service__app_vrf`, `on_delete: no-action`, `order_weight: 920`. The fabric tenant VRF. Lab: `K8S_PROD` |
| `vip_block` | `IpamPrefix` | one | yes | `kind: Attribute`, `identifier: service__app_vip_block`, `on_delete: no-action`, `order_weight: 930`. Lab: `10.112.240.0/28`. Mandatory in practice when `exposed` is true; left optional so an unexposed app is valid (US3 scenario 4) |
| `allowed_source_prefixes` | `IpamPrefix` | many | yes | `identifier: service__app_allowed_sources`, `on_delete: no-action`, `order_weight: 940`. **The load-bearing relationship.** Lab: `10.210.0.0/24`, `10.60.0.0/16`, `10.70.0.0/24` — the same three prefixes the firewall zone policy and the leaf ACL name, now the same objects (FR-023 of the spec's US3 scenario 3) |
| `peering_service` | `ServiceFabricPeering` | one | yes | `kind: Attribute`, `identifier: service__app_peering`, `on_delete: no-action`, `order_weight: 950`. Which peering carries its advertisement |

**Note on `exposed`.** The lab expresses this by the presence or absence of an `expose`
block. A schema has no optional-block construct, so the boolean plus optional
`vip_block` / `service_selector` is the faithful translation. The contract test asserts
that an object with `exposed: false` and no `vip_block` validates.

---

## 8. Security technical layer: `schemas/security/security.yml` — US4

### `SecurityZone` (node)

- `human_friendly_id: [device__name__value, name__value]`
- `display_label: "{{ name__value }}"`, `order_by: [name__value]`
- `uniqueness_constraints: [["device", "name__value"]]`
- `icon: mdi:shield-lock`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `order_weight: 1000`. Lab: `k8s-prod`, `app-prod`, `wan`, `branch`, `acme-cloud`, `globex-cloud` |
| `description` | Text | yes | `order_weight: 1100` |
| `trust_level` | Number | yes | `parameters: {min_value: 0, max_value: 100}`, `order_weight: 1200` (FR-027) |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `device` | `DcimDevice` | one | no | `kind: Attribute`, `identifier: device__security_zones`, `order_weight: 900` (FR-045) |
| `interfaces` | `DcimInterface` | many | yes | `identifier: security_zone__interfaces`, `order_weight: 910` (FR-045). Lab: `ge-0/0/0`..`ge-0/0/5` |
| `vrf` | `IpamVRF` | one | yes | `kind: Attribute`, `identifier: security_zone__vrf`, `order_weight: 920`. The fabric VRF on the other side of the handoff. Lab: `K8S_PROD` ↔ `k8s-prod` |

### `SecurityAddress` (node)

An address-book entry. References an IPAM object rather than restating a CIDR (FR-044).

- `human_friendly_id: [name__value]`, `display_label: name__value`, `order_by: [name__value]`
- `uniqueness_constraints: [["name__value"]]`
- `icon: mdi:ip-network`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `unique: true`, `order_weight: 1000`. Lab: `k8s-nodes`, `k8s-pods`, `k8s-services`, `access-portal`, `app-hosts`, `fabric-infra`, `wan-customers`, `branch-users`, `acme-hq`, `acme-dr`, `acme-cloud`, `globex-hq`, `globex-cloud` |
| `description` | Text | yes | `order_weight: 1100` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `prefix` | `IpamPrefix` | one | yes | `kind: Attribute`, `identifier: security_address__prefix`, `order_weight: 900` |
| `ip_address` | `IpamIPAddress` | one | yes | `kind: Attribute`, `identifier: security_address__ip_address`, `order_weight: 910`. Lab: `access-portal` is `10.112.240.33/32` |

Exactly one of `prefix` / `ip_address` is expected. Infrahub cannot express
"exactly-one-of" as a constraint, so this is asserted by the contract test and is a
candidate for a later `checks/` definition — recorded as a known limitation rather than
silently assumed.

### `SecurityAddressGroup` (node)

- Same display and uniqueness shape as `SecurityAddress`
- `icon: mdi:folder-network`, `include_in_menu: true`

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `addresses` | `SecurityAddress` | many | yes | `identifier: address_group__addresses`, `order_weight: 900` |
| `groups` | `SecurityAddressGroup` | many | yes | `identifier: address_group__nested_groups`, `order_weight: 910`. Self-referential nesting (FR-043 of the spec's US4 scenario 3) |

Lab groups: `acme-sites` (acme-hq + acme-dr), `globex-sites`, `k8s-all` (k8s-nodes +
k8s-pods), `k8s-reachable` (k8s-nodes + k8s-services).

**Edge case, carried forward**: the spec asks whether an emptied group is match-nothing
or match-anything. On Junos an empty address set is a commit error, so the model treats
an empty group as invalid — asserted by a contract test, enforceable later by a check.
Self-referential nesting also admits a cycle, which no schema constraint can prevent;
also a check-cycle item.

### `SecurityApplication` (node)

A port and protocol tuple a rule matches on.

- `human_friendly_id: [name__value]`, `uniqueness_constraints: [["name__value"]]`
- `icon: mdi:network`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `unique: true`, `order_weight: 1000` |
| `protocol` | Dropdown | no | `default_value: tcp`. Choices `tcp`, `udp`, `icmp`, `any`. `order_weight: 1100` |
| `port` | Number | yes | `parameters: {min_value: 1, max_value: 65535}`, `order_weight: 1200` |
| `port_range_end` | Number | yes | `parameters: {min_value: 1, max_value: 65535}`, `order_weight: 1210`. Set for a range; `port` alone is a single port |

### `SecurityPolicy` (node)

One zone-pair policy. Owns its rules.

- `human_friendly_id: [name__value]`, `display_label: "{{ source_zone__name__value }} → {{ destination_zone__name__value }}"`
- `uniqueness_constraints: [["source_zone", "destination_zone"]]` (FR-072)
- `icon: mdi:shield-check`, `include_in_menu: true`

**Correction found at load time.** The zone pair is the semantic identity, but it cannot
also be the human-friendly id. Infrahub rejects an HFID path that traverses a peer to a
non-unique attribute combination, and `SecurityZone.name` is unique only *per device* —
deliberately, so two firewalls may each hold a zone named `wan`. The load failed with
`HFID of SecurityPolicy refers to peer SecurityZone with a non-unique combination of
attributes ['name__value']`. `SecurityPolicy` therefore carries its own unique `name`,
conventionally `<source>-to-<destination>`, and `SecurityPolicyRule`'s HFID goes through
that name rather than through the zones.

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `unique: true`, `order_weight: 1000`. Conventionally `branch-to-k8s-prod` |
| `description` | Text | yes | `order_weight: 1100` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `source_zone` | `SecurityZone` | one | no | `kind: Attribute`, `identifier: policy__source_zone`, `order_weight: 900` |
| `destination_zone` | `SecurityZone` | one | no | `kind: Attribute`, `identifier: policy__destination_zone`, `order_weight: 910` |
| `rules` | `SecurityPolicyRule` | many | yes | `kind: Component`, `identifier: policy__rules`, `order_weight: 920` (FR-042) |

Lab zone pairs — **eleven**, carrying nineteen rules between them:
`app-prod→k8s-prod` (3 rules), `k8s-prod→app-prod` (2), `wan→k8s-prod` (2),
`branch→k8s-prod` (3), `wan→acme-cloud` (2), `wan→globex-cloud` (2),
`acme-cloud→wan` (1), `globex-cloud→wan` (1), `wan→app-prod` (1), `wan→branch` (1),
`branch→wan` (1). The last three are single explicit denies, and the two
cloud-to-wan pairs exist because a session permitted outbound still needs its
reply path stated.

### `SecurityPolicyRule` (node)

- `human_friendly_id: [policy__name__value, name__value]` (via the policy's unique name, for the same reason)
- `display_label: "{{ name__value }}"`, `order_by: [sequence__value]`
- `uniqueness_constraints: [["policy", "name__value"], ["policy", "sequence__value"]]` (FR-073)
- `icon: mdi:format-list-numbered`, `include_in_menu: false` (browsed through its policy)

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `order_weight: 1000`. Lab: `deny-spoofed-infra`, `app-to-k8s-services`, `wan-to-k8s-services`, `branch-to-access-portal`, `acme-sites-to-acme-cloud`, … |
| `sequence` | Number | no | `parameters: {min_value: 1}`, `order_weight: 1100` (FR-026). First-match order; the anti-spoofing deny is always `sequence: 10` |
| `action` | Dropdown | no | `default_value: permit`. Choices `permit`, `deny`, `reject`. `order_weight: 1200` (FR-026) |
| `log_session_init` | Boolean | no | `default_value: false`, `order_weight: 1300` |
| `log_session_close` | Boolean | no | `default_value: false`, `order_weight: 1310` |
| `managed_by_service` | Boolean | no | `default_value: false`, `order_weight: 2000`. **The unmanaged-object guard.** The spec's edge case asks how a generator avoids deleting the hand-written anti-spoofing rule; this flag is the answer — a generator reconciles only rules where it is true |
| `description` | Text | yes | `order_weight: 1400` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `policy` | `SecurityPolicy` | one | no | `kind: Parent`, `identifier: policy__rules`, `order_weight: 900` |
| `source_addresses` | `SecurityAddress` | many | yes | `identifier: rule__source_addresses`, `order_weight: 910` |
| `source_address_groups` | `SecurityAddressGroup` | many | yes | `identifier: rule__source_address_groups`, `order_weight: 920` |
| `destination_addresses` | `SecurityAddress` | many | yes | `identifier: rule__destination_addresses`, `order_weight: 930` |
| `destination_address_groups` | `SecurityAddressGroup` | many | yes | `identifier: rule__destination_address_groups`, `order_weight: 940` |
| `applications` | `SecurityApplication` | many | yes | `identifier: rule__applications`, `order_weight: 950` |

`match_any_source` / `match_any_destination` are **not** modeled as booleans; an empty
address relationship set with `action: permit` would be ambiguous. Instead the lab's
`destination-address any` is represented by a `SecurityAddress` named `any` bound to the
`0.0.0.0/0` prefix, which keeps every rule's match explicit.

---

## 9. Access service: `schemas/service/access_services.yml` — US5

### `ServiceAppAccess` (node)

"This person may use that application", as one object — composing the application and
the firewall rule, which the lab notes are "the two halves that are always forgotten
separately".

- `inherit_from: [ServiceGeneric, GeneratorTarget, CoreArtifactTarget]`
- `icon: mdi:key-chain`, `label: Application Access Grant`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `requester` | Text | no | `order_weight: 1300` (FR-029) |
| `justification` | TextArea | yes | `order_weight: 1310` |
| `approved` | Boolean | no | `default_value: false`, `order_weight: 1400` (FR-029). **The gate.** While false, nothing is composed — an unapproved request is inert, not merely hidden |
| `approved_by` | Text | yes | `order_weight: 1410` |
| `approved_at` | DateTime | yes | `order_weight: 1420`. Audit trail lives with the grant (US5 scenario 3) |
| `ports` | List | yes | `order_weight: 1500`. Lab default: `[80]`. Empty is rejected, not read as "all" |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `application` | `ServiceFabricApp` | one | no | `kind: Attribute`, `identifier: service__access_application`, `on_delete: no-action`, `order_weight: 910` (FR-049) |
| `source_zone` | `SecurityZone` | one | no | `kind: Attribute`, `identifier: service__access_source_zone`, `on_delete: no-action`, `order_weight: 920` (FR-049). Lab: `branch` |
| `source_address` | `SecurityAddress` | one | no | `kind: Attribute`, `identifier: service__access_source_address`, `on_delete: no-action`, `order_weight: 930` (FR-049). Lab: `branch-users`. The firewall's own vocabulary; this never synthesizes a CIDR |
| `destination_vip` | `IpamIPAddress` | one | no | `kind: Attribute`, `identifier: service__access_destination_vip`, `on_delete: no-action`, `order_weight: 940` |
| `granted_rules` | `SecurityPolicyRule` | many | yes | `identifier: service__access_granted_rules`, `on_delete: no-action`, `order_weight: 950`. What the grant caused to exist, so revocation is traceable (FR-082, US5 scenario 5) |

**On US5 scenario 4** (a VIP outside the range the border leaf re-advertises): because
`destination_vip` is an `IpamIPAddress` and the re-advertised range is an `IpamPrefix`,
containment is a graph question. The schema makes it *detectable*; the check that fails
it belongs to a later cycle.

---

## 10. WAN technical layer: `schemas/wan/wan.yml` — US6

### `WanTenant` (node)

The unit of isolation on the provider edge: one VRF, one identity, one policy (R8, R9).

- `human_friendly_id: [name__value]`, `display_label: name__value`, `order_by: [name__value]`
- `uniqueness_constraints: [["name__value"]]`
- `icon: mdi:account-network`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `unique: true`, `order_weight: 1000`. Lab: `acme`, `globex`, `branch` |
| `tenant_id` | Number | no | `order_weight: 1100`. Drives addressing and the VRF table number. Lab: `10`, `20` |
| `kind` | Dropdown | no | `default_value: customer`. Choices `customer`, `internal`. `order_weight: 1200` (R10). The branch is `internal` |
| `vrf_name` | Text | yes | `order_weight: 1300`. Lab: `CUST_ACME`, `CUST_GLOBEX` |
| `vrf_table_id` | Number | yes | `order_weight: 1310`. Lab: `1010`, `1020` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `customer` | `OrganizationCustomer` | one | yes | `kind: Attribute`, `identifier: customer__wan_tenants`, `order_weight: 900` (R8). Optional because an `internal` tenant has no customer |
| `provider` | `OrganizationProvider` | one | no | `kind: Attribute`, `identifier: provider__wan_tenants`, `order_weight: 910`. The ISP (FR-006) |
| `sites` | `WanSite` | many | yes | `kind: Component`, `identifier: tenant__sites`, `order_weight: 920` |
| `dc_vrf` | `IpamVRF` | one | yes | `kind: Attribute`, `identifier: wan_tenant__dc_vrf`, `order_weight: 930`. Lab: `TENANT_ACME` (R9) |

### `WanSite` (node)

- `human_friendly_id: [tenant__name__value, name__value]`
- `display_label: "{{ tenant__name__value }} / {{ name__value }}"`, `order_by: [name__value]`
- `uniqueness_constraints: [["tenant", "name__value"]]` (FR-074)
- `icon: mdi:office-building-marker`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `order_weight: 1000`. Lab: `hq`, `dr` |
| `attachment_kind` | Dropdown | no | `default_value: bgp`. Choices `bgp`, `static`. `order_weight: 1100` (FR-028) |
| `site_asn` | Number | yes | `parameters: {min_value: 1, max_value: 4294967295}`, `order_weight: 1200`. Set only when `attachment_kind` is `bgp`. Lab: `65010`, `65020`, `65030` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `tenant` | `WanTenant` | one | no | `kind: Parent`, `identifier: tenant__sites`, `order_weight: 900` |
| `lan_prefix` | `IpamPrefix` | one | no | `kind: Attribute`, `identifier: wan_site__lan_prefix`, `order_weight: 910`. Lab: `10.60.10.0/24` |
| `circuit` | `WanCircuit` | one | yes | `kind: Component`, `identifier: site__circuit`, `order_weight: 920` |
| `location` | `LocationGeneric` | one | yes | `kind: Attribute`, `identifier: location__wan_sites`, `order_weight: 930` |

### `WanCircuit` (node)

One attachment circuit: two endpoints on two devices (FR-046). The lab is explicit that
conflating them "is how the internet router ends up waiting forever for an interface
that only exists on isp-pe2".

- `human_friendly_id: [site__tenant__name__value, site__name__value]`
- `display_label: "{{ site__tenant__name__value }} / {{ site__name__value }} circuit"`
- `uniqueness_constraints: [["provider_edge_interface"]]` (FR-074)
- `icon: mdi:transit-connection-variant`, `include_in_menu: false`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `mtu` | Number | yes | `default_value: 9214`, `order_weight: 1100`. The lab warns the veth default of 9500 makes the mismatch "silent and expensive" |
| `circuit_id` | Text | yes | `order_weight: 1000` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `site` | `WanSite` | one | no | `kind: Parent`, `identifier: site__circuit`, `order_weight: 900` |
| `provider_edge_interface` | `DcimInterface` | one | no | `kind: Attribute`, `identifier: circuit__pe_interface`, `order_weight: 910`. Peers the generic so a circuit can terminate on `border-leaf1` for the branch, not only on a PE (R10) |
| `provider_edge_address` | `IpamIPAddress` | one | yes | `kind: Attribute`, `identifier: circuit__pe_address`, `order_weight: 920`. Lab: `10.51.10.1/30` |
| `customer_edge_interface` | `DcimInterface` | one | yes | `kind: Attribute`, `identifier: circuit__ce_interface`, `order_weight: 930` |
| `customer_edge_address` | `IpamIPAddress` | one | yes | `kind: Attribute`, `identifier: circuit__ce_address`, `order_weight: 940`. Lab: `10.51.10.2/30` |
| `bgp_session` | `RoutingBGPNeighbor` | one | yes | `kind: Attribute`, `identifier: circuit__bgp_session`, `order_weight: 950`. Present when `attachment_kind` is `bgp`; reuses the repository's existing routing kind rather than a parallel session model |
| `static_routes` | `RoutingVrfStaticRoute` | many | yes | `identifier: circuit__static_routes`, `order_weight: 960`. Present when `attachment_kind` is `static` (US6 scenario 3) |

### `WanInternetPeering` (node)

- `human_friendly_id: [name__value]`, `uniqueness_constraints: [["name__value"]]`
- `icon: mdi:web`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `name` | Text | no | `unique: true`, `order_weight: 1000` |
| `peer_asn` | Number | no | `order_weight: 1100`. Lab: `64500` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `provider` | `OrganizationProvider` | one | no | `kind: Attribute`, `identifier: provider__internet_peerings`, `order_weight: 900`. The ISP |
| `internet_provider` | `OrganizationProvider` | one | no | `kind: Attribute`, `identifier: internet_provider__peerings`, `order_weight: 910`. AS 64500 |
| `provider_interface` | `DcimInterface` | one | yes | `kind: Attribute`, `identifier: internet_peering__provider_interface`, `order_weight: 920`. Lab: `isp-pe2 eth3` |
| `peer_interface` | `DcimInterface` | one | yes | `kind: Attribute`, `identifier: internet_peering__peer_interface`, `order_weight: 930`. Lab: `internet-rtr eth1`. Two relationships because they are two devices |
| `customer_aggregate` | `IpamPrefix` | one | yes | `kind: Attribute`, `identifier: internet_peering__customer_aggregate`, `order_weight: 940`. Lab: `10.60.0.0/16` |
| `internet_prefixes` | `IpamPrefix` | many | yes | `identifier: internet_peering__internet_prefixes`, `order_weight: 950`. Lab: `198.51.100.0/24` |

---

## 11. WAN services: `schemas/service/wan_services.yml` — US7

### `ServiceL3vpn` (node)

- `inherit_from: [ServiceGeneric, GeneratorTarget]` — not an artifact target (R3)
- `icon: mdi:lan-connect`, `label: Tenant L3VPN`, `include_in_menu: true`

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `tenant` | `WanTenant` | one | no | `kind: Attribute`, `identifier: service__l3vpn_tenant`, `on_delete: no-action`, `order_weight: 910` (FR-048) |
| `vrf` | `IpamVRF` | one | yes | `kind: Attribute`, `identifier: service__l3vpn_vrf`, `on_delete: no-action`, `order_weight: 920` |
| `circuits` | `WanCircuit` | many | yes | `identifier: service__l3vpn_circuits`, `on_delete: no-action`, `order_weight: 930` (FR-048). Member sites' circuits — why two sites of one tenant reach each other without anything being leaked |
| `dc_service_prefixes` | `IpamPrefix` | many | yes | `identifier: service__l3vpn_dc_prefixes`, `on_delete: no-action`, `order_weight: 940`. The shared half of the import policy. Lab: `10.112.240.0/24` |

### `ServiceInternetAccess` (node)

The product a tenant either buys or does not. Its presence is the *entire* difference
between the lab's two tenants (SC-007, US7 scenario 3).

- `inherit_from: [ServiceGeneric, GeneratorTarget]`
- `icon: mdi:web-check`, `label: Internet Access`, `include_in_menu: true`

| Attribute | Kind | Opt | Notes |
| --- | --- | --- | --- |
| `default_route_imported` | Boolean | no | `default_value: true`, `order_weight: 1300` |
| `prefixes_announced` | Boolean | no | `default_value: true`, `order_weight: 1310` |

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `l3vpn` | `ServiceL3vpn` | one | no | `kind: Attribute`, `identifier: service__internet_l3vpn`, `on_delete: no-action`, `order_weight: 910` (US7 scenario 2) |
| `peering` | `WanInternetPeering` | one | yes | `kind: Attribute`, `identifier: service__internet_peering`, `on_delete: no-action`, `order_weight: 920` |

### `ServiceTenantCloud` (node)

Couples a fabric VRF, a firewall zone, and a subnet — the bridge between the provider
edge and the fabric (R9).

- `inherit_from: [ServiceGeneric, GeneratorTarget]`
- `icon: mdi:cloud-lock`, `label: Tenant Cloud`, `include_in_menu: true`

| Relationship | Peer | Card | Opt | Notes |
| --- | --- | --- | --- | --- |
| `tenant` | `WanTenant` | one | no | `kind: Attribute`, `identifier: service__cloud_tenant`, `on_delete: no-action`, `order_weight: 910` |
| `vrf` | `IpamVRF` | one | no | `kind: Attribute`, `identifier: service__cloud_vrf`, `on_delete: no-action`, `order_weight: 920` (FR-047). Lab: `TENANT_ACME` |
| `zone` | `SecurityZone` | one | no | `kind: Attribute`, `identifier: service__cloud_zone`, `on_delete: no-action`, `order_weight: 930` (FR-047). Lab: `acme-cloud` |
| `prefix` | `IpamPrefix` | one | no | `kind: Attribute`, `identifier: service__cloud_prefix`, `on_delete: no-action`, `order_weight: 940` (FR-047). Lab: `10.220.10.0/24` |
| `vlan` | `IpamVLAN` | one | yes | `kind: Attribute`, `identifier: service__cloud_vlan`, `order_weight: 950`. Lab: VLAN 1310 |

Note this file introduces a service→service relationship (`ServiceInternetAccess.l3vpn`)
and a cross-domain service reference (`ServiceTenantCloud.zone` → `SecurityZone`). Both
are within the service layer or service→technical, so neither violates FR-080.

---

## 12. Layering invariants (FR-080 — testable)

| Invariant | How it is asserted |
| --- | --- |
| No technical file names a service kind | Walk `schemas/kubernetes/`, `schemas/security/`, `schemas/wan/`, `schemas/organization_extensions.yml`; fail on any `peer:` value starting with `Service` |
| Technical files load standalone | `infrahubctl schema check` on the technical set only (SC-009) |
| Only one place couples DCIM to services | Exactly one `extensions:` block with `peer: ServiceGeneric`, in `schemas/service/service.yml` |
| Every service kind is a generator target | Every node in `schemas/service/` inherits `GeneratorTarget` (FR-081) |
| Cluster-delivered services are artifact targets | `ServiceFabricPeering`, `ServiceFabricApp`, `ServiceAppAccess` inherit `CoreArtifactTarget` (FR-083) |
| No service→technical relationship cascades | Every such relationship sets `on_delete: no-action` (FR-053) |

## 13. Known limitations carried to later cycles

| Limitation | Why the schema cannot express it | Where it belongs |
| --- | --- | --- |
| `SecurityAddress` must have exactly one of `prefix` / `ip_address` | No exactly-one-of constraint | `checks/` |
| A `SecurityAddressGroup` must not be empty | No min-count-on-union constraint | `checks/` |
| `SecurityAddressGroup` nesting must be acyclic | No acyclicity constraint | `checks/` |
| `ServiceFabricApp.vip_block` must be inside the cluster's `service_prefix` | Prefix containment is a graph query, not a constraint | `checks/` |
| `ServiceAppAccess.destination_vip` must be inside a re-advertised range | Same | `checks/` |
| `WanSite.site_asn` is required exactly when `attachment_kind: bgp` | No conditional-requirement constraint | `checks/` |
| Rule `sequence` collisions across an insert | Uniqueness catches the duplicate but cannot renumber | Generator logic |
