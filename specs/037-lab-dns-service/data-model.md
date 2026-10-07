# Data Model: Lab DNS Service

## Changes to existing kinds

| Kind | Change | Why |
| --- | --- | --- |
| `ServiceFabricApp` | New optional attribute `dns_zone` (Text, hostname pattern). Set only on the resolver application. | Decision 3: the zone is stored on the resolver application. Optional, because making an attribute mandatory against existing data is refused. |
| `IpamIPAddress` | No change. The existing optional `fqdn` is filled. | Decision 3. |
| `SecurityIPProtocol` objects | New object `udp`, protocol 17. | DNS needs UDP ([research.md](./research.md#r-5)). |
| `SecurityService` objects | New `dns-udp` and `dns-tcp`, port 53. | The seeded rule names them. |
| Address book | New entry for the resolver's VIP. | The seeded rule's destination. |
| `SecurityPolicyRule` | New `branch-to-dns`, `branch` to `k8s-prod`, not managed by a service. | Access in the bootstrapped version. |

## Not added

- No new kind. [CLAUDE RECOMMENDED – based on decision 3] Planning found no case a new kind would handle that the attribute and `fqdn` cannot: withdrawal is "no live application, so no record", and the generator clears the address.

## Derived data

A DNS record is not stored as a node. It is the pair of an application's `name` plus the zone, and the application's VIP address with its `fqdn`.

| Field | Source |
| --- | --- |
| Name | `<ServiceFabricApp.name>.<resolver.dns_zone>` |
| Address | The address in the application's `vip_block` that holds the `fqdn`. Which address is [open](./research.md#r-3). |
| Live | Application `status` is not `decommissioning` or `decommissioned`, and `exposed` is true and `vip_block` is set. |

## Validation rules

- `dns_zone` is set on at most one application. A check should refuse two resolvers ([plan: tasks](./plan.md)).
- A name must be a valid DNS label. The portal pattern covers portal requests; the generator skips and reports any application whose name is not a valid label.
- The renderer refuses to produce a zone with no records.

## State transitions

```text
application created (provisioning, no block)  -> no record
generate-fabric-app allocates the block       -> generate-dns-record sets fqdn on the address
status -> decommissioning / decommissioned    -> generate-dns-record clears fqdn, removes the address it created
```
