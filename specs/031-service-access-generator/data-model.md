# Phase 1 Data Model: Application Access Grant Generator

No schema changes. Every kind below exists today; this document records what the generator **reads**, what it **writes**, and the keys that make a second run a no-op.

Kinds and field names come from `schemas/service/access_services.yml`, `schemas/security/security.yml` and `schemas/security_extensions.yml`.

---

## 1. Input — what a grant carries

`ServiceAppAccess` inherits `ServiceGeneric`, `GeneratorTarget` and `CoreArtifactTarget`.

| Field | Kind | Required | Used for |
| --- | --- | --- | --- |
| `name` | Text, unique | yes | The natural key every generated object's name derives from (research R3) |
| `status` | Dropdown | yes, default `provisioning` | Written back by the generator — see §5 |
| `approved` | Boolean | yes, default `false` | **The gate.** Nothing is created while false |
| `approved_by`, `approved_at` | Text, DateTime | no | Audit trail; read only, never written |
| `requester`, `justification` | Text, TextArea | yes / no | Carried into the generated rule's description |
| `ports` | List | no | One service object per entry. **Empty is rejected, never read as "all"** |
| `application` | → `ServiceFabricApp`, one | yes | Source of the destination zone, via its VRF |
| `source_zone` | → `SecurityZone`, one | yes | The rule's source zone, used directly |
| `source_address` | → `SecurityGenericAddress`, one | yes | The rule's source address, used directly — an existing book entry, never a synthesised CIDR |
| `destination_vip` | → `IpamIPAddress`, one | yes | Wrapped in an address-book entry (§3.1) |
| `granted_rules` | → `SecurityPolicyRule`, many | no | **Written** — the rules this grant caused |

`owner` is inherited from `ServiceGeneric` and is not used by the generator.

---

## 2. Derived inputs

Two facts the rule needs that the grant does not name.

### 2.1 Destination zone

```text
ServiceAppAccess.application → ServiceFabricApp.vrf → IpamVRF
                                                        ↑
                                              SecurityZone.vrf
```

The destination zone is the `SecurityZone` whose `vrf` is the application's `vrf`. Both relationships are `optional: true`, so three cases raise before anything is written:

- the application has no `vrf`
- no zone carries that VRF
- more than one zone carries it

See [research.md](./research.md) R2 for why this replaces the interface-containment derivation in FR-028.

### 2.2 Policy

```text
SecurityPolicy where device_target = the firewall
```

Exactly one exists: `nfd41-perimeter`, `device_target: fw1`. `SecurityPolicyRule.policy` is mandatory and cardinality one, so a missing or ambiguous policy raises.

---

## 3. Output — what the generator writes

Three kinds are created or adopted, in dependency order. Adoption rules are in [research.md](./research.md) R6: an object found by its natural key is used as-is and **not** marked as service-managed, because the generator did not create it.

### 3.1 `SecurityIPAMIPAddress` — the destination VIP's book entry

Bridges `destination_vip` (an `IpamIPAddress`) into the firewall's address-book vocabulary. `access-portal` is the hand-written example of exactly this shape.

| Field | Value |
| --- | --- |
| `name` | `svc-<grant>-vip` |
| `description` | The application's name and the grant's requester |
| `ip_address` | → the grant's `destination_vip` |
| `book_index` | 1000 + a deterministic per-grant offset |

**`book_index` is mandatory in practice.** `transforms/junos_config.py::_addresses` skips any entry whose index is null — it would be referenced by the rule and never declared, and the configuration would not load. Hand-written entries occupy 10–130, so a floor of 1000 leaves the pinned order in `tests/unit/test_junos_config.py` untouched.

**Adoption**: keyed on the `IpamIPAddress` the entry points at, not on the name. If an entry already wraps that address it is used and no second entry is created.

### 3.2 `SecurityService` — one per permitted port

| Field | Value |
| --- | --- |
| `name` | `svc-<grant>-tcp-<port>` |
| `port` | the port |
| `ip_protocol` | → `SecurityIPProtocol` `tcp` |

**Adoption is keyed on `(ip_protocol, port)`, not on name.** The firewall already declares `junos-http` (80) and `junos-https` (443); a grant for 443 must reference `junos-https` rather than create a duplicate, or the rendered configuration gains a second application declaration for the same port and stops reading like the rules beside it (FR-022).

Only TCP is generated. `ports` is a list of TCP ports; ICMP is not requestable through a grant.

### 3.3 `SecurityPolicyRule` — the rule itself

| Field | Value |
| --- | --- |
| `name` | `svc-<grant>` |
| `index` | 100 + a deterministic per-grant offset (research R1) |
| `action` | `permit` |
| `log` | `true` |
| `log_session_close` | `true` |
| `managed_by_service` | **`true`** |
| `policy` | → the derived policy (§2.2) |
| `source_zone` | → the grant's `source_zone` |
| `destination_zone` | → the derived zone (§2.1) |
| `source_address` | → the grant's `source_address` |
| `destination_address` | → the entry from §3.1 |
| `destination_services` | → the objects from §3.2 |

`log` and `log_session_close` are both true because a grant is an audited exception to the baseline; the baseline's own rules leave `log_session_close` false, which is the distinction `schemas/security_extensions.yml` records as behaviour rather than formatting.

An index floor of 100 puts every generated rule **after** the `deny-spoofed-infra` baseline at index 10, so a grant can never permit a spoofed `fabric-infra` source.

### 3.4 Backlink

Every created rule is added to the grant's `granted_rules`. This is the grant-side record of what it caused; the graph-side record is the SDK tracking group.

---

## 4. Natural keys and idempotence

`allow_upsert=True` upserts against each kind's `human_friendly_id`, which is `["name__value"]` on all three. Because every name derives deterministically from the grant's name — itself unique across all service kinds — a second run with unchanged input upserts the same three nodes and creates nothing.

| Kind | HFID | Derived from |
| --- | --- | --- |
| `SecurityIPAMIPAddress` | `name__value` | grant name |
| `SecurityService` | `name__value` | grant name + port |
| `SecurityPolicyRule` | `name__value` | grant name |

Withdrawal is **partly** the tracking context's and partly explicit — see [research.md](./research.md) R8, which corrects what this section originally claimed.

- **Narrowing** a grant (three ports to one) is the tracking context's: the run still writes a rule, so the dropped service objects fall out of a non-empty member set and are deleted.
- **Revoking** a grant is the generator's. `update_group` returns early when nothing was touched, so the unapproved path prunes nothing; `_withdraw` deletes the rule, the address entry and the service objects explicitly, keyed on the generated name.
- **Objects this generator created earlier must be rewritten every run**, or they drop out of the tracking group and are deleted while the rule referencing them survives.

A *foreign* object — `junos-https`, or a hand-written entry wrapping the same VIP — is referenced and never written, so it is a candidate for neither mechanism.

---

## 5. State transitions on `status`

The generator owns `status` on the grant. `ServiceGeneric` supplies the five choices; three are used here.

```text
                    approved: false
  provisioning ──────────────────────────► provisioning   (no-op, nothing created)
       │
       │ approved: true, generator succeeds
       ▼
     active
       │
       │ approved flipped to false, or ports/application changed and run fails
       ▼
     error ──── or ────► provisioning
```

| Outcome | `status` | Why |
| --- | --- | --- |
| Approved, objects created | `active` | Materialized and in service |
| Not approved | unchanged (`provisioning`) | The request is inert, not failed |
| Approved, generator raised | `error` | `schemas/service/service.yml` distinguishes this from `provisioning` deliberately: both leave no technical objects behind, and "tried to build and failed" is otherwise indistinguishable from "not built yet" |

`decommissioning` and `decommissioned` are operator-set and not written by this generator. A grant moved to either is treated as not approved for the purposes of the gate.

---

## 6. Validation rules

Checked **before** anything is written, because a partial write is the one path by which the tracking context deletes a real object — `generate_fabric_peering.py` calls this ordering load bearing and it applies identically here.

| # | Rule | On failure |
| --- | --- | --- |
| V1 | `approved` is true | Return without writing; leave `status` unchanged |
| V2 | `ports` is non-empty | Raise. An empty list is rejected, never read as "all ports" — matching the lab's `FirewallAccess` CRD, which sets `minItems: 1` |
| V3 | Every port is an integer in 1–65535 | Raise |
| V4 | The application resolves and has a `vrf` | Raise |
| V5 | Exactly one `SecurityZone` carries that VRF | Raise, naming how many matched |
| V6 | Exactly one `SecurityPolicy` targets the firewall | Raise |
| V7 | `source_zone`, `source_address` and `destination_vip` all resolve | Raise |
| V8 | The derived destination zone differs from `source_zone` | Raise — an intrazone grant is not something this firewall's model expresses |

V2 and V8 set `status` to `error` before raising; V4 to V7 are model-incompleteness failures and do the same.

---

## 7. What is not modelled

- **Reachability.** Whether the VIP sits inside a prefix the border leaf re-advertises to the source is a graph question the schema comment on `destination_vip` assigns to a check. This generator does not test it, so a grant can be permitted by the firewall and still unroutable. Recorded as an edge case in the spec and out of scope.
- **Kubernetes NetworkPolicy.** `ServiceFabricApp.policy_allow_ports` is declared intent on the application, not per-grant. Writing to it from here would put two writers on one attribute.
- **Zone-pair sequence.** Junos matches by zone rather than position, so the order of pair blocks is presentation and no object carries it — the same limitation `transforms/junos_config.py` already documents.
