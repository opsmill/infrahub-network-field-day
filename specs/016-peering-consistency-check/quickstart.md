# Quickstart: Validating the Peering Consistency Check

**Feature**: `specs/016-peering-consistency-check` | **Date**: 2026-09-11

## Prerequisites

```bash
uv run infrahubctl branch create peer-check --sync-with-git
uv run infrahubctl schema load schemas --branch peer-check --wait 120
uv run infrahubctl object load objects/ --branch peer-check
```

## Step 1 — Unit tests (no server)

```bash
uv run pytest tests/unit/test_peering_consistency_check.py -v
```

One test per rule C-1 … C-7, plus: several simultaneous violations all reported, an empty model
passing, and every error carrying attribution.

## Step 2 — Regenerate the typed model (server)

```bash
INFRAHUB_DEFAULT_BRANCH=peer-check uv run infrahubctl graphql export-schema \
  --destination /tmp/schema.pc.graphql
uv run infrahubctl graphql generate-return-types checks/peering_consistency_check.gql \
  --schema /tmp/schema.pc.graphql
```

Select `__typename` at every union point, or the run fails with `union_tag_not_found`.

## Step 3 — The clean model passes — SC-001

```bash
uv run infrahubctl check peering-consistency --branch peer-check
```

**Expected**: no errors. If this fails, the check disagrees with the generator and one of them
is wrong — resolve that before trusting any failure it reports.

## Step 4 — A seeded violation fails — SC-002

Edit one session's `peer_asn` away from its device's `RoutingAsn`, re-run, and confirm the
error names the session, the recorded value and the device's value. Revert afterwards.

## Step 5 — Several violations at once — SC-007

Introduce two unrelated violations and confirm **both** are reported in one run. A check that
stops at the first forces a merge-fix-merge cycle per problem.

## Step 6 — Full gate

```bash
uv run pytest tests/unit
uv run invoke lint
```

`lint-prose` has a pre-existing baseline of 7 errors / 4 warnings.

## What is deliberately not validated

| Not tested | Why |
| --- | --- |
| Agreement with AVD's rendered config | Nothing rendered exists — research R1. This is the most valuable remaining rule and needs the AVD chain run first |
| `$infrahub-run-integration-tests` | Not installed; same exception as cycles 010–015 |

## Failure triage

| Symptom | Likely cause |
| --- | --- |
| Check passes when it should fail | The rule iterated an empty collection — the vacuous-pass failure mode research R1 warns about |
| Check fails on a generator-produced model | The check and the generator disagree; the generator is authoritative for C-1 and C-2 |
| Errors have no object attribution | The query omits `id` or `__typename` |
| `EvpnSviNode` false positives | Matching on device alone instead of device and VLAN (R5) |
