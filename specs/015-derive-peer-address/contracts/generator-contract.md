# Contract: Generator Interface (revised)

**Feature**: `specs/015-derive-peer-address` | **Date**: 2026-09-11

This revises cycle 012's generator contract. Registration is unchanged — same query name, same
class, same target group. Only the derivation and the payloads change.

## 1. Registration

Unchanged from cycle 012: `generate-fabric-peering`, query `generate_fabric_peering`, targets
`service_fabric_peerings`, class `FabricPeeringGenerator`, `convert_query_response: false`.

## 2. Query contract

Extended: the peer device's virtual interfaces, their `role`, and their `ip_addresses`.
Everything cycle 012's contract required is still required.

## 3. Guarantees

Cycle 012's G-1 … G-7 all still hold. Three are added, one is withdrawn:

| Guarantee | |
| --- | --- |
| G-8 | `peer_address` always resolves to the address on the peer device's `peering`-role SVI |
| G-9 | A session is created for a cabled peer that has none, provided its address is derivable |
| G-10 | A disagreement between a recorded and a derived address is reported before being corrected |
| ~~G-4~~ | ~~On adoption, `name`, `enabled` and `peer_address` are unchanged~~ → **`name` and `enabled` only**. `peer_address` is now derived |

## 4. Idempotence contract

Unchanged in wording and stronger in coverage: two runs against an unchanged model leave the
object set, every attribute, and the artifact checksum unchanged. The baseline remains
`0d800c9d5005b5fdb6b371bb5627d143`.

## 5. Failure contract

Validation still completes before the first write, for the same reason: a partial write is the
only path by which this generator can delete a real session. V-6′, V-8 and V-9 join the set.

## 6. What this contract still does not cover

- `name`, which remains a lab-facing label and is not derivable.
- The fabric side of the session; `RoutingBGPNeighbor` has no objects.
- The other five service kinds.
