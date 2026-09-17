---
title: Generators
description: The infrastructure generators that create devices, interfaces, cabling, and AVD inputs.
audience: developer
sidebar_position: 3
---

# Generators

:::info Developer Guide
Explains how the generators are structured. To *run* generators as an operator, start with [Quick Start](../quick-start.md).
:::

## Overview

Generators create infrastructure objects based on templates and target objects. They run via the Infrahub UI or API and use checksums for idempotent execution.

## Generator architecture

Each generator consists of:

1. **Generator Class** (`generate_*.py`) - Python class extending `InfrahubGenerator`
2. **Query Class** (`*_query.py`) - Pydantic models for GraphQL response parsing
3. **GraphQL Query** (`*.gql`) - Query to fetch target data

```text
┌──────────────────┐     ┌────────────────────┐     ┌─────────────────┐
│  GraphQL Query   │ ──▶ │  Pydantic Parser   │ ──▶ │  Generator      │
│  (*.gql)         │     │  (*_query.py)      │     │  (generate_*.py)│
└──────────────────┘     └────────────────────┘     └─────────────────┘
```

## Device-design-driven generation

The fabric, pod, and rack generators take device counts and templates from their
container's `device_designs` relationship — not from per-role fields on the
container. Each design has a `role`, a `device_quantity`, and a
`device_template`; see [Schemas](schemas.md#device-design-entities--networkdevicedesign-generic)
for the entity itself.

Every generator resolves designs through the same `GeneratorMixin` helper:

```python
# Which super-spines should this fabric have?
template_id, quantity = self.device_design_for(fabric_node.device_designs, "super_spine")
```

`device_design_for` returns `(template_id, quantity)`, or `(None, 0)` when the
container has no design for that role. **Absence means none**: a rack with no
`l2leaf` design gets no L2 leaves, and the generator does not error. This
replaces the older "set the count to `0`" idiom.

Which role each tier reads:

| Generator | Container | Design roles read |
| --- | --- | --- |
| `FabricGenerator` | `NetworkFabric` | `super_spine` |
| `PodGenerator` | `NetworkPod` | `spine` |
| `RackGenerator` | `LocationRack` | `leaf`, `l2leaf` |

### Cross-tier completeness reads

A generator also reads the *upstream* container's designs to decide whether its
prerequisites exist yet, so a partially generated fabric defers instead of
producing a half-cabled topology:

- `PodGenerator` reads the fabric's `super_spine` design. If the fabric expects
  super-spines but they do not all exist yet, the pod generator waits rather
  than cabling spines to an incomplete super-spine layer. A fabric with no
  `super_spine` design skips super-spine uplinks entirely.
- `RackGenerator` reads the pod's `spine` design and compares it to the spines
  that exist, applying the same rule before cabling leaves upward.

These reads are why the generator `.gql` queries select `device_designs` on the
parent as well as on the target.

## Generators

### FabricGenerator

**File**: `generators/generate_fabric.py`

**Target**: `NetworkFabric`

**Purpose**: Initialize fabric infrastructure

**Actions**:

1. Resolve fabric-scoped pools
   - `loopback_pool` for device Loopback0 addresses
   - `vtep_pool` for VTEP loopback addresses
   - `mgmt_pool` for management addresses
   - `asn_pool` for BGP autonomous systems
   - `node_id_pool` for unique device identifiers
2. Create super-spine devices from the fabric's `super_spine` device design
3. Assign loopback IPs to super-spines

**Query**: `generate_fabric.gql`

```graphql
query FabricGenerator($fabric_id: String!) {
  NetworkFabric(ids: [$fabric_id]) {
    edges {
      node {
        id
        name { value }
        supernet_pool { value }
        # ... pool and template data
      }
    }
  }
}
```

### PodGenerator

**File**: `generators/generate_pod.py`

**Target**: `NetworkPod`

**Purpose**: Create pod infrastructure

**Actions**:

1. Create spine devices from the pod's `spine` device design
2. Link spines to super-spines
3. Allocate loopback IPs from pod pools
4. Set BGP ASN and node IDs

**Query**: `generate_pod.gql`

```graphql
query PodGenerator($pod_id: String!) {
  NetworkPod(ids: [$pod_id]) {
    edges {
      node {
        id
        name { value }
        fabric { node { ... } }
        # ... template and pool data
      }
    }
  }
}
```

### RackGenerator

**File**: `generators/generate_rack.py`

**Target**: `LocationRack`

**Purpose**: Create rack infrastructure

**Actions**:

1. Create leaf and L2-leaf devices from the rack's `leaf` / `l2leaf` device designs
2. Link leaves to pod spines
3. Allocate loopback IPs
4. Set BGP ASN and node IDs

**Query**: `generate_rack.gql`

```graphql
query RackGenerator($rack_id: String!) {
  LocationRack(ids: [$rack_id]) {
    edges {
      node {
        id
        name { value }
        pod { node { ... } }
        # ... device and link data
      }
    }
  }
}
```

### GenerateAVDDeviceHostvar

**File**: `generators/generate_avd_device_hostvar.py`

**Target**: `DcimDevice`

**Purpose**: Generate PyAVD hostvars for each device

**Actions**:

1. Extract device attributes (hostname, role, ASN, node ID)
2. Extract IP addresses (loopback, management)
3. Determine uplink topology by device role
4. Extract connected endpoints (servers with VLANs)
5. Validate optional EVPN Gateway group intent for `border_leaf` devices
6. Build PyAVD-compatible hostvars structure
7. Upload hostvars JSON to object store
8. Create/update AvdArtifact with checksum

**Query**: `avd_device_hostvar.gql`

For EVPN Multi-Domain Gateway hostvars, the query fetches `EvpnGatewayGroup.local_domain`, the selected `pod` and its `evpn_domain`, `remote_domain`, members, and peer candidate groups from `remote_domain.remote_gateway_groups`. The generator emits `l3leaf.nodes[].evpn_gateway` only for valid grouped `border_leaf` devices, rejects Pod/local-domain mismatches and same local/remote domain intent, validates the final payload with `pyavd.validate_inputs()`, and derives hostname-only remote peers from valid groups that share the selected remote domain.

### AvdDeviceStructuredConfigGenerator

**File**: `generators/generate_avd_device_structured_config.py`

**Target**: `NetworkFabric`

**Purpose**: Generate AVD structured configs for all fabric devices

**Actions**:

1. Traverse fabric hierarchy (pods → devices, racks → devices)
2. Fetch hostvars from object store for each device
3. Validate inputs with `pyavd.validate_inputs()`
4. Generate AVD facts with `pyavd.get_avd_facts()`
5. Generate structured config per device
6. Upload configs to object store
7. Update AvdArtifact with config identifier

**Query**: `generate_avd.gql`

### ServerCablingGenerator

**File**: `generators/generate_server_cabling.py`

**Target**: `ComputePhysicalServer` (group `servers`)

**Purpose**: Cable a server to the leaf switches in its rack, then reconcile its LAGs and VLANs

**Actions**:

1. Resolve the server's rack and find the `leaf` / `l2leaf` switches in it
2. Build sorted interface maps for the server and for the leaves' `role=server` interfaces
3. On first run, pick the next free port index across those leaves and create the links; on a
   re-run, rebuild the existing cabling plan instead of cabling again
4. For a dual-homed server, create the server-side `Bond1` and the switch-side
   `Port-Channel<ID>` LAGs, assign members, and set `evpn_ethernet_segment` when the pair is not
   MLAG-backed
5. Assign VLANs from server intent — on a single-homed server they stay on the physical interface,
   on a dual-homed server they are assigned to the LAG
6. Trigger AVD hostvar regeneration for the leaves the server connects to

**Query**: `generate_server_cabling.gql`

Because steps 3–5 run on every invocation, the generator is the reconciliation path as well as the
creation path: re-running it after a VLAN or LAG change updates an already-cabled server without
producing duplicate links. The operator-facing walkthrough is
[Add a Server](../how-to/add-server.md).

### FabricPeeringGenerator

**File**: `generators/generate_fabric_peering.py`

**Design object**: `Service.FabricPeering` — the ordered intent, "this cluster peers with the
fabric"

**Generated objects**: `Cluster.FabricPeering` — one BGP session per fabric device the
cluster's nodes are cabled to

**Target group**: `service_fabric_peerings`

This is the generator that sits underneath the service layer. Before it, each session's peer
device, address and BGP AS were written by hand in `objects/34_nfd41_cluster.yml`. The AS was
a second copy of a number the fabric model already held, and the lab's own notes describe what
a second copy costs: change either side without the other and BGP either does not come up or
comes up carrying nothing.

**What it derives.** The peer set comes from the cabling — cluster nodes, their interfaces,
each link's far end — reduced to *distinct* devices whose role is `leaf`, `border_leaf` or
`l2leaf`, and sorted by device name. `peer_asn` is read from the peer device's own
`Routing.Asn`, the same node AVD renders the switch from, so the two ends of the session
cannot drift apart.

**Two traps worth knowing.** `NetworkLink.connected_endpoints` returns *both* ends of a cable,
including the cluster node's own interface, so the near end is excluded by interface id —
filtering by device kind only appears to work because cluster nodes are `Compute.PhysicalServer`
rather than `Dcim.Device`. And adoption fetches the existing session and sets one attribute
rather than upserting: an upsert validates every mandatory field, so a payload that omits
`name` and `peer_address` in order to preserve them is rejected outright.

**It creates as well as adopts.** `peer_address` is derived from the peer device's
`peering`-role SVI, selected by interface role rather than by VLAN id or position — every leaf
carries a `Loopback0` alongside its `Vlan110`, so a positional rule picks the wrong one. A
newly cabled leaf with a peering SVI is therefore provisioned without anyone writing the
session first. A leaf with no such SVI, with more than one, or with one carrying more than one address,
fails naming the device: the address is derived, never invented.

**Two fields are derived; one is not.** `name` remains a lab-facing label — `k8s-leaf1` is the
containerlab hostname of the switch the fabric model calls `leaf-nfd41-pod1-1-1`, and the lab
models the same switches twice — so a session created from scratch takes its device's name.
That means delete-and-recreate is **not** artifact-neutral: the peer labels in the rendered
manifest change even though addresses and ASNs do not.

**Drift is reported, not silently corrected.** When a session's recorded address disagrees
with the derived one, the run logs the device and the old value before correcting it. An
address change moves where BGP points, and that belongs in the run output.

**Cleanup.** Sessions the generator previously produced and no longer derives are removed by
the tracking context. Sessions it never produced are outside that context and are never
deletion candidates.

### AppAccessGenerator

**File**: `generators/generate_app_access.py`

**Target**: `ServiceAppAccess` (group `service_app_accesses`)

**Purpose**: Turn an approved access grant into the firewall objects that permit the session, and
into the fabric advertisement that makes its destination reachable

**Actions**:

1. Check `approved`. An unapproved grant creates nothing and its status is left alone.
2. Validate and derive everything before the first write — ports, the destination zone, the
   policy, and the `tcp` protocol object.
3. Upsert a `SecurityIPAMIPAddress` for the grant's destination VIP, or adopt an entry that
   already wraps that address.
4. Upsert a `SecurityService` per permitted port, or adopt the firewall's existing object for
   that protocol and port.
5. Upsert the `SecurityPolicyRule` joining them, with `managed_by_service: true`.
6. Link the rule into the grant's `granted_rules` and set its status to `active`.
7. Add the destination VIP to the prefix list the DC advertises toward the grant's source zone, at
   device scope on that zone's advertising switch.
8. Ask for the firewall's artifact to be re-rendered.

A grant therefore acts in all three domains of this lab: Kubernetes through the application it
names, Junos through the rule, and the fabric through the advertisement.

**Query**: `generate_app_access.gql`

Nothing downstream changes. `junos_config.gql` queries `SecurityGenericAddress` and
`SecurityPolicy` unfiltered, so a generated object is rendered into the firewall's existing
artifact the moment it exists, and the deployment reconciler pushes it.

#### The fabric leg, and where it stops

Steps 7 and 8 exist because a firewall rule alone permits a session to somewhere the border leaf
never re-advertises — permitted and unroutable, which the schema comment on
`ServiceAppAccess.destination_vip` warns about. The generator uses the two fields
`Security.Zone` gained for it: `dc_advertised_prefix_list` and `advertising_device`.

The entry is written at **device scope** rather than fabric scope. The hostvar generator merges the
scopes by entry identity, so a device-scope sequence composes with the fabric's baseline instead of
replacing it, and the hand-authored policy every other switch shares is untouched.

**The write does not reach a switch on its own.** It lands in `avd_custom_hostvars`, which
`generate-avd-device-hostvar` reads — and that generator is registered `execute_after_merge: false`
because the AVD chain is expensive and run explicitly. The model is correct immediately; the switch
follows on the next `invoke avd`, exactly as it does for any other fabric change. The Junos half has
no such gap: step 8 re-renders the firewall's artifact, and the reconciler pushes it.

A zone the datacentre advertises nothing toward yields no advertisement, which is not an error —
four of the six zones are in that state, and a grant from one gets its firewall rule and nothing
else. A zone carrying one half of the policy raises instead, because acting on it would either write
into an unnamed list or name a list on no device. [`zone-advertisement`](./checks.md#zone-advertisement)
refuses the merge that introduces either fault.

#### Why the artifact re-render is explicit

An artifact regenerates when its **target** changes, and the target here is the firewall — a new
`Security.PolicyRule` is not a change to `fw1`. Without step 8 the objects appear, the rendered
artifact keeps its old checksum, and the reconciler compares the device against stale output and
reports no difference. Infrahub's trigger rules cannot close this: `CoreGeneratorAction` and
`CoreGroupAction` are the only actions, and neither renders an artifact.

The request is best effort. The objects are already written and correct by that point, and raising
would skip the tracking context's group update, leaving the run's objects outside the group they own.

#### The approval gate

`approved` is the gate, so an unapproved request is inert rather than merely hidden. The grant
seeded in `objects/38_nfd41_access_grants.yml` is unapproved deliberately: it keeps the rendered
artifact byte-identical to what the unit tests hold against the device's own configuration, while
leaving the whole demo one field-flip away.

The cost is that "ran successfully and created nothing" is the normal outcome, which is
indistinguishable from a broken generator unless you check the flag first.

#### The two allocation floors

| Value | Floor | Hand-written range | Why |
| --- | --- | --- | --- |
| `SecurityPolicyRule.index` | 100 | 10, 20, 30 | Junos is first-match within a zone pair. The baseline puts an anti-spoofing `deny` at index 10, so a generated permit must sort **after** it — below it, every grant becomes a bypass for a spoofed infrastructure source. |
| `SecurityIPAMIPAddress.book_index` | 1000 | 10–130 | The address book renders in `book_index` order and that order is pinned. An entry with **no** index is skipped entirely — referenced by a rule and never declared, so the configuration does not load. |

Both are deterministic functions of the grant's name. A value that moves between runs would churn
the tracking context even though nothing changed.

#### Deriving the destination zone

The grant names a source zone but not a destination one. It is derived through the VRF:

```text
ServiceAppAccess.application → ServiceFabricApp.vrf → IpamVRF ← SecurityZone.vrf
```

Deriving it instead from "the firewall interface whose subnet contains the VIP" cannot work: the
handoff interfaces are `/30` point-to-points and contain no service VIP, so containment matches
nothing and every grant raises.

#### Adoption, and why revocation is safe

Adoption fetches and modifies; it never upserts. An upsert validates every mandatory field, so a
payload omitting fields in order to preserve them is rejected outright.

An adopted object is never renamed, never re-indexed, and never marked `managed_by_service` —
so the tracking context, which only removes what this generator created, leaves it alone. That is
what keeps `junos-https` alive when a grant that used port 443 is revoked, while the rule the
grant created disappears.

### FabricAppGenerator

**File**: `generators/generate_fabric_app.py`

**Target**: `ServiceFabricApp` (group `service_fabric_apps`)

**Purpose**: Give an exposed application a LoadBalancer VIP block from its cluster's pool, so
stating a size is the request rather than choosing addresses by hand

**Actions**:

1. Check `exposed` and `status`. An unexposed or decommissioned application withdraws.
2. Keep any block the application already holds, whoever created it.
3. Otherwise resolve the pool through the cluster, allocate a block, and record it together
   with `vip_block_managed: true`.
4. Ask for the Crossplane manifest to be re-rendered.

**Query**: `generate_fabric_app.gql`

This is the second generator here that **allocates rather than selects**, after
[NetworkSegmentGenerator](#networksegmentgenerator), and it closes a harder edge: an exposed
application with no block does not degrade, it **fails**. `crossplane_fabric_app.py` raises
`application {name} is exposed but has no vip_block; the XRD requires expose.vipBlock`, so
before this generator every exposed application needed a block picked by hand out of
`10.112.240.0/24` with nothing preventing two of them from picking the same one.

#### `vip_block_managed`, and why withdrawal is safe

`vip_block` is one field holding two very different things:

| Origin | Example | May the generator delete it? |
| --- | --- | --- |
| Declared in `objects/` by a human | `10.112.240.0/28` for `nfd41-demo` | **No** |
| Allocated from the pool by this generator | `10.112.240.16/28` onward | Yes |

`vip_block_managed` records which, is set only on the allocating path, and is the only thing
withdrawal consults. It plays exactly the role `managed_by_service` plays on
`SecurityPolicyRule`: the guard that lets a generator work beside hand-maintained data. Deleting
the seeded block would remove an object `objects/29_nfd41_offfabric_prefixes.yml` owns and break
the next `invoke load`.

It is written in the **same save** as the block. Two saves leave a window in which the block
exists and nothing records who owns it, and a withdrawal landing in that window would decline to
remove a block the generator had in fact allocated — leaking it.

#### The pool comes from the cluster

Not from a name, and not from a role scan. A cluster's `vip_pools` are the only supernets its
LoadBalancer addresses may come from: the leaves' inbound route policy permits exactly
`10.112.240.0/24 le 32`, so a block from anywhere else is advertised by the cluster and refused
by the fabric — permitted and unroutable, the same failure
`schemas/service/access_services.yml` warns about on `destination_vip`. Exactly one pool must
draw from those supernets; two would allocate against each other.

#### What it does not do

Reallocate an existing block. That is what keeps `nfd41-demo` on `10.112.240.0/28`, which matters
because the `zone-advertisement` check measures grant VIPs against it and the rendered manifest
is already applied in the cluster.

### NetworkSegmentGenerator

**File**: `generators/generate_network_segment.py`

**Target**: `ServiceNetworkSegment` (group `service_network_segments`)

**Purpose**: Turn a request for a network into the three technical objects a network is — a
subnet, a VLAN, and a gateway in a VRF

**Actions**:

1. Check `status`. `decommissioning` and `decommissioned` withdraw; everything else builds.
2. Resolve and validate everything before the first write — the pools, the L2 domain, the AVD
   tags, and whether anything already wears the requested name.
3. Allocate an `IpamPrefix` from the subnet pool, or reuse the one already recorded.
4. Upsert an `IpamVLAN`, with an id that is stated, remembered, or allocated.
5. Upsert an `EvpnSvi` whose `svi_id` equals the VLAN id and whose virtual address is the
   subnet's first usable host.
6. Record all three on the service and set its status to `active`.

**Query**: `generate_network_segment.gql`

This is the first generator here that **allocates rather than selects**. `ServiceL3vpn` and its
WAN siblings name technical objects that already exist, so a generator beneath them would have
nothing to create. A segment states a size and a tenant, and leaving `vlan_id` empty is the
normal case rather than an incomplete request — the person asking for a network is exactly the
person who does not know which ids are free.

#### `avd_tags` decides whether any of it renders

AVD puts an SVI on a device only where `svis[].tags` intersects that device's node-group
`filter.tags`, and in this fabric those filters are the racks' own `AvdTag`s:

| Node group | Filter | Rack |
| --- | --- | --- |
| K8S_LEAFS | `k8s` | the two Kubernetes leaves |
| APP_LEAFS | `app`, `cloud` | the two application leaves |
| BORDER_LEAFS | `border` | the border leaf |

`EvpnSvi.rack_tags` exists, looks like the scoping relationship, and contributes the rack's
**name** — `K8S_LEAFS` — which matches no filter. Measured on a branch: an SVI with no tags
rendered on zero switches, and the same SVI tagged `k8s` rendered on exactly the two K8S leaves.
Nothing errors on that path, so `avd_tags` is mandatory in the schema and checked again in the
generator. An empty list is not "the whole fabric"; it is nowhere, with an artifact that reports
`Ready` and simply lacks the interface.

#### The pools are found by role, not by name

A default of `NFD41-Segment-Subnet-Pool` would tie the generator to one lab's object files and,
when it was missing, fail with a message naming a string that appears in no schema. Instead:

- the subnet pool is the `CoreIPPrefixPool` whose resources carry role `tenant_host`;
- the VLAN pool is the `CoreNumberPool` allocating `IpamVLAN.vlan_id`.

Both demand exactly one candidate. Zero and several are reported the same way, with the remedy —
name the pool on the segment — because "ambiguous" on its own sends the reader to the wrong file.

#### Adoption is asked for, never inferred

The VLAN and the SVI take the segment's own name, so a generated segment reads like the four
hand-written ones beside it. The cost is that a request named `K8S_NODES` would upsert onto the
lab's existing VLAN — and delete it on decommissioning. So an object wearing the requested name
that the service does not already record is **refused**. Adopting one is explicit: point the
service's `vlan` or `svi` at it first.

#### What withdrawal does, and why it is written out

`InfrahubGroupContext.update_group` opens with `if not members: return`, so a run that writes
nothing prunes nothing — a decommissioned segment would keep its subnet, VLAN and gateway while
reporting success. Withdrawal is therefore explicit, deletes in reference order (SVI, then VLAN,
then prefix), and only ever removes what the service records. Deleting the prefix last is also
what returns the subnet to its pool.

#### Nothing here reaches a switch on its own

The writes land in the graph. `generate-avd-device-hostvar` carries them onto the fabric and is
registered `execute_after_merge: false`, because the AVD chain is expensive and is run
explicitly. A correct segment that is invisible on the device means `invoke avd` has not run
yet, not that the generator failed.

**There is no seeded segment**, deliberately. An active one would allocate a subnet and a VLAN
into the default data set and change every rendered EOS artifact, and the fixtures those are
held against are the hand-written baseline. Request one on a branch instead.

### BackfillStructuredConfigGenerator

**File**: `generators/backfill_structured_config.py`

**Target**: `AvdStructuredConfigFile` (group `avd_structured_configs`)

**Purpose**: Read AVD's structured-config output back into the Infrahub data model

**Actions**: Parse each device's stored structured config and upsert the objects it implies —
`IpamPrefix` and `IpamIPAddress` entries, `DcimInterface.mtu`, BGP peer groups and neighbors,
prefix lists, route maps, and static routes.

**Query**: `backfill_structured_config.gql`

This generator runs in the opposite direction to the rest of the chain: everything else turns intent
into AVD inputs, while the backfill turns AVD's derived output into queryable objects. Those objects
are reconciled *from* AVD, not authored as inputs — see
[Supported Capabilities](../supported-capabilities.md).

## Generator execution order

Run generators in this order for a new fabric:

```text
1. FabricGenerator     (on Fabric)
        ↓
2. PodGenerator        (on each Pod)
        ↓
3. RackGenerator       (on each Rack)
        ↓
4. AVD Hostvars        (on each Device)
        ↓
5. AVD Structured Cfg  (on Fabric)
```

For an existing fabric, `generate-fabric` is also the reconciliation entry point.
Checksum changes still drive the existing trigger rules: a changed pod checksum
fires `generate-pod`, and a changed rack checksum fires `generate-rack`. When a
pod or rack checksum is already current, the upstream generator explicitly
continues the cascade with `CoreGeneratorDefinitionRun` targeted to the unchanged
node IDs. This keeps repeated fabric runs from faking checksum churn while still
reaching pod, rack, hostvar, and structured-config generation.

The fabric generator skips direct continuation for the fabric-role pod because
that pod is owned by `FabricGenerator` for super-spine creation. Pod generation
uses the same pattern for racks: changed racks rely on checksum-trigger saves;
unchanged racks are scheduled directly.

Device reconciliation is fill-only by default. `GeneratorMixin.create_avd_device()`
fetches any existing device by name before building the upsert payload, then
populates missing generator-owned values such as status, role, object template,
pod, rack, index, AVD group membership, node ID, management IP, loopback IP,
VTEP loopback IP, and ASN. Existing non-empty operator values, including
`serial` and `mgmt_ip`, are preserved during standard generation.

## Running generators

### Via Infrahub UI

1. Navigate to target object (Fabric, Pod, Rack, or Device)
2. Click **Actions** → **Generator definitions**
3. Select the generator
4. Click **Run**

### Via infrahubctl CLI

The CLI takes the generator name followed by `key=value` variables — the parameters declared for
that generator in `.infrahub.yml`. Every generator here is parameterised by `name`, so the value is
the target object's name, not its ID:

```bash
uv run infrahubctl generator generate-fabric name=Fabric-L3LS-MultiPod-A --branch <branch-name>
uv run infrahubctl generator generate-pod name=Pod-A2 --branch <branch-name>
uv run infrahubctl generator generate-rack name=Rack-A2-1 --branch <branch-name>
uv run infrahubctl generator generate-avd-device-hostvar name=leaf-pod-a2-1-1 --branch <branch-name>

# List the generators the repository defines
uv run infrahubctl generator --list
```

`backfill-structured-config` is the exception: its parameter is the artifact name
(`artifact__name__value`), still passed as `name=`.

## GeneratorMixin

All generators use `GeneratorMixin` from `src/solution_arista_avd/generator.py`:

```python
class GeneratorMixin:
    def calculate_checksum(self, related_node_ids: list[str]) -> str:
        """
        Calculate deterministic checksum from related node IDs.
        Used to detect when regeneration is needed.
        """
        sorted_ids = sorted(related_node_ids)
        combined = "".join(sorted_ids)
        return hashlib.sha256(combined.encode()).hexdigest()

    @classmethod
    def device_design_for(cls, device_designs, role) -> tuple[str | None, int]:
        """
        Return (template_id, quantity) for one role's device design,
        or (None, 0) when the container has no design for that role.
        """

    async def assign_mlag_peer_interfaces(
        self, device, count=2, carvable_roles=frozenset({"server", "mlag_peer"})
    ) -> None:
        """
        Repurpose a device's highest-numbered carvable ports as its MLAG
        peer-link, for switch models that ship no dedicated mlag_peer
        interfaces. Deterministic (ordered by the interface's computed
        `index`) and idempotent, so a re-run converts nothing further.
        Used by the rack generator for l2leaf pairs and the pod generator
        for the l2spine pair.
        """
```

Usage in generator:

```python
class FabricGenerator(GeneratorMixin, InfrahubGenerator):
    async def generate(self, data):
        # Calculate checksum from related nodes
        new_checksum = self.calculate_checksum([
            pod.id for pod in data.pods
        ])

        # Skip if unchanged
        if new_checksum == data.checksum:
            return

        # ... generate infrastructure ...

        # Update checksum
        data.checksum = new_checksum
        await data.save()
```

## Query classes (Pydantic)

Each generator has a corresponding query class for type-safe parsing. **These `*_query.py` files are generated, not hand-written** — regenerate them whenever the `.gql` query or the schema changes:

```bash
uv run infrahubctl graphql generate-return-types generators/generate_fabric.gql
```

This reads `schema.graphql` at the repo root (refresh with `uv run infrahubctl graphql export-schema --destination schema.graphql` when needed) and emits the matching `*_query.py` next to the query file.

Shape of a typical generated class:

```python
# generators/fabric_generator_query.py  (generated)

from pydantic import BaseModel

class FabricNode(BaseModel):
    id: str
    name: ValueWrapper[str]
    supernet_pool: ValueWrapper[str]
    pods: EdgesWrapper[PodNode]

class FabricGeneratorQuery(BaseModel):
    NetworkFabric: EdgesWrapper[FabricNode]
```

## Configuration

Generators are registered in `.infrahub.yml`:

```yaml
generator_definitions:
  - name: generate-fabric
    file_path: "./generators/generate_fabric.py"
    class_name: FabricGenerator
    targets: fabrics
    query: generate_fabric

  - name: generate-pod
    file_path: "./generators/generate_pod.py"
    class_name: PodGenerator
    targets: pods
    query: generate_pod

  - name: generate-rack
    file_path: "./generators/generate_rack.py"
    class_name: RackGenerator
    targets: racks
    query: generate_rack

  - name: generate-server-cabling
    file_path: "./generators/generate_server_cabling.py"
    class_name: ServerCablingGenerator
    targets: servers
    query: generate_server_cabling

  - name: backfill-structured-config
    file_path: "./generators/backfill_structured_config.py"
    class_name: BackfillStructuredConfigGenerator
    targets: avd_structured_configs
    query: backfill_structured_config
```

The AVD generators are registered in the same block; the file is the authoritative list of all seven.

## Pool resolution

The fabric, pod, rack, and hostvars generators consume role-driven pool collections first. `NetworkFabric.fabric_ip_pools` supplies fabric Management, Loopback, Loopback VTEP, Fabric Point-to-Point, DCI, and Fabric Supernet roles. `NetworkPod.pod_ip_pools` can override pod-specific Loopback, Loopback VTEP, and Fabric Point-to-Point pools.

If a required fabric prefix pool is missing and a Fabric Supernet pool exists, `GeneratorMixin` creates deterministic fallback prefix pools with stable names such as `<fabric>-Loopback-Pool`, then wraps Loopback and VTEP prefix pools in address pools for device allocation. Repeated runs upsert the same names.

The hostvars generator resolves MLAG and MLAG Peering from `pod_ip_pools`, then legacy pod relationships, then pod-scoped default pools named `<pod>-MLAG-Peer-Subnet` and `<pod>-MLAG-L3-Peering-Subnet`. Each pod is allocated its own child prefix — a `/24` from `169.254.0.0/16` for the peer-link, a `/28` from `192.0.0.0/24` for L3 peering — because PyAVD carves a `/31` per MLAG pair out of the pool, and MLAG L3 peering addresses are advertised into the underlay. Treat the L3 peering default as a safety net, not a design: define an explicit `mlag_peering` pool.

## File structure

```text
generators/
├── generate_fabric.py              # Fabric generator class
├── generate_fabric.gql             # Fabric GraphQL query
├── fabric_generator_query.py       # Fabric Pydantic models
├── generate_pod.py                 # Pod generator class
├── generate_pod.gql                # Pod GraphQL query
├── pod_generator_query.py          # Pod Pydantic models
├── generate_rack.py                # Rack generator class
├── generate_rack.gql               # Rack GraphQL query
├── rack_generator_query.py         # Rack Pydantic models
├── generate_avd_device_hostvar.py  # AVD hostvars generator
├── avd_device_hostvar.gql          # AVD device query
├── generate_avd_device_structured_config.py  # AVD structured config
├── generate_avd.gql                # AVD fabric query
├── generate_avd_inputs_query.py    # AVD fabric Pydantic models
├── generate_avd_device_inputs_query.py  # AVD device Pydantic models
├── generate_server_cabling.py      # Server cabling generator
├── generate_server_cabling.gql     # Server cabling query
├── server_cabling_query.py         # Server cabling Pydantic models
├── backfill_structured_config.py   # Structured-config backfill generator
├── backfill_structured_config.gql  # Backfill query
└── backfill_structured_config_query.py  # Backfill Pydantic models
```

## Source

- Generator framework: [`src/solution_arista_avd/generator.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/src/solution_arista_avd/generator.py) — `GeneratorMixin` with checksum-based change detection.
- Infrastructure generators:
  - [`generators/generate_fabric.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_fabric.py) — `FabricGenerator`.
  - [`generators/generate_pod.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_pod.py) — `PodGenerator`.
  - [`generators/generate_rack.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_rack.py) — `RackGenerator`.
  - [`generators/generate_server_cabling.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_server_cabling.py) — `ServerCablingGenerator`.
  - [`generators/backfill_structured_config.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/backfill_structured_config.py) — `BackfillStructuredConfigGenerator`.
- AVD generators (documented in detail in the [AVD Pipeline sub-section](./avd/overview.md)):
  - [`generators/generate_avd_device_hostvar.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_avd_device_hostvar.py) — `GenerateAVDDeviceHostvar`.
  - [`generators/generate_avd_device_structured_config.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_avd_device_structured_config.py) — `AvdDeviceStructuredConfigGenerator`.
- Registration: [`.infrahub.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/.infrahub.yml) — `generator_definitions:` block.
- Tests: [`tests/unit/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/tests/unit) and [`tests/integration/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/tests/integration).
