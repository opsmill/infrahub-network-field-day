---
title: Supported capabilities
description: What this Arista AVD reference design supports today, what is partial, and what is not yet covered.
---

# Supported capabilities

This is a **reference design** that covers a defined set of AVD capabilities on Infrahub — it is not a full replacement for every AVD feature. Uncommon or highly customized AVD options may not be modeled. Use the matrix below to check the status of a capability before planning a deployment.

**Status key:** ✅ Supported today · 🟡 Partial / confirm scope · ⬜ Not yet

:::note
Some boundaries below are marked *confirm scope* and are being finalized with the maintainers. Where a row says `confirm`, treat the exact edge as undecided rather than guaranteed.
:::

## The modelled fabric

This fork models one fabric: **`NFD41_FABRIC`**, the containerlab topology deployed for Network Field Day 41. Upstream's seven example designs were removed — the seed data describes the deployed lab and nothing else, so there is exactly one source of truth and no cross-fabric numbering collisions.

| Aspect | What it is |
|--------|------------|
| Topology | Single-pod 3-stage L3LS: two spines, two MLAG leaf pairs (`K8S_LEAFS`, `APP_LEAFS`) and a single non-MLAG `BORDER_LEAFS` node. |
| Underlay / overlay | eBGP underlay, eBGP EVPN overlay, ASNs per MLAG pair (`65100` spines, `65101`-`65103` leaves). |
| Tenants | Four tenants, six VRFs: `K8S_PROD`, `APP_PROD`, `TENANT_ACME`, `TENANT_GLOBEX`, `WAN`, `BRANCH`. No route leaking anywhere. |
| Service insertion | Every tenant VRF's only route out is a default pointing at its own firewall zone, originated on the border leaf. The firewall is unavoidable rather than a policy that could be bypassed. |
| Workload BGP | Cilium peers eBGP from each k3s node into `K8S_PROD`, bounded by `RM-CILIUM-IN` and `maximum_routes`. |
| Platform | Arista cEOS-LAB containers. |

The numbering a running lab fixes — node ID, management address, loopback, ASN — is pinned in `objects/26_nfd41_devices.yml` and preserved by the generators, because the fabric's route targets and BGP communities already reference it. Everything genuinely design-driven is generated: uplink and MLAG cabling, interface expansion, point-to-point and MLAG peer addressing, host_vars, structured config.

Hostnames are the generators' (`spine-{pod}-{index}`, `leaf-{pod}-{rack_index}-{index}`) and the lab is redeployed under them. The seed data spells the same names out only because the generators upsert devices by name.

**Parity is asserted, not assumed.** `tests/integration/test_nfd41_fabric.py` boots a real Infrahub stack, runs the generator chain, renders the EOS configuration for all seven switches and compares it byte for byte against the configuration the lab is deployed with (`tests/integration/golden/nfd41/`). A diff there is a regression.

The schema still carries the roles and underlay choices the upstream examples used (`l2leaf`, `l2spine`, `l3spine`, `p`, `pe`, `rr`; `ospf`, `isis-ldp`, `none`), so those designs remain expressible — there is simply no seed data for them here.

## Fabric generation

| Capability | Status | Notes |
|------------|:------:|-------|
| Generate a full fabric (Fabric → Pod → Rack → Device) from a design | ✅ | Super-spines, spines, and leaves are created from device templates — no per-device host_vars authored manually. |
| Cable devices together automatically | ✅ | Uplinks and device-to-device links created by the generators. |
| Regenerate idempotently | ✅ | Checksum-based change detection skips work when nothing changed; re-running is safe. |

## Addressing & numbering

| Capability | Status | Notes |
|------------|:------:|-------|
| Allocate loopback, interconnect, and management prefixes/IPs from pools | ✅ | Drawn from branch-aware pools so parallel work does not collide. |
| Allocate DCI point-to-point /31 prefixes from fabric DCI pool roles | ✅ | Generated DCI `l3_edge` addressing resolves from `NetworkFabric.fabric_ip_pools` role `dci` first, legacy `NetworkFabric.dci_pool` second, and deterministic Fabric Supernet fallback when the required DCI prefix-pool role is missing. |
| Allocate BGP ASNs and node IDs from pools | ✅ | Assigned automatically during generation. |

<!-- vale Google.Headings = NO -->
<!-- Every word here is an accepted acronym, but Vale still reads the heading as
     title case. Scoped off rather than reworded, so the published anchor is
     unchanged. -->
## Services (VLAN / EVPN / VRF / MLAG / LAG / routing)
<!-- vale Google.Headings = YES -->

| Capability | Status | Notes |
|------------|:------:|-------|
| Model VLANs and L2 domains | ✅ | Defined in the source of truth and rendered into config. |
| Fabric-level EVPN settings | ✅ | Fabric EVPN overlay configuration. Exact EVPN depth is being confirmed. |
| EVPN Multi-Domain Gateway on Border Leafs | 🟡 | Models Fabric-owned `EvpnDomain` objects with domain-owned local `EvpnGatewayGroup` children for `border_leaf` devices, then emits PyAVD EVPN Gateway hostvars for All-Active Multihoming only. Pods remain selected context and must point at the group's local domain. MLAG, Anycast IP, route-server, and route-reflector gateway models are not included. |
| EVPN L3 VRFs | 🟡 | Wired into the PyAVD hostvar generator and produce config. The maintainers flagged `we don't do VRF and route targets` — **confirm** whether the exclusion is VRF-lite, route-leaking, or explicit route targets. |
| MLAG (domain + peer) | 🟡 | Modeled and wired into hostvars; **confirm** supported scope. |
| Server LAG | 🟡 | Modeled and wired into hostvars; **confirm** supported scope. |
| BGP peer groups | 🟡 | Wired into hostvars and produce config; **confirm** supported scope. |
| DCI links between Border Leafs | ✅ | `NetworkLink` objects with `role=dci` reuse shared physical endpoints and generate PyAVD `l3_edge.p2p_links`; external networks and EVPN Gateway are out of scope for this phase. |
| Route targets | 🟡 | Modeled but AVD-derived (not fed as input). |
| VRF static routes | ✅ | `Routing.VrfStaticRoute` objects, each scoped to the devices that originate it. |
| VRF BGP peers | ✅ | `Routing.VrfBgpPeer` objects with password, communities, `maximum_routes` and in/out route maps. |
| VRF L3 interfaces (firewall / WAN handoffs) | ✅ | `Routing.VrfL3Interface` objects with inbound and outbound ACL bindings. |
| Per-node SVI addresses + VARP gateway | ✅ | `Evpn.SviNode` plus `Evpn.Svi.ip_virtual_router_addresses`, for SVIs a workload peers BGP over. |
| ACL, prefix-list and route-map *contents* | 🟡 | Supplied through the fabric's `avd_custom_hostvars` escape hatch; the interface and peer *bindings* are native. |
| Prefix lists, route maps, static routes (reconciled) | 🟡 | The backfill generator still reconciles what AVD derives; authored inputs take precedence. |

## Rendering & artifacts

| Capability | Status | Notes |
|------------|:------:|-------|
| Render Arista EOS device configurations (PyAVD) | ✅ | Deploy-ready per-device EOS CLI, as downloadable artifacts. |
| Fabric and per-device documentation (Markdown) | ✅ | Generated from the same source of truth as the config. |
| Cabling plan (CSV) | ✅ | One row per connection for the field/cabling team. |
| Computed interface descriptions | ✅ | Consistent, auto-maintained interface descriptions. |
| ANTA test catalog (per device, YAML) | ✅ | Catalog **generation** is included (gated by the fabric `anta_enabled` flag). Execution is not yet included — see below. |

## Validation (ANTA)

| Capability | Status | Notes |
|------------|:------:|-------|
| ANTA test-catalog generation | ✅ | The `avd_anta_catalog` transform, gated by `anta_enabled`. |
| ANTA execution / block-merge-on-failure | ⬜ | Running the tests and blocking merges on failure is on the roadmap. |

## Validation (CloudVision)

| Capability | Status | Notes |
|------------|:------:|-------|
| CloudVision config validation in a proposed change | ✅ | The `cv-config-validation` check deploys the rendered configs to a CloudVision workspace and blocks the proposed change on a failed build. Opt in per fabric with `cloudvision_managed`. See [CloudVision Validation](./cloudvision.md). |
| Workspace tracking and review link | ✅ | Each workspace is recorded as a `CloudvisionWorkspace` object and its URL posted to the proposed change. |
| Workspace submission | 🟡 | Submission runs from a `CoreCustomWebhook` on proposed-change merge, or manually via `invoke submit-cv-workspace`. The shipped webhook target is a placeholder URL, not a production receiver. |
| CloudVision change-control management | ⬜ | Out of scope for this phase. |

## Lab

| Capability | Status | Notes |
|------------|:------:|-------|
| ContainerLab topology per fabric | ✅ | The `containerlab_topology` artifact renders every device and link the fabric owns; kinds, images, and interface mappings come from schema attributes. See [ContainerLab](./containerlab.md). |
| Deploying the generated topology | ✅ | `ansible/deploy_clab.yml` stages the topology, EOS configs, and bind sources on a ContainerLab host and deploys them. The Semaphore template fetches and stages only — it does not deploy. |
| ISIS-LDP devices in the generated topology | ⬜ | The `p`, `pe`, and `rr` roles are excluded; their interface naming is not validated against ContainerLab. |

## Deployment

| Capability | Status | Notes |
|------------|:------:|-------|
| Deploy configurations to devices | ✅ | Through the bundled Ansible runner or CloudVision (CVP/CVaaS). |

## Interfaces & change management

| Capability | Status | Notes |
|------------|:------:|-------|
| Self-service portal (Streamlit) for guided provisioning | ✅ | Alongside the Infrahub Web UI, GraphQL API, and MCP. |
| Branches, proposed changes, approvals, full lineage | ✅ | Standard Infrahub platform change management. |
| Approval rules that vary by service type | ⬜ | You can require approvals, but per-service approval rules are on the roadmap. |

## Brownfield & coverage

| Capability | Status | Notes |
|------------|:------:|-------|
| Self-serve brownfield import | 🟡 | Modeling an existing fabric and importing configs via Infrahub Sync is done today in a **guided engagement**, not as a download-and-try path. |
| Every AVD feature | ⬜ | This reference design covers a defined set of AVD inputs and scenarios, implemented per customer; uncommon or highly custom options may not be modeled. |

## Fabric pool management

| Capability | Status | Notes |
|------------|:------:|-------|
| Role-driven fabric pool collection | ✅ | `NetworkFabric.fabric_ip_pools` covers Management, Loopback, Loopback VTEP, Fabric Point-to-Point, DCI, and Fabric Supernet roles. |
| Pod-scoped pool collection and containment validation | ✅ | `NetworkPod.pod_ip_pools` supports pod Loopback, VTEP, Fabric Point-to-Point, MLAG, and MLAG Peering roles with parent-fabric containment checks. |
| Legacy pool migration compatibility | ✅ | Legacy fabric and pod pool relationships remain optional and seed data is dual-populated during migration. |
| Deterministic fallback/default pools | ✅ | Fabric Supernet fallback creates stable prefix pools; MLAG defaults use stable `/31` pool objects. |
