# Phase 0 Research: Peering Consistency Check

**Feature**: `specs/016-peering-consistency-check` | **Date**: 2026-09-11

## R1 — What the check can compare against

**Decision**: The graph only. Not AVD's rendered view.

Measured on every branch before the spec was written:

| Source | Objects |
| --- | --- |
| `RoutingBGPNeighbor` | 0 |
| `AvdStructuredConfigFile` | 0 |
| `AvdHostvarFile` | 0 |
| `AvdArtifact` | 0 |
| `EvpnSviNode` | **16** |

The AVD generator chain has never run on this instance. A check comparing the cluster's view
against the fabric's rendered view would therefore iterate an empty collection and report
success — a vacuous pass, which is worse than no check because it creates false confidence.

`EvpnSviNode` is present and is a genuine second record of the same fact, so it is checkable
and becomes US3.

**Consequence**: the single most valuable rule for this project — "do the two ends of the
session agree?" — is deferred behind a precondition (run the AVD chain) rather than written
against nothing.

---

## R2 — Global, not targeted

**Decision**: No `targets` in the registration.

The skill's registration rule: a check with no `targets` runs on every proposed change; a
targeted check needs both `targets` and `parameters` and runs per member of a `CoreCheckGroup`.

The inconsistencies here are not scoped to a fabric — "two services claim one cluster" is a
statement about the whole graph, and there is no natural group to iterate. Both existing checks
in this repository are targeted on `fabrics` because they validate per-fabric pools; this one
is not analogous.

---

## R3 — `log_error` versus `log_info`

**Decision**: `log_error` for every rule in FR-007 … FR-012; `log_info` for the advisory case
in US3 scenario 2.

The SDK has **no `log_warning`**. Any `log_error` blocks the merge, and `log_info` does not, so
the choice between them is the choice of whether a finding is a gate or a note. An
`EvpnSviNode` with no matching SVI is not necessarily wrong — not every SVI node is a peering
SVI — so it is a note.

---

## R4 — Overlap with the generator is deliberate

**Decision**: Rules FR-007 and FR-008 duplicate what the generator derives.

This is not redundancy. The generator asserts those values *when it runs*; object data can set
them at any time, and a proposed change can be merged without the generator having run at all.
The check is the gate, the generator is the corrector, and the overlap is the point.

FR-014 draws the line: the check does not re-validate things object data cannot express, such
as a cluster with no `local_asn`, which blocks generation anyway.

---

## R5 — Matching `EvpnSviNode` to an SVI

**Decision**: On device **and** VLAN id, not device alone.

A device may carry several `EvpnSviNode` records — the lab has 16 across 8 devices. Matching on
device alone would compare a peering SVI against an unrelated tenant SVI and report a
difference that is not drift.

---

## R6 — Reporting every violation

**Decision**: Accumulate, never return early.

A check that stops at the first failure forces a merge-fix-merge cycle for each independent
problem. The existing `fabric_pool_check.py` accumulates in the same way.

## Risk register

| Risk | Mitigation |
| --- | --- |
| The check fails a model the generator produced | SC-001 runs it against exactly that |
| A vacuous pass on empty collections | R1; SC-008 asserts an empty model passes *deliberately* rather than by accident |
| Matching the wrong SVI node | R5 — device and VLAN |
| The check blocks merges for an advisory finding | R3 — `log_info` for the one non-gate case |
