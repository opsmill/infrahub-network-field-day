# Phase 0 Research: Application Access Grant Generator

Seven questions. Two were carried forward from the spec as open risks, one corrects a premise in the spec itself, and four were found while reading the firewall's seed data.

Everything here was resolved against the repository rather than from general Infrahub knowledge. The firewall's objects are in `objects/32_nfd41_security.yml`; the renderer's ordering rules are documented in the module docstring of `transforms/junos_config.py`.

---

## R1 — Where a generated rule sits in its zone pair

**Decision**: generated rules take `index` values from **100 upward**, allocated deterministically per grant. The hand-written baseline occupies only `10`, `20` and `30`.

**Rationale**. Junos evaluates policies first-match *within* a zone pair, so `index` is semantic — `transforms/junos_config.py` says so directly: "a reordered render is a different firewall that loads without complaint." The baseline is structured with an anti-spoofing deny first:

| Pair | 10 | 20 | 30 |
| --- | --- | --- | --- |
| `branch -> k8s-prod` | `deny-spoofed-infra` (**deny**) | `branch-to-access-portal` | `branch-to-k8s-icmp` |
| `app-prod -> k8s-prod` | `deny-spoofed-infra` (**deny**) | `app-to-k8s-services` | `app-to-k8s-icmp` |
| `wan -> k8s-prod` | `deny-spoofed-infra` (**deny**) | `wan-to-k8s-services` | — |

A generated permit placed at 100+ evaluates *after* every baseline rule. That is the safe direction: it can never shadow the anti-spoofing deny, so a grant cannot accidentally permit a spoofed `fabric-infra` source. Placing generated rules first would invert that and make every grant a potential hole in the baseline.

Across all nineteen rules the maximum index is 30, so a floor of 100 leaves 70 free for baseline growth before anything collides.

**Alternatives considered**:

- *Append after the highest existing index in the pair.* Rejected: not deterministic. Two grants generated in different orders would swap indices between runs, and the tracking context would churn.
- *Interleave by trust level.* Rejected: invents a policy the lab does not have, and trust level already lives on the zone.
- *Place generated rules first.* Rejected for the shadowing reason above.

---

## R2 — How the destination zone is derived

**Decision**: the destination zone is the `SecurityZone` whose `vrf` relationship points at the same `IpamVRF` as the grant's application. One hop from each side, no address arithmetic.

**This corrects FR-028 in the spec**, which said to derive the zone from "the firewall interface whose subnet contains the VIP". That premise is false. The handoff interfaces are `/30` point-to-points:

```text
ge-0/0/0  10.250.110.2/30  security_zone: k8s-prod    # border-leaf1 Et10
ge-0/0/1  10.250.210.2/30  security_zone: app-prod    # border-leaf1 Et11
ge-0/0/3  10.250.170.2/30  security_zone: branch      # private circuit
```

None of them contains a service VIP. The existing `access-portal` entry is `10.112.240.33/32`, inside the `k8s-services` prefix `10.112.0.0/16` — and no firewall interface is on that subnet, because the firewall reaches it *through* the `/30` handoff. Containment would match nothing and the generator would raise on every grant.

The VRF path works because both halves already exist and are already populated:

```text
ServiceFabricApp.vrf  -> IpamVRF   (cardinality one, optional)
SecurityZone.vrf      -> IpamVRF   (cardinality one, optional)
```

`SecurityZone.vrf` carries a comment saying exactly why it is there: "Every tenant VRF in this fabric has exactly one route out — a default pointing at its own zone — so the pairing between a VRF and a zone is the thing that makes the firewall unavoidable rather than decorative." That pairing is the derivation.

**Failure behaviour**: both relationships are `optional: true`, so the generator raises when the application has no VRF, when no zone carries that VRF, or when more than one does. FR-028's "fail loudly when ambiguous or empty" survives the change of mechanism.

**Alternatives considered**:

- *Interface containment.* Rejected — the premise is false, as above.
- *Containment in an address-book prefix* (`k8s-services` contains the VIP, and `k8s-services` is used as a destination in `k8s-prod` rules). Rejected: the prefix→zone link is inferred from rule usage rather than modelled, so it is a guess that happens to be right today.
- *A `zone` relationship added to `ServiceFabricApp`.* Rejected: that is a schema change, and SC-008 forbids one this cycle. It would also duplicate a fact the VRF pairing already carries.

---

## R3 — Deterministic names for generated objects

**Decision**: every generated object's name is derived from the grant's name, which is unique across all service kinds (`ServiceGeneric` has `unique: true` and a `["name__value"]` HFID).

| Object | Name |
| --- | --- |
| `SecurityIPAMIPAddress` | `svc-<grant>-vip` |
| `SecurityService` | `svc-<grant>-tcp-<port>` |
| `SecurityPolicyRule` | `svc-<grant>` |

**Rationale**. These kinds all use `human_friendly_id: ["name__value"]`, so the name *is* the natural key that `allow_upsert=True` upserts against. A deterministic name is therefore what makes the generator idempotent, per constitution principle II. The `svc-` prefix makes a generated object visible as generated at a glance in the UI, alongside `managed_by_service` which is what a query filters on.

Grant names are already constrained to be unique, so no collision is possible between grants. A collision with a hand-written object is possible in principle; the generator treats that as adoption (R6) and `managed_by_service` records which is which.

**Alternatives considered**: a UUID or a hash suffix. Rejected — it is not readable in the UI, and it is not needed given grant names are unique.

---

## R4 — `book_index` for the generated address-book entry

**Decision**: generated address-book entries take `book_index` from **1000 upward**, allocated deterministically per grant.

**Rationale**. Two facts from `transforms/junos_config.py::_addresses`:

1. Entries are rendered **in `book_index` order**, and that order is presentational — Junos writes the book in authoring order and nothing derives it, which is why `book_index` was added locally.
2. **An entry with no `book_index` is skipped entirely.** The docstring: "An entry without an index is a keyword Junos never declares, so it is referenced by rules and absent from the book." A generated entry that forgets its index would be referenced by a rule and never declared — the configuration would not load.

Hand-written entries occupy `10` through `130`. A floor of 1000 puts every generated entry after all of them, so the pinned order that `tests/unit/test_junos_config.py` asserts is untouched, and the generated entries appear as a block at the end of the book.

**Alternatives considered**: interleaving generated entries by address. Rejected — it would move hand-written entries relative to one another and break the byte-for-byte assertion for no benefit, since the order is presentational anyway.

---

## R5 — The seeded grant is unapproved, and why that is the point

**Decision**: `objects/38_nfd41_access_grants.yml` seeds exactly one grant, with `approved: false`.

**Rationale**. This resolves the risk the spec's checklist carried against FR-060 and FR-062, which pulled in opposite directions:

- FR-060 wants a seeded grant, because `ServiceAppAccess` has no object anywhere and an unexercised generator is an untested one.
- FR-062 wants the Junos artifact unchanged, because `tests/unit/test_junos_config.py` holds it byte-for-byte against the device's `junos.conf` and `test_the_exclusions_add_up` asserts the line totals.

An **approved** seed grant would generate a rule and an address entry into the default data set, changing the rendered artifact permanently and breaking both assertions — and the device file it is held against is the hand-written baseline, so there would be nothing correct to update them to.

An **unapproved** seed grant satisfies both. `approved: false` is the gate (FR-030), so it materializes nothing and the artifact is byte-identical. The kind stops being empty, the group has a member, and the demo is one field-flip away — which is exactly the shape of the real workflow, where approval is a patch on one field.

The creation path is exercised where it belongs: unit tests for the logic, and the quickstart's branch-scoped approve-render-push run for the end-to-end claim.

**The lab is already staged for this.** The `access-portal` address entry carries the description "The only DC service the branch may reach before requesting access", and `branch -> k8s-prod` permits branch users to reach it and nothing else. The seed grant is a branch user requesting access to an application behind that portal.

**Alternatives considered**:

- *Seed an approved grant and update the byte-for-byte tests.* Rejected — those tests hold the artifact against the real device file, and the device has no such rule. Updating them would make them assert something untrue about `fw1`.
- *Seed nothing and rely on fixtures.* Rejected — FR-060's point stands: the group would have no member and the generator would never run in a bootstrap.

---

## R6 — Adoption versus creation for addresses and services

**Decision**: the generator looks the object up by its natural key first. If one exists it is adopted and left unmodified except for the relationships this grant needs; if not, it is created.

**Rationale**. `generate_fabric_peering.py` already establishes this, and its header says why: "Adoption fetches and modifies; it does not upsert. An upsert mutation validates every mandatory field on the node, so a payload that omits them in order to preserve them is rejected outright. Fetching the existing session and setting one attribute leaves the others exactly as they were."

The same applies here for service objects in particular. The firewall already declares `junos-http` (port 80) and `junos-https` (port 443). A grant for port 443 must reference `junos-https` rather than create `svc-<grant>-tcp-443` beside it, or the rendered configuration gains a duplicate application declaration for the same port and reads nothing like the hand-written rules next to it — which FR-022 forbids.

Adopted objects are **not** marked `managed_by_service` and **not** deleted on revocation, because the generator did not create them. That is the same guard `SecurityPolicyRule.managed_by_service` provides for rules, applied consistently.

**R8a later split this decision in two.** "Adoption" as written here is correct only for a *foreign* object. An object this generator created on an earlier run has the same name and must be written again every run, or the tracking context deletes it.

**Consequence for R3's naming**: a generated service object is only named `svc-<grant>-tcp-<port>` when no existing service covers that protocol and port. The lookup is by `(ip_protocol, port)`, not by name.

**Alternatives considered**: always create. Rejected for the duplicate-declaration reason. Always adopt. Rejected — a port with no existing service object has nothing to adopt.

---

## R7 — Target group kind

**Decision**: `service_app_accesses` is a **`CoreStandardGroup`**, declared in `objects/00_groups.yml` beside `service_fabric_peerings` and `service_fabric_apps`.

**Rationale**. The `infrahub-managing-generators` skill says a generator targets a `CoreGeneratorGroup`. This repository does not: `objects/00_groups.yml` declares one `CoreStandardGroup` document containing every target group, including `service_fabric_peerings`, which `generate-fabric-peering` targets successfully today. Following the skill here would make this the only generator in the repository with a differently-kinded target group, for no behavioural gain.

Membership is declared explicitly on the grant object, matching `objects/35_nfd41_peering_service.yml` and `objects/36_nfd41_app_services.yml`, both of which list their group by name rather than deriving it.

**Alternatives considered**: a `CoreGeneratorGroup` as the skill describes. Rejected as above — consistency with the eight generators already registered wins over the generic guidance, and the spec's FR-052 already asks for a comment recording why.

---

## What did not need research

- **Which policy a rule joins.** There is exactly one `SecurityPolicy` — `nfd41-perimeter`, with `device_target: fw1`. The derivation is "the policy whose device target is the firewall", and it is unambiguous today.
- **Whether the transform needs changing.** `transforms/junos_config.gql` queries `SecurityGenericAddress` and `SecurityPolicy` unfiltered, so generated objects are picked up with no change. Verified by reading the query.
- **How withdrawal works.** `InfrahubGenerator.run()` wraps `generate()` in `start_tracking(identifier=..., delete_unused_nodes=True)`. Objects a previous run created and this run did not touch are deleted. This is already how `generate-fabric-peering` prunes, and it is why this cycle needed no schema for recording what a service built.

  **This turned out to be half right, and the other half was a bug.** See R8.

---

## R8 — What the tracking context does not do (found during implementation)

Two defects, both found by running the generator against a live branch and neither reachable by a unit test with a fake client. Recorded here because the plan, the data model and FR-040 all asserted the opposite.

**R8a — an object the generator already created must be written again, every run.**

The obvious adoption implementation returns an existing object's id without touching it. On the second run that leaves the address-book entry and the service objects out of the run's tracking group, and `delete_unused_nodes=True` deletes them — while the rule, which *is* rewritten, survives referencing both. Measured: run 2 removed `svc-<grant>-vip` and `svc-<grant>-tcp-8080` and left the rule pointing at them. That is an address referenced by a rule and declared nowhere, which is exactly what stops the configuration loading.

So "adoption" is two different things and they are handled oppositely. An object whose name matches what this grant generates is **ours** and is rewritten every run. Anything else — `junos-https`, a hand-written address entry wrapping the same VIP — is **foreign**, referenced and never written, so it never joins the tracking group and survives revocation. `Existing.is_ours` is the distinction.

**R8b — revoking a grant is not covered by tracking at all.**

`InfrahubGroupContext.update_group` opens with:

```python
members: list[str] = self.related_group_ids + self.related_node_ids
if not members:
    return
```

A run that touches nothing therefore prunes nothing. That is fine for *narrowing* a grant — the run still writes a rule, so dropped service objects fall out of a non-empty member set — and wrong for *revoking* one, where the unapproved path writes nothing at all. Measured: un-approving a grant left its rule, its address entry and its service object exactly where they were, on a firewall that would still be permitting the session.

`_withdraw` now deletes them explicitly, keyed on the deterministic generated name and nothing else, so a foreign object is never a candidate. Verified live: after revocation the branch holds 19 rules (all hand-written), `access-portal` and all four of the firewall's own service objects, and the grant's status is back to `provisioning`.
