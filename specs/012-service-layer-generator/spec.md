# Generator Specification: Service-Layer Fabric Peering Generator

> **Workflow type**: Infrahub Generator (design-driven automation)
> **Skill**: Use the `infrahub-managing-generators` skill to implement this specification.

**Feature Branch**: `012-service-layer-generator`
**Created**: 2026-09-10
**Status**: Draft
**Input**: User description: "lets continue onto next task"

The next task is fixed by the repository, not inferred. [spec 010's Out of Scope](../010-lab-service-layer-model/spec.md) lists it first — "Generators that materialize technical objects from service intent (**next cycle**)" — and FR-081 exists to make it possible: "Every concrete service kind MUST be reachable as a generator target, so a generator can sit underneath it and materialize the technical objects it implies."

It is also the missing half of the original request that opened cycle 010: *"a services schema with a generator that sits underneath the services schema."* 010 delivered the schema and 011 delivered a transform — 011 took the transform first only because its inputs were already loaded. The generator is what remains.

## Generator Overview

Today the technical objects beneath the peering service are **hand-written**. `objects/34_nfd41_cluster.yml` declares two `ClusterFabricPeering` rows by hand, naming the peer device, its BGP AS and its address. Every one of those facts already exists elsewhere in the graph, put there by the fabric model that AVD renders the switches from. Keeping them in two places by hand is the failure the lab's own notes describe:

> Change either side without the other and BGP either does not come up or comes up and carries nothing.

This generator removes the second copy. An operator orders one thing — "this cluster peers with the fabric" — and the sessions beneath it are derived from the cabling and the fabric's own BGP data. The Crossplane manifest that cycle 011 renders then follows automatically, so the loop is: **order a service → the generator materializes the technical objects → the transform renders the artifact.**

**Design Object (Source)**: `ServiceFabricPeering` — the ordered intent, already an instantiable generator target because it inherits `GeneratorTarget`

**Generated Objects (Targets)**: `ClusterFabricPeering` — one per fabric device the cluster's nodes are cabled to

**Target Group**: `service_fabric_peerings` — the `CoreStandardGroup` that cycle 011 created for the artifact definition

## Why this is derivable — what was verified against the live graph

This specification was written against loaded data on the `cx-peering` branch rather than from the schema alone, because whether the peer set is *derivable* decides the entire scope. Three traversals were checked:

| Fact | Path through the graph | Result |
| --- | --- | --- |
| Which fabric devices to peer with | `ClusterKubernetes.nodes` → `ComputePhysicalServer.interfaces` → `NetworkLink.connected_endpoints` → far-end device | ✅ `leaf-nfd41-pod1-1-1`, `leaf-nfd41-pod1-1-2` |
| The peer's BGP AS | far-end device → `DcimDevice.asn` → `RoutingAsn` | ✅ `65101` — identical to the hand-written value |
| The peer's address | `IpamIPAddress` `10.110.0.2/24` → `interface` | ❌ `null` — the address is free-standing |

The ASN result is the one that matters most: it is the same number, reached from the same node AVD reads, which is exactly the drift this feature exists to remove.

The address result is a genuine boundary, and it bounds the cycle honestly: **of the two facts
duplicated by hand today, this cycle makes one of them model-derived, not both.** The ASN stops
being a second copy; the address stays declared until the leaves' peering SVIs are modelled,
which is a schema cycle and therefore has to come first (FR-027, and the follow-up recorded
under Out of Scope).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sessions are derived from cabling, not typed twice (Priority: P1) 🎯 MVP

An operator has a Kubernetes cluster whose nodes are cabled into the fabric. Rather than writing one `ClusterFabricPeering` row per leaf and copying each leaf's BGP AS by hand, they order a single `ServiceFabricPeering` naming the cluster. The generator walks the cabling, finds the fabric devices those nodes attach to, reads each device's AS from the fabric model, and creates one session per device.

**Why this priority**: This is the whole feature. Without it the service layer is a label over hand-maintained rows, and the second copy of the ASN stays in the file where it can drift from the switch.

**Independent Test**: Delete the two hand-written `ClusterFabricPeering` rows, run the generator against `nfd41-fabric-peering`, and confirm two sessions reappear with the same peer devices and ASNs.

**Acceptance Scenarios**:

1. **Given** a `ServiceFabricPeering` whose cluster has three nodes cabled to two leaves, **When** the generator runs, **Then** exactly two `ClusterFabricPeering` objects exist, one per distinct fabric device
2. **Given** those sessions exist, **When** the generator runs again with nothing changed, **Then** no duplicates appear and no object is recreated
3. **Given** a leaf's `RoutingAsn` is changed in the fabric model, **When** the generator runs, **Then** the session's `peer_asn` follows it without anyone editing an object file
4. **Given** the generator has produced the sessions, **When** the Crossplane artifact is regenerated, **Then** it renders the same peers cycle 011 recorded

---

### User Story 2 - The rendered manifest does not change (Priority: P1) 🎯 MVP

The artifact from cycle 011 is deployed against a live cluster. Replacing hand-written rows with generated ones must not silently alter what reaches Kubernetes: same peers, same addresses, same AS numbers.

**Why this priority**: Equal to US1, because a generator that produces *different* sessions is not a refactor — it is an unreviewed change to a running BGP configuration. Cycle 011 left a byte-exact record of the current artifact, which makes this cheap to prove and negligent to skip.

**Independent Test**: Capture the artifact's checksum before, run the generator, regenerate, and compare.

**Acceptance Scenarios**:

1. **Given** the artifact checksum recorded in cycle 011, **When** the generator replaces the hand-written sessions and the artifact is regenerated, **Then** the checksum is unchanged
2. **Given** the rendered manifest, **When** compared field by field with `../lab/crossplane/platform/10-peering.yaml`, **Then** peer names, addresses and AS numbers still match

---

### User Story 3 - Removing a node removes only what it justified (Priority: P2)

A cluster node is decommissioned. If it was the last node attached to a given leaf, that session should disappear; sessions to leaves still carrying nodes must survive, and technical objects nobody's service created must not be touched.

**Why this priority**: The generator's tracking context runs with `delete_unused_nodes=True`, so cleanup is automatic and therefore dangerous. This story is where that behaviour is pinned down deliberately instead of discovered later. It is P2 because the destructive path is only reachable after US1 works.

**Independent Test**: Remove one node's cabling, re-run, and confirm the arithmetic of what disappeared.

**Acceptance Scenarios**:

1. **Given** three nodes across two leaves, **When** the only node attached to leaf 2 is removed, **Then** the leaf 2 session is deleted and the leaf 1 session remains
2. **Given** a `ClusterFabricPeering` that no service produced, **When** the generator runs, **Then** that object is not deleted
3. **Given** a `ServiceFabricPeering` whose cluster has no cabled nodes, **When** the generator runs, **Then** it fails loudly rather than deleting every session and reporting success

---

### Edge Cases

- **A node is cabled to a device that is not a fabric leaf** — for example an out-of-band switch or a firewall. The peer set must be filtered by role rather than accepting whatever is on the other end of a cable.
- **Two nodes attach to the same leaf** (the normal case — three nodes, two leaves). The peer set is the set of *distinct* devices; sessions must not be duplicated per node.
- **An MLAG pair shares one AS.** Both leaves here return `65101`. Two sessions with the same `peer_asn` are correct and must not be collapsed.
- **A node's interface is uncabled** (`connector` is null). It contributes no peer rather than raising.
- **The cluster has no `local_asn`.** The service cannot describe a working session; cycle 011's transform already refuses to render this, and the generator should not manufacture sessions that the renderer will reject.
- **A leaf has no `RoutingAsn`.** The session's mandatory `peer_asn` cannot be derived.
- **A newly cabled leaf has no recorded peering address.** Under FR-027 the generator cannot invent one, so it must fail naming that device rather than create a session that cannot come up.
- **The service is deleted entirely.** 010 left this open: are the sessions orphaned, cascaded, or blocked? `ClusterFabricPeering.cluster` is a mandatory `Parent` relationship to the cluster, not to the service, so deleting the service does not cascade to them.
- **Two services reference one cluster.** Both would derive the same peer set and fight over the same objects on every run.
- **The generator runs on a branch versus on main.** Cycle 011 established that `main` holds neither the schema nor the objects, so a branch is the only place this can currently run.

## Requirements *(mandatory)*

### Functional Requirements

**Generator Class & Method**:

- **FR-001**: Generator MUST inherit from `infrahub_sdk.generator.InfrahubGenerator`
- **FR-002**: Generator MUST implement `async generate(self, data: dict) -> None`
- **FR-003**: Generator MUST use `self.client` for all Infrahub SDK operations
- **FR-004**: Generator MUST consume the query response through generated typed models rather than raw dictionary indexing, per the repository's existing convention for every generator and transform

**GraphQL Query**:

- **FR-005**: A GraphQL query file MUST exist co-located in `generators/` (this repository's convention, which overrides the skill's suggested `queries/` layout)
- **FR-006**: The query MUST accept the parameter declared in the `.infrahub.yml` `parameters` mapping, resolving one `ServiceFabricPeering` by name
- **FR-007**: The query MUST fetch, in one round trip: the service, its cluster, the cluster's `local_asn`, the cluster's nodes, each node's interfaces, each interface's link, each link's far-end interface and that interface's device, and each such device's `role` and `asn`
- **FR-008**: The query MUST also fetch the sessions already attached to the cluster, so the generator can recognise what it is updating rather than only what it is creating

**Derivation**:

- **FR-009**: The peer set MUST be the **distinct** set of devices reached from the cluster's nodes through cabling, so two nodes on one leaf yield one session
- **FR-010**: The peer set MUST be filtered to fabric devices by role; a node cabled to a non-fabric device MUST NOT produce a session
- **FR-011**: `peer_asn` MUST be derived from the peer device's own `RoutingAsn` in the fabric model, never from the service or an object file — this is the requirement that removes the drift the feature exists to eliminate
- **FR-012**: `peer_device` MUST be set to the fabric device the cabling reached
- **FR-013**: Session ordering MUST be deterministic, so repeated runs and the artifact rendered from them do not churn

**Object Creation**:

- **FR-014**: Generator MUST create and maintain `ClusterFabricPeering` objects
- **FR-015**: All `save()` calls MUST use `allow_upsert=True`, so a re-run updates rather than fails, and so the two existing hand-written sessions are **adopted** on first run rather than duplicated
- **FR-016**: Generated sessions MUST be linked to the ordering `ServiceFabricPeering` through its `peerings` relationship, so the service can answer "what did I create"
- **FR-017**: `enabled` MUST default to true for a newly derived session, and MUST NOT be overwritten on an existing session that an operator has disabled

**Validation**:

- **FR-018**: Generator MUST fail with a message naming the object and the missing field when the cluster has no `local_asn`, when a derived peer device has no `RoutingAsn`, or when the cluster has no cabled nodes at all
- **FR-019**: Generator MUST NOT silently produce zero sessions; an empty peer set is an error, because cycle 011 established that an empty `peers` list yields a manifest that applies cleanly, reports healthy and carries no routes

**Tracking & Cleanup**:

- **FR-020**: Generator MUST be idempotent: running it twice against an unchanged model MUST leave the object set, its attributes, and the checksum of any artifact rendered from it unchanged
- **FR-021**: Sessions the generator previously created that are no longer justified by the cabling MUST be removed, so a decommissioned node does not leave a session behind
- **FR-022**: `ClusterFabricPeering` objects that this generator did not create MUST NOT be deleted by it — 010 raised this exact risk for hand-maintained technical objects, and the tracking context's `delete_unused_nodes=True` makes it the default failure mode rather than an unlikely one

**Registration**:

- **FR-023**: Generator MUST be registered in `.infrahub.yml` under `generator_definitions` with `name`, `file_path`, `query`, `targets`, `class_name`, and `parameters`
- **FR-024**: The GraphQL query MUST be registered under `queries`
- **FR-025**: The registration MUST target the existing `service_fabric_peerings` group rather than introducing a second group over the same objects

**Naming and addressing**:

Both of these were settled by asking rather than guessing, because each decides what reaches
a running cluster. Both answers were chosen to leave the deployed manifest untouched.

- **FR-026**: The session's `name` MUST be preserved on upsert for a session that already
  exists, and derived from the peer device's name only for a genuinely new session. The name
  is a lab-facing label — `k8s-leaf1` against device `leaf-nfd41-pod1-1-1` — that cycle 011's
  transform renders as `spec.peers[].name`. Preserving it adopts today's values with no
  renumbering and no change to the artifact. An ordinal scheme was rejected: it is positional,
  so inserting a leaf would silently rewrite the names of every peer after it in a deployed
  manifest
- **FR-027**: The session's `peer_address` MUST be taken from the address already recorded for
  that cluster and peer device, and the generator MUST fail naming the device when a newly
  derived peer has no recorded address. It MUST NOT invent, allocate, or reassign one
- **FR-028**: Because FR-026 and FR-027 both preserve existing values, a first run against the
  current model MUST be a pure adoption: the two hand-written sessions are matched, their names
  and addresses are kept, and only `peer_asn` becomes model-derived

### Key Entities

- **`ServiceFabricPeering`** (design object): the ordered intent. Carries `name`, `status`, `owner`, a mandatory `cluster`, optional `communities` and `advertisement_selector`, and the `peerings` relationship this generator fills. Already a `GeneratorTarget` and a `CoreArtifactTarget`.
- **`ClusterKubernetes`**: supplies `local_asn` and, through `nodes`, the cabling that determines the peer set.
- **`ComputePhysicalServer`**: a cluster node. Its interfaces are the starting point of every traversal.
- **`NetworkLink`**: the cable. Its `connected_endpoints` hold both interfaces; the far-end interface's device is the peer.
- **`DcimDevice`** (peer): supplies `role` for filtering and `asn` for `peer_asn`.
- **`ClusterFabricPeering`** (generated): one BGP session. Mandatory `cluster` (Parent), `peer_device`, `peer_asn`, `name`; `enabled` defaults true. Unique on `["cluster", "peer_device"]`, which is precisely the identity the derivation produces.
- **`RoutingAsn`**: the fabric's own AS record — the single source this feature makes authoritative.

### Key Files

| File | Purpose |
| --- | --- |
| `generators/generate_fabric_peering_service.py` | Generator class implementing `generate()` |
| `generators/generate_fabric_peering_service.gql` | Query fetching the service, cluster, cabling and peer ASNs |
| `generators/generate_fabric_peering_service_query.py` | Generated typed models (never hand-edited) |
| `.infrahub.yml` | Registration of the query and the generator definition |
| `objects/34_nfd41_cluster.yml` | Loses its two hand-written `ClusterFabricPeering` rows once the generator produces them |
| `tests/unit/test_generate_fabric_peering_service.py` | Unit coverage for derivation, dedup, filtering and the validation paths |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ordering one peering service against a cluster with cabled nodes produces one session per distinct fabric device, with no object file edited
- **SC-002**: Running the generator twice against an unchanged model changes nothing — no duplicates, no attribute churn, no new object versions
- **SC-003**: The peer AS numbers in the generated sessions match what the fabric model holds for those devices, for 100% of sessions, with no second copy of the number anywhere in the repository
- **SC-004**: The Crossplane artifact rendered after the generator runs is **byte-identical** to the one cycle 011 recorded, proving the change is a refactor rather than a silent reconfiguration
- **SC-005**: Changing a leaf's AS in the fabric model and re-running updates the session and moves the artifact's checksum, demonstrating the two ends can no longer drift apart
- **SC-006**: Removing the last node attached to a leaf removes exactly that leaf's session and no other object
- **SC-007**: A technical object the generator did not create survives a run untouched
- **SC-008**: An incomplete model — no cluster AS, no cabled nodes, a peer with no AS, or a newly derived peer with no recorded address — fails with a message naming the object and the field, and produces no partial session set
- **SC-009**: The generator can be exercised locally against a named service before it is registered
- **SC-010**: All unit tests and the repository's linters pass

## Assumptions

1. **The peer set is derived from cabling, not declared on the service.** `ServiceFabricPeering` has no relationship naming which devices to peer with, and adding one would make this a schema cycle. Derivation also matches what a generator is for, and the traversal was verified to work against loaded data.
2. **Cycle 011's artifact is the regression oracle.** Its recorded checksum and field-by-field comparison make "did this change what reaches the cluster?" a cheap, exact question.
3. **The existing hand-written sessions are adopted, not duplicated.** They already carry the identity the derivation produces — the same cluster and peer devices — and `ClusterFabricPeering` is unique on that pair, so an upsert matches them.
4. **`objects/34_nfd41_cluster.yml` loses its two hand-written session rows** once the generator produces them, since keeping both would leave the second copy this feature exists to remove. The cluster, its nodes and its addresses stay.
5. **Fabric devices are identified by role.** The lab's peers are `leaf`; the filter is expressed in terms of role rather than a name pattern.
6. **This cycle covers one service kind.** `ServiceFabricApp`, `ServiceAppAccess` and the three WAN services also inherit `GeneratorTarget`, but `ServiceFabricPeering` is the only one with loaded data, a working downstream artifact, and a hand-written technical layer to replace.
7. **Delivery is unchanged.** This cycle changes how technical objects come to exist, not how the artifact reaches the cluster.
8. **One of the two duplicated facts is fixed, deliberately.** `peer_asn` becomes model-derived; `peer_address` stays declared because nothing in the fabric model connects it to a device (verified: `interface: null`). Fixing both would require modelling the leaves' SVIs, which is a schema cycle. Doing half now is what keeps this cycle to one artifact type and leaves the deployed manifest byte-identical.

## Out of Scope

- Generators for the other five service kinds.
- Any schema change. If a clarification below forces one, it belongs in a schema cycle first, per the layering rule 010 established.
- Modelling the peering VLAN's SVIs on the leaves. This is the follow-up that would finish the job FR-027 leaves half-done — with the address reachable from the peer device, it too could be derived and the last hand-maintained copy would go. It is a schema change, so it is a cycle of its own and must precede any generator change that depends on it.
- Changing the Crossplane transform, the AVD pipeline, or anything the fabric generators emit.
- The fabric side of the session. `RoutingBGPNeighbor` on the leaf is what AVD renders; this generator produces the cluster side only.
- Wiring the Vidra operator.

## Dependencies

- Cycle 010's schema (`ClusterKubernetes`, `ClusterFabricPeering`, `ServiceFabricPeering`) — merged.
- Cycle 011's transform and artifact definition, which provide the regression oracle — merged.
- Loaded object data including the cluster, its nodes and the fabric cabling. Currently present only on a feature branch; `main` has neither the schema nor the data.
- A reachable Infrahub instance whose scheduled repository sync is running. Cycle 011 found that sync silently stops when an orphaned Prefect run holds its concurrency slot.
