# Quickstart: Validating the Derived Peering Address

**Feature**: `specs/015-derive-peer-address` | **Date**: 2026-09-11

## Prerequisites

```bash
uv run infrahubctl branch create peer-addr --sync-with-git
uv run infrahubctl schema load schemas --branch peer-addr --wait 120
uv run infrahubctl object load objects/ --branch peer-addr
```

**Capture the baseline first** — it is the oracle:

```bash
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch peer-addr > /tmp/baseline.yaml
```

## Step 1 — Unit tests (no server)

```bash
uv run pytest tests/unit/test_generate_fabric_peering.py -v
```

Every cycle-012 behaviour still asserted, plus: SVI selection by role, the restored create
path, ambiguity failures (V-6′, V-8, V-9), and drift reporting.

## Step 2 — Regenerate the typed model (server)

```bash
INFRAHUB_DEFAULT_BRANCH=peer-addr uv run infrahubctl graphql export-schema \
  --destination /tmp/schema.peer-addr.graphql
uv run infrahubctl graphql generate-return-types generators/generate_fabric_peering.gql \
  --schema /tmp/schema.peer-addr.graphql
```

Remember `__typename` at every union point, or the run fails with `union_tag_not_found`.

## Step 3 — Run it (server) — SC-001

```bash
uv run infrahubctl generator generate-fabric-peering --branch peer-addr name=nfd41-fabric-peering
```

**Expected**: two sessions, addresses `10.110.0.2/24` and `10.110.0.3/24`, derived from the
SVIs rather than read from a file.

## Step 4 — The oracle — SC-002

```bash
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch peer-addr | diff /tmp/baseline.yaml -
```

**Expected**: no output. Deriving the address must not change what reaches the cluster.

## Step 5 — The create path — SC-004

Delete both sessions, re-run, and confirm they come back complete. **This is impossible before
this cycle** — cycle 012 recorded it as a real limitation — so it is the clearest single proof
the feature works.

## Step 6 — A real change still propagates — SC-003

Change an SVI's address, re-run, and confirm the session and the artifact checksum both move.
Revert afterwards.

## Step 7 — Full gate

```bash
uv run pytest tests/unit
uv run invoke lint
```

`lint-prose` has a pre-existing baseline of 7 errors / 4 warnings; confirm it is unchanged.

## Failure triage

| Symptom | Likely cause |
| --- | --- |
| `union_tag_not_found` | `__typename` missing at a union point in the query |
| Address is null | The SVI's `role` is not `peering`, or the reverse relationship is `ip_address` rather than `ip_addresses` |
| Artifact checksum moved | The derived address differs from the live one — read the drift log before assuming a bug |
| A `Loopback0` was selected | Selection fell back to position instead of role |
