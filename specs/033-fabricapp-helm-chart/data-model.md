# Phase 1 Data Model: Fabric Application as a Helm Chart

**Feature**: `033-fabricapp-helm-chart`
**File**: `schemas/service/kubernetes_services.yml`

All shapes below were validated against Infrahub 1.10.6 — see
[research.md](./research.md) R1 to R7.

---

## ServiceFabricApp — changed

### Attributes

| Attribute | Kind | Before | After | Note |
| --- | --- | --- | --- | --- |
| `chart_repository` | Text | `optional: true` | **`optional: false`** | R1: data must be populated first |
| `chart_name` | Text | `optional: true` | **`optional: false`** | |
| `chart_version` | Text | `optional: true` | **`optional: false`** | XRD requires all three together |
| `chart_values` | JSON | `optional: true` | unchanged | Inline escape hatch, file wins |
| `manifests` | JSON | `optional: true` | **removed** | `state: absent`, then deleted (R3) |

No attribute is added. `order_weight` 1440, freed by `manifests`, is left unused
rather than reassigned (FR-015).

Everything else on the node — `namespace_name`, `exposed`, `service_selector`,
`communities`, the six `policy_*` fields, `workload_selector`, `vip_block_size`,
`vip_block_managed` — is untouched.

### Relationships

| Relationship | Peer | Kind | Card. | Before | After |
| --- | --- | --- | --- | --- | --- |
| `advertised_services` | `SecurityService` | Generic | many | — | **added** |
| `manifests_file` | `ServiceFabricAppManifestsFile` | Component | one | present | **removed** |
| `values_file` | `ServiceFabricAppValuesFile` | Component | one | present | unchanged |
| `cluster`, `vrf`, `vip_block`, `allowed_source_prefixes`, `peering_service` | | | | | unchanged |

### The added relationship

```yaml
- name: advertised_services
  peer: SecurityService
  label: Advertised Services
  kind: Generic
  cardinality: many
  optional: true
  on_delete: no-action
  description: "Services this application's VIP answers on; a grant permits these"
  identifier: service__app_advertised_services
  order_weight: 945
```

Each field is a decision, not a default:

- **`kind: Generic`** — a plain reference. `Attribute` is the "belongs to"
  flavour and pairs with `cardinality: one`; `Component` would mean the
  application *owns* `junos-http`. This mirrors `allowed_source_prefixes`, the
  other cardinality-many reference on this node to objects it does not own.
- **`cardinality: many`** and **`optional: true`** — both are the schema
  defaults, stated explicitly because relationship defaults invert the attribute
  ones and reading them as attribute defaults gives the opposite meaning.
- **`on_delete: no-action`** — the only alternative, `cascade`, deletes the
  **peer**. Here that would mean deleting an application deletes `junos-http`,
  taking four hand-written baseline rules with it.
- **`peer: SecurityService`**, not `SecurityGenericService` — the generic also
  covers `SecurityServiceRange` and `SecurityServiceGroup`, neither of which has
  a single `port`, and the access generator works in integers throughout
  (FR-027).
- **No reverse side.** `SecurityService` gains nothing. A technical kind does not
  reference the service layer, and a bare `identifier` on one side is a
  one-directional reference, which is what this is.
- **`order_weight: 945`** — between `vip_block` (930) and `peering_service`
  (950), placing it with the exposure relationships it belongs to rather than
  with the payload attachments at 960/970.

**Measured** (R4): relating `nfd41-demo` to `junos-http` and reading it back
gives `('junos-http', 80, 'tcp')` — port and protocol from one hop — and leaves
the service object byte-identical.

---

## ServiceFabricAppValuesFile — unchanged

`CoreFileObject`, `human_friendly_id: [app__name__value]`,
`uniqueness_constraints: [["app"]]`, `app` as `kind: Parent, cardinality: one,
optional: false` with identifier `fabricapp__values_file`.

It becomes the only payload attachment a fabric application has. It cannot be
removed alongside the manifests file: a JSON attribute whose keys contain dots or
slashes cannot be seeded through the object-load path, and Helm values are full
of both.

---

## ServiceFabricAppManifestsFile — removed

Removed with `state: absent` on the node, then deleted from the YAML (R3).

**The two existing file objects must be deleted first.** The schema load removes
the kind whether or not instances exist (R2), which leaves them unreachable
rather than demonstrably gone — and once the kind is absent there is no way to
query for what remains. Two exist today:

| Object | Owner |
| --- | --- |
| `nfd41-demo-manifests.yaml` | the seeded application |
| `podinfo-manifests_file.yaml` | an application created through the portal |

The second is the one a migration written from `objects/` alone would miss.

---

## SecurityService — referenced, not changed

Defined in `schemas/security/security.yml`. One `name`, one `port` (Number), one
`ip_protocol` (`SecurityIPProtocol`, cardinality one, optional).

This feature gives it an incoming reference and changes nothing about it. The
three seeded instances relevant here:

| Name | Port | Protocol |
| --- | --- | --- |
| `junos-http` | 80 | tcp |
| `junos-https` | 443 | tcp |
| `junos-ping` | 0 | icmp |

It is already what a `SecurityPolicyRule` names in `destination_services`, which
is what makes the application's advertised port and the rule's permitted port the
same object rather than two numbers that have to agree.

---

## Validation rules

| ID | Rule | Enforced by |
| --- | --- | --- |
| V1 | An application names a chart repository, name and version | Schema (`optional: false`) |
| V2 | An application cannot carry raw manifests | Schema (kind and fields absent) |
| V3 | Values may be inline or attached; attached wins | Renderer, documented in the field description |
| V4 | A named service is never modified by naming it | Measured, R4 |
| V5 | A named service resolves to a port and a protocol | Measured, R4 |
| V6 | Deleting an application never deletes a named service | Schema (`on_delete: no-action`) |
| V7 | An exposed application naming no services is distinguishable from one naming none | Relationship is optional and empty-readable |

V7 is the one with no schema enforcement and is deliberate: the schema permits
it, and the consumer refuses. An exposed application with no named services is a
legitimate intermediate state while a request is being filled in; it is only an
error at the point a grant needs a port, which is where the refusal already
lives.

---

## Migration order

The order is forced by R1 and R2 and inverts `invoke load`'s schema-then-objects
sequence:

1. Populate the three chart fields on **every** existing `ServiceFabricApp`,
   including ones not in `objects/`.
2. Delete every `ServiceFabricAppManifestsFile` instance.
3. Load the schema carrying `state: absent` and the mandatory chart fields.
4. Verify the kind, attribute and relationship are gone and the new relationship
   is present.
5. Delete the `state: absent` blocks from the YAML.
6. Regenerate `protocols.py` and verify it names no manifests kind.

A fresh instance skips 1 and 2 because it has no data, and step 5's result is the
correct schema for it, so the finally-committed YAML is right for both a rebuild
and an in-place upgrade.

---

## Seeded application after the change

```yaml
name: nfd41-demo
chart_repository: https://cowboysysop.github.io/charts/
chart_name: whoami
chart_version: "6.0.0"          # app version 1.11.0 = traefik/whoami:v1.11.0
advertised_services:
  - junos-http                  # 80/tcp, already seeded
```

with values carrying `service.type: LoadBalancer`,
`commonLabels: {nfd41.lab/advertise: "true"}` so the Service is selected by
`service_selector`, and `replicaCount: 3` to keep pod-to-pod traffic crossing the
fabric.

Chart port 80 is what keeps `junos-http` applicable and the rendered firewall
artifact unchanged (SC-008). The backend tier and the two L7 policies are
knowingly dropped — see research R5.
