# Quickstart: Validating the Fabric Peering Generator

**Feature**: `specs/012-service-layer-generator` | **Date**: 2026-09-10

Nine steps, cheapest proofs first. Steps 1–3 need no server. Steps 4–8 need a branch with the
schema and objects loaded. Step 7 is the acceptance oracle.

Design detail is not repeated here: see [data-model.md](./data-model.md) for the derivation
and validation rules, [contracts/generator-contract.md](./contracts/generator-contract.md)
for the registration and guarantees, and [research.md](./research.md) for why.

---

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status ✅, Infrahub 1.10.6
```

A branch with this feature's schema **and** object data. Cycle 011 established that `main` has
neither, and that the branch must be created with git sync or the repository never reads
`.infrahub.yml` for it:

```bash
uv run infrahubctl branch create <branch> --sync-with-git
uv run infrahubctl schema load schemas --branch <branch> --wait 120
uv run infrahubctl object load objects/ --branch <branch>
```

**Record the baseline before touching anything** — it is the oracle for step 7:

```bash
# Expect: 2 sessions, k8s-leaf1 / k8s-leaf2, ASN 65101, addresses 10.110.0.2 and .3
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch <branch> > /tmp/baseline.yaml
```

---

## Step 1 — Lint (no server)

```bash
uv run ruff check . && uv run ruff format --check .
uv run yamllint objects/ schemas/
```

---

## Step 2 — Unit tests (no server)

The primary quality gate, and the only place several behaviours are reachable at all: the
schema forbids a session with no ASN, so V-5 cannot be produced live.

```bash
uv run pytest tests/unit/test_generate_fabric_peering.py -v
```

Coverage to expect, per [data-model.md](./data-model.md) §4–§5:

| Behaviour | Why a fixture rather than live data |
| --- | --- |
| Near-end exclusion — `peer_device` is never a cluster node | Cheap to construct; catastrophic if wrong |
| Dedup — two nodes on one leaf yield one session | The live lab has exactly this shape |
| Role filtering — a node cabled to a non-fabric device yields no session | Awkward to arrange live |
| Adopt versus create payloads | The distinction that implements both clarifications |
| MLAG pair — equal ASNs do not collapse the set | The live shape, worth pinning |
| Every validation path V-1 … V-7 | Most cannot be created against the live schema |
| Deterministic ordering from a shuffled fixture | Makes the guarantee independent of the server's `order_by` |

---

## Step 3 — Confirm the typed-model contract (no server)

```bash
# The generated model is imported and used, not bypassed
grep -n 'GenerateFabricPeeringQuery' generators/generate_fabric_peering.py

# No raw dictionary indexing of the response
grep -nE 'data\[.(ServiceFabricPeering|target).\]' generators/generate_fabric_peering.py
```

**Expected**: the first matches, the second returns nothing.

---

## Step 4 — Regenerate the typed model (server)

Only needed if you change the `.gql`. The generated model is committed.

```bash
# generate-return-types resolves against a LOCAL schema.graphql exported from `main`
# by default -- where this feature's kinds do not exist. Export from the branch first.
INFRAHUB_DEFAULT_BRANCH=<branch> uv run infrahubctl graphql export-schema \
  --destination /tmp/schema.branch.graphql
uv run infrahubctl graphql generate-return-types generators/generate_fabric_peering.gql \
  --schema /tmp/schema.branch.graphql
uv run invoke lint-mypy
```

`invoke lint-mypy` checks `src/solution_arista_avd` only — that is the repository's actual
gate. Do not widen it to `generators/`: that surfaces 141 pre-existing errors across the seven
existing generators and tells you nothing about your change.

Never hand-edit the generated file to satisfy mypy. Regenerate it.

---

## Step 5 — Run it (server) — SC-001

```bash
uv run infrahubctl generator generate-fabric-peering \
  --branch <branch> name=nfd41-fabric-peering
```

**Expected**: two `ClusterFabricPeering` objects, unchanged in name and address, with
`peer_asn` now derived. Check by eye:

- exactly **two** sessions, not three — three nodes across two leaves (D-4)
- `peer_device` is `leaf-nfd41-pod1-1-1` / `-1-2`, **never** `k8s-node1` (G-2)
- `name` still `k8s-leaf1` / `k8s-leaf2` (G-4)
- `peer_address` still `10.110.0.2/24` / `10.110.0.3/24` (G-4)
- `peer_asn` `65101` on both — equal ASNs are correct for an MLAG pair (D-6)

---

## Step 6 — Prove idempotence (server) — SC-002

```bash
uv run infrahubctl generator generate-fabric-peering --branch <branch> name=nfd41-fabric-peering
uv run infrahubctl generator generate-fabric-peering --branch <branch> name=nfd41-fabric-peering
```

**Expected**: still exactly two sessions, same ids, same attribute values. Object *count*
alone is not sufficient evidence — compare the values, then do step 7, which compares the
rendered output.

---

## Step 7 — The acceptance oracle: the artifact must not move (server) — SC-004

This is the step that decides whether the cycle succeeded.

```bash
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch <branch> > /tmp/after.yaml
diff /tmp/baseline.yaml /tmp/after.yaml && echo "byte-identical — the refactor changed nothing"
```

**Expected**: no output from `diff`. Replacing hand-written rows with generated ones must not
alter what reaches Kubernetes.

Through the artifact rather than stdout, which is what an operator actually consumes:

```bash
# Regenerate and compare against cycle 011's recorded value
curl -s -X POST -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" \
  "http://localhost:8000/api/artifact/generate/<definition-id>?branch=<branch>"
```

**Expected checksum**: `0d800c9d5005b5fdb6b371bb5627d143`, unchanged.

⚠️ Confirm the regeneration actually ran before believing an unchanged checksum. Cycle 011
found that passing the *artifact* id where the endpoint wants the *artifact definition* id
returns HTTP 200 and then fails in the background with `NodeNotFoundError` — which looks
exactly like a passing stability test.

---

## Step 8 — Prove a real change still propagates — SC-005

The complement of step 7. If nothing can move the output, step 7 proves nothing.

```bash
# Change a leaf's ASN in the fabric model (UI or GraphQL), then:
uv run infrahubctl generator generate-fabric-peering --branch <branch> name=nfd41-fabric-peering
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch <branch> | grep asn
```

**Expected**: the session's `peer_asn` follows the fabric model with no object file edited —
which is the entire point of the feature. Revert afterwards.

---

## Step 9 — Full gate

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
| `$infrahub-test-generator-idempotence` | Not installed; steps 6–8 are the documented alternative | plan.md Complexity Tracking |
| `$infrahub-run-integration-tests` | Not installed; same exception as cycles 010 and 011 | plan.md Complexity Tracking |
| BGP actually establishing in the lab | Needs the lab deployed; this cycle derives objects, it does not deploy | Lab verification |
| `peer_address` derivation | Underivable until the leaves' SVIs are modelled | A later schema cycle |

---

## Failure triage

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| Three sessions instead of two | Dedup applied per node rather than per device | data-model D-4 |
| A session whose `peer_device` is `k8s-node1` | The near end was not excluded | research R2 — exclude by interface id |
| `name` or `peer_address` changed on the first run | The adopt payload sent fields it must omit | research R3 — two payload shapes |
| The artifact checksum moved | Same as above, or ordering is not pinned | steps 7 and 8; data-model D-7 |
| A hand-written session disappeared | It was adopted in an earlier run, then stopped being justified | research R4 — adoption is one-way |
| Sessions deleted after a failed run | Validation ran after the first write | contract §5 — validate before writing |
| `Cannot query field 'ServiceFabricPeering'` | Return types generated against `main` | step 4 — export from the branch |
| Generator not found | `query` does not match the registered query name | contract §1 |
| Nothing generated, no error | The target group has no members | Confirm the service is in `service_fabric_peerings` |
