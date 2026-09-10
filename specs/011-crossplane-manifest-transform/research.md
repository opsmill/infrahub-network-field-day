# Phase 0 Research: Crossplane FabricPeering Manifest

**Feature**: `specs/011-crossplane-manifest-transform` | **Date**: 2026-09-10

Ten decisions. Each resolved against the `infrahub-managing-transforms` skill, the two
existing YAML transforms in this repository, the lab's XRD, or the live graph. No
NEEDS CLARIFICATION items remain.

---

## R1 — Transform type: hybrid, not pure Python

> **⚠️ Reversed after implementation.** The maintainer asked why YAML was being
> rendered through Jinja2, and the spec's original instinct was right. The transform is
> now **pure Python**: it builds a dict and emits it with `yaml.dump`. The template
> `transforms/templates/crossplane_fabric_peering.j2` was deleted. See R1a below for what
> this section got wrong.

**Original decision (superseded)**: Python prepares a context, a Jinja2 template renders
the manifest.

**This overturns the spec.** The spec's Transform Type section proposed pure Python
emitting YAML through a dumper, reasoning that a template "has to be careful about
quoting". The reasoning was sound in the abstract and wrong about this repository:

| Existing transform | Output | How it emits |
| --- | --- | --- |
| `containerlab_topology` | `application/yaml` | **Hybrid** — `jinja2.Environment` with a `FileSystemLoader` over `transforms/templates/`, rendering `containerlab_topology.j2` |
| `avd_anta_catalog` | `application/yaml` | pyavd's own `catalog.dump().yaml()` |

Neither uses a general-purpose YAML dumper, and no transform in the repository imports
`yaml` at all. `containerlab_topology` is the direct precedent: a Python transform that
prepares data and renders YAML through a co-located template, for output consumed by
another tool.

The split of work is what makes this safe. Everything that is genuinely logic stays in
Python — parsing selectors, stripping prefix lengths, sorting, validating — so the
template receives a context that is already correct and does nothing but lay out fields.
That is exactly how `containerlab_topology` describes its own division ("Grouped in
Python rather than the template: the template stays free of...").

**Alternatives considered**:

- *Pure Python with `yaml.safe_dump`* — rejected on dependency grounds, see R2.
- *Pure Jinja2 transform* (registered under `jinja2_transforms`) — rejected. The selector
  parsing and address stripping are real transformations; doing them in template filters
  would be less testable and would put logic where the repository keeps layout.

---

## R1a — Pure Python after all, and what R1/R2 got wrong

**Decision**: Build a dict, emit it with `yaml.dump` through a small `SafeDumper`
subclass. No template.

Three things were wrong above:

1. **"No transform in the repository imports `yaml` at all"** was true of `transforms/`
   and irrelevant. `generators/generate_avd_device_hostvar.py` imports it in production
   code, and 18 test modules do. The precedent for importing `yaml` here already existed;
   R1 looked in one directory and drew a repository-wide conclusion.
2. **The skill points the other way.** `rules/types-overview.md` puts "JSON
   restructuring" under *when to use Python* and "text-based output where the template
   closely mirrors the output format" under *when to use Jinja2*. A Kubernetes manifest is
   structured data. `containerlab_topology` is a genuine precedent for hybrid, but it is
   not a precedent that binds a differently-shaped output.
3. **Quoting is the whole argument, and the template lost it.** The dumper decides what
   needs quoting from the value's type. The template needed a hand-written `"{{ value }}"`
   on the two selector loops and the community loop, correct only while the next editor
   remembers why. `true` must stay a string or the API rejects the label map, and
   `65401:110` is ambiguous enough that parsers have disagreed about it — so the transform
   forces a quote on any colon-bearing scalar and leaves everything else to the resolver.
   `test_every_value_survives_a_round_trip_with_its_type_intact` asserts the outcome
   rather than the mechanism.

The cost is one declared dependency and about the same amount of code. Two conditionals
that existed only to omit unset optional fields became a dict comprehension.

**What carried over unchanged**: every validation, the selector parsing, the address
stripping, the peer sort, and the fixed key order — which is now insertion order plus
`sort_keys=False` rather than the template's line order. Determinism is unaffected and
still asserted at the byte level.

## R2 — Declaring PyYAML

> **⚠️ Reversed with R1.** `pyyaml>=6.0.1` is now a declared dependency in
> `pyproject.toml`.

**Original decision (superseded)**: Use `jinja2`. Do not add PyYAML.

**Rationale as recorded**: Neither is declared in `pyproject.toml`, so both arrive
transitively — but not equally:

```text
jinja2 3.1.6   required by: infrahub-sdk, pyavd, anta, fastapi, ...
pyyaml 6.0.3   required by: pyavd, anta, cvprac, testcontainers, ...
```

`jinja2` is a requirement of **`infrahub-sdk` itself**, which is a declared first-order
dependency of this project and the thing every transform already imports. `pyyaml`
reaches the environment only through `pyavd` and the test stack.

**Why that no longer holds.** The constitution's rule is that a dependency must not be
introduced *outside* `pyproject.toml` — which is precisely the state the repository was
already in, since `generators/generate_avd_device_hostvar.py` imports `yaml` without
declaring it. Declaring `pyyaml` fixes that latent problem rather than creating a new one:
a future `pyavd` that dropped it would otherwise break a generator. The alternative R2
listed as "defensible, and the right one if a second YAML-emitting transform ever wanted a
dumper" is the one taken.

---

## R3 — File layout and naming

**Decision**: `.gql`, generated `*_query.py`, and `.py` all co-located in `transforms/`.
Names all `crossplane_fabric_peering`. (No template, per R1a.)

**Rationale**: The skill's template suggests `queries/[QUERY_PATH].gql`, but AGENTS.md
overrides it for this repository — "GraphQL queries MUST be stored in `.gql` files
co-located with their Python consumers" — and both existing transforms comply:

```text
transforms/avd_anta_catalog.gql
transforms/avd_anta_catalog_query.py      (generated)
transforms/avd_anta_catalog.py
transforms/containerlab_topology.gql
transforms/templates/containerlab_topology.j2
```

The registered names follow the same convention: `.infrahub.yml` registers the query and
the transform under the same snake_case name (`avd_anta_catalog`), and the class sets
`query = "avd_anta_catalog"` to match. The GraphQL *operation* name inside the `.gql`
file is PascalCase (`AvdAntaCatalogQuery`) because the code generator derives its model
class names from it.

So: operation name `CrossplaneFabricPeeringQuery`, registered name
`crossplane_fabric_peering`, class `CrossplaneFabricPeeringTransform`.

**Alternatives considered**: the skill's `queries/` layout — rejected, AGENTS.md and both
precedents disagree with it.

---

## R4 — The artifact target

**Decision**: Target `ServiceFabricPeering` through a `CoreStandardGroup` named
`service_fabric_peerings`.

**Rationale**: An artifact definition's target group members must inherit
`CoreArtifactTarget`. Verified in the generated protocols:

```python
class ServiceFabricPeering(ServiceGeneric, GeneratorTarget, CoreArtifactTarget):
class ServiceFabricApp(ServiceGeneric, GeneratorTarget, CoreArtifactTarget):
class ClusterKubernetes(ClusterGeneric, ClusterGenericComputeUnitNodes, GeneratorTarget):
```

`ClusterKubernetes` is deliberately not an artifact target — spec 010's FR-083 scoped
`CoreArtifactTarget` to the three cluster-delivered service kinds precisely so the
artifact hangs off the ordered intent rather than off a piece of infrastructure.

The group name is not invented here: `specs/010-lab-service-layer-model/contracts/schema-kinds.md`
section 6 already declared `service_fabric_peerings` as the group this artifact would
target. This cycle creates it.

**Alternatives considered**:

- *Add `CoreArtifactTarget` to `ClusterKubernetes`* — rejected. It would make the
  technical layer directly artifact-bearing and blur the layer boundary the previous
  feature exists to draw. It is also a schema change in a transform cycle.
- *Target the cluster's group and render without a service* — same objection, plus there
  is no cluster group and creating one to dodge the layering would be worse.

---

## R5 — Typed query responses

**Decision**: Generate `transforms/crossplane_fabric_peering_query.py` with
`infrahubctl graphql generate-return-types` and parse through it. Never hand-write it.

**Rationale**: Constitution III forbids untyped dictionary access to GraphQL responses in
production code, and AGENTS.md lists the generated `*_query.py` modules as regenerated
artifacts. `avd_anta_catalog` shows the pattern, including the practical detail that
generated class names are long and are worth aliasing at module scope:

```python
parsed = AvdAntaCatalogQuery(**data)
target = parsed.target.edges[0].node if parsed.target.edges else None
```

The transform will do the same: `parsed = CrossplaneFabricPeeringQuery(**data)`, then work
through typed attributes rather than string keys.

**Alternatives considered**: `data["ServiceFabricPeering"]["edges"][0]["node"]` — rejected,
prohibited by the constitution and the exact failure mode typed models exist to prevent.

---

## R6 — Query shape: one round trip, target aliased

**Decision**: A single query, `$name: String!`, with the target aliased `target:` and the
cluster and peerings reached by traversal.

**Rationale**: The artifact definition passes `name: "name__value"`, so the query takes a
`$name` variable. `avd_anta_catalog.gql` establishes the alias convention:

```graphql
query AvdAntaCatalogQuery($name: String!) {
  target: DcimDevice(name__value: $name) { edges { node { ... } } }
```

Aliasing to `target` keeps the transform readable and decouples it from the target's kind.
Everything needed is reachable from the service in one traversal — `cluster` gives the
ASN, secret name, timers, communities and selectors; `peerings` gives each peer's name,
ASN, device and address — so there is no reason for a second query.

Note `containerlab_topology` does issue a second query
(`containerlab_link_endpoints.gql`) for batched endpoint resolution. That is a genuinely
different situation: it resolves many links whose endpoints cannot be reached in one
traversal. Nothing here needs it.

**Alternatives considered**: separate queries for the cluster and the peerings — rejected,
one traversal reaches both and two queries would need reconciling.

---

## R7 — Determinism

**Decision**: Sort peers by peering name; fix the manifest's key order by construction;
render one YAML document.

**Rationale**: SC-004 requires byte-identical output for an unchanged model, and the
artifact's checksum is what tells an operator whether anything changed. Two sources of
non-determinism have to be closed:

1. **Relationship ordering.** `ClusterFabricPeering` declares
   `order_by: [name__value]`, so the graph already returns them ordered — but relying on
   that implicitly is fragile, so the transform sorts explicitly. Belt and braces, and it
   makes the unit test meaningful without a server.
2. **Mapping key order.** Building the dict in XRD order fixes key order by construction, which is one of the
   quiet advantages of R1's hybrid approach over a dumper that needs `sort_keys=False`
   passed correctly.

**Alternatives considered**: relying on the schema's `order_by` alone — rejected, an
implicit guarantee that a future schema edit could remove silently.

---

## R8 — The two real transformations

**Decision**: Parse `key=value` selector strings into label maps; strip the prefix length
from peer addresses.

**Rationale**: Both exist because of decisions taken upstream of this cycle.

**Selectors.** They are stored as `List` of `key=value` rather than a JSON map because
Infrahub 1.10.6 returns a 500 for a JSON attribute key containing a dot or a slash, and
every Kubernetes label selector looks like `nfd41.lab/bgp`. Recorded in
`schemas/MARKETPLACE.md`. The lab's XRD wants a real map:

```yaml
nodeSelector:
  nfd41.lab/bgp: "true"
```

so the transform splits on the first `=` only — a value may legitimately contain one —
and raises on a string with no `=` at all. `opsmill/infrahub-dogfooding` solves the same
problem the same way in its AWS transform's `_labels_to_map`, including raising on a
malformed entry.

**Addresses.** `ClusterFabricPeering.peer_address` points at an `IpamIPAddress`, whose
value carries the mask (`10.110.0.2/24`). A BGP neighbour address must not:

```yaml
peers:
  - name: k8s-leaf1
    address: 10.110.0.2
```

**Alternatives considered**:

- *Store selectors pre-parsed* — impossible, that is the server bug being worked around.
- *Store a separate mask-free address attribute* — rejected, it would duplicate a fact the
  IPAM object already holds and could drift from it.

---

## R9 — Testing strategy

**Decision**: Unit tests over fixture dictionaries, mirroring
`tests/unit/test_avd_anta_catalog.py` and `tests/unit/test_containerlab_topology.py`.
End-to-end via `infrahubctl transform` and a Kubernetes dry-run.

**Rationale**: The repository already tests transforms without a server by constructing
the query response as a dictionary and calling the transform directly. That is what makes
the error paths in FR-017 testable at all — you cannot easily produce a cluster with no
`local_asn` in a live database without breaking the schema's own constraints, but you can
hand a transform a fixture that omits it.

The unit tests cover: selector parsing including the malformed case, address stripping,
peer ordering, disabled-peering omission, all three FR-017 errors, and that the rendered
output parses as YAML with the expected `apiVersion` and `kind`.

The live render adds what fixtures cannot: proof that the query is valid against the real
schema and that the real data produces the real manifest.

**Alternatives considered**: integration-test-only coverage — rejected, it cannot reach
the error paths and it is unavailable in this environment anyway (see the plan's
Complexity Tracking).

---

## R10 — Failure behaviour

**Decision**: Raise `ValueError` naming the object and the missing field. Do not emit a
partial manifest.

**Rationale**: The lab's own commentary is the argument. A BGP contract that is half
configured "either does not come up, or comes up and carries nothing", and the XRD's
comments note that each such failure "looks like a different problem". A renderer that
emits a manifest with an empty `peers` list produces a resource that applies cleanly,
reports healthy, and carries no routes — the worst available outcome.

`src/solution_arista_avd/avd.py` sets the precedent for the shape:

```python
msg = f"Unknown device role: {role}"
raise ValueError(msg)
```

Three conditions raise: no `local_asn` on the cluster, no enabled peerings on the service,
and a peering with no `peer_address`. Each message names the object and the field.

Deliberately *not* an error: a `provisioning` service status. Whether to apply a rendered
manifest is an operator's decision, not a renderer's, and refusing to render an
un-activated service would make the artifact useless for review before activation.

**Alternatives considered**:

- *Emit a comment marker instead of raising*, as `avd_anta_catalog` does for a
  fabric with ANTA disabled — rejected. That case is a deliberate opt-out; these are
  incomplete models, and silence would hide them.

---

## Resolved risks

| Risk | Resolution |
| --- | --- |
| Spec's pure-Python approach adds an undeclared dependency | R1a and R2 — pure Python, with `pyyaml` declared, which also fixes an existing undeclared import in a generator |
| Nothing to attach the artifact to | R4 — `ServiceFabricPeering` is already a `CoreArtifactTarget`; one seed object and the group declared by cycle 010 |
| Artifact checksum churning on an unchanged model | R7 — explicit sort plus insertion-order keys and `sort_keys=False` |
| Selector keys unusable as stored | R8 — parse `key=value`, the same split `infrahub-dogfooding` uses |
| A prefix reaching a BGP neighbour field | R8 — strip the mask; the unit test asserts it |
| An incomplete model rendering a manifest that applies and carries nothing | R10 — raise, naming the object and field |
| Untyped GraphQL access | R5 — generated Pydantic models, as `avd_anta_catalog` does |
