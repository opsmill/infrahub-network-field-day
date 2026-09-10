# Acceptance Transcription Audit

**Feature**: `specs/010-lab-service-layer-model` | **Date**: 2026-09-10

Evidence for SC-003, SC-004, SC-005 and SC-007. Each lab source file is walked field
by field and every field is given a modeled destination. A field with no destination is
a gap in the schema, recorded as such rather than worked around.

Filled incrementally: US3 records the Crossplane platform and app halves (T029), US4 the
firewall (T038), US5 the access half (T044), US6 and US7 the WAN (T053, T060).

---

## SC-005a — `../lab/crossplane/platform/` (US3, task T029)

### `FabricPeering` XRD (`00-xrd-fabric-peering.yaml`)

| Lab field | Modeled destination | Notes |
| --- | --- | --- |
| `spec.localASN` | `KubernetesCluster.local_asn` | Number, 32-bit AS range |
| `spec.nodeSelector` | `KubernetesCluster.node_selector` | JSON — user-defined label map |
| `spec.authSecretName` | `KubernetesCluster.bgp_auth_secret_name` | Secret **name** only |
| `spec.timers.connectRetrySeconds` | `KubernetesCluster.bgp_timers` | JSON, all three timers |
| `spec.timers.holdTimeSeconds` | `KubernetesCluster.bgp_timers` | |
| `spec.timers.keepAliveSeconds` | `KubernetesCluster.bgp_timers` | |
| `spec.peers[].name` | `KubernetesFabricPeering.name` | one object per leaf |
| `spec.peers[].address` | `KubernetesFabricPeering.leaf_address` | → `IpamIPAddress` |
| `spec.peers[].asn` | `KubernetesFabricPeering.peer_asn` | |
| `spec.podCIDRCommunities` | `KubernetesCluster.pod_cidr_communities` | List |
| `spec.advertisementSelector` | `KubernetesCluster.advertisement_selector` and `ServiceFabricPeering.advertisement_selector` | |
| `status.peerCount` | *derived* | Count of `fabric_peerings`; a stored copy would be a second truth |

### `10-peering.yaml` instance

| Lab value | Destination | Verified |
| --- | --- | --- |
| `localASN: 65401` | `KubernetesCluster.local_asn` | ✅ |
| `peers[0]` k8s-leaf1 / `10.110.0.2` / 65101 | `KubernetesFabricPeering` + `leaf_device` → `DcimDevice` | ✅ |
| `peers[1]` k8s-leaf2 / `10.110.0.3` / 65101 | second `KubernetesFabricPeering` | ✅ |

The two peer addresses are the leaves' unique Vlan110 SVI addresses. The model's
mandatory cardinality-one `leaf_device` + `leaf_address` pair is what prevents someone
recording the shared VARP gateway `10.110.0.1` instead, since one anycast address cannot
identify a single peer.

**Result**: no gaps. Every field the composition consumes has a destination.

---

## SC-005b — `../lab/crossplane/apps/` (US3, task T029)

### `FabricApp` XRD (`00-xrd-fabric-app.yaml`)

| Lab field | Modeled destination | Notes |
| --- | --- | --- |
| `spec.namespace` | `ServiceFabricApp.namespace_name` | renamed: `namespace` is a reserved schema key |
| `spec.tenant` | `ServiceFabricApp.vrf` → `IpamVRF` | see improvement 1 below |
| `spec.chart.repository` | `ServiceFabricApp.chart_repository` | |
| `spec.chart.name` | `ServiceFabricApp.chart_name` | |
| `spec.chart.version` | `ServiceFabricApp.chart_version` | |
| `spec.chart.values` | `ServiceFabricApp.chart_values` | JSON |
| `spec.manifests` | `ServiceFabricApp.manifests` | JSON |
| presence of `spec.expose` | `ServiceFabricApp.exposed` | boolean; a schema has no optional-block construct |
| `spec.expose.vipBlock` | `ServiceFabricApp.vip_block` → `IpamPrefix` | |
| `spec.expose.serviceSelector` | `ServiceFabricApp.service_selector` | JSON |
| `spec.expose.communities` | `ServiceFabricApp.communities` | List |
| `spec.expose.advertisementSelector` | `ServiceFabricApp.peering_service` | see improvement 2 below |
| `spec.policy.defaultDeny` | `ServiceFabricApp.policy_default_deny` | |
| `spec.policy.allowDNS` | `ServiceFabricApp.policy_allow_dns` | |
| `spec.policy.allowIntraNamespace` | `ServiceFabricApp.policy_allow_intra_namespace` | |
| `spec.policy.allowEgressToAPIServer` | `ServiceFabricApp.policy_allow_egress_api_server` | |
| `spec.policy.allowEgressToInternet` | `ServiceFabricApp.policy_allow_egress_internet` | |
| `spec.policy.allowFrom` | `ServiceFabricApp.allowed_source_prefixes` → `IpamPrefix` | see improvement 3 below |
| `spec.policy.allowFromPorts` | `ServiceFabricApp.policy_allow_ports` | JSON, port/protocol pairs |
| `spec.policy.workloadSelector` | `ServiceFabricApp.workload_selector` | JSON |
| `status.namespace` | `ServiceFabricApp.namespace_name` | |
| `status.exposed` | `ServiceFabricApp.exposed` | |

### `10-demo.yaml` instance

| Lab value | Destination | Verified |
| --- | --- | --- |
| `namespace: nfd41-demo` | `namespace_name` | ✅ |
| `tenant: k8s-prod` | `vrf` → `IpamVRF` K8S_PROD | ✅ |
| `expose.vipBlock: 10.112.240.0/28` | `vip_block` → `IpamPrefix` role `vip_pool` | ✅ |
| `expose.serviceSelector` | `service_selector` | ✅ |
| `policy.allowFrom: 10.210.0.0/24` | `allowed_source_prefixes` | ✅ |
| `policy.allowFrom: 10.60.0.0/16` | `allowed_source_prefixes` | ✅ |
| `policy.allowFrom: 10.70.0.0/24` | `allowed_source_prefixes` | ✅ |
| `policy.allowFromPorts: 8080/TCP` | `policy_allow_ports` | ✅ |
| `policy.workloadSelector: app=frontend` | `workload_selector` | ✅ |
| `manifests` — 2 Deployments, 2 Services, 2 CiliumNetworkPolicies | `manifests` | ✅ |

**Result**: no gaps.

### Three deliberate modeling improvements

These change the shape relative to the lab, all in the direction the spec asks for. Each
removes a restatement rather than adding one, so a renderer can reproduce the lab's field
from the model but not vice versa.

1. **`tenant` becomes a VRF relationship, not a string.** The lab carries
   `tenant: k8s-prod` as a label value. Modeling it as `IpamVRF` means the app names the
   same object the leaves put its traffic in. A renderer derives the
   `nfd41.lab/tenant` label from `vrf.name`.

2. **`expose.advertisementSelector` becomes a `peering_service` relationship.** The XRD
   comments warn this "must match the FabricPeering's advertisementSelector, or the
   advertisement is created and never attached to a BGP session". Relating the app to its
   peering makes that mismatch impossible rather than merely detectable — the renderer
   reads the selector from the peering it is attached to.

3. **`policy.allowFrom` becomes prefix relationships, not CIDR strings.** This is
   SC-008 and the point of the feature. The same three networks are named by the vSRX
   zone policy and the leaf ACL; as relationships all three gates reference one object
   each.

---

## SC-004 — `../lab/configs/fw/vsrx/junos.conf` (US4, task T038)

Exact counts, taken from the file rather than from memory: **6 zones, 13 address
entries, 4 address sets, 11 zone pairs, 19 rules.**

An earlier draft of the spec recorded 15 addresses and 6 zone pairs. Both were wrong;
the spec, data model and task list have been corrected. The schema needed no change —
uniqueness is per zone pair, so eleven pairs are as valid as six — but SC-004 is an
acceptance criterion and had to state the real numbers.

### Zones (6/6)

| Lab zone | Interface | Destination |
| --- | --- | --- |
| `k8s-prod` | ge-0/0/0, `10.250.110.2/30` | `SecurityZone` + `interfaces` + `vrf` → K8S_PROD |
| `app-prod` | ge-0/0/1, `10.250.210.2/30` | `SecurityZone` → APP_PROD |
| `wan` | `10.250.150.2/30` | `SecurityZone` → WAN |
| `branch` | `10.250.170.2/30` | `SecurityZone` → BRANCH |
| `acme-cloud` | ge-0/0/4, `10.250.10.2/30` | `SecurityZone` → TENANT_ACME |
| `globex-cloud` | ge-0/0/5, `10.250.20.2/30` | `SecurityZone` → TENANT_GLOBEX |

Zone interface addresses become `IpamIPAddress` objects on the firewall's interfaces —
technical-layer DCIM data, not a `SecurityZone` attribute.

### Address book (13 addresses + 4 sets)

Each address → one `SecurityAddress` referencing an `IpamPrefix` (or `IpamIPAddress` for
the /32):

`k8s-nodes` 10.110.0.0/24 · `k8s-pods` 10.111.0.0/16 · `k8s-services` 10.112.0.0/16 ·
`access-portal` 10.112.240.33/32 → `ip_address` · `app-hosts` 10.210.0.0/24 ·
`fabric-infra` 10.41.0.0/16 · `wan-customers` 10.60.0.0/16 · `branch-users`
10.70.0.0/24 · `acme-hq` 10.60.10.0/24 · `acme-dr` 10.60.11.0/24 · `acme-cloud`
10.220.10.0/24 · `globex-hq` 10.60.20.0/24 · `globex-cloud` 10.220.20.0/24

Each address-set → one `SecurityAddressGroup`:

| Lab set | Members | Destination |
| --- | --- | --- |
| `acme-sites` | acme-hq, acme-dr | `SecurityAddressGroup.addresses` |
| `globex-sites` | globex-hq | `SecurityAddressGroup.addresses` |
| `k8s-all` | k8s-nodes, k8s-pods | `SecurityAddressGroup.addresses` |
| `k8s-reachable` | k8s-nodes, k8s-services | `SecurityAddressGroup.addresses` |

`acme-sites` having two members is the lab's own illustration that a tenant is not a
site — and it is why `SecurityPolicyRule` matches on groups as well as addresses.

### Zone pairs and rules (11 pairs, 19 rules)

One `SecurityPolicy` per pair, one `SecurityPolicyRule` per rule, `sequence` assigned in
file order:

| # | Zone pair | Rules (in evaluation order) | `managed_by_service` |
| --- | --- | --- | --- |
| 1 | `app-prod` → `k8s-prod` | deny-spoofed-infra, app-to-k8s-services, app-to-k8s-icmp | all false |
| 2 | `k8s-prod` → `app-prod` | deny-spoofed-infra, k8s-to-app | all false |
| 3 | `wan` → `k8s-prod` | deny-spoofed-infra, wan-to-k8s-services | all false |
| 4 | `branch` → `k8s-prod` | deny-spoofed-infra, branch-to-access-portal, branch-to-k8s-icmp | all false |
| 5 | `wan` → `acme-cloud` | deny-spoofed-infra, acme-sites-to-acme-cloud | all false |
| 6 | `wan` → `globex-cloud` | deny-spoofed-infra, globex-sites-to-globex-cloud | all false |
| 7 | `acme-cloud` → `wan` | acme-cloud-to-acme-sites | false |
| 8 | `globex-cloud` → `wan` | globex-cloud-to-globex-sites | false |
| 9 | `wan` → `app-prod` | deny-wan-to-app | false |
| 10 | `wan` → `branch` | deny-wan-to-branch | false |
| 11 | `branch` → `wan` | deny-branch-to-wan | false |

Every rule in the file today is hand-written, so every one loads with
`managed_by_service: false`. Grants issued by `ServiceAppAccess` will be the first rules
to carry `true`, and pair 4 (`branch` → `k8s-prod`) is where they land — which is
exactly why the flag exists: a generator reconciling that pair must add and remove its
own grants while leaving `deny-spoofed-infra` and `branch-to-k8s-icmp` untouched.

### Rule field mapping

| Lab construct | Destination |
| --- | --- |
| `match.source-address <name>` | `SecurityPolicyRule.source_addresses` or `source_address_groups` |
| `match.destination-address <name>` | `destination_addresses` or `destination_address_groups` |
| `match.destination-address any` | a `SecurityAddress` named `any` bound to 0.0.0.0/0 |
| `match.application <name>` | `applications` → `SecurityApplication` |
| `then permit` / `then deny` | `action` |
| `then log session-init` | `log_session_init` |
| `then log session-close` | `log_session_close` |
| policy order within a pair | `sequence`, unique per policy |

**Result**: no gaps. The five deny-only pairs (7–11) are the reason `action` needs an
explicit `deny` rather than treating absence-of-permit as the only denial mechanism —
the lab uses both, and they are different statements.

### One item deferred, deliberately

`security-zone` interface MTU (9214, the one place the vSRX profile cannot match the
rest of the lab) is DCIM interface data, not security data. It belongs on the firewall's
`DcimInterface` objects in the object cycle, not on `SecurityZone`.

---

## SC-005c — `../lab/crossplane/access/` (US5, task T044)

### `AppAccess` XRD (`01-xrd-app-access.yaml`)

| Lab field | Modeled destination | Notes |
| --- | --- | --- |
| `spec.app` | `ServiceAppAccess.name` (inherited) + `application` | catalog key becomes the service name and the app relationship |
| `spec.displayName` | `ServiceAppAccess.description` (inherited) | |
| `spec.requester` | `ServiceAppAccess.requester` | |
| `spec.justification` | `ServiceAppAccess.justification` | TextArea |
| `spec.approved` | `ServiceAppAccess.approved` | Boolean, default false — the gate |
| `spec.approvedBy` | `ServiceAppAccess.approved_by` | |
| `spec.source.zone` | `ServiceAppAccess.source_zone` → `SecurityZone` | |
| `spec.source.address` | `ServiceAppAccess.source_address` → `SecurityAddress` | |
| `spec.source.cidr` | *collapsed* — see improvement 4 | |
| `spec.access.vip` | `ServiceAppAccess.destination_vip` → `IpamIPAddress` | |
| `spec.access.ports` | `ServiceAppAccess.ports` | List |
| `spec.provision.namespace` | `ServiceFabricApp.namespace_name` | provisioning is a FabricApp concern |
| `spec.provision.image` | `ServiceFabricApp.manifests` | |
| `spec.provision.containerPort` | `ServiceFabricApp.manifests` | |
| `spec.provision.vipBlock` | `ServiceFabricApp.vip_block` | |
| `spec.provision.replicas` | `ServiceFabricApp.manifests` | |
| `status.phase` | `ServiceGeneric.status` | `provisioning` / `active` / `error` covers PendingApproval, Provisioning, Granted |
| `status.vip` | `destination_vip` | |
| `status.provisioned` | `application` presence | |

### `FirewallAccess` CRD (`00-crd-firewall-access.yaml`)

| Lab field | Modeled destination | Notes |
| --- | --- | --- |
| `spec.sourceZone` | `ServiceAppAccess.source_zone` | |
| `spec.sourceAddress` | `ServiceAppAccess.source_address` | |
| `spec.destinationZone` | `ServiceFabricApp.vrf` → `SecurityZone.vrf` | derived: the zone whose VRF the app sits in |
| `spec.destination` | `ServiceAppAccess.destination_vip` | |
| `spec.ports` | `ServiceAppAccess.ports` | |
| `spec.requester` | `ServiceAppAccess.requester` | |
| `spec.justification` | `ServiceAppAccess.justification` | |
| `status.policyRef` | `granted_rules` → `SecurityPolicyRule` | the graph path replaces the string `"branch->k8s-prod/aa-access-grafana"` |
| `status.portSummary` | `ports` | |
| `status.conditions` | `ServiceGeneric.status` | |

**Result**: no gaps.

### A fourth deliberate improvement

4. **`spec.source.cidr` disappears.** The lab carries the source twice — once as a Junos
   address-book name for the firewall and once as a CIDR for the Cilium policy, with the
   XRD noting "both gates have to agree". Because `SecurityAddress` already references an
   `IpamPrefix`, one relationship serves both: the firewall renderer reads the address
   object's name, the Cilium renderer reads the same object's prefix. The two gates
   cannot disagree because there is only one fact.

### One item the schema makes detectable but cannot enforce

US5 acceptance scenario 4 — a `destination_vip` outside the range the border leaf
re-advertises to the source — is a prefix-containment question between two IPAM objects.
The schema puts both in the graph so a query can answer it; the check that fails it is a
`checks/` cycle item, recorded in data-model.md section 13.

---

## SC-003 — `../lab/wan/tenants.yml` (US6, task T053)

### The ISP block

| Lab field | Modeled destination |
| --- | --- |
| `isp.asn: 65500` | `OrganizationProvider` + `RoutingAsn` |
| `isp.dc_service_prefixes` (`10.112.240.0/24`) | `ServiceL3vpn.dc_service_prefixes` → `IpamPrefix` (US7) |
| `isp.internet.asn: 64500` | `WanInternetPeering.peer_asn` + a second `OrganizationProvider` |
| `isp.internet.router: internet-rtr` | `DcimDevice` role `internet_edge` |
| `isp.internet.customer_aggregate: 10.60.0.0/16` | `WanInternetPeering.customer_aggregate` |
| `isp.internet.peering.node: isp-pe2` | `WanInternetPeering.provider_interface` → device |
| `isp.internet.peering.interface: eth3` | `WanInternetPeering.provider_interface` |
| `isp.internet.peering.address: 10.52.0.1/30` | `IpamIPAddress` on that interface |
| `isp.internet.peering.router_interface: eth1` | `WanInternetPeering.peer_interface` |
| `isp.internet.peering.peer: 10.52.0.2` | `IpamIPAddress` on that interface |
| `isp.internet.host.*` (`internet-host`, `198.51.100.10/24`) | `DcimDevice` + `IpamIPAddress` |
| `isp.internet.lan: 198.51.100.0/24` | `WanInternetPeering.internet_prefixes` |
| `isp.internet.lan_interface` / `lan_address` | `DcimInterface` + `IpamIPAddress` |
| `isp.edge.node: isp-pe1` | `DcimDevice` role `isp_edge` |
| `isp.edge.loopback: 10.50.0.1` | `IpamIPAddress` on a loopback interface |
| `isp.edge.core.*` (`eth1`, `10.50.255.1/30`, peer `.2`) | `DcimInterface` + `IpamIPAddress` + `NetworkLink` |
| `isp.core.node: isp-pe2` | `DcimDevice` role `isp_core` |
| `isp.core.loopback: 10.50.0.2` | `IpamIPAddress` |
| `isp.core.dc.*` (`eth2`, `10.250.50.2/30`, peer `.1`, peer_asn 65103) | `RoutingBGPNeighbor` to border-leaf1 |
| `mtu: 9214` | `WanCircuit.mtu` (default) |

The peering's two-sided `interface` / `router_interface` split is exactly what
`WanCircuit` and `WanInternetPeering` model as separate relationships — the lab's own
comment explains why: "Two names because they are two devices."

### Tenant `acme` — the fleshed-out case

| Lab field | Modeled destination |
| --- | --- |
| `name: acme` | `WanTenant.name` + `OrganizationCustomer` "acme" |
| `id: 10` | `WanTenant.tenant_id` |
| `vrf: CUST_ACME` | `WanTenant.vrf_name` |
| `vrf_table: 1010` | `WanTenant.vrf_table_id` |
| `internet: true` | **presence of a `ServiceInternetAccess`** (US7) — SC-007 |
| `dc.vrf: TENANT_ACME` | `WanTenant.dc_vrf` → `IpamVRF`, and `ServiceTenantCloud.vrf` |
| `dc.zone: acme-cloud` | `ServiceTenantCloud.zone` → `SecurityZone` |
| `dc.subnet: 10.220.10.0/24` | `ServiceTenantCloud.prefix` → `IpamPrefix` role `tenant_cloud` |
| `dc.hosts[]` (`acme-cloud1`, `10.220.10.10/24`, gw `.1`) | `DcimDevice` / `ComputePhysicalServer` + `IpamIPAddress` |
| `sites[0].name: hq` | `WanSite.name` |
| `sites[0].kind: bgp` | `WanSite.attachment_kind` = `bgp` |
| `sites[0].asn: 65010` | `WanSite.site_asn` |
| `sites[0].lan: 10.60.10.0/24` | `WanSite.lan_prefix` role `wan_customer` |
| `sites[0].pe.node/interface/address` | `WanCircuit.provider_edge_interface` + `provider_edge_address` |
| `sites[0].ce.node/wan_interface/wan_address` | `WanCircuit.customer_edge_interface` + `customer_edge_address` |
| `sites[0].ce.lan_interface/lan_address` | `DcimInterface` + `IpamIPAddress` on the CE |
| `sites[0].host.*` | `DcimDevice` + `IpamIPAddress` |
| *(implied by `kind: bgp`)* | `WanCircuit.bgp_session` → `RoutingBGPNeighbor` |
| `sites[1].name: dr` | `WanSite.name` |
| `sites[1].kind: static` | `WanSite.attachment_kind` = `static`, **no** `site_asn` |
| `sites[1].lan: 10.60.11.0/24` | `WanSite.lan_prefix` |
| `sites[1].pe.*` / `ce.*` / `host.*` | as above |
| *(implied by `kind: static`)* | `WanCircuit.static_routes` → `RoutingVrfStaticRoute` |

Both sites belong to one `WanTenant`, so they share one `ServiceL3vpn` and reach each
other by VPN membership. There is deliberately no site-to-site relationship, which is
the lab's point: "they reach each other because they share a VRF, not because anything
was leaked between them."

### Tenant `globex` — the control

Identical structure: `id: 20`, `CUST_GLOBEX` / `1020`, `internet: false`, `dc` block
→ `TENANT_GLOBEX` / `globex-cloud` / `10.220.20.0/24`, one `bgp` site with ASN 65020 and
LAN `10.60.20.0/24`. Every field has the same destination as acme's.

### The branch office

| Lab field | Modeled destination |
| --- | --- |
| `branch.name: branch` | `WanTenant.name`, **`kind: internal`** |
| `branch.asn: 65030` | `WanSite.site_asn` |
| `branch.loopback: 10.70.255.1` | `IpamIPAddress` on a loopback |
| `branch.lan: 10.70.0.0/24` | `WanSite.lan_prefix` role `branch_lan` |
| `branch.router.node: branch-rtr` | `DcimDevice` role `branch_router` |
| `branch.router.dc_interface/dc_address` | `WanCircuit.customer_edge_interface` + address |
| `branch.router.dc_peer: 10.250.70.1` | `WanCircuit.provider_edge_address` — on **border-leaf1** |
| `branch.router.dc_peer_asn: 65103` | `WanCircuit.bgp_session` → `RoutingBGPNeighbor` |
| `branch.router.lan_bridge: br-branch` | `InterfaceVirtual` on the branch router |
| `branch.router.lan_address: 10.70.0.1/24` | `IpamIPAddress` on that bridge |
| `branch.router.lan_interfaces[]` (eth2–eth4) | `DcimInterface` objects enslaved to the bridge |
| `branch.hosts[]` (branch-host, branch-desktop, branch-guacd) | `DcimDevice` + `IpamIPAddress` |

The branch's circuit terminates on `border-leaf1`, not on a PE. That works without a
special case because `WanCircuit.provider_edge_interface` peers the `DcimInterface`
generic rather than a PE-specific kind.

The switched LAN — three devices sharing `10.70.0.0/24`, reachable directly so guacd can
open a VNC session to the desktop without leaving the site — is modeled as one
`lan_prefix` with three host addresses on it, plus the bridge interface. Not a link per
host, which is what the lab warns against.

**Result**: no gaps. Every field of `wan/tenants.yml` has a destination.

### One deliberate improvement

5. **`internet: true|false` becomes the presence or absence of an object.** The lab
   carries it as a boolean on the tenant. Modeling it as a `ServiceInternetAccess`
   service is what makes SC-007 true — the only difference between acme and globex
   becomes one object rather than one field, which is the layering claim in miniature.

---

## SC-007 — acme and globex differ by exactly one object (US7, task T060)

The criterion: *"The difference between the lab's two WAN tenants is expressible as the
presence of one internet-access service and nothing else."*

### Field-by-field comparison of the two tenants in `wan/tenants.yml`

| Lab field | acme | globex | Same shape? |
| --- | --- | --- | --- |
| `name` | acme | globex | ✅ both `WanTenant.name` |
| `id` | 10 | 20 | ✅ both `tenant_id` |
| `vrf` | CUST_ACME | CUST_GLOBEX | ✅ both `vrf_name` |
| `vrf_table` | 1010 | 1020 | ✅ both `vrf_table_id` |
| `dc.vrf` | TENANT_ACME | TENANT_GLOBEX | ✅ both `ServiceTenantCloud.vrf` |
| `dc.zone` | acme-cloud | globex-cloud | ✅ both `ServiceTenantCloud.zone` |
| `dc.subnet` | 10.220.10.0/24 | 10.220.20.0/24 | ✅ both `ServiceTenantCloud.prefix` |
| `dc.hosts` | acme-cloud1 | globex-cloud1 | ✅ both DCIM + IPAM |
| `sites` | hq (bgp), dr (static) | hq (bgp) | ✅ both `WanSite`; acme simply has two |
| **`internet`** | **true** | **false** | ❌ **the one difference** |

Every row but the last maps to the same kind and the same field on both tenants, with
only the values differing. The last row is the one that becomes structural.

### How the difference is expressed in the model

| | acme | globex |
| --- | --- | --- |
| `WanTenant` | 1 | 1 |
| `WanSite` | 2 | 1 |
| `WanCircuit` | 2 | 1 |
| `ServiceL3vpn` | 1 | 1 |
| `ServiceTenantCloud` | 1 | 1 |
| **`ServiceInternetAccess`** | **1** | **0** |

No field anywhere says "globex does not buy internet access". The object is simply
absent, which is the same shape the lab's route policy has — `RM-GLOBEX-IMPORT` has no
`permit 30` clause, so no default route enters globex's VRF and its prefixes are never
announced upstream. Nothing out there has a route back either.

`ServiceInternetAccess` carries no `tenant`, `vrf`, `circuits` or `sites` relationship,
which is what keeps this true: had it duplicated any of them, the two tenants would
differ in a second place and the criterion would be a claim rather than a fact.
`test_internet_access_duplicates_nothing_the_l3vpn_holds` asserts that emptiness.

### The site count is not a second difference

acme has two sites and globex has one, but that is a difference in *how many* objects of
the same kind exist, not in which kinds exist or which fields are set. The lab makes the
same distinction: `acme-sites` is an address-set with two members and `globex-sites` has
one, and adding a third acme site is "one line here, not a new policy".

**Result**: SC-007 satisfied.

---

## Summary

| Criterion | Source | Result |
| --- | --- | --- |
| SC-003 | `../lab/wan/tenants.yml` | ✅ no gaps |
| SC-004 | `../lab/configs/fw/vsrx/junos.conf` | ✅ no gaps (counts corrected: 11 zone pairs, 19 rules) |
| SC-005 | `../lab/crossplane/{platform,apps,access}/` | ✅ no gaps |
| SC-007 | acme vs globex | ✅ one object |

Five deliberate modeling improvements were made, each removing a restatement rather than
adding one: the app tenant becomes a VRF relationship; the advertisement selector becomes
a peering relationship; `allowFrom` becomes prefix relationships; the access grant's
duplicate source CIDR collapses into one address object; and `internet: true|false`
becomes the presence or absence of a service. In every case a renderer can reproduce the
lab's field from the model, but not the reverse — which is the direction that makes the
model the source of truth rather than a copy of one.
