# Generator Specification: Derive the Peering Address

> **Workflow type**: Infrahub Generator (design-driven automation)
> **Skill**: Use the `infrahub-managing-generators` skill to implement this specification.

**Feature Branch**: `015-derive-peer-address`
**Created**: 2026-09-11
**Status**: Draft
**Input**: "Please tackle the outstanding items" — this is the follow-up cycle 014 explicitly scoped out, and the second half of what cycle 012 deliberately left undone.

## Generator Overview

Cycle 012 made a `ClusterFabricPeering`'s `peer_asn` derived: it is read from the peer device's
own `RoutingAsn`, the same node AVD renders the switch from, so the two ends of the session
cannot drift apart. It could not do the same for `peer_address`, because nothing in the graph
connected an address to a device — `IpamIPAddress.interface` was null.

Cycle 014 fixed that by modelling each k8s leaf's `Vlan110` SVI with its own peering address.
The traversal `peer_device → interfaces → ip_addresses` is now complete.

This cycle consumes it. After it, **both** facts that were duplicated by hand are derived from
the fabric model, and `objects/34_nfd41_cluster.yml` loses the last hand-maintained copy.

**Design Object (Source)**: `ServiceFabricPeering`
**Generated Objects (Targets)**: `ClusterFabricPeering`
**Target Group**: `service_fabric_peerings`

## What changes, precisely

| Field | Before this cycle | After |
| --- | --- | --- |
| `peer_device` | derived from cabling | unchanged |
| `peer_asn` | derived from `DcimDevice.asn` | unchanged |
| `peer_address` | **hand-declared in object data, preserved on adopt** | **derived from the peer device's SVI** |
| `name` | hand-declared, preserved on adopt | unchanged — still a lab-facing label |

The `create` path that cycle 012 proved unreachable becomes reachable: with an address
derivable from the device, a newly cabled leaf can get a session without a human writing one
first. That closes the limitation recorded in 012's acceptance evidence.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The address follows the fabric (Priority: P1) 🎯 MVP

An operator changes a leaf's peering SVI address in the fabric model. The BGP session's
`peer_address` follows it, with no object file edited.

**Why this priority**: It is the feature, and it is the half of the drift problem cycle 012
could not close.

**Independent Test**: Change an SVI's address, re-run the generator, observe the session follow.

**Acceptance Scenarios**:

1. **Given** a leaf with a `Vlan110` SVI carrying `10.110.0.2/24`, **When** the generator runs, **Then** the session's `peer_address` resolves to that address object
2. **Given** the hand-written address in `objects/34_nfd41_cluster.yml` has been removed, **When** the generator runs, **Then** the sessions still carry the correct addresses
3. **Given** a leaf whose SVI address changes, **When** the generator runs, **Then** the session follows and the rendered manifest changes accordingly
4. **Given** an unchanged model, **When** the generator runs twice, **Then** nothing changes

---

### User Story 2 - A new leaf provisions without a human writing a session (Priority: P1) 🎯 MVP

A cluster node is cabled to a leaf that has no session yet. Because the address is now
derivable, the generator creates the session rather than refusing.

**Why this priority**: Equal to US1. Cycle 012's evidence recorded "there is no create path, and
there cannot be" as a real limitation; this is the cycle that removes it.

**Acceptance Scenarios**:

1. **Given** a cabled leaf with a peering SVI and no session, **When** the generator runs, **Then** a session is created with the derived address, ASN and device
2. **Given** a cabled leaf with **no** peering SVI, **When** the generator runs, **Then** it fails naming that device, because an address still cannot be invented
3. **Given** a leaf whose SVI has two addresses, **When** the generator runs, **Then** it fails rather than guessing which is the peering address

---

### User Story 3 - The rendered manifest does not change (Priority: P1) 🎯 MVP

Deriving the address must not alter what reaches the cluster.

**Why this priority**: The same reasoning as cycles 012 and 013. A generator that produces a
*different* address is an unreviewed change to a live BGP session.

**Acceptance Scenarios**:

1. **Given** the artifact checksum `0d800c9d5005b5fdb6b371bb5627d143`, **When** the generator derives the addresses and the artifact is regenerated, **Then** the checksum is unchanged
2. **Given** the rendered manifest, **When** compared with `../lab/crossplane/platform/10-peering.yaml`, **Then** the peer addresses still match

---

### Edge Cases

- **A leaf with no peering SVI.** Must fail naming the device; the address cannot be invented.
- **An SVI with several addresses.** Ambiguous — must fail rather than pick one.
- **Several SVIs on one leaf**, only one of which is the peering VLAN. The selection must be principled, not positional.
- **An address on the SVI that is outside the cluster's peering prefix.** Probably a modelling error.
- **The SVI exists but its address is the MLAG shared VARP gateway.** An anycast address cannot identify one BGP peer; `ClusterFabricPeering`'s schema comment already warns about this.
- **An existing session whose hand-declared address disagrees with the derived one.** This is the drift the cycle exists to expose — it must be visible, not silently overwritten.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The query MUST traverse from the peer device to its interfaces and their IP addresses, in the same round trip it already uses
- **FR-002**: `peer_address` MUST be derived from the peer device's peering SVI, never from an object file or an existing session
- **FR-003**: The peering SVI MUST be selected by a principled rule — not the first interface returned — and that rule MUST be stated
- **FR-004**: A derived address MUST be the same `IpamIPAddress` object the SVI references, not a copy
- **FR-005**: The generator MUST now support creating a session for a cabled leaf that has none, since the address is no longer unobtainable
- **FR-006**: The generator MUST fail, naming the device, when a cabled fabric peer has no peering SVI, more than one candidate address, or an ambiguous SVI
- **FR-007**: Adoption MUST still preserve `name` and `enabled`; only `peer_asn` and `peer_address` are derived
- **FR-008**: An existing session whose recorded address differs from the derived one MUST be reported, so drift is surfaced rather than silently corrected
- **FR-009**: The generator MUST remain idempotent: an unchanged model leaves objects, attributes and the artifact checksum unchanged
- **FR-010**: ~~`objects/34_nfd41_cluster.yml` MUST lose its hand-declared `peer_address` values~~ — **revised during implementation.** Both `peer_asn` and `peer_address` are `optional: false`, so an object file cannot declare a session without them; removing them means removing the rows, and the rows carry `name`. The file keeps them as **seeds the generator overwrites**, and the annotation MUST say so
- **FR-011**: All existing guarantees MUST hold — distinct peers, near-end exclusion, role filtering, deterministic ordering, and no deletion of objects the generator did not create

### Key Entities

- **`ClusterFabricPeering`**: gains a derived `peer_address`. `name` stays declared.
- **`InterfaceVirtual`** (the SVI): the new link in the traversal, added by cycle 014.
- **`IpamIPAddress`**: the address object, now reachable from its device.
- **`DcimDevice`**: supplies role, ASN and now — through its SVI — the address.

### Key Files

| File | Purpose |
| --- | --- |
| `generators/generate_fabric_peering.gql` | Extended traversal to the peer device's SVI addresses |
| `generators/generate_fabric_peering_query.py` | Regenerated |
| `generators/generate_fabric_peering.py` | Derivation, the restored create path, drift reporting |
| `objects/34_nfd41_cluster.yml` | Loses the hand-declared addresses |
| `tests/unit/test_generate_fabric_peering.py` | Extended |

## Success Criteria *(mandatory)*

- **SC-001**: Both sessions carry addresses derived from their leaf's SVI, with no address in any object file
- **SC-002**: The artifact checksum is `0d800c9d5005b5fdb6b371bb5627d143` — unchanged
- **SC-003**: Changing an SVI address moves the session and the artifact checksum
- **SC-004**: Deleting both sessions and re-running recreates them completely — the create path cycle 012 could not offer
- **SC-005**: A cabled leaf with no peering SVI fails naming the device, with nothing written
- **SC-006**: An ambiguous SVI selection fails rather than guessing
- **SC-007**: Two runs against an unchanged model change nothing
- **SC-008**: ~~`objects/34_nfd41_cluster.yml` contains no `peer_address`~~ — **unachievable, see FR-010.** Replaced by: the file's `peer_asn` and `peer_address` are documented as seeds, and the generator's derived values win over them
- **SC-009**: All unit tests and the repository's linters pass

## Assumptions

1. **Cycle 014's SVIs are the source.** Each k8s leaf has a `Vlan110` SVI with role `peering` carrying its own address.
2. **The peering VLAN identifies the SVI.** Selection is by a property of the interface, not by position.
3. **Cycle 011's artifact is the regression oracle**, as in every cycle since.
4. **`name` stays declared.** It is a lab-facing label that is not derivable — cycle 012 settled this, and nothing here changes it.
5. **`EvpnSviNode.ip_address` remains a separate record.** Cycle 014 flagged the duplication; collapsing it is a schema change and its own cycle.

## Out of Scope

- Converting `EvpnSviNode.ip_address` to a relationship.
- Deriving `name`.
- Generators for the other five service kinds.
- Any schema change.
- The FabricApp transform, the check cycle, and everything else in the backlog.
