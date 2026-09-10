# Acceptance Evidence

**Feature**: `specs/011-crossplane-manifest-transform` | **Date**: 2026-09-10
**Branch**: `cx-peering` | **Infrahub**: 1.10.6

> **Re-verified after the Jinja2 template was replaced by `yaml.dump`** (research R1a).
> Every criterion below was re-run against the new implementation. The only change to the
> output is quote *style* — the dumper emits `'true'` and `'65401:110'` where the template
> emitted `"true"` and `"65401:110"`, and drops the unnecessary quotes around `fabric`.
> Parsed values, types and key order are unchanged.

## SC-001 — renders without error

`uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering --branch cx-peering`

```yaml
apiVersion: nfd41.lab/v1alpha1
kind: FabricPeering
metadata:
  name: nfd41-fabric-peering
spec:
  localASN: 65401
  authSecretName: nfd41-bgp-auth
  nodeSelector:
    nfd41.lab/bgp: 'true'
  advertisementSelector:
    nfd41.lab/advertise: fabric
  podCIDRCommunities:
    - '65401:110'
  timers:
    connectRetrySeconds: 5
    holdTimeSeconds: 9
    keepAliveSeconds: 3
  peers:
    - name: k8s-leaf1
      address: 10.110.0.2
      asn: 65101
    - name: k8s-leaf2
      address: 10.110.0.3
      asn: 65101
```

## SC-002 / T034 — satisfies the XRD

Validated against `../lab/crossplane/platform/00-xrd-fabric-peering.yaml`:

| Check | Result |
| --- | --- |
| `apiVersion` and `kind` match the XRD | ✅ |
| `localASN` present and an integer (XRD-required) | ✅ |
| `peers` non-empty (XRD-required) | ✅ |
| Each peer carries exactly `name`, `address`, `asn` | ✅ |
| No peer address contains `/` — a neighbour, not a prefix | ✅ |
| Every label-map value is a string, not a coerced boolean | ✅ |
| Every `podCIDRCommunities` entry is a string, not a coerced number | ✅ — a colon-bearing scalar is force-quoted; `test_every_value_survives_a_round_trip_with_its_type_intact` asserts it |

## SC-003 / T035 — compared with the hand-written file it replaces

`../lab/crossplane/platform/10-peering.yaml`, field by field:

| Field | Hand-written | Rendered |
| --- | --- | --- |
| `localASN` | `65401` | `65401` |
| `peers` | k8s-leaf1 / 10.110.0.2 / 65101, k8s-leaf2 / 10.110.0.3 / 65101 | identical |
| `authSecretName` | *absent, XRD default* | `nfd41-bgp-auth` |
| `nodeSelector` | *absent, XRD default* | `{nfd41.lab/bgp: "true"}` |
| `advertisementSelector` | *absent, XRD default* | `{nfd41.lab/advertise: fabric}` |
| `podCIDRCommunities` | *absent, XRD default* | `['65401:110']` |
| `timers` | *absent, XRD default* | `{5, 9, 3}` |

**Shared fields: 2. Mismatched: 0. Omitted by the render: nothing.**

Every one of the five added fields carries **exactly** the value the XRD would have
defaulted to, so the rendered manifest is semantically identical to the hand-written one
with the defaults made explicit. That is the desired direction: a reviewer can see the
whole contract rather than having to cross-reference the XRD to know what is in force.

### ⚠️ One finding needing a decision: `metadata.name`

| | Value |
| --- | --- |
| Hand-written resource | `nfd41` |
| Rendered resource | `nfd41-fabric-peering` |

`metadata.name` comes from the `ServiceFabricPeering` object's name, and I named the seed
object descriptively. The XRD is **cluster-scoped with one resource per cluster**, so
applying the rendered manifest as it stands would create a *second* `FabricPeering`
alongside the deployed one rather than updating it in place.

Three ways to resolve it, none yet chosen:

1. **Rename the service object to `nfd41`** — one line in
   `objects/35_nfd41_peering_service.yml`. Simplest, but makes the service's name a
   Kubernetes identifier rather than a description.
2. **Render `metadata.name` from the cluster name instead of the service name** — one line
   in the transform. Arguably more correct: the XRD is cluster-scoped, so the resource is
   identified by its cluster, and it stays right even if someone renames the service.
   Two services referencing one cluster would then collide, which a check should catch
   anyway (already listed in `data-model.md` section 7).
3. **Accept it** and let the lab's hand-written resource be deleted when the artifact
   takes over.

**Recommendation: option 2.** It ties the manifest's identity to the thing the XRD is
actually scoped to, and it removes a way for a rename to silently produce a duplicate
resource. It was not applied unilaterally because it changes what the artifact is called,
which is a decision about the deployed system rather than about the code.

## SC-004 / T019 — deterministic

Two consecutive renders of an unchanged model: `diff` reports nothing. **Byte-identical.**
Re-run against the `yaml.dump` implementation: still byte-identical. Key order now comes
from dict insertion order with `sort_keys=False` rather than from a template's line order,
and selector keys are inserted sorted.

## SC-005 / T020 — a one-field change moves one line

Changed the cluster's `local_asn` from 65401 to 65999 and re-rendered:

```diff
6c6
<   localASN: 65401
---
>   localASN: 65999
```

Two lines of diff output, one changed line. Reverted afterwards. This is the property the
whole feature exists for. Re-verified against the `yaml.dump` implementation at the fixture
level rather than by mutating live data a second time: `+0 added, -0 removed, ~1 modified`.

## SC-006 — an incomplete model fails loudly

Six error paths covered by fixture tests, each naming the object and the field:

| Condition | Message names |
| --- | --- |
| Cluster has no `local_asn` | the cluster and the field |
| Service has no enabled peering | the service, and why an empty list is worse than an error |
| Service has no peerings at all | as above |
| Peering has no `peer_address` | that peering |
| Selector entry has no `=` | that entry |
| No target matched the name | the kind |

A `provisioning` status deliberately still renders — whether to apply a manifest is an
operator's decision, and refusing would make the artifact useless for review before
activation.

## SC-007 — no secret value rendered

`test_no_secret_value_is_ever_rendered` asserts the output contains `nfd41-bgp-auth` (the
secret's *name*) and none of `password`, `Nfd41-Cilium` or `cleartext`. The transform only
ever reads `bgp_auth_secret_name`.

## SC-008 / SC-009 — tests and linters

```text
uv run pytest tests/unit          809 passed
lint-ruff                         PASS
lint-yaml                         PASS
lint-mypy                         PASS
lint-markdown                     PASS
lint-prose                        7 errors / 4 warnings — pre-existing in docs/, unchanged
```

Ruff findings in the new files were resolved by following existing precedent rather than by
suppression, except one documented `# noqa: S107` where ruff flags any default whose name
contains "secret" — the value there is a secret's *name*, which is exactly what this
transform renders instead of a password. The dumper subclass's `indentless` argument, which
PyYAML passes by keyword and which the override exists to ignore, is discarded with an
explanatory `del` rather than a `# noqa: ARG002`.

`pyyaml>=6.0.1` was added to `[project].dependencies`. That also resolves a pre-existing
undeclared import: `generators/generate_avd_device_hostvar.py` already imported `yaml` in
production code while relying on pyavd to supply it.

## SC-011 / T008 — the seed object loads idempotently

Two consecutive loads of `objects/35_nfd41_peering_service.yml`: zero uniqueness
violations, one `ServiceFabricPeering`. `ServiceFabricPeering` inherits its
human-friendly id from `ServiceGeneric`, so unlike `SecurityPolicyRule` it upserts
cleanly.

Also resolved here, from `data-model.md` section 6's open question: **a scalar name does
resolve through the `OrganizationGeneric` generic.** `owner: branch` loaded without an
inline `kind:` block.

## Not yet evidenced

| Criterion | Status | Why |
| --- | --- | --- |
| SC-010 — repository sync and artifact generation | **Blocked** | `infrahubctl repository list` returns empty: no `CoreRepository` is registered on this instance. Exercising a sync needs the branch pushed to a remote and `repository.yml` loaded, which is deployment setup rather than transform work |

### What that leaves unverified, precisely

The three `.infrahub.yml` registrations are written and `yamllint`-clean, and the artifact
definition matches the repository's existing conventions for a YAML artifact
(`avd_anta_catalog`, `containerlab_topology`). What has **not** been proven:

| Unverified | Risk |
| --- | --- |
| Infrahub accepts the three registrations on sync (US2 scenario 1) | Low. The shapes match five existing entries field for field. The one thing a sync catches that nothing else does is a mismatch between the transform's `query` attribute and the registered query name — and that pairing was checked by hand: both are `crossplane_fabric_peering` |
| An artifact is produced against the service (US2 scenario 2) | Low. `ServiceFabricPeering` inherits `CoreArtifactTarget`, verified in the generated protocols, and the object is in the `service_fabric_peerings` group, verified by query |
| The artifact's checksum is stable for an unchanged model (US2 scenario 3) | **Already proven at the content level** — two renders are byte-identical (SC-004), and the checksum is a function of the content |

So US2's substance is evidenced; what is missing is the plumbing between Infrahub and a
git remote. Registering a repository is the natural first step of whatever cycle wires
the Vidra operator, which spec assumption 3 already placed outside this one.
