# Quickstart: validating the deployment state schema

**Feature**: `specs/029-deployment-executor`

How to prove this cycle works. Every step is runnable; the expected outcome is stated so a
failure is legible rather than just red. The schema in
[`contracts/deployment.yml`](./contracts/deployment.yml) has already been checked against a
live Infrahub 1.10.6 — see [research.md](./research.md) — so a failure at step 2 means
something changed, not that the design was never tried.

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be ✅
```

`infrahubctl schema check` and `schema load` both need a reachable server and an
authenticated session. If a call returns `401 Unauthorized`, export the token the local stack
was started with before continuing — the compose files carry the default in
`INFRAHUB_INITIAL_ADMIN_TOKEN`.

---

## 1. Put the schema in place

```bash
cp specs/029-deployment-executor/contracts/deployment.yml schemas/deployment.yml
```

No other file changes. `.infrahub.yml` deliberately does not declare `schemas:` — the block is
commented out so load order stays controlled — and `infrahubctl schema load schemas` walks
the directory, so nothing needs registering (research R6).

## 2. Check before loading

```bash
uv run infrahubctl schema check schemas/
```

**Expected**: every file reports `Valid!`, and the diff is purely additive:

```text
diff:
    added:
        DeploymentDiffFile: {added: {}, changed: {}, removed: {}}
        DeploymentState:    {added: {}, changed: {}, removed: {}}
    changed: {}
    removed: {}
```

Anything under `changed:` or `removed:` means this cycle has touched an existing kind, which
it is not supposed to do (FR-024). Stop and find out why.

## 3. Load onto a branch, never straight onto `main`

```bash
uv run infrahubctl branch create deployment-state
uv run infrahubctl schema load schemas --branch deployment-state
```

**One thing to understand before running this.** The *schema definition* is branch-aware, so
it lands only on `deployment-state`. The **records** these kinds hold are `branch: agnostic`,
so any record created later is shared by every branch immediately. Creating test records on a
branch does not isolate them. Step 6 says what to do about that.

## 4. Regenerate protocols

```bash
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
uv run mypy --show-error-codes src/solution_arista_avd
```

**Expected**: `protocols.py` gains `DeploymentState` and `DeploymentDiffFile`, and mypy
passes. The file is generated — if it needs hand-editing to pass, the schema is wrong, not the
file (constitution principle III).

## 5. Prove the model does what the spec claims

Against the branch, in the UI or through the SDK. Each maps to a success criterion.

| # | Do this | Expect | Criterion |
| --- | --- | --- | --- |
| 1 | Create a record against a `DcimFabricSwitch`, supplying its `name` and the device | Accepted; reads back `never_deployed`, `suspend` false | SC-005 |
| 2 | Read its identifier | The switch's name, not a UUID | SC-003 |
| 3 | Create a second record for the same device | **Rejected** by the uniqueness constraint | SC-004 |
| 4 | Create records for a `DcimDevice`, a `SecurityFirewall` and a `ComputePhysicalServer` | All three accepted — the peer is the generic | SC-002 |
| 5 | Set `suspend` and `suspend_reason` on one record | Both persist; other records unaffected | Story 2 |
| 6 | Attach a diff, then delete the record | The diff goes with it; no orphan | SC-007 |

**Step 4 is the one that catches the expensive mistake.** If the device relationship had been
written against `DcimDevice` instead of `DcimGenericDevice`, steps 1–3 would still pass and
only the fabric switch would be missing — silently, with no error anywhere.

## 6. The deletion behaviour FR-025 left open — answered

**This is no longer an open question.** It was measured during implementation and the answer
shaped the schema. Re-run it only if you are changing the device relationship.

With `device` mandatory, Infrahub refuses to delete a device that holds a `DeploymentState`:

```text
Cannot delete DcimDevice '...'. It is linked to mandatory relationship device
on node DeploymentState '...' at DeploymentState.device
```

and — measured twice on freshly created throwaway devices — **it keeps refusing after the
record is deleted**, naming a record that no longer exists. Since a reconciler attaches a
record to every device, mandatory would make the whole fabric undeletable.

`device` is therefore `optional: true`, and the delete succeeds. The record survives with an
unresolvable peer; sweeping those is the reconciler's job, not the schema's.

That optionality is why identity lives on the `name` attribute: Infrahub requires any
relationship used in `human_friendly_id` or `uniqueness_constraints` to be mandatory
(`cannot use device relationship, relationship must be mandatory`). If you make `device`
mandatory again, you get the undeletable-device trap back; if you move identity onto it, you
force it mandatory and get the same trap by a different route.
`tests/unit/test_deployment_schema_contract.py::test_device_relationship_is_optional_and_identity_does_not_depend_on_it`
asserts both halves together for exactly that reason.

**Do not reach for `on_delete` to tidy this up.** On `DeploymentState.device` the only
available value, `cascade`, deletes the *peer* when the record is deleted — that is, deleting
a deployment record deletes the switch. `infrahubctl schema check` accepts it silently.

## 7. The no-generation rule

```bash
uv run pytest tests/unit/test_deployment_schema_contract.py -v
```

**Expected**: passes. Then prove it actually bites — temporarily add a trigger rule to
`triggers.yml` whose `node_kind` is `DeploymentState`, re-run, and confirm it **fails naming
that rule**. Revert.

A test that passes but would also pass with the rule broken is worth nothing here, and this
rule exists because the loop it prevents currently stays open only by accident.

Note the test reads `triggers.yml` and `.infrahub.yml` from the repository root. It must not
read anything under `specs/` — `tests/unit/test_unit_test_contracts.py` walks the AST of every
unit test and fails on it (research R7).

## 8. Full gate

```bash
uv run pytest tests/unit
uv run invoke lint
```

**Expected**: both green, including `test_dcim_schema_contract.py::test_every_identifier_is_two_sided_and_agrees`.
That test scans every identifier in `schemas/`. The `last_diff` / `state` pair carries a
matching identifier on both sides and passes it; `device` declares no identifier at all, so
the check cannot see it — the same arrangement `AvdArtifact.device` uses, for the same reason
(research R4).

## 9. Merge

```bash
uv run infrahubctl branch merge deployment-state
```

**Expected**: the two kinds are on `main` and `DeploymentState` is reachable from the sidebar
under the default menu, because `include_in_menu: true`. Delete any records created during
step 5 **before** finishing — they are `branch: agnostic`, so merging or deleting a branch
does not remove them. The follow-up menu cycle flips that
to `false` in the same commit that adds a curated `menus/menu.yml` entry — so the node is
never unreachable in between (research R5).

---

## Rolling back

The cycle is additive: one new schema file, one new test, an `AGENTS.md` paragraph, and a
regenerated `protocols.py`. Nothing existing is modified. If the branch is not merged,
deleting it removes the schema; the records are branch-agnostic, so delete any created during
step 5 first.
