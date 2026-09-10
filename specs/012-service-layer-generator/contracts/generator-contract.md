# Contract: Generator Interface

**Feature**: `specs/012-service-layer-generator` | **Date**: 2026-09-10

A generator's external interface is what Infrahub invokes it with, what it writes, and what
it guarantees about repeated execution. Everything downstream — cycle 011's artifact, any
future check, an operator's mental model — is written against this surface. A change to
anything here is a breaking change to a consumer.

---

## 1. Registration

Added to `.infrahub.yml`. Field values are fixed by this contract; the shapes match the eight
existing entries.

```yaml
queries:
  - name: generate_fabric_peering
    file_path: "./generators/generate_fabric_peering.gql"

generator_definitions:
  - name: generate-fabric-peering
    file_path: "./generators/generate_fabric_peering.py"
    query: generate_fabric_peering
    targets: service_fabric_peerings
    parameters:
      name: name__value
    class_name: FabricPeeringGenerator
    convert_query_response: false
```

| Field | Value | Why |
| --- | --- | --- |
| `query` | `generate_fabric_peering` | MUST equal the `queries` entry name. A mismatch here is the one error only a repository sync catches |
| `targets` | `service_fabric_peerings` | The existing `CoreStandardGroup`, shared with cycle 011's artifact definition (R1, FR-025) |
| `parameters` | `name: name__value` | Maps the target's name to the query's `$name` |
| `convert_query_response` | `false` | Typed models are consumed explicitly (Principle III, R9) |

`execute_in_proposed_change` and `execute_after_merge` are left at their SDK defaults
(`True`). Note the consequence: `execute_after_merge=True` is what makes the SDK's tracking
group a `CoreGeneratorGroup` rather than a `CoreGeneratorAwareGroup` (R1).

---

## 2. Query contract

**Operation**: `GenerateFabricPeeringQuery($name: String!)` — the operation name determines the generated root model's class name, so it ends in `Query` to match the repository's convention

**Target aliasing**: the service is aliased `target:` in the query, matching the repository's
convention for the object a definition is parameterised on.

The query MUST return, in one round trip: the service; its cluster with `local_asn`; the
cluster's existing `fabric_peerings` with `name`, `peer_asn`, `enabled`, `peer_device` and
`peer_address`; and the cluster's `nodes` with their interfaces, each interface's connector,
and each connector's `connected_endpoints` with the far interface's `device`, `role` and
`asn`.

Omitting the existing sessions breaks adoption (R3) and is therefore a contract violation,
not an optimisation.

---

## 3. Written objects

Exactly one kind: `ClusterFabricPeering`. Payloads per [data-model.md](../data-model.md) §3.

| Guarantee | Enforced by |
| --- | --- |
| G-1 | One session per distinct fabric device; never one per node |
| G-2 | `peer_device` is never a `ComputePhysicalServer` — the near end is excluded by interface id |
| G-3 | `peer_asn` always equals the peer device's `RoutingAsn` |
| G-4 | On adoption, `name`, `enabled` and `peer_address` are byte-for-byte unchanged |
| G-5 | Writes happen only after every validation passes — a failing run writes nothing |
| G-6 | Objects outside the tracking group are never deleted |
| G-7 | Sessions are written in a deterministic order (by device name) |

---

## 4. Idempotence contract

The property the constitution's Principle II demands, stated so it can be tested:

> Running the generator twice against an unchanged model MUST leave the `ClusterFabricPeering`
> set, every attribute on each of them, and the checksum of the artifact rendered from them
> unchanged.

The third clause is the operative one. Object counts can match while values churn; the
artifact checksum is a function of the rendered content, so it cannot.

**Baseline**: cycle 011 recorded checksum `0d800c9d5005b5fdb6b371bb5627d143` for the artifact
rendered from the current hand-written sessions. After this generator adopts them, that value
MUST be unchanged. If it moves, the refactor altered what reaches the cluster (SC-004).

---

## 5. Failure contract

The generator raises rather than writing a partial set. Each message names the object and the
field, per [data-model.md](../data-model.md) §5 (V-1 … V-7).

A partial write is the only path by which this generator can delete a real session: the
tracking group's set difference removes previously managed sessions that this run did not
write. Failing before the first write is therefore not defensive tidiness — it is the
mechanism that makes G-5 and G-6 hold together.

---

## 6. What this contract does not cover

- The fabric side of the session. `RoutingBGPNeighbor` on the leaf is what AVD renders; this
  generator writes the cluster side only.
- `peer_address` derivation. Preserved on adopt, required-and-recorded on create, and
  underivable until the leaves' peering SVIs are modelled.
- The other five service kinds, none of which have loaded data or a downstream artifact.
- Delivery. The artifact reaches the cluster through the Vidra operator, unchanged by this
  cycle.
