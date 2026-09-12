# Phase 1 Data Model: Junos Configuration for the Perimeter Firewall

**Feature**: `023-junos-config-render` | **Date**: 2026-09-12

No new kinds and no schema change. Two new objects — a target group and the `any` service — plus
**33 corrections to the existing seed**, because implementation found that cycle 010 modelled the
firewall's structure faithfully and its values approximately (research.md R9).

## The seed repair

`objects/32_nfd41_security.yml` is corrected against `../lab/configs/fw/vsrx/junos.conf`, which
is the oracle. Every correction is a transcription; none is invented.

| What | Count | Detail |
| --- | --- | --- |
| Rule `application` links | 14 | 11 of them `any`; the rest `junos-http`, `junos-https`, `junos-ping` |
| Rule source address-**group** references | 3 | `k8s-all`, `acme-sites`, `globex-sites` |
| Rule destination address-**group** references | 3 | `k8s-reachable`, `acme-sites`, `globex-sites` |
| Interface descriptions | 6 | paraphrases → the file's strings |
| Interface MTUs | 6 | `1514` (schema default) → `9192` |
| New `SecurityService` | 1 | `any` |

**All four address groups are seeded today and referenced by no rule.** That is the single
largest cause of the gap, and it is why a render could emit `source-address app-hosts;` correctly
while emitting nothing at all for `destination-address acme-sites;`.

Nothing else in the seed changes: the 13 address-book entries already match the oracle by name
**and** value with no drift, and the rules' identity — names, zone pairs, `index`, `action`,
`log` — was verified correct in Phase 0.

## The render context

| Junos stanza | Source | Lines |
| --- | --- | --- |
| `interfaces { … }` | `SecurityFirewallInterface` ×6, with their `ip_addresses` | 76 |
| `security { address-book { global { … } } }` | `SecurityGenericAddress` ×13 + `SecurityAddressGroup` ×4 | ~45 |
| `security { zones { security-zone … } }` | `SecurityZone` ×6, each with its `interfaces` | ~75 |
| `security { policies { from-zone … } }` | `SecurityPolicy` → `rules` ×19, grouped by zone pair | ~340 |

Totalling the 573 in-scope lines. `security { flow }` (7 lines), `routing-options` (12) and
`system` (13) are excluded — see the spec's Out of Scope.

## Entities

### `SecurityFirewall` — the render target

`fw1`. Inherits `DcimGenericDevice`, `DcimPhysicalDevice`, **`CoreArtifactTarget`** and
`SecurityPolicyAssignment`, so it carries artifacts with no schema change (R7). Reachable from
its policy through `SecurityPolicy.device_target`, which resolves.

### `SecurityZone` ×6

`name`, `trust_level`, `interfaces` (many), `vrf` (one). The zones are `k8s-prod`, `app-prod`,
`wan`, `branch`, `acme-cloud`, `globex-cloud`.

### `SecurityFirewallInterface` ×6

`name` (`ge-0/0/0` … `ge-0/0/5`), `description`, `device`, `security_zone`, `ip_addresses`.
Supplies both the `interfaces` stanza and each zone's interface list.

### The address book — 13 rendered, 14 stored

`SecurityGenericAddress` is a generic with three concrete kinds in play:

| Kind | Count | Value read from |
| --- | --- | --- |
| `SecurityIPAMIPPrefix` | 12 | `ip_prefix → prefix` |
| `SecurityIPAMIPAddress` | 1 | `ip_address → address` |
| `SecurityPrefix` | 1 | `prefix` (a literal) |

All 13 rendered entries match the golden file by name **and** value, with no drift.

**The fourteenth is `any` (0.0.0.0/0), and it must not be rendered.** Junos treats `any` as a
keyword; the address book never declares it. It exists as an object only so a rule's
`destination_address` has something to point at (R8, FR-017).

Reading a value needs an inline fragment per concrete kind — the field name differs on each
(`ip_prefix`, `ip_address`, `prefix`) — and cycle 022 established the fragment must name the kind
the server returns, or the generated model silently yields a variant without the field.

### `SecurityAddressGroup` ×4

`acme-sites` (2 members), `globex-sites` (1), `k8s-all` (2), `k8s-reachable` (2). A member is
referenced by name; the address is defined once in the book above.

The single-member group is the bracket-form trap in miniature: Junos writes one member
differently from several.

### `SecurityPolicy` and `SecurityPolicyRule` ×19

One policy, `nfd41-perimeter`, holding 19 rules. Each rule carries:

- `name`, `index`, `action`, `log`
- `source_zone`, `destination_zone` — **cardinality one and mandatory**, which is what makes a
  rule belong to exactly one zone pair
- `source_address`, `destination_address` — many, → `SecurityGenericAddress`
- `source_services`, `destination_services` — many, → `SecurityGenericService`

**Zone pairs are derived, not stored.** Grouping by `(source_zone, destination_zone)` yields the
eleven pairs; sorting by `index` within a pair yields the evaluation order. Phase 0 confirmed
both match the golden file exactly.

**Six of the nineteen are `deny-spoofed-infra`** — six distinct objects, one per pair. The model
mirrors the file's repetition because the schema requires it; the render reproduces it and must
not let the six diverge (R2, SC-003).

### `SecurityGenericService` ×5

`SecurityService` ×3 and `SecurityIPProtocol` ×2, becoming a rule's `application` clause. Same
polymorphic fragment requirement as the address book, and the same bracket-form rule.

## The one new object

A `CoreStandardGroup` in `objects/00_groups.yml` with `fw1` as its only member. An artifact
definition cannot target a group that does not exist; cycles 017 and 022 set the precedent for
adding one inside a transform cycle.

## Invariants

- **Nothing is hardcoded but Junos syntax.** Every zone, address, group, service and rule comes
  from the graph.
- **No credential is read, stored or rendered.** The `system` stanza has no representation and
  must gain none (FR-015, SC-005).
- **Rule order within a pair is `index` order**, because Junos evaluates first-match.
- **`any` is referenced, never defined.**
- **Brace nesting is balanced** and the file ends with a newline.
- **One artifact, for one firewall.**
