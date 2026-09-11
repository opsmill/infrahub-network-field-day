# Quickstart: Validating the Application File Attachments

**Feature**: `specs/013-app-file-attachments` | **Date**: 2026-09-10

Seven steps, cheapest first. Steps 1–2 need no server. Step 6 is the regression oracle.

Design detail is not repeated here: see [data-model.md](./data-model.md) for the shape and
[contracts/schema-kinds.md](./contracts/schema-kinds.md) for the guarantees.

---

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status ✅, Infrahub 1.10.6
```

A branch created **with git sync**, or the repository never reads `.infrahub.yml` for it:

```bash
uv run infrahubctl branch create app-files --sync-with-git
uv run infrahubctl schema load schemas --branch app-files --wait 120
uv run infrahubctl object load objects/ --branch app-files
```

**Capture the baseline before changing anything** — it is the oracle for step 6:

```bash
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch app-files > /tmp/baseline.yaml
```

---

## Step 1 — Lint (no server)

```bash
uv run yamllint schemas/
```

---

## Step 2 — Contract tests (no server)

The primary gate. These read the YAML directly, so they run without an instance.

```bash
uv run pytest tests/unit/test_service_layer_schema_contract.py -v
```

Coverage to expect, per [contracts/schema-kinds.md](./contracts/schema-kinds.md) §5:

| Assertion | Guards |
| --- | --- |
| Both kinds exist and inherit `CoreFileObject` | GI-4 — the checksum arrives by inheritance |
| Each has a mandatory cardinality-one `Parent` to `ServiceFabricApp` | GI-1 |
| Each is unique on `["app"]`, written bare | GI-2, and the skill's uniqueness rule |
| Both sides of each relationship share one identifier | GI-5 — a mismatch silently makes two one-way links |
| `ServiceFabricApp` still has all 16 attributes and its 5 original relationships | GI-6, additivity |
| Neither kind redeclares a `CoreFileObject` field | Inheritance is real, not copied |

---

## Step 3 — Schema check (server)

```bash
uv run infrahubctl schema check schemas/ --branch app-files
```

**Expected**: zero validation errors, and a diff that adds exactly two kinds and modifies
`ServiceFabricApp` only.

---

## Step 4 — Load and regenerate (server)

```bash
uv run infrahubctl schema load schemas --branch app-files --wait 120
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
uv run invoke lint-mypy
```

`invoke lint-mypy` checks `src/solution_arista_avd` — the repository's actual gate. Never
hand-edit `protocols.py`; regenerate it.

---

## Step 5 — Attach a file and read it back (server) — SC-002, SC-003, SC-006, SC-007

There is no CLI for this: `infrahubctl object load` cannot upload file content. Use the SDK,
as `generators/generate_avd_device_hostvar.py` does.

**Expected**:

- the content returns byte-for-byte, including keys containing dots and slashes (SC-006)
- a payload of 150+ lines of nested YAML survives unchanged (SC-007)
- re-uploading identical content leaves `checksum` unchanged (SC-003)
- attaching a second values file to the same application is rejected (SC-004)

---

## Step 6 — The regression oracle (server) — SC-008

The step that decides whether the change was really additive.

```bash
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch app-files | diff /tmp/baseline.yaml -
```

**Expected**: no output. The artifact's checksum should still be
`0d800c9d5005b5fdb6b371bb5627d143`. A schema change that moves it is not additive, whatever
the diff said.

---

## Step 7 — Full gate

```bash
uv run pytest tests/unit
uv run invoke lint
```

**Expected**: all tests pass; ruff, yamllint, mypy and rumdl pass. `lint-prose` fails on 7
pre-existing errors in `docs/` unrelated to this feature — confirm the count is unchanged
rather than assuming.

---

## What is deliberately not validated here

| Not tested | Why | Where it lands |
| --- | --- | --- |
| `$infrahub-run-integration-tests` | Not installed; same exception as cycles 010–012 | plan.md Complexity Tracking |
| The seeding script | It is code, and belongs to the cycle that needs it | Cycle 014 |
| The transform that reads the attachment | Next cycle | Cycle 014 |
| Enforcement of the file-beats-attribute rule | The schema documents it; only a check could enforce it | A later check cycle |

---

## Failure triage

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| `references unknown field` on load | `__value` used on a relationship in the uniqueness constraint | data-model §3 |
| Two one-way relationships instead of one | The two sides' `identifier` strings differ | research R4; the skill's CRITICAL rule |
| A file survives its application's deletion | Parent side is not `Component` | data-model §7 V-3 |
| The artifact checksum moved | The change was not additive | step 6 — stop and investigate before proceeding |
| mypy fails on `protocols.py` | It was hand-edited | Regenerate it |
