# Schema Contract: A Device Kind for Fabric Switches

**Cycle**: 027 | **Consumed by**: `tests/unit/test_dcim_schema_contract.py` (new),
`tests/unit/test_device_type_and_platform.py` (extended), `tests/unit/test_avd.py` (extended)

Every clause is an assertion against the schema YAML, the object files, or rendered output. The
YAML clauses need no running Infrahub; the ones marked **live** are checked in
[quickstart.md](../quickstart.md) instead.

## C1 — The node exists and inherits exactly three generics

`schemas/base/dcim.yml` declares a node `FabricSwitch` in namespace `Dcim` whose `inherit_from`
is exactly `[CoreArtifactTarget, DcimGenericDevice, DcimPhysicalDevice]` — the same list
`DcimDevice` carries, in the same order.

Asserted as an **exact list**, not a superset. A fourth generic appearing later is a design change
that should fail a test rather than land quietly.

## C2 — The twelve moved fields

| Field | On `DcimFabricSwitch` | On `DcimDevice` |
| --- | --- | --- |
| `vtep_loopback_ip`, `mlag_domain`, `evpn_gateway_group` | present | **absent** |
| `node_id`, `index`, `avd_custom_hostvars` | present | **absent** |
| `pod`, `rack`, `avd_artifact`, `object_template` | present | **absent** |
| `loopback_ip`, `mgmt_ip` | present | **absent** |

Both directions are asserted. Presence alone would pass if the field were copied rather than
moved, which is the likeliest way to get this half-right.

## C3 — The three fields that stay

`router_id`, `bgp_neighbors` and `location` are on `DcimDevice` and **not** on
`DcimFabricSwitch`.

`bgp_neighbors` is the one worth naming: its reverse side is `RoutingBGPNeighbor.device`, which
holds ten objects, **all on routers** (measured). Moving it would break the WAN for no gain.

## C4 — The six shared fields

`status`, `role`, `rack_face`, `asn`, `device_type` and `platform` resolve on **both** kinds,
whether declared directly or inherited.

## C5 — The two role dropdowns are disjoint and exhaustive

| Kind | Choices |
| --- | --- |
| `DcimFabricSwitch` | exactly the ten keys of `ROLE_TO_AVD_TYPE` |
| `DcimDevice` | exactly `isp_edge`, `isp_core`, `internet_edge`, `customer_edge`, `branch_router`, `k8s_node` |

Three assertions, not one:

1. `DcimFabricSwitch`'s choice set **equals** `ROLE_TO_AVD_TYPE.keys()`. This replaces
   `test_schema_roles_all_mapped`'s current shape, which excludes `NON_AVD_DEVICE_ROLES` by hand
   because both sets lived in one dropdown. After the split the exclusion list is unnecessary
   there — the kinds separate what the list used to.
2. `DcimDevice`'s choice set is **disjoint** from `ROLE_TO_AVD_TYPE`. A fabric role reappearing on
   the router kind is how the split would silently undo itself.
3. Their union equals today's sixteen values. Nothing is lost in the split; if a role should be
   retired, that is a separate decision made visibly.

## C6 — The reverse sides, which are more numerous than the moved fields

**This is the clause a reader working from FR-005's list of twelve would miss.** There are
**thirteen** `peer: DcimDevice` sites across `schemas/`, and four of the seven that must change
have **no forward side on `DcimDevice` at all** — the device end is declared only on the related
node, so nothing in the twelve-field list points at them.

Each site's disposition was decided by **counting the objects actually attached**, not by reading
the field name.

### C6a — Seven become `DcimFabricSwitch`

| Site | Relationship | Objects, and on what |
| --- | --- | --- |
| `schemas/logical_design.yml:169` | `NetworkPod.devices` | 7, all switches |
| `schemas/objects/objects.yml:21` | `AvdArtifact.device` | 7, all switches |
| `schemas/mlag/mlag.yml:136` | `MlagDomain.peers` | 2 domains, 4 leaves |
| `schemas/evpn/evpn_services.yml:196` | `EvpnSviNode.device` † | 8, all leaves |
| `schemas/routing/vrf_services.yml:163` | `RoutingVrfBgpPeer.devices` † | 5, all leaves |
| `schemas/routing/vrf_services.yml:234` | `RoutingVrfL3Interface.device` † | 8, all `leaf-nfd41-pod1-3-1` |
| `schemas/evpn/evpn_gateway.yml:182` | `EvpnGatewayGroup.members` | **0** — border-leaf-only by definition |

† no forward side on `DcimDevice`.

### C6b — Two become `DcimGenericDevice`, because the data is mixed

| Site | Relationship | Measured |
| --- | --- | --- |
| `schemas/routing/routing.yml:190` | `RoutingAsn.devices` | 9 ASNs across **6 routers and 7 switches** |
| `schemas/routing/vrf_services.yml:66` | `RoutingVrfStaticRoute.devices` | 10 routes across **`isp-pe1` and `leaf-nfd41-pod1-3-1`** |

`asn` is on both kinds (C4), so its reverse cannot name either. This is the shape cycle 024 gave
`RoutingStaticRoute.device` for the firewall, and the comment block at `routing.yml:403` already
explains why: *"a concrete peer here silently excludes…"*.

`RoutingVrfStaticRoute.devices` is the surprise. A tenant VRF static route is shared by a provider
edge and a border leaf — the two ends of the same tenant handoff — so it genuinely spans the
split. Nothing in the field's name says so; only the count did.

### C6c — Four stay `DcimDevice`

`RoutingBGPNeighbor.device` (10 objects, all routers), and `RoutingBGPPeerGroup.device`,
`RoutingPrefixList.device`, `RoutingRouteMap.device` (0 objects each, and their forward sides
`bgp_peer_groups` / `prefix_lists` / `route_maps` stay on `DcimDevice` per Assumption 4).

### C6d — One needs nothing

`LocationRack.devices` already peers `DcimPhysicalDevice`, a generic the new kind inherits.
`rack` moves; its reverse does not move with it.

### C6e — No one-way relationship survives

For every identifier declared on both ends, the two ends name the **same** peer. A forward side on
the new kind with a reverse still on `DcimDevice` produces two one-way relationships and **no
error** — the failure mode `routing.yml`'s comment block was written about.

Asserted by parsing every identifier in `schemas/` and grouping by name, not by inspecting the
ones this cycle happened to touch.

## C7 — Display and identification match

`DcimFabricSwitch` declares the same `human_friendly_id`, `display_label` and `order_by` as
`DcimDevice`, so nothing downstream special-cases it.

## C8 — The pinned peer map, extended

`tests/unit/test_routing_schema_contract.py` already pins the complete `Dcim*` peer map — added
in cycle 024 after a careless global `sed` flipped five unrelated relationships and **nothing
would have caught it**. That map gains `DcimFabricSwitch` entries and the two widened peers.

This cycle edits thirteen peer lines across seven files. It is the same hazard, larger.

## C9 — Consumers: the six query roots

*Corrected at task time; this clause said three. See research R8.*

Eight GraphQL query roots name `DcimDevice`. Six become `DcimFabricSwitch`:

| File | Site |
| --- | --- |
| `generators/avd_device_hostvar.gql` | `:2` |
| `transforms/avd_device_config.gql` | `:2` |
| `transforms/avd_anta_catalog.gql` | `:2` **and `:31`** |
| `transforms/avd_fabric_devices.gql` | `:12` |
| `checks/cv_config_check.gql` | `:15` |

The other two are `frr_config.gql` — C10.

Asserted by reading the files, so a retarget that misses one fails offline rather than at render
time.

## C10 — Consumers: `frr_config.gql` is unchanged

Its two `DcimDevice(...)` filters are **byte-identical** to before. Asserted explicitly, because
"change every `DcimDevice`" is the obvious wrong way to do this cycle and this is the file it
would break.

## C11 — No fragment, and no kind-name string, can silently return nothing

*Corrected at task time; this clause covered 4 sites in 4 files. It is 20 sites in 10 files, plus
7 Python string comparisons the original enumeration could not see. See research R8.*

### C11a — The twenty fragment sites

| File | Sites |
| --- | --- |
| `generators/avd_device_hostvar.gql` | 5 (`:319`, `:434`, `:779`, `:937`, `:1003`) |
| `service_catalog/pages/4_Fabric_View.py` | 5 |
| `transforms/containerlab_topology.gql` | 2 |
| `transforms/cabling_plan.py` | 2 |
| `transforms/cabling_plan.gql` | 1 |
| `generators/generate_avd.gql` | 1 |
| `generators/backfill_structured_config.gql` | 1 |
| `generators/generate_fabric_peering.gql` | 1 |
| `checks/fabric_pool_check.gql` | 1 |
| `checks/peering_consistency_check.gql` | 1 |

Every one reads `name`, `role` or `pod` off a device reached through an interface, link or pod —
all of which can be a fabric switch.

### C11b — The seven kind-name strings, three of them silent

**No fragment grep reaches these.** They are Python comparing a kind as a string:

| Site | Code | Failure |
| --- | --- | --- |
| `transforms/containerlab_topology.py:202` | `if node.typename != "DcimDevice": continue` | **silent** — drops all 7 switches, emits valid empty YAML |
| `generators/generate_avd_device_hostvar.py:2786` | `raw_data.get("DcimDevice", {})` | **silent** — the response key moves with the query root |
| `checks/cv_config_check.py:57` | `normalized.get("DcimDevice", {})` | **silent** |
| `generate_avd_device_hostvar.py:1836`, `:1857` | `kind="DcimDevice"` | loud |
| `src/solution_arista_avd/sorting.py:22`, `:38` | `cast("DcimDevice", …)` | type-only |

### C11c — The three raw mutation strings

`generators/asn.py:21`, `src/solution_arista_avd/generator.py:1063` and `:1087` each embed
`DcimDeviceUpsert(...)` in a GraphQL string.

### C11d — The rule every site is measured by

Each site either:

- reads its fields from `... on DcimGenericDevice`, or
- has both `... on DcimDevice` and `... on DcimFabricSwitch`, or
- is proven never to meet a switch.

Enumerated, one row per site, with the disposition named:

| Site | Field | Disposition |
| --- | --- | --- |
| `transforms/containerlab_topology.gql:17, :97` | `name` | read from the generic |
| `service_catalog/pages/4_Fabric_View.py:281, :287` | `interfaces` | read from the generic |
| `service_catalog/pages/4_Fabric_View.py:92, :341, :349` | `name`, `role` | `name` generic; `role` both fragments |
| `transforms/cabling_plan.gql:52`, `cabling_plan.py:83, :96` | `rack` | add a `DcimFabricSwitch` fragment |

`role` cannot move to the generic: C5 makes the two dropdowns different enumerations.

This is SC-008, and it is the clause that exists because the same failure hid the cabling plan's
missing cables for months. C11b is that failure in a form the cabling-plan fix would not have
caught — a string comparison rather than a fragment.

## C12 — Objects declare the right kinds

`objects/26_nfd41_devices.yml` declares `kind: DcimFabricSwitch`;
`objects/31_nfd41_offfabric_devices.yml` and `31a_nfd41_wan_addressing.yml` keep
`kind: DcimDevice`. Asserted by parsing the YAML.

## C13 — Every device still has a device type and a platform

Cycle 026's guarantee, re-asserted across **all four** kinds rather than the one it was written
against. `tests/unit/test_device_type_and_platform.py` is extended, not copied.

## C14 — `protocols.py` is regenerated

`src/solution_arista_avd/protocols.py` contains a `DcimFabricSwitch` protocol and its header is
unmodified, proving it came from `infrahubctl protocols` rather than an editor.

## Live clauses — verified in quickstart, not by unit test

| # | Clause |
| --- | --- |
| L1 | `infrahubctl schema check schemas/` passes; the diff names `DcimFabricSwitch` added and `DcimDevice` changed, and **nothing else** |
| L2 | A `DcimFabricSwitch` query returns 7; `DcimDevice` returns 7; `DcimGenericDevice` returns 22 |
| L3 | All seven EOS configs match `lab/avd/intended/configs/*.cfg` line for line |
| L4 | The six FRR configs and the Junos config are byte-identical to their pre-cycle output |
| L5 | The cabling plan renders 17 cables; the ContainerLab topology renders 14 nodes and 17 links |
| L6 | A full destroy → build → start → load → `invoke avd --topology` produces the same 33 artifacts |
