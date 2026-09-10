# Schema Specification: Application File Attachments

> **Workflow type**: Infrahub Schema (data model)
> **Skill**: Use the `infrahub-managing-schemas` skill to implement this specification.

**Feature Branch**: `013-app-file-attachments`
**Created**: 2026-09-10
**Status**: Draft
**Input**: User description: "okay let's store the chart values as infrahub object attachments we could do that right?"

Yes. `CoreFileObject` is described by the API as *"A file object for storing and managing file attachments"*, and this repository already uses it twice — `AvdHostvarFile` and `AvdStructuredConfigFile`. This cycle applies the same mechanism to application payloads, so that cycle 014 can render a `FabricApp` manifest without those payloads being stored as JSON attributes.

## Why this cycle exists

`ServiceFabricApp` currently stores two large payloads as JSON attributes: `chart_values` (Helm values) and `manifests` (an array of whole Kubernetes objects). Both are the wrong shape for an attribute, for three separate reasons found by inspection rather than assumed:

1. **They cannot be seeded.** `infrahubctl object load` returns HTTP 500 for a JSON key containing a dot or a slash. Kubernetes payloads are made of such keys — `app.kubernetes.io/name`, `nfd41.lab/advertise`, `grafana.ini`, `node-role.kubernetes.io/control-plane`. Verified on this instance in both directions: the GraphQL mutation path handles the same payload correctly, so the defect is in the object-load path, not in Infrahub's JSON handling.
2. **They are large and opaque.** `20-observability.yaml`'s chart values alone are roughly 150 lines of nested Helm configuration — Prometheus scrape configs, affinity rules, probe timings. None of it is network intent, and none of it is a thing the fabric has an opinion about.
3. **They are human-authored.** Values files are iterated on and argued about in review. A JSON attribute gives no line-by-line diff.

An attachment fixes all three. The payload becomes a file with its own checksum, the seeding path becomes an upload rather than an attribute write, and the source stays a reviewable YAML file in the repository.

**The alternative considered and rejected** was storing a path in Infrahub and having the transform read the file from the repository checkout at render time. It works — transforms already run from a checkout — but it moves the artifact's inputs outside the graph, so "an unchanged model renders an unchanged artifact" stops being strictly true. That property is what cycles 011 and 012 spent their evidence on, and it is worth keeping.

## Why both fields, not just chart values

The request named chart values. Covering only those would leave the most important seed unbuildable: **`10-demo.yaml` has no chart at all** — it is entirely `manifests`, and it is the richest oracle cycle 014 has. `20-observability.yaml` has both. So the two fields share one problem and need one solution.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An application's payload is stored as a file (Priority: P1) 🎯 MVP

An operator models an application whose deployment payload — Helm values, raw manifests, or both — is too large and too Kubernetes-shaped to belong in an attribute. The payload is attached to the application as a file.

**Why this priority**: Nothing else in this cycle or the next works without it.

**Independent Test**: Load the schema and confirm a file object can be attached to a `ServiceFabricApp` and read back with its checksum.

**Acceptance Scenarios**:

1. **Given** the schema is loaded, **When** a file is attached to an application, **Then** it carries `file_name`, `file_size`, `file_type` and `checksum`, and its content is retrievable
2. **Given** an application, **When** its files are queried, **Then** each is identifiable by the role it plays — chart values or manifests
3. **Given** an attached file, **When** the same content is uploaded again, **Then** the checksum is unchanged, so an unchanged payload is distinguishable from a changed one
4. **Given** an application is deleted, **When** its files are queried, **Then** they do not survive it as orphans

---

### User Story 2 - The payload stops being an attribute (Priority: P2)

The existing `chart_values` and `manifests` JSON attributes remain for small inline payloads, but they are no longer the only way to express a payload, and they are no longer the way a large one is expressed.

**Why this priority**: P2 because the attachment can exist alongside them. It matters for coherence — two mechanisms for one thing needs a stated rule about which wins.

**Acceptance Scenarios**:

1. **Given** an application with both an attached values file and a `chart_values` attribute, **When** the model is read, **Then** the precedence between them is unambiguous
2. **Given** an application with neither, **When** the model is read, **Then** that is a valid state, because an application may be manifests-only or chart-only

---

### Edge Cases

- **An application with two files of the same role.** Two values files is not a meaningful state.
- **A file attached to no application.** The file object should not be creatable in isolation, or should be cleaned up.
- **A payload that is valid YAML but not valid Kubernetes.** Out of scope for the schema; the cluster rejects it.
- **A very large file.** Helm values for a large chart can reach hundreds of kilobytes.
- **The seeding script runs twice with unchanged content.** Must not produce a second file or a new checksum.
- **The committed source file and the attached copy drift** because someone edited the file and did not re-run the seeding.

## Requirements *(mandatory)*

### Functional Requirements

**The file kind**:

- **FR-001**: A new node kind MUST exist that inherits `CoreFileObject`, so it carries `file_name`, `file_size`, `file_type`, `checksum` and `storage_id` without redeclaring them
- **FR-002**: The kind MUST belong to the `Service` namespace, matching the layer it serves
- **FR-003**: The kind MUST have a mandatory `Parent` relationship to `ServiceFabricApp`, so a file cannot exist without the application it belongs to
- **FR-004**: The kind MUST record which **role** the file plays, from a closed set covering chart values and manifests
- **FR-005**: The kind MUST be unique on the application and role together, so one application cannot hold two values files
- **FR-006**: The kind MUST have a human-friendly id derived from the application and the role
- **FR-007**: The kind MUST NOT appear in the menu as a top-level entry; it is reached through its application, matching `AvdHostvarFile`

**The application side**:

- **FR-008**: `ServiceFabricApp` MUST gain a relationship to its files, cardinality many, optional
- **FR-009**: The relationship MUST be a `Component`, so deleting an application removes its files rather than orphaning them
- **FR-010**: The existing `chart_values` and `manifests` JSON attributes MUST be retained, as an inline escape hatch for payloads small enough not to need a file

**Precedence**:

- **FR-011**: The model MUST make it unambiguous which source wins when both an attached file and the corresponding attribute are set, and that rule MUST be stated in the schema description so a consumer does not have to guess

**Compatibility**:

- **FR-012**: The change MUST be additive: no existing kind loses a field, and no loaded object becomes invalid
- **FR-013**: The change MUST NOT alter `ServiceFabricPeering`, `ClusterFabricPeering`, or anything the cycle 011 transform and cycle 012 generator read, so their artifacts and checksums are untouched

### Key Entities

- **`ServiceFabricApp`** (extended): gains a relationship to its attached files. Keeps all 16 attributes and 5 relationships it has today.
- **The new file kind**: inherits `CoreFileObject`; carries a role and a parent application. Holds the payload itself in object storage, not in the graph.
- **`CoreFileObject`** (inherited): supplies `file_name`, `file_size`, `file_type`, `checksum`, `storage_id`. The checksum is what makes an unchanged payload cheap to detect.

### Key Files

| File | Purpose |
| --- | --- |
| `schemas/service/kubernetes_services.yml` | The new kind and the relationship on `ServiceFabricApp` |
| `tests/unit/test_service_layer_schema_contract.py` | Contract assertions for the new kind |
| `src/solution_arista_avd/protocols.py` | Regenerated, never hand-edited |

## Success Criteria *(mandatory)*

- **SC-001**: The schema loads with no validation error, and the diff adds exactly one kind and one relationship
- **SC-002**: A file can be attached to an application, and its content read back byte-for-byte
- **SC-003**: Re-uploading identical content leaves the checksum unchanged, so an unchanged payload is detectable without downloading it
- **SC-004**: Attaching a second file of the same role to one application is rejected
- **SC-005**: Deleting an application removes its attached files
- **SC-006**: A payload containing keys with dots and slashes round-trips unchanged — this is the defect that motivated the cycle
- **SC-007**: A payload of at least 150 lines of nested YAML round-trips unchanged
- **SC-008**: Every existing contract test still passes, and the `crossplane_fabric_peering` artifact's checksum is unchanged
- **SC-009**: All unit tests and the repository's linters pass

## Assumptions

1. **`CoreFileObject` is the right mechanism**, on the evidence that Infrahub describes it as being for file attachments and that this repository already uses it twice for exactly this shape of problem.
2. **Content arrives through a committed seeding script**, chosen over a generator sync and over manual upload. `infrahubctl object load` cannot upload file content — the repository's existing file objects are all created by code.
3. **The source of truth for authoring is a committed YAML file.** The attachment is the copy the transform reads. This keeps line-by-line review in git while keeping the artifact's inputs inside the graph.
4. **Existing `CoreFileObject` usage in this repository is generated content**, not human-authored. This cycle is the first human-authored use, which is why assumption 3 matters.
5. **The seeding script is idempotent** and safe to re-run, using the checksum comparison the repository's `save_file_if_changed` helper already implements.
6. **Cycle 014 renders from the attachment**, and is out of scope here.

## Out of Scope

- **The `FabricApp` transform.** It is the next cycle, and its draft specification is already written; this cycle exists so that it can be seeded.
- **The seeding script itself.** It is code, not schema, and belongs with the cycle that needs it.
- **The `AppAccess` transform**, which has an XRD but no hand-written instance to validate a render against.
- Removing the `chart_values` and `manifests` attributes. They stay as an inline escape hatch.
- Any change to the peering service, its generator, or its artifact.
- Modelling the contents of a payload as first-class objects. They are Kubernetes' contract.
- The AVD pipeline and the EOS rendering path.

## Dependencies

- Cycle 010's `ServiceFabricApp` — merged.
- `CoreFileObject`, present in Infrahub 1.10.6 and already inherited twice in this repository.
- `save_file_if_changed` in `src/solution_arista_avd/generator.py`, the existing checksum-comparing upload helper.
