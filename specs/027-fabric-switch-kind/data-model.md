# Phase 1 Data Model: A Device Kind for Fabric Switches

**Cycle**: 027 | **Date**: 2026-09-14

One new node, twelve fields moved, two role dropdowns split. Everything else follows from those.

## The four device kinds, after

All inherit `DcimGenericDevice`, so anything peering that generic sees all four — verified live in
[research.md](./research.md) R2, where `DcimGenericDevice` returned 23 objects across four kinds.

| Kind | Holds | Rendered by |
| --- | --- | --- |
| **`DcimFabricSwitch`** *(new)* | spines, leaves, border leaves | PyAVD → EOS config |
| `DcimDevice` *(narrowed)* | the WAN's FRR routers | `frr_config` |
| `SecurityFirewall` | `fw1` | `junos_config` |
| `ComputePhysicalServer` | k8s nodes, hosts, cloud instances | — |

The first two are the change. The last two are untouched, and `SecurityFirewall` is the worked
example being copied.

## `DcimFabricSwitch`

```yaml
  - name: FabricSwitch
    namespace: Dcim
    label: Fabric Switch
    inherit_from:
      - CoreArtifactTarget      # it carries artifacts
      - DcimGenericDevice       # name, description, interfaces, platform, static_routes, …
      - DcimPhysicalDevice      # position, serial, rack_face
```

`inherit_from` is copied verbatim from `DcimDevice` rather than redesigned. All three are needed:
`CoreArtifactTarget` because EOS configs, device docs and ANTA catalogs attach to switches;
`DcimGenericDevice` so the polymorphic relationships keep resolving; `DcimPhysicalDevice` because
a switch is rack-mounted.

## The twelve fields that move

| Field | Kind | Why it is fabric-only |
| --- | --- | --- |
| `vtep_loopback_ip` | Relationship | VXLAN tunnel endpoint; an FRR router has none |
| `mlag_domain` | Relationship | MLAG is a switch-pair concept |
| `evpn_gateway_group` | Relationship | valid on `border_leaf` alone — see below |
| `node_id` | Number | AVD node identifier |
| `index` | Number | position within a rack pair |
| `pod` | Relationship | fabric hierarchy |
| `rack` | Relationship | fabric hierarchy |
| `avd_artifact` | Relationship | the AVD hostvar/structured-config container |
| `object_template` | Relationship | `TemplateDcimDevice`, a fabric construct |
| `loopback_ip` | Relationship | router-id loopback in AVD's sense |
| `mgmt_ip` | Relationship | fabric management addressing |
| `avd_custom_hostvars` | JSON | the PyAVD escape hatch |

### `evpn_gateway_group` is the clearest case

Zero objects exist, on any device. It is valid on one role out of thirteen, and the only thing
preventing misuse is a runtime exception in `generators/generate_avd_device_hostvar.py`:

```python
if role != "border_leaf":
    raise _gateway_error(gateway, hostname,
        f"target device role must be 'border_leaf'; actual role is {role!r}")
```

That guard exists **because the schema cannot express the constraint**. Moving the field is a step
toward the model stating it. The guard stays — it still enforces border-leaf-only *within* the
fabric kind — but it stops being the only thing between a router and a meaningless field.

## What stays on `DcimDevice`

| Field | Why |
| --- | --- |
| `router_id` | populated on 6 of 7 routers, on no switch |
| `bgp_neighbors` | the WAN's eBGP sessions |
| `location` | routers sit at sites, not in racks |

## What both kinds need

`status`, `role`, `rack_face`, `asn`, `device_type`, `platform`.

`device_type` and `platform` come from cycle 026, which gave every device both. That guarantee
must survive this split — SC-007.

### `role` is the one field that differs in shape

Both kinds have a `role` dropdown, with **different choices**:

| Kind | Choices |
| --- | --- |
| `DcimFabricSwitch` | the ten in `ROLE_TO_AVD_TYPE`: `super_spine`, `spine`, `leaf`, `border_leaf`, `l2leaf`, `l2spine`, `l3spine`, `p`, `pe`, `rr` |
| `DcimDevice` | `isp_edge`, `isp_core`, `internet_edge`, `customer_edge`, `branch_router`, `k8s_node` |

This is the split expressed in the model. `get_avd_type` already raises on an unmapped role, so
the code guard and the schema now say the same thing from two directions.

**Consequence for queries**: `role` must stay on concrete fragments, never moved to the generic —
the two dropdowns are different enumerations.

## Consumers, and what each needs

### Retarget to the new kind

| Site | Change |
| --- | --- |
| `generators/avd_device_hostvar.gql:2` | `DcimDevice(` → `DcimFabricSwitch(` |
| `transforms/avd_device_config.gql:2` | same |
| `transforms/avd_anta_catalog.gql:2` | same |
| `generators/generate_pod.py:244` | `kind=DcimDevice` → `kind=DcimFabricSwitch` |
| `generators/generate_rack.py:179` | same |
| `generators/generate_server_cabling.py:56` | same |
| `generators/asn.py:46` | same |
| `src/solution_arista_avd/generator.py:712` | `client.create(DcimDevice, …)` → the new kind |

### Read from the generic instead of adding a fragment

Preferred wherever the field lives on `DcimGenericDevice`, because it fixes every kind at once —
the remedy cycle 026 applied to the cabling plan.

| Site | Field | Action |
| --- | --- | --- |
| `transforms/containerlab_topology.gql:17, :97` | `name` | `... on DcimDevice` → `... on DcimGenericDevice` |
| `service_catalog/pages/4_Fabric_View.py:281, :287` | `interfaces` | same |
| `service_catalog/pages/4_Fabric_View.py:92, :341, :349` | `name`, `role` | `name` from the generic; `role` needs both concrete fragments |

### Add a concrete fragment

`rack` is genuinely concrete and moves to the new kind.

| Site | Action |
| --- | --- |
| `transforms/cabling_plan.gql:52` | add `... on DcimFabricSwitch { rack { … } }` |
| `transforms/cabling_plan.py:83, :96` | same |

**These degrade rather than break.** Cycle 026 moved `name` onto the generic, so the guard
`if src_dev_name and dst_dev_name` still passes for a switch and the cable row is still emitted —
only the rack column empties. Worth knowing, because it means the cabling plan cannot silently
lose cables again.

### Must not change

`transforms/frr_config.gql` — two `DcimDevice(...)` filters, both targeting routers.

## Objects

| File | Change |
| --- | --- |
| `objects/26_nfd41_devices.yml` | `spec.kind: DcimDevice` → `DcimFabricSwitch` |
| `objects/31_nfd41_offfabric_devices.yml` | unchanged — routers keep the kind |
| `objects/31a_nfd41_wan_addressing.yml` | unchanged — same |

## Migration

**None.** The environment is destroyed and rebuilt, on the requester's decision. The seven
switches are *seeded*, so changing `spec.kind` plus a rebuild is the entire data story. Infrahub
offers no in-place kind change, so without that decision this cycle would need one built by hand.

## What this cycle does not touch

- The eleven fields unused by both kinds — a separate question about dead versus aspirational.
- `SecurityFirewall`, `ComputePhysicalServer` — already their own kinds.
- `RoutingStaticRoute.device` — cycle 024 widened it to the generic; it needs nothing.
- The ContainerLab transform's fabric-only scope — unchanged by request, and orthogonal to this.
