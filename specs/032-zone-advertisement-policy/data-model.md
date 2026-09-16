# Phase 1 Data Model: Zone Advertisement Policy

Two fields on one existing kind. No new node, no new generic — and FR-003 makes that a tripwire rather than an observation: needing one means the design drifted toward migrating the fabric's BGP policy instead of referencing it.

---

## 1. What `SecurityZone` carries today

From `schemas/security/security.yml` (upstream) and `schemas/security_extensions.yml` (local additions):

| Field | Kind | Source | `order_weight` |
| --- | --- | --- | --- |
| `name` | Text, unique | upstream | — |
| `description` | Text, optional | upstream | — |
| `trust_level` | Number 0–100, optional | **local** | 1200 |
| `vrf` | → `IpamVRF`, one, optional | **local** | 930 |

`vrf` is the existing precedent and the closest sibling of what this cycle adds. Its description — *"The fabric VRF on the other side of this zone's handoff"* — is the same shape of fact: something about the fabric side of a zone that the firewall model alone cannot express.

The firewall side is modelled from the other direction too: `SecurityFirewallInterface.security_zone` binds an interface to a zone. Nothing binds a zone to the fabric.

---

## 2. What this cycle adds

### 2.1 `dc_advertised_prefix_list` — the policy's name

| Property | Value |
| --- | --- |
| `kind` | `Text` |
| `optional` | `true` |
| `order_weight` | 1300 |
| `label` | DC Advertised Prefix List |

The name of the prefix list governing what the datacentre advertises **toward** this zone.

**It is an attribute, not a relationship, and that is forced.** There are zero `RoutingPrefixList` objects in the graph — every prefix list in this fabric exists only as an entry in `custom_structured_configuration_prefix_lists` inside `NetworkFabric.avd_custom_hostvars`. A relationship needs a peer to point at and there is none.

**The `dc_` prefix is load bearing.** Both directions exist in this lab and they are different objects:

```text
PL-DC-ADVERTISED-BRANCH   what we tell the branch      <- this field
PL-BRANCH-PERMITTED       what we accept from it
```

`advertised_prefix_list` alone reads at least as naturally as the second. See [research.md](./research.md) R3.

**The description must say it is a soft reference** (FR-013). Nothing enforces the name resolves; an undocumented soft reference is how the next reader mistakes it for a validated one.

### 2.2 `advertising_device` — who applies it

| Property | Value |
| --- | --- |
| `peer` | `DcimFabricSwitch` |
| `kind` | `Attribute` |
| `cardinality` | `one` |
| `optional` | `true` |
| `on_delete` | omitted |
| `identifier` | `security_zone__advertising_device` |
| `order_weight` | 940 |

The fabric switch that applies that prefix list to a BGP neighbor.

**`DcimFabricSwitch`, and the two alternatives fail differently:**

| Peer | What happens |
| --- | --- |
| `DcimDevice` | **Silently matches nothing.** `DcimDevice` is the WAN's FRR routers here; `AGENTS.md` warns a query naming it "does not see a fabric switch and reports nothing". The schema loads, the relationship never resolves. |
| `DcimGenericDevice` | Resolves, but admits `SecurityFirewall` and `ComputePhysicalServer` — neither carries `avd_custom_hostvars`, so a zone could point where the next cycle's write has nowhere to land. |
| **`DcimFabricSwitch`** | Device-scope `avd_custom_hostvars` is declared on exactly this kind. |

**"Applies", not "renders".** `custom_structured_configuration_prefix_lists` sits at fabric scope, so all seven switches render `PL-DC-ADVERTISED-BRANCH`; only the border leaf references it on a neighbor. The seven-device answer is derivable and useless; the one-device answer is what a generator needs. Research R2.

**No `on_delete`.** Its only value is `cascade`, which deletes the *peer* — here, deleting a switch would delete a security zone. Same reasoning `schemas/deployment.yml` records for `DeploymentState.device`, and `infrahubctl schema check` accepts the line without complaint either way.

### 2.3 The inverse, on the switch

Declared by the same `identifier` so the two sides are one bidirectional link rather than two relationships:

| Property | Value |
| --- | --- |
| `name` | `advertised_zones` |
| `peer` | `SecurityZone` |
| `cardinality` | `many` |
| `optional` | `true` |
| `identifier` | `security_zone__advertising_device` |

So "what does this leaf advertise, and to whom" is answerable from the switch, not only from the zone (US2-2).

**Mismatched identifiers are the classic failure here** — they produce two independent relationships that each look right and never connect.

---

## 3. What is deliberately absent

| Not modelled | Why |
| --- | --- |
| A `RoutingPrefixList` object for each list | Zero exist; the policy lives in `avd_custom_hostvars`. Migrating it is a separate, much larger cycle. |
| The route-map (`RM-DC-TO-BRANCH`) | The prefix list is what a per-grant entry is added to. The route-map that matches it is stable and adds a hop without adding an answer. |
| The inbound counterpart (`PL-BRANCH-PERMITTED`) | Nothing needs it yet. Adding it later is additive and the `dc_` prefix leaves the name free. |
| Cardinality many on `advertising_device` | Each zone in this lab hands off to one border leaf. Widening later is additive; narrowing is not. |
| A check that the named list exists | User Story 3 requires the model *permit* one. Building it is a different artifact type and a different cycle. |

---

## 4. Validation rules

Enforced by the schema:

| # | Rule | Mechanism |
| --- | --- | --- |
| V1 | Both fields are optional | `optional: true`; six zones already exist without them (FR-050) |
| V2 | `advertising_device` resolves to a fabric switch or nothing | `peer: DcimFabricSwitch` |
| V3 | Deleting a switch never deletes a zone | `on_delete` omitted |
| V4 | The two sides are one link | matching `identifier` |

**Not** enforced, and named so it is not mistaken for enforced:

| # | Gap | Consequence |
| --- | --- | --- |
| G1 | The named prefix list may not exist on any device | A generator writes an entry into a list nothing matches; the route never appears and nothing errors |
| G2 | The named list may exist on a device other than `advertising_device` | Same outcome, harder to see |
| G3 | One field may be set without the other | A zone that is half-modelled loads cleanly |

G1–G3 are why User Story 3 exists. FR-030 requires both values be queryable together so a later check can compare them against the device's merged AVD inputs in one pass.

---

## 5. Seed data

Two of six zones get values. Full evidence in [contracts/seed-values.md](./contracts/seed-values.md).

| Zone | `dc_advertised_prefix_list` | `advertising_device` |
| --- | --- | --- |
| `branch` | `PL-DC-ADVERTISED-BRANCH` | `leaf-nfd41-pod1-3-1` |
| `wan` | `PL-DC-ADVERTISED` | `leaf-nfd41-pod1-3-1` |
| `k8s-prod`, `app-prod`, `acme-cloud`, `globex-cloud` | — | — |

`leaf-nfd41-pod1-3-1` is the lab's `border-leaf1`, matched by `mgmt_ip` `172.20.41.25`. Infrahub and ContainerLab name the same box differently and there is no renaming layer, so the mapping is by address.

**Four empty zones is the steady state, not incomplete work.** The tenant-cloud prefixes appear *inside* `PL-DC-ADVERTISED` — they are the subject of an advertisement toward `wan`, not the destination of one. Recording them against `acme-cloud` would invert the field's meaning.
