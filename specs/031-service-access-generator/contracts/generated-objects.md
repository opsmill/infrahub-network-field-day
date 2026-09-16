# Contract: objects the generator creates

What `AppAccessGenerator.generate()` writes, in the order it writes it, and the key each is upserted against. Field values are in [data-model.md](../data-model.md) §3; this file is the ordering and adoption contract.

## Ordering

Dependency order, because a rule cannot reference objects that do not exist yet:

```text
1. validate everything          (V1–V8, before any write)
2. SecurityIPAMIPAddress        the destination VIP's book entry
3. SecurityService × N          one per permitted port
4. SecurityPolicyRule           references 2 and 3
5. grant.granted_rules += rule  the backlink
6. grant.status = active        last, so it is only set once the rest succeeded
```

**Validation precedes every write.** A partial write is the one path by which the tracking context deletes a real object, which `generate_fabric_peering.py` calls load bearing. Step 6 is last for the same reason: `active` must not be claimable by a run that failed halfway.

## Adoption

| Object | Adoption key | Not the name |
| --- | --- | --- |
| `SecurityIPAMIPAddress` | the `IpamIPAddress` it wraps | An entry may already wrap this VIP under a hand-written name — `access-portal` is exactly that |
| `SecurityService` | `(ip_protocol, port)` | The firewall declares `junos-http` (80) and `junos-https` (443); a grant for 443 must reference `junos-https` |
| `SecurityPolicyRule` | name, `svc-<grant>` | A rule is always this grant's; there is nothing to adopt |

**An adopted object is left alone.** It is not renamed, not given a new `book_index`, and **not** marked `managed_by_service`. Adoption fetches and modifies rather than upserting — an upsert validates every mandatory field, so a payload omitting them to preserve them is rejected outright (`generate_fabric_peering.py` header).

The consequence that matters: because the generator did not create an adopted object, the tracking context never deletes it. Revoking a grant that used `junos-https` leaves `junos-https` in place for the baseline rules that also use it.

## Deterministic allocation

Both floors sit above everything hand-written, so generated objects never displace what the byte-for-byte tests pin.

| | Floor | Hand-written range | Why the floor |
| --- | --- | --- | --- |
| `SecurityPolicyRule.index` | 100 | 10, 20, 30 | Generated permits evaluate **after** `deny-spoofed-infra`, so a grant can never permit a spoofed `fabric-infra` source |
| `SecurityIPAMIPAddress.book_index` | 1000 | 10–130 | Generated entries render as a block at the end of the address book, leaving the pinned order untouched |

The per-grant offset must be a pure function of the grant's name. Two runs must produce the same numbers, or the tracking context churns.

**`book_index` is not optional in practice.** `transforms/junos_config.py::_addresses` skips entries whose index is null — the entry would be referenced by the rule and never declared, and the configuration would not load.

## Marking

| Field | Set on | Value |
| --- | --- | --- |
| `managed_by_service` | every rule the generator **creates** | `true` |
| `managed_by_service` | anything the generator **adopts** | untouched, stays `false` |
| `log`, `log_session_close` | every rule the generator creates | `true` — a grant is an audited exception to the baseline |

Nothing else in the graph has `managed_by_service` set by this generator. All nineteen hand-written rules keep `false`, which is the guard that lets a reconciling generator run against a hand-maintained firewall.

## Downstream: nothing changes

`transforms/junos_config.gql` queries `SecurityGenericAddress` and `SecurityPolicy` unfiltered, so generated objects are rendered by the existing artifact with no transform change. The deployment reconciler pushes that artifact onto `fw1` unchanged.

This is the whole reason the cycle is one generator: every stage after it already exists and is under test.

## Failure contract

| Condition | Behaviour |
| --- | --- |
| Not approved (V1) | Return having written nothing. `status` unchanged — the request is inert, not failed |
| Empty `ports` (V2) | Set `status = error`, raise. **Never** read as "all ports" |
| Model incomplete (V4–V7) | Set `status = error`, raise, naming what was missing or how many matched |
| Intrazone (V8) | Set `status = error`, raise |

Every raise happens before any object is written.
