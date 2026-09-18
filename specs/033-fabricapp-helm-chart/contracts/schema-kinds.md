# Contract: Schema Kind Surface

**Feature**: `specs/033-fabricapp-helm-chart` | **Date**: 2026-09-18

A schema feature's external interface is the set of kinds it publishes and the
graph invariants they guarantee. Everything downstream — the `crossplane_fabric_app`
transform, `generate-app-access`, the two portals, the seeding script and the
generated protocols — is written against this surface.

This cycle **narrows** the surface published by cycle 013 and cycle 010.

## 1. Withdrawn kinds (1)

| Kind | Was reached as | Replacement |
| --- | --- | --- |
| `ServiceFabricAppManifestsFile` | `ServiceFabricApp.manifests_file` | none — an application is a chart |

Consumers must stop naming this kind. After the load it is not merely empty, it
does not resolve: `SchemaNotFoundError: Unable to find the schema
'ServiceFabricAppManifestsFile'` (measured, research R2).

## 2. Withdrawn fields on `ServiceFabricApp` (2)

| Field | Kind | Replacement |
| --- | --- | --- |
| `manifests` | JSON attribute | none |
| `manifests_file` | relationship, Component/one | none |

## 3. Tightened fields on `ServiceFabricApp` (3)

| Field | Was | Is | Consumer effect |
| --- | --- | --- | --- |
| `chart_repository` | optional | **mandatory** | may be read without a null check |
| `chart_name` | optional | **mandatory** | may be read without a null check |
| `chart_version` | optional | **mandatory** | may be read without a null check |

In generated protocols these move from `StringOptional` to `String` (measured,
research R3). A renderer no longer needs the "chart or manifests?" branch: a
chart is always present and always complete.

## 4. Published field on `ServiceFabricApp` (1)

```yaml
advertised_services:
  peer: SecurityService
  kind: Generic
  cardinality: many
  optional: true
  on_delete: no-action
  identifier: service__app_advertised_services
```

In generated protocols: `advertised_services: RelationshipManager[SecurityService]`.

### Guarantees

| # | Guarantee | Basis |
| --- | --- | --- |
| G1 | Each named service resolves to a `port` (Number) and an `ip_protocol` | Measured: `('junos-http', 80, 'tcp')` |
| G2 | Naming a service never modifies it | Measured: name, description and port identical before and after |
| G3 | Deleting an application never deletes a named service | `on_delete: no-action` |
| G4 | An application may name zero services, and zero is readable as zero | `optional: true`, cardinality many |
| G5 | A named service is never marked `managed_by_service` by this relationship | Nothing writes it; G2 |
| G6 | Every peer has exactly one port | `peer` is `SecurityService`, not the generic |

G5 is what makes revocation safe without a name comparison: `_delete_orphans` in
`generate-app-access` deletes only what it marked, and this relationship marks
nothing.

### Non-guarantees

- **A named service need not be referenced by any policy rule.** A new port's
  service object exists before the first grant that uses it. This is the ordinary
  case, not an error.
- **Nothing prevents deleting a `SecurityService` an application names.**
  `on_delete: no-action` is one-directional; the application is then left naming
  nothing where it named something. Detecting that belongs to a check, not to a
  schema constraint.
- **The schema does not require an exposed application to name a service.** See
  V7 in [data-model.md](../data-model.md): the refusal lives where a port is
  actually needed.

## 5. Unchanged, and depended upon

| Kind / field | Why it is named here |
| --- | --- |
| `ServiceFabricAppValuesFile` | Now the only payload attachment; `values_file` unchanged |
| `ServiceFabricApp.chart_values` | Inline values retained; the attachment still wins |
| `SecurityService` | Referenced only. No attribute, relationship or constraint added |
| `SecurityPolicyRule.destination_services` | Already peers `SecurityService`; this is what makes the application's port and the rule's port one object |

## 6. Consumer migration

| Consumer | Change required |
| --- | --- |
| `transforms/crossplane_fabric_app.py` | Drop the manifests branch and the `not chart and not manifests` refusal; render `spec.chart` unconditionally |
| `transforms/crossplane_fabric_app.gql` | Remove `manifests` and `manifests_file` |
| `generators/generate_app_access.py` | Replace `advertised_service_ports` / `_selector_labels` with a read of `advertised_services`; `index_tcp_services` no longer adopts for a default grant |
| `generators/generate_app_access.gql` | Remove `manifests`; add `advertised_services` with `port` and `ip_protocol` |
| `scripts/seed_app_payloads.py` | Drop the `ServiceFabricAppManifestsFile` entry |
| `backstage/plugins/infrahub-backend/src/provider.ts` | Drop the manifests `_content` textarea; keep values |
| `service_catalog/pages/6_Deploy_Application.py` | Collect chart fields instead of manifests |
| `objects/36_nfd41_app_services.yml` | Chart fields plus `advertised_services: [junos-http]` |
| `payloads/nfd41-demo-manifests.yaml` | Deleted; a values payload replaces it |

Any code calling `RelationshipManager.add()` on `advertised_services` must
`await ...fetch()` first, or it raises `UninitializedError` (research R4).
