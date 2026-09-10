# Quickstart: Validating the Crossplane FabricPeering Transform

**Feature**: `specs/011-crossplane-manifest-transform` | **Date**: 2026-09-10

Nine steps, cheapest proofs first. Steps 1–3 need no server. Steps 4–7 need the local
stack with the technical layer loaded. Step 8 is the acceptance oracle — the consumer's
own validator.

Design detail is not repeated here: see [data-model.md](./data-model.md) for the field
mapping, [contracts/manifest-contract.md](./contracts/manifest-contract.md) for the
rendered resource and registration, and [research.md](./research.md) for why.

---

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status ✅, Infrahub 1.10.6
```

The technical layer must be loaded. On a fresh branch:

```bash
uv run infrahubctl branch create cx-peering
uv run infrahubctl schema load schemas --branch cx-peering --wait 30
uv run infrahubctl object load objects/ --branch cx-peering
```

Confirm the transform has something to read:

```bash
# Expect: nfd41, ASN 65401, two peerings
uv run infrahubctl object load objects/34_nfd41_cluster.yml --branch cx-peering
```

---

## Step 1 — Lint (no server)

```bash
uv run yamllint objects/ schemas/
uv run ruff check . && uv run ruff format --check .
```

**Expected**: clean. `ruff format` is worth running before committing — this session's
earlier cycles needed it twice.

---

## Step 2 — Unit tests (no server)

The primary quality gate, and the only place the error paths are reachable.

```bash
uv run pytest tests/unit/test_crossplane_fabric_peering.py -v
```

**Expected**: all pass. Coverage, per FR-040:

| Behaviour | Why a fixture rather than live data |
| --- | --- |
| Selector parsing, including `a=b=c` and a missing `=` | A malformed selector cannot be stored without breaking the schema |
| Address stripping | Deterministic and worth pinning |
| Peer ordering | Provable without depending on the server's `order_by` |
| Disabled peering omitted | Cheap to construct, awkward to arrange live |
| No `local_asn` → raises | The live schema makes this hard to create |
| No enabled peerings → raises | Same |
| Missing `peer_address` → raises | Same — the relationship is mandatory |
| Output parses as YAML with the right `apiVersion` and `kind` | The structural guarantee |

---

## Step 3 — Confirm nothing untyped or undeclared crept in (no server)

```bash
# Generated model is imported and used, not bypassed
grep -n 'CrossplaneFabricPeeringQuery' transforms/crossplane_fabric_peering.py

# No raw dictionary indexing of the response
grep -nE 'data\[.(ServiceFabricPeering|target).\]' transforms/crossplane_fabric_peering.py

# The transform imports yaml, so pyyaml must be a DECLARED dependency (research R2)
grep -n '^import yaml' transforms/crossplane_fabric_peering.py
grep -n 'pyyaml' pyproject.toml
```

**Expected**: the first matches, the second returns nothing, the last two both match.

---

## Step 4 — Regenerate the typed model (server)

```bash
# generate-return-types validates against a LOCAL schema.graphql, which is exported from
# `main` by default -- where this feature's schema does not exist yet. Export from the
# feature branch first, or it fails with "Cannot query field 'ServiceFabricPeering'".
INFRAHUB_DEFAULT_BRANCH=cx-peering uv run infrahubctl graphql export-schema \
  --destination /tmp/schema.cx.graphql
uv run infrahubctl graphql generate-return-types transforms/crossplane_fabric_peering.gql \
  --schema /tmp/schema.cx.graphql
uv run mypy --show-error-codes src/solution_arista_avd transforms
```

**Expected**: the model is written and mypy passes. This is also the first real check that
the query is valid against the live schema — a bad field name fails here.

Only needed if you change the `.gql`. The generated model is committed.

Never hand-edit the generated file to satisfy mypy. Regenerate.

---

## Step 5 — Render it (server) — SC-001

```bash
uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering \
  --branch cx-peering
```

**Expected**: the manifest from
[contracts/manifest-contract.md](./contracts/manifest-contract.md) §1. Check by eye:

- `localASN: 65401`
- `nodeSelector` is a **map**, `nfd41.lab/bgp: 'true'` — quoted, because it is a label value
  and would otherwise be read back as a boolean. The dumper decides this, not a template
- `podCIDRCommunities` entries are quoted too — `'65401:110'`, forced because a colon in a
  plain scalar is the one thing YAML parsers read differently
- both peers present, addresses **without** `/24`
- `k8s-leaf1` before `k8s-leaf2`
- no password anywhere, only `authSecretName`

---

## Step 6 — Prove it is deterministic (server) — SC-004

```bash
for i in 1 2; do
  uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering \
    --branch cx-peering > "/tmp/render-$i.yaml"
done
diff /tmp/render-1.yaml /tmp/render-2.yaml && echo "byte-identical"
```

**Expected**: no output from `diff`. If this fails, key ordering or peer sorting is not
pinned — see research R7.

---

## Step 7 — Prove a model change moves exactly one line (server) — SC-005

```bash
# Change one value, re-render, diff
# (adjust the cluster's local_asn in the UI or via GraphQL, then:)
uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering \
  --branch cx-peering > /tmp/render-3.yaml
diff /tmp/render-1.yaml /tmp/render-3.yaml
```

**Expected**: exactly the `localASN` line differs. Revert the change afterwards.

This is the property the whole feature exists for — the lab's own workflow is "change the
model, re-render, review the diff, then push".

---

## Step 8 — Acceptance: the consumer validates it — SC-002, SC-003

Two independent checks, and the second is the real oracle.

**Does Kubernetes accept it against the lab's XRD?**

```bash
uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering \
  --branch cx-peering > /tmp/rendered.yaml
kubectl apply --dry-run=client -f /tmp/rendered.yaml
```

**Expected**: accepted. If the lab cluster is not up, validate the shape against
`../lab/crossplane/platform/00-xrd-fabric-peering.yaml` by hand instead — the XRD lists
`localASN` and `peers` as the only required fields.

**Does it match the hand-written file it replaces?**

```bash
diff <(python3 -c "import yaml,sys; print(yaml.safe_dump(yaml.safe_load(open('/tmp/rendered.yaml')), sort_keys=True))") \
     <(python3 -c "import yaml,sys; print(yaml.safe_dump(yaml.safe_load(open('../lab/crossplane/platform/10-peering.yaml')), sort_keys=True))")
```

Normalising both through a sorted dump compares content rather than formatting.

**Expected**: differences only where deliberate. The hand-written file omits fields that
rely on XRD defaults (`authSecretName`, `timers`, `podCIDRCommunities`,
`advertisementSelector`, `nodeSelector`), so the rendered version is a **superset** —
every field it adds carries the value the XRD would have defaulted to. Any difference in
`localASN`, a peer name, address or ASN is a **bug**, not a deliberate difference.

Record the field-by-field comparison as SC-003 evidence.

---

## Step 9 — Artifact generation (server) — SC-010

```bash
uv run infrahubctl object load objects/00_groups.yml --branch cx-peering
uv run infrahubctl object load objects/35_nfd41_peering_service.yml --branch cx-peering
# twice, to prove SC-011
uv run infrahubctl object load objects/35_nfd41_peering_service.yml --branch cx-peering
```

**Expected**: the second load produces no uniqueness violation and leaves one
`ServiceFabricPeering`.

Then sync the repository and confirm the artifact appears against the service with content
type `application/yaml`, and that regenerating an unchanged model leaves the checksum
alone (US2 scenario 3).

---

## Step 10 — Full gate

```bash
uv run pytest tests/unit
uv run invoke lint
```

**Expected**: all tests pass; ruff, yamllint, mypy and rumdl pass. `lint-prose` currently
fails on 7 pre-existing errors in `docs/` unrelated to this feature — confirm the count is
unchanged rather than assuming.

---

## What is deliberately not validated here

| Not tested | Why | Where it lands |
| --- | --- | --- |
| The manifest actually establishing BGP in the lab | Needs the lab deployed; this cycle renders, it does not deploy | Lab verification |
| The Vidra operator pulling the artifact | Delivery is out of scope (spec assumption 3) | Later cycle |
| `FabricApp` and `AppAccess` manifests | Need service-layer objects not loaded, and hit the JSON dotted-key bug | Later cycle |
| That the rendered ASNs match what AVD put on the leaves | Comparing two renderings, not producing one | `checks/` |

---

## Failure triage

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| `Unable to find the node ...` on loading the seed | `ServiceGeneric.owner` peers a generic; a scalar name may not resolve | data-model §6 — an inline `kind:` block may be needed |
| Selector renders as a string, not a map | `_parse_selector` not applied to that field | research R8; the split belongs in Python |
| Peer address carries `/24` | Stripping not applied | data-model §3 |
| `diff` in Step 6 shows output | Key order or peer sort not pinned | research R7 |
| mypy complains about the generated module | It was hand-edited | Regenerate; never edit it |
| Transform not found by `infrahubctl transform` | `query` attribute does not match the registered query name | contract §2 — it matches the registered name, not the operation name |
| 500 on writing a selector | A JSON attribute was used instead of a `List` | `schemas/MARKETPLACE.md` — the dotted-key server bug |
