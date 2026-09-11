# Contract: Peering SVI Object Data

**Feature**: `specs/014-k8s-leaf-peering-svi`
**Consumers**: a future `generate-fabric-peering` change; anyone querying "which device owns this
address?"

This is the interface this cycle exposes. A later cycle may rely on every clause below; nothing
here may be weakened without a corresponding change to whatever consumes it.

---

## C1 — The traversal exists and is total

For each of the two peering addresses:

```text
IpamIPAddress(address = A) -> interface -> device -> name
```

resolves to exactly one device, with no null link at any step.

| Address | Resolves to |
| --- | --- |
| `10.110.0.2/24` | `leaf-nfd41-pod1-1-1` |
| `10.110.0.3/24` | `leaf-nfd41-pod1-1-2` |

**Guaranteed by**: the `ip_addresses` relationship (identifier `interfacelayer3__ipamipaddress`),
which is the only interface-facing relationship `IpamIPAddress` has, and the mandatory `device`
parent on every interface.

**Not guaranteed by**: `InterfaceVirtual.ip_address` (identifier `interface__ip_address`), which
has no reverse side and would leave this contract unsatisfied while appearing to attach the
address. A consumer MUST traverse `interface`, not assume either relationship will do.

---

## C2 — The derivation is unambiguous

For each leaf named as a `ClusterFabricPeering.peer_device`, the set

```text
{ addresses on that device's interfaces that fall inside 10.110.0.0/24 }
```

has **exactly one** member.

This is the property that makes `peer_address` derivable. A consumer may implement the derivation
as "the single address this device owns inside the cluster's node prefix" and rely on there being
no second candidate to choose between.

**Threat this closes**: the MLAG pair's shared VARP gateway `10.110.0.1` is a member of that
prefix and is present on *both* leaves in the fabric's intent (`EvpnSvi.ip_virtual_router_addresses`).
If it were ever attached to an interface, this contract would break and the derivation would
silently become ambiguous. It is therefore asserted that `10.110.0.1` is attached to no interface.

---

## C3 — The derived value equals the declared value

For each session:

```text
derive(session.peer_device) == session.peer_address
```

| Session | `peer_device` | Declared `peer_address` | Derived |
| --- | --- | --- | --- |
| `k8s-leaf1` | `leaf-nfd41-pod1-1-1` | `10.110.0.2/24` | `10.110.0.2/24` |
| `k8s-leaf2` | `leaf-nfd41-pod1-1-2` | `10.110.0.3/24` | `10.110.0.3/24` |

This is what makes the follow-up cycle a refactor rather than a change: the generator can start
setting `peer_address` from the traversal and no value moves.

---

## C4 — Device naming

Peering SVIs are attached to the device names that `ClusterFabricPeering.peer_device` uses —
`leaf-nfd41-pod1-1-1` and `leaf-nfd41-pod1-1-2`.

The lab also models the same two switches as `k8s-leaf1` / `k8s-leaf2`. Those objects are **not**
part of this contract and carry no peering address. A consumer must not resolve a peer through
the containerlab hostname.

---

## C5 — Nothing else moves

| Invariant | Why a consumer cares |
| --- | --- |
| The rendered Crossplane `FabricPeering` artifact is byte-identical to the cycle 011/012 baseline; its normalised digest is `0d800c9d5005b5fdb6b371bb5627d143` | This manifest is applied to a live cluster by a controller. A moved checksum means the cycle changed what runs. |
| No file under `schemas/` changes | This is an object-data cycle; a schema change would need its own review. |
| No file under `generators/` changes | The generator change is the follow-up, deliberately separated. |
| The declared `peer_address` values are unchanged | They remain the source of truth until the follow-up lands. |

---

## C6 — Idempotence

Loading the object data any number of times produces the same two SVIs with the same
attachments. The seed file contains no pool allocation and no order-dependent value; both objects
are addressed by a fixed human-friendly id.

---

## What this contract does NOT promise

- **That any generator uses it.** This cycle adds data only. `generate_fabric_peering.py` still
  sets `peer_asn` and leaves `peer_address` to the seed file. Wiring the derivation is the
  follow-up cycle's job.
- **That every device in the fabric has a peering SVI.** Only the two k8s leaves do. A consumer
  iterating devices must tolerate a device with no address in the node prefix.
- **That the address is allocated from a pool.** These addresses are pinned in seed data to match
  the deployed lab, exactly as the rest of the NFD41 fabric model is.
