# Acceptance Evidence

**Feature**: `specs/017-fabric-app-transform` | **Date**: 2026-09-11
**Branch**: `app-render` (Infrahub) / `017-fabric-app-transform` (git) | **Infrahub**: 1.10.6

## SC-001 — it renders

```yaml
apiVersion: nfd41.lab/v1alpha1
kind: FabricApp
metadata:
  name: nfd41-demo
spec:
  namespace: nfd41-demo
  tenant: k8s-prod
  manifests:
    - apiVersion: apps/v1
      kind: Deployment
      …
```

## SC-003 / SC-005 — compared with the hand-written manifest

Normalised field by field against `../lab/crossplane/apps/10-demo.yaml`:

```text
<     allowEgressToAPIServer: false
<     allowEgressToInternet: false
<     allowIntraNamespace: true
```

**Three differences, all fields the render adds, each carrying exactly the XRD's default.**
Zero shared fields differ.

| Check | Result |
| --- | --- |
| `policy.allowFrom` identical | ✅ `['10.210.0.0/24', '10.60.0.0/16', '10.70.0.0/24']` |
| `spec.manifests` identical | ✅ all **6** Kubernetes objects, round-tripped through the attachment |
| `spec.expose` identical | ✅ |
| `allowFromPorts[].port` is a string | ✅ |
| `serviceSelector` value is a string | ✅ `'true'`, not a boolean |

## The comparison earned its keep twice

Neither of these would have been caught by reading the schema.

**`tenant` rendered as `k8s_prod`.** The VRF is `K8S_PROD` and research R3 said "lower-cased".
Lower-casing alone leaves an underscore; the XRD's default and the hand-written manifest both
say `k8s-prod`. Now lower-cased **and** `_`→`-`.

**`allowIntraNamespace` was semantically wrong.** I seeded `policy_allow_intra_namespace:
false`. The XRD defaults it to `true` and the oracle omits it, so the deployed application
permits intra-namespace traffic — the rendered manifest would have **denied** it. This is not a
cosmetic difference: it is a change to a live network policy, and it is exactly the class of
error SC-003 exists to catch. The seed is corrected and the reason is recorded in the object
file.

## SC-004 — deterministic

Two consecutive renders: `diff` reports nothing.

## SC-008 — the seeding script is idempotent

```text
run 1: nfd41-demo: uploaded (4529 bytes) — 1 payload(s) written
run 2: nfd41-demo: unchanged (4529 bytes) — 0 payload(s) written
```

## SC-010 — cycle 011 is undisturbed

The peering render is byte-identical before and after. This is the first cycle since 011 to add
a second artifact definition, so it was asserted rather than assumed.

## SC-011 — tests and linters

```text
uv run pytest tests/unit          886 passed  (871 + 15 new)
lint-ruff / lint-yaml / lint-mypy / lint-markdown    PASS
lint-prose    7 errors / 4 warnings — pre-existing, unchanged
```

---

## Three things implementation corrected

**A payload file cannot live under `objects/`.** `infrahubctl object load objects/` parses
every YAML file in that tree as an Infrahub object file. A bare list of Kubernetes manifests
aborts the entire load with a pydantic `dict_type` error, **taking every other object file with
it** — the branch ended up with no cluster, no devices, nothing. The payload now lives in
`payloads/` and both the file and the script say why.

**`download_file()` is a method on an SDK node, not on a generated query model.** The query
returns the attachment's metadata; the node must be re-fetched by id before its content can be
read. `avd_anta_catalog.py` already does exactly this for `AvdStructuredConfigFile`.

**`ServiceFabricApp` has no `advertisement_selector`.** That attribute belongs to
`ServiceFabricPeering`. The query and the field mapping dropped it; the XRD defaults
`expose.advertisementSelector`, so omitting it is correct rather than a gap.

## A note for whoever brings up a fresh instance

`invoke load` alone **no longer fully seeds the repository**. The manifests payload is a file
attachment, and `object load` cannot upload file content, so
`scripts/seed_app_payloads.py` must run after it or the application renders with no workload.
This is the cost cycle 013 accepted when it chose the attachment over an inline attribute.

## Principle IV — the documented alternative

`$infrahub-run-integration-tests` is not installed, the same exception as cycles 010–016.
Evidence: 15 fixture tests, a live render, a field-by-field comparison with the manifest this
replaces, determinism, and an assertion that the previous cycle's artifact is unmoved.
