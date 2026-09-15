# Phase 0 research: deployment state schema

**Feature**: `specs/029-deployment-executor` | **Date**: 2026-09-15

Every finding below was produced by running `infrahubctl schema check` against a candidate
`deployment.yml` placed in a copy of `schemas/`, on the live instance (Infrahub 1.10.6, SDK
1.22.0), or by reading the version-matched reference. Nothing here is inferred from general
Infrahub knowledge, because the two questions the spec left open are exactly the kind that
general knowledge gets confidently wrong.

---

## R1. Can a branch-agnostic node hold a mandatory relationship to a branch-aware one?

**Decision**: Yes. Both nodes take `branch: agnostic` as FR-007 requires, and the
relationship to `DcimGenericDevice` (branch-aware) validates.

**Rationale**: this was the assumption the spec said to escalate rather than silently
downgrade. It does not need escalating — the candidate schema, with `branch: agnostic` on
both `DeploymentState` and `DeploymentDiffFile` and `optional: false` on the device
relationship, returns `Valid` and produces a clean two-node additive diff:

```text
diff:
    added:
        DeploymentDiffFile: {added: {}, changed: {}, removed: {}}
        DeploymentState:    {added: {}, changed: {}, removed: {}}
    changed: {}
    removed: {}
```

Relationship-level `branch` is documented as "if not defined, it will be determined based on
both peers", so the mixed pairing is an intended case rather than a tolerated one.

**Alternatives considered**: `branch: local` — rejected, it is still per-branch data and so
reintroduces exactly the "Monday's state arrives on Friday" problem from decision log item 11.
Plain `aware` — rejected for the same reason, plus deployment records would appear in every
proposed change as proposed intent.

---

## R2. Does a two-hop `human_friendly_id` validate?

**Decision**: No — a two-hop path is rejected. `DeploymentDiffFile` ends up with a **one-hop**
`state__name__value`, which became available once R3 forced a `name` attribute onto the parent.

> **Superseded in part.** This finding was written before R3 established that `DeploymentState`
> must carry a copied `name`. The rejection of the two-hop path stands exactly as measured; the
> conclusion "gets no `human_friendly_id` at all" does not. Read the two together.

**Rationale**: the spec's FR-041 pinned `state__device__name__value` with a stated fallback.
The server rejects it outright:

```text
Unable to load the schema:
  DeploymentDiffFile.human_friendly_id: device is not a valid attribute of DeploymentState
```

An HFID path traverses **one** relationship and then names an attribute. At the time this was
measured `DeploymentState` had no `name` attribute (FR-010 — its identity was the device), so
there was no one-hop path from the diff file to anything human-readable, and removing the HFID
was what validated.

R3 then forced a `name` onto `DeploymentState` for unrelated reasons, which made
`state__name__value` a legal one-hop path. It was tested and validates, so the diff file keeps
an HFID after all — and FR-041 is satisfied as originally written rather than through its
fallback clause. The `state` relationship is mandatory, which is what an identity path
requires (see R3).

This is not a loss. `DeploymentDiffFile` is `include_in_menu: false` and is reached through
its parent record in one hop, exactly as `AvdHostvarFile` is reached through its artifact. An
HFID exists so objects can be referenced from object-data files by something other than a
UUID, and no object file will ever seed a diff — the reconciler writes them.

**Alternatives considered**:

- Add a `name` attribute to `DeploymentState` carrying the device name, giving the diff file
  a one-hop `state__name__value`. **Rejected here, then adopted in R3** — not to buy the diff
  file an identifier, which nothing needed, but because it turned out to be the only way to
  keep devices deletable while leaving records identifiable. The duplication objection was
  right and is answered by making the reconciler own the field.
- Give `DeploymentDiffFile` its own `name`. **Rejected**: same duplication, one level further
  down, and the uniqueness constraint on `state` already makes it exactly identified.

**Spec impact**: FR-041's fallback clause was taken during planning and then became
unnecessary during implementation. The shipped schema satisfies FR-041 as written.

---

## R3. How is FR-025 (device deletion) delivered — and the trap in the obvious answer

**Decision**: **Not** with `on_delete`. The obvious line is accepted by schema check and is
actively dangerous. Cleanup is the reconciler's, and the runtime behaviour of deleting a
device is verified during implementation rather than assumed now.

**Rationale**: `on_delete: cascade` on `DeploymentState.device` passes `infrahubctl schema
check` with no warning. It also means the opposite of what a reader would assume. The
reference is unambiguous:

> `on_delete` — Default is no-action. **If cascade, related node(s) are deleted when this
> node is deleted.**

The relationship is declared *on* `DeploymentState` and its peer is the device. So
`cascade` there means: **deleting a deployment record deletes the switch.** A reconciler
tidying up a stale record would delete a fabric member, and every gate in this repository —
schema check, `invoke lint`, `pytest tests/unit` — passes on the way there.

The direction that would be wanted, "deleting the device removes its record", has to be
declared on the device's side of the relationship. There is no device side: FR-021 makes the
relationship one-sided precisely so that no deployment relationship lands on the four device
kinds. So `on_delete` cannot deliver FR-025 in either direction, and its one available
spelling is a footgun.

**What delivers FR-025 instead**: the reconciler enumerates devices and upserts one record
each. A record whose device is gone is simply never visited again, so the reconciler sweeps
records whose device relationship no longer resolves. That is one pass in the executor cycle,
not a schema property.

### ANSWERED during implementation (T011) — and it was worse than either option

**Infrahub 1.10.6 blocks the deletion, and keeps blocking it after the record is gone.**

Measured twice, on freshly created throwaway devices:

```text
Cannot delete DcimDevice '18d58a5a-...'. It is linked to mandatory relationship
device on node DeploymentState '18d58a5a-7d21-...' at DeploymentState.device
```

The second run deleted the `DeploymentState` first, confirmed it was absent
(`record confirmed gone: True`), fetched the device fresh, and deleted it — and the delete
was still refused, **naming the record that had just been deleted**. So with
`optional: false` the block is not "delete the record first"; it is permanent for the life
of the device. Since the reconciler attaches a record to every device, mandatory would make
every device in the fabric undeletable, by a bookkeeping node most operators would not know
existed.

That disqualifies `optional: false`. But making `device` optional collided with two other
things, and the collision is the real finding:

```text
DeploymentState.uniqueness_constraints: cannot use device relationship,
relationship must be mandatory. (`device`)
```

**A relationship used for identity — in `uniqueness_constraints` *or* in
`human_friendly_id`, which Infrahub derives a uniqueness constraint from — must be
mandatory.** So the three things the spec wanted could not all hold at once:

| Wanted | Requires |
| --- | --- |
| Device stays deletable (FR-025) | `device` optional |
| Record identified by device name (FR-040, SC-003) | `device` mandatory |
| One record per device (FR-050) | `device` mandatory |

**Decision**: identity moves off the relationship onto a copied `name` attribute
(`unique: true`), and `device` becomes optional.

- FR-025 holds — verified: `device delete = ALLOWED with optional device relationship`, and
  the record remains with an unresolvable peer, which is what the reconciler sweeps.
- FR-040 / SC-003 hold — `human_friendly_id: [name__value]`, and a lookup by
  `leaf-nfd41-pod1-1-1` returns the record with that display label.
- FR-050 holds — a duplicate is rejected with `Violates uniqueness constraint 'name'`.

**Cost, stated plainly**: this reverses FR-010, which said `DeploymentState` must have no
`name` because "duplicating the device name into a second place that can drift from it buys
nothing". It buys something after all — it is the only arrangement that keeps devices
deletable while leaving records identifiable. The drift it warned about is real and becomes a
reconciler obligation: **the reconciler owns `name` and refreshes it from the device every
cycle**, so a device rename converges rather than stranding a stale record.

**Alternatives rejected**: keeping `optional: false` and accepting undeletable devices —
rejected, this repository decommissions devices and the failure would surface as a confusing
error naming a kind the operator has never heard of. Dropping identity entirely and
addressing records by UUID — rejected, it fails SC-003 and with it the point of user story 1.

**Alternatives considered**: a reverse relationship on `DcimGenericDevice` carrying
`on_delete: cascade`. **Rejected** — it requires an `extensions` block on the generic, which
FR-024 forbids, and it puts a deployment relationship on all four device kinds, which is the
surface user story 5 exists to keep clear. Buying automatic cleanup at the price of the
isolation the whole design rests on is the wrong trade.

---

## R4. Does the one-sided device relationship survive the repository's own contract tests?

**Decision**: Yes, and the precedent is explicit.

**Rationale**: `tests/unit/test_dcim_schema_contract.py::test_every_identifier_is_two_sided_and_agrees`
runs over **every** identifier in `schemas/`, not just the ones a cycle touches — it was
written after a global `sed` silently flipped five unrelated peers. A one-way relationship
that declares an `identifier` would fail it.

`DeploymentState.device` declares **no** `identifier`, so the check cannot see it. That is the
same arrangement `AvdArtifact.device` uses, and `schemas/objects/objects.yml` says so in a
comment rather than leaving it to be rediscovered:

> this relationship declares no identifier, so the two-sided check in
> `tests/unit/test_dcim_schema_contract.py` cannot see it — it is pinned by the fragment/peer
> clauses instead.

The `last_diff` / `state` Component-Parent pair **does** carry a matching identifier on both
sides, so it is visible to that test and passes it.

**Consequence for the plan**: the new schema file carries the same explanatory comment. A
one-sided relationship that is invisible to the repository's own two-sided check is worth
three lines of comment wherever it appears, because the next person to read it will otherwise
assume it is a bug.

---

## R5. Where does `DeploymentState` appear in the UI, given `menus/menu.yml` exists?

**Decision**: `include_in_menu: true` this cycle; the menu cycle flips it to `false` and adds
a `menus/menu.yml` entry.

**Rationale**: `menus/menu.yml` states the rule in its own header — *"To prevent duplicate
menu entries, set `include_in_menu: false` on schema nodes that appear in this menu."* A node
that is in neither place is reachable only by UUID, which fails FR-043 and with it user story
1, the entire point of the feature.

So the two settings are a handoff, not a choice: `true` now makes the node reachable in the
default menu with no `menus/` change; the follow-up menu cycle sets it to `false` in the same
commit that adds the curated entry, and the node is never unreachable in between.
`include_in_menu: true` is already used in `schemas/security/security.yml` and
`schemas/service/access_services.yml`, so it is not novel here.

**Alternatives considered**: doing the menu entry in this cycle. **Rejected** — the routing
hook takes one artifact type per cycle, and a `menus/` change is a Menu artifact with its own
contract test (`test_service_layer_menu_contract.py`, `test_evpn_gateway_menu_contract.py`)
that this cycle is not scoped to write.

---

## R6. Does the new schema file need registering anywhere?

**Decision**: No. `schemas/deployment.yml` is picked up with no other file changed.

**Rationale**: `.infrahub.yml` deliberately does **not** declare `schemas:` — the block is
present but commented out, with the reason given inline: schemas load explicitly through
`invoke load` / `invoke load-schema` so that load order and timing stay controlled, rather
than on every repository sync. `infrahubctl schema load schemas` walks the directory, so a new
file in it is loaded and no registration is required.

This also means FR-024's "no `extensions` block" and the absence of any `.infrahub.yml` edit
together give the cycle a genuinely additive footprint: one new schema file, one new test,
one `AGENTS.md` paragraph, and a regenerated `protocols.py`.

---

## R7. What the FR-061 test may and may not read

**Decision**: the test reads `triggers.yml` and `.infrahub.yml` from the repository root.

**Rationale**: `tests/unit/test_unit_test_contracts.py::test_unit_tests_do_not_read_specs_directory`
walks the AST of every `tests/unit/test_*.py` and fails on any `Path(...)` or `open(...)`
whose first argument starts with `specs/`. A test that tried to assert the no-generation rule
by reading this spec would fail that contract.

Both files the test does need are at the repository root and outside `specs/`, so the check is
satisfied by construction. Worth stating because "assert the rule from the document that
states it" is the natural first instinct and it is blocked here on purpose.

---

## Summary of changes to the spec's stated assumptions

| Spec statement | Research outcome |
| --- | --- |
| FR-007 `branch: agnostic`, escalate if rejected | **Confirmed valid.** No escalation. |
| FR-041 two-hop HFID, fallback if rejected | **Rejected by server.** Fallback taken: no HFID on `DeploymentDiffFile` (R2). |
| FR-025 "`on_delete` behaviour **or** removal by the reconciler" | **`on_delete` eliminated** — its only spelling deletes the device (R3). Reconciler sweep, plus one live verification task. |
| FR-043 reachable in UI | `include_in_menu: true`, handed to the menu cycle (R5). |
| FR-021 one-sided relationship | **Confirmed safe** against the repository's two-sided contract test, with precedent (R4). |

No `NEEDS CLARIFICATION` items remain.
