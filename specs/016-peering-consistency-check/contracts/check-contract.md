# Contract: Check Interface

**Feature**: `specs/016-peering-consistency-check` | **Date**: 2026-09-11

## 1. Registration

```yaml
queries:
  - name: peering_consistency_check
    file_path: "./checks/peering_consistency_check.gql"

check_definitions:
  - name: peering-consistency
    file_path: "./checks/peering_consistency_check.py"
    class_name: PeeringConsistencyCheck
```

**No `targets` and no `parameters`** — this is a global check. Both existing checks in this
repository are targeted on `fabrics` because they validate per-fabric pools; these rules are
statements about the whole graph, and "two services claim one cluster" has no natural group to
iterate.

The class attribute `query = "peering_consistency_check"` must match the registered query name
exactly. A mismatch fails silently.

## 2. Query contract

**Operation**: `PeeringConsistencyCheckQuery` — no variables, because the check is global.

MUST return `id` and `__typename` on every node it may report on, or the errors cannot carry
attribution.

## 3. Guarantees

| # | |
| --- | --- |
| G-1 | A model the generator produced passes with zero errors |
| G-2 | Every violation in a run is reported, not just the first |
| G-3 | Every `log_error` carries `object_id` and `object_type` |
| G-4 | The check writes nothing |
| G-5 | An empty model passes |
| G-6 | Only C-7 uses `log_info`; every other finding blocks the merge |

## 4. Relationship to the generator

Deliberate overlap. The generator asserts C-1 and C-2 **when it runs**; the check asserts them
**before a merge**. Object data can set either value at any time, and a proposed change can be
merged without the generator ever having run.

## 5. What this contract does not cover

- Agreement between the cluster's view and AVD's rendered configuration. Not implementable
  here: `RoutingBGPNeighbor`, `AvdStructuredConfigFile`, `AvdHostvarFile` and `AvdArtifact` are
  all empty. Running the AVD chain is the precondition, and that rule is the most valuable one
  remaining for this project.
- The other five service kinds, which have no objects.
