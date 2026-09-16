---
title: Schemas
description: All Infrahub schema definitions in this solution.
audience: developer
sidebar_position: 2
---

# Schemas

:::info Developer Guide
Documents the YAML schema files that define the data model.
:::

Every kind in the data model is defined in a YAML file under `schemas/` and loaded with `infrahubctl schema load schemas` (`inv load-schema`). The GraphQL kind is the schema `namespace` joined to its `name` — `Dcim` + `Device` becomes `DcimDevice`. Generics load as GraphQL interfaces; nodes load as GraphQL object types.

Regenerate the typed protocol classes after any schema change (see [the command below](#protocols)).

## Schema files

| File | Defines |
|------|---------|
| `base/dcim.yml` | `Dcim.GenericDevice`, `Dcim.PhysicalDevice`, `Dcim.Device`, interface generics/nodes, `Dcim.DeviceType` (incl. `containerlab_interface_mapping`), `Dcim.Platform` (incl. `containerlab_os`, `containerlab_image`) |
| `base/ipam.yml` | `Ipam.IPAddress`, `Ipam.Prefix` base definitions |
| `base/location.yml` | `Location.Generic`, `Location.Hosting` base definitions |
| `base/organization.yml` | `Organization.Generic`, `Organization.Manufacturer`, `Organization.Provider` |
| `logical_design.yml` | `Network.Fabric` (incl. `cloudvision_managed`), `Network.Pod`, `Network.BuildingBlock` |
| `device_design.yml` | `Network.DeviceDesign` generic plus the fabric/pod/rack device-design nodes |
| `dcim_extensions.yml` | `Network.Link`, including `role=dci` and DCI link fields, plus device extensions (`role`, BGP ASN relationship, `node_id`, loopback/mgmt, pod/rack relations) and the interface `role`/`description`/`ip_address` extensions |
| `dci.yml` | `NetworkFabric.dci_pool` DCI addressing source |
| `l3ls_extensions.yml` | L3LS fabric attributes (routing protocols, MTU, spanning-tree, EVPN overlay) and pod/rack/VRF/MLAG extensions |
| `location_extensions.yml` | `Location.Hall`, `Location.Rack` (`rack_type`, leaf counts, `generation_complete`, `device_name_template`, `always_include_vrfs_in_tenants`) |
| `ipam_extensions.yml` | `Ipam.Prefix` `role` and `status` dropdowns |
| `management.yml` | `Network.DnsServer`, `Network.NtpServer`, `Network.LocalUser` |
| `generator.yml` | `Generator.Target` generic (`checksum` tracking) |
| `vlan/vlan.yml` | `Ipam.VLAN`, `Ipam.L2Domain` |
| `vrf/vrf.yml` | `Ipam.VRF`, `Ipam.RouteTarget` |
| `evpn/evpn_services.yml` | `Evpn.Tenant`, `Evpn.Svi`, `Evpn.SviNode`, `Evpn.L2Vlan` |
| `evpn/evpn_gateway.yml` | `Evpn.Domain`, `Evpn.GatewayGroup`, plus fabric/pod/device EVPN Gateway relationship extensions |
| `lag/lag.yml` | `Interface.Lag`, `Generic.InterfaceBundle` |
| `mlag/mlag.yml` | `Generic.MlagDomain`, `Mlag.Domain`, `Mlag.Interface` |
| `routing/routing.yml` | `Routing.BGPPeerGroup`, `Routing.BGPNeighbor`, prefix lists, route maps, static routes |
| `routing/vrf_services.yml` | `Routing.VrfStaticRoute`, `Routing.VrfBgpPeer`, `Routing.VrfL3Interface` — the per-VRF services authored as AVD *inputs* |
| `compute/compute.yml` | `Compute.GenericUnit`, `Compute.PhysicalServer`, virtualization hosts |
| `avd/avd.yml` | `Avd.Evpn` |
| `cv/cv.yml` | `Cloudvision.Workspace` — CloudVision workspace tracking for proposed-change validation |
| `objects/objects.yml` | `Avd.Artifact`, `Avd.HostvarFile`, `Avd.StructuredConfigFile` |
| `service/service.yml` | `Service.Generic` plus the `Service.GenericDevice` / `Service.GenericInterface` binding generics, and the one extension block coupling DCIM to the service layer |
| `service/kubernetes_services.yml` | `Service.FabricPeering`, `Service.FabricApp` |
| `service/access_services.yml` | `Service.AppAccess` |
| `service/wan_services.yml` | `Service.L3vpn`, `Service.InternetAccess`, `Service.TenantCloud` |
| `cluster/cluster.yml` | **Marketplace** (`infrahub/cluster`): `Cluster.Generic`, `Cluster.GenericComputeUnitNodes` |
| `cluster/kubernetes.yml` | `Cluster.Kubernetes`, `Cluster.FabricPeering` — the CNI, pod/service/node ranges, VIP pools, and the fabric BGP contract |
| `security/security.yml` | **Marketplace** (`infrahub/security`): 22 kinds — zones, the polymorphic address book, service objects, zone-pair policy rules, `Security.Firewall` as a device kind, `Security.FirewallInterface` |
| `security_extensions.yml` | Adds `trust_level`, a fabric `vrf` link and the advertisement policy to `Security.Zone`, `managed_by_service` to `Security.PolicyRule`, and the inverse `advertised_zones` to `Dcim.FabricSwitch` |
| `circuit/circuit.yml` | **Marketplace** (`infrahub/circuit`): `Dcim.Circuit`, `Dcim.CircuitEndpoint` |
| `circuit_extensions.yml` | Adds `interface` to `Dcim.CircuitEndpoint`, so a circuit end resolves to the interface it terminates on and through it to real IP addresses |
| `tenancy/tenancy.yml` | **Marketplace** (`infrahub/tenancy`): `Organization.Tenant`, plus tenant back-references on device, prefix, address, and location |
| `wan/wan.yml` | `Wan.Tenant`, `Wan.Site`, `Wan.InternetPeering` — the provider-edge construct only; the circuit itself comes from the marketplace. `bgp_sessions` is cardinality many on both `Wan.Site` and `Wan.InternetPeering`: a session between two devices is two `Routing.BGPNeighbor` objects, one per device |

> The WAN's addressing — the routers' interfaces, their IP addresses, their ASNs, both ends of
> every BGP session, and each router's ID — is seeded in `objects/31a_nfd41_wan_addressing.yml`.
> That file sorts between the off-fabric devices (31) and the circuits and sites that name its
> interfaces (33), and the PE-side `CUST_*` VRFs live there too rather than in the service-layer
> file 37, because a VRF is a technical-layer object.

The device and interface `role` dropdowns that the fabric uses are defined in `dcim_extensions.yml`, not in the base `dcim.yml` — the extension redefines the base lists.

## Check the marketplace before authoring

Some files under `schemas/` are downloaded from the [Infrahub
Marketplace](https://marketplace.infrahub.app) rather than written here, and are kept
byte-identical to the published version so a re-download diffs cleanly. Local additions
go in a separate `*_extensions.yml`, never into the adopted file.

```bash
uv run infrahubctl marketplace get infrahub/security --stdout > schemas/security/security.yml
```

**Look there first.** The marketplace publishes 56 schemas across 10 collections, so a
new domain is likely already covered — and adopting one tends to yield a better model
than a first draft. `infrahub/security`, for instance, makes its address book
polymorphic through a `Security.GenericAddress` generic, which removes a constraint a
hand-rolled version has to push into a check.

`schemas/MARKETPLACE.md` records what is adopted, at which version, how to verify a file
is unmodified, and which schemas were evaluated and rejected with reasons.

## Technical and service layers

The schema is split into two layers, and the split is enforced structurally rather than
by convention.

**Technical layer** — what exists, per device. Interfaces, addresses, firewall zones,
address-book entries, cluster nodes, BGP sessions, attachment circuits. Every attribute
maps to something a renderer emits into a device or cluster configuration. The fabric
hierarchy below is part of this layer, as are `kubernetes/`, `security/` and `wan/`.

**Service layer** — what was ordered, per consumer. An L3VPN, an internet-access
product, an isolated tenant cloud, a fabric-peered cluster, an exposed application, an
access grant. A service names its consumer, its lifecycle status and its intent, and
carries no per-device detail. Everything under `service/` belongs to this layer.

### The dependency runs one way

Service schemas reference technical kinds. Technical schemas reference no service kind,
so `kubernetes/`, `security/` and `wan/` load without `service/` present:

```bash
uv run infrahubctl schema check schemas/base schemas/cluster schemas/security \
  schemas/wan schemas/circuit schemas/tenancy schemas/dcim_extensions.yml \
  schemas/ipam_extensions.yml schemas/generator.yml --branch <branch>
```

The reverse fails, which is the point: checking `schemas/service` alone reports
`Unable to find the schema 'SecurityZone' in the registry`.

One place couples the technical layer back to the service layer — an `extensions:` block
in `service/service.yml` adding `device_services` to `Dcim.GenericDevice` and
`interface_services` to `Dcim.Interface`. It lives in the service file deliberately:
putting it in `base/dcim.yml` would make the base layer depend on the service layer.
`tests/unit/test_service_layer_schema_contract.py` asserts both halves, because no
server-side schema check can catch a violation — a technical file that peers a service
kind validates cleanly as long as both are loaded together.

### What a service kind inherits

| Generic | Supplies | Applied to |
|---------|----------|------------|
| `Service.Generic` | `name`, `description`, `status`, `owner` | every service kind |
| `Generator.Target` | `checksum` for change detection | every service kind |
| `CoreArtifactTarget` | artifact rendering | only the kinds delivered to the cluster as manifests |

Every service kind inherits the first two, which is the mechanism by which a generator
sits underneath the service layer: it targets a group of service objects and uses
`checksum` to stay idempotent.

`CoreArtifactTarget` is applied to `Service.FabricPeering`, `Service.FabricApp` and
`Service.AppAccess` only. Those three render into Crossplane manifests, so marking them
now means an artifact definition can be attached later without a schema migration.
`Service.L3vpn`, `Service.InternetAccess` and `Service.TenantCloud` render through
device-scoped artifacts instead, so they are not artifact targets themselves.

### Addresses are always IPAM objects

No node in either layer restates a prefix or an address as text. A network referenced by
more than one object is one `Ipam.Prefix`, related to from each. This matters most where
three enforcement points match on the same network: a fabric route policy, a firewall
zone policy and a Kubernetes network policy can all name one prefix object, so agreement
between them is a graph fact rather than three copies that might drift.

### A zone's advertisement policy is a name, not a relationship

`Security.Zone` carries two fields describing the fabric side of a zone:
`dc_advertised_prefix_list`, the prefix list governing what the DC advertises **toward**
that zone, and `advertising_device`, the fabric switch that applies it.

The first is a `Text` attribute rather than a relationship, and that is forced rather
than careless. No object exists to point at: every prefix list in this fabric lives
inside `Network.Fabric.avd_custom_hostvars` as
`custom_structured_configuration_prefix_lists`, which is AVD's channel for inputs this
data model does not model. **Nothing enforces that the name resolves.** A zone can name a
list no device defines, and the only symptom is a route that never appears.

The `dc_` prefix carries the direction because both directions exist here as separate
objects, and the shorter name reads as the wrong one:

| Direction | List | Meaning |
| --- | --- | --- |
| DC → zone | `PL-DC-ADVERTISED-BRANCH` | advertised to the branch |
| zone → DC | `PL-BRANCH-PERMITTED` | accepted from the branch |

`advertising_device` peers `Dcim.FabricSwitch`, not `Dcim.Device` — see
[the four device kinds](#there-are-four-device-kinds-not-one). It records
the switch that **applies** the policy to a BGP neighbor, not the seven that merely
render its definition: the prefix lists sit at fabric scope, so every switch renders them
and one consults them.

Both fields are optional and four of the six zones use neither. That is the steady state:
the DC advertises nothing toward `k8s-prod` or `app-prod`, and the two tenant clouds are
the *subject* of an advertisement toward `wan` rather than its destination.

### Non-EOS device roles

`dcim_extensions.yml` carries seven device roles for equipment pyAVD never renders:
`firewall`, `isp_edge`, `isp_core`, `internet_edge`, `customer_edge`, `branch_router`
and `k8s_node`. These are deliberately absent from `ROLE_TO_AVD_TYPE` in
`src/solution_arista_avd/avd.py`. `get_avd_type` raises `ValueError` for an unmapped
role, and that loud failure is the wanted behaviour: mapping one would let a firewall be
rendered as an EOS switch. Devices with these roles must also stay out of the
`avd_devices` group, which is the only path into the AVD hostvar generator.

The "adding a device role" checklist in `AGENTS.md` applies to fabric roles only.

## Network fabric hierarchy

### `NetworkFabric` — `Network.Fabric`

Top-level container for a datacenter fabric. Inherits `Network.BuildingBlock` and `CoreArtifactTarget`; parents `NetworkPod`.

- **Attributes**: `name` (unique), `index`, interface-sorting methods, `mgmt_gateway`, `avd_hostvars_ready`. L3LS attributes (via `l3ls_extensions.yml`): `underlay_routing_protocol` (`ebgp`/`ospf`), `overlay_routing_protocol` (`ebgp`/`ibgp`), `p2p_uplinks_mtu`, `spanning_tree_mode`, `virtual_router_mac`, EVPN/underlay/MLAG passwords, `anta_enabled`.
- **Relationships**: `device_designs` -> `NetworkFabricDeviceDesign` (super-spine sizing), `fabric_ip_pools` -> `CoreResourcePool`, `uplink_pool` / `vtep_pool` / `loopback_pool` / `dci_pool` -> `CoreIPPrefixPool`, `asn_pool` / `node_id_pool` -> `CoreNumberPool`, `mgmt_pool` -> `CoreIPAddressPool`, `avd_evpn` -> `AvdEvpn`, `dns_servers` / `ntp_servers` / `local_users` -> management kinds. `fabric_ip_pools` is the preferred source for Management, Loopback, Loopback VTEP, Fabric Point-to-Point, DCI, and Fabric Supernet pools. Legacy fabric pool relationships remain optional fallback inputs during migration.

### `NetworkPod` — `Network.Pod`

A pod within a fabric. Inherits `Network.BuildingBlock` and `Generator.Target`; parented by `NetworkFabric`.

- **Attributes**: `name` (unique), `index`, `role` (`fabric`, `cpu`, `storage`), interface-sorting methods, `checksum` (from `Generator.Target`).
- **Relationships**: `device_designs` → `NetworkPodDeviceDesign` (spine sizing), `racks` → `LocationRack`, `devices` → `DcimDevice` (the pod's spines), `mlag_peer_pool` / `mlag_l3_pool` → `CoreIPAddressPool`.

### `NetworkBuildingBlock` — `Network.BuildingBlock` (generic)

Hierarchical base for `NetworkFabric` and `NetworkPod`. Attributes: `name` (unique), `index`.

### Device design entities — `Network.DeviceDesign` (generic)

Normalized description of the devices a container should produce, defined in `device_design.yml`. Instead of a fixed `<role>_switch_template` relationship plus an `amount_of_<role>s` attribute per role, each container relates to *many* device design entities — one per device role — through a `device_designs` relationship.

- **`NetworkDeviceDesign`** (generic): `role` (`super_spine`, `spine`, `leaf`, `l2leaf`), `device_quantity` (Number ≥ 1), and `device_template` → `CoreObjectTemplate` (cardinality one; `on_delete: no-action`, so the shared template survives a design deletion). `role` is authoritative for generation.
- **Concrete nodes**, each inheriting the generic and parented by one container:
  - `NetworkFabricDeviceDesign` → parent `NetworkFabric` (super-spine designs)
  - `NetworkPodDeviceDesign` → parent `NetworkPod` (spine designs)
  - `NetworkRackDeviceDesign` → parent `LocationRack` (leaf / l2leaf designs)
- **Ownership**: each container's `device_designs` is a `Component` (many, `on_delete: cascade`) — deleting the container deletes its designs; the templates are untouched.
- **Identity**: a design is unique per `(container, role)`; `human_friendly_id` is `"<container-name>__<role>"`. "None of a role" is the **absence** of a design (replacing `amount_of_*: 0`).

In seed data, designs are nested under their container. A rack with an MLAG leaf
pair and a single L2 leaf looks like this (from `objects/10a_l3ls_multipod_rack.yml`):

```yaml
- name: "Rack-A2-1"
  index: 1
  rack_type: compute
  pod: Pod-A2
  parent: "Hall-A1"
  device_designs:
    data:
      - role: leaf
        device_quantity: 2
        device_template: leaf-switch-compute
      - role: l2leaf
        device_quantity: 1
        device_template: l2leaf-switch
  member_of_groups: ["racks"]
```

Omit a role's entry to get none of that device type — a rack with no `l2leaf`
design gets no L2 leaves. Fabric and pod designs follow the same shape with
`role: super_spine` and `role: spine` respectively.

Adding a new device design for a supported role is data, not a schema change. Device designs are the only source of device sizing: the fabric, pod, and rack generators read `device_designs` exclusively, and the legacy paired fields they replaced (`amount_of_super_spines` / `super_spine_switch_template`, `amount_of_spines` / `spine_switch_template`, `amount_of_leafs` / `leaf_switch_template`, `amount_of_l2leafs` / `l2leaf_switch_template`) no longer exist in the schema.

### `NetworkLink` — `Network.Link`

A cabled connection between interfaces. Inherits `Dcim.Connector`, so it has `name` and `medium` (`mmf`, `smf`, `copper`) and relates to `connected_endpoints` → `DcimEndpoint`. A DCI connection is a normal `NetworkLink` with `role=dci`, not a separate schema node.

- **DCI attributes**: `role` (`dci`) and `include_in_underlay_protocol` (Boolean, default `true`). BGP ASNs are taken from each endpoint device's own `asn`, not stored on the link.
- **Relationships**: inherited `connected_endpoints`; no DCI-specific endpoint, pool, subnet, endpoint IP, speed, BFD, MTU, external-network, or EVPN Gateway fields are added.
- **Addressing source**: the hostvars generator allocates one `/31` per valid DCI-role link from `NetworkFabric.fabric_ip_pools` role `dci`, then the legacy `NetworkFabric.dci_pool` fallback, then a deterministic Fabric Supernet-derived fallback when the required DCI prefix-pool role is missing.

## Devices and interfaces

### There are four device kinds, not one

Since cycle 027 the equipment in this lab is modelled as four sibling node kinds, all inheriting `DcimGenericDevice`:

| Kind | Holds | Rendered by |
| --- | --- | --- |
| `DcimFabricSwitch` | the fabric's spines, leaves and border leaves | pyAVD → EOS config |
| `DcimDevice` | the WAN's FRR routers | `frr_config` |
| `SecurityFirewall` | the perimeter firewall | `junos_config` |
| `ComputePhysicalServer` | Kubernetes nodes, hosts, cloud instances | — |

They are **siblings, not subtypes**. Infrahub inheritance targets generics, and `DcimDevice` is a node, so `DcimFabricSwitch` could not inherit it. The consequence is the thing to remember before writing a query:

> **A query that names `DcimDevice` does not see a fabric switch, and says nothing about it.** It returns no error and no rows. Peer or spread `DcimGenericDevice` to reach every device kind at once.

`schemas/dcim_extensions.yml` recorded this decision first for the firewall — *"a firewall is its own device kind rather than a `DcimDevice` with a role"* — and cycle 027 applied it a second time.

### `DcimFabricSwitch` — `Dcim.FabricSwitch`

An Arista EOS switch in the datacenter fabric. Inherits `Dcim.GenericDevice`, `Dcim.PhysicalDevice`, and `CoreArtifactTarget` — the same three as `DcimDevice`.

- **Attributes**: `name` (unique), `description`, `os_version`, `status`. Fabric extensions (via `dcim_extensions.yml`): `role` (the ten fabric roles below), `index`, `node_id`, `avd_custom_hostvars`.
- **Relationships**: `interfaces` → `DcimInterface`, `device_type` → `DcimDeviceType`, `platform` → `DcimPlatform`, `loopback_ip` / `mgmt_ip` / `vtep_loopback_ip` → `IpamIPAddress`, `pod` → `NetworkPod`, `rack` → `LocationRack`, `asn` → `RoutingAsn`, `avd_artifact` → `AvdArtifact`, `mlag_domain` → `MlagDomain`, `evpn_gateway_group` → `EvpnGatewayGroup`, `object_template` → `TemplateDcimFabricSwitch`, plus `static_routes` inherited from the generic.

### `DcimDevice` — `Dcim.Device`

The WAN's FRR routers. Inherits `Dcim.GenericDevice`, `Dcim.PhysicalDevice`, and `CoreArtifactTarget`.

- **Attributes**: `name` (unique), `description`, `os_version`, `status`. Extensions: `role` (the six non-EOS roles below).
- **Relationships**: `interfaces` → `DcimInterface`, `device_type` → `DcimDeviceType`, `platform` → `DcimPlatform`, `router_id` → `IpamIPAddress` (explicit rather than derived, because a customer edge's router ID is its LAN address and not a loopback), `asn` → `RoutingAsn`, plus routing relations (`bgp_peer_groups`, `bgp_neighbors`, `prefix_lists`, `route_maps`, `static_routes`).

It does **not** carry `vtep_loopback_ip`, `mlag_domain`, `evpn_gateway_group`, `pod`, `rack`, `node_id`, `index`, `loopback_ip`, `mgmt_ip`, `avd_artifact`, `object_template` or `avd_custom_hostvars`. Those are fabric concepts and live on `DcimFabricSwitch`; an ISP provider edge exposed every one of them before the split.

`location` is on the shared `Dcim.PhysicalDevice` generic and is therefore available to all four kinds.

### Interface kinds

`DcimInterface` (`Dcim.Interface`) is the interface generic; the concrete nodes are `InterfacePhysical` (`Interface.Physical`), `InterfaceVirtual` (`Interface.Virtual`), and `InterfaceLag` (`Interface.Lag`). GraphQL queries that select any interface root on `DcimInterface`.

- **`DcimInterface` attributes**: `name`, `description`, `mtu`, `status`, `role`. The fabric `role` list (via `dcim_extensions.yml`) is `uplink`, `access`, `spine`, `super_spine`, `leaf`, `loopback`, `server`, `peering`, `storage`, `mlag_peer`.
- **`DcimInterface` relationships**: `device` → `DcimGenericDevice` (parent), `ip_address` → `IpamIPAddress`, `untagged_vlan` / `tagged_vlan` → `IpamVLAN`.
- Layer-2/3 behaviour comes from the `Interface.Layer2` (`l2_mode`) and `Interface.Layer3` (`ip_addresses`, `dot1q_id`, `mac_address`) generics.

### `DcimDeviceType` — `Dcim.DeviceType`

A device model. Attributes: `name` (unique), `part_number`, `height`, `full_depth`, `weight`. Relationships: `manufacturer` → `OrganizationManufacturer`, `platform` → `DcimPlatform`.

### `OrganizationManufacturer` — `Organization.Manufacturer`

A device manufacturer. Inherits `Organization.Generic`; attributes `name` (unique), `description`; relates to `device_type` → `DcimDeviceType`.

## Locations

### `LocationHall` — `Location.Hall`

A datacenter hall. Inherits `Location.Generic`; parents `LocationRack`. Attributes: `name`, `shortname`, `description`, `index`.

### `LocationRack` — `Location.Rack`

A physical rack. Inherits `Location.Generic`, `Location.Hosting`, and `Generator.Target`; parented by `LocationHall`.

- **Attributes**: `name`, `index`, `rack_type` (`compute`, `storage`), `mlag`, `generation_complete`, `checksum`.
- **Relationships**: `device_designs` → `NetworkRackDeviceDesign` (leaf and l2leaf sizing), `pod` → `NetworkPod`, `devices` → `DcimPhysicalDevice`.

## IPAM

### `IpamIPAddress` — `Ipam.IPAddress`

An IP address. Inherits `BuiltinIPAddress`. Relationships: `interface` → `Interface.Layer3`, `vrf` → `IpamVRF`.

### `IpamPrefix` — `Ipam.Prefix`

An IP prefix. Inherits `BuiltinIPPrefix`.

- **`role`** (required, via `ipam_extensions.yml`): `supernet`, `pod_super_spine_spine`, `pod_leaf_spine`, `loopback`, `loopback-vtep`, `technical`, `management`, `backfill`, and the off-fabric lab roles `pod`, `service`, `vip_pool`, `wan_customer`, `branch_lan`, `tenant_cloud`.
- **`status`** (via `ipam_extensions.yml`): `active`, `deprecated`, `reserved`.
- **Relationships**: `gateway` → `IpamIPAddress`, `vlan` → `IpamVLAN`, `vrf` → `IpamVRF`, `location` → `Location.Hosting`.

### `IpamVLAN` — `Ipam.VLAN`

A VLAN. Attributes: `name`, `vlan_id`, `status`, `role` (`server`, `management`, `user`). Relationships: `l2domain` → `IpamL2Domain` (required), `prefixes` → `IpamPrefix`.

### `IpamL2Domain` — `Ipam.L2Domain`

A layer-2 domain grouping VLANs. Attributes: `name`. Relationships: `vlans` → `IpamVLAN`.

### `IpamVRF` — `Ipam.VRF`

A VRF. Attributes: `name` (unique), `vrf_rd`, `vrf_id`, `vrf_vni`, `enable_mlag_ibgp_peering_vrfs`, `redistribute_connected`, `redistribute_static`, `vtep_diagnostic_loopback`. Relationships: `namespace` → `BuiltinIPNamespace`, `import_rt` / `export_rt` → `IpamRouteTarget`, `tenant` → `EvpnTenant`, `svis` → `EvpnSvi`, `static_routes` → `RoutingVrfStaticRoute`, `bgp_peers` → `RoutingVrfBgpPeer`, `l3_interfaces` → `RoutingVrfL3Interface` (all components).

`vrf_id` is distinct from `vrf_vni` even though the two are usually set to the same number: `vrf_id` seeds the route distinguisher and the MLAG iBGP peering VLAN.

### `IpamRouteTarget` — `Ipam.RouteTarget`

A route target. Attributes: `name` (unique), `description`. Relationships: `vrf` → `IpamVRF`.

## EVPN services

### `EvpnTenant` — `Evpn.Tenant`

An EVPN tenant. Attributes: `name` (unique), `mac_vrf_vni_base`, `description`. Relationships: `fabrics` → `NetworkFabric`, `vrfs` → `IpamVRF`, `l2vlans` → `EvpnL2Vlan` (component).

### `EvpnSvi` — `Evpn.Svi`

An SVI. Attributes: `name`, `svi_id`, `ip_address_virtual`, `ip_virtual_router_addresses`, `enabled`, `description`. Relationships: `vrf` → `IpamVRF` (parent), `vlan` → `IpamVLAN`, `rack_tags` → `LocationRack`, `avd_tags` → `AvdTag`, `nodes` → `EvpnSviNode` (component).

The two gateway styles are mutually exclusive per SVI. `ip_address_virtual` is a shared anycast address and needs nothing else. `ip_virtual_router_addresses` (VARP) is paired with per-node addresses in `nodes`, and is what an SVI needs when a workload peers BGP over it — an anycast-only SVI leaves the neighbour address ambiguous across an MLAG pair.

### `EvpnSviNode` — `Evpn.SviNode`

One device's own address on an SVI, alongside the shared VARP gateway. Attributes: `ip_address`. Relationships: `svi` → `EvpnSvi` (parent), `device` → `DcimDevice`.

Its human-friendly ID is `device` + `ip_address` rather than `svi` + `device`: `EvpnSvi.name` is only unique within its VRF, so an ID through it is not a stable identifier.

### `EvpnL2Vlan` — `Evpn.L2Vlan`

An L2-only VLAN attached to a tenant. Attributes: `name`, `vlan_id`, `vni_override`. Relationships: `tenant` → `EvpnTenant` (parent), `vlan` → `IpamVLAN`.

## VRF services

These three are AVD **inputs**, not reconciled output. They are what makes a
service-insertion design expressible: a tenant VRF whose only route out is a
default pointing at a firewall handoff. Each names the devices it applies to,
because a VRF is fabric-wide but a handoff or a peering is not.

### `RoutingStaticRoute` — `Routing.StaticRoute`

A device-level static route, in the global routing table unless `vrf` says otherwise. Attributes: `prefix`, `gateway`, `next_hop`, `interface`, `distance`, `tag`, `route_name`, `vrf` (default `"default"`). Relationships: `device` → **`DcimGenericDevice`** (mandatory, cardinality one). Unique per `[device, prefix, vrf]`.

The peer is the device *generic*, not `DcimDevice`, and that is deliberate. `SecurityFirewall` inherits `DcimGenericDevice` but not `DcimDevice`, so a concrete peer would exclude the perimeter firewall — which is what kept `routing-options` out of the Junos artifact until cycle 024. `ComputePhysicalServer` inherits the same generic and can therefore hold a route too; no peer names exactly two kinds, so that breadth is accepted rather than prevented.

`route_name` is the "Route Description" field and is where a device's own per-route comment belongs.

**Do not confuse this with `RoutingVrfStaticRoute` below.** They are separate kinds with separate identifiers: this one is device-level and reached through `DcimGenericDevice.static_routes`; that one is VRF-scoped, reached through `IpamVRF` and `WanSite`, and is what `transforms/frr_config.py` reads. `tests/unit/test_routing_schema_contract.py` pins both so a tidy-up cannot merge them.

### `RoutingVrfStaticRoute` — `Routing.VrfStaticRoute`

A static route originated inside a VRF. Attributes: `prefix`, `next_hop`, `description`. Relationships: `vrf` → `IpamVRF` (parent), `devices` → `DcimDevice`.

`description` is documentation only — AVD's static-route model has no such key and rejects one, so it is not emitted into the host_vars. Scoping to `devices` matters: originating a tenant default fabric-wide would black-hole traffic on every leaf with no path to the next hop.

### `RoutingVrfBgpPeer` — `Routing.VrfBgpPeer`

An eBGP neighbour inside a VRF — a workload (Cilium on a Kubernetes node) or an external router (an ISP PE, a branch router). Attributes: `ip_address`, `remote_asn`, `description`, `cleartext_password`, `send_community`, `next_hop_self`, `maximum_routes`, `route_map_in`, `route_map_out`. Relationships: `vrf` → `IpamVRF` (parent), `devices` → `DcimDevice` (both members of an MLAG pair, typically).

`route_map_in` and `maximum_routes` are the load-bearing fields: together they bound what a peer may announce and how much of it, which is what keeps a compromised node from injecting a default route or hijacking another tenant.

Prefer `cleartext_password` over a pre-hashed value. EOS type-7 ciphertext is keyed by the peer address or peer-group name, so a hash copied between peers applies cleanly and then silently fails to authenticate.

### `RoutingVrfL3Interface` — `Routing.VrfL3Interface`

A routed interface placed in a VRF, such as a firewall or WAN handoff. Attributes: `interface_name`, `ip_address`, `description`, `enabled`, `ipv4_acl_in`, `ipv4_acl_out`. Relationships: `vrf` → `IpamVRF` (parent), `device` → `DcimDevice`.

AVD takes parallel `interfaces` / `nodes` / `ip_addresses` lists; each object is one device-and-interface pair and becomes a single-element entry, so every handoff stays individually addressable with its own ACL bindings and change history. The ACL *names* are references — the ACL bodies are an AVD `ipv4_acls` input supplied through the fabric's `avd_custom_hostvars`, so a name with no matching ACL renders an interface bound to a list that does not exist.

### `EvpnDomain` — `Evpn.Domain`

An EVPN domain owned by one `NetworkFabric`. Attributes: `name`, `domain_id`, and optional `description`. Relationships: `fabric` -> `NetworkFabric` (parent), `pods` -> `NetworkPod`, `local_gateway_groups` -> `EvpnGatewayGroup` (component children), and `remote_gateway_groups` -> `EvpnGatewayGroup`. `domain_id` and `name` are unique per fabric. The hostvar generator uses `EvpnGatewayGroup.local_domain.domain_id` as the local EVPN Gateway D-PATH domain ID and `EvpnGatewayGroup.remote_domain.domain_id` as the remote D-PATH domain ID.

### `EvpnGatewayGroup` — `Evpn.GatewayGroup`

EVPN Multi-Domain Gateway intent shared by one or more Border Leaf devices in a selected Pod. Attributes include `resiliency_model` (only `all_active_multihoming`), EVPN L2/L3 enablement flags, D-PATH enablement, All-Active Multihoming enablement, and Ethernet Segment identifier/RT import values. Relationships: `local_domain` -> `EvpnDomain` (parent), `pod` -> `NetworkPod` (required non-owning context), `remote_domain` -> `EvpnDomain`, and `members` -> `DcimDevice`. The selected Pod must have `evpn_domain` set to the same object as `local_domain`, `remote_domain` must differ from `local_domain`, and group names are unique by `[local_domain, pod, name__value]`. Its schema-valid HFID uses the selected Pod and group name, while the display label and ordering include native `local_domain`, `pod`, `remote_domain`, and `name` fields. Reviewers distinguish the parent local domain from the EVPN Domain relationship view through `EvpnDomain.local_gateway_groups`; no computed or denormalized helper attribute is added solely for local-domain display.

`NetworkFabric.evpn_domains`, `NetworkPod.evpn_domain`, `NetworkPod.evpn_gateway_groups`, and `DcimDevice.evpn_gateway_group` are additive relationships from `evpn/evpn_gateway.yml`. Both `EvpnDomain` and `EvpnGatewayGroup` set `include_in_menu: false` because the custom EVPN Services menu exposes one Domains item for `EvpnDomain`; gateway groups are reached from EVPN Domain relationship views.

## Compute

### `ComputePhysicalServer` — `Compute.PhysicalServer`

A physical server. Inherits `Compute.GenericUnit`, `Dcim.GenericDevice`, and `Generator.Target`. Attributes: `name`, `role` (`compute`, `gpu`), `status`. Relationships: `rack` → `LocationRack`, `interfaces` → `DcimInterface`.

## AVD

### `AvdArtifact` — `Avd.Artifact`

Per-device container linking a device to its stored hostvars and structured config. Attributes: `name` (unique). Relationships: `device` → `DcimDevice` (required), `hostvar_file` → `AvdHostvarFile` (component), `structured_config_file` → `AvdStructuredConfigFile` (component). See [AvdArtifact & File Storage](./avd/artifacts.md).

### `AvdHostvarFile` — `Avd.HostvarFile` · `AvdStructuredConfigFile` — `Avd.StructuredConfigFile`

Child file nodes holding the per-device hostvars and structured-config JSON. Both inherit `CoreFileObject` (providing `content`, `content_type`, `checksum`) and are parented by `AvdArtifact`.

### `AvdEvpn` — `Avd.Evpn`

AVD EVPN fabric-wide settings. Attributes include `ebgp_multihop` and `overlay_bgp_rtc`. Relationships: `fabric` → `NetworkFabric`.

### `AvdTag` — `Avd.Tag`

AVD-specific fabric tag object. Attributes: `name`, `description`. Relationships: `racks` → `LocationRack`; reciprocal rack assignments emit PyAVD node-group `filter.tags`, and SVI `avd_tags` emit PyAVD SVI `tags`.

## CloudVision

### `CloudvisionWorkspace` — `Cloudvision.Workspace`

Tracks one CloudVision workspace created by the `cv-config-validation` check for a proposed change and fabric, defined in `cv/cv.yml`. Excluded from the UI menu (`include_in_menu: false`); identified by `workspace_id`.

- **Attributes**: `name` (display name), `workspace_id` (unique — the CloudVision workspace UUID), `proposed_change_id`, `workspace_url`, `thread_id` (the `CoreChangeThread` used for lifecycle comments), `change_control_id` and `change_control_url` (set when a change control exists), `last_submission_error`, `last_submission_attempt_at`, `submitted_at`, and `status`.
- **Relationships**: `fabric` → `NetworkFabric` (cardinality one).

The workspace ID is derived deterministically from the proposed-change ID and the fabric name, so re-running validation updates the same workspace rather than creating another. See [Checks](./checks.md) and [CloudVision Validation](../cloudvision.md).

Fabrics opt in through `NetworkFabric.cloudvision_managed` (Boolean, default `false`) in `logical_design.yml`; the check skips everything else when it is false.

## Deployment state

### `DeploymentState` — `Deployment.State`

One record per device, holding whether that device matches the configuration Infrahub renders for it. Defined in `deployment.yml`, shared by all four device families rather than only the AVD-rendered switches.

- **Attributes**: `name` (unique — the device's name; the record's identity), `status` (`never_deployed`, `in_sync`, `pending`, `drifted`, `failed`), `last_confirmed_at` (the last time the device was *confirmed to match*, not merely pushed to), `last_checked_at`, `last_attempt_at`, `last_error`, `suspend` (per-device break-glass) and `suspend_reason`.
- **Relationships**: `device` → `DcimGenericDevice` (cardinality one, optional, one-sided); `last_diff` → `DeploymentDiffFile` (Component).

### `DeploymentDiffFile` — `Deployment.DiffFile`

The device-computed difference between a device and its intent, from the most recent comparison that found one. Inherits `CoreFileObject`, so a first-configuration diff the size of a whole device configuration stores intact. Excluded from the UI menu; reached through its parent record.

Four properties of these kinds are deliberate and each looks like an oversight:

- **Nothing may generate from them** — no generator input, no artifact target, no trigger source. Writing state onto a device emits an event, `triggers.yml` turns node events into generator runs, a generator run regenerates artifacts, and a moved artifact is what a reconciler would act on. `tests/unit/test_deployment_schema_contract.py` fails, naming the rule, when someone adds one.
- **No `on_delete`.** Its only value, `cascade`, deletes the *peer* when the node is deleted, so on `DeploymentState.device` it would mean deleting a deployment record deletes the switch — and schema validation accepts the line without complaint.
- **`device` is optional, and identity lives on the copied `name` instead.** A relationship used in `human_friendly_id` or `uniqueness_constraints` must be mandatory, and a mandatory `device` makes any device that has ever held a record permanently undeletable. The consequence is that the graph enforces one record per *name*; keeping `name` equal to the device's name is the writer's job.
- **Both kinds are `branch: agnostic`.** Deployment state is a fact about the physical world, not about a branch: modelled branch-aware, a branch cut on Monday and merged on Friday would carry Monday's state into `main`, and every proposed change would display deployment records as proposed intent.

## Application payload attachments

### `ServiceFabricAppValuesFile` · `ServiceFabricAppManifestsFile`

An application's deployment payload — Helm values and raw Kubernetes manifests — is stored as
an attached file rather than as a JSON attribute. Both kinds inherit `CoreFileObject`, so they
carry `file_name`, `file_size`, `file_type`, `checksum` and `storage_id` without declaring
them, and the content lives in object storage rather than in the graph.

Each is reached from its application as `values_file` or `manifests_file`: a `Component`
relationship of cardinality one, so an application holds at most one of each and deleting the
application removes them.

**Why a file rather than an attribute.** Three reasons, all found by inspection:

- A JSON attribute whose keys contain a dot or a slash cannot be seeded — `infrahubctl object
  load` returns a server error for it, and every real Kubernetes payload has such keys
  (`app.kubernetes.io/name`, `grafana.ini`, `node-role.kubernetes.io/control-plane`).
- The payloads are large and opaque. One chart's values can run to 150 lines of nested
  configuration, none of which is network intent.
- They are human-authored and reviewed, and a file gives a real diff.

**Precedence.** When both a file and its corresponding attribute are set, **the file wins**.
`chart_values` and `manifests` remain as an inline escape hatch for payloads small enough not
to need a file, and are read only when no file is attached. The schema documents this rule;
it cannot enforce it.

**Content is uploaded, not loaded.** `infrahubctl object load` cannot write file content. Use
the SDK's `upload_from_bytes()` or `upload_from_path()` before the first `save()`, as
`generators/generate_avd_device_hostvar.py` does for `AvdHostvarFile`. The
`save_file_if_changed` helper in `src/solution_arista_avd/generator.py` compares checksums and
skips an upload whose content has not changed.

## Generator target

### `GeneratorTarget` — `Generator.Target` (generic)

Mixed into kinds that can be generator targets (`NetworkPod`, `LocationRack`, `ComputePhysicalServer`). Provides `checksum` (optional), which stores a hash of related node IDs for idempotent regeneration.

## Dropdown reference

**Device role** — two disjoint dropdowns since cycle 027, one per device kind:

- **`DcimFabricSwitch.role`**: `super_spine`, `spine`, `leaf`, `border_leaf`, `l2leaf`, `l2spine`, `l3spine`, `p`, `pe`, `rr`. This list must equal the keys of `ROLE_TO_AVD_TYPE` in `src/solution_arista_avd/avd.py`; `get_avd_type` raises `ValueError` on anything else, so the schema and the code state the same boundary from two directions and a test asserts the equality.
- **`DcimDevice.role`**: `isp_edge`, `isp_core`, `internet_edge`, `customer_edge`, `branch_router`, `k8s_node`. These describe equipment pyAVD never renders and are deliberately absent from `ROLE_TO_AVD_TYPE`.

There is no `firewall` value in either: a firewall is `SecurityFirewall`, its own kind.

**Interface role** (`DcimInterface.role`): `uplink`, `access`, `spine`, `super_spine`, `leaf`, `loopback`, `vtep_loopback`, `server`, `peering`, `storage`, `mlag_peer`.

**Pod role** (`NetworkPod.role`): `fabric`, `cpu`, `storage`.

**Rack type** (`LocationRack.rack_type`): `compute`, `storage`.

**Underlay routing protocol** (`NetworkFabric.underlay_routing_protocol`): `ebgp`, `ospf`, `none`, `isis-ldp`.

**Overlay routing protocol** (`NetworkFabric.overlay_routing_protocol`): `ebgp`, `ibgp`.

**Spanning-tree mode** (`NetworkFabric.spanning_tree_mode`): `mstp`, `rstp`, `rapid-pvst`, `none`.

**CloudVision workspace status** (`CloudvisionWorkspace.status`): `pending`, `built`, `submitted`, `abandoned`, `submit_failed`.

**Prefix role** (`IpamPrefix.role`): `fabric_supernet`, `fabric_point_to_point`, `dci`, `mlag`, `mlag_peering`, `supernet`, `pod_super_spine_spine`, `pod_leaf_spine`, `loopback`, `loopback-vtep`, `technical`, `management`, `backfill`, and the off-fabric lab roles `pod`, `service`, `vip_pool`, `wan_customer`, `branch_lan`, `tenant_cloud`.

**Prefix status** (`IpamPrefix.status`): `active`, `deprecated`, `reserved`.

## Role-driven pool collections

`NetworkFabric.fabric_ip_pools` is the preferred fabric-scope IP pool collection. It accepts `CoreResourcePool` members so Management address pools and Loopback, Loopback VTEP, Fabric Point-to-Point, DCI, and Fabric Supernet prefix pools can be managed through one relationship. Legacy fabric relationships remain optional during migration and are used only as fallback inputs.

`NetworkPod.pod_ip_pools` is the preferred pod-scope IP pool collection. It accepts pod-specific Loopback, Loopback VTEP, Fabric Point-to-Point, MLAG, and MLAG Peering pools. Management remains fabric-scoped.

Pool purpose is resolved from the `IpamPrefix.role` values on each pool's resources. A pool with mixed authoritative roles, duplicate role coverage in one fabric or pod, a non-IP pool in these collections, or a pod prefix outside the matching fabric prefix is invalid.

## Source {#protocols}

- [`schemas/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/schemas) — all schema definitions.
- [`schemas/base/dcim.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/base/dcim.yml) — base `Dcim.GenericDevice` / `Dcim.PhysicalDevice` / `Dcim.Device`, interfaces, `DcimDeviceType`; project device extensions (`role`, BGP ASN relationship, relations) and `Network.Link` live in [`schemas/dcim_extensions.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/dcim_extensions.yml).
- [`schemas/logical_design.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/logical_design.yml) — `Network.Fabric`, `Network.Pod`.
- [`schemas/base/location.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/base/location.yml) + [`schemas/location_extensions.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/location_extensions.yml) — `Location.Hall`, `Location.Rack`.
- [`schemas/base/ipam.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/base/ipam.yml) + [`schemas/ipam_extensions.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/ipam_extensions.yml) — IPAM nodes (the `Prefix` `role`/`status` dropdowns live in the extension).
- [`schemas/avd/avd.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/avd/avd.yml) — `Avd.Evpn`, `Avd.Tag`.
- [`schemas/objects/objects.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/objects/objects.yml) — `Avd.Artifact`, `Avd.HostvarFile`, `Avd.StructuredConfigFile` (see [AvdArtifact & File Storage](./avd/artifacts.md) for the full reference).
- [`schemas/cv/cv.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/cv/cv.yml) — `Cloudvision.Workspace`.
- [`schemas/deployment.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/deployment.yml) — `Deployment.State`, `Deployment.DiffFile`.
- [`schemas/device_design.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/device_design.yml) — `Network.DeviceDesign` and the per-container design nodes.
- Generated protocols: [`src/solution_arista_avd/protocols.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/src/solution_arista_avd/protocols.py) — regenerate after any schema change with:

  ```bash
  uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
  ```

  Note the `--out` flag (not `--output`) and the explicit path — the default would drop `schema_protocols.py` in the current directory instead of overwriting the checked-in file.
