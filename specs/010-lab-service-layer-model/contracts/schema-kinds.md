# Contract: Schema Kind Surface

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


A schema feature's external interface is the set of **kinds** it publishes and the
**graph invariants** they guarantee. Everything downstream — GraphQL queries, generated
protocol classes, generators, transforms, object data files, menus, and the service
portal — is written against this surface. A change to anything in this document is a
breaking change to a consumer.

Kind names are derived as `Namespace + Name` and are how every consumer references the
model.

---

## 1. Published kinds

### Generics (3)

| Kind | Purpose | Inherited by |
| --- | --- | --- |
| `ServiceGeneric` | The service-layer query surface: name, status, owner | all 6 service nodes |
| `ServiceGenericDevice` | Binds a service to the devices realizing it | opt-in per service kind |
| `ServiceGenericInterface` | Binds a service to interfaces | opt-in per service kind |

### Service-layer nodes (6)

| Kind | Inherits | Artifact target |
| --- | --- | --- |
| `ServiceFabricPeering` | `ServiceGeneric`, `GeneratorTarget`, `CoreArtifactTarget` | yes |
| `ServiceFabricApp` | `ServiceGeneric`, `GeneratorTarget`, `CoreArtifactTarget` | yes |
| `ServiceAppAccess` | `ServiceGeneric`, `GeneratorTarget`, `CoreArtifactTarget` | yes |
| `ServiceL3vpn` | `ServiceGeneric`, `GeneratorTarget` | no |
| `ServiceInternetAccess` | `ServiceGeneric`, `GeneratorTarget` | no |
| `ServiceTenantCloud` | `ServiceGeneric`, `GeneratorTarget` | no |

### Technical-layer nodes (14)

| Kind | Domain | Owned components |
| --- | --- | --- |
| `KubernetesCluster` | Kubernetes | `KubernetesNode`, `KubernetesFabricPeering` |
| `KubernetesNode` | Kubernetes | — |
| `KubernetesFabricPeering` | Kubernetes | — |
| `SecurityZone` | Security | — |
| `SecurityAddress` | Security | — |
| `SecurityAddressGroup` | Security | — |
| `SecurityApplication` | Security | — |
| `SecurityPolicy` | Security | `SecurityPolicyRule` |
| `SecurityPolicyRule` | Security | — |
| `WanTenant` | WAN | `WanSite` |
| `WanSite` | WAN | `WanCircuit` |
| `WanCircuit` | WAN | — |
| `WanInternetPeering` | WAN | — |
| `OrganizationCustomer` | Organization | — |

### Extended kinds (4)

| Kind | Change | Compatibility |
| --- | --- | --- |
| `DcimGenericDevice` | gains `device_services` → `ServiceGeneric` (many, optional) | additive |
| `DcimInterface` | gains `interface_services` → `ServiceGeneric` (many, optional) | additive |
| `DcimDevice` | `role` dropdown gains 7 choices | additive — existing values unchanged |
| `IpamPrefix` | `role` dropdown gains 6 choices | additive — existing values unchanged |

---

## 2. Human-friendly ID contract

Object data files and generators reference objects by HFID, so these are the reference
forms consumers must use. A single-element HFID is written as a scalar; two or more
elements as a list.

| Kind | HFID | Reference form in object YAML |
| --- | --- | --- |
| `ServiceGeneric` and all service nodes | `name__value` | `"nfd41-demo-app"` |
| `OrganizationCustomer` | `name__value` | `"acme"` |
| `KubernetesCluster` | `name__value` | `"nfd41"` |
| `KubernetesNode` | `cluster__name__value`, `name__value` | `["nfd41", "k8s-node1"]` |
| `KubernetesFabricPeering` | `cluster__name__value`, `name__value` | `["nfd41", "k8s-leaf1"]` |
| `SecurityZone` | `device__name__value`, `name__value` | `["fw1", "k8s-prod"]` |
| `SecurityAddress` | `name__value` | `"branch-users"` |
| `SecurityAddressGroup` | `name__value` | `"acme-sites"` |
| `SecurityApplication` | `name__value` | `"http"` |
| `SecurityPolicy` | `name__value` | `"branch-to-k8s-prod"` |
| `SecurityPolicyRule` | `policy__name__value`, `name__value` | `["branch-to-k8s-prod", "branch-to-access-portal"]` |
| `WanTenant` | `name__value` | `"acme"` |
| `WanSite` | `tenant__name__value`, `name__value` | `["acme", "hq"]` |
| `WanCircuit` | `site__tenant__name__value`, `site__name__value` | `["acme", "hq"]` |
| `WanInternetPeering` | `name__value` | `"isp-to-internet"` |

Note `SecurityZone`'s HFID traverses to the device, so two firewalls may each hold a
zone named `wan` without collision. That is exactly why `SecurityPolicy` carries a
`name` of its own: an HFID path through a peer must reach a globally unique attribute,
and a zone name is unique only within its device. The zone pair remains the semantic
identity, enforced by FR-072's uniqueness constraint rather than by the HFID.

---

## 3. Uniqueness contract

| Kind | Constraint | Rejects |
| --- | --- | --- |
| `ServiceGeneric` | `[["name__value"]]` | two services of any kind sharing a name |
| `KubernetesCluster` | `[["name__value"]]` | duplicate cluster |
| `KubernetesNode` | `[["cluster", "name__value"]]` | duplicate node in one cluster |
| `KubernetesFabricPeering` | `[["cluster", "leaf_device"]]` | a second session to the same leaf (US2 scenario 3) |
| `SecurityZone` | `[["device", "name__value"]]` | duplicate zone on one firewall |
| `SecurityAddress` | `[["name__value"]]` | duplicate address-book entry |
| `SecurityAddressGroup` | `[["name__value"]]` | duplicate group |
| `SecurityApplication` | `[["name__value"]]` | duplicate application |
| `SecurityPolicy` | `[["source_zone", "destination_zone"]]` | a second policy for one zone pair (US4 scenario 6) |
| `SecurityPolicyRule` | `[["policy", "name__value"]]`, `[["policy", "sequence__value"]]` | duplicate rule name, and two rules claiming one evaluation position |
| `WanTenant` | `[["name__value"]]` | duplicate tenant |
| `WanSite` | `[["tenant", "name__value"]]` | duplicate site per tenant |
| `WanCircuit` | `[["provider_edge_interface"]]` | two circuits claiming one PE interface |
| `WanInternetPeering` | `[["name__value"]]` | duplicate peering |
| `OrganizationCustomer` | `[["name__value"]]` | duplicate customer |

Format follows the `uniqueness-constraints` rule: `__value` suffix for attributes, bare
names for relationships.

---

## 4. Graph invariants

Guarantees a consumer may rely on without re-checking.

| # | Invariant | Enforced by |
| --- | --- | --- |
| GI-1 | Every service object has exactly one owner resolvable to an `OrganizationGeneric` | `owner` mandatory, cardinality one |
| GI-2 | Every service object has a status from a closed set of 5 values | `Dropdown` with `choices` |
| GI-3 | Every service object exposes a `checksum` field for change detection | `GeneratorTarget` inheritance |
| GI-4 | No technical object holds a relationship to a service kind | Layering test (data-model §12) |
| GI-5 | Deleting a service never cascades into infrastructure | `on_delete: no-action` on every service→technical relationship |
| GI-6 | Every network or address referenced by more than one object is one IPAM object | Relationships to `IpamPrefix` / `IpamIPAddress`; no shared `IPNetwork` attribute exists |
| GI-7 | A cluster's nodes and peerings are deleted with the cluster | `Component`/`Parent` pairs |
| GI-8 | A policy's rules are deleted with the policy | `Component`/`Parent` pair |
| GI-9 | Policy rules have a total order within their policy | `sequence` mandatory + unique per policy |
| GI-10 | A rule generated by a service is distinguishable from a hand-written one | `SecurityPolicyRule.managed_by_service` |
| GI-11 | An unapproved access grant is inert | `approved` defaults to false; nothing is composed while false |
| GI-12 | A tenant's sites share one VPN and reach each other without a leak | `ServiceL3vpn.circuits` spans a tenant's sites; no site-to-site relationship exists |
| GI-13 | A `KubernetesFabricPeering` names one leaf and one address on that leaf | `leaf_device` and `leaf_address` both cardinality one, mandatory |

---

## 5. GraphQL surface a consumer can rely on

Query shapes the later cycles will be written against. No `.gql` file is created this
cycle; these are the guaranteed shapes.

**All services and their state** — the query behind SC-006:

```graphql
ServiceGeneric { edges { node {
  id  name { value }  status { value }
  owner { node { ... on OrganizationGeneric { name { value } } } }
} } }
```

**A cluster with everything beneath it** — the input a Crossplane `FabricPeering`
transform needs:

```graphql
KubernetesCluster(name__value: "nfd41") { edges { node {
  local_asn { value }  cni_kind { value }  cni_version { value }
  bgp_timers { value }  pod_cidr_communities { value }
  pod_prefix { node { prefix { value } } }
  service_prefix { node { prefix { value } } }
  nodes { edges { node { name { value } bgp_enabled { value } } } }
  fabric_peerings { edges { node {
    name { value }  peer_asn { value }
    leaf_device { node { name { value } } }
    leaf_address { node { address { value } } }
  } } }
} } }
```

**A zone pair's rules in evaluation order** — the input a Junos transform needs:

```graphql
SecurityPolicy { edges { node {
  source_zone { node { name { value } } }
  destination_zone { node { name { value } } }
  rules { edges { node {
    name { value }  sequence { value }  action { value }
    managed_by_service { value }
    source_addresses { edges { node { name { value } } } }
    destination_addresses { edges { node { name { value } } } }
    applications { edges { node { protocol { value } port { value } } } }
  } } }
} } }
```

Rule ordering is guaranteed by `order_by: [sequence__value]` on `SecurityPolicyRule`, so
a consumer need not sort.

---

## 6. Group contract

Generator and artifact definitions target `CoreStandardGroup` names. The later cycles
will need these added to `objects/00_groups.yml`, alongside the existing `halls`,
`racks`, `fabrics`, `pods`, `avd_devices`, `servers`, `avd_artifacts`,
`avd_structured_configs`:

| Group | Members | Consumed by |
| --- | --- | --- |
| `service_fabric_peerings` | `ServiceFabricPeering` | generator + Crossplane artifact |
| `service_fabric_apps` | `ServiceFabricApp` | generator + Crossplane artifact |
| `service_app_accesses` | `ServiceAppAccess` | generator + Crossplane artifact |
| `service_l3vpns` | `ServiceL3vpn` | generator |
| `service_internet_access` | `ServiceInternetAccess` | generator |
| `service_tenant_clouds` | `ServiceTenantCloud` | generator |
| `firewalls` | `DcimDevice` with role `firewall` | Junos config artifact |
| `wan_routers` | `DcimDevice` with the ISP/CE/branch roles | FRR config artifact |

Declared here as part of the contract because the group name is what a
`generator_definitions` or `artifact_definitions` entry binds to; creating them is
object-cycle work.

---

## 7. Backward compatibility

| Consumer | Impact |
| --- | --- |
| `src/solution_arista_avd/protocols.py` | Regenerated; gains 3 generics + 20 node classes. No existing class changes shape except `DcimDevice` and `IpamPrefix` role choices, which are `str` either way |
| `ROLE_TO_AVD_TYPE` | **Unchanged, deliberately.** Adding a new role here would let a non-EOS device be rendered as EOS (research R7) |
| `generators/*` | None. No existing generator queries a new kind |
| `transforms/*` | None |
| `objects/*.yml` | None. Existing files load unchanged |
| `menus/menu.yml` | None this cycle. New kinds are menu-capable but unplaced (research R12) |
| `.infrahub.yml` | Unchanged. Schemas are not declared there in this repository |

The whole change is additive. No attribute is removed, no `state: absent` is needed, and
no existing object requires a value it does not have — the two extended dropdowns only
gain choices.
