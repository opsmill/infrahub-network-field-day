# Schema Design Specification: Fabric Application as a Helm Chart

> **This is a schema design spec.** The implementing agent MUST use the `infrahub-managing-schemas` skill to build and validate all schema definitions.

**Feature Branch**: `033-fabricapp-helm-chart`
**Created**: 2026-09-18
**Status**: Draft
**Input**: User description: "lets alter the fabricapplication to use helm charts instead of manifests specifying a chart and maybe some values"

## Schema Files

All schema definitions live in `schemas/*.yml`. Each file must start with:

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"
```

The kinds in scope live in `schemas/service/kubernetes_services.yml`.

---

## Context

`ServiceFabricApp` today offers **two ways to say what an application is**, and
they are not alternatives so much as an unresolved choice:

- a Helm chart — `chart_repository`, `chart_name`, `chart_version`, plus values
  as either the inline `chart_values` attribute or an attached
  `ServiceFabricAppValuesFile`; and
- raw Kubernetes API objects — the inline `manifests` attribute or an attached
  `ServiceFabricAppManifestsFile`.

Every one of those six fields is optional. The renderer decides which path an
application took by looking at what happens to be populated, and refuses only
when **both** are empty. The one seeded application, `nfd41-demo`, takes the
manifests path: a 4.4 KB payload file carrying two Deployments, two Services and
two network policies, which is a hand-written copy of a Kubernetes deployment
rather than a statement of intent.

This feature makes the chart the **only** way an application is expressed. A
requester names a chart and supplies values; nobody transcribes Kubernetes API
objects into Infrahub.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A chart is the whole workload source (Priority: P1)

An application owner describes their workload by naming a chart repository, a
chart, and a version, and optionally supplying values. There is no second way to
describe a workload, and no combination of populated fields the model accepts
but the delivery path cannot honour.

**Why this priority**: This is the feature. Every other story is a consequence of
it, and none of them is worth doing on its own.

**Independent Test**: Load the schema on a branch and create a
`ServiceFabricApp` naming only a cluster, a namespace and the three chart
fields. It is accepted. Create one naming no chart fields; it is rejected by the
model rather than by a downstream renderer.

**Acceptance Scenarios**:

1. **Given** the schema is loaded, **When** an application is created naming a
   chart repository, chart name and chart version, **Then** it is accepted with
   no values supplied.
2. **Given** the schema is loaded, **When** an application is created with no
   chart repository, chart name or chart version, **Then** the create is refused
   because those fields are mandatory.
3. **Given** an application with a chart, **When** values are supplied as an
   attached file and as the inline attribute at the same time, **Then** both are
   accepted by the model and the attached file is documented as taking
   precedence.

---

### User Story 2 - Raw manifests leave the model (Priority: P1)

The `manifests` attribute, the `manifests_file` relationship and the
`ServiceFabricAppManifestsFile` kind are retired. An application cannot be
expressed as raw API objects, and nothing in the graph is left pointing at a
kind that no longer exists.

**Why this priority**: Leaving the manifests path in place while calling the
chart mandatory produces the worst of both — two documented ways to describe a
workload, one of which is now unreachable, and an orphaned file kind whose
parent relationship still resolves.

**Independent Test**: Load the schema on a branch and confirm the retired
attribute, relationship and kind are absent from the loaded schema, and that the
attached manifests file previously held by `nfd41-demo` is gone rather than
orphaned.

**Acceptance Scenarios**:

1. **Given** the schema is loaded, **When** the `ServiceFabricApp` kind is
   inspected, **Then** it has no `manifests` attribute and no `manifests_file`
   relationship.
2. **Given** the schema is loaded, **When** the schema is listed, **Then**
   `ServiceFabricAppManifestsFile` is not present.
3. **Given** an application that previously carried an attached manifests file,
   **When** the schema change is loaded, **Then** the removal is performed by
   the schema's documented removal mechanism and leaves no file object whose
   parent relationship is undefined.

---

### User Story 3 - An exposed application names the services its VIP answers on (Priority: P1)

An exposed application relates to the `SecurityService` objects describing the
ports its VIP answers on — `junos-http` for 80, `junos-https` for 443. Access
grants read that relationship instead of reading the application's manifests.

**Why this priority**: Without it this feature silently breaks the firewall path.
`generate-app-access` derives a grant's destination ports today by reading the
application's manifests for `LoadBalancer` Services and taking each one's
`spec.ports[].port`, and it deliberately **refuses rather than guessing** when it
finds none. A chart's Services exist only once the chart is rendered inside the
cluster, which Infrahub cannot do — so after this change every grant against
every application would refuse, and the only application in the lab would become
unreachable through the portal.

**Why a relationship rather than a list of port numbers**: the invariant the
manifests derivation exists to protect is that **one object decides both the
VIP's port and the firewall rule's**. A port number copied into an attribute
re-opens the gap that derivation closed — the two can disagree again, and the
symptom is a healthy application nobody can reach. A relationship keeps it to one
object literally: the rule's `destination_services` is the very object the
application named. Three further things then fall out rather than having to be
arranged:

- **Adoption stops being a derivation.** `index_tcp_services` exists to key
  adoption on `(protocol, port)` so that a grant for 443 references the
  firewall's own `junos-https` instead of declaring a second application for the
  same port. If the application *names* `junos-https`, there is nothing to
  match — the generator uses the named object.
- **Revocation stays safe by construction.** A named service is never created by
  the generator, so it is never marked `managed_by_service`, so revoking the
  grant never deletes it. That is today's rule for `junos-https`, holding because
  of what the object is rather than because of a name comparison.
- **The seeded data already agrees.** `junos-http` is `port: 80,
  ip_protocol: tcp` and `nfd41-demo`'s frontend Service is `port: 80,
  type: LoadBalancer`, so the demo application names an object that already
  exists and the rendered firewall rule does not move.

**Independent Test**: Load the schema on a branch and confirm an exposed
application can name one or more existing `SecurityService` objects, and that an
application naming `junos-http` is distinguishable from one naming nothing.

**Acceptance Scenarios**:

1. **Given** an exposed application, **When** it is related to the existing
   `junos-http` service object, **Then** that relationship is readable from the
   application without fetching any payload and without consulting the cluster.
2. **Given** an application that is not exposed, **When** it is created naming no
   services, **Then** it is accepted.
3. **Given** an exposed application naming no services, **Then** the state is
   detectable — a consumer can tell "none named" from "named and empty", and can
   refuse rather than guess.
4. **Given** an application naming a service the firewall already declares,
   **When** the relationship is set, **Then** the service object is neither
   renamed nor marked as owned by any service.

---

### User Story 4 - The seeded application is a chart (Priority: P2)

`nfd41-demo` is expressed as a chart in the seed data, so a freshly bootstrapped
instance demonstrates the only supported shape rather than a retired one.

**Why this priority**: The seed data is the worked example. It is also the thing
that proves the model is usable — a schema that permits only charts and ships an
application that is not one has not been tested. Lower than P1 because the
schema is correct without it and the object change lands in the Objects cycle
that follows.

**Independent Test**: Load the seed data on a branch and confirm `nfd41-demo`
carries a chart repository, name and version, and no manifests.

**Acceptance Scenarios**:

1. **Given** a fresh load, **When** `nfd41-demo` is read, **Then** it names a
   chart and carries no manifests payload.
2. **Given** a fresh load, **When** the application's artifact is rendered,
   **Then** it renders without raising.

---

### Edge Cases

- An application naming a chart name and repository but **no version**. The
  downstream Crossplane definition requires all three together, so a
  two-of-three chart is a rendered resource the cluster rejects. The model must
  refuse it rather than pass it on.
- Values supplied both inline and as an attached file. Both remain valid; the
  precedence rule (attachment wins) is unchanged and must stay documented, since
  it is the only thing distinguishing the two.
- An existing application object carrying manifests when the new mandatory chart
  fields arrive. Making an attribute mandatory on populated data fails unless the
  data is migrated or a default is supplied; the migration order is part of this
  feature, not an afterthought.
- An application whose chart is correct but which is exposed while naming no
  services. Nothing downstream can invent them, so this must be detectable
  rather than rendering a grant that permits nothing or everything.
- An application naming a service the firewall's hand-written rules also use —
  `junos-http`, which four baseline rules reference. Relating to it must not
  change it, and revoking a grant that used it must not delete it.
- An application naming a service object that no firewall policy has ever
  referenced. The object exists in the graph and simply has no rule yet; that is
  the ordinary case for a new port and must not be treated as an error.
- An application naming a service whose protocol is not TCP. Permitted, because
  the named object carries its own protocol — but it changes what a generated
  rule covers, so it is a behaviour change rather than a widening by accident.
- A `SecurityService` deleted while an application still names it. The
  relationship takes no action on delete, so the application is left naming
  nothing where it named something; this is detectable and belongs to a check
  rather than to a schema constraint.
- A values payload whose keys contain dots or slashes — `grafana.ini`,
  `app.kubernetes.io/name`. The inline JSON attribute cannot be seeded with
  these (the object-load path returns HTTP 500), which is the reason the
  attached file exists and the reason it cannot be removed alongside the
  manifests file.
- An application that genuinely has no chart. Workloads exist with no published
  chart, and this feature removes their escape hatch. That exclusion is
  deliberate and must be stated, not discovered.

## Requirements *(mandatory)*

### Functional Requirements

#### Nodes & Generics

- **FR-001**: `ServiceFabricApp` MUST remain the single kind describing an
  application, under the existing `Service` namespace, with its existing
  inheritance (`ServiceGeneric`, `GeneratorTarget`, `CoreArtifactTarget`)
  unchanged.
- **FR-002**: `ServiceFabricAppValuesFile` MUST be retained unchanged as the
  attachment carrying Helm values.
- **FR-003**: `ServiceFabricAppManifestsFile` MUST be removed from the schema.
- **FR-004**: No new node or generic is introduced by this feature.

#### Attributes

- **FR-010**: `chart_repository` MUST become mandatory on `ServiceFabricApp`.
- **FR-011**: `chart_name` MUST become mandatory on `ServiceFabricApp`.
- **FR-012**: `chart_version` MUST become mandatory on `ServiceFabricApp`.
- **FR-013**: `chart_values` MUST remain an optional JSON attribute, retained as
  the inline escape hatch for values small enough not to need a file.
- **FR-014**: The `manifests` attribute MUST be removed using the schema's
  documented attribute-removal mechanism (`state: absent`) rather than being
  deleted from the YAML.
- **FR-015**: Attribute `order_weight` values MUST keep the chart fields
  contiguous and ahead of the exposure and policy blocks; the weight freed by
  the removed `manifests` attribute MUST NOT be reused by an unrelated field.
- **FR-016**: All attribute names MUST remain snake_case and all kinds MUST
  remain valid non-deprecated kinds.
- **FR-017**: No attribute is added to `ServiceFabricApp` by this feature. The
  ports an exposed application answers on are modelled as a relationship — see
  FR-024 — rather than copied into an attribute.

#### Relationships

- **FR-020**: The `manifests_file` relationship on `ServiceFabricApp` MUST be
  removed, together with its `fabricapp__manifests_file` identifier.
- **FR-021**: The `values_file` relationship MUST be retained as
  `kind: Component`, `cardinality: one`, optional, with its existing
  `fabricapp__values_file` identifier and its matching `Parent` side on
  `ServiceFabricAppValuesFile` unchanged.
- **FR-022**: No relationship may be left with an identifier whose counterpart
  kind has been removed.
- **FR-023**: All other relationships on `ServiceFabricApp` (`cluster`, `vrf`,
  `vip_block`, `allowed_source_prefixes`, `peering_service`) are unchanged.
- **FR-024**: `ServiceFabricApp` MUST gain a relationship naming the
  `SecurityService` objects its VIP answers on: peer `SecurityService`,
  `cardinality: many`, optional, a plain reference rather than ownership, with
  `on_delete: no-action` and its own identifier following the existing
  `service__app_*` convention. It mirrors `allowed_source_prefixes`, which is
  the other relationship on this kind that names technical objects the
  application does not own.
- **FR-025**: The relationship MUST distinguish "none named" from "named and
  empty", so a consumer that must refuse rather than guess can tell which it is
  looking at.
- **FR-026**: Relating to a service object MUST NOT modify it — not its name, not
  its description, and not any ownership marker. The firewall's own `junos-http`
  and `junos-https` are referenced by applications and stay owned by the
  hand-maintained baseline.
- **FR-027**: The peer MUST be `SecurityService` specifically, not the
  `SecurityGenericService` generic. `SecurityServiceRange` and
  `SecurityServiceGroup` also inherit that generic, and neither has a single
  port; admitting them would give the access generator a port list it cannot
  resolve to integers. Naming a range is a separate feature with its own case.
- **FR-028**: The relationship MUST be permitted to name services of any
  protocol the `SecurityService` kind admits, not TCP alone. The existing
  manifests derivation skips non-TCP because it cannot tell an advertised UDP
  port from an incidental one; a named object carries its own protocol and
  removes that ambiguity.

#### Display & Identification

- **FR-030**: `human_friendly_id`, `display_label`, `order_by` and the name
  uniqueness constraint MUST continue to be inherited from `ServiceGeneric`; this
  feature introduces no local overrides.
- **FR-031**: Field descriptions MUST state the precedence rule between the
  inline values attribute and the attached values file, since removing the
  manifests pair removes the only other place that rule is written down.

#### Migration

- **FR-040**: The three chart fields MUST be made mandatory in an order that does
  not fail against existing populated data: either the seed data supplies them
  before the tightening, or they are introduced with a default and tightened
  afterwards. The chosen order MUST be stated in the plan.
- **FR-041**: Removed attributes and the removed node kind MUST use
  `state: absent` rather than being deleted from the YAML.
- **FR-042**: The manifests payload attached to `nfd41-demo` MUST be removed
  along with its kind, and the seeding step that uploads it MUST stop referencing
  a kind that no longer exists.

### Key Entities

- **ServiceFabricApp**: An application that participates in the fabric. After
  this change its workload source is a Helm chart and nothing else: a chart
  repository, chart name and chart version, all mandatory, plus optional values
  held inline or as an attachment. It keeps its namespace, exposure, VIP block,
  network-policy and source-prefix fields unchanged, and gains a relationship
  naming the services its VIP answers on.
- **ServiceFabricAppValuesFile**: Helm values as an attached file, parented to
  exactly one application. Unchanged, and now the only payload attachment a
  fabric application has.
- **ServiceFabricAppManifestsFile**: Retired. Raw Kubernetes API objects are no
  longer a way to describe an application.
- **SecurityService**: An existing technical kind — one name, one port, one IP
  protocol — already carrying the firewall's own `junos-http`, `junos-https` and
  `junos-ping`, and already the thing a `SecurityPolicyRule` names as its
  destination. **Unchanged by this feature**; it gains an incoming reference and
  nothing else. It is the object that makes the application's advertised port
  and the firewall rule's permitted port the same object rather than two numbers
  that have to agree.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `infrahubctl schema check schemas/` passes with zero validation
  errors.
- **SC-002**: An application created with a chart repository, chart name and
  chart version and nothing else is accepted; one created without all three is
  refused by the model.
- **SC-003**: The loaded schema contains no `manifests` attribute, no
  `manifests_file` relationship, and no `ServiceFabricAppManifestsFile` kind.
- **SC-004**: No file object remains in the graph whose parent kind has been
  removed.
- **SC-005**: An exposed application's advertised services are readable from the
  application object alone, with no payload fetched and no cluster consulted,
  and each resolves to a port and a protocol.
- **SC-006**: A fresh bootstrap produces an `nfd41-demo` that names a chart, and
  its rendered artifact is produced without raising.
- **SC-007**: The existing schema-contract test asserting that an application's
  workload source may be a chart, manifests, or both is updated to assert the
  single supported source, and passes.
- **SC-008**: Relating `nfd41-demo` to the existing `junos-http` object leaves
  that object byte-identical — same name, same description, same ownership — and
  the firewall artifact rendered for a grant using it is unchanged from the
  manifests-derived one.

## Assumptions

- The downstream Crossplane composite definition already accepts a chart and
  requires `repository`, `name` and `version` together when one is present. That
  definition belongs to the sibling lab repository and is **not** changed by this
  feature; making the three fields mandatory here brings Infrahub's model into
  line with a constraint that already exists downstream.
- The composite definition keeps its optional `manifests` field. Infrahub simply
  stops emitting it. No lab-side change is required for the removal.
- Values must remain available as an attachment: a JSON attribute whose keys
  contain dots or slashes cannot be seeded through the object-load path, and real
  Helm values are full of both.
- `nfd41-demo`'s two workloads are a published upstream image with a chart
  available, so expressing it as a chart is a matter of naming one rather than
  authoring one.
- A service kind referencing a technical kind is the permitted direction here:
  `ServiceFabricApp` already names `IpamPrefix`, `IpamVRF` and
  `ClusterKubernetes`, and nothing in the technical layer references back. Naming
  `SecurityService` follows that, and does not make the Kubernetes model depend
  on a firewall being present — an application that names no services is valid.
- The seeded `junos-http` (`port: 80, ip_protocol: tcp`) is the object
  `nfd41-demo` needs, so User Story 3 introduces no new security object and the
  rendered firewall configuration does not move.
- This cycle delivers the schema. The renderer, the two portals, the access
  generator and the seed data follow in the Transform, Generator and Objects
  cycles the routing chain names.

## Dependencies & Downstream Impact

Named here because the schema change makes each of them fail rather than degrade:

- **`crossplane_fabric_app`** decides between a chart and manifests and raises
  only when both are missing. It must render the chart path unconditionally.
- **`generate-app-access`** derives grant ports from the manifests and refuses
  when it finds no advertised Service. It must read the application's named
  services instead; see User Story 3. Three of its parts get simpler rather than
  merely different: `advertised_service_ports` and `_selector_labels` have
  nothing left to parse, `index_tcp_services` has nothing left to adopt for a
  default grant, and `_upsert_services` creates objects only for a grant that
  names ports its application did not.
- **`scripts/seed_app_payloads.py`** uploads the demo manifests into a kind that
  will no longer exist.
- **The Backstage portal** offers a manifests textarea and attaches it with a
  file-upload step; that field goes, the values field stays.
- **The Streamlit application page** collects the same payload.
- **`objects/36_nfd41_app_services.yml`** and `payloads/nfd41-demo-manifests.yaml`
  carry the seeded application and its payload.

## Out of Scope

- Rendering a chart to discover what it creates. Infrahub does not run Helm, and
  nothing in this feature makes it do so.
- Workloads with no published chart. They were served by the manifests escape
  hatch and are deliberately no longer expressible; if one is needed later it is
  a new feature with its own justification.
- Any change to the lab repository's composite definitions or to the two
  applications the lab owns.
