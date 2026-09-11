# Acceptance Evidence

**Feature**: `specs/016-peering-consistency-check` | **Date**: 2026-09-11
**Branch**: `peer-check` (Infrahub) / `016-peering-consistency-check` (git) | **Infrahub**: 1.10.6

## SC-001 — the clean model passes

```text
$ uv run infrahubctl check peering-consistency --branch peer-check
INFO  peering_consistency_check::PeeringConsistencyCheck: PASSED
```

The stop-and-check of the cycle. A check that fails a generator-produced model is worse than
no check: it and the generator would disagree, and neither could then be trusted.

## SC-002 — a hand-edited session fails the merge

`k8s-leaf1`'s `peer_asn` edited from `65101` to `64999`:

```text
ERROR  peering_consistency_check::PeeringConsistencyCheck: FAILED
ERROR    session 'k8s-leaf1' records peer_asn 64999 …
```

This is the gap the cycle exists to close. The generator would have corrected this on its next
run; nothing previously stopped it being merged first. Reverted, and the check passes again.

## SC-006, C-7 — the advisory path behaves correctly

The lab has `EvpnSviNode` records on devices with no matching virtual interface —
`app-leaf1`, `app-leaf2`, `leaf-nfd41-pod1-2-1` and others. Not every SVI node is a peering
SVI, so these are advisory and must not block a merge. Verified: with the ASN reverted the
check **passes** even though those findings exist.

⚠️ **A presentation detail worth knowing.** `infrahubctl check` prints nothing on success, and
on failure prints *every* message at `ERROR` level — including `log_info` advisories, which
appear as `ERROR  ADVISORY: …`. They did not cause the failure; the ASN error did. Reading
that output without knowing this would suggest fourteen problems where there is one.

## SC-003 … SC-005, SC-007 … SC-009 — fixture coverage

12 tests, one per rule plus the reporting guarantees:

| Rule | Test |
| --- | --- |
| C-1 ASN | `test_asn_mismatch_is_reported` — asserts both values are in the message |
| C-2 address | `test_address_mismatch_is_reported` |
| C-3 one service per cluster | `test_two_services_on_one_cluster_is_reported` |
| C-4 uncabled peer | `test_uncabled_peer_is_reported` |
| C-5 non-leaf role | `test_non_leaf_peer_is_reported` |
| C-6 SVI agreement | `test_svi_node_disagreement_is_reported` |
| C-6 matching | `test_svi_node_matching_is_by_device_and_vlan` — device **and** VLAN |
| C-7 advisory | `test_svi_node_without_a_matching_interface_is_advisory` |
| G-1 | `test_clean_model_passes` |
| G-2 | `test_every_violation_is_reported` |
| G-3 | `test_every_error_carries_attribution` |
| SC-008 | `test_empty_model_passes` |

Fixtures rather than live data because most violations cannot be created against a live
instance — the generator refuses to write them. A proposed change can still contain them,
which is the whole point.

## SC-010 — tests and linters

```text
uv run pytest tests/unit          871 passed  (859 + 12 new)
lint-ruff / lint-yaml / lint-mypy / lint-markdown    PASS
lint-prose    7 errors / 4 warnings — pre-existing, unchanged
```

---

## The rule that is deliberately absent

The most valuable rule for this project would be "does the cluster's view agree with what AVD
renders onto the leaf?" It is **not implemented**, and the reason was measured before the spec
was written rather than discovered during implementation:

| Candidate authority for the fabric's own view | Objects, every branch |
| --- | --- |
| `RoutingBGPNeighbor` | 0 |
| `AvdStructuredConfigFile` | 0 |
| `AvdHostvarFile` | 0 |
| `AvdArtifact` | 0 |

The AVD generator chain has never run on this instance. A check written against these would
iterate an empty collection and log nothing — **a vacuous pass**, which is worse than no check
because it manufactures confidence. Running the AVD chain is the precondition, and that rule is
then a cycle of its own. It is the single most valuable item left in the backlog.

## Three generator-model facts found while implementing

Each cost a red test and is worth recording for the next `.gql`:

1. **`__typename` must be selected on nested relationship nodes too**, not just at the obvious union points — `device { node { … } }` needed it, and the first run failed with a missing-discriminator error.
2. **The generator drops `__typename` on concrete nodes.** It emits a discriminator only where a union needs one, so `session.typename__` does not exist and the kind must be named in code for error attribution.
3. **Field names are snake_cased aggressively**: `ClusterFabricPeering` → `cluster_fabric_peering` for attribute access (PascalCase still works as an input alias), and `dot1q_id` → `dot_1_q_id`.

## Principle IV — the documented alternative

`$infrahub-run-integration-tests` is not installed, the same exception as cycles 010–015.
Evidence here: 12 fixture tests covering every rule, a live PASS against the generator's own
output, and a live FAIL against a deliberately seeded violation with the message content
checked.
