# Quickstart: Validating the FabricApp Transform

**Feature**: `specs/017-fabric-app-transform` | **Date**: 2026-09-11

## Prerequisites

```bash
uv run infrahubctl branch create app-render --sync-with-git
uv run infrahubctl schema load schemas --branch app-render --wait 120
uv run infrahubctl object load objects/ --branch app-render
```

**Record cycle 011's checksum before starting** — SC-010 asserts this cycle does not disturb it:

```bash
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch app-render > /tmp/peering-baseline.yaml
```

Then upload the payload, which `object load` cannot do:

```bash
uv run python scripts/seed_app_payloads.py --branch app-render
```

## Step 1 — Unit tests (no server)

```bash
uv run pytest tests/unit/test_crossplane_fabric_app.py -v
```

Covers the field mapping, selector parsing, type discipline, attachment precedence, and all
five validation paths — most unreachable live because the schema forbids the shapes.

## Step 2 — Regenerate the typed model (server)

```bash
INFRAHUB_DEFAULT_BRANCH=app-render uv run infrahubctl graphql export-schema \
  --destination /tmp/schema.ar.graphql
uv run infrahubctl graphql generate-return-types transforms/crossplane_fabric_app.gql \
  --schema /tmp/schema.ar.graphql
```

Select `__typename` at every union point **including nested relationship nodes** — cycle 016
found the generator needs it in both places.

## Step 3 — Render it — SC-001

```bash
uv run infrahubctl transform crossplane_fabric_app name=nfd41-demo --branch app-render
```

Check by eye: `serviceSelector` is a map with `'true'` quoted; `allowFromPorts[].port` is a
string; `allowFrom` has three CIDRs; `manifests` carries the workload.

## Step 4 — Compare with the oracle — SC-003, SC-005

```bash
uv run infrahubctl transform crossplane_fabric_app name=nfd41-demo --branch app-render > /tmp/rendered.yaml
diff <(uv run python -c "import yaml;print(yaml.safe_dump(yaml.safe_load(open('/tmp/rendered.yaml')),sort_keys=True))") \
     <(uv run python -c "import yaml;print(yaml.safe_dump(yaml.safe_load(open('../lab/crossplane/apps/10-demo.yaml')),sort_keys=True))")
```

Exits non-zero — read the hunks, not the exit code. Every difference must be a field the render
**adds** carrying an XRD default. **`policy.allowFrom` and `spec.manifests` must not appear in
the diff at all.**

## Step 5 — Determinism — SC-004

Two consecutive renders; `diff` reports nothing.

## Step 6 — The peering artifact is undisturbed — SC-010

```bash
uv run infrahubctl transform crossplane_fabric_peering \
  name=nfd41-fabric-peering --branch app-render | diff /tmp/peering-baseline.yaml -
```

**Expected**: no output. This is the first cycle since 011 to add a second artifact definition.

## Step 7 — Seeding is idempotent — SC-008

Run the seeding script twice; the attachment count and checksum are unchanged.

## Step 8 — Full gate

```bash
uv run pytest tests/unit
uv run invoke lint
```

`lint-prose` has a pre-existing baseline of 7 errors / 4 warnings.

## Failure triage

| Symptom | Likely cause |
| --- | --- |
| `union_tag_not_found` | `__typename` missing at a union point or a nested relationship node |
| `manifests` is empty | The attachment was never uploaded — run the seeding script |
| `serviceSelector` renders as a string | Selector parsing not applied |
| `'true'` became `true` | The value was passed through a path that re-typed it |
| `policy: {}` emitted | An empty policy was not omitted, and may override XRD defaults |
| The peering render moved | Something in this cycle touched shared code — stop and investigate |
