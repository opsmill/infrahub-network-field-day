# Data Model: Application Catalogue

## ServiceApplicationDefinition (new, `schemas/catalogue/application_catalogue.yml`)

Not a service instance: it inherits neither `ServiceGeneric` nor `GeneratorTarget`, belongs to no generator group, has no status lifecycle beyond `active` and `deprecated`.

| Field | Kind | Required | Notes |
| --- | --- | --- | --- |
| `name` | Text, unique | yes | HFID. Slug such as `whoami`. |
| `title` | Text | yes | Title shown in the picker and the menu, such as "Who am I". Used as `display_label`. |
| `description` | Text | no | Shown on the portal catalogue entity. |
| `chart_repository` | Text | yes | |
| `chart_name` | Text | yes | |
| `chart_version` | Text | yes | |
| `default_values` | TextArea | no | YAML text. Never JSON (HTTP 500 for keys with a dot or slash). |
| `default_vip_block_size` | Number | yes, default 28 | `min_value` 24, `max_value` 30 as on the application. |
| `default_service_selector` | List | no | `key=value` strings. |
| `requestable` | Boolean | yes, default false | Never offered unless true. |
| `status` | Dropdown | yes, default `active` | `active`, `deprecated`. Only `active` is requestable. |
| `default_advertised_services` | Relationship to `SecurityService`, many | no | `on_delete: no-action`. |
| `applications` | Relationship to `ServiceFabricApp`, many, inverse of `definition` | no | Read-only in practice. |

Uniqueness: `name__value`. `order_by`: `name__value`.

## ServiceFabricApp (extended, `schemas/service/kubernetes_services.yml`)

| Field | Kind | Notes |
| --- | --- | --- |
| `definition` | Relationship to `ServiceApplicationDefinition`, one, optional | `on_delete: no-action`. Not watched. |
| `definition_pinned` | Boolean, optional, default false | Write-back. Set true in the same save as the chart fields. Never set by hand except in seed data. Not watched. |

## State transitions of pinning

```text
created (definition set, definition_pinned false)
   -- generate-fabric-app, build path -->
pinned (chart_*, selector/advertised if empty set; definition_pinned true; values file attached if default_values non-empty)
   -- any later run, any catalogue edit --> unchanged
```

No definition: the generator returns immediately; behaviour is as before. Withdrawn status: never pinned.
