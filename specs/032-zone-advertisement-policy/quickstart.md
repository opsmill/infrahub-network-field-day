# Quickstart: validating the zone advertisement policy

A schema cycle, so most of this is fast. The one step worth care is the last: the query the *next* cycle depends on has to return something useful, or this cycle has shipped two fields nobody can use.

Roughly 10 minutes, all on a branch.

## Prerequisites

```bash
uv run infrahubctl info          # Connection Status must be ✅
```

---

## 1. Check before loading

```bash
uv run infrahubctl schema check schemas/
```

**Expected**: zero errors, and a diff showing two additions to `SecurityZone` and one to `DcimFabricSwitch`. Nothing else should appear — if another kind shows up, the extension landed in the wrong block.

Covers SC-001.

---

## 2. Load onto a branch

```bash
uv run infrahubctl branch create zone-advert
uv run infrahubctl schema load schemas --branch zone-advert
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
```

**Expected**: the load succeeds and `protocols.py` regenerates with the two new fields on `SecurityZone`. Do not hand-edit it — it is generated, and the constitution forbids editing it to satisfy static analysis.

```bash
git diff --stat src/solution_arista_avd/protocols.py    # should be small and additive
```

---

## 3. The seed data still loads

```bash
uv run infrahubctl object load objects/32_nfd41_security.yml --branch zone-advert
```

**Expected**: every one of the six zones loads, plus the rest of the file — seven firewall interfaces, twelve prefixes, four address groups, one policy, nineteen rules. The two new fields are optional, so nothing that omits them is rejected.

**This is the step that catches a mandatory-by-accident attribute.** Attributes default to `optional: false`; four of the six zones supply no value at all.

Covers SC-003, SC-004, FR-050.

---

## 4. The values are right

```bash
uv run infrahubctl object load objects/32_nfd41_security.yml --branch zone-advert
```

Then read them back — in the UI, or by query. **Expected**, exactly:

| Zone | prefix list | device |
| --- | --- | --- |
| `branch` | `PL-DC-ADVERTISED-BRANCH` | `leaf-nfd41-pod1-3-1` |
| `wan` | `PL-DC-ADVERTISED` | `leaf-nfd41-pod1-3-1` |
| the other four | empty | empty |

**The negative half is the half that matters.** Four empty zones is the correct steady state; a run that populated `acme-cloud` would look more complete and be wrong — those prefixes are the *subject* of an advertisement toward `wan`, not the destination of one. See [contracts/seed-values.md](./contracts/seed-values.md).

Covers SC-002, FR-062.

---

## 5. Deleting a switch does not delete a zone

The one behaviour a wrong `on_delete` would silently change.

On the branch, delete `leaf-nfd41-pod1-3-1`, then read the `branch` zone.

**Expected**: the zone still exists and is readable; only its `advertising_device` is now empty. If the zone disappeared, `on_delete: cascade` was added — it deletes the *peer*, and `infrahubctl schema check` accepts the line without complaint.

Discard the branch afterwards rather than keeping a fabric with a missing leaf.

Covers SC-005, FR-023, V3.

---

## 6. The query the next cycle depends on

This is the point of the whole cycle. A client that knows only the zone kind must get both values in one request, with no traversal into `NetworkFabric.avd_custom_hostvars`.

```graphql
query {
  SecurityZone {
    edges {
      node {
        name { value }
        dc_advertised_prefix_list { value }
        advertising_device { node { name { value } } }
      }
    }
  }
}
```

**Expected**: six zones, two populated. If this needs a second query or a JSON parse, FR-030 is not met and the generator cycle inherits the problem.

Covers SC-002, SC-006, FR-030.

---

## 7. Nothing else moved

```bash
uv run pytest tests/unit -q
uv run invoke lint
```

**Expected**: all pass, including the new contract tests and the existing `tests/unit/test_junos_config.py`, which holds the rendered firewall artifact byte-for-byte. This cycle renders nothing new — no generator writes to the fields yet — so any movement there means something unintended changed.

Covers SC-007.

---

## 8. Clean up

```bash
uv run infrahubctl branch delete zone-advert
```

`main` is untouched throughout.

---

## Full-environment check

After merging:

```bash
scripts/verify_bootstrap.sh          # ~20 minutes, destroys and rebuilds
```

**Expected**: all sixteen assertions pass. A schema change that loads on a branch and breaks a cold build is a real failure mode — the branch already had the old schema converged.

Covers SC-008.
