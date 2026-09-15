# Phase 1 data model: deployment state

**Feature**: `specs/029-deployment-executor` | **Date**: 2026-09-15
**Validated against**: Infrahub 1.10.6 via `infrahubctl schema check` **and against a loaded
schema on a live branch** — every claim below was exercised, not just parsed. Amended after
implementation; see research R3 for the measurement that moved identity off the device
relationship.

Two nodes in a new `Deployment` namespace, in one new file `schemas/deployment.yml`. The
shape is deliberately the same as `AvdArtifact` / `AvdHostvarFile` in
`schemas/objects/objects.yml`: a small parent node carrying the facts you scan, and a
`CoreFileObject` child carrying the payload you open.

```text
DcimGenericDevice ──(one-sided, no identifier)── DeploymentState ──Component──> DeploymentDiffFile
   (branch-aware)                                 (agnostic)                      (agnostic)
```

---

## DeploymentState

One record per device: that device's standing against its rendered intent.

**Node properties**

| Property | Value | Why |
| --- | --- | --- |
| `namespace` / `name` | `Deployment` / `State` → kind `DeploymentState` | New namespace; the kind spans all four device families, so neither `Avd` nor `Dcim` fits |
| `branch` | `agnostic` | FR-007. One fact shared by every branch; never shows in a proposed change, never overwritten by a merge |
| `generate_profile` | `false` | FR-006. A profile supplies defaults for *intent*; this node holds *observation* |
| `include_in_menu` | `true` | FR-043, handed to the menu cycle (research R5) |
| `human_friendly_id` | `[name__value]` | FR-040. Identity is the device's name, carried on the record |
| `display_label` | `name__value` | FR-041 |
| `uniqueness_constraints` | `[[name__value]]` | FR-050. **Not** `[[device]]` — see below |

**Attributes**

| Name | Kind | Optional | Default | Weight | Meaning |
| --- | --- | --- | --- | --- | --- |
| `name` | Text (`unique`) | no | — | 950 | The device's name, copied. The record's identity |
| `status` | Dropdown | no | `never_deployed` | 1000 | The device's standing against intent |
| `last_confirmed_at` | DateTime | yes | — | 1100 | Last time the device was **confirmed to match**. The load-bearing field — decision log item 12 |
| `last_checked_at` | DateTime | yes | — | 1150 | Last time a comparison ran at all, match or not |
| `last_attempt_at` | DateTime | yes | — | 1200 | Last time a push was attempted |
| `last_error` | TextArea | yes | — | 1300 | Failure detail. `TextArea`, not `Text` — device errors are multi-line (FR-015) |
| `suspend` | Boolean | no | `false` | 1500 | Per-device break-glass. The reconciler skips the device entirely |
| `suspend_reason` | Text | yes | — | 1550 | Why, and by whom |

`status` and `suspend` are mandatory **with defaults** (FR-013), so a record created carrying
only its `name` and device is already legible. Attributes are mandatory by default in
Infrahub, which is the opposite of relationships — a default is what makes "mandatory" safe
here.

**`status` choices** (FR-012)

| Name | Meaning | How it differs from its neighbour |
| --- | --- | --- |
| `never_deployed` | No confirmation has ever been recorded | Not the same as `in_sync`; the cold-start hazard from decision log item 8 depends on telling these apart |
| `in_sync` | Confirmed to match at `last_confirmed_at` | — |
| `pending` | Intent moved; not yet pushed or confirmed | — |
| `drifted` | Intent did **not** move; the device did | The structurally different reason to push, from item 15 |
| `failed` | The last push or comparison failed | `last_error` carries the detail |

`suspend` is **not** a status choice (FR-014). Status is an observation about the device;
suspension is an operator's instruction. Collapsing them loses what the device was doing at
the moment someone suspended it, which is the one thing you want to know afterwards.

**Relationships**

| Name | Peer | Kind | Card. | Optional | Identifier | Weight |
| --- | --- | --- | --- | --- | --- | --- |
| `device` | `DcimGenericDevice` | Attribute | one | **yes** | **none** | 900 |
| `last_diff` | `DeploymentDiffFile` | Component | one | yes | `deploymentstate__last_diff` | 950 |

Two things about `device` that are easy to get wrong and silent when you do:

- **The peer is the generic.** The four device kinds are siblings; `DcimDevice` would be
  invisible to every fabric switch, and this feature deploys all four families (FR-020).
- **It declares no `identifier`, and that is deliberate** (FR-021, research R4). No reverse
  side is added to `DcimGenericDevice`, so no deployment relationship lands on the device
  kinds. `test_every_identifier_is_two_sided_and_agrees` scans every identifier in `schemas/`
  and would fail a one-way relationship that declared one — declaring none is how
  `AvdArtifact.device` handles the same situation, and the schema file carries the same
  comment saying so.

- **It is optional, which is not an oversight.** A record about no device is meaningless, so
  mandatory is the natural choice — and it is unusable. Infrahub requires any relationship
  used in `human_friendly_id` or `uniqueness_constraints` to be mandatory, and a mandatory
  `device` makes any device that has ever held a record **permanently undeletable**: the
  delete is refused even after the record is gone, naming a record that no longer exists.
  Measured twice on throwaway devices (research R3). Since the reconciler attaches a record to
  every device, mandatory would freeze the whole fabric.

**`on_delete` appears nowhere on this node, on purpose.** On `device` the only available
spelling, `cascade`, means *deleting a deployment record deletes the switch* — and
`infrahubctl schema check` accepts it without complaint. See research R3.

**The identity chain, in one line.** `device` must be optional so devices stay deletable →
identity cannot traverse `device` → the record carries `name` → uniqueness is on
`name__value`. Break any link and the other three stop making sense; that is why
`test_device_relationship_is_optional_and_identity_does_not_depend_on_it` asserts the pair
together.

---

## DeploymentDiffFile

The device-computed difference between the device and its intent, from the most recent
comparison that found one. The evidence behind a `drifted` status.

**Node properties**

| Property | Value | Why |
| --- | --- | --- |
| `namespace` / `name` | `Deployment` / `DiffFile` → kind `DeploymentDiffFile` | — |
| `inherit_from` | `[CoreFileObject]` | FR-003, FR-017. Content is a file, so a first-configuration diff the size of a whole device config stores intact |
| `branch` | `agnostic` | Matches its parent |
| `generate_profile` | `false` | FR-006 |
| `include_in_menu` | `false` | FR-044. Read through its parent, as `AvdHostvarFile` is |
| `human_friendly_id` | `[state__name__value]` | One hop to an attribute. The two-hop `state__device__name__value` is rejected outright (research R2) |
| `uniqueness_constraints` | `[[state]]` | FR-051 |

**Relationships**

| Name | Peer | Kind | Card. | Optional | Identifier |
| --- | --- | --- | --- | --- | --- |
| `state` | `DeploymentState` | Parent | one | no | `deploymentstate__last_diff` |

Component on the parent, Parent on the child, `many`/`one`… except this pair is `one`/`one`,
because a record holds at most one current diff. The identifier matches on both sides, so the
repository's two-sided contract test sees this pair and passes it.

---

## State transitions

Written by the reconciler in a later cycle; recorded here because the choice of attributes has
to support them.

```text
                    ┌──────────────────┐
                    │  never_deployed  │  (record created, device never reached)
                    └────────┬─────────┘
                             │ first comparison
             ┌───────────────┼────────────────┐
             v               v                v
        ┌─────────┐    ┌──────────┐     ┌────────┐
        │ in_sync │<──>│ drifted  │────>│ failed │
        └─────────┘    └──────────┘     └────────┘
             ^               ^                │
             │               │                │
             └──── push confirmed ────────────┘
                             ^
                       ┌──────────┐
                       │ pending  │  (intent moved, not yet confirmed)
                       └──────────┘
```

- `in_sync` is written **only** when the device's own comparator reports no difference.
  `last_confirmed_at` moves at the same moment and at no other. That is the "confirmed, not
  sent" semantic from decision log item 12, and it is why the field is named for confirmation
  rather than for the push.
- `last_checked_at` moves on **every** comparison, including the ones that find a difference
  and the ones that fail. It is what separates "this device is fine" from "the reconciler
  stopped running a week ago" — two states that look identical if you only have
  `last_confirmed_at`.
- `suspend` is orthogonal to all of it. A suspended device keeps whatever status it had; the
  reconciler does not visit it, so nothing moves. That is the point: you can see what it was
  doing when someone took it out of the loop.

---

## Validation rules

| Rule | Source | Enforced by |
| --- | --- | --- |
| One record per device | FR-050 | `uniqueness_constraints: [[name__value]]`. **Partly the reconciler's job**: the graph enforces one record per *name*, and it is the reconciler keeping `name` equal to the device's name that makes that one per device |
| One diff per record | FR-051 | `uniqueness_constraints: [[state]]` |
| A record must name a device | FR-020 | `optional: false` on `device` |
| A diff cannot outlive its record | FR-022 | Parent side `optional: false`; deleting the record removes the diff |
| A record cannot be created blank | FR-013 | `status` and `suspend` mandatory with defaults |
| No deployment kind is a generator input, artifact target, or trigger source | FR-060 | New test, FR-061 |

---

## What this model deliberately does not hold

- **Executor configuration** — poll interval, the 60-second floor, the every-fourth-cycle
  firewall multiple. Service configuration, not device state.
- **Per-artifact state.** A device either matches or it does not; artifact-level state is what
  decision log item 7 rejected for stranding partial failures.
- **History.** Each record is current state. An audit trail is Infrahub's own versioning of
  these nodes, which is also why the executor's write cadence is a decision with a cost — see
  the spec's assumption on write volume.
- **An independent identity.** `DeploymentState` does carry a `name`, but it is the device's
  name copied, not a key of its own. It exists because identity cannot traverse an optional
  relationship, not because the record wants a name. The reconciler owns it and refreshes it
  each cycle, which is what answers the drift objection.
