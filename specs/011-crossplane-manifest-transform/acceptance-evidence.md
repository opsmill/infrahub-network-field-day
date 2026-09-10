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
  name: nfd41
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

**Shared fields: 3 (including `metadata.name`). Mismatched: 0. Omitted by the render: nothing.**

Every one of the five added fields carries **exactly** the value the XRD would have
defaulted to, so the rendered manifest is semantically identical to the hand-written one
with the defaults made explicit. That is the desired direction: a reviewer can see the
whole contract rather than having to cross-reference the XRD to know what is in force.

### `metadata.name` — resolved, option 2 applied

| | Value |
| --- | --- |
| Hand-written resource | `nfd41` |
| Rendered resource, as first written | `nfd41-fabric-peering` |
| Rendered resource, now | `nfd41` |

`metadata.name` originally came from the `ServiceFabricPeering` object's name, which was
seeded descriptively. Because the XRD is **cluster-scoped with one resource per cluster**,
applying that manifest would have created a *second* `FabricPeering` beside the deployed
one rather than updating it in place.

The transform now renders `metadata.name` from `ClusterKubernetes.name`. That ties the
manifest's identity to the thing the XRD is actually scoped to, and removes a path by
which renaming a service silently produces a duplicate resource;
`test_metadata_name_comes_from_the_cluster_not_the_service` renames the service in a
fixture and asserts the manifest's identity does not move. Two services pointing at one
cluster now collide instead, which is the failure a check should catch and which
`data-model.md` section 7 already lists.

**The rendered manifest is now field-for-field identical to the hand-written one**, with
the five XRD defaults made explicit. Nothing about the deployed lab changed; this only
changes what the artifact would do if applied.

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

## SC-010 / T025 — repository sync

**Correcting an earlier claim in this document**: SC-010 was recorded as blocked because
"exercising a sync needs the branch pushed to a remote". That was wrong. The working tree
is already bind-mounted into the task-worker at `/upstream`
(`docker-compose.override.yml:40`), which is exactly the `location` that `repository.yml`
declares, and `invoke load` registers it as part of routine setup. No remote is involved.

Registering it worked first time and synced git `main`:

| Imported from git main's `.infrahub.yml` | Count |
| --- | --- |
| Python transforms | 8 |
| Artifact definitions | 6 |
| Check definitions | 2 |
| Generator definitions | 7 |
| GraphQL queries | 17 |

`sync_status: in-sync`, `operational_status: online`, commit `4412576`. Artifact generation
was triggered automatically for all six existing definitions, which is the behaviour US2
depends on.

### Two prerequisites nothing documents

Getting the feature branch to sync took two discoveries, both worth recording because
neither is in the quickstart, the skill rules, or `AGENTS.md`:

**1. `infrahubctl branch create` defaults to `--no-sync-with-git`.** A branch created
without that flag is never associated with a git branch, so Infrahub never reads
`.infrahub.yml` for it and no registration can ever appear. This is the actual reason
SC-010 looked blocked: the branch used for every other piece of evidence in this document
had `sync_with_git=False`. Nothing warns you; the branch simply stays empty of
repository-derived objects.

**2. The instance's scheduled sync was deadlocked.** `git_repositories_sync` is scheduled
every minute but had not run since 13:57 — seven hours. Its Prefect deployment carries a
concurrency limit of 1, and a flow run orphaned when the workers restarted was still
holding the slot in `PENDING` with no start time, so every subsequent run was cancelled
with `Deployment concurrency limit reached`. `clean-up-deadlocks` was stuck the same way,
on the same minute. Cancelling the two orphaned runs released both slots and the
minute-by-minute sync resumed immediately.

That second one is worth a bug report: a worker restart can permanently wedge every
scheduled flow with a concurrency limit, and the only symptom is that repository syncs
silently stop happening.

**3. The branch's schema must be loaded before its first sync.** Infrahub validates a
`CoreGraphQLQuery` against the branch's schema as it imports it, so syncing a branch whose
schema has not been loaded yet fails at the first new query:

```text
Found 9 Python transforms in the repository
Found 7 artifact definitions in the repository
Failed to synchronize branch, skipping it.
  reason=Cannot query field 'ServiceFabricPeering' on type 'Query'
         path: ['CoreGraphQLQueryCreate']
```

This is the registration check doing its job — the counts show Infrahub read the feature's
`.infrahub.yml` correctly — but it means a branch created by `infrahubctl branch create`
must have `schema load` and `object load` run against it *before* the repository sync
reaches it. The ordering is not obvious, because the branch is created from `main` and
inherits `main`'s schema, which is exactly what a new feature's schema is not.

It also has a sharp edge: the commit is recorded on the repository *before* the import
runs, so after an `error-import` the branch sits at the failed commit and the sync has
nothing new to do. Loading the schema afterwards does not trigger a retry — the branch has
to advance to a new commit. Both facts together mean the reliable order is: create the
branch, load schema, load objects, *then* push the code.

### Result — US2 scenario 1

With the schema loaded, the next sync accepted all three registrations:

| Registration | Imported as |
| --- | --- |
| `CoreGraphQLQuery` | `crossplane_fabric_peering`, owned by `test-repository` |
| `CoreTransformPython` | `crossplane_fabric_peering` → `CrossplaneFabricPeeringTransform`, query `crossplane_fabric_peering` |
| `CoreArtifactDefinition` | `crossplane_fabric_peering` → artifact "Crossplane FabricPeering", `application/yaml`, targets `service_fabric_peerings` |

`sync_status: in-sync`. The pairing a sync catches that nothing else does — the transform's
`query` attribute against the registered query name — resolved correctly.

## SC-010 / T026 — the artifact is generated

Artifact generation fired automatically as part of the sync
(`21:25:13 Generate artifact Crossplane FabricPeering`), with no manual trigger:

| Field | Value |
| --- | --- |
| Name | `Crossplane FabricPeering` |
| Status | `Ready` |
| Content type | `application/yaml` |
| Target | `nfd41-fabric-peering` |
| Checksum | `a69b520a245e75fe1e6c3195f32f8229` (superseded — see below) |

Fetched from storage, the artifact's bytes are identical to the `infrahubctl transform`
render recorded under SC-001, and `md5sum` of those bytes equals the checksum Infrahub
recorded. The only difference against the captured CLI output is one trailing blank line,
which `infrahubctl` adds when printing to a terminal; the artifact itself ends with a
single newline.

## SC-010 / T027 — the checksum is stable

Regenerated against an unchanged model via
`POST /api/artifact/generate/<definition-id>?branch=cx-peering`:

| | Before | After |
| --- | --- | --- |
| Checksum | `a69b520a245e75fe1e6c3195f32f8229` | `a69b520a245e75fe1e6c3195f32f8229` |
| Storage id | `18d412b3-786e-…` | `18d412b3-786e-…` |
| Artifact count | 1 | 1 |

The regeneration was confirmed to have actually executed before the comparison was
believed — `21:25:57 Beginning subflow run 'Generate artifact Crossplane FabricPeering'`,
following the trigger at `21:25:55`. Checking that mattered: an earlier attempt passed the
*artifact* id where the endpoint wants the *artifact definition* id, which returns HTTP 200
and then fails in the background with `NodeNotFoundError`. Without reading the logs, that
failure would have looked like a passing stability test.

This is SC-004 observed through the artifact rather than through stdout, and it is what
makes a changed checksum meaningful to an operator.

### The other direction: a real change moves the checksum

Applying the `metadata.name` decision gave the complementary proof. Regenerating after the
transform changed produced a new artifact:

| | Before | After |
| --- | --- | --- |
| Checksum | `a69b520a245e75fe1e6c3195f32f8229` | `0d800c9d5005b5fdb6b371bb5627d143` |
| Storage id | `18d412b3-786e-…` | `18d4133e-a9bd-…` |
| `metadata.name` | `nfd41-fabric-peering` | `nfd41` |
| Artifact count | 1 | 1 |

`md5sum` of the fetched bytes again equals the checksum Infrahub recorded. Together with
T027 this is the property an operator needs in both directions: unchanged model, unchanged
checksum; changed output, changed checksum.

**Operational note worth keeping**: a repository sync that picks up new *transform code*
does not regenerate existing artifacts. The sync reached commit `a49ffcc` and reported
`in-sync`, and the artifact still carried the old checksum until generation was triggered
explicitly. Artifacts are regenerated when their target data changes, not when the code
that renders them does.

## US2 acceptance, closed

All three scenarios this document previously listed as unproven are now evidenced
end to end, so the earlier "what that leaves unverified" table has been removed rather
than left to contradict the sections above:

| Scenario | Evidence |
| --- | --- |
| 1 — Infrahub accepts the three registrations on sync | T025 above: `in-sync`, all three imported, the `query`-attribute pairing resolved by the server rather than by hand |
| 2 — an artifact is produced against the service | T026 above: `Ready`, `application/yaml`, against `nfd41-fabric-peering`, bytes identical to the render |
| 3 — the checksum is stable for an unchanged model | T027 above: identical checksum and storage id across a regeneration confirmed to have executed |

The one thing still outside this cycle is delivery: nothing here proves the Vidra operator
pulls the artifact or that the manifest establishes BGP in the lab. Spec assumption 3
placed both outside this feature, and they remain there.

With this, the alternative evidence set that [plan.md](./plan.md)'s Complexity Tracking
offers in place of `$infrahub-run-integration-tests` is **complete**: fixture unit tests,
a live render, a Kubernetes-shape validation against the consumer's XRD, and a repository
sync plus artifact generation. T043 is a sign-off decision, not a gap in coverage.
