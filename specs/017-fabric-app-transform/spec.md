# Transform Specification: Crossplane FabricApp Manifest

> **Workflow type**: Infrahub Transform (data rendering)
> **Skill**: Use the `infrahub-managing-transforms` skill to implement this specification.

**Feature Branch**: `017-fabric-app-transform`
**Created**: 2026-09-11
**Status**: Draft
**Input**: "let's implement the transforms" — the `FabricApp` manifest, drafted during cycle 013 and unblocked by it.

## Transform Overview

**Approach**: Python
**Output Format**: YAML (a Crossplane composite resource; `application/yaml`)
**Target Nodes**: `ServiceFabricApp`

An application on the cluster is described twice today: as the `ServiceFabricApp` an operator
orders, and as a hand-written `FabricApp` manifest in `../lab/crossplane/apps/`. This renders
the second from the first, the way cycle 011 did for `FabricPeering`.

**Why Python.** Structured API resource, not a text config — the same reasoning as cycle 011's
R1a. The dumper decides quoting from the value's type, which matters more here because the
payload contains `"true"` label values, ports as strings, and keys that must survive verbatim.

## What cycles 013 and 016 changed about this cycle

The 013 draft of this spec carried two open questions. Both are now answered:

| Then | Now |
| --- | --- |
| How to seed JSON attributes with dotted keys, given `object load` returns HTTP 500 | Cycle 013 added `ServiceFabricAppManifestsFile` and `ServiceFabricAppValuesFile`, `CoreFileObject` attachments. The payload is a file, so the bug is bypassed rather than worked around |
| How much of the lab to model | One app, `nfd41-demo` — the richest oracle, and the only one whose payload is `manifests` rather than a Helm chart |

## Verified before writing this spec

| Fact | Result |
| --- | --- |
| The three `policy.allowFrom` prefixes exist | ✅ `10.210.0.0/24`, `10.60.0.0/16`, `10.70.0.0/24` in `objects/29` |
| VRF `K8S_PROD` exists, matching the XRD's `tenant: k8s-prod` default | ✅ `objects/24` |
| The VIP block `10.112.240.0/28` exists | ❌ **absent** — this cycle must create it |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An ordered application renders as its manifest (Priority: P1) 🎯 MVP

An operator orders an application — a namespace, a workload, a VIP, and the policy governing
who may reach it — and the manifest the cluster consumes is rendered from that order.

**Independent Test**: Render against the seeded app and compare with `10-demo.yaml`.

**Acceptance Scenarios**:

1. **Given** a seeded `ServiceFabricApp`, **When** the transform runs, **Then** it renders `apiVersion: nfd41.lab/v1alpha1`, `kind: FabricApp`, and a `spec` the XRD accepts
2. **Given** the same object unchanged, **When** rendered twice, **Then** the two renders are byte-identical
3. **Given** an app with a manifests attachment, **When** rendered, **Then** `spec.manifests` carries the attachment's content
4. **Given** an app with neither a chart nor manifests, **When** rendered, **Then** it fails naming the object — a FabricApp that deploys nothing is a namespace and a policy with no workload

---

### User Story 2 - The rendered manifest matches the hand-written one (Priority: P1) 🎯 MVP

**Why this priority**: Equal to US1. A transform that renders a *different* policy is an
unreviewed change to which CIDRs may reach a live workload.

**Acceptance Scenarios**:

1. **Given** the render and `10-demo.yaml`, **When** compared field by field, **Then** every shared field is equal
2. **Given** `policy.allowFrom`, **When** compared, **Then** the CIDRs match exactly — this list is a security control and a silent change to it is the most damaging error this transform can make
3. **Given** a difference, **When** examined, **Then** it is a field the render adds carrying the XRD's own default, never a differing value

---

### User Story 3 - The attachment is the source, and its absence is loud (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an app with both an attachment and the inline `manifests` attribute, **When** rendered, **Then** the attachment wins — the precedence cycle 013 documented
2. **Given** an app with only the inline attribute, **When** rendered, **Then** the attribute is used
3. **Given** an attachment whose content is not valid YAML, **When** rendered, **Then** it fails naming the app rather than emitting a broken manifest

---

### Edge Cases

- **`exposed` is false.** `spec.expose` must be omitted, not emitted with a null `vipBlock`.
- **Exposed with no `vip_block`.** The XRD requires `vipBlock` under `expose`; incoherent, must fail.
- **An empty `policy`.** The XRD defaults the whole object, so emitting `policy: {}` could override a default.
- **Selector values that look like booleans.** `nfd41.lab/advertise: "true"` must stay a string.
- **Ports.** `allowFromPorts[].port` is a string in the XRD, not an integer.
- **A chart and manifests together.** `20-observability.yaml` has both, so this is normal.

## Requirements *(mandatory)*

**Query**:

- **FR-001**: A `.gql` co-located in `transforms/` resolving one `ServiceFabricApp` by name, aliased `target:`
- **FR-002**: It MUST fetch every attribute the XRD consumes, plus `cluster`, `vrf`, `vip_block`, `allowed_source_prefixes`, and both attachment relationships
- **FR-003**: Responses MUST be consumed through generated typed models
- **FR-004**: `__typename` MUST be selected at every union point, including nested relationship nodes — cycle 016 found the generator needs it in both places

**Rendering**:

- **FR-005**: `apiVersion: nfd41.lab/v1alpha1`, `kind: FabricApp`
- **FR-006**: `metadata.name` from the service's own name — the application *is* the resource, unlike cycle 011's cluster-scoped peering
- **FR-007**: `spec.namespace` from `namespace_name`, required
- **FR-008**: `spec.tenant` from the VRF's name, lower-cased to match the XRD's `k8s-prod` default
- **FR-009**: `spec.chart` when a chart is set, carrying `repository`, `name`, `version`, `values`
- **FR-010**: `spec.manifests` from the attachment when present, else the inline attribute
- **FR-011**: `spec.expose` only when exposed, carrying `vipBlock` from the prefix and `serviceSelector` parsed from the `key=value` list
- **FR-012**: `spec.policy` carrying the five booleans, `allowFrom` from the allowed source prefixes, `allowFromPorts`, and `workloadSelector`
- **FR-013**: Selector lists MUST be parsed into label maps, as cycle 011 does
- **FR-014**: Label values and ports MUST render as strings; `true` MUST NOT become a boolean
- **FR-015**: Unset optional fields MUST be omitted so the XRD's defaults apply
- **FR-016**: Rendering MUST be deterministic — an unchanged model renders byte-identically

**Validation**:

- **FR-017**: MUST fail naming the object and field when no target matches, there is no namespace, it is exposed with no VIP block, it has neither chart nor manifests, or an attachment's content is unparseable

**Seeding**:

- **FR-018**: Object data MUST create the VIP prefix `10.112.240.0/28`, which does not exist
- **FR-019**: Object data MUST seed one `ServiceFabricApp` for the demo application
- **FR-020**: The manifests payload MUST be committed as a reviewable YAML file and uploaded to the attachment by a committed script, since `object load` cannot upload file content
- **FR-021**: The seeding script MUST be idempotent, using the checksum comparison `save_file_if_changed` already implements

**Registration**:

- **FR-022**: Query, transform and artifact definition registered in `.infrahub.yml` with `content_type: application/yaml`
- **FR-023**: The artifact definition MUST target a group containing the application services

## Success Criteria *(mandatory)*

- **SC-001**: The transform renders a `FabricApp` for the seeded app without error
- **SC-002**: The render satisfies the XRD — required fields present, types correct
- **SC-003**: Compared field by field with `10-demo.yaml`, **zero shared fields differ**
- **SC-004**: Two renders of an unchanged model are byte-identical
- **SC-005**: `policy.allowFrom` matches the hand-written CIDR list exactly
- **SC-006**: Every label value and port renders as a string
- **SC-007**: An incomplete model fails naming the object and the field
- **SC-008**: The seeding script is idempotent — running it twice leaves one attachment with one checksum
- **SC-009**: The artifact is generated with content type `application/yaml` and a stable checksum
- **SC-010**: The `crossplane_fabric_peering` artifact checksum is unchanged — this cycle must not disturb cycles 011–015
- **SC-011**: All unit tests and the repository's linters pass

## Assumptions

1. **The XRD is the contract.** `../lab/crossplane/apps/00-xrd-fabric-app.yaml`, group `nfd41.lab`, version `v1alpha1`.
2. **`10-demo.yaml` is the regression oracle**, as `10-peering.yaml` was for cycle 011.
3. **`manifests` and `chart_values` are opaque passthrough** — stored and emitted, never interpreted.
4. **The attachment wins over the attribute**, per cycle 013's documented precedence.
5. **Delivery is unchanged** — artifacts reach the cluster through Vidra.

## Out of Scope

- The `AppAccess` transform. Its XRD exists but no hand-written instance does, so there is no oracle. A separate cycle whose first task is establishing one.
- Modelling `manifests` contents as first-class objects. They are Kubernetes' contract.
- Seeding `nfd41-observability` or `nfd41-access`. One app proves the transform; the second would mostly add an opaque Helm blob, and the third contains a committed password.
- Any schema change. Cycle 013 added what this needs.
- The AVD pipeline and the EOS rendering path.
