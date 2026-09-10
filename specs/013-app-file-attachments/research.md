# Phase 0 Research: Application File Attachments

**Feature**: `specs/013-app-file-attachments` | **Date**: 2026-09-10

Six decisions, resolved against the `infrahub-managing-schemas` skill, this repository's
existing `CoreFileObject` usage, and the live instance. No NEEDS CLARIFICATION items remain.

---

## R1 — Two kinds, not one kind with a role discriminator

**Decision**: `ServiceFabricAppValuesFile` and `ServiceFabricAppManifestsFile`, each with a
mandatory cardinality-one `Parent` to `ServiceFabricApp` and `uniqueness_constraints: [["app"]]`.

The spec sketched one kind carrying a role, reached through a cardinality-many relationship.
The repository's own precedent is the other shape, and it is better here:

```yaml
- name: HostvarFile
  namespace: Avd
  inherit_from: [CoreFileObject]
  human_friendly_id: ["artifact__name__value"]
  uniqueness_constraints: [["artifact"]]
  relationships:
    - name: artifact
      kind: Parent
      cardinality: one
      identifier: "avdartifact__hostvar_file"
```

Two kinds means the role is carried by the kind itself, so there is no dropdown to keep in
step, "one values file per application" falls out of cardinality one rather than needing a
composite constraint, and a consumer writes `app.values_file` instead of filtering a
collection by role. `AvdArtifact` holds exactly this pair — `hostvar_file` and
`structured_config_file` — for exactly this reason.

**Cost**: a third payload type later means a third kind rather than a new dropdown choice.
Acceptable, and it is the trade the repository has already made twice.

**Alternatives considered**: one kind + `role` dropdown + cardinality many — rejected as
above. A single generic `ServiceFile` reusable across service kinds — rejected as speculative
generality; no other service kind needs a payload today.

---

## R2 — The attachment wins over the attribute

**Decision**: When both an attached file and its corresponding JSON attribute are set, the
**attachment wins**, and the schema description says so.

FR-011 required this rule to exist and be stated, but deliberately left the direction open.
The attachment wins because it is the only one of the two that can express the payloads this
cycle exists for: `infrahubctl object load` cannot write a JSON attribute whose keys contain
a dot or a slash, and every real Kubernetes payload has such keys. A precedence rule that
favoured the attribute would make the attachment unreachable in exactly the cases it was
added for.

The attributes remain as an inline escape hatch for payloads small enough not to need a file,
and a consumer reads the attribute only when no file is attached.

**Alternatives considered**: attribute wins — rejected as above. Forbid both being set —
rejected because the schema cannot express a cross-field constraint, so it would be an
unenforceable rule rather than a guarantee; a check could enforce it later.

---

## R3 — Where the kinds live

**Decision**: `schemas/service/kubernetes_services.yml`, beside `ServiceFabricApp`.

`schemas/objects/objects.yml` holds the AVD artifact file kinds, but that file is the AVD
domain. Spec 010 established one file per service domain and these kinds belong to the
service that owns them. Putting them in `objects.yml` would also reintroduce the cross-domain
coupling 010's layering rule exists to prevent.

---

## R4 — Namespace and naming

**Decision**: Namespace `Service`; names `FabricAppValuesFile` and `FabricAppManifestsFile`,
giving kinds `ServiceFabricAppValuesFile` and `ServiceFabricAppManifestsFile`.

The namespace matches the layer, as `AvdHostvarFile` matches its own. The `File` suffix
matches the repository's existing file kinds and signals that the payload is not in the graph.
Relationship identifiers follow the skill's CRITICAL rule that both sides share one string:
`fabricapp__values_file` and `fabricapp__manifests_file`.

---

## R5 — Human-friendly id

**Decision**: `["app__name__value"]` on both kinds.

Matching `AvdHostvarFile`'s `["artifact__name__value"]`. The parent's name is unique, and each
application has at most one file of each kind, so the application name alone identifies the
file within its kind. The kind supplies the rest.

---

## R6 — How content gets in, and why the schema does not care

**Decision**: A committed seeding script using the SDK's file upload, out of scope here but
recorded because it constrains nothing in the schema.

`infrahubctl object load` cannot upload file content — every existing `CoreFileObject` in this
repository is created by generator code, using `save_file_if_changed` in
`src/solution_arista_avd/generator.py`, which checksums the new content, compares it against
`existing_file.download_file()`, and skips the upload when it matches. That helper is directly
reusable and is what makes SC-003 true.

The schema is unaffected by this choice, which is why the seeding script belongs to the cycle
that needs it rather than to this one.

---

## Risk register

| Risk | Mitigation |
| --- | --- |
| The change is not as additive as it looks and something downstream moves | The artifact checksum check: `0d800c9d5005b5fdb6b371bb5627d143` must be unchanged |
| A relationship identifier mismatch creates two one-way links instead of one | The skill's CRITICAL rule; asserted by a contract test on both sides |
| `CoreFileObject` cannot be inherited by a node in a non-Core namespace | Disproved by `AvdHostvarFile`, which does exactly that and is loaded |
| The precedence rule is stated but unenforceable | True and recorded in R2. A check could enforce it; the schema cannot |
