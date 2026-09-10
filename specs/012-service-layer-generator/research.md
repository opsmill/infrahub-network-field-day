# Phase 0 Research: Service-Layer Fabric Peering Generator

**Feature**: `specs/012-service-layer-generator` | **Date**: 2026-09-10

Ten decisions. Each resolved against the `infrahub-managing-generators` skill, the seven
existing generators in this repository, the installed `infrahub-sdk` source, or the live
graph on the `cx-peering` branch. No NEEDS CLARIFICATION items remain.

---

## R1 — Target group: `CoreStandardGroup`, and the apparent contradiction explained

**Decision**: Register `targets: service_fabric_peerings`, the existing `CoreStandardGroup`.

The skill's `registration-config.md` says `targets` "references a `CoreGeneratorGroup`",
which contradicts this repository, where all seven generators target `CoreStandardGroup`
objects (`fabrics`, `pods`, `racks`, `servers`, `avd_devices`) and demonstrably work.

Reading the SDK resolves it — **there are two different groups**, and only one of them is
the target:

| Group | Kind | Created by | Purpose |
| --- | --- | --- | --- |
| `service_fabric_peerings` | `CoreStandardGroup` | `objects/00_groups.yml` | The *target* group: which objects the generator runs against |
| `<identifier>-<params>` | `CoreGeneratorGroup` | the SDK, at runtime | The *tracking* group: what this run created, used for cleanup |

`InfrahubGenerator.run()` picks the tracking group's type itself:

```python
group_type = "CoreGeneratorGroup" if self.execute_after_merge else "CoreGeneratorAwareGroup"
```

So the skill's rule describes the tracking group, which the SDK manages, not the target group,
which the repository declares. No new group is needed, and FR-025 stands.

**Alternatives considered**: a second, generator-specific group — rejected as duplicate
membership over the same single object, with two places to forget to add a service.

---

## R2 — The traversal, and the near-end trap

**Decision**: One query walking `ServiceFabricPeering` → `cluster` → `nodes` →
`interfaces` → `connector` (`NetworkLink`) → `connected_endpoints` → far-end interface →
`device` → `role`, `asn`.

Verified live. The shape that matters:

```text
NetworkLink "nfd41-k8s-node1-eth1".connected_endpoints:
  endpoint: eth1        | device: k8s-node1              ← the near end
  endpoint: Ethernet10  | device: leaf-nfd41-pod1-1-1    ← the peer
```

**`connected_endpoints` returns both ends, including the cluster node's own interface.** A
generator that took the first endpoint, or every endpoint, would try to peer the cluster with
itself and create a session whose `peer_device` is a `ComputePhysicalServer`. The near end
must be excluded explicitly — by interface id, which is unambiguous, rather than by device
kind, which happens to work only because cluster nodes are not `DcimDevice`.

**Alternatives considered**:

- *A query per node* — rejected: N round trips for data one traversal already returns, and the
  repository's existing generators fetch their whole design in one query.
- *Deriving peers from the leaf side* (find devices with an interface in the peering VLAN) —
  rejected: it depends on SVI modelling that FR-027 established does not exist yet.

---

## R3 — Adoption without overwriting: build a different payload, do not "update everything"

**Decision**: Fetch existing sessions in the same query, and for a device that already has a
session, omit `name` and `peer_address` from the upsert payload entirely.

This is the mechanical consequence of FR-026 and FR-027. `save(allow_upsert=True)` writes
whatever the payload contains, so "preserve the existing name" cannot be expressed by passing
the name — it is expressed by *not passing it*. Two payload shapes:

| Case | Payload |
| --- | --- |
| Session exists for this `(cluster, peer_device)` | `peer_asn` only — plus `cluster` and `peer_device` to resolve the node |
| No session exists | `name`, `peer_asn`, `peer_device`, `cluster`, `enabled` — and **fail** if no address is recorded (FR-027) |

`enabled` is treated the same way (FR-017): never sent for an existing session, so an operator
who disabled a session keeps it disabled across runs.

**Alternatives considered**:

- *Read-modify-write via `client.get()` per device* — rejected: an extra round trip per peer to
  retrieve data the query can return, and it races with the query it duplicates.
- *Always send every field* — rejected: it is precisely what the two clarifications ruled out,
  and it would rewrite `name` and `peer_address` on the first run, moving the artifact checksum
  and breaking SC-004.

---

## R4 — Why FR-022 holds by construction, and where the real danger is

**Decision**: Rely on the tracking context's own scoping; use `update_group_context=False` for
any object the generator touches but does not own.

From `infrahub_sdk/query_groups.py`:

```python
self.unused_member_ids = list(set(existing_group.members.peer_ids) - set(members))
```

Deletion candidates are **last run's group members minus this run's**. An object that was never
a member — a hand-written `ClusterFabricPeering`, a session another service created — is not in
the left-hand set and therefore cannot be deleted. FR-022 is satisfied by the SDK's design, not
by generator code.

Two precise consequences worth stating, because both are easy to get wrong in the other
direction:

1. **Adoption is one-way.** The moment the generator upserts a hand-written session, that
   session joins the tracking group and is thereafter managed — including deleted if it stops
   being justified. That is intended (FR-015, FR-021), but it means the first run is the point
   of no return, which is why SC-004 checks the artifact immediately after it.
2. **The "deletes everything and reports success" fear is narrower than it looks.**
   `update_group()` begins `if not members: return`, so a run that writes *nothing at all*
   deletes nothing. The dangerous case is a run that writes *some* peers — a partial traversal
   — because the rest are then absent from `members` and get deleted. FR-018 and FR-019 target
   exactly that case: fail before writing anything rather than write a partial set.

`update_group_context=False` is the repository's existing tool for this distinction;
`generate_rack.py` and `generate_fabric.py` already use it when saving objects they touch but
do not own.

---

## R5 — Deriving `peer_asn`

**Decision**: `peer_device.asn` → `RoutingAsn`, read as the AS number.

Verified: `leaf-nfd41-pod1-1-1.asn` returns `RoutingAsn` with display label `65101`, identical
to the hand-written `peer_asn: 65101`. This single fact is the feature's whole justification —
the number now comes from the node AVD renders the switch from, so the two ends cannot drift.

An MLAG pair shares one AS, so both leaves return `65101`. Two sessions with equal `peer_asn`
are correct and must not be deduplicated on ASN; dedup is on device (R6).

**Alternatives considered**: reading the AS from the device's BGP peer-group or session
objects — rejected as an indirection that can disagree with `DcimDevice.asn`, which is the
attribute the fabric model treats as authoritative.

---

## R6 — Which devices count as peers

**Decision**: Keep far-end devices whose `role` is in `{leaf, border_leaf, l2leaf}`; skip
others silently; fail if the resulting set is empty.

`DcimDevice.role` offers `super_spine, spine, leaf, border_leaf, l2leaf, l2spine, l3spine, p,
pe, rr, isp_edge, isp_core, internet_edge, customer_edge, branch_router, k8s_node`. Servers
attach to leaves, so the leaf family is the correct filter. The lab's peers are `leaf`.

Skipping is silent because a node legitimately has cabling that is not a fabric uplink —
out-of-band management being the obvious case — and raising on it would make the generator
fail on normal topologies. The safety net is FR-019: an empty peer set is an error, so
"silently skipped everything" cannot masquerade as success.

**Alternatives considered**:

- *Accept any far-end `DcimDevice`* — rejected: an out-of-band switch would become a BGP peer.
- *Filter on interface role `peering`* — rejected: the lab's leaf interface is `Ethernet10`
  with no peering-specific role, so this would find nothing.

---

## R7 — Validating idempotence without the mandated skill

**Decision**: Three layers, in increasing strength.

1. **Unit tests over fixtures.** Stages 1–3 of the pipeline are pure functions of the query
   response, so derivation, near-end exclusion, dedup, role filtering, adoption-versus-create,
   and every validation path are reachable without a server — including the ones a live server
   cannot produce, since the schema forbids a session with no ASN.
2. **A live double-run.** `infrahubctl generator` twice against the same branch, comparing the
   `ClusterFabricPeering` set and each object's attributes before and after.
3. **The artifact checksum.** Regenerate cycle 011's artifact after each run. Its checksum is a
   function of the rendered content, so an unchanged checksum proves the generator's output is
   unchanged *as the consumer sees it*.

Layer 3 is stronger than a generic idempotence check: it validates the observable output rather
than object counts, and cycle 011 already established both the baseline value and the procedure.

**Alternatives considered**: skipping repeated-run validation because the skill is unavailable —
rejected; the constitution permits a documented alternative, not an omission.

---

## R8 — File and definition naming

**Decision**: `generators/generate_fabric_peering.py`, `generate_fabric_peering.gql`,
`generate_fabric_peering_query.py`; class `FabricPeeringGenerator`; definition
`generate-fabric-peering`; query `generate_fabric_peering`.

AGENTS.md fixes the pattern (`generate_<entity>.py`, `.gql` co-located, `*_query.py`
regenerated not hand-written) and the existing definitions fix the style (`generate-fabric`,
`generate-pod`, `generate-rack`, `generate-server-cabling`).

The spec's draft name `generate_fabric_peering_service.py` is superseded: the `_service` suffix
would be the only one in the directory, and the entity being generated is the peering, not the
service. The service is the *target*, which the registration already states.

---

## R9 — Typed models and `convert_query_response`

**Decision**: `convert_query_response: false`, with a generated `*_query.py` consumed through
Pydantic models.

Every generator and transform in the repository does this, and Principle III requires it. Note
the SDK's default is already `False`; the repository states it explicitly in all eight existing
registrations, so this one does too.

Generating the model requires the branch's schema, which `main` does not have. Cycle 011
recorded the procedure: export the schema from the feature branch with
`INFRAHUB_DEFAULT_BRANCH=<branch> infrahubctl graphql export-schema`, then pass `--schema`.
Without it, `generate-return-types` fails with `Cannot query field 'ServiceFabricPeering'`.

---

## R10 — Determinism

**Decision**: Sort the peer set by device name before writing.

Sessions are written in a stable order and the artifact rendered from them sorts its peers by
name independently (cycle 011, FR-013 there). Sorting here as well means the object-creation
order does not vary between runs, which keeps the live double-run in R7 comparing like with
like and avoids spurious "changed" results from ordering alone.

---

## Risk register

| Risk | Mitigation |
| --- | --- |
| First run rewrites `name`/`peer_address` and moves the artifact | R3's two payload shapes; SC-004 checks the checksum immediately after the first run |
| The near end becomes a peer | R2 — exclude by interface id; a unit test asserts no `ComputePhysicalServer` is ever a `peer_device` |
| A partial traversal deletes real sessions | R4 — validate before writing; FR-018/FR-019 fail with nothing written |
| Adoption is irreversible | Stated in R4; the branch is disposable and `objects/34` retains the values until the file is edited |
| The generated query model is stale against `main` | R9 — export the schema from the feature branch first |
