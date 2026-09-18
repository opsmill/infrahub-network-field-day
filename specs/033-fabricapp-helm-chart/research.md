# Phase 0 Research: Fabric Application as a Helm Chart

**Feature**: `033-fabricapp-helm-chart`
**Date**: 2026-09-18

Every finding below was measured against the running Infrahub 1.10.6 instance on a
throwaway branch (`research-033-schema`, created and deleted during this phase),
or read from the sibling lab repository. Nothing here is inferred from
documentation alone.

---

## R1 — Making the three chart fields mandatory fails against existing data

**Decision**: Populate `chart_repository`, `chart_name` and `chart_version` on
every existing `ServiceFabricApp` **before** loading the schema that makes them
mandatory. Do not use `default_value`.

**Measured**: loading the patched schema with the three fields at
`optional: false` against a branch carrying real data was refused:

```text
Unable to load the schema:
  Attribute-level 'optional' constraint violation on schema 'ServiceFabricApp'.
  Node (nfd41-demo) is not compliant.,
  ... (six messages: three attributes x two nodes)
```

After setting the three values on both applications on the same branch, the
identical schema check passed and produced the intended diff. So the ordering is
real, not theoretical, and it **inverts `invoke load`**, which loads schema before
objects.

Two details worth carrying forward:

- The error names the **node** and the constraint but never the **attribute**.
  With three fields changed at once it says "not compliant" six times and points
  at no field, so a partial population looks identical to none.
- The instance carried a second application, `podinfo`, created through the
  portal rather than seeded. A migration that only considers `objects/` misses
  it. Any instance that has been used will have others.

**Rationale for rejecting `default_value`**: a default chart repository is a
value nobody chose. Every application that had not stated one would silently
acquire it, and an application pointing at the wrong chart renders, merges and
delivers — the failure mode this whole feature is meant to remove.

**Alternatives considered**:

- *`default_value: ""`* — passes the constraint and means "mandatory" is a lie;
  the renderer would have to re-check emptiness, which is where we started.
- *Leave the three optional and enforce in the transform* — keeps the ambiguity
  in the model and moves the error later, which is the current behaviour.

---

## R2 — `state: absent` removes an attribute, a relationship and a whole node kind

**Decision**: Use `state: absent` for `manifests`, `manifests_file` and
`ServiceFabricAppManifestsFile`.

**Measured**: with the three marked absent, `infrahubctl schema check` reported
exactly the intended diff and nothing else:

```text
changed:
    ServiceFabricApp:
        attributes:
            removed:
                manifests: null
        relationships:
            added:
                advertised_services: null
            removed:
                manifests_file: null
removed:
    ServiceFabricAppManifestsFile: null
```

`infrahubctl schema load` then succeeded, and afterwards the kind was gone
(`SchemaNotFoundError: Unable to find the schema
'ServiceFabricAppManifestsFile'`), `manifests` and `manifests_file` were no
longer attributes of the application, and `advertised_services` was.

Notably the load was **not** blocked by the two existing file objects
(`nfd41-demo-manifests.yaml` and `podinfo-manifests_file.yaml`). It removes the
kind regardless, which means the file objects become unreachable rather than
demonstrably deleted.

**Consequence**: delete the file objects *before* removing the kind, so removal
is something the plan does rather than something it relies on the schema loader
to have done. SC-004 is otherwise unverifiable — once the kind is gone there is
no way to query for what is left.

---

## R3 — `infrahubctl protocols` ignores `state: absent`

**Decision**: `state: absent` is a migration step, not an end state. The blocks
come out of the YAML in the same cycle, after the load has been performed.

**Measured**: regenerating protocols from the patched schema produced a
`ServiceFabricApp` that still declares the removed fields, alongside the new
relationship it did pick up correctly:

```python
class ServiceFabricApp(ServiceGeneric, GeneratorTarget, CoreArtifactTarget):
    chart_name: String                    # mandatory: String, not StringOptional
    chart_repository: String
    chart_version: String
    manifests: JSONAttributeOptional      # REMOVED from the graph, still here
    ...
    advertised_services: RelationshipManager[SecurityService]    # correct
    manifests_file: RelationshipAttribute[ServiceFabricAppManifestsFile]  # ditto
```

and `ServiceFabricAppManifestsFile` was still emitted as a class.

The generator reads the YAML files, not the loaded schema, so a `state: absent`
block is read as a declaration rather than as a deletion. Leaving those blocks in
place permanently would make `protocols.py` advertise three things that do not
exist at runtime — precisely the drift Constitution III (Type Safety) exists to
prevent, and it would not be caught by mypy, because the types are internally
consistent.

**Sequence**: mark absent → load → verify gone → delete the blocks from the YAML
→ regenerate protocols → verify clean. A fresh instance never had the kind, so
the finally-committed YAML carrying no manifests blocks at all is correct for
both a rebuild and an in-place upgrade.

**Alternatives considered**:

- *Delete the blocks outright with no `state: absent` step* — a fresh instance is
  fine, but an existing one silently keeps the kind and its data forever. The
  developer's own stack is exactly such an instance.
- *Keep `state: absent` forever and hand-edit `protocols.py`* — prohibited by
  Constitution III, which requires regeneration rather than hand-editing.

---

## R4 — The `advertised_services` relationship resolves port and protocol from one object

**Decision**: `peer: SecurityService`, `kind: Generic`, `cardinality: many`,
`optional: true`, `on_delete: no-action`, identifier
`service__app_advertised_services`.

**Measured**: after loading, relating `nfd41-demo` to the seeded `junos-http` and
reading it back gave:

```text
named services: [('junos-http', 80, 'tcp')]
service object unchanged: True
```

Both halves matter. The first is the whole point of FR-024: one hop from the
application reaches a port *and* a protocol, with no payload fetched and no
cluster consulted. The second discharges FR-026 — `name`, `description` and
`port` on the referenced object were byte-identical before and after, so an
application naming the firewall's own service does not take it over.

**Rationale for `kind: Generic` rather than `Attribute`**: `Attribute` is the
"belongs to" flavour and pairs with `cardinality: one`. This is a
cardinality-many plain reference to objects the application does not own, which
is exactly what `allowed_source_prefixes` on the same node already is.

**Rationale for `on_delete: no-action`**: the only other value is `cascade`,
which deletes the **peer**. On this relationship that would mean deleting an
application deletes `junos-http` and with it four hand-written baseline rules.

**SDK note for the implementing cycle**: `RelationshipManager.add()` raises
`UninitializedError: Must call fetch() on RelationshipManager before editing
members`. Any generator or script touching this relationship must `await
node.advertised_services.fetch()` first. This cost a cycle to find here and is
not in the schema documentation.

**Alternatives considered**:

- *A JSON attribute of port/protocol pairs* (the spec's first draft) — rejected
  on review; see the spec's User Story 3. The number can disagree with the rule
  that permits it.
- *`peer: SecurityGenericService`* — admits `SecurityServiceRange` and
  `SecurityServiceGroup`, neither of which has a single `port`. The access
  generator works in integers throughout, so it would gain a case it cannot
  resolve. Rejected per FR-027.

---

## R5 — The seeded demo has no two-tier chart, and the lab says so

**Decision**: `nfd41-demo` becomes a single-tier `cowboysysop/whoami` release.
**Confirmed with the user**; it was an open assumption in the spec, and the
assumption as written was wrong.

**Found**: the lab's own `crossplane/apps/10-demo.yaml` states the reason it
uses manifests:

> The reason it uses `manifests` rather than `chart` is simply that
> traefik/whoami has no upstream chart worth depending on; the point of the
> escape hatch is that "no chart" does not mean "not managed".

The spec's assumption — "a published upstream image with a chart available, so
expressing it as a chart is a matter of naming one" — was therefore false as
written. A chart does exist; what does not exist is a chart producing the
**two-tier** shape the demo has.

**What the demo actually is**: a frontend Deployment plus a `LoadBalancer`
Service on port 80 (mapping to `targetPort: 8080`), a backend Deployment plus a
`ClusterIP` Service on 8080, and two `CiliumNetworkPolicy` objects expressing an
L7 rule (`GET /api/.*` from frontend to backend). A `FabricApp` renders exactly
one Helm `Release` — the composition's `{{- if $spec.chart }}` is singular — so
one application cannot be two tiers from one chart.

**Chart facts, verified against the chart's own source**:

| Fact | Value | Why it matters |
| --- | --- | --- |
| Repository | `https://cowboysysop.github.io/charts/` | Public, no auth |
| Chart / app version | `6.0.0` / `1.11.0` | `traefik/whoami:v1.11.0` — the image the demo already runs |
| `service.ports.http` | `80` | Matches the seeded `junos-http` exactly, so SC-008 holds |
| `service.type` | `ClusterIP` by default | Must be overridden to `LoadBalancer` in values |
| `commonLabels` | "Labels to add to all deployed objects" | Carries `nfd41.lab/advertise: "true"` onto the Service |
| Service `metadata.labels` | `whoami.labels` + `commonLabels` | The selector uses the narrower `whoami.selectorLabels` |

That last row is the one that could have gone wrong: if `commonLabels` fed
`spec.selector` as well, adding a label would mutate an immutable field and every
upgrade would fail. It does not — the template uses two different helpers.

**What is knowingly lost**: the backend Deployment and its `ClusterIP` Service,
and the two L7 policies. That costs two things the repository currently
demonstrates — the ClusterIP backend's unreachability from the app tenant as an
asserted negative, and the L7 HTTP policy — and both are recorded here so their
removal is a decision rather than an accident.

**Alternatives considered and rejected by the user**: two `FabricApp` objects,
one per tier (lands them in separate namespaces, so `allowIntraNamespace` no
longer spans them); retaining a manifests escape hatch (contradicts the feature);
`podinfo` (genuinely two-tier via its `backend` value, but serves on 9898, which
needs a new `SecurityService` and breaks SC-008).

---

## R6 — The composition needs no change

**Decision**: no lab-repository change is required, for either half.

**Found**: `crossplane/apps/01-composition-fabric-app.yaml` renders the chart
under `{{- if $spec.chart }}` and the manifests under
`{{- range $i, $m := ($spec.manifests | default list) }}`. Both are already
conditional, so a `FabricApp` carrying a chart and no manifests is the
observability application's existing shape and is known to work.

The XRD requires `[repository, name, version]` together whenever `chart` is
present. Making the three mandatory in Infrahub therefore aligns the model with
a constraint that already exists downstream — it is not a new restriction, it is
the same one stated a step earlier, where it can be enforced before an artifact
is rendered rather than after the cluster rejects it.

---

## R7 — The cross-file peer resolves without an `extensions:` block

**Decision**: declare `advertised_services` directly on `ServiceFabricApp` in
`schemas/service/kubernetes_services.yml`.

**Measured**: `peer: SecurityService` resolved with no error even though
`SecurityService` is defined in `schemas/security/security.yml`. Peers are
resolved across the whole loaded set, so an `extensions:` block is only needed to
add fields to a node defined *elsewhere* — not to reference one.

This also keeps the change away from `extensions:`, which matters here: per
`AGENTS.md`, `infrahubctl protocols` does not apply the `extensions:` block, so a
relationship added that way would be invisible to the generated protocols. R3
confirms the direct declaration *is* picked up.

**Layering**: a service kind referencing a technical kind is the permitted
direction. `ServiceFabricApp` already names `IpamPrefix`, `IpamVRF` and
`ClusterKubernetes`; `SecurityService` joins that list and nothing in the
technical layer points back.
