# Transform Specification: Crossplane FabricPeering Manifest

**Feature Branch**: `nfd41-fabric-model`
**Created**: 2026-09-10
**Status**: Draft
**Input**: User description: "proceed on the next task" — the transform cycle deferred by `specs/010-lab-service-layer-model`, which is what the original request ("start generating the crossplane configuration in Infrahub") was driving at.

## Context

`specs/010-lab-service-layer-model` built the data model and this session loaded the
technical layer into Infrahub. What does not exist yet is anything that turns that data
back into configuration. The lab still holds its Crossplane inputs as hand-maintained
YAML in `../lab/crossplane/platform/10-peering.yaml`.

The cluster's BGP contract with the fabric is now fully modelled, and it was verified
against the live graph:

```text
nfd41  ASN 65401  cilium 1.18.6
node_selector: ['nfd41.lab/bgp=true']
pod CIDR 10.111.0.0/16   VIP pool ['10.112.240.0/24']
members: ['k8s-node1', 'k8s-node2', 'k8s-node3']
peering k8s-leaf1  -> leaf-nfd41-pod1-1-1    10.110.0.2/24    AS 65101
peering k8s-leaf2  -> leaf-nfd41-pod1-1-2    10.110.0.3/24    AS 65101
```

Every field the lab's `FabricPeering` composite resource consumes is in there. So this
transform is unblocked today, and it closes the loop the feature was built for: change
the model, re-render, review the diff, push.

### Why this one first

Of the five cycles deferred by 010, this is the only one whose inputs are already
loaded. The application manifest (`FabricApp`) needs service-layer objects that were
deliberately not loaded; the FRR and Junos renderers are larger; the generator cycle
inverts the flow. Rendering `FabricPeering` proves the whole path — model to artifact —
on the smallest complete example.

## Transform Type

- **Approach**: Python
- **Output Format**: YAML (a Kubernetes custom resource; `application/yaml`)
- **Target Nodes**: `ServiceFabricPeering`

**Why Python rather than Jinja2.** The output is a Kubernetes resource whose shape is
mostly nested mappings and lists, and two fields need real logic rather than
substitution: the `key=value` selector lists have to be parsed back into label maps, and
each peer's address has to have its prefix length stripped. Emitting it through
a YAML dumper from a dict guarantees valid YAML and correct quoting, which a template has
to be careful about by hand. The repository's `containerlab_topology` transform is hybrid
rather than pure Python, but its output is a topology file for another tool rather than a
structured API resource; the `infrahub-managing-transforms` skill puts structured output
under Python and text output that mirrors a template under Jinja2.

**Why `ServiceFabricPeering` is the target.** Spec 010's FR-083 made the three
cluster-delivered service kinds `CoreArtifactTarget`s for exactly this, and
`ClusterKubernetes` is deliberately not one. The service supplies the artifact's identity
and the thing an operator ordered; every rendered *value* comes from the technical layer
beneath it, which keeps 010's rule that renderers read technical objects.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Render the peering manifest from the model (Priority: P1)

An operator changes the cluster's BGP settings in Infrahub — adds a community, retimes a
session, corrects a peer address — and gets back the exact `FabricPeering` resource the
lab's Crossplane composition consumes, without editing YAML by hand.

**Why this priority**: This is the feature. Everything else in this spec is a property of
this one rendering.

**Independent Test**: `uv run infrahubctl transform crossplane_fabric_peering name=<service>`
prints a `FabricPeering` resource, and `kubectl apply --dry-run=client -f -` accepts it.
Diffing it against `../lab/crossplane/platform/10-peering.yaml` shows only differences
that are deliberate and explained.

**Acceptance Scenarios**:

1. **Given** the loaded cluster and its two peerings, **When** the transform runs, **Then** it emits one `FabricPeering` resource carrying the cluster's local ASN, both peers with their names, addresses and ASNs, the auth secret name, the timers, the pod-CIDR communities and both selectors
2. **Given** a peer address stored as `10.110.0.2/24`, **When** it is rendered, **Then** the manifest carries `10.110.0.2` — a BGP neighbour address, not a prefix
3. **Given** a selector stored as `nfd41.lab/bgp=true`, **When** it is rendered, **Then** the manifest carries the label map `{nfd41.lab/bgp: "true"}`
4. **Given** two peerings, **When** they are rendered, **Then** they appear in a deterministic order so an unchanged model produces a byte-identical artifact
5. **Given** a peering marked disabled, **When** the transform runs, **Then** it is omitted from `peers`

---

### User Story 2 - Store it as an artifact the cluster can pull (Priority: P2)

The rendered manifest is attached to its service as an Infrahub artifact, so an
in-cluster operator can fetch it rather than someone copying YAML into a repository.

**Why this priority**: Rendering on demand is useful; rendering into a durable, versioned
artifact is what makes Infrahub the source of truth. Depends on US1.

**Independent Test**: After a repository sync and artifact generation, the artifact exists
against the `ServiceFabricPeering` object with content type `application/yaml`, and
fetching it returns the same bytes the transform prints.

**Acceptance Scenarios**:

1. **Given** the transform and artifact definition are registered, **When** the repository syncs, **Then** the transform, its query and the artifact definition are all accepted with no error
2. **Given** a `ServiceFabricPeering` object in the target group, **When** artifacts are generated, **Then** an artifact is produced against it
3. **Given** the model is unchanged, **When** artifacts are regenerated, **Then** the artifact's checksum is unchanged
4. **Given** a value changes in the cluster, **When** artifacts are regenerated, **Then** the artifact changes and the previous version remains available for diffing

---

### User Story 3 - Fail loudly on an incomplete model (Priority: P3)

A model that cannot produce a working manifest fails at render time with a message naming
what is missing, rather than emitting a resource that applies cleanly and carries nothing.

**Why this priority**: The lab's own notes are emphatic that a BGP contract half-configured
"comes up and carries nothing", and that each such failure looks like a different problem.
A renderer that hides an incomplete model recreates exactly that.

**Independent Test**: Render a service whose cluster has no `local_asn` and confirm the
transform raises with a message naming the cluster and the missing field.

**Acceptance Scenarios**:

1. **Given** a cluster with no `local_asn`, **When** the transform runs, **Then** it raises an error naming the cluster and the field, because a session with no local AS cannot come up
2. **Given** a service with no peerings, **When** the transform runs, **Then** it raises rather than emitting an empty `peers` list
3. **Given** a peering whose `peer_address` is missing, **When** the transform runs, **Then** it raises naming that peering

---

### Edge Cases

- What happens when a selector string has no `=`, or has more than one?
- What happens when two peerings resolve to the same peer address — the MLAG VARP-gateway mistake the schema's mandatory cardinality-one relationships exist to prevent?
- What happens when the cluster's `bgp_timers` JSON carries keys the composition does not know?
- What happens when a peering's `peer_device` has been decommissioned but the peering remains?
- How does the artifact behave when the service is renamed — new artifact, or the same one moved?
- What happens when `pod_cidr_communities` is empty rather than absent?
- What happens when the same cluster is referenced by two `ServiceFabricPeering` objects?

## Requirements *(mandatory)*

### Functional Requirements

#### GraphQL Query

- **FR-001**: A GraphQL query MUST be created at `transforms/crossplane_fabric_peering.gql` retrieving everything the manifest needs in one round trip
- **FR-002**: The query MUST accept a `$name: String!` parameter matching the artifact definition's `name: name__value`
- **FR-003**: The query MUST retrieve, from `ServiceFabricPeering`: its own `name`, `status`, `communities` and `advertisement_selector`
- **FR-004**: The query MUST traverse to the related `ClusterKubernetes` and retrieve `name`, `local_asn`, `bgp_auth_secret_name`, `bgp_timers`, `pod_cidr_communities`, `node_selector` and `advertisement_selector`
- **FR-005**: The query MUST traverse to each `ClusterFabricPeering` and retrieve `name`, `peer_asn`, `enabled`, the `peer_device` name and the `peer_address` value
- **FR-006**: A generated Pydantic return-type module MUST be produced with `infrahubctl graphql generate-return-types` and used in the transform, per the project's type-safety rules; it MUST NOT be hand-written

#### Transform Logic

- **FR-010**: The transform MUST be a Python class inheriting `InfrahubTransform`, in `transforms/crossplane_fabric_peering.py`
- **FR-011**: The transform MUST set `query = "crossplane_fabric_peering"`
- **FR-012**: The transform MUST return a `str` containing a single YAML document — a `FabricPeering` resource with `apiVersion`, `kind`, `metadata.name` and `spec`
- **FR-013**: The transform MUST parse each `key=value` selector string into a label map, and MUST raise on a string containing no `=`
- **FR-014**: The transform MUST strip the prefix length from each peer address, so a BGP neighbour is `10.110.0.2` rather than `10.110.0.2/24`
- **FR-015**: The transform MUST order `peers` deterministically by peering name, so an unchanged model renders byte-identically
- **FR-016**: The transform MUST omit peerings whose `enabled` is false
- **FR-017**: The transform MUST raise a descriptive error naming the object and field when the cluster has no `local_asn`, when the service has no enabled peerings, or when a peering has no `peer_address`
- **FR-018**: The transform MUST omit optional spec fields that have no value rather than emitting empty or null ones, so the composition's own defaults apply
- **FR-019**: The transform MUST NOT emit the BGP session password — only the name of the secret holding it

#### Artifact & Registration

- **FR-020**: The query MUST be registered in `.infrahub.yml` under `queries`
- **FR-021**: The transform MUST be registered in `.infrahub.yml` under `python_transforms`
- **FR-022**: An artifact definition MUST be registered with `content_type: "application/yaml"`, matching the repository's existing convention for YAML artifacts
- **FR-023**: The artifact definition MUST target a `CoreStandardGroup` whose members are `ServiceFabricPeering` objects, and that group MUST be added to `objects/00_groups.yml`
- **FR-024**: The artifact definition MUST map `name: "name__value"`

#### Seed Data

- **FR-030**: One `ServiceFabricPeering` object MUST be loaded so the transform has a target. It is the minimum service-layer data this cycle requires, and nothing else from the service layer is loaded
- **FR-031**: That object MUST reference the existing `nfd41` cluster and both existing `ClusterFabricPeering` objects, and MUST have an owner
- **FR-032**: Loading it MUST remain idempotent across repeated runs

#### Testing

- **FR-040**: Unit tests MUST cover the selector parsing, the address stripping, the deterministic ordering, the disabled-peering omission and every error in FR-017, using fixture data rather than a live server
- **FR-041**: A test MUST assert the rendered output parses as YAML and carries the expected `apiVersion` and `kind`

### Key Files

| File | Purpose |
|------|---------|
| `transforms/crossplane_fabric_peering.gql` | GraphQL query |
| `transforms/crossplane_fabric_peering_query.py` | Generated Pydantic return types — regenerated, never hand-written |
| `transforms/crossplane_fabric_peering.py` | The transform class |
| `.infrahub.yml` | Query, transform and artifact-definition registration |
| `objects/00_groups.yml` | The target group |
| `objects/35_nfd41_peering_service.yml` | The one seed `ServiceFabricPeering` |
| `tests/unit/test_crossplane_fabric_peering.py` | Unit tests over fixture data |

### Key Entities

- **`ServiceFabricPeering`**: the artifact target and the ordered intent — "this cluster peers with the fabric". Supplies the artifact's identity, its owner and its status; contributes communities and an advertisement selector.
- **`ClusterKubernetes`**: where every rendered value comes from — local ASN, the auth secret's name, timers, pod-CIDR communities, and both selectors.
- **`ClusterFabricPeering`**: one per fabric leaf, supplying a peer's name, address and ASN. The schema's mandatory cardinality-one `peer_device` and `peer_address` are what stop a shared VARP gateway being recorded in place of a leaf's own SVI address.
- **Rendered artifact**: one `FabricPeering` custom resource per peering service, in YAML.

## Assumptions

1. **The manifest shape is the lab's existing XRD.** `../lab/crossplane/platform/00-xrd-fabric-peering.yaml` defines `FabricPeering` in group `nfd41.lab`, version `v1alpha1`, cluster-scoped. The transform renders to that contract; the composition is not changed. Spec 010's Out of Scope already fixed this ("Infrahub renders their inputs; the compositions stay where they are").
2. **One service, one manifest.** The XRD is cluster-scoped and the lab has exactly one of these per cluster, so a per-service artifact is the right granularity.
3. **Delivery is out of scope here.** Spec 010 assumption 9 settled that artifacts reach the cluster through the Vidra operator. This cycle produces the artifact; wiring the operator is separate.
4. **Selectors are `key=value` lists.** Not a style choice: Infrahub 1.10.6 returns a 500 for a JSON attribute key containing a dot or a slash, which every Kubernetes label selector has. The workaround is recorded in `schemas/MARKETPLACE.md`, and parsing them back is the transform's job — the same split `opsmill/infrahub-dogfooding` uses.
5. **`bgp_timers` passes through as-is.** Its keys are already the composition's field names and contain no dots, so it needs no translation.
6. **The status field does not gate rendering.** A `provisioning` service still renders; whether to apply the result is the operator's decision, not the renderer's.

## Out of Scope

- The `FabricApp` and `AppAccess` manifests. Both need service-layer objects that were deliberately not loaded, and `FabricApp` additionally depends on `manifests` and `chart_values`, which are JSON attributes that will hit the dotted-key server bug described in `schemas/MARKETPLACE.md`.
- Rendering FRR configuration for the ISP, CE and branch routers, and Junos configuration for the firewall. Both are larger and independent.
- Any generator. This cycle reads the model; nothing writes to it.
- Applying the artifact to the cluster, and the Vidra operator's own configuration.
- Any change to the lab's Crossplane compositions or XRDs.
- Any change to the AVD pipeline or the EOS rendering path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The transform runs against the loaded model and prints a `FabricPeering` resource with no error
- **SC-002**: The rendered manifest is accepted by a client-side Kubernetes dry-run against the lab's XRD
- **SC-003**: Every field the lab's `FabricPeering` composition consumes appears in the rendered output, verified field by field against `../lab/crossplane/platform/10-peering.yaml`; any difference is deliberate and recorded
- **SC-004**: Rendering the same unchanged model twice produces byte-identical output
- **SC-005**: Changing one value in Infrahub changes exactly the corresponding line of the rendered manifest
- **SC-006**: An incomplete model produces an error naming the object and the missing field, never a manifest that applies cleanly and carries nothing
- **SC-007**: No rendered output contains a password or secret value
- **SC-008**: `uv run pytest tests/unit` passes, including the new tests
- **SC-009**: `uv run invoke lint` passes on the ruff, yamllint, mypy and rumdl gates
- **SC-010**: The repository syncs with the new query, transform and artifact definition registered, and an artifact is generated against the seeded service
- **SC-011**: Loading the seed object twice leaves one `ServiceFabricPeering` and produces no uniqueness violation
