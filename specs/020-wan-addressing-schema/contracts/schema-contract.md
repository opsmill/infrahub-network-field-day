# Contract: Schema Surface

**Feature**: `specs/020-wan-addressing-schema` | **Date**: 2026-09-11

The schema is this cycle's only interface. What follows is the exact surface downstream cycles
may rely on, expressed as the YAML that must land and the traversals that must then be
possible. It is enforced by `tests/unit/test_wan_schema_contract.py`, which already exists and
is extended here rather than replaced.

## 1. `schemas/circuit_extensions.yml` — new file

```yaml
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
---
version: "1.0"

extensions:
  nodes:
    - kind: DcimCircuitEndpoint
      relationships:
        - name: interface
          label: Terminating Interface
          peer: DcimInterface
          kind: Attribute
          cardinality: one
          optional: true
          identifier: "circuit_endpoint__interface"
          order_weight: 960
```

`schemas/circuit/circuit.yml` MUST NOT appear in this cycle's diff.

## 2. `schemas/wan/wan.yml` — `WanSite`

The existing `bgp_session` entry is replaced by two entries, in this order:

```yaml
      # Tombstoned by cycle 020. A schema load is an upsert, so deleting this
      # entry would leave the old cardinality-one relationship live on the
      # server while `schema check` reported nothing. Remove it once the
      # instance has been rebuilt from empty.
      - name: bgp_session
        peer: RoutingBGPNeighbor
        kind: Attribute
        cardinality: one
        optional: true
        identifier: wan_site__bgp_session
        state: absent
      - name: bgp_sessions
        peer: RoutingBGPNeighbor
        label: BGP Sessions
        kind: Attribute
        cardinality: many
        optional: true
        description: "Both ends of the attachment session; present when attachment_kind is bgp"
        identifier: wan_site__bgp_sessions
        order_weight: 940
```

## 3. `schemas/wan/wan.yml` — `WanInternetPeering`

Appended after `internet_prefixes`:

```yaml
      - name: bgp_sessions
        peer: RoutingBGPNeighbor
        label: BGP Sessions
        kind: Attribute
        cardinality: many
        optional: true
        description: "Both ends of the transit session"
        identifier: internet_peering__bgp_sessions
        order_weight: 950
```

## 4. `schemas/dcim_extensions.yml` — `DcimDevice`

Inserted among the existing address relationships, before `rack`:

```yaml
        - name: router_id
          label: Router ID
          peer: IpamIPAddress
          kind: Attribute
          cardinality: one
          optional: true
          identifier: "device__router_id"
```

## 5. Traversals this guarantees

The next cycle seeds objects against these paths, and the cycle after that queries them. Both
may rely on all four:

| From | Path | Yields |
| --- | --- | --- |
| `DcimCircuit` | `endpoints → interface → ip_addresses` | the addresses on both ends of a circuit |
| `WanSite` | `bgp_sessions → {device, peer_address, remote_as}` | both ends of an attachment session |
| `WanInternetPeering` | `bgp_sessions → {device, peer_address, remote_as}` | both ends of the transit session |
| `DcimDevice` | `router_id → address` | the router ID, without inferring it |

**The interface traversal needs an inline fragment.** Because the peer is the `DcimInterface`
generic (R5), `ip_addresses` is not selectable directly on it — it lives on `InterfaceLayer3`.
Verified against the live schema: the plain form is rejected with *"Cannot query field
'ip_addresses' on type 'DcimInterface'"*, and this form is accepted:

```graphql
interface {
  node {
    __typename
    name { value }
    ... on InterfaceLayer3 {
      ip_addresses { edges { node { address { value } } } }
    }
  }
}
```

This is the price of peering with the generic, and it is the right price — a concrete peer
would remove the fragment and reintroduce the sub-interface failure. The next cycle's query
must use the fragment form, which echoes cycle 016's finding that `__typename` is needed at
every union point.

## 6. The `schema check` diff

With all four changes applied and nothing else, `uv run infrahubctl schema check schemas/` MUST
report every file `is Valid!` and a diff of exactly:

```text
changed:
    DcimCircuitEndpoint:  relationships added: {interface}
    DcimDevice:           relationships added: {router_id}
    WanInternetPeering:   relationships added: {bgp_sessions}
    WanSite:              relationships added: {bgp_sessions}
                          relationships removed: {bgp_session}
```

Any other entry means something was changed that this cycle did not intend. The `removed` line
is the one that proves the tombstone worked; its absence is the silent failure mode R6
documents.

## 7. Test contract

`tests/unit/test_wan_schema_contract.py::test_site_reuses_existing_routing_kinds_for_both_handoffs`
currently asserts `relationships["bgp_session"]["peer"]`. It MUST be re-pointed at
`bgp_sessions` and MUST additionally assert `cardinality == "many"`, so the widening is pinned
rather than merely permitted. New assertions cover the other three relationships and the
tombstone's continued presence.

The test MUST NOT be loosened — a version that stops asserting a peer kind in order to pass
both names would remove the guard this cycle relies on.
