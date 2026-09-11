# Object Population Specification: k8s Leaf Peering SVIs

> **Workflow**: This spec targets Infrahub object data population. The implementing agent MUST use the `infrahub-managing-objects` skill to generate all object files.

**Feature Branch**: `014-k8s-leaf-peering-svi`
**Created**: 2026-09-10
**Status**: Draft
**Input**: User description: "Model the k8s leaves' Vlan110 peering SVIs in Infrahub object data so `ClusterFabricPeering.peer_address` becomes derivable from the peer device instead of hand-declared."

## Context

Cycle 012 (`specs/012-service-layer-generator`) built `generate-fabric-peering`, which derives
each Kubernetes cluster's BGP sessions from cabling and sets `peer_asn` by reading the peer
device's own `RoutingAsn`. It deliberately stopped short of `peer_address`, and its annotation
in `objects/34_nfd41_cluster.yml` says why:

> Nothing in the fabric model connects a peering address to a device: the `IpamIPAddress` is
> attached to no interface, so the generator has no traversal to derive it from and is
> forbidden to invent one (FR-027).

That is the gap this cycle closes. The two peering addresses exist as `IpamIPAddress` objects
but hang off nothing — their `interface` relationship is null — so `peer_address` remains
hand-declared alongside `name`, `description` and `svi` in the seed file.

The fabric already knows the pairing. `EvpnSviNode` records `device: leaf-nfd41-pod1-1-1` and
`ip_address: 10.110.0.2/24`. But `EvpnSviNode.ip_address` is an **IPHost attribute, not a
relationship**, so there is no edge from the `IpamIPAddress` object back to a device. An
attribute that merely spells the same text as another object is not a traversal.

This cycle supplies the missing edge as object data: an SVI interface on each leaf that
*holds* the address object. Nothing else changes.

### Explicitly out of scope

Changing `generate_fabric_peering.py` to consume the new edge is **out of scope**. This cycle
models the data; a follow-up cycle is what consumes it. That separation is deliberate — it
keeps the regression surface of this cycle to "object data was added" and lets the follow-up
be reviewed on its own merits.

Also out of scope: any schema change. The verification below establishes that none is needed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The peering address belongs to a device (Priority: P1)

As a network engineer, I need each k8s leaf's Vlan110 peering address to be attached to an
interface on that leaf, so that "which device answers on 10.110.0.2?" is a question the model
can answer rather than a fact that lives only in a hand-written comment.

**Why this priority**: This is the entire feature. Every other story is a consequence of it.

**Independent Test**: Query `IpamIPAddress` for `10.110.0.2/24` and follow
`interface -> device`. Before this cycle the traversal dead-ends at a null interface; after it,
it lands on `leaf-nfd41-pod1-1-1`.

**Acceptance Scenarios**:

1. **Given** the schema and seed objects are loaded, **When** querying the two peering
   addresses, **Then** each resolves through `interface` to exactly one interface object
2. **Given** the peering addresses resolve to interfaces, **When** following
   `interface -> device`, **Then** `10.110.0.2/24` reaches `leaf-nfd41-pod1-1-1` and
   `10.110.0.3/24` reaches `leaf-nfd41-pod1-1-2`
3. **Given** a `ClusterFabricPeering` row with `peer_device: leaf-nfd41-pod1-1-1`, **When** the
   device's interfaces are searched for an address inside the peering prefix `10.110.0.0/24`,
   **Then** exactly one address is found and it equals that row's declared `peer_address`

---

### User Story 2 - The shared gateway is never mistaken for a peer (Priority: P1)

As a network engineer, I need the derivation to be unable to select the MLAG pair's shared VARP
gateway `10.110.0.1`, because an anycast address is present on both leaves and therefore cannot
identify a single BGP neighbour.

**Why this priority**: Equal to P1. A derivation that can return the wrong address is worse
than no derivation, because it fails silently — BGP comes up against the wrong peer or flaps
between the pair.

**Independent Test**: Enumerate every address reachable from either leaf through the modelled
SVI and confirm `10.110.0.1` is not among them.

**Acceptance Scenarios**:

1. **Given** the objects are loaded, **When** enumerating addresses attached to each leaf's
   peering SVI, **Then** each leaf carries exactly one address and it is that leaf's own
2. **Given** the VARP gateway `10.110.0.1` is recorded on `EvpnSvi.ip_virtual_router_addresses`,
   **When** searching for it as an attached interface address, **Then** it is attached to no
   interface on either leaf
3. **Given** both leaves are queried, **When** comparing their peering addresses, **Then** the
   two addresses are distinct

---

### User Story 3 - Nothing that reaches the cluster moves (Priority: P1)

As an operator, I need proof that adding this data changed nothing that is applied to the live
Kubernetes cluster, because the Crossplane `FabricPeering` manifest is rendered from the same
model and is applied by a controller without further review.

**Why this priority**: Equal to P1. This is the regression oracle for the whole cycle. Cycles
011 and 012 both recorded the same artifact checksum; a third cycle that moves it has changed
what a controller applies.

**Independent Test**: Render the `crossplane_fabric_peering` transform before and after the
change and compare the bytes.

**Acceptance Scenarios**:

1. **Given** a render captured before the change, **When** the same transform is rendered after
   the objects are loaded, **Then** the two renders are byte-identical
2. **Given** the render after the change, **When** its bytes are normalised to a single trailing
   newline and hashed, **Then** the digest equals the value cycles 011 and 012 recorded

---

### User Story 4 - The seed data can be loaded twice (Priority: P2)

As a developer, I need the new object data to be idempotent, so that a repeated load — which
happens on every repository sync and every developer's local rebuild — does not create
duplicate interfaces or detach addresses.

**Why this priority**: Required by the project constitution (Idempotent Operations), but it is
a property of the load rather than the model, so it ranks below the three P1 stories.

**Acceptance Scenarios**:

1. **Given** the objects have been loaded once, **When** they are loaded a second time, **Then**
   the load succeeds with no errors
2. **Given** two loads have completed, **When** counting the peering SVIs, **Then** the count is
   the same after the second load as after the first
3. **Given** two loads have completed, **When** the transform is rendered again, **Then** it is
   still byte-identical to the baseline

---

### Edge Cases

- **The address is declared in a file that sorts later than the interface.** The interface
  references the address by human-friendly id, so the address must already exist. File
  numbering must place the interface file after the file that declares the addresses.
- **The relationship is written from the address side.** `IpamIPAddress.interface` peers the
  generic `InterfaceLayer3`, which has no human-friendly id, so a reference written from that
  side cannot be resolved by the loader. The edge must be written from the interface side.
- **A second interface on the same leaf carries an address in the same prefix.** The derivation
  a follow-up cycle performs would then be ambiguous. Only one interface per leaf may hold an
  address inside the peering prefix.
- **The lab models the same two switches twice.** `k8s-leaf1` and `k8s-leaf2` are containerlab
  hostnames for the same hardware the fabric model calls `leaf-nfd41-pod1-1-1` and
  `leaf-nfd41-pod1-1-2`. The peering rows point at the `leaf-nfd41-*` names, so those are the
  devices that must carry the SVI. Attaching an address to the duplicate instead would produce
  a traversal that the peering rows cannot reach.
- **An interface name collides with one a device-type template already creates.** Every leaf
  already carries a template-generated `Loopback0`. A new interface must not reuse a name the
  template owns, or the two definitions fight over the same human-friendly id.
- **Adding interfaces changes what interface-consuming artifacts render.** Several generators
  and transforms enumerate a device's interfaces. Any that do not filter by interface type would
  see the new SVI.

## Requirements *(mandatory)*

### Functional Requirements

**File Format & Structure**

- **FR-001**: Every object file MUST use `apiVersion: infrahub.app/v1` and `kind: Object`
- **FR-002**: Every `spec` block MUST contain a `kind` field matching a valid schema node kind
  and a `data` list of object instances
- **FR-003**: Multiple YAML documents in a single file MUST be separated by `---`

**Relationship References**

- **FR-004**: All relationships MUST reference the target by its human-friendly id — scalar for
  a single-element id, list for a multi-element id
- **FR-005**: The interface-to-address edge MUST be written from the **interface** side. The
  address side peers a generic with no human-friendly id and cannot be resolved by the loader
- **FR-006**: Each peering SVI MUST reference its device by the device name the
  `ClusterFabricPeering.peer_device` rows use, not by the containerlab hostname of the same
  hardware

**File Organization & Load Order**

- **FR-007**: The new object data MUST live in the `objects/` directory
- **FR-008**: The file MUST carry a numeric prefix that sorts after every file it depends on
- **FR-009**: The file MUST sort after the file that declares the peering `IpamIPAddress`
  objects, because it references them
- **FR-010**: The new file MUST NOT require any change to the load order of existing files

**Data Integrity**

- **FR-011**: Dropdown attribute values MUST use the choice `name`, not the display label
- **FR-012**: The SVI interface name MUST NOT collide with any interface a device-type template
  already creates on the same device
- **FR-013**: Each peering SVI MUST carry exactly one IP address, and it MUST be that leaf's own
  address, never the MLAG pair's shared VARP gateway
- **FR-014**: The two leaves' peering addresses MUST be distinct

**Population-Specific Requirements**

- **FR-015**: The system MUST create one virtual interface per k8s leaf, representing that
  leaf's VLAN 110 switched virtual interface
- **FR-016**: Exactly two such interfaces MUST exist — one on `leaf-nfd41-pod1-1-1` and one on
  `leaf-nfd41-pod1-1-2`
- **FR-017**: Each interface MUST attach the `IpamIPAddress` whose address equals the
  `peer_address` the corresponding `ClusterFabricPeering` row declares
- **FR-018**: After loading, `IpamIPAddress -> interface -> device` MUST be a complete traversal
  for both peering addresses
- **FR-019**: The change MUST NOT require any modification to `schemas/`
- **FR-020**: The change MUST NOT modify `generators/generate_fabric_peering.py` or its query
- **FR-021**: The hand-declared `peer_address` values in the seed data MUST be left in place.
  They remain authoritative until a follow-up cycle derives them; removing them now would leave
  a deleted session unrecreatable
- **FR-022**: The rendered Crossplane `FabricPeering` artifact MUST be byte-identical before and
  after the change

### Key Entities

- **`InterfaceVirtual`**: The peering SVI. A virtual interface that inherits the device parent
  relationship, layer-2 attributes, and the layer-3 address relationship. Depends on the leaf
  devices existing. This is the entity the cycle adds.
- **`IpamIPAddress`**: The peering addresses `10.110.0.2/24` and `10.110.0.3/24`. Already exist;
  this cycle attaches them rather than creating them.
- **`DcimDevice` (leaf)**: `leaf-nfd41-pod1-1-1` and `leaf-nfd41-pod1-1-2`. Already exist; the
  parent of each new interface.
- **`ClusterFabricPeering`**: The BGP sessions whose `peer_address` this cycle makes derivable.
  Read-only for this cycle — its rows are the oracle the new data is checked against, not
  something the cycle edits.
- **`EvpnSvi` / `EvpnSviNode`**: The existing fabric-side record of VLAN 110 and each leaf's
  address on it. Read-only for this cycle. `EvpnSviNode.ip_address` being an attribute rather
  than a relationship is the reason the traversal is missing.

### Key Files

- `objects/*.yml` — object data files, loaded in filename sort order
- `objects/34_nfd41_cluster.yml` — declares the peering addresses and the sessions; read by this
  cycle, not modified except for annotation
- `objects/27_nfd41_vrf_services.yml` — declares the VLAN 110 SVI and each leaf's address on it
- `schemas/base/dcim.yml`, `schemas/base/ipam.yml` — the definitions the new objects conform to;
  not modified
- `.infrahub.yml` — project configuration; not modified

### Dependency Load Order

```text
20_nfd41_device_types.yml   -- device types, including interface templates
26_nfd41_devices.yml        -- the leaf devices and their loopback/management addresses
27_nfd41_vrf_services.yml   -- EvpnSvi VLAN 110 and the per-leaf EvpnSviNode records
34_nfd41_cluster.yml        -- the peering IpamIPAddress objects and the sessions
<new file>                  -- the peering SVIs (depends on devices and on the addresses)
```

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All object files load without errors — no missing references, no schema
  validation failures
- **SC-002**: Exactly 2 peering SVI objects exist after loading, one per k8s leaf
- **SC-003**: Both peering addresses resolve through `interface` to a device, and the device
  each reaches is the one the corresponding session names as its peer
- **SC-004**: The shared VARP gateway `10.110.0.1` is attached to no interface
- **SC-005**: For each of the two sessions, deriving the peer address from the peer device
  yields exactly one candidate and it equals the hand-declared `peer_address` — demonstrating
  that a follow-up cycle can replace the hand-declared value without changing it
- **SC-006**: The rendered Crossplane `FabricPeering` artifact is byte-identical to the
  pre-change baseline, and its normalised digest equals the value cycles 011 and 012 recorded
- **SC-007**: Loading the object data twice succeeds and leaves the peering SVI count unchanged
- **SC-008**: No file under `schemas/` is modified, and no file under `generators/` is modified
- **SC-009**: The unit test suite passes with at least as many tests as before the change, and
  every project linter is clean
