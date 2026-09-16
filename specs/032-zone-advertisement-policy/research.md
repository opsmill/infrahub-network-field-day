# Phase 0 Research: Zone Advertisement Policy

Six questions. All resolved against the repository and the running instance; none needed a judgement call the spec had not already framed.

The decisive finding is R4: **both of the ways you would expect to derive the carrying device fail**, which is what turns this from a convenience relationship into a necessary one.

---

## R1 — Which kind the carrying-device relationship peers

**Decision**: `DcimFabricSwitch`.

**Rationale**. Three candidates, and two of them are wrong in ways that do not fail loudly.

| Candidate | Outcome |
| --- | --- |
| `DcimDevice` | **Matches nothing.** In this repository `DcimDevice` is the WAN's FRR routers. `AGENTS.md` states it outright: "A query naming `DcimDevice` does not see a fabric switch and reports nothing." The relationship would validate, load, and silently never resolve. |
| `DcimGenericDevice` | Matches, but too widely. It also admits `SecurityFirewall` and `ComputePhysicalServer`, neither of which carries `avd_custom_hostvars` — so a zone could point at a device where the eventual write has nowhere to go. |
| **`DcimFabricSwitch`** | Correct. Device-scope `avd_custom_hostvars` is declared on exactly this kind in `schemas/dcim_extensions.yml`, and a border leaf is one. |

The attribute the next cycle writes to and the kind this relationship peers must be the same kind, or the relationship points somewhere the write cannot land. FR-061 exists to hold that.

**Alternatives considered**: peering `DcimGenericDevice` and validating the kind in the generator. Rejected — the schema can express the constraint, so expressing it in code instead moves a static guarantee into a runtime one.

---

## R2 — What "the device carrying the policy" means

**Decision**: the device that **applies** the policy to a BGP neighbor, not the devices that merely render its definition.

**Rationale**. These are different sets, and the difference is invisible from the rendered configuration alone.

`custom_structured_configuration_prefix_lists` sits at the **top level** of `NetworkFabric.avd_custom_hostvars`, so it is fabric-wide: all seven switches render `PL-DC-ADVERTISED-BRANCH`. Only one references it:

```text
border-leaf1, VRF BRANCH:  neighbor 10.250.70.2 route-map RM-DC-TO-BRANCH out
border-leaf1, VRF WAN:     neighbor 10.250.50.2 route-map RM-DC-TO-EXTERNAL out
```

Every other switch renders a prefix list it never consults. So "which device carries this policy" has a seven-device answer that is useless and a one-device answer that is the one a generator needs — because a device-scope override only takes effect where the policy is applied.

A useful consequence: a device-scope entry on the border leaf makes its copy of the list differ from the other six. That is correct rather than untidy — the other six never use it.

**Alternatives considered**: recording every device that renders the definition (cardinality many). Rejected — it is derivable from fabric scope, it is the same seven devices for every zone, and it answers a question nobody asks.

---

## R3 — What the attribute is called

**Decision**: `dc_advertised_prefix_list`, not `advertised_prefix_list`.

**Rationale**. The shorter name is genuinely ambiguous *in this lab*, because both directions exist and are different objects:

| Direction | List | Meaning |
| --- | --- | --- |
| DC → zone | `PL-DC-ADVERTISED-BRANCH` | what we tell the branch |
| zone → DC | `PL-BRANCH-PERMITTED` | what we will accept from the branch |

Read cold, "the zone's advertised prefix list" is at least as likely to mean the second. The `dc_` prefix fixes the direction in the name rather than only in a description, and it matches the artifacts it points at — every one of them is literally `PL-DC-ADVERTISED*`, which makes the attribute greppable against the thing it names.

**Alternatives considered**: `advertisement_prefix_list` (still directionless), `outbound_prefix_list` (accurate but uses BGP vocabulary where the rest of the zone model uses plain language).

---

## R4 — Why the relationship cannot be replaced by a derivation

**Decision**: model it. Both plausible derivations fail against the live instance.

**Derivation 1 — by role.** Expected: "the device whose role is `border_leaf`". Verified against `main`:

```text
leaf-nfd41-pod1-1-1  role=leaf     leaf-nfd41-pod1-2-2  role=leaf
leaf-nfd41-pod1-1-2  role=leaf     leaf-nfd41-pod1-3-1  role=leaf
leaf-nfd41-pod1-2-1  role=leaf     spine-nfd41-pod1-1   role=spine
                                   spine-nfd41-pod1-2   role=spine
```

**No device has the `border_leaf` role.** The lab's `border-leaf1` is `leaf-nfd41-pod1-3-1`, identified by matching `mgmt_ip` `172.20.41.25` against the ContainerLab topology. Its role is plain `leaf`, like the other four. `border_leaf` exists in the `DcimFabricSwitch` dropdown and in `ROLE_TO_AVD_TYPE`, and nothing in this fabric uses it.

**Derivation 2 — through the zone's VRF.** Expected: `SecurityZone.vrf` → `IpamVRF` → the devices carrying it. `IpamVRF` relates to `IpamPrefix` and `IpamIPAddress` and to nothing in `Dcim`. **There is no VRF-to-device relationship in this schema.**

So the fact is not recoverable from the graph by any route. That is precisely the case a relationship exists for, and it removes the last argument for inferring the device instead of recording it.

---

## R5 — Which zones get values, and what they are

**Decision**: two of six.

| Zone | `dc_advertised_prefix_list` | `advertising_device` |
| --- | --- | --- |
| `branch` | `PL-DC-ADVERTISED-BRANCH` | `leaf-nfd41-pod1-3-1` |
| `wan` | `PL-DC-ADVERTISED` | `leaf-nfd41-pod1-3-1` |
| `k8s-prod`, `app-prod` | — | — |
| `acme-cloud`, `globex-cloud` | — | — |

**Rationale**. Only two BGP neighbors carry an outbound route-map, both on the border leaf. The four remaining zones are internal or tenant-facing: the tenant cloud prefixes `10.220.10.0/24` and `10.220.20.0/24` appear *inside* `PL-DC-ADVERTISED`, which is what the DC tells the **WAN** — they are the subject of an advertisement toward `wan`, not the destination of one. Recording them against `acme-cloud` would invert the relationship's meaning.

Four empty zones is the expected steady state, which is why FR-011 makes both fields optional and acceptance scenario US1-2 asserts that empty is valid rather than incomplete.

---

## R6 — Placement on the existing zone

**Decision**:

| Field | Kind | `order_weight` | Sits after |
| --- | --- | --- | --- |
| `advertising_device` | relationship, one, optional | 940 | `vrf` (930) |
| `dc_advertised_prefix_list` | `Text`, optional | 1300 | `trust_level` (1200) |

**Rationale**. `schemas/security_extensions.yml` already places `vrf` at 930 and `trust_level` at 1200 on this kind, and the repository's convention puts primary relationships in 900–999 and secondary attributes in 1100–1499. The two new fields are the fabric-side counterparts of `vrf`, so they sit immediately after their nearest existing sibling in each band. FR-042's requirement that nothing existing be displaced is met by construction — neither number is taken.

The extension goes in `schemas/security_extensions.yml` beside `trust_level`, `vrf`, `book_index` and `log_session_close`, whose header explains the pattern: add here rather than edit the adopted `schemas/security/security.yml`, so a later `marketplace get` diffs cleanly.

---

## What did not need research

- **Attribute kind.** `Text`. There is no object to reference (zero `RoutingPrefixList` objects exist), which the spec established; a `Text` attribute is the only honest representation of a name pointing into a JSON blob.
- **Cascade behaviour.** `on_delete` has one useful value, `cascade`, which deletes the *peer*. On `SecurityZone.advertising_device` that would mean deleting a switch deletes the zone. Omitted, per FR-023 and the same reasoning `schemas/deployment.yml` records for `DeploymentState.device`.
- **Protocol regeneration.** `src/solution_arista_avd/protocols.py` is generated from `schemas/`, so it is regenerated, not edited. Constitution principle I.
