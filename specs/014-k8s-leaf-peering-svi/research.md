# Phase 0 — Research: k8s Leaf Peering SVIs

**Feature**: `specs/014-k8s-leaf-peering-svi`
**Date**: 2026-09-10
**Infrahub**: 1.10.6 | **SDK**: 1.22.0

Every finding below was verified against the live instance on branch `svi-model` (schema and
objects loaded from this worktree), not inferred from reading YAML. Where a claim could have
been taken on trust from the task framing, it was re-checked; two of those re-checks changed
the design.

---

## R1 — Does this need a schema change?

**Decision**: No. This is an object-data cycle.

**Verification**:

- `InterfaceVirtual` exists as a concrete node (`schemas/base/dcim.yml:520`), inheriting
  `DcimInterface`, `InterfaceLayer2` and `InterfaceLayer3`. 14 instances are already loaded —
  a `Loopback0` on each of the 14 switches.
- `IpamIPAddress.interface` exists (`schemas/base/dcim.yml` peer side; `schemas/base/ipam.yml:30`),
  `cardinality: one`, `optional: true`, peer `InterfaceLayer3`.
- Both halves of the traversal the follow-up cycle needs therefore already exist. Nothing under
  `schemas/` has to change, and per the spec's FR-019 nothing under `schemas/` may change.

**Rationale**: The project constitution's first principle is schema-driven architecture, so the
temptation in a cycle like this is to add a relationship. That would have been wrong here: the
model already expresses "an address lives on an interface" and "an interface belongs to a
device". What was missing was not vocabulary but *instances*.

**Alternatives considered**:

- *Make `EvpnSviNode.ip_address` a relationship instead of an `IPHost` attribute.* This is the
  most direct reading of the problem — `EvpnSviNode` already records exactly the (device,
  address) pairing this cycle needs, and it is the fabric's own record rather than a new one.
  Rejected: it is a schema change, explicitly out of scope, and a breaking one. `ip_address` is
  read as a string by `generate_avd_device_hostvar.py:1705` and again at `:1792`; converting it
  to a relationship changes the shape every one of those call sites sees, which would move AVD
  output. That is a much larger blast radius than adding two interfaces, and it would have to be
  justified on its own rather than smuggled into a data cycle. It remains the better long-term
  model and is recorded here as a candidate for a later cycle.

---

## R2 — Which relationship carries the address? *(this one changed the design)*

**Decision**: `InterfaceVirtual.ip_addresses` — the relationship whose identifier is
`interfacelayer3__ipamipaddress`. **Not** `InterfaceVirtual.ip_address`.

**Verification**: `InterfaceVirtual` has *two* relationships to `IpamIPAddress`:

| Relationship | Cardinality | Identifier | Reverse side on `IpamIPAddress` |
| --- | --- | --- | --- |
| `ip_addresses` | many | `interfacelayer3__ipamipaddress` | **yes** — `IpamIPAddress.interface` |
| `ip_address` | one | `interface__ip_address` | **no** |

Dumping every relationship on `IpamIPAddress` from the live schema returns exactly one
interface-facing edge — `interface`, identifier `interfacelayer3__ipamipaddress`. The
`interface__ip_address` relationship, added by `schemas/dcim_extensions.yml`, has no counterpart
on the address node at all.

**Rationale**: This is the crux of the cycle. The goal is to make `peer_address` derivable, and
the derivation starts from a device and must reach an address (or starts from an address and must
reach a device). Only `interfacelayer3__ipamipaddress` is navigable in both directions. Writing
the link into `ip_address` would look correct in the UI, would satisfy a naive "the SVI has an
address" reading, and would leave `IpamIPAddress.interface` still null — reproducing the exact
condition this cycle exists to fix, while appearing to have fixed it. That is the silent failure
worth the most care here.

**Consequence for the file syntax**: the edge must also be *written* from the interface side.
`IpamIPAddress.interface` peers the generic `InterfaceLayer3`, and the live schema reports
`human_friendly_id: None` for that generic. Per the `infrahub-managing-objects` rule
`value-generic-relationships.md`, a reference to a generic with no HFID cannot be resolved by the
loader and fails with "Unable to lookup node by HFID". So even though the relationship is
bidirectional once created, only one of the two directions can be expressed in seed YAML.

**Alternatives considered**:

- *Write it from the address side using the documented inline-`kind:` workaround.* The rule for
  generics without an HFID says to use an inline data block with an explicit concrete `kind:`.
  That would work syntactically. Rejected because it inverts ownership: the address file would
  then have to restate the interface's mandatory `device` parent, making `34_nfd41_cluster.yml`
  the creator of leaf interfaces. Writing from the interface side keeps each object declared by
  the file that owns it.
- *Set both relationships.* Rejected: `ip_address` is consumed by
  `src/solution_arista_avd/addressing.py:29` on the fabric P2P addressing path. Populating a
  relationship that an addressing generator reads, for data that generator did not allocate, is
  an invitation to a later conflict for no benefit — `ip_addresses` alone satisfies every
  requirement.

---

## R3 — Which device carries the SVI?

**Decision**: `leaf-nfd41-pod1-1-1` and `leaf-nfd41-pod1-1-2`.

**Verification**: the two `ClusterFabricPeering` rows declare
`peer_device: leaf-nfd41-pod1-1-1` / `leaf-nfd41-pod1-1-2`. `ClusterFabricPeering.peer_device`
peers `DcimGenericDevice`, which does have `human_friendly_id: ['name__value']`, so the scalar
reference form is correct and is already proven by that existing seed data.

**The trap**: the lab models the same two physical switches a second time as `k8s-leaf1` and
`k8s-leaf2` (their containerlab hostnames). Both duplicates exist as devices and both carry a
`Loopback0`. Attaching the peering addresses to the duplicates would produce a model that looks
right in isolation but that the derivation cannot use, because the derivation starts from
`peer_device`, which names the `leaf-nfd41-*` objects.

This duplication is **pre-existing and out of scope**. It is recorded here because it is a live
hazard for the follow-up cycle, not because this cycle fixes it.

---

## R4 — Interface name, and collision with template-generated interfaces

**Decision**: `Vlan110`.

**Verification**: `DcimInterface` has `uniqueness_constraints: [[device, name__value]]` and
`human_friendly_id: [device__name__value, name__value]`, so the name only has to be unique per
device. Querying `InterfaceVirtual` on `leaf-nfd41-pod1-1-1` returns exactly one interface,
`Loopback0`, created from the device-type template in `objects/20_nfd41_device_types.yml` via
`TemplateInterfaceVirtual`. `Vlan110` does not collide.

**Rationale**: `Vlan110` is the name EOS and AVD use for the SVI of VLAN 110, and it is the name
the existing descriptions in `objects/34_nfd41_cluster.yml` already use in prose
("leaf-nfd41-pod1-1-1 Vlan110 SVI"). Matching the string that is already written down means the
model now says formally what the comment said informally.

**Note on the computed `index` attribute**: `schemas/dcim_extensions.yml` gives `DcimInterface` a
read-only computed `index`, rendered by the Jinja2 template
`{{ "%03d" | format(name__value | split_interface | last | int) }}`. `Loopback0` currently
computes to `000`. `Vlan110` is expected to compute to `110`. This is asserted after loading
rather than assumed, because a computed attribute that raises on an unexpected name would surface
as a confusing load-time failure.

---

## R5 — Blast radius: what else reads a device's interfaces?

**Decision**: adding two `InterfaceVirtual` objects is expected to be inert to every existing
artifact, and the Crossplane artifact proves it byte-for-byte.

**Verification**, by inspecting each consumer that enumerates interfaces:

| Consumer | Behaviour with a new `InterfaceVirtual` |
| --- | --- |
| `generators/generate_avd_device_hostvar.py` | Guards explicitly — `if _typename(...) != "InterfacePhysical"` at lines 802, 1137, 1202, 2109. Virtual interfaces are skipped. |
| `generators/avd_device_hostvar.gql` | Selects interface fields only inside `... on InterfacePhysical` fragments. A virtual interface contributes `__typename` and `id` and nothing else. |
| `transforms/cabling_plan.gql` / `.py` | Same — fields are selected inside `... on InterfacePhysical`. An SVI has no cabling. |
| `transforms/computed_interface_description` | Traverses `connector -> connected_endpoints`. An SVI has no connector, so it yields nothing. |
| `transforms/crossplane_fabric_peering` | Does not touch interfaces at all. Covered by the byte-identical baseline check regardless. |

**The strongest existing evidence** is not any of the above: it is that every one of the 14
switches *already* carries an `InterfaceVirtual` (`Loopback0`), and all of these artifacts render
correctly today. Adding a second virtual interface is the same shape as data that is already
present, not a new shape.

**Residual risk, stated honestly**: the byte-identical check in this cycle covers the Crossplane
artifact only. The AVD artifacts are not part of the declared regression oracle. The type guards
above are strong, but "strong argument" is not "measured". Phase 2 therefore adds an explicit
before/after render of an AVD EOS config for one of the two affected leaves, so the claim is
measured rather than reasoned. If that render moves, the cycle stops.

---

## R6 — File placement and load order

**Decision**: a new file, `objects/36_nfd41_peering_svis.yml`.

**Rationale**:

- It must sort **after** `34_nfd41_cluster.yml`, which declares the two `IpamIPAddress` objects
  the SVI references by human-friendly id. The loader resolves references against objects that
  already exist, so the addresses must be created first.
- It must sort after `26_nfd41_devices.yml`, which creates the leaves. `34` already does.
- `35` is taken by `35_nfd41_peering_service.yml`, so `36` is the next free number, satisfying the
  constitution's "add to existing numbered files or use the next available sequence number".

**Alternatives considered**:

- *Append a document to `objects/34_nfd41_cluster.yml`.* Tempting, because the addresses are
  declared there and the file already tells the peering story. Rejected: `34` is titled "the
  Kubernetes cluster as a routing participant" and owns cluster-side facts. A leaf's interface is
  a fabric-side fact. Keeping them apart means the follow-up cycle that deletes hand-declared
  `peer_address` rows from `34` does not have to pick its way around fabric data in the same file.
- *Append to `objects/27_nfd41_vrf_services.yml`, next to `EvpnSviNode`.* This is where the
  conceptually closest data lives. Rejected on load order: `27` sorts *before* `34`, so the
  addresses would not exist yet. Declaring them inline in `27` instead would mean two files
  upserting the same `IpamIPAddress` objects with different descriptions, where the later load
  wins — exactly the kind of order-dependent data this repo has been careful to avoid.

---

## R7 — Idempotence

**Decision**: no special handling required; verified by loading twice.

**Rationale**: `infrahubctl object load` uses `allow_upsert=True` and matches on human-friendly
id. `InterfaceVirtual`'s HFID is `[device__name__value, name__value]`, both of which are fixed
literals in the seed file, so a second load matches the existing object and updates it in place.
The `ip_addresses` reference resolves to the same two address objects. Nothing in the file
allocates from a pool or depends on execution order, which are the two usual sources of
non-idempotence in this repo.

This is asserted by measurement (SC-007), not by argument.

---

## R8 — Where the seed data's `peer_address` rows stand after this cycle

**Decision**: leave every hand-declared value in `objects/34_nfd41_cluster.yml` exactly as it is.

**Rationale**: cycle 012's annotation is explicit that these rows are not removed, because they
are the only record of each session's address and deleting them would leave a deleted session
unrecreatable. That reasoning is unchanged by this cycle: until a generator actually derives
`peer_address`, the seed rows are still the only source. Removing them now would break the model
in exchange for tidiness.

What *does* change is the annotation, which currently says removal "becomes possible once the
leaves' peering SVIs are modelled". After this cycle that precondition is met, so the comment is
updated to say the data is now in place and to name what the follow-up must do. The values
themselves are untouched — which is also what keeps the artifact byte-identical.
